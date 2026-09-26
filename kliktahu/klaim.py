"""kliktahu/klaim.py - VERIFIKASI KLAIM (tahap 5 rencana upgrade 2026-09).

Mesin riset menghasilkan tiga macam kalimat yang sering tertukar:

  FAKTA        pernyataan yang bisa dibuktikan salah/benar ("tsunami Palu mencapai 10 meter")
  INFERENSI    kesimpulan dari data, masih bisa berubah ("kemungkinan dipicu longsor bawah laut")
  SINYAL_MINAT apa yang DICARI orang ("kenapa tsunami bisa terjadi") - bukan pernyataan, tidak butuh pembuktian

Modul ini memetakan tiap klaim ke bukti yang BENAR-BENAR dibaca (judul + penerbit + tahun + URL/DOI yang lolos
validasi), lalu memberi status:

  DIDUKUNG      >= 1 bukti kredibel, dan >= 1 penerbit independen bila klaimnya spesifik
  LEMAH         ada bukti kredibel, tetapi hanya satu sumber / tidak independen (perlu sumber kedua)
  KONFLIK       dua sumber kredibel memberi ANGKA yang berbeda untuk hal yang sama
  TIDAK_DIDUKUNG tidak ada bukti kredibel yang menyentuh klaim ini
  TANPA_DATA    tidak ada bukti sama sekali (sumber ilmiah gagal diambil)

Deteksi konflik bersifat HEURISTIK (membandingkan angka + satuan yang sama), bukan pemahaman bahasa: hasilnya
"perlu dicek manusia", bukan vonis. Kemandirian penerbit dihitung dari domain yang berbeda.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from . import teks
from .validasi import domain, kredibel_dari_url

FAKTA = "fakta"
INFERENSI = "inferensi"
SINYAL_MINAT = "sinyal_minat"

DIDUKUNG = "didukung"
LEMAH = "lemah"
KONFLIK = "konflik"
TIDAK_DIDUKUNG = "tidak_didukung"
TANPA_DATA = "tanpa_data"
SINYAL = "sinyal"

LABEL = {
    DIDUKUNG: "DIDUKUNG bukti",
    LEMAH: "LEMAH (perlu sumber kedua)",
    KONFLIK: "KONFLIK sumber (harus dicek)",
    TIDAK_DIDUKUNG: "TIDAK DIDUKUNG",
    TANPA_DATA: "TANPA DATA",
    SINYAL: "SINYAL MINAT (bukan klaim)",
}

KATA_INFERENSI = (
    "kemungkinan",
    "diduga",
    "diperkirakan",
    "mungkin",
    "bisa jadi",
    "sepertinya",
    "dugaan",
    "hipotesis",
    "menunjukkan",
    "mengisyaratkan",
    "diduga kuat",
    "belum pasti",
    "masih diteliti",
    "para ahli menduga",
)
KATA_TANYA = ("kenapa", "mengapa", "apakah", "bagaimana", "kapan", "siapa", "dimana", "di mana", "berapa")
_ANGKA = re.compile(
    r"(?<![\w.])(\d+(?:[.,]\d+)?)\s*(km|m|meter|kilometer|detik|menit|jam|hari|tahun|persen|%|derajat|celsius|liter|kg|gram|kali|ribu|juta|miliar|sr|richter|mw)?",
    re.I,
)
_SATUAN_SAMA = {"m": "meter", "meter": "meter", "km": "meter", "kilometer": "meter"}


@dataclass
class Bukti:
    judul: str
    url: str | None = None
    penerbit: str | None = None
    tahun: int | None = None
    doi: str | None = None
    kredibel: bool = False
    kutipan: int | None = None
    diambil: str | None = None
    relevan: float = 0.0  # 0..1 kemiripan kata klaim dengan judul bukti

    @property
    def domain(self) -> str | None:
        return domain(self.url)

    def baris(self) -> dict[str, Any]:
        return {
            "judul": self.judul,
            "url": self.url,
            "penerbit": self.penerbit,
            "tahun": self.tahun,
            "doi": self.doi,
            "kredibel": self.kredibel,
            "relevan": round(self.relevan, 3),
        }


@dataclass
class Klaim:
    teks: str
    jenis: str = FAKTA
    status: str = TANPA_DATA
    bukti: list[Bukti] = field(default_factory=list)
    penerbit: set[str] = field(default_factory=set)
    catatan: list[str] = field(default_factory=list)

    @property
    def kredibel(self) -> list[Bukti]:
        return [b for b in self.bukti if b.kredibel]

    @property
    def n_independen(self) -> int:
        return len(self.penerbit)

    @property
    def boleh_dipakai(self) -> bool:
        """boleh masuk naskah? Fakta harus didukung; sinyal minat selalu boleh (itu pertanyaannya)."""
        if self.jenis == SINYAL_MINAT:
            return True
        return self.status in (DIDUKUNG, LEMAH)

    def baris(self) -> dict[str, Any]:
        return {
            "teks": self.teks,
            "jenis": self.jenis,
            "status": self.status,
            "bukti": [b.baris() for b in self.bukti[:5]],
            "penerbit_independen": sorted(self.penerbit),
            "catatan": self.catatan or None,
        }

    def __str__(self) -> str:
        return f"[{LABEL.get(self.status, self.status)}] {self.teks}"


# ================================================================================================ klasifikasi
def klasifikasi(t: str) -> str:
    """tebak jenis kalimat. Pertanyaan = sinyal minat (bukan klaim yang perlu dibuktikan)."""
    n = teks.norm(t).strip()
    if not n:
        return SINYAL_MINAT
    if n.endswith("?") or n.split()[0] in KATA_TANYA:
        return SINYAL_MINAT
    if any(teks.kata_utuh_semua(k, n) for k in KATA_INFERENSI):
        return INFERENSI
    return FAKTA


def angka_satuan(teks_: str) -> list[tuple[float, str]]:
    """semua pasangan (angka, satuan) dalam kalimat - dipakai mendeteksi konflik antar sumber."""
    out: list[tuple[float, str]] = []
    for a, s in _ANGKA.findall(teks_ or ""):
        try:
            v = float(str(a).replace(",", "."))
        except ValueError:
            continue
        u = (s or "").lower()
        if u in _SATUAN_SAMA:
            v *= 1000 if u in ("km", "kilometer") else 1
            u = "meter"
        out.append((v, u))
    return out


def mandiri(b1: Bukti, b2: Bukti) -> bool:
    """dua bukti dari penerbit yang berbeda? (domain beda = independen; DOI beda saja belum tentu)"""
    d1, d2 = b1.domain, b2.domain
    if d1 and d2:
        return d1 != d2
    return (b1.penerbit or "").lower() != (b2.penerbit or "").lower()


# ================================================================================================ verifikasi
def dari_sumber(items: Iterable[Mapping[str, Any]], domain_terpercaya: Sequence[str]) -> list[Bukti]:
    """ubah daftar sumber (sudah divalidasi atau mentah) jadi objek Bukti; kredibel dihitung ULANG."""
    out = []
    for it in items or []:
        if not isinstance(it, Mapping):
            continue
        url = it.get("url")
        kre = bool(it.get("kredibel")) and (
            kredibel_dari_url(url, domain_terpercaya) or (bool(it.get("doi")) and bool(it.get("penerbit")))
        )
        out.append(
            Bukti(
                judul=str(it.get("judul") or "").strip(),
                url=url,
                penerbit=it.get("penerbit") or domain(url),
                tahun=int(it["tahun"]) if str(it.get("tahun", "")).isdigit() else None,
                doi=it.get("doi"),
                kredibel=kre,
                kutipan=int(it["kutipan"]) if str(it.get("kutipan", "")).isdigit() else None,
                diambil=it.get("diambil"),
            )
        )
    return out


def _relevan(klaim: str, bukti: Bukti) -> float:
    kata = {w for w in teks.norm(klaim).split() if len(w) > 3}
    if not kata or not bukti.judul:
        return 0.0
    judul = teks.norm(bukti.judul)
    return round(len([w for w in kata if w in judul]) / len(kata), 3)


def verifikasi(
    t: str,
    bukti: Sequence[Bukti] | Sequence[Mapping[str, Any]] | None = None,
    domain_terpercaya: Sequence[str] = (),
    butuh_independen: int = 1,
) -> Klaim:
    """petakan satu klaim ke bukti yang tersedia -> status + catatan yang bisa diaudit."""
    daftar: list[Bukti] = (
        [b for b in bukti if isinstance(b, Bukti)]
        if bukti and isinstance(bukti[0], Bukti)
        else dari_sumber([b for b in (bukti or []) if isinstance(b, Mapping)], domain_terpercaya)
    )
    jenis = klasifikasi(t)
    k = Klaim(teks=t, jenis=jenis, bukti=[])
    if jenis == SINYAL_MINAT:
        k.status = SINYAL
        k.catatan.append("ini pertanyaan pencarian (sinyal minat), bukan pernyataan - tidak perlu pembuktian")
        k.bukti = list(daftar)
        return k
    if not daftar:
        k.status = TANPA_DATA
        k.catatan.append("tidak ada sumber sama sekali (sumber ilmiah gagal diambil atau tidak dikonfigurasi)")
        return k
    for b in daftar:
        b.relevan = _relevan(t, b)
    k.bukti = sorted(daftar, key=lambda b: (-b.relevan, -(b.kutipan or 0)))
    kre = [b for b in k.bukti if b.kredibel and b.relevan > 0]
    k.penerbit = {b.domain or (b.penerbit or "?").lower() for b in kre}
    if not kre:
        k.status = TIDAK_DIDUKUNG
        k.catatan.append(
            f"{len(k.bukti)} sumber ada tetapi tidak ada yang kredibel & relevan "
            "(domain di luar daftar kanal atau judulnya tidak menyentuh klaim)"
        )
        return k
    # klaim yang MENYEBUT angka: angkanya harus ada di sumber (toleransi 25%); sumber yang saling
    # bertentangan untuk besaran yang sama -> KONFLIK (harus dicek manusia, bukan vonis otomatis)
    angka_klaim = angka_satuan(t)
    if angka_klaim:
        satuan_klaim = {u for _, u in angka_klaim if u} or {""}
        sumber_angka = [(v, u, b) for b in kre for v, u in angka_satuan(b.judul)]
        cocok = [
            (v, u, b)
            for v, u, b in sumber_angka
            for vc, uc in angka_klaim
            if (u == uc or (not u and not uc)) and v > 0 and vc > 0 and abs(v - vc) / max(v, vc) <= 0.25
        ]
        if not cocok and sumber_angka:
            k.status = TIDAK_DIDUKUNG
            k.catatan.append(
                "angka pada klaim tidak ditemukan di sumber kredibel (toleransi 25%): "
                + ", ".join(f"{v:g}{(' ' + u) if u else ''}" for v, u, _ in sumber_angka[:4])
            )
            return k
        for i, (v1, u1, a) in enumerate(cocok):
            for v2, u2, b in cocok[i + 1 :]:
                if u1 == u2 and u2 in satuan_klaim and abs(v1 - v2) / max(v1, v2) > 0.2 and mandiri(a, b):
                    k.status = KONFLIK
                    k.catatan.append(
                        f"sumber berbeda untuk besaran '{u1 or 'angka'}': {v1:g} ({a.penerbit}) vs {v2:g} "
                        f"({b.penerbit}) - heuristik angka, WAJIB dicek manusia sebelum masuk naskah"
                    )
                    return k
    if len(k.penerbit) >= max(1, butuh_independen):
        k.status = DIDUKUNG
        k.catatan.append(
            f"{len(kre)} sumber kredibel relevan dari {len(k.penerbit)} penerbit berbeda "
            f"({', '.join(sorted(k.penerbit)[:3])})"
        )
    else:
        k.status = LEMAH
        k.catatan.append(
            f"hanya {len(k.penerbit)} penerbit independen (butuh {butuh_independen}) - cari sumber kedua "
            "sebelum fakta ini masuk naskah"
        )
    if jenis == INFERENSI:
        k.catatan.append("ini inferensi (bukan fakta pasti): pastikan naskah memakai kata 'diduga/diperkirakan'")
    return k


def verifikasi_banyak(
    daftar_klaim: Iterable[str], bukti: Sequence[Bukti] | Sequence[Mapping[str, Any]], domain_terpercaya: Sequence[str]
) -> list[Klaim]:
    return [verifikasi(t, bukti, domain_terpercaya) for t in daftar_klaim]


def ringkas(daftar: Sequence[Klaim]) -> dict[str, int]:
    out: dict[str, int] = {}
    for k in daftar:
        out[k.status] = out.get(k.status, 0) + 1
    return out


def laporan_md(daftar: Sequence[Klaim]) -> list[str]:
    if not daftar:
        return ["(tidak ada klaim yang diajukan)"]
    out = ["| klaim | jenis | status | penerbit | catatan |", "|---|---|---|---|---|"]
    for k in daftar:
        cat = "; ".join(k.catatan) or "-"
        out.append(f"| {k.teks[:90]} | {k.jenis} | {LABEL.get(k.status, k.status)} | {len(k.penerbit)} | {cat[:110]} |")
    return out


def klaim_dari_frasa(frasa: Iterable[str], batas: int = 6) -> list[str]:
    """kandidat klaim dari frasa pencarian: pertanyaan = sinyal minat; frasa pernyataan = calon fakta."""
    out: list[str] = []
    for f in frasa:
        s = " ".join(str(f).split())
        if not s:
            continue
        if s.lower().split()[0] in KATA_TANYA or s.endswith("?"):
            out.append(s)
        if len(out) >= batas:
            break
    return out
