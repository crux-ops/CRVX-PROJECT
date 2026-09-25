"""kliktahu/riset/keputusan.py - dari papan skor ke KEPUTUSAN: niche/pilar fokus, topik, format, sudut, alasan.

Aturan:
1. Kandidat = topik segar atau 'long' (boleh Shorts sudut baru), tidak diblokir, frasa tidak didominasi kata sensitif.
2. Topik BERMOMEN yang waktunya mepet (event <= momen_hari_sebelum + 10 hari) dan skornya <= 8 poin di bawah
   juara dipilih lebih dulu (kesempatan yang tidak datang dua kali).
3. Format Long bila pohon pertanyaannya lebar & dalam (v4) dan evergreen; selain itu Shorts.
4. Keyakinan < 0.5 -> rekomendasi SEMENTARA (data belum cukup; jalankan riset online / lengkapi data agen).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass, field
from typing import Any

from .. import kanal as kanal_mod
from .. import skor as S
from ..tema import TEMA


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

    def dict(self) -> dict[str, Any]:
        return asdict(self)


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


def putuskan(rows: list[dict[str, Any]], k: kanal_mod.Kanal, hari_ini: dt.date) -> Keputusan | None:
    calon = [r for r in rows if r["status"] in ("segar", "long") and not r.get("dominan_sensitif")]
    if not calon:
        return None
    calon.sort(key=lambda r: -r["v7_peluang"])
    juara = calon[0]
    batas = k.jadwal.momen_hari_sebelum + 10
    for r in calon[:5]:
        if r.get("momen_tanggal") and r["komponen"]["waktu"] >= 0.5:
            sisa = (dt.date.fromisoformat(r["momen_tanggal"]) - hari_ini).days
            if 0 <= sisa <= batas and r["v7_peluang"] >= juara["v7_peluang"] - 8:
                juara = r
                break
    t = TEMA[juara["tema"]]
    fmt = S.format_saran(juara.get("jaring", 0), juara.get("kedalaman", 0), t.ever, juara["v7_peluang"])
    tayang = None
    if juara.get("momen_tanggal"):
        tg = dt.date.fromisoformat(juara["momen_tanggal"]) - dt.timedelta(days=k.jadwal.momen_hari_sebelum)
        tayang = max(tg, hari_ini + dt.timedelta(days=1)).isoformat()
    peringatan = []
    if t.pilar in k.aturan.pilar_kesehatan:
        peringatan.append(f"Topik kesehatan: wajib '{k.aturan.disclaimer_kesehatan}' di outro & deskripsi.")
    if juara.get("frasa_sensitif"):
        peringatan.append(
            "Ada frasa pencarian sensitif ("
            + ", ".join(juara["frasa_sensitif"][:3])
            + ") - JANGAN dipakai di judul/tag/hook."
        )
    if juara.get("momen_jenis") in ("live", "agen") and t.nama in ("gempa bumi", "tsunami", "gunung berapi"):
        peringatan.append(
            "Momen bencana nyata: bahas sainsnya dengan hormat, tanpa sensasi, sertakan sumber resmi BMKG."
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
            }
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
        alasan=alasan(juara),
        peringatan=peringatan,
        alternatif=alt,
        seri=juara.get("seri", []),
        momen=juara.get("momen_nama"),
        tayang_paling_lambat=tayang,
        niche=niche(calon),
        sementara=juara["keyakinan"] < 0.5,
    )
