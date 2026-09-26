"""kliktahu/niche.py - PEMILIHAN NICHE & TOPIK (tahap 6 rencana upgrade 2026-09).

Skor di sini bisa DIJELASKAN per komponen, dan selalu menyertakan ketidakpastian. Yang tidak dilakukan modul ini:
mengubah skor jadi "peluang sukses". 72 bukan "72% akan viral", melainkan posisi relatif kandidat hari ini pada
skala yang ditentukan bobot di bawah, dengan data yang ada (dan keyakinan yang menyertainya).

Komponen (mengembangkan v7 di skor.py):
  permintaan  frasa pencarian asli (Google + YouTube Autocomplete) - berapa banyak & sekuat apa
  momentum    sedang naik sekarang (velocity snapshot, berita, Google Trends, lonjakan Wikipedia)
  celah       kejenuhan pasokan (hanya bila [riset] pesaing = true)
  kecocokan   bisa divisualkan, bobot pilar dari performa kanal, evergreen
  kesegaran   belum dibahas & tidak mirip episode lama
  bukti       tersedia sumber ilmiah kredibel & independen
  biaya       kebalikan dari ongkos produksi (visual sulit, riset lama, format panjang = mahal)
  waktu       momen yang tidak datang dua kali

Keluaran utama: `skor_niche()` -> (skor 0..100, keyakinan 0..1, rentang, rincian per komponen).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from . import skor as S
from .tema import TEMA

Nilai = S.Nilai

BOBOT_NICHE: dict[str, float] = {
    "permintaan": 0.22,
    "momentum": 0.14,
    "celah": 0.12,
    "kecocokan": 0.13,
    "kesegaran": 0.06,
    "bukti": 0.07,
    "biaya": 0.08,
    "waktu": 0.18,  # momen: kesempatan yang tidak datang dua kali diberi bobot besar
}
assert abs(sum(BOBOT_NICHE.values()) - 1.0) < 1e-12

URUTAN = ("permintaan", "momentum", "waktu", "kecocokan", "celah", "bukti", "biaya", "kesegaran")

# ongkos produksi relatif (1 = paling mahal). Dipakai untuk komponen `biaya` (x = 1 - biaya).
BIAYA_FORMAT = {"shorts": 0.15, "long": 0.55}
BIAYA_KETERSEDIAAN_SUMBER = 0.20  # tidak ada sumber ilmiah kredibel -> riset manual lebih lama


@dataclass
class SkorNiche:
    nama: str
    pilar: str
    skor: float  # 0..100
    keyakinan: float  # 0..1 = porsi bobot yang didukung data nyata
    rentang: tuple[float, float]  # rentang ketidakpastian, BUKAN selang kepercayaan probabilitas
    x: dict[str, float]  # nilai 0..1 per komponen (0.5 = netral/tanpa data)
    tanpa: tuple[str, ...] = ()
    catatan: list[str] = field(default_factory=list)

    def baris(self) -> dict[str, Any]:
        return {
            "nama": self.nama,
            "pilar": self.pilar,
            "skor": round(self.skor, 1),
            "keyakinan": round(self.keyakinan, 3),
            "rentang": [round(self.rentang[0], 1), round(self.rentang[1], 1)],
            "x": {k: round(v, 4) for k, v in self.x.items()},
            "tanpa": list(self.tanpa),
            "catatan": self.catatan or None,
        }

    def __str__(self) -> str:
        return f"{self.nama}: {self.skor:.1f} (yakin {self.keyakinan:.0%}, rentang {self.rentang[0]:.0f}-{self.rentang[1]:.0f})"


def biaya_produksi(
    visual: float = 0.5,
    format_: str = "shorts",
    ada_sumber: bool = True,
    di_registri: bool = True,
    butuh_riset_lanjut: bool = False,
) -> float:
    """ongkos produksi relatif 0..1 (1 = paling mahal). Dipakai terbalik pada komponen `biaya`.

    Penyumbang ongkos: format panjang (10 bab vs 9 adegan), visual yang sulit divisualkan (membutuhkan animasi
    khusus), tidak ada sumber kredibel (riset manual), topik di luar registri (tanpa aspek/alias siap pakai),
    dan topik yang butuh riset lanjutan (cek instansi, data lapangan).
    """
    b = BIAYA_FORMAT.get(format_, 0.2)
    b += 0.35 * (1.0 - min(1.0, max(0.0, visual)))  # susah divisualkan = mahal
    if not ada_sumber:
        b += BIAYA_KETERSEDIAAN_SUMBER
    if not di_registri:
        b += 0.08
    if butuh_riset_lanjut:
        b += 0.15
    return round(min(1.0, b), 4)


def rentang_ketidakpastian(skor: float, keyakinan: float, lebar_maks: float = 26.0) -> tuple[float, float]:
    """rentang tampilan: makin rendah keyakinan, makin lebar. BUKAN selang kepercayaan statistik."""
    lebar = lebar_maks * (1.0 - min(1.0, max(0.0, keyakinan)))
    return (round(max(0.0, skor - lebar), 2), round(min(100.0, skor + lebar), 2))


def skor_niche(
    nama: str,
    pilar: str,
    komponen: Mapping[str, Nilai | None],
    tanpa: Iterable[str] = (),
    catatan: Sequence[str] = (),
) -> SkorNiche:
    """skor 0..100 + keyakinan + rentang. Komponen tanpa data = netral 0.5 dengan keyakinan 0."""
    skor, yakin, x = S.v7_peluang(komponen, tanpa, BOBOT_NICHE)
    lo, hi = rentang_ketidakpastian(skor, yakin)
    return SkorNiche(nama, pilar, round(skor, 2), round(yakin, 4), (lo, hi), x, tuple(tanpa), list(catatan))


def komponen_dasar(
    permintaan: float | None = None,
    momentum: float | None = None,
    celah: float | None = None,
    kecocokan: float | None = None,
    kesegaran: float | None = None,
    bukti: float | None = None,
    biaya: float | None = None,
    waktu: float | None = None,
    yakin: Mapping[str, float] | None = None,
) -> dict[str, Nilai | None]:
    """susun kamus komponen; None = tanpa data (netral 0.5, keyakinan 0). `yakin` bisa menimpanya per komponen."""
    mentah = {
        "permintaan": permintaan,
        "momentum": momentum,
        "celah": celah,
        "kecocokan": kecocokan,
        "kesegaran": kesegaran,
        "bukti": bukti,
        "biaya": biaya,
        "waktu": waktu,
    }
    out: dict[str, Nilai | None] = {}
    for k, v in mentah.items():
        if v is None:
            out[k] = None
        else:
            out[k] = (S._j(float(v)), S._j(float((yakin or {}).get(k, 1.0))))
    return out


def jelaskan(h: SkorNiche) -> list[str]:
    """kalimat alasan per komponen (untuk laporan & keputusan)."""
    out = [
        f"Skor niche {h.skor:.1f}/100 (rentang tampil {h.rentang[0]:.0f}-{h.rentang[1]:.0f}, keyakinan {h.keyakinan:.0%})."
    ]
    out.append("Catatan: angka ini POSISI RELATIF hari ini pada bobot yang ditetapkan, BUKAN peluang tayangan/sukses.")
    for k in URUTAN:
        if k not in h.x:
            continue
        w = BOBOT_NICHE[k]
        nilai = h.x[k]
        if k in h.tanpa:
            out.append(f"{k}: tidak dipakai (bobot {w:.0%} dinormalisasi keluar).")
        elif abs(nilai - 0.5) < 1e-9:
            out.append(f"{k}: 0.50 = netral (tanpa data, atau memang nilainya pas di tengah; bobot {w:.0%}).")
        else:
            out.append(f"{k}: {nilai:.2f} x bobot {w:.0%}.")
    out += list(h.catatan)
    return out


def peta_pilar(daftar: Sequence[SkorNiche], n_atas: int = 3) -> list[dict[str, Any]]:
    """ringkasan per pilar -> pilar mana yang sedang paling subur (niche fokus)."""
    per: dict[str, list[SkorNiche]] = {}
    for h in daftar:
        per.setdefault(h.pilar or "-", []).append(h)
    out = []
    for p, hs in per.items():
        top = sorted(hs, key=lambda h: -h.skor)[:n_atas]
        out.append(
            {
                "pilar": p,
                "n": len(hs),
                "rata": round(sum(h.skor for h in top) / len(top), 1),
                "keyakinan": round(sum(h.keyakinan for h in top) / len(top), 3),
                "top": [h.nama for h in top],
            }
        )
    return sorted(out, key=lambda d: -d["rata"])


def urutkan(daftar: Sequence[SkorNiche]) -> list[SkorNiche]:
    """urutan rekomendasi: skor, lalu keyakinan (data lebih lengkap menang saat skor berdekatan)."""
    return sorted(daftar, key=lambda h: (-h.skor, -h.keyakinan, h.nama))


def pilih(
    daftar: Sequence[SkorNiche],
    hari_ini: dt.date | None = None,
    momen: Mapping[str, dt.date | None] | None = None,
    batas_selisih: float = 8.0,
) -> tuple[SkorNiche | None, list[str]]:
    """pilih satu niche/topik. Momen yang masih terkejar boleh mendahului juara skor bila selisih <= batas.

    Mengembalikan (pilihan, alasan). Alasan SELALU menyebut bila juara skor dilewati.
    """
    if not daftar:
        return None, ["tidak ada kandidat"]
    urut = urutkan(daftar)
    juara = urut[0]
    alasan = [f"Juara skor: {juara}."]
    if not momen or hari_ini is None:
        return juara, alasan
    for h in urut[1:]:
        tgl = momen.get(h.nama)
        if not tgl or tgl < hari_ini:
            continue
        sisa = (tgl - hari_ini).days
        if sisa > 45:
            continue
        if juara.skor - h.skor <= batas_selisih:
            alasan.append(
                f"Didahulukan: {h.nama} punya momen {tgl} ({sisa} hari lagi) dan selisih skor hanya "
                f"{juara.skor - h.skor:.1f} <= {batas_selisih:.0f} - kesempatan yang tidak datang dua kali."
            )
            return h, alasan
        break
    return juara, alasan


def tabel_md(daftar: Sequence[SkorNiche], n: int = 15) -> list[str]:
    if not daftar:
        return ["(tidak ada kandidat)"]
    out = [
        "| # | topik | pilar | skor | rentang | yakin | permintaan | momentum | waktu | cocok | bukti | biaya |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, h in enumerate(urutkan(daftar)[:n], 1):
        sel = {k: ("-" if k in h.tanpa else f"{h.x.get(k, 0.5):.2f}") for k in URUTAN}
        out.append(
            f"| {i} | {h.nama} | {h.pilar or '-'} | **{h.skor:.1f}** | {h.rentang[0]:.0f}-{h.rentang[1]:.0f} | "
            f"{h.keyakinan:.0%} | {sel['permintaan']} | {sel['momentum']} | {sel['waktu']} | {sel['kecocokan']} | "
            f"{sel['bukti']} | {sel['biaya']} |"
        )
    return out


def biaya_dari_tema(tema: str, format_: str = "shorts", ada_sumber: bool = True) -> float:
    """ongkos produksi untuk tema registri (visual bawaan & evergreen ikut menentukan)."""
    t = TEMA.get(tema)
    vis = t.visb if t else 0.4
    return biaya_produksi(vis, format_, ada_sumber, di_registri=t is not None)
