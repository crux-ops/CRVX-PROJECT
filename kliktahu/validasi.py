"""kliktahu/validasi.py - VALIDASI INPUT & PROVENANCE (tahap 1 rencana upgrade 2026-09).

Semua data yang masuk ke mesin (berkas agen, hasil pencarian, sumber ilmiah, momen live) melewati gerbang ini
SEBELUM dipakai menghitung skor. Prinsip:

* struktur, tipe, dan batas angka ditegakkan; nilai di luar batas DITOLAK, bukan dibulatkan diam-diam
* waktu wajib berzona waktu (ISO 8601 dengan offset) - waktu tanpa zona tidak bisa dipakai menghitung kesegaran
* URL wajib skema http/https, tanpa userinfo (``user:pass@``) dan tanpa rahasia di query
* **kredibilitas TIDAK pernah diberikan secara bawaan**: ``kredibel`` hanya True bila domain penerbit ada di daftar
  kanal (``[sumber_kredibel] domain``) atau sumber menyertakan bukti yang bisa dicek (DOI)
* provenance (siapa mengambil, kapan, dari mana) ikut tersimpan supaya laporan bisa menyebut umur datanya

Galat dikumpulkan, tidak langsung melempar, sehingga satu berkas buruk tidak menghentikan seluruh riset.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

UTC = dt.UTC
MAKS_TEKS = 400
MAKS_URL = 800
TAHUN_MIN = 1600
_SKEMA_URL = ("http", "https")
_PARAM_RAHASIA = {"key", "api_key", "apikey", "token", "access_token", "authorization", "x-subscription-token"}
_DOI = re.compile(r"^10\.\d{4,9}/[^\s\"'<>]+$", re.I)
_WAKTU = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?)?(Z|[+-]\d{2}:?\d{2})?$")


class ValidasiError(ValueError):
    """data tidak sah dan tidak bisa dipakai sama sekali."""


@dataclass(frozen=True)
class Masalah:
    jalur: str  # letak masalah, mis. "sumber_ilmiah[2].url"
    pesan: str
    parah: bool = True  # True = galat (data dibuang), False = peringatan (data dipakai, dicatat)

    def __str__(self) -> str:
        return f"{'GALAT' if self.parah else 'peringatan'} {self.jalur}: {self.pesan}"


@dataclass
class HasilValidasi:
    galat: list[Masalah] = field(default_factory=list)
    peringatan: list[Masalah] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.galat

    def tambah(self, jalur: str, pesan: str, parah: bool = True) -> None:
        (self.galat if parah else self.peringatan).append(Masalah(jalur, pesan, parah))

    def gabung(self, lain: HasilValidasi) -> HasilValidasi:
        self.galat += lain.galat
        self.peringatan += lain.peringatan
        return self

    def ringkas(self) -> str:
        return f"{len(self.galat)} galat, {len(self.peringatan)} peringatan"


# ================================================================================================ primitif
def angka(v: Any, jalur: str, hv: HasilValidasi, lo: float, hi: float, wajib: bool = True) -> float | None:
    """angka dalam rentang [lo, hi]; bool DITOLAK (bool adalah subclass int di Python)."""
    if v is None:
        if wajib:
            hv.tambah(jalur, "wajib ada")
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        hv.tambah(jalur, f"harus angka, bukan {type(v).__name__}")
        return None
    x = float(v)
    if x != x or x in (float("inf"), float("-inf")):
        hv.tambah(jalur, "angka tidak terhingga/NaN")
        return None
    if not lo <= x <= hi:
        hv.tambah(jalur, f"di luar rentang wajar {lo}..{hi} (nilai {x})")
        return None
    return x


def teks(v: Any, jalur: str, hv: HasilValidasi, maks: int = MAKS_TEKS, wajib: bool = True) -> str | None:
    if v is None:
        if wajib:
            hv.tambah(jalur, "wajib ada")
        return None
    if not isinstance(v, str):
        hv.tambah(jalur, f"harus teks, bukan {type(v).__name__}")
        return None
    s = " ".join(v.split()).strip()
    if not s:
        hv.tambah(jalur, "tidak boleh kosong")
        return None
    if len(s) > maks:
        hv.tambah(jalur, f"terlalu panjang ({len(s)} > {maks} karakter)")
        return None
    return s


def url_sah(v: Any, jalur: str, hv: HasilValidasi, wajib: bool = False) -> str | None:
    """URL http/https tanpa userinfo dan tanpa parameter rahasia. None bila tidak wajib & kosong."""
    if v is None or (isinstance(v, str) and not v.strip()):
        if wajib:
            hv.tambah(jalur, "wajib ada")
        return None
    s = str(v).strip()
    if len(s) > MAKS_URL:
        hv.tambah(jalur, f"URL terlalu panjang ({len(s)} > {MAKS_URL})")
        return None
    try:
        p = urlparse(s)
    except ValueError:
        hv.tambah(jalur, "URL tidak bisa diurai")
        return None
    if p.scheme.lower() not in _SKEMA_URL:
        hv.tambah(jalur, f"skema URL harus http/https (dapat {p.scheme or 'kosong'!r})")
        return None
    if not p.netloc:
        hv.tambah(jalur, "URL tanpa host")
        return None
    if "@" in p.netloc:
        hv.tambah(jalur, "URL memuat userinfo (user:pass@host) - berbahaya, ditolak")
        return None
    for k, _ in _param_rahasia_items(p.query):
        if k.lower() in _PARAM_RAHASIA:
            hv.tambah(jalur, f"URL memuat parameter rahasia '{k}'")
            return None
    return s


def _param_rahasia_items(query: str) -> list[tuple[str, str]]:
    from urllib.parse import parse_qsl

    return parse_qsl(query, keep_blank_values=True)


def waktu_berzona(v: Any, jalur: str, hv: HasilValidasi, wajib: bool = False) -> dt.datetime | None:
    """ISO 8601 dengan zona waktu. Waktu tanpa zona DITOLAK (tidak bisa dipakai menghitung umur data)."""
    if v is None or (isinstance(v, str) and not v.strip()):
        if wajib:
            hv.tambah(jalur, "wajib ada (ISO 8601 + zona waktu)")
        return None
    s = str(v).strip()
    if not _WAKTU.match(s):
        hv.tambah(jalur, f"bukan format waktu ISO 8601 yang dikenal: {s[:40]!r}")
        return None
    coba = s.replace(" ", "T")
    if coba.endswith("Z"):
        coba = coba[:-1] + "+00:00"
    try:
        t = dt.datetime.fromisoformat(coba)
    except ValueError:
        hv.tambah(jalur, f"waktu tidak bisa diurai: {s[:40]!r}")
        return None
    if t.tzinfo is None:
        hv.tambah(jalur, "waktu tanpa zona waktu (wajib ada offset, mis. +07:00 atau Z)")
        return None
    return t


def doi_sah(v: Any) -> str | None:
    if not isinstance(v, str):
        return None
    s = v.strip().replace("https://doi.org/", "").replace("http://dx.doi.org/", "")
    return s if _DOI.match(s) else None


def domain(url: str | None) -> str | None:
    if not url:
        return None
    try:
        h = urlparse(url).hostname
    except ValueError:
        return None
    return (h or "").lower() or None


def kredibel_dari_url(url: str | None, domain_terpercaya: Sequence[str]) -> bool:
    """kredibel HANYA bila domain cocok daftar kanal (bukan bawaan True)."""
    h = domain(url)
    if not h:
        return False
    return any(h == d or h.endswith("." + d) for d in domain_terpercaya)


# ================================================================================================ sumber ilmiah
def bersihkan_sumber(
    items: Iterable[Any],
    domain_terpercaya: Sequence[str],
    jalur: str = "sumber_ilmiah",
    diambil: str | None = None,
) -> tuple[list[dict[str, Any]], HasilValidasi]:
    """bersihkan & beri provenance daftar sumber ilmiah. Item yang tidak sah DIBUANG (bukan dipaksa lolos).

    Aturan kredibilitas: domain penerbit harus ada di daftar kanal, ATAU sumber punya DOI yang sah (bisa dicek).
    Field 'kredibel' dari sumber luar TIDAK dipercaya - dihitung ulang di sini.
    """
    hv = HasilValidasi()
    out: list[dict[str, Any]] = []
    for i, it in enumerate(items or []):
        j = f"{jalur}[{i}]"
        if not isinstance(it, Mapping):
            hv.tambah(j, f"harus objek, bukan {type(it).__name__}")
            continue
        hv_item = HasilValidasi()
        judul = teks(it.get("judul"), f"{j}.judul", hv_item, maks=300)
        taut = url_sah(it.get("url"), f"{j}.url", hv_item, wajib=False)
        doi = doi_sah(it.get("doi"))
        tahun_v = angka(it.get("tahun"), f"{j}.tahun", hv_item, TAHUN_MIN, dt.datetime.now(UTC).year + 1, wajib=False)
        penerbit = teks(it.get("penerbit"), f"{j}.penerbit", hv_item, maks=120, wajib=False)
        kutipan = angka(it.get("kutipan"), f"{j}.kutipan", hv_item, 0, 10_000_000, wajib=False)
        terbit = waktu_berzona(it.get("terbit"), f"{j}.terbit", hv_item, wajib=False)
        if hv_item.galat:
            hv.gabung(hv_item)
            continue
        if judul is None:
            continue
        if taut is None and doi is None:
            hv.gabung(hv_item)
            hv.tambah(j, "butuh URL atau DOI (bukti harus bisa dicek)")
            continue
        kredibel = kredibel_dari_url(taut, domain_terpercaya) or (doi is not None and bool(penerbit))
        if it.get("kredibel") is True and not kredibel:
            hv.tambah(
                j, "sumber luar mengaku kredibel tetapi tidak lolos daftar domain/DOI - ditandai tidak kredibel", False
            )
        out.append(
            {
                "judul": judul,
                "url": taut or f"https://doi.org/{doi}",
                "doi": doi,
                "penerbit": penerbit or domain(taut),
                "tahun": int(tahun_v) if tahun_v is not None else None,
                "jenis": teks(it.get("jenis"), f"{j}.jenis", HasilValidasi(), maks=40, wajib=False) or "jurnal",
                "kutipan": int(kutipan) if kutipan is not None else None,
                "terbit": terbit.isoformat() if terbit else None,
                "kredibel": bool(kredibel),
                "diambil": diambil,
            }
        )
        hv.gabung(hv_item)
    return out, hv


# ================================================================================================ berkas data agen
BAGIAN_DIKENAL = {
    "diambil",
    "alat",
    "saran",
    "wiki",
    "berita",
    "tren_harian",
    "pesaing",
    "momen_live",
    "sumber_ilmiah",
    "tanya",
    "cuaca",
    "klaim",
    "_catatan",
}


def validasi_data_agen(
    data: Mapping[str, Any],
    tema_sah: Iterable[str] | None = None,
    domain_terpercaya: Sequence[str] = (),
) -> HasilValidasi:
    """validasi menyeluruh berkas data agen: struktur, tipe, rentang, waktu berzona, URL, penerbit."""
    hv = HasilValidasi()
    if not isinstance(data, Mapping):
        hv.tambah("akar", f"harus objek JSON, bukan {type(data).__name__}")
        return hv
    asing = set(data) - BAGIAN_DIKENAL
    if asing:
        hv.tambah("akar", f"bagian tidak dikenal: {sorted(asing)}")
    diambil = waktu_berzona(data.get("diambil"), "diambil", hv, wajib=False)
    diambil_s = diambil.isoformat() if diambil else None
    if diambil is None:
        hv.tambah("diambil", "tidak ada waktu pengambilan - umur data tidak bisa dihitung", parah=False)
    teks(data.get("alat"), "alat", hv, maks=200, wajib=False)

    saran = data.get("saran", {})
    if not isinstance(saran, Mapping):
        hv.tambah("saran", "harus objek {google: {...}, youtube: {...}}")
    else:
        for sumber, isi in saran.items():
            if sumber not in ("google", "youtube"):
                hv.tambah(f"saran.{sumber}", "sumber saran harus 'google' atau 'youtube'")
                continue
            if not isinstance(isi, Mapping):
                hv.tambah(f"saran.{sumber}", "harus objek {kueri: [frasa]}")
                continue
            for q, daftar in isi.items():
                qq = teks(q, f"saran.{sumber}.<kueri>", hv, maks=120, wajib=False)
                if not isinstance(daftar, list):
                    hv.tambah(f"saran.{sumber}[{qq}]", f"harus daftar teks, bukan {type(daftar).__name__}")
                    continue
                for i, f in enumerate(daftar):
                    if not isinstance(f, str) or not f.strip():
                        hv.tambah(f"saran.{sumber}[{qq}][{i}]", "frasa kosong/bukan teks")
                    elif len(f) > 200:
                        hv.tambah(f"saran.{sumber}[{qq}][{i}]", "frasa > 200 karakter")

    for bagian, wajib_angka in (("berita", ("n7", "n28")), ("pesaing", ("jumlah", "umur_median_hari"))):
        isi = data.get(bagian, {})
        if not isinstance(isi, Mapping):
            hv.tambah(bagian, "harus objek {tema: {...}}")
            continue
        for tema, v in isi.items():
            if tema_sah is not None and tema not in set(tema_sah):
                hv.tambah(f"{bagian}.{tema}", "tema tidak ada di registri tema")
            if not isinstance(v, Mapping):
                hv.tambah(f"{bagian}.{tema}", "harus objek")
                continue
            for kk in wajib_angka:
                angka(v.get(kk), f"{bagian}.{tema}.{kk}", hv, 0, 1e9, wajib=False)
            if "rasio" in v:
                angka(v.get("rasio"), f"{bagian}.{tema}.rasio", hv, 0, 1e4, wajib=False)

    wiki = data.get("wiki", {})
    if not isinstance(wiki, Mapping):
        hv.tambah("wiki", "harus objek {tema: {...}}")
    else:
        for tema, v in wiki.items():
            if tema_sah is not None and tema not in set(tema_sah):
                hv.tambah(f"wiki.{tema}", "tema tidak ada di registri tema")
            if not isinstance(v, Mapping):
                hv.tambah(f"wiki.{tema}", "harus objek")
                continue
            if "bulanan" in v:
                if not isinstance(v["bulanan"], Mapping) or not v["bulanan"]:
                    hv.tambah(f"wiki.{tema}.bulanan", "harus objek {YYYY-MM: jumlah}")
                else:
                    for bulan, n in v["bulanan"].items():
                        if not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", str(bulan)):
                            hv.tambah(f"wiki.{tema}.bulanan.{bulan}", "kunci harus format YYYY-MM")
                        angka(n, f"wiki.{tema}.bulanan.{bulan}", hv, 0, 1e10, wajib=False)
                    angka(v.get("hari_bulan_ini"), f"wiki.{tema}.hari_bulan_ini", hv, 1, 31, wajib=False)
            else:
                angka(v.get("views60"), f"wiki.{tema}.views60", hv, 0, 1e12, wajib=False)
                if "tren" in v:
                    angka(v.get("tren"), f"wiki.{tema}.tren", hv, 0, 100, wajib=False)

    for i, m in enumerate(data.get("momen_live", []) or []):
        j = f"momen_live[{i}]"
        if not isinstance(m, Mapping):
            hv.tambah(j, "harus objek")
            continue
        teks(m.get("nama"), f"{j}.nama", hv, maks=160)
        try:
            if m.get("tanggal"):
                dt.date.fromisoformat(str(m["tanggal"]))
            if m.get("selesai"):
                dt.date.fromisoformat(str(m["selesai"]))
        except (ValueError, TypeError):
            hv.tambah(f"{j}.tanggal", "tanggal harus format YYYY-MM-DD")
        angka(m.get("urgensi"), f"{j}.urgensi", hv, 0, 1, wajib=False)
        if not isinstance(m.get("tema", []), (list, tuple)):
            hv.tambah(f"{j}.tema", "harus daftar nama tema")

    if "sumber_ilmiah" in data:
        if not isinstance(data["sumber_ilmiah"], Mapping):
            hv.tambah("sumber_ilmiah", "harus objek {tema: [..]}")
        else:
            for tema, daftar in data["sumber_ilmiah"].items():
                if tema_sah is not None and tema not in set(tema_sah):
                    hv.tambah(f"sumber_ilmiah.{tema}", "tema tidak ada di registri tema")
                _, hv2 = bersihkan_sumber(daftar, domain_terpercaya, f"sumber_ilmiah.{tema}", diambil_s)
                hv.gabung(hv2)

    for i, t in enumerate(data.get("tren_harian", []) or []):
        j = f"tren_harian[{i}]"
        if not isinstance(t, Mapping):
            hv.tambah(j, "harus objek")
            continue
        teks(t.get("judul"), f"{j}.judul", hv, maks=200)
        angka(t.get("traffic"), f"{j}.traffic", hv, 0, 1e9, wajib=False)

    for i, c in enumerate(data.get("klaim", []) or []):
        j = f"klaim[{i}]"
        if not isinstance(c, Mapping):
            hv.tambah(j, "harus objek")
            continue
        teks(c.get("teks"), f"{j}.teks", hv, maks=300)
        if "jenis" in c and c["jenis"] not in ("fakta", "inferensi", "sinyal_minat"):
            hv.tambah(f"{j}.jenis", "jenis harus fakta|inferensi|sinyal_minat")
    return hv
