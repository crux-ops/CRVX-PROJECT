"""kliktahu/observabilitas.py - JEJAK AUDIT & OBSERVABILITAS (tahap 12 rencana upgrade 2026-09).

Satu run analisis harus bisa DIPERIKSA ULANG: apa yang dicari, sumber mana yang menjawab & mana yang gagal,
berapa lama, berapa kuota yang dipakai, dan kenapa mesin memilih topik itu. Modul ini menyimpan jejaknya:

* run id (bisa diisi dari basis data bila ada) + waktu mulai/selesai + durasi per tahap
* status tiap sumber (lihat kesegaran.py) dan alasan kegagalan
* pemakaian kuota/biaya per sumber (mis. YouTube Data API = 100 unit per search.list)
* keputusan & alasannya (ringkas, agar bisa dibaca pemilik)
* audit trail ke berkas JSONL (append-only) untuk dibandingkan antar run

RAHASIA TIDAK PERNAH DICATAT: semua teks yang masuk lewat `catat()` disanitasi (parameter kunci/token,
URL dengan userinfo, dan nilai variabel lingkungan yang dikenal sebagai kunci API).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import time
import uuid
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from . import kesegaran as G

UTC = dt.UTC
_PARAM_RAHASIA = {
    "key",
    "api_key",
    "apikey",
    "token",
    "access_token",
    "authorization",
    "x-subscription-token",
    "client_secret",
    "refresh_token",
    "password",
    "passwd",
    "secret",
}
# biaya relatif per panggilan (unit kuota resmi bila ada; 1 = gratis/umum)
BIAYA_SATUAN: dict[str, float] = {
    "pesaing_youtube": 100.0,  # YouTube Data API search.list = 100 unit
    "web_brave": 1.0,
    "web_searxng": 0.0,
}


def redaksi_url(url: str) -> str:
    try:
        b = urlsplit(str(url))
    except ValueError:
        return "<url tidak bisa diurai>"
    q = [(k, "<rahasia>" if k.lower() in _PARAM_RAHASIA else v) for k, v in parse_qsl(b.query, keep_blank_values=True)]
    netloc = b.netloc.rsplit("@", 1)[-1]
    return urlunsplit((b.scheme, netloc, b.path, urlencode(q), ""))


def redaksi(nilai: Any, nama_env_rahasia: Sequence[str] = ()) -> Any:
    """buang rahasia dari nilai apa pun sebelum dicatat/ditulis."""
    if isinstance(nilai, Mapping):
        return {
            k: ("<rahasia>" if str(k).lower() in _PARAM_RAHASIA else redaksi(v, nama_env_rahasia))
            for k, v in nilai.items()
        }
    if isinstance(nilai, (list, tuple)):
        return [redaksi(v, nama_env_rahasia) for v in nilai]
    if isinstance(nilai, str):
        s = nilai
        for env in nama_env_rahasia:
            v = os.environ.get(env, "").strip()
            if v and len(v) >= 8 and v in s:
                s = s.replace(v, "<rahasia>")
        s = re.sub(r"((?:https?|ftp)://[^\s/?#]*@)", "https://<rahasia>@", s)  # userinfo
        s = re.sub(rf"(?i)\b({'|'.join(sorted(_PARAM_RAHASIA))})\b\s*[=:]\s*\S+", r"\1=<rahasia>", s)
        return s
    return nilai


@dataclass
class Peristiwa:
    waktu: str
    jenis: str
    data: dict[str, Any] = field(default_factory=dict)

    def baris(self) -> dict[str, Any]:
        return {"waktu": self.waktu, "jenis": self.jenis, **self.data}


@dataclass
class Jejak:
    """pengumpul jejak satu run. Dipakai analisis.py dan CLI."""

    run_id: str = ""
    nama: str = "analisis"
    mulai: dt.datetime = field(default_factory=lambda: dt.datetime.now(UTC))
    peristiwa: list[Peristiwa] = field(default_factory=list)
    kuota: Counter = field(default_factory=Counter)
    status: dict[str, G.Status] = field(default_factory=dict)
    keputusan: dict[str, Any] = field(default_factory=dict)
    selesai: dt.datetime | None = None

    def __post_init__(self) -> None:
        if not self.run_id:
            self.run_id = f"{self.mulai:%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:6]}"

    # --------------------------------------------------------------------------------------- catat
    def catat(self, jenis: str, **data: Any) -> None:
        self.peristiwa.append(Peristiwa(dt.datetime.now(UTC).isoformat(), jenis, redaksi(dict(data))))

    def galat(self, jenis: str, galat: BaseException | str, **data: Any) -> None:
        self.catat(
            f"galat.{jenis}",
            galat=f"{type(galat).__name__}: {galat}" if isinstance(galat, BaseException) else str(galat),
            **data,
        )

    def sumber(self, status: G.Status) -> None:
        self.status[status.jenis] = status
        self.catat("sumber", data=status.baris())

    def banyak_sumber(self, daftar: Sequence[G.Status]) -> None:
        for s in daftar:
            self.sumber(s)

    def pakai(self, sumber: str, n: int = 1) -> None:
        self.kuota[sumber] += n
        self.catat("kuota", sumber=sumber, n=n, biaya=BIAYA_SATUAN.get(sumber, 0.0) * n)

    def putus(self, **keputusan: Any) -> None:
        self.keputusan = redaksi(dict(keputusan))
        self.catat("keputusan", **self.keputusan)

    @contextmanager
    def tahap(self, nama: str, **data: Any) -> Iterator[None]:
        t0 = time.perf_counter()
        self.catat("mulai." + nama, **data)
        try:
            yield
        except Exception as e:
            self.galat(nama, e)
            raise
        finally:
            self.catat("selesai." + nama, detik=round(time.perf_counter() - t0, 3))

    def tutup(self) -> None:
        self.selesai = dt.datetime.now(UTC)

    # --------------------------------------------------------------------------------------- laporan
    @property
    def durasi(self) -> dt.timedelta:
        return (self.selesai or dt.datetime.now(UTC)) - self.mulai

    @property
    def durasi_detik(self) -> float:
        return self.durasi.total_seconds()

    def ringkas(self) -> dict[str, Any]:
        gagal = [p for p in self.peristiwa if p.jenis.startswith("galat.")]
        biaya = sum(BIAYA_SATUAN.get(s, 0.0) * n for s, n in self.kuota.items())
        return {
            "run_id": self.run_id,
            "nama": self.nama,
            "mulai": self.mulai.isoformat(),
            "selesai": self.selesai.isoformat() if self.selesai else None,
            "durasi_detik": round(self.durasi_detik, 3),
            "permintaan": int(sum(self.kuota.values())),
            "kuota_per_sumber": dict(self.kuota),
            "biaya_unit": round(biaya, 1),
            "status_sumber": {j: s.status for j, s in sorted(self.status.items())},
            "keyakinan_data": G.keyakinan_data(list(self.status.values())),
            "galat": [
                {"jenis": p.jenis, **{k: v for k, v in p.data.items() if k in ("galat", "sumber", "jenis")}}
                for p in gagal
            ],
            "keputusan": self.keputusan,
            "n_peristiwa": len(self.peristiwa),
        }

    def tabel_md(self) -> list[str]:
        r = self.ringkas()
        out = [
            f"- run_id: `{r['run_id']}` - durasi {r['durasi_detik']} s - {r['permintaan']} permintaan "
            f"(biaya {r['biaya_unit']:g} unit)",
            f"- keyakinan data (kesegaran sumber): {r['keyakinan_data']:.0%}",
        ]
        if r["status_sumber"]:
            out.append("- status sumber: " + ", ".join(f"{j}={s}" for j, s in r["status_sumber"].items()))
        for gg in r["galat"]:
            sumber = gg.get("sumber") or gg["jenis"].replace("galat.", "")
            alasan = str(gg.get("galat", ""))[:120]
            out.append(f"- GAGAL {sumber}: {alasan}")
        return out

    def tulis(self, path: Path | str) -> Path:
        """tulis audit trail JSONL (append). Rahasia sudah disanitasi saat dicatat."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"run": self.ringkas()}, ensure_ascii=False) + "\n")
            for e in self.peristiwa:
                f.write(json.dumps(e.baris(), ensure_ascii=False) + "\n")
        return p
