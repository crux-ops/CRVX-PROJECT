"""kliktahu/evaluasi.py - EVALUASI (tahap 11 rencana upgrade 2026-09).

Uji kualitas pipeline riset -> analisis -> metadata dengan dua jalur:

1. OFFLINE (bawaan, deterministik, AMAN untuk CI): kumpulan kasus di `data/evaluasi/kasus.jsonl` dijalankan
   dengan transport palsu (`riset/fixture.py`) lalu dinilai: relevansi topik, dukungan klaim oleh bukti kredibel,
   kesegaran sumber, kelengkapan metadata, dan biaya (waktu + jumlah permintaan).
2. LIVE (opsional, TIDAK pernah jalan otomatis): butuh `izin=True` DAN env `KLIKTAHU_LIVE=1`. Ini menyentuh
   layanan publik (Google/YouTube Autocomplete, Wikipedia, dll.) - jadi harus sengaja dihidupkan pemilik,
   tidak pernah di cron/CI (aturan GitHub & sopan santun ke server; lihat AGEN.md §3).

Yang TIDAK diukur modul ini: tayangan/retensi/CTR. Tidak ada data performa dalam evaluasi offline, jadi hasilnya
bukan ramalan sukses - hanya pemeriksaan bahwa mesin menjawab pertanyaan yang benar dengan bukti yang benar.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import kesegaran as G
from . import teks

AMBANG = {
    "relevansi": 0.70,  # topik terpilih harus mendekati topik yang diharapkan kasus
    "dukungan_klaim": 0.60,  # porsi klaim fakta yang didukung bukti kredibel
    "kesegaran": 0.80,  # porsi sumber yang masih segar (dalam TTL)
    "kelengkapan": 1.00,  # metadata lengkap (4 blok, lint draf bersih)
}
KASUS_BAWAAN = Path(__file__).resolve().parent.parent / "data" / "evaluasi" / "kasus.jsonl"


@dataclass
class Kasus:
    id: str
    kueri: str
    tema_diharapkan: tuple[str, ...] = ()
    frasa_wajar: tuple[str, ...] = ()  # frasa pencarian yang wajar muncul di judul/tag
    catatan: str = ""

    @classmethod
    def dari_dict(cls, d: Mapping[str, Any]) -> Kasus:
        return cls(
            id=str(d["id"]),
            kueri=str(d["kueri"]),
            tema_diharapkan=tuple(d.get("tema_diharapkan", [])),
            frasa_wajar=tuple(d.get("frasa_wajar", [])),
            catatan=str(d.get("catatan", "")),
        )

    def baris(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kueri": self.kueri,
            "tema_diharapkan": list(self.tema_diharapkan),
            "frasa_wajar": list(self.frasa_wajar),
            "catatan": self.catatan or None,
        }


def ambang_dari_kanal(k: Any | None = None) -> dict[str, float]:
    """ambang lulus dari kanal.toml ([analisis.ambang_evaluasi]); modul AMBANG dipakai bila tidak ada."""
    from . import kanal as kanal_mod

    k = k or kanal_mod.muat()
    return dict(k.analisis.ambang) if getattr(k, "analisis", None) and k.analisis.ambang else dict(AMBANG)


def muat_kasus(path: Path | str = KASUS_BAWAAN) -> list[Kasus]:
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        out.append(Kasus.dari_dict(json.loads(ln)))
    return out


@dataclass
class Metrik:
    kasus: str
    relevansi: float = 0.0
    dukungan_klaim: float = 0.0
    kesegaran: float = 1.0
    kelengkapan: float = 0.0
    biaya: dict[str, float] = field(default_factory=dict)
    catatan: list[str] = field(default_factory=list)
    ambang: dict[str, float] = field(default_factory=lambda: dict(AMBANG))

    @property
    def lulus(self) -> bool:
        return all(
            getattr(self, k) >= self.ambang[k] for k in ("relevansi", "dukungan_klaim", "kesegaran", "kelengkapan")
        )

    def gagal(self) -> list[str]:
        out = []
        for k in ("relevansi", "dukungan_klaim", "kesegaran", "kelengkapan"):
            if getattr(self, k) < self.ambang[k]:
                out.append(f"{k} {getattr(self, k):.2f} < ambang {self.ambang[k]:.2f}")
        return out

    def baris(self) -> dict[str, Any]:
        return {
            "kasus": self.kasus,
            "relevansi": round(self.relevansi, 3),
            "dukungan_klaim": round(self.dukungan_klaim, 3),
            "kesegaran": round(self.kesegaran, 3),
            "kelengkapan": round(self.kelengkapan, 3),
            "biaya": {k: round(v, 3) for k, v in self.biaya.items()},
            "lulus": self.lulus,
            "catatan": self.catatan or None,
        }


# ================================================================================================ penilaian
def nilai_relevansi(kasus: Kasus, topik: str, kandidat: Sequence[str] = ()) -> tuple[float, str]:
    """seberapa dekat topik terpilih dengan yang diharapkan (1.0 = tepat; kemiripan teks untuk yang dekat)."""
    if not kasus.tema_diharapkan:
        return 1.0, "kasus tanpa topik yang diharapkan - relevansi tidak dinilai"
    n = teks.norm(topik)
    terbaik = 0.0
    cocok = ""
    for t in kasus.tema_diharapkan:
        nt = teks.norm(t)
        s = 1.0 if n == nt else (0.9 if (n in nt or nt in n) else teks.mirip(n, nt) / 100.0)
        if s > terbaik:
            terbaik, cocok = s, t
    if terbaik < 0.9:
        for k in kandidat[:5]:
            nk = teks.norm(k)
            for t in kasus.tema_diharapkan:
                if nk == teks.norm(t) or (nk and nk in teks.norm(t)):
                    return 0.8, f"topik terpilih '{topik}', tetapi '{k}' ada di 5 kandidat teratas"
    return terbaik, f"topik terpilih '{topik}' vs diharapkan '{cocok or kasus.tema_diharapkan[0]}'"


def nilai_dukungan(klaim: Sequence[Any]) -> tuple[float, str]:
    """porsi klaim FAKTA/INFERENSI yang didukung bukti kredibel (sinyal minat tidak dihitung)."""
    dihitung = [
        c
        for c in klaim or []
        if (getattr(c, "jenis", None) or (c.get("jenis") if isinstance(c, dict) else None)) != "sinyal_minat"
    ]
    if not dihitung:
        return 1.0, "tidak ada klaim fakta yang diajukan (semua sinyal minat) - dukungan tidak dinilai"
    ok = sum(
        1
        for c in dihitung
        if (getattr(c, "status", None) or (c.get("status") if isinstance(c, dict) else None)) in ("didukung", "lemah")
    )
    return ok / len(dihitung), f"{ok}/{len(dihitung)} klaim fakta didukung bukti kredibel"


def nilai_kelengkapan(paket: Any | None) -> tuple[float, list[str]]:
    """metadata lengkap? (3 judul, deskripsi, hashtag, tag; lint DRAF bersih).

    Menerima objek `metadata.Paket` maupun kamus (bagian "metadata" dari `analisis.jalankan`).
    """
    if paket is None:
        return 0.0, ["tidak ada paket metadata"]

    def ambil(kunci: str) -> Any:
        return paket.get(kunci) if isinstance(paket, Mapping) else getattr(paket, kunci, None)

    galat = list(ambil("galat") or [])
    if not galat and isinstance(paket, Mapping) and paket.get("lint_lulus") is False:
        galat = ["lint metadata belum lulus (lihat laporan analisis)"]
    judul = list(ambil("judul") or [])
    catatan: list[str] = []
    skor = 1.0
    if len(judul) != 3:
        skor -= 0.35
        catatan.append(f"jumlah judul {len(judul)} (harus 3)")
    if not str(ambil("deskripsi") or "").strip():
        skor -= 0.35
        catatan.append("deskripsi kosong")
    if not list(ambil("hashtag") or []):
        skor -= 0.15
        catatan.append("hashtag kosong")
    if not list(ambil("tag") or []):
        skor -= 0.15
        catatan.append("tag kosong")
    if galat:
        skor = min(skor, 0.5)
        catatan += [f"lint: {g}" for g in galat[:4]]
    return round(max(0.0, skor), 4), catatan


def _nama_kandidat(k: Any) -> str:
    return str(k.get("nama", "")) if isinstance(k, Mapping) else str(getattr(k, "nama", ""))


def _status_objek(status: Sequence[Any]) -> list[G.Status]:
    """terima objek Status atau kamus (hasil `analisis.jalankan` berbentuk kamus)."""
    out: list[G.Status] = []
    for s in status or []:
        if isinstance(s, G.Status):
            out.append(s)
        elif isinstance(s, Mapping):
            out.append(
                G.Status(
                    str(s.get("jenis", "?")),
                    str(s.get("status", G.TANPA_DATA)),
                    None,
                    float(s.get("ttl_jam", G.TTL_BAWAAN)),
                    str(s.get("sumber", "")),
                )
            )
    return out


def nilai(
    kasus: Kasus,
    topik: str = "",
    kandidat: Sequence[str] = (),
    klaim: Sequence[Any] = (),
    status: Sequence[G.Status] = (),
    paket: Any | None = None,
    detik: float = 0.0,
    permintaan: int = 0,
    anggap_fixture_segar: bool = False,
    ambang: Mapping[str, float] | None = None,
) -> Metrik:
    """nilai satu hasil analisis terhadap satu kasus.

    `anggap_fixture_segar=True` dipakai evaluasi offline: data fixture memang BUKAN data pasar, tetapi untuk
    mengukur RANTAI (apakah tiap sumber menjawab dan distempel waktunya) statusnya dihitung seperti data segar.
    """
    rel, c1 = nilai_relevansi(kasus, topik, kandidat)
    duk, c2 = nilai_dukungan(klaim)
    daftar_status = _status_objek(status)
    if anggap_fixture_segar:
        from dataclasses import replace

        daftar_status = [replace(s, status=G.LIVE) if s.status == G.FIXTURE else s for s in daftar_status]
    segar = G.keyakinan_data(daftar_status) if daftar_status else 1.0
    lengkap, c4 = nilai_kelengkapan(paket)
    m = Metrik(
        kasus=kasus.id,
        relevansi=rel,
        dukungan_klaim=duk,
        kesegaran=segar,
        kelengkapan=lengkap,
        biaya={"detik": round(detik, 3), "permintaan": float(permintaan)},
        catatan=[c1, c2, f"kesegaran sumber {segar:.0%}", *c4],
        ambang=dict(ambang or AMBANG),
    )
    return m


# ================================================================================================ lari
def jalankan_offline(
    kasus: Sequence[Kasus] | None = None,
    path: Path | str = KASUS_BAWAAN,
    hari: dt.date | None = None,
    log: Callable[[str], None] = lambda s: None,
) -> tuple[list[Metrik], dict[str, Any]]:
    """jalankan SEMUA kasus dengan mode uji (offline, deterministik). Tidak menyentuh jaringan."""
    from . import analisis  # impor lambat: analisis memakai evaluasi untuk laporannya

    ambang = ambang_dari_kanal()
    daftar = list(kasus) if kasus is not None else muat_kasus(path or KASUS_BAWAAN)
    metrik: list[Metrik] = []
    for ks in daftar:
        log(f"[eval] {ks.id}: {ks.kueri}")
        h = analisis.jalankan(kueri=ks.kueri, mode="uji", hari=hari, dalam=False)
        m = nilai(
            ks,
            topik=h.get("topik", ""),
            kandidat=[_nama_kandidat(k) for k in h.get("kandidat", [])],
            klaim=h.get("klaim", []),
            status=h.get("status", []),
            paket=h.get("paket") or h.get("metadata"),
            detik=h.get("detik", 0.0),
            permintaan=h.get("permintaan", 0),
            anggap_fixture_segar=True,
            ambang=ambang,
        )
        metrik.append(m)
    ringkasan = ringkas(metrik)
    ringkasan["ambang"] = dict(ambang)
    return metrik, ringkasan


def jalankan_live(
    kasus: Sequence[Kasus] | None = None,
    path: Path | str = KASUS_BAWAAN,
    izin: bool = False,
    hari: dt.date | None = None,
    log: Callable[[str], None] = lambda s: None,
) -> tuple[list[Metrik], dict[str, Any]]:
    """jalankan kasus dengan mode ONLINE. Butuh `izin=True` DAN env KLIKTAHU_LIVE=1.

    TIDAK pernah dipanggil CI maupun `uji_semua.sh`. Ini menghubungi layanan publik sungguhan.
    """
    if not izin or os.environ.get("KLIKTAHU_LIVE", "").strip() != "1":
        raise ValueError(
            "evaluasi live butuh izin=True dan env KLIKTAHU_LIVE=1 (menyentuh layanan publik; "
            "tidak boleh jalan otomatis di CI/cron)"
        )
    from . import analisis

    daftar = list(kasus) if kasus is not None else muat_kasus(path)
    metrik: list[Metrik] = []
    for ks in daftar:
        log(f"[eval-live] {ks.id}: {ks.kueri}")
        h = analisis.jalankan(kueri=ks.kueri, mode="online", hari=hari, dalam=False)
        metrik.append(
            nilai(
                ks,
                topik=h.get("topik", ""),
                kandidat=[_nama_kandidat(k) for k in h.get("kandidat", [])],
                klaim=h.get("klaim", []),
                status=h.get("status", []),
                paket=h.get("paket") or h.get("metadata"),
                detik=h.get("detik", 0.0),
                permintaan=h.get("permintaan", 0),
            )
        )
    return metrik, ringkas(metrik)


def ringkas(metrik: Sequence[Metrik]) -> dict[str, Any]:
    """ringkasan evaluasi; ambang diambil dari metrik pertama (bila ada)."""
    if not metrik:
        return {"n": 0, "lulus": 0, "rata": {}}
    rata = {
        k: round(sum(getattr(m, k) for m in metrik) / len(metrik), 3)
        for k in ("relevansi", "dukungan_klaim", "kesegaran", "kelengkapan")
    }
    return {
        "n": len(metrik),
        "lulus": sum(1 for m in metrik if m.lulus),
        "rata": rata,
        "total_detik": round(sum(m.biaya.get("detik", 0.0) for m in metrik), 2),
        "total_permintaan": int(sum(m.biaya.get("permintaan", 0.0) for m in metrik)),
        "ambang": dict(metrik[0].ambang),
    }


def laporan_md(metrik: Sequence[Metrik], judul: str = "Evaluasi offline") -> str:
    r = ringkas(metrik)
    L = [
        f"# {judul}",
        "",
        f"- Kasus: {r.get('n', 0)} | lulus: {r.get('lulus', 0)} | total {r.get('total_detik', 0)} s, "
        f"{r.get('total_permintaan', 0)} permintaan HTTP",
        "- Ambang: " + ", ".join(f"{k} >= {v:.2f}" for k, v in AMBANG.items()),
        "",
        "| kasus | relevansi | dukungan klaim | kesegaran | kelengkapan | detik | permintaan | hasil |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for m in metrik:
        L.append(
            f"| {m.kasus} | {m.relevansi:.2f} | {m.dukungan_klaim:.2f} | {m.kesegaran:.2f} | "
            f"{m.kelengkapan:.2f} | {m.biaya.get('detik', 0):.2f} | {int(m.biaya.get('permintaan', 0))} | "
            f"{'LULUS' if m.lulus else 'GAGAL: ' + '; '.join(m.gagal())} |"
        )
    if r.get("rata"):
        rr = r["rata"]
        L += [
            "",
            f"Rata-rata: relevansi {rr['relevansi']:.2f}, dukungan klaim {rr['dukungan_klaim']:.2f}, "
            f"kesegaran {rr['kesegaran']:.2f}, kelengkapan {rr['kelengkapan']:.2f}.",
            "",
            "Yang TIDAK diukur di sini: tayangan, retensi, CTR. Evaluasi offline tidak punya data performa, "
            "jadi hasilnya bukan ramalan sukses - hanya pemeriksaan bahwa mesin menjawab pertanyaan yang benar "
            "dengan bukti yang benar.",
        ]
    for m in metrik:
        if m.catatan:
            L += ["", f"### {m.kasus}", *[f"- {c}" for c in m.catatan]]
    return "\n".join(L) + "\n"


def tulis_laporan(metrik: Sequence[Metrik], path: Path | str, judul: str = "Evaluasi offline") -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(laporan_md(metrik, judul), encoding="utf-8")
    return p


def contoh_kasus() -> Iterable[Kasus]:
    """kasus bawaan bila berkas dataset belum ada (dipakai tes & contoh)."""
    return [
        Kasus("k01", "kenapa gunung meletus", ("gunung berapi",), ("kenapa gunung meletus",)),
        Kasus("k02", "kenapa tsunami bisa terjadi", ("tsunami",), ("kenapa tsunami bisa terjadi",)),
        Kasus("k03", "kenapa pelangi melengkung", ("pelangi",), ("kenapa pelangi",)),
    ]
