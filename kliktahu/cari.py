"""kliktahu/cari.py - LAPISAN PENCARIAN MULTISUMBER real-time (tahap 3 rencana upgrade 2026-09).

Satu pintu untuk "cari sesuatu" dari banyak sumber sekaligus. Tiap sumber dibungkus ADAPTOR yang seragam:

* punya id, jenis, label, TTL, dan status kunci (butuh kunci API atau tidak)
* dijalankan dengan batas waktu, kuota per run, dan jeda sopan (dari ``riset/http.py``)
* gagal -> dicatat, TIDAK menghentikan sumber lain; satu jenis punya RANTAI CADANGAN (fallback)
* hasil digabung, dideduplikasi (URL/judul), dan distempel status kesegarannya (``kesegaran.py``)

Mode:
  online - internet langsung (dipakai di komputer biasa)
  uji    - transport palsu deterministik (``riset/fixture.py``), seluruh jalur HTTP tetap dilalui
  agen   - tanpa klien HTTP: hasil diisi dari data agen (lihat ``PencariAgen``)

Tidak ada server, tidak ada antrean: ini pustaka yang dipanggil ``analisis.py`` dan CLI ``kliktahu cari``.
"""

from __future__ import annotations

import datetime as dt
import time
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from . import astro, teks
from . import kanal as kanal_mod
from . import kesegaran as G
from .riset import agen as AG
from .riset import sumber as SB
from .riset.http import GagalHTTP, KlienRiset, Offline
from .tema import TEMA

UTC = dt.UTC

# jenis sumber (dipakai TTL & rantai cadangan)
SARAN = "saran"
WIKI = "wiki"
BERITA = "berita"
TREN = "tren"
ILMIAH = "ilmiah"
MOMEN = "momen"
CUACA = "cuaca"
WEB = "web"
PESAING = "pesaing"

SEMUA_JENIS: tuple[str, ...] = (SARAN, WIKI, BERITA, TREN, ILMIAH, MOMEN, CUACA, WEB, PESAING)

# rantai cadangan per jenis: sumber pertama yang memberi hasil dipakai, sisanya tidak dihubungi
RANTAI: dict[str, tuple[str, ...]] = {
    SARAN: ("saran_google", "saran_youtube"),
    WIKI: ("wiki_cari", "wiki_pageview", "wiki_top"),
    BERITA: ("berita_gnews", "berita_gdelt"),
    TREN: ("tren_google",),
    ILMIAH: ("ilmiah_openalex", "ilmiah_crossref", "ilmiah_europepmc"),
    MOMEN: ("momen_bmkg", "momen_usgs", "momen_noaa", "momen_eonet", "momen_jpl", "cuaca_ekstrem"),
    CUACA: ("cuaca_ekstrem",),
    WEB: ("web_brave", "web_searxng"),
    PESAING: ("pesaing_youtube",),
}

# kuota bawaan: maksimal panggilan per sumber dalam SATU runanalisis (menghormati server & kuota API)
KUOTA_BAWAAN: dict[str, int] = {
    "saran_google": 400,
    "saran_youtube": 400,
    "wiki_cari": 80,
    "wiki_pageview": 80,
    "wiki_top": 2,
    "berita_gnews": 40,
    "berita_gdelt": 20,
    "tren_google": 2,
    "ilmiah_openalex": 20,
    "ilmiah_crossref": 20,
    "ilmiah_europepmc": 20,
    "momen_bmkg": 2,
    "momen_usgs": 2,
    "momen_noaa": 2,
    "momen_eonet": 2,
    "momen_jpl": 2,
    "cuaca_ekstrem": 6,
    "web_brave": 10,
    "web_searxng": 10,
    "pesaing_youtube": 10,
}


@dataclass
class Hasil:
    """satu temuan dari satu sumber (bukan frozen: status & waktu diambil distempel setelah diambil)."""

    sumber: str
    jenis: str
    kueri: str
    judul: str
    url: str | None = None
    cuplik: str | None = None
    metrik: float | None = None  # views / traffic / peringkat / posisi (makna bergantung sumber)
    satuan: str = ""
    terbit: str | None = None
    status: str = G.TANPA_DATA
    diambil: str | None = None
    mentah: dict[str, Any] | None = None

    @property
    def segar(self) -> bool:
        return self.status in (G.LIVE, G.CACHE_SEGAR)

    def kunci(self) -> tuple[str, str]:
        """kunci deduplikasi: URL bila ada, kalau tidak judul ternormalisasi."""
        return (self.url or "", teks.norm(self.judul))

    def ringkas(self) -> str:
        if self.metrik is None:
            return f"({self.sumber}) {self.judul}"
        n = f"{self.metrik:,.0f}" if abs(self.metrik) >= 100 else f"{self.metrik:g}"
        return f"({self.sumber}) {self.judul} [{n}{(' ' + self.satuan) if self.satuan else ''}]"


@dataclass
class Catatan:
    """jejak satu percobaan sumber (untuk observabilitas)."""

    sumber: str
    jenis: str
    kueri: str
    ok: bool
    jumlah: int = 0
    durasi_ms: int = 0
    alasan: str = ""
    dari_cache: bool = False

    def baris(self) -> dict[str, Any]:
        return {
            "sumber": self.sumber,
            "jenis": self.jenis,
            "kueri": self.kueri,
            "ok": self.ok,
            "jumlah": self.jumlah,
            "durasi_ms": self.durasi_ms,
            "alasan": self.alasan or None,
            "dari_cache": self.dari_cache,
        }


@dataclass
class LaporanCari:
    kueri: str
    hasil: list[Hasil] = field(default_factory=list)
    status: list[G.Status] = field(default_factory=list)
    catatan: list[Catatan] = field(default_factory=list)
    dilewati: list[tuple[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.hasil)

    def per_jenis(self) -> dict[str, list[Hasil]]:
        out: dict[str, list[Hasil]] = {}
        for h in self.hasil:
            out.setdefault(h.jenis, []).append(h)
        return out

    def gagal(self) -> list[Catatan]:
        return [c for c in self.catatan if not c.ok]

    def ringkas(self) -> str:
        return f"{len(self.hasil)} temuan dari {len({h.sumber for h in self.hasil})} sumber" + (
            f", {len(self.gagal())} sumber gagal" if self.gagal() else ""
        )


# ================================================================================================ adaptor
def _saran(sumber: str, ds: str) -> Callable[..., list[Hasil]]:
    def ambil(klien: KlienRiset, kueri: str, k: kanal_mod.Kanal, hari: dt.date) -> list[Hasil]:
        daftar = SB.saran(klien, kueri, ds)
        sekarang = dt.datetime.now(UTC).isoformat()
        return [
            Hasil(
                sumber=sumber,
                jenis=SARAN,
                kueri=kueri,
                judul=s,
                metrik=float(10 - i),  # posisi: 10 = teratas
                satuan="posisi",
                status=G.LIVE,
                diambil=sekarang,
            )
            for i, s in enumerate(daftar)
        ]

    return ambil


def _ambil_wiki_cari(klien: KlienRiset, kueri: str, k: kanal_mod.Kanal, hari: dt.date) -> list[Hasil]:
    judul = SB.wiki_judul(klien, kueri) or SB.wiki_kanonik(klien, kueri)
    if not judul:
        return []
    return [
        Hasil(
            sumber="wiki_cari",
            jenis=WIKI,
            kueri=kueri,
            judul=judul,
            url=f"https://id.wikipedia.org/wiki/{judul.replace(' ', '_')}",
            cuplik="judul kanonik (alihan diikuti)",
            status=G.LIVE,
            diambil=dt.datetime.now(UTC).isoformat(),
        )
    ]


def _ambil_wiki_pageview(klien: KlienRiset, kueri: str, k: kanal_mod.Kanal, hari: dt.date) -> list[Hasil]:
    judul = kueri
    w = SB.wiki_views(klien, judul, hari)
    if not w:
        return []
    return [
        Hasil(
            sumber="wiki_pageview",
            jenis=WIKI,
            kueri=kueri,
            judul=str(w.get("judul") or judul),
            url=f"https://id.wikipedia.org/wiki/{str(w.get('judul') or judul).replace(' ', '_')}",
            cuplik=f"tren {w.get('tren')}x, lonjakan z {w.get('lonjakan_z')}",
            metrik=float(w.get("views60") or 0),
            satuan="views/60h",
            status=G.LIVE,
            diambil=dt.datetime.now(UTC).isoformat(),
            mentah={kk: v for kk, v in w.items() if kk != "judul"},
        )
    ]


def _ambil_wiki_top(klien: KlienRiset, kueri: str, k: kanal_mod.Kanal, hari: dt.date) -> list[Hasil]:
    daftar = SB.wiki_top(klien, hari, k.bahasa)
    sekarang = dt.datetime.now(UTC).isoformat()
    return [
        Hasil(
            sumber="wiki_top",
            jenis=WIKI,
            kueri=kueri or "top harian",
            judul=a["judul"],
            url=f"https://{k.bahasa}.wikipedia.org/wiki/{a['judul'].replace(' ', '_')}",
            metrik=float(a["views"]),
            satuan="views/hari",
            status=G.LIVE,
            diambil=sekarang,
            mentah={"peringkat": a["peringkat"]},
        )
        for a in daftar
    ]


def _ambil_berita(klien: KlienRiset, kueri: str, k: kanal_mod.Kanal, hari: dt.date) -> list[Hasil]:
    sekarang = dt.datetime(hari.year, hari.month, hari.day, 9, tzinfo=UTC)
    b = SB.berita(klien, kueri, sekarang)
    return [
        Hasil(
            sumber="berita_gnews",
            jenis=BERITA,
            kueri=kueri,
            judul=j,
            status=G.LIVE,
            diambil=dt.datetime.now(UTC).isoformat(),
        )
        for j in b.get("judul", [])
    ] + [
        Hasil(
            sumber="berita_gnews",
            jenis=BERITA,
            kueri=kueri,
            judul=f"{int(b.get('n7', 0))} berita 7 hari (rasio {b.get('rasio')}x)",
            metrik=float(b.get("n7", 0)),
            satuan="berita/7h",
            status=G.LIVE,
            diambil=dt.datetime.now(UTC).isoformat(),
            mentah={kk: b.get(kk) for kk in ("n7", "n28", "rasio")},
        )
    ]


def _ambil_gdelt(klien: KlienRiset, kueri: str, k: kanal_mod.Kanal, hari: dt.date) -> list[Hasil]:
    g = SB.gdelt(klien, kueri)
    if not g:
        return []
    return [
        Hasil(
            sumber="berita_gdelt",
            jenis=BERITA,
            kueri=kueri,
            judul=f"Volume liputan GDELT 7 hari (rasio {g['rasio']}x)",
            metrik=float(g.get("n7", 0)),
            satuan="dokumen",
            status=G.LIVE,
            diambil=dt.datetime.now(UTC).isoformat(),
            mentah=dict(g),
        )
    ]


def _ambil_tren(klien: KlienRiset, kueri: str, k: kanal_mod.Kanal, hari: dt.date) -> list[Hasil]:
    daftar = SB.tren_harian(klien, k.wilayah)
    return [
        Hasil(
            sumber="tren_google",
            jenis=TREN,
            kueri=kueri,
            judul=t["judul"],
            metrik=float(t.get("traffic") or 0),
            satuan="pencarian/hari",
            terbit=t.get("terbit"),
            status=G.LIVE,
            diambil=dt.datetime.now(UTC).isoformat(),
            mentah={"berita": t.get("berita", [])[:3]},
        )
        for t in daftar
    ]


def _ilmiah(nama: str, fn: Callable[[KlienRiset, str], list[dict[str, Any]]]) -> Callable[..., list[Hasil]]:
    def ambil(klien: KlienRiset, kueri: str, k: kanal_mod.Kanal, hari: dt.date) -> list[Hasil]:
        sekarang = dt.datetime.now(UTC).isoformat()
        out = []
        for s in fn(klien, kueri):
            out.append(
                Hasil(
                    sumber=nama,
                    jenis=ILMIAH,
                    kueri=kueri,
                    judul=str(s.get("judul") or ""),
                    url=s.get("url"),
                    cuplik=" - ".join(str(s.get(x)) for x in ("penerbit", "tahun") if s.get(x)),
                    metrik=_angka(s.get("kutipan")),
                    satuan="kutipan",
                    status=G.LIVE,
                    diambil=sekarang,
                    mentah=dict(s),
                )
            )
        return out

    return ambil


def _momen(fn: Callable[[KlienRiset, dt.date], Any], nama: str) -> Callable[..., list[Hasil]]:
    def ambil(klien: KlienRiset, kueri: str, k: kanal_mod.Kanal, hari: dt.date) -> list[Hasil]:
        daftar = fn(klien, hari)
        if isinstance(daftar, tuple):
            daftar = daftar[0]
        sekarang = dt.datetime.now(UTC).isoformat()
        out = []
        for m in daftar:
            out.append(
                Hasil(
                    sumber=nama,
                    jenis=MOMEN,
                    kueri=kueri or "momen live",
                    judul=m.nama,
                    cuplik=", ".join(m.tema),
                    metrik=float(m.urgensi),
                    satuan="urgensi",
                    terbit=m.tanggal.isoformat(),
                    status=G.LIVE,
                    diambil=sekarang,
                    mentah={"sumber": m.sumber, "jenis": m.jenis},
                )
            )
        return out

    return ambil


def _ambil_cuaca(klien: KlienRiset, kueri: str, k: kanal_mod.Kanal, hari: dt.date) -> list[Hasil]:
    """ramalan cuaca kota (kueri = nama kota; kosong = Jakarta). Cuaca ekstrem = calon momen."""
    nama = (kueri or "Jakarta").strip().lower()
    kota = next((c for c in astro.KOTA if c.nama.lower() == nama), None) or astro.KOTA[4]
    d = SB.cuaca(klien, kota.lat, kota.lon)
    sekarang = dt.datetime.now(UTC).isoformat()
    out = [
        Hasil(
            sumber="cuaca_ekstrem",
            jenis=CUACA,
            kueri=kota.nama,
            judul=f"{kota.nama}: ramalan {len(d.get('hari', []))} hari",
            metrik=float(sum(h["hujan_mm"] for h in d.get("hari", []))),
            satuan="mm/hari",
            status=G.LIVE,
            diambil=sekarang,
            mentah={"hari": d.get("hari", [])},
        )
    ]
    for e in d.get("ekstrem", []):
        out.append(
            Hasil(
                sumber="cuaca_ekstrem",
                jenis=MOMEN,
                kueri=kota.nama,
                judul=f"{kota.nama}: {e['jenis']} {e['nilai']} {e['satuan']} ({e['tanggal']})",
                metrik=float(e["nilai"]),
                satuan=e["satuan"],
                terbit=e["tanggal"],
                status=G.LIVE,
                diambil=sekarang,
                mentah=dict(e),
            )
        )
    return out


def _ambil_brave(klien: KlienRiset, kueri: str, k: kanal_mod.Kanal, hari: dt.date) -> list[Hasil]:
    key = k.riset.rahasia(k.riset.env_brave_key)
    if not key:
        return []
    d = SB.brave(klien, kueri, key)
    sekarang = dt.datetime.now(UTC).isoformat()
    return [
        *[
            Hasil(
                sumber="web_brave",
                jenis=WEB,
                kueri=kueri,
                judul=r["judul"],
                url=r.get("url"),
                cuplik=r.get("cuplik"),
                status=G.LIVE,
                diambil=sekarang,
            )
            for r in d.get("hasil", [])
        ],
        *[
            Hasil(
                sumber="web_brave",
                jenis=WEB,
                kueri=kueri,
                judul=t["tanya"],
                url=t.get("url"),
                satuan="pertanyaan",
                status=G.LIVE,
                diambil=sekarang,
            )
            for t in d.get("tanya", [])
        ],
    ]


def _ambil_searxng(klien: KlienRiset, kueri: str, k: kanal_mod.Kanal, hari: dt.date) -> list[Hasil]:
    base = k.riset.rahasia(k.riset.env_searxng_url)
    if not base:
        return []
    d = SB.searxng(klien, base, kueri)
    sekarang = dt.datetime.now(UTC).isoformat()
    return [
        Hasil(
            sumber="web_searxng",
            jenis=WEB,
            kueri=kueri,
            judul=r["judul"],
            url=r.get("url"),
            cuplik=r.get("cuplik"),
            status=G.LIVE,
            diambil=sekarang,
        )
        for r in d.get("hasil", [])
    ]


def _ambil_pesaing(klien: KlienRiset, kueri: str, k: kanal_mod.Kanal, hari: dt.date) -> list[Hasil]:
    key = k.riset.rahasia(k.riset.env_youtube_key)
    if not key:
        return []
    p = SB.youtube_pesaing(klien, kueri, key, hari)
    out = [
        Hasil(
            sumber="pesaing_youtube",
            jenis=PESAING,
            kueri=kueri,
            judul=j,
            status=G.LIVE,
            diambil=dt.datetime.now(UTC).isoformat(),
        )
        for j in p.get("judul", [])
    ]
    out.append(
        Hasil(
            sumber="pesaing_youtube",
            jenis=PESAING,
            kueri=kueri,
            judul="ringkasan kejenuhan pesaing",
            cuplik=f"{p.get('jumlah')} video kuat, median {p.get('median_views')} views",
            metrik=float(p.get("median_views") or 0),
            satuan="views",
            status=G.LIVE,
            diambil=dt.datetime.now(UTC).isoformat(),
            mentah={kk: p.get(kk) for kk in ("jumlah", "umur_median_hari", "median_views", "rasio_outlier")},
        )
    )
    return out


@dataclass(frozen=True)
class SumberCari:
    id: str
    jenis: str
    label: str
    ambil: Callable[..., list[Hasil]]
    butuh_kunci: bool = False
    ttl_jam: float | None = None

    @property
    def ttl(self) -> float:
        return self.ttl_jam if self.ttl_jam is not None else G.ttl(self.jenis)


SUMBER: dict[str, SumberCari] = {
    s.id: s
    for s in (
        SumberCari("saran_google", SARAN, "Google Autocomplete", _saran("saran_google", "google")),
        SumberCari("saran_youtube", SARAN, "YouTube Autocomplete", _saran("saran_youtube", "youtube")),
        SumberCari("wiki_cari", WIKI, "Wikipedia (judul kanonik)", _ambil_wiki_cari),
        SumberCari("wiki_pageview", WIKI, "Wikipedia pageview 60 hari", _ambil_wiki_pageview),
        SumberCari("wiki_top", WIKI, "Wikipedia teratas harian", _ambil_wiki_top),
        SumberCari("berita_gnews", BERITA, "Google News RSS", _ambil_berita),
        SumberCari("berita_gdelt", BERITA, "GDELT DOC 2.0", _ambil_gdelt),
        SumberCari("tren_google", TREN, "Google Trends harian", _ambil_tren),
        SumberCari("ilmiah_openalex", ILMIAH, "OpenAlex", _ilmiah("ilmiah_openalex", SB.openalex)),
        SumberCari("ilmiah_crossref", ILMIAH, "Crossref (DOI)", _ilmiah("ilmiah_crossref", SB.crossref)),
        SumberCari("ilmiah_europepmc", ILMIAH, "Europe PMC", _ilmiah("ilmiah_europepmc", SB.europepmc)),
        SumberCari("momen_bmkg", MOMEN, "BMKG gempa", _momen(SB.momen_bmkg, "momen_bmkg")),
        SumberCari("momen_usgs", MOMEN, "USGS gempa", _momen(SB.momen_usgs, "momen_usgs")),
        SumberCari("momen_noaa", MOMEN, "NOAA SWPC badai geomagnetik", _momen(SB.momen_noaa, "momen_noaa")),
        SumberCari("momen_jpl", MOMEN, "NASA JPL asteroid dekat", _momen(SB.momen_jpl, "momen_jpl")),
        SumberCari("momen_eonet", MOMEN, "NASA EONET peristiwa alam", _momen(SB.momen_eonet, "momen_eonet")),
        SumberCari("cuaca_ekstrem", CUACA, "Open-Meteo ramalan cuaca", _ambil_cuaca, ttl_jam=3.0),
        SumberCari("web_brave", WEB, "Brave Search", _ambil_brave, butuh_kunci=True),
        SumberCari("web_searxng", WEB, "SearXNG sendiri", _ambil_searxng, butuh_kunci=True),
        SumberCari("pesaing_youtube", PESAING, "YouTube Data API", _ambil_pesaing, butuh_kunci=True),
    )
}


def daftar_sumber(jenis: str | Iterable[str] | None = None, hanya_aktif: bool = True) -> list[SumberCari]:
    """daftar adaptor; `hanya_aktif` membuang sumber yang butuh kunci bila kuncinya tidak diisi."""
    from . import kanal as K

    k = K.muat()
    pilih = {jenis} if isinstance(jenis, str) else set(jenis) if jenis else set(SEMUA_JENIS)
    out = []
    for s in SUMBER.values():
        if s.jenis not in pilih:
            continue
        if hanya_aktif and s.butuh_kunci and not _kunci_ada(s, k):
            continue
        out.append(s)
    return out


def _kunci_ada(s: SumberCari, k: kanal_mod.Kanal) -> bool:
    return {
        "web_brave": bool(k.riset.rahasia(k.riset.env_brave_key)),
        "web_searxng": bool(k.riset.rahasia(k.riset.env_searxng_url)),
        "pesaing_youtube": bool(k.riset.rahasia(k.riset.env_youtube_key)),
    }.get(s.id, True)


# ================================================================================================ mesin cari
class Pencari:
    """pencarian multi-sumber dengan kuota, rantai cadangan, deduplikasi, dan jejak status."""

    def __init__(
        self,
        klien: KlienRiset | None,
        kanal: kanal_mod.Kanal | None = None,
        hari: dt.date | None = None,
        mode: str = "online",
        kuota: Mapping[str, int] | None = None,
        ttl: Mapping[str, float] | None = None,
    ) -> None:
        self.klien = klien
        self.k = kanal or kanal_mod.muat()
        self.hari = hari or G.sekarang().date()
        self.mode = mode
        self.kuota = dict(KUOTA_BAWAAN)
        if kuota:
            self.kuota.update({kk: int(v) for kk, v in kuota.items()})
        self.ttl = dict(ttl or {})
        self.pakai: Counter[str] = Counter()
        self.status: list[G.Status] = []
        self.catatan: list[Catatan] = []

    # ------------------------------------------------------------------------------------ inti
    def _boleh(self, id_sumber: str) -> str | None:
        if self.klien is None:
            return "tidak ada klien HTTP (mode agen/offline)"
        if self.pakai[id_sumber] >= self.kuota.get(id_sumber, 5):
            return f"kuota habis ({self.pakai[id_sumber]}/{self.kuota.get(id_sumber, 5)})"
        return None

    def _satu(self, id_sumber: str, kueri: str) -> tuple[list[Hasil], Catatan]:
        s = SUMBER[id_sumber]
        self.pakai[id_sumber] += 1
        t0 = time.perf_counter()
        assert self.klien is not None
        try:
            out = s.ambil(self.klien, kueri, self.k, self.hari)
        except Offline as e:
            return [], Catatan(id_sumber, s.jenis, kueri, False, 0, _ms(t0), f"offline: {e}")
        except GagalHTTP as e:
            return [], Catatan(id_sumber, s.jenis, kueri, False, 0, _ms(t0), f"HTTP {e.status}")
        except Exception as e:  # format berubah / JSON rusak: jangan mematikan seluruh riset
            return [], Catatan(id_sumber, s.jenis, kueri, False, 0, _ms(t0), f"{type(e).__name__}: {e}")
        dur = _ms(t0)
        diambil = dt.datetime.now(UTC)
        for h in out:
            h.diambil = h.diambil or diambil.isoformat()
            h.status = G.LIVE if self.mode == "online" else h.status
        st = G.status_sumber(
            s.jenis,
            diambil,
            None,
            s.ttl if self.ttl.get(s.jenis) is None else self.ttl[s.jenis],
            id_sumber,
            dari_jaringan=True,
            fixture=self.mode == "uji",
        )
        self.status.append(st)
        return out, Catatan(id_sumber, s.jenis, kueri, True, len(out), dur, "", dari_cache=False)

    def cari_jenis(self, jenis: str, kueri: str, berhenti_pertama: bool = True) -> tuple[list[Hasil], list[Catatan]]:
        """jalankan rantai cadangan satu jenis sampai ada hasil (bila `berhenti_pertama`)."""
        hasil: list[Hasil] = []
        catatan: list[Catatan] = []
        for id_sumber in RANTAI.get(jenis, ()):
            if id_sumber not in SUMBER:
                continue
            alasan = self._boleh(id_sumber)
            if alasan:
                catatan.append(Catatan(id_sumber, jenis, kueri, False, 0, 0, alasan))
                self.catatan.append(catatan[-1])
                continue
            out, c = self._satu(id_sumber, kueri)
            catatan.append(c)
            self.catatan.append(c)
            hasil += out
            if out and berhenti_pertama:
                break
        return hasil, catatan

    def cari(
        self,
        kueri: str,
        jenis: Sequence[str] | str | None = None,
        sumber: Sequence[str] | None = None,
        berhenti_pertama: bool = True,
    ) -> LaporanCari:
        """cari `kueri` ke banyak sumber sekaligus. `sumber` = paksa id sumber tertentu (lewat rantai)."""
        pilih = [jenis] if isinstance(jenis, str) else list(jenis) if jenis else list(SEMUA_JENIS)
        if sumber:
            hasil: list[Hasil] = []
            catatan: list[Catatan] = []
            for sid in sumber:
                if sid not in SUMBER:
                    continue
                alasan = self._boleh(sid)
                if alasan:
                    catatan.append(Catatan(sid, SUMBER[sid].jenis, kueri, False, 0, 0, alasan))
                    continue
                out, c = self._satu(sid, kueri)
                hasil += out
                catatan.append(c)
            return self._laporan(kueri, hasil, catatan)
        semua_h: list[Hasil] = []
        semua_c: list[Catatan] = []
        for j in pilih:
            temuan, jejak = self.cari_jenis(j, kueri, berhenti_pertama)
            semua_h += temuan
            semua_c += jejak
        return self._laporan(kueri, semua_h, semua_c)

    def _laporan(self, kueri: str, hasil: list[Hasil], catatan: list[Catatan]) -> LaporanCari:
        return LaporanCari(kueri, dedup(hasil), list(self.status), catatan)

    # ------------------------------------------------------------------------------------ laporan
    def ringkas(self) -> str:
        ok = sum(1 for c in self.catatan if c.ok)
        return f"{ok}/{len(self.catatan)} sumber menjawab, kuota terpakai {dict(self.pakai)}"


def _angka(v: Any) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


def dedup(hasil: Iterable[Hasil]) -> list[Hasil]:
    """buang temuan ganda (URL sama, atau judul sama persis); simpan yang metriknya paling tinggi."""
    out: dict[tuple[str, str], Hasil] = {}
    for h in hasil:
        if not h.judul.strip():
            continue
        k = h.kunci()
        if k not in out or (h.metrik or 0) > (out[k].metrik or 0):
            out[k] = h
    return sorted(out.values(), key=lambda h: -(h.metrik or 0))


def kueri_ilmiah(tema: str) -> str:
    """kata kunci bahasa Inggris untuk pencarian jurnal (registri tema -> field `en`)."""
    t = TEMA.get(tema)
    return (t.en if t else tema) or tema


class PencariAgen:
    """pencarian TANPA HTTP: hasil disuntik dari berkas data agen (mode agen di sandbox terblokir).

    Bentuknya sama dengan `Pencari` supaya `analisis.py` tidak perlu tahu bedanya, tetapi status sumbernya
    FIXTURE/CACHE (bukan LIVE) agar laporan tidak mengklaim data diambil langsung saat ini.
    """

    def __init__(
        self, data: Mapping[str, Any], kanal: kanal_mod.Kanal | None = None, hari: dt.date | None = None
    ) -> None:
        self.d = dict(data)
        self.k = kanal or kanal_mod.muat()
        self.hari = hari or G.sekarang().date()
        self.mode = "agen"
        self.sb = AG.SumberAgen(self.d, self.hari)  # konversi wiki/berita bulan-an -> metrik mesin
        self.pakai: Counter[str] = Counter()
        self.status: list[G.Status] = []
        self.catatan: list[Catatan] = []
        self.klien = None

    def _stempel(self, jenis: str, sumber: str) -> G.Status:
        st = G.status_sumber(jenis, self.d.get("diambil"), None, None, sumber)
        self.status.append(st)
        return st

    def cari(
        self, kueri: str, jenis: Sequence[str] | str | None = None, sumber: Sequence[str] | None = None
    ) -> LaporanCari:
        pilih = {jenis} if isinstance(jenis, str) else set(jenis) if jenis else set(SEMUA_JENIS)
        hasil: list[Hasil] = []
        catatan: list[Catatan] = []
        diambil = self.d.get("diambil")
        if SARAN in pilih:
            for sm in ("google", "youtube"):
                daftar = self.d.get("saran", {}).get(sm, {}).get(kueri)
                if daftar is None:
                    continue
                st = self._stempel(SARAN, f"saran_{sm}")
                hasil += [
                    Hasil(
                        f"saran_{sm}",
                        SARAN,
                        kueri,
                        s,
                        metrik=float(10 - i),
                        satuan="posisi",
                        status=st.status,
                        diambil=diambil,
                    )
                    for i, s in enumerate(daftar)
                ]
                catatan.append(Catatan(f"saran_{sm}", SARAN, kueri, True, len(daftar)))
        if WIKI in pilih:
            tema_w = _tema_dari_kueri(kueri)
            w = self.sb.wiki(tema_w) if tema_w else None
            if w:
                jw = str(w.get("judul") or tema_w)
                st = self._stempel(WIKI, "wiki_agen")
                hasil.append(
                    Hasil(
                        "wiki_agen",
                        WIKI,
                        kueri,
                        jw,
                        url=f"https://id.wikipedia.org/wiki/{jw.replace(' ', '_')}",
                        cuplik=f"tren {w.get('tren')}x, lonjakan z {w.get('lonjakan_z')}",
                        metrik=float(w.get("views60") or 0),
                        satuan="views/60h",
                        status=st.status,
                        diambil=diambil,
                        mentah={kk: v for kk, v in w.items() if kk != "judul"},
                    )
                )
                catatan.append(Catatan("wiki_agen", WIKI, kueri, True, 1))
        if BERITA in pilih:
            tema_b = _tema_dari_kueri(kueri)
            b = self.sb.berita(tema_b) if tema_b else None
            if b:
                st = self._stempel(BERITA, "berita_agen")
                for judul_b in b.get("judul", []):
                    hasil.append(Hasil("berita_agen", BERITA, kueri, str(judul_b), status=st.status, diambil=diambil))
                hasil.append(
                    Hasil(
                        "berita_agen",
                        BERITA,
                        kueri,
                        f"{int(b.get('n7', 0))} berita 7 hari (rasio {b.get('rasio')}x)",
                        metrik=float(b.get("n7", 0)),
                        satuan="berita/7h",
                        status=st.status,
                        diambil=diambil,
                        mentah={kk: b.get(kk) for kk in ("n7", "n28", "rasio")},
                    )
                )
                catatan.append(Catatan("berita_agen", BERITA, kueri, True, len(b.get("judul", [])) + 1))
        if ILMIAH in pilih:
            tema = _tema_dari_kueri(kueri)
            daftar = self.d.get("sumber_ilmiah", {}).get(tema, []) if tema else []
            if daftar:
                st = self._stempel(ILMIAH, "ilmiah_agen")
                hasil += [
                    Hasil(
                        "ilmiah_agen",
                        ILMIAH,
                        kueri,
                        str(s.get("judul") or ""),
                        url=s.get("url"),
                        cuplik=" - ".join(str(s.get(x)) for x in ("penerbit", "tahun") if s.get(x)),
                        status=st.status,
                        diambil=diambil,
                        mentah=dict(s),
                    )
                    for s in daftar
                ]
                catatan.append(Catatan("ilmiah_agen", ILMIAH, kueri, True, len(daftar)))
        if TREN in pilih and self.d.get("tren_harian"):
            st = self._stempel(TREN, "tren_agen")
            hasil += [
                Hasil(
                    "tren_agen",
                    TREN,
                    kueri,
                    str(t.get("judul") or ""),
                    metrik=float(t.get("traffic") or 0),
                    satuan="pencarian/hari",
                    status=st.status,
                    diambil=diambil,
                )
                for t in self.d["tren_harian"]
            ]
            catatan.append(Catatan("tren_agen", TREN, kueri, True, len(self.d["tren_harian"])))
        if MOMEN in pilih and self.d.get("momen_live"):
            st = self._stempel(MOMEN, "momen_agen")
            hasil += [
                Hasil(
                    "momen_agen",
                    MOMEN,
                    kueri,
                    str(m.get("nama") or ""),
                    cuplik=", ".join(m.get("tema", [])),
                    metrik=float(m.get("urgensi") or 0),
                    satuan="urgensi",
                    terbit=m.get("tanggal"),
                    status=st.status,
                    diambil=diambil,
                    mentah=dict(m),
                )
                for m in self.d["momen_live"]
            ]
            catatan.append(Catatan("momen_agen", MOMEN, kueri, True, len(self.d["momen_live"])))
        if WEB in pilih:
            tema = _tema_dari_kueri(kueri)
            tanya = self.d.get("tanya", {}).get(tema, []) if tema else []
            if tanya:
                st = self._stempel(WEB, "tanya_agen")
                hasil += [
                    Hasil("tanya_agen", WEB, kueri, str(q), satuan="pertanyaan", status=st.status, diambil=diambil)
                    for q in tanya
                ]
                catatan.append(Catatan("tanya_agen", WEB, kueri, True, len(tanya)))
        self.pakai.update(h.sumber for h in hasil)
        return LaporanCari(kueri, dedup(hasil), list(self.status), catatan)

    def ringkas(self) -> str:
        if not self.pakai:
            return "mode agen: belum ada bagian data terpakai"
        rinci = ", ".join(f"{s}:{n}" for s, n in self.pakai.most_common())
        return f"mode agen: {len(self.pakai)} sumber, {sum(self.pakai.values())} temuan ({rinci})"


def _tema_dari_kueri(kueri: str) -> str | None:
    n = teks.norm(kueri)
    for nama in TEMA:
        if teks.kata_utuh_semua(nama, n) or any(teks.kata_utuh_semua(k, n) for k in TEMA[nama].kata):
            return nama
    return None
