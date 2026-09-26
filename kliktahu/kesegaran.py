"""kliktahu/kesegaran.py - STATUS & KESEGARAN SUMBER (tahap 2 rencana upgrade 2026-09).

Masalah yang dipecahkan: laporan riset lama hanya mencatat "sumber ok" tanpa umur data, sehingga data cache yang
sudah berumur minggu terlihat sama dengan data yang baru diambil. Modul ini memisahkan lima keadaan:

  LIVE          baru diambil dari jaringan pada run ini
  CACHE_SEGAR   dari cache/berkas, masih di dalam TTL sumbernya
  KEDALUWARSA   ada, tetapi lebih tua dari TTL -> boleh dipakai, HARUS diberi tanda di laporan & menurunkan keyakinan
  OFFLINE       sumber tidak terjangkau (jaringan/host diblokir) -> tidak ada data
  FIXTURE       data contoh/uji (bukan data nyata) -> tidak boleh dianggap data pasar

TTL per JENIS sumber (bukan per URL) supaya umpan cepat (momen gempa) tidak disamakan dengan jurnal ilmiah.
Waktu pengambilan (``diambil``) ikut dilaporkan, bukan hanya waktu laporan dibuat.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

UTC = dt.UTC

LIVE = "live"
CACHE_SEGAR = "cache_segar"
KEDALUWARSA = "kedaluwarsa"
OFFLINE = "offline"
FIXTURE = "fixture"
TANPA_DATA = "tanpa_data"

SEMUA_STATUS = (LIVE, CACHE_SEGAR, KEDALUWARSA, OFFLINE, FIXTURE, TANPA_DATA)

LABEL = {
    LIVE: "LIVE (diambil run ini)",
    CACHE_SEGAR: "CACHE (segar)",
    KEDALUWARSA: "KEDALUWARSA (lewat TTL)",
    OFFLINE: "OFFLINE (tidak terjangkau)",
    FIXTURE: "FIXTURE (data uji, bukan data nyata)",
    TANPA_DATA: "TANPA DATA",
}

# TTL (jam) per JENIS sumber. Umpan momen harus segar; jurnal ilmiah boleh berumur berminggu-minggu.
TTL_JAM: dict[str, float] = {
    "saran": 12.0,  # Google/YouTube Autocomplete: cepat berubah
    "pencarian": 12.0,
    "momen": 0.5,  # gempa/cuaca: 30 menit
    "cuaca": 3.0,  # ramalan Open-Meteo
    "berita": 6.0,
    "tren": 2.0,  # Google Trends harian
    "wiki": 24.0,
    "wiki_top": 24.0,
    "pesaing": 24.0,
    "ilmiah": 168.0,  # jurnal/lembaga: seminggu
    "klaim": 168.0,
    "performa": 720.0,  # ekspor YouTube Studio
}
TTL_BAWAAN = 24.0

# status yang boleh tetap dipakai untuk menghitung skor (dengan penalti keyakinan untuk KEDALUWARSA)
PAKAI = (LIVE, CACHE_SEGAR, KEDALUWARSA, FIXTURE)
PENGALI_YAKIN = {LIVE: 1.0, CACHE_SEGAR: 0.95, KEDALUWARSA: 0.6, FIXTURE: 0.3, OFFLINE: 0.0, TANPA_DATA: 0.0}


@dataclass(frozen=True)
class Status:
    jenis: str
    status: str
    diambil: dt.datetime | None = None
    ttl_jam: float = TTL_BAWAAN
    sumber: str = ""
    catatan: str = ""

    @property
    def umur_jam(self) -> float | None:
        return None if self.diambil is None else max(0.0, umur_detik(self.diambil) / 3600.0)

    @property
    def pakai(self) -> bool:
        return self.status in PAKAI

    @property
    def segar(self) -> bool:
        return self.status in (LIVE, CACHE_SEGAR)

    @property
    def yakin(self) -> float:
        return PENGALI_YAKIN.get(self.status, 0.0)

    def baris(self) -> dict[str, Any]:
        return {
            "jenis": self.jenis,
            "status": self.status,
            "sumber": self.sumber,
            "diambil": self.diambil.isoformat() if self.diambil else None,
            "umur_jam": round(self.umur_jam, 2) if self.umur_jam is not None else None,
            "ttl_jam": self.ttl_jam,
            "catatan": self.catatan or None,
        }

    def __str__(self) -> str:
        umur = f"{self.umur_jam:.1f} jam" if self.umur_jam is not None else "-"
        return f"{self.jenis}: {LABEL.get(self.status, self.status)} (umur {umur}, TTL {self.ttl_jam:g} jam)"


def sekarang() -> dt.datetime:
    return dt.datetime.now(UTC)


def umur_detik(waktu: dt.datetime, kini: dt.datetime | None = None) -> float:
    return ((kini or sekarang()) - waktu).total_seconds()


def ttl(jenis: str, ubah: Mapping[str, float] | None = None) -> float:
    if ubah and jenis in ubah:
        return float(ubah[jenis])
    return TTL_JAM.get(jenis, TTL_BAWAAN)


def status_sumber(
    jenis: str,
    diambil: dt.datetime | str | None,
    kini: dt.datetime | None = None,
    ttl_jam: Mapping[str, float] | float | None = None,
    sumber: str = "",
    dari_jaringan: bool = False,
    fixture: bool = False,
    catatan: str = "",
) -> Status:
    """status satu sumber. `dari_jaringan` = diambil pada run ini (LIVE). `fixture` = data uji.

    Waktu tanpa zona waktu dianggap UTC agar tidak menolak data lama secara diam-diam, tetapi dicatat.
    """
    batas = float(ttl_jam) if isinstance(ttl_jam, (int, float)) else ttl(jenis, ttl_jam)
    kini = kini or sekarang()
    if diambil is None:
        return Status(jenis, OFFLINE if catatan else TANPA_DATA, None, batas, sumber, catatan)
    t = diambil
    if isinstance(t, str):
        try:
            t = dt.datetime.fromisoformat(t.replace("Z", "+00:00"))
        except ValueError:
            return Status(jenis, TANPA_DATA, None, batas, sumber, "waktu pengambilan tidak bisa diurai")
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
        catatan = (catatan + "; " if catatan else "") + "waktu tanpa zona (dianggap UTC)"
    if fixture:
        return Status(jenis, FIXTURE, t, batas, sumber, catatan)
    if dari_jaringan:
        return Status(jenis, LIVE, t, batas, sumber, catatan)
    umur = umur_detik(t, kini) / 3600.0
    return Status(jenis, KEDALUWARSA if umur > batas else CACHE_SEGAR, t, batas, sumber, catatan)


def gabung(status: Iterable[Status]) -> dict[str, Status]:
    """satu status perjenis: ambil yang PALING segar (LIVE > cache > kedaluwarsa > offline)."""
    urutan = {LIVE: 0, CACHE_SEGAR: 1, KEDALUWARSA: 2, FIXTURE: 3, OFFLINE: 4, TANPA_DATA: 5}
    out: dict[str, Status] = {}
    for s in status:
        if s.jenis not in out or urutan.get(s.status, 9) < urutan.get(out[s.jenis].status, 9):
            out[s.jenis] = s
    return out


def keyakinan_data(status: Sequence[Status]) -> float:
    """0..1: porsi jenis sumber yang datanya masih segar (kedaluwarsa dihitung sebagian)."""
    if not status:
        return 0.0
    return round(sum(PENGALI_YAKIN.get(s.status, 0.0) for s in status) / len(status), 4)


def ringkas(status: Iterable[Status]) -> str:
    d = gabung(status)
    if not d:
        return "tidak ada sumber"
    return "; ".join(str(s) for _, s in sorted(d.items()))


def tabel_md(status: Iterable[Status]) -> list[str]:
    d = gabung(status)
    if not d:
        return ["| - | - | - | - | - |"]
    out = ["| jenis | status | sumber | diambil (UTC) | umur |", "|---|---|---|---|---|"]
    for _, s in sorted(d.items()):
        diambil = s.diambil.strftime("%Y-%m-%d %H:%M") if s.diambil else "-"
        umur = "-" if s.umur_jam is None else f"{s.umur_jam:.1f} jam"
        out.append(f"| {s.jenis} | {LABEL.get(s.status, s.status)} | {s.sumber or '-'} | {diambil} | {umur} |")
    return out
