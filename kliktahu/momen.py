"""kliktahu/momen.py - DETEKSI MOMEN: kalender kurasi + astronomi terhitung + umpan live -> skor momen per tema.

Sumber momen:
  statis : analisis/momen.json (gerhana, hari peringatan, musim - dikurasi, bersumber)
  astro  : dihitung kliktahu/astro.py (ekuinoks/solstis, supermoon, blue moon, hujan meteor, hari tanpa bayangan)
  live   : mesin riset (gempa BMKG/USGS, badai geomagnetik NOAA, asteroid JPL, erupsi EONET, Google Trends)
  agen   : hasil web search agen (data agen)
Skor (rumus prompt v5): momen = 1 - sisa_hari/(jendela*1.25) bila 0 <= sisa_hari <= jendela.
Momen live yang SEDANG terjadi: skor = urgensi, meluruh dalam 3 hari (topik harus cepat tayang).
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import ROOT, astro, skor, teks
from .tema import SINONIM_MOMEN, TEMA, Tema

STATIS = ROOT / "analisis" / "momen.json"
KOTA_HTB = ("Jakarta", "Bandung", "Semarang", "Yogyakarta", "Surabaya", "Denpasar", "Makassar", "Medan", "Pontianak")


@dataclass
class Momen:
    tanggal: dt.date
    nama: str
    tema: list[str]
    jenis: str
    sumber: str
    urgensi: float = 0.0
    selesai: dt.date | None = None
    lokasi: str | None = None
    ekstra: dict = field(default_factory=dict)

    def baris_db(self) -> dict:
        d = asdict(self)
        d.pop("ekstra")
        d["tanggal"] = self.tanggal.isoformat()
        d["selesai"] = self.selesai.isoformat() if self.selesai else None
        return d


def statis(path: Path = STATIS) -> list[Momen]:
    data = json.loads(path.read_text(encoding="utf-8"))["events"]
    out = []
    for e in data:
        out.append(
            Momen(
                dt.date.fromisoformat(e["tanggal"]),
                e["nama"],
                list(e["tema"]),
                "statis",
                e["sumber"],
                selesai=dt.date.fromisoformat(e["selesai"]) if e.get("selesai") else None,
            )
        )
    return out


def _tgl_wib(t: dt.datetime) -> dt.date:
    return t.astimezone(dt.timezone(dt.timedelta(hours=7))).date()


def astro_tahun(tahun: int) -> list[Momen]:
    out: list[Momen] = []
    label = {
        "ekuinoks_maret": "Ekuinoks Maret",
        "solstis_juni": "Solstis Juni",
        "ekuinoks_september": "Ekuinoks September",
        "solstis_desember": "Solstis Desember",
    }
    for k, t in astro.ekuinoks_solstis(tahun).items():
        jam = t.astimezone(dt.timezone(dt.timedelta(hours=7))).strftime("%H.%M")
        out.append(Momen(_tgl_wib(t), f"{label[k]} ({jam} WIB)", ["matahari"], "astro", "dihitung (Meeus/NOAA)"))
    for t, jarak in astro.supermoon(tahun):
        out.append(
            Momen(
                _tgl_wib(t),
                f"Supermoon - purnama terdekat ({round(jarak):,} km)".replace(",", "."),
                ["bulan"],
                "astro",
                "dihitung (Meeus bab 47 & 49)",
                ekstra={"jarak_km": round(jarak)},
            )
        )
    purnama = [t for n, t in astro.fase_bulan_tahun(tahun) if n == "purnama"]
    for a, b in zip(purnama, purnama[1:]):
        if (a.year, a.month) == (b.year, b.month):
            out.append(
                Momen(
                    _tgl_wib(b),
                    "Blue moon - purnama kedua dalam satu bulan",
                    ["bulan"],
                    "astro",
                    "dihitung (Meeus bab 49)",
                )
            )
    for nama, t, zhr in astro.hujan_meteor(tahun):
        out.append(
            Momen(
                _tgl_wib(t),
                f"Puncak hujan meteor {nama} (~{zhr} meteor/jam di langit ideal)",
                ["meteor & komet"],
                "astro",
                "dihitung dari bujur Matahari J2000 (kalender IMO)",
            )
        )
    per_tanggal: dict[dt.date, list[str]] = {}
    for kota in astro.KOTA:
        if kota.nama not in KOTA_HTB:
            continue
        for t in astro.hari_tanpa_bayangan(kota, tahun):
            per_tanggal.setdefault(t.date(), []).append(f"{kota.nama} {t.strftime('%H.%M')} {kota.zona}")
    for d, daftar_kota in sorted(per_tanggal.items()):
        out.append(
            Momen(
                d,
                "Hari tanpa bayangan: " + ", ".join(daftar_kota),
                ["hari tanpa bayangan", "matahari"],
                "astro",
                "dihitung (deklinasi Matahari = lintang kota)",
                lokasi=", ".join(x.split(" ")[0] for x in daftar_kota),
            )
        )
    return out


def semua(
    hari_ini: dt.date, jendela_hari: int = 400, live: list[Momen] | None = None, dengan_statis: bool = True
) -> list[Momen]:
    """momen dari (hari_ini - 3 hari) sampai (hari_ini + jendela_hari), terurut tanggal, tanpa duplikat."""
    awal, akhir = hari_ini - dt.timedelta(days=3), hari_ini + dt.timedelta(days=jendela_hari)
    semua_m: list[Momen] = []
    if dengan_statis:
        semua_m += statis()
    for th in range(awal.year, akhir.year + 1):
        semua_m += astro_tahun(th)
    semua_m += live or []
    lihat, out = set(), []
    for m in sorted(semua_m, key=lambda m: (m.tanggal, m.jenis, m.nama)):
        kunci = (m.tanggal, teks.norm(m.nama))
        if awal <= (m.selesai or m.tanggal) and m.tanggal <= akhir and kunci not in lihat:
            lihat.add(kunci)
            out.append(m)
    return out


def cocok(m: Momen, t: Tema) -> bool:
    kunci = {teks.norm(t.nama), *(teks.norm(k) for k in t.kata)}
    sinonim = [teks.norm(s) for s in SINONIM_MOMEN.get(t.nama, [])]
    for e in m.tema:
        en = teks.norm(e)
        if en in kunci or any(teks.kata_utuh_semua(k, en) for k in kunci if len(k) > 3):
            return True
        if any(s and teks.kata_utuh_semua(s, en) for s in sinonim):
            return True
    return False


def skor_momen(m: Momen, hari_ini: dt.date, jendela: int = 45) -> float:
    sisa = (m.tanggal - hari_ini).days
    if m.jenis in ("live", "agen") and m.urgensi > 0:
        akhir = m.selesai or m.tanggal
        if m.tanggal <= hari_ini <= akhir:  # sedang berlangsung -> penuh
            return round(m.urgensi, 3)
        lewat = (hari_ini - akhir).days
        if 0 < lewat <= 3:  # baru lewat -> meluruh dalam 3 hari
            return round(m.urgensi * (1 - lewat / 4), 3)
        if sisa > 0:  # prakiraan (mis. badai geomagnetik 2 hari lagi)
            return round(skor.v5_momen(sisa, jendela) * (0.5 + 0.5 * m.urgensi), 3)
        return 0.0
    if m.selesai and m.tanggal <= hari_ini <= m.selesai:
        sisa = 0
    return round(skor.v5_momen(sisa, jendela), 3)


def skor_tema(nama_tema: str, daftar: list[Momen], hari_ini: dt.date, jendela: int = 45) -> tuple[float, Momen | None]:
    t = TEMA[nama_tema]
    best: tuple[float, Momen | None] = (0.0, None)
    for m in daftar:
        if cocok(m, t):
            s = skor_momen(m, hari_ini, jendela)
            if s > best[0]:
                best = (s, m)
    return best


def nama_pendek(nama: str, maks: int = 40) -> str:
    """nama momen ringkas untuk judul: bagian sebelum ':'/'(' dan dipotong di BATAS KATA (<= maks karakter)."""
    n = (nama or "").split(":")[0].split("(")[0].strip()
    if len(n) <= maks:
        return n
    potong = n[: maks + 1].rsplit(" ", 1)[0] if " " in n[: maks + 1] else n[:maks]
    return potong.rstrip(" -&,;")


def ke_tema(m: Momen) -> list[str]:
    return [n for n, t in TEMA.items() if cocok(m, t)]
