"""kliktahu/riset/keputusan.py - dari papan skor ke KEPUTUSAN: niche/pilar fokus, topik, format, sudut, alasan.

Aturan:
1. Kandidat = topik segar atau 'long' (boleh Shorts sudut baru), tidak diblokir, frasa tidak didominasi kata sensitif.
2. Topik BERMOMEN yang waktunya mepet (event <= momen_hari_sebelum + 10 hari) dan skornya <= 8 poin di bawah
   juara dipilih lebih dulu (kesempatan yang tidak datang dua kali) - asal masih TERKEJAR jeda produksi: momen
   bertanggal minimal siap_shorts_hari lagi, atau momen berlangsung yang masih berlangsung saat paling cepat tayang.
   Bila juara skor dilewati, alasannya DITULIS (transparan) dan juara skor diberi catatan penjadwalan.
3. Format Long bila pohon pertanyaannya lebar & dalam (v4) dan evergreen; selain itu Shorts.
4. Keyakinan < 0.5 -> rekomendasi SEMENTARA (data belum cukup; jalankan riset online / lengkapi data agen).
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .. import kanal as kanal_mod
from .. import skor as S
from ..tema import BENCANA, TEMA


@dataclass
class Keputusan:
    tema: str
    slug: str
    pilar: str
    format: str
    peluang: float
    keyakinan: float
    status: str
    sudut: str | None
    hook: list[str]
    alasan: list[str]
    peringatan: list[str]
    alternatif: list[dict[str, Any]]
    seri: list[str]
    momen: str | None
    tayang_paling_lambat: str | None
    niche: list[dict[str, Any]] = field(default_factory=list)
    sementara: bool = False
    segera: bool = False  # momen SEDANG berlangsung -> tayang secepatnya (paling cepat H+siap produksi)

    def dict(self) -> dict[str, Any]:
        return asdict(self)


def dari_laporan(run: dict[str, Any] | None, laporan: Path) -> dict[str, Any] | None:
    """keputusan milik `run` dari riset_terakhir.json (None bila tidak ada / berkas milik run lain)."""
    if not run:
        return None
    js = laporan / ("_uji" if run.get("mode") == "uji" else "") / "riset_terakhir.json"
    if not js.exists():
        return None
    d = json.loads(js.read_text(encoding="utf-8"))
    kep = d.get("keputusan") if d.get("run_id") == run.get("id") else None
    return kep if isinstance(kep, dict) else None


def _rb(x: float) -> str:
    return f"{int(round(x)):,}".replace(",", ".")


def alasan(r: dict[str, Any]) -> list[str]:
    k, sg = r["komponen"], r["sinyal"]
    out = [
        f"Permintaan {k['permintaan']:.2f}: {int(sg['jml'])} frasa pencarian asli, {int(sg['yt'])} juga muncul di "
        f"YouTube Autocomplete (v5 skor_views {r['v5_views']:.1f})."
    ]
    if r.get("wiki"):
        w = r["wiki"]
        out.append(f"Minat Wikipedia {k['minat']:.2f}: {_rb(w['views60'])} tayangan 60 hari, tren {w['tren']:.2f}x.")
    if r.get("momen_nama"):
        out.append(f"Momen {k['waktu']:.2f}: {r['momen_nama']} ({r['momen_tanggal']}).")
    if r.get("pesaing"):
        p = r["pesaing"]
        out.append(
            f"Celah pesaing {k['celah']:.2f}: {p.get('jumlah', 0)} video kuat, median {_rb(p.get('median_views', 0))} "
            f"views, umur median {int(p.get('umur_median_hari', 0))} hari."
        )
    if r.get("berita"):
        out.append(
            f"Momentum {k['momentum']:.2f}: {int(r['berita'].get('n7', 0))} berita 7 hari terakhir "
            f"(rasio {r['berita'].get('rasio', 0):.2f}x dari biasanya)."
        )
    if r.get("tren_traffic"):
        out.append(f"Sedang tren di Google Indonesia: ~{_rb(r['tren_traffic'])}+ pencarian hari ini.")
    yk = r["keyakinan"]
    out.append(
        f"Keyakinan data {yk:.0%} ({'tinggi' if yk >= 0.75 else 'sedang' if yk >= 0.5 else 'rendah'}); "
        f"komponen tanpa data dinetralkan 0.5."
    )
    return out


def niche(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """peta pilar: rata-rata 3 teratas per pilar -> pilar fokus (sub-niche) untuk seri berikutnya."""
    per: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        per.setdefault(r["pilar"], []).append(r)
    out = []
    for p, rs in per.items():
        top = sorted(rs, key=lambda r: -r["v7_peluang"])[:3]
        out.append(
            {
                "pilar": p,
                "n": len(rs),
                "peluang_top3": round(sum(r["v7_peluang"] for r in top) / len(top), 1),
                "permintaan": round(sum(r["komponen"]["permintaan"] for r in top) / len(top), 3),
                "celah": round(sum(r["komponen"]["celah"] for r in top) / len(top), 3),
                "contoh": [r["tema"] for r in top],
            }
        )
    return sorted(out, key=lambda x: -x["peluang_top3"])


def sisa_momen(r: dict[str, Any], hari_ini: dt.date, siap: int) -> int | None:
    """hari menuju momen yang MASIH TERKEJAR jeda produksi `siap` hari; 0 = sedang berlangsung dan masih berlangsung
    saat paling cepat tayang; None = tidak bermomen / momen lewat sebelum video bisa tayang."""
    if not r.get("momen_tanggal"):
        return None
    mulai = dt.date.fromisoformat(r["momen_tanggal"])
    akhir = dt.date.fromisoformat(r.get("momen_selesai") or r["momen_tanggal"])
    siap_tayang = hari_ini + dt.timedelta(days=siap)
    if mulai <= hari_ini:
        return 0 if akhir >= siap_tayang else None
    sisa = (mulai - hari_ini).days
    return sisa if sisa >= siap else None


def _catatan_juara_skor(top: dict[str, Any], hari_ini: dt.date, siap: int) -> str:
    akhir = top.get("momen_selesai") or top.get("momen_tanggal")
    if (
        top.get("momen_jenis") in ("live", "agen")
        and akhir
        and akhir < (hari_ini + dt.timedelta(days=siap)).isoformat()
    ):
        return (
            f"juara skor; momennya berlangsung (terakhir terverifikasi {akhir}) - angkat berikutnya selama masih "
            "berlangsung, cek status di sumber resmi dulu"
        )
    return "juara skor - jadwalkan berikutnya"


def putuskan(rows: list[dict[str, Any]], k: kanal_mod.Kanal, hari_ini: dt.date) -> Keputusan | None:
    calon = [r for r in rows if r["status"] in ("segar", "long") and not r.get("dominan_sensitif")]
    if not calon:
        return None
    calon.sort(key=lambda r: -r["v7_peluang"])
    juara = top = calon[0]
    batas = k.jadwal.momen_hari_sebelum + 10
    siap_min = k.jadwal.siap_shorts_hari
    for r in calon[:5]:
        sisa = sisa_momen(r, hari_ini, siap_min)
        dekat = sisa is not None and 0 <= sisa <= batas
        if dekat and r["komponen"]["waktu"] >= 0.5 and r["v7_peluang"] >= top["v7_peluang"] - 8:
            juara = r
            break
    t = TEMA[juara["tema"]]
    fmt = S.format_saran(juara.get("jaring", 0), juara.get("kedalaman", 0), t.ever, juara["v7_peluang"])
    tayang, segera = None, False
    if juara.get("momen_tanggal"):
        siap = k.jadwal.siap_shorts_hari if fmt == "shorts" else k.jadwal.siap_long_hari
        tg = dt.date.fromisoformat(juara["momen_tanggal"]) - dt.timedelta(days=k.jadwal.momen_hari_sebelum)
        tayang = max(tg, hari_ini + dt.timedelta(days=siap)).isoformat()
        segera = juara.get("momen_jenis") in ("live", "agen") and juara["momen_tanggal"] <= hari_ini.isoformat()
    peringatan = []
    if t.pilar in k.aturan.pilar_kesehatan:
        peringatan.append(f"Topik kesehatan: wajib '{k.aturan.disclaimer_kesehatan}' di outro & deskripsi.")
    if juara.get("frasa_sensitif"):
        peringatan.append(
            "Ada frasa pencarian sensitif ("
            + ", ".join(juara["frasa_sensitif"][:3])
            + ") - JANGAN dipakai di judul/tag/hook."
        )
    if t.nama in BENCANA:  # SELALU (dulu hanya untuk momen live -> peringatan tsunami Palu tidak memicu apa pun)
        peringatan.append(
            "Topik bencana dengan korban jiwa nyata: bahas sainsnya dengan hormat, tanpa sensasi & tanpa menakut-nakuti "
            f"(tanpa kata 'seru', 'ngeri', 'bikin kaget'); arahkan ke info resmi {BENCANA[t.nama]}."
        )
        if juara.get("momen_jenis") in ("live", "agen"):
            peringatan.append(
                "Momen bencana SEDANG berlangsung: cek status terbaru di sumber resmi sebelum naskah & rilis."
            )
        elif juara.get("momen_nama") and "peringatan" in juara["momen_nama"].lower():
            peringatan.append(
                f"Momen peringatan ({juara['momen_nama'].split('(')[0].strip()}): hormati korban & penyintas; "
                "fokus sains dan kesiapsiagaan, bukan dramatisasi."
            )
    if juara["keyakinan"] < 0.5:
        peringatan.append(
            "Keyakinan rendah: sebagian komponen belum berdata (jalankan riset online atau lengkapi data agen)."
        )
    if juara["status"] == "long":
        peringatan.append("Topik ini pernah jadi video panjang: Shorts wajib sudut BARU.")
    alt: list[dict[str, Any]] = []
    for r in calon:
        if r is juara or len(alt) >= 3:
            continue
        alt.append(
            {
                "tema": r["tema"],
                "pilar": r["pilar"],
                "peluang": round(r["v7_peluang"], 1),
                "keyakinan": round(r["keyakinan"], 2),
                "sudut": (r.get("sudut") or [None])[0],
                "momen": r.get("momen_nama"),
                **({"catatan": _catatan_juara_skor(r, hari_ini, siap_min)} if r is top else {}),
            }
        )
    daftar_alasan = alasan(juara)
    if juara is not top:  # transparan: kenapa juara SKOR tidak dipilih
        sisa = sisa_momen(juara, hari_ini, siap_min)
        daftar_alasan.insert(
            0,
            f"Didahulukan dari {top['tema']} (peluang {top['v7_peluang']:.1f}; selisih "
            f"{top['v7_peluang'] - juara['v7_peluang']:.1f} <= 8 poin): momen "
            f"{(juara.get('momen_nama') or '').split('(')[0].strip()} {juara['momen_tanggal']} tinggal {sisa} hari "
            "dan masih terkejar jeda produksi - kesempatan yang tidak datang dua kali (aturan 2).",
        )
    return Keputusan(
        tema=juara["tema"],
        slug=juara["slug"],
        pilar=juara["pilar"],
        format=fmt,
        peluang=round(juara["v7_peluang"], 1),
        keyakinan=round(juara["keyakinan"], 3),
        status=juara["status"],
        sudut=(juara.get("sudut") or [None])[0],
        hook=juara.get("hook", []),
        alasan=daftar_alasan,
        peringatan=peringatan,
        alternatif=alt,
        seri=juara.get("seri", []),
        momen=juara.get("momen_nama"),
        tayang_paling_lambat=tayang,
        niche=niche(calon),
        sementara=juara["keyakinan"] < 0.5,
        segera=segera,
    )
