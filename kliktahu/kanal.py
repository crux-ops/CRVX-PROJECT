"""kliktahu/kanal.py - PENGATURAN KANAL (kanal.toml): muat + validasi ketat.

Aturan keras pemilik ikut ditegakkan di sini (tidak bisa dimatikan lewat file):
* blokir wajib memuat kentut, ngiler, keringat, bau badan
* subtitle = false, musik = false
* file hanya boleh berisi NAMA variabel lingkungan untuk kunci API (bukan kuncinya)
"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from . import ROOT

PILAR_SAH = ("tubuh", "antariksa", "bumi", "hewan", "teknologi", "misteri")
BLOKIR_WAJIB = ("kentut", "ngiler", "keringat", "bau badan")
_ENV = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_JAM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
_TAGAR = re.compile(r"^#[A-Za-z0-9]{2,40}$")


class KanalError(ValueError):
    """kanal.toml tidak sah (pesan dalam bahasa Indonesia, menunjuk kunci yang salah)."""


@dataclass(frozen=True)
class Merek:
    cream: tuple[int, int, int]
    ink: tuple[int, int, int]
    muted: tuple[int, int, int]
    aksen: tuple[str, ...]
    font: str
    font_berat: tuple[str, ...]
    shorts: dict[str, int]
    long: dict[str, int]


@dataclass(frozen=True)
class Aturan:
    blokir: tuple[str, ...]
    sensitif: tuple[str, ...]
    hindari_hook: tuple[str, ...]
    pilar_kesehatan: tuple[str, ...]
    disclaimer_kesehatan: str
    subtitle: bool
    musik: bool


@dataclass(frozen=True)
class Jadwal:
    slot_wib: tuple[str, ...]
    shorts_per_minggu: int
    long_per_bulan: int
    momen_hari_sebelum: int
    jendela_momen_hari: int
    siap_shorts_hari: int = 2
    siap_long_hari: int = 7


@dataclass(frozen=True)
class MetaAturan:
    hashtag_wajib: tuple[str, ...]
    hashtag_shorts: str
    maks_hashtag: int
    maks_judul: int
    ideal_judul_shorts: int
    ideal_judul_long: int
    maks_deskripsi: int
    maks_tag_karakter: int
    cta: str
    komentar_sematan: str


@dataclass(frozen=True)
class Riset:
    benih: tuple[str, ...]
    hl: str
    gl: str
    maks_paralel: int
    maks_paralel_per_host: int
    jeda_min_detik: float
    cache_jam: float
    maks_youtube_tema: int
    user_agent: str
    env_youtube_key: str
    env_brave_key: str
    env_searxng_url: str
    env_openalex_mailto: str
    derau: tuple[str, ...] = ()
    pesaing: bool = True  # False = analisis pesaing YouTube tidak dipakai (keputusan pemilik) -> komponen celah keluar

    def rahasia(self, nama_env: str) -> str | None:
        """nilai variabel lingkungan (kunci API) - TIDAK pernah dicetak/disimpan."""
        v = os.environ.get(nama_env, "").strip()
        return v or None


@dataclass(frozen=True)
class Kanal:
    nama: str
    bahasa: str
    wilayah: str
    zona_waktu: str
    niche: str
    slogan: str
    shorts_terakhir: int
    long_terakhir: int
    pilar: dict[str, float]
    merek: Merek
    aturan: Aturan
    jadwal: Jadwal
    metadata: MetaAturan
    riset: Riset
    sumber_kredibel: tuple[str, ...]
    path: Path = field(default=ROOT / "kanal.toml")


def _ambil(d: dict[str, Any], bagian: str, kunci: str, tipe: type | tuple[type, ...]) -> Any:
    if kunci not in d:
        raise KanalError(f"[{bagian}] kunci '{kunci}' wajib ada")
    v = d[kunci]
    if tipe is float and isinstance(v, int) and not isinstance(v, bool):
        v = float(v)
    if not isinstance(v, tipe) or (tipe is int and isinstance(v, bool)):
        raise KanalError(
            f"[{bagian}] '{kunci}' harus bertipe {getattr(tipe, '__name__', tipe)}, bukan {type(v).__name__}"
        )
    return v


def _daftar_str(d: dict[str, Any], bagian: str, kunci: str, min_n: int = 1) -> tuple[str, ...]:
    v = _ambil(d, bagian, kunci, list)
    if len(v) < min_n or not all(isinstance(x, str) and x.strip() for x in v):
        raise KanalError(f"[{bagian}] '{kunci}' harus daftar teks (minimal {min_n})")
    return tuple(x.strip() for x in v)


def _rgb(d: dict[str, Any], kunci: str) -> tuple[int, int, int]:
    v = _ambil(d, "merek", kunci, list)
    if len(v) != 3 or not all(isinstance(x, int) and 0 <= x <= 255 for x in v):
        raise KanalError(f"[merek] '{kunci}' harus [R, G, B] 0..255")
    return (v[0], v[1], v[2])


def _bagian(data: dict[str, Any], nama: str) -> dict[str, Any]:
    b = data.get(nama)
    if not isinstance(b, dict):
        raise KanalError(f"bagian [{nama}] wajib ada")
    return b


def dari_dict(data: dict[str, Any], path: Path | None = None) -> Kanal:
    k = _bagian(data, "kanal")
    p = _bagian(data, "pilar")
    m = _bagian(data, "merek")
    a = _bagian(data, "aturan")
    j = _bagian(data, "jadwal")
    md = _bagian(data, "metadata")
    r = _bagian(data, "riset")
    sk = _bagian(data, "sumber_kredibel")

    pilar: dict[str, float] = {}
    for nama, bobot in p.items():
        if nama not in PILAR_SAH:
            raise KanalError(f"[pilar] '{nama}' bukan pilar sah {PILAR_SAH}")
        if not isinstance(bobot, (int, float)) or isinstance(bobot, bool) or not 0 <= float(bobot) <= 1:
            raise KanalError(f"[pilar] bobot '{nama}' harus 0..1")
        pilar[nama] = float(bobot)
    if set(pilar) != set(PILAR_SAH):
        raise KanalError(f"[pilar] harus memuat keenam pilar: {', '.join(PILAR_SAH)}")

    aksen = _daftar_str(m, "merek", "aksen")
    for h in aksen:
        if not _HEX.match(h):
            raise KanalError(f"[merek] warna aksen '{h}' harus format #RRGGBB")
    merek = Merek(
        cream=_rgb(m, "cream"),
        ink=_rgb(m, "ink"),
        muted=_rgb(m, "muted"),
        aksen=aksen,
        font=_ambil(m, "merek", "font", str),
        font_berat=_daftar_str(m, "merek", "font_berat"),
        shorts=dict(_ambil(m, "merek", "shorts", dict)),
        long=dict(_ambil(m, "merek", "long", dict)),
    )

    blokir = tuple(x.lower() for x in _daftar_str(a, "aturan", "blokir"))
    for w in BLOKIR_WAJIB:
        if w not in blokir:
            raise KanalError(f"[aturan] blokir WAJIB memuat '{w}' (aturan keras pemilik §2.6)")
    if _ambil(a, "aturan", "subtitle", bool) or _ambil(a, "aturan", "musik", bool):
        raise KanalError("[aturan] subtitle dan musik harus false (aturan keras pemilik §2.1-2.2)")
    pk = _daftar_str(a, "aturan", "pilar_kesehatan")
    for x in pk:
        if x not in PILAR_SAH:
            raise KanalError(f"[aturan] pilar_kesehatan '{x}' bukan pilar sah")
    aturan = Aturan(
        blokir=blokir,
        sensitif=tuple(x.lower() for x in _daftar_str(a, "aturan", "sensitif")),
        hindari_hook=tuple(x.lower() for x in _daftar_str(a, "aturan", "hindari_hook")),
        pilar_kesehatan=pk,
        disclaimer_kesehatan=_ambil(a, "aturan", "disclaimer_kesehatan", str),
        subtitle=False,
        musik=False,
    )

    slot = _daftar_str(j, "jadwal", "slot_wib")
    for s in slot:
        if not _JAM.match(s):
            raise KanalError(f"[jadwal] slot '{s}' harus format HH:MM")
    jadwal = Jadwal(
        slot_wib=slot,
        shorts_per_minggu=_ambil(j, "jadwal", "shorts_per_minggu", int),
        long_per_bulan=_ambil(j, "jadwal", "long_per_bulan", int),
        momen_hari_sebelum=_ambil(j, "jadwal", "momen_hari_sebelum", int),
        jendela_momen_hari=_ambil(j, "jadwal", "jendela_momen_hari", int),
        siap_shorts_hari=int(j.get("siap_shorts_hari", 2)),
        siap_long_hari=int(j.get("siap_long_hari", 7)),
    )
    if not 1 <= jadwal.shorts_per_minggu <= 14:
        raise KanalError("[jadwal] shorts_per_minggu harus 1..14")
    if not 0 <= jadwal.long_per_bulan <= 8:
        raise KanalError("[jadwal] long_per_bulan harus 0..8")

    tagar = _daftar_str(md, "metadata", "hashtag_wajib")
    for t in (*tagar, _ambil(md, "metadata", "hashtag_shorts", str)):
        if not _TAGAR.match(t):
            raise KanalError(f"[metadata] hashtag '{t}' harus '#' + huruf/angka ASCII tanpa spasi")
    meta = MetaAturan(
        hashtag_wajib=tagar,
        hashtag_shorts=md["hashtag_shorts"],
        maks_hashtag=_ambil(md, "metadata", "maks_hashtag", int),
        maks_judul=_ambil(md, "metadata", "maks_judul", int),
        ideal_judul_shorts=_ambil(md, "metadata", "ideal_judul_shorts", int),
        ideal_judul_long=_ambil(md, "metadata", "ideal_judul_long", int),
        maks_deskripsi=_ambil(md, "metadata", "maks_deskripsi", int),
        maks_tag_karakter=_ambil(md, "metadata", "maks_tag_karakter", int),
        cta=_ambil(md, "metadata", "cta", str),
        komentar_sematan=_ambil(md, "metadata", "komentar_sematan", str),
    )
    if meta.maks_tag_karakter > 500 or meta.maks_judul > 100 or meta.maks_deskripsi > 5000:
        raise KanalError("[metadata] batas melebihi batas keras YouTube (tag 500, judul 100, deskripsi 5000)")
    if not 3 <= meta.maks_hashtag <= 15:
        raise KanalError("[metadata] maks_hashtag harus 3..15 (YouTube mengabaikan SEMUA bila > 60)")
    for teks in (meta.cta, meta.komentar_sematan, aturan.disclaimer_kesehatan):
        if not teks.isascii():
            raise KanalError(f"[metadata/aturan] teks harus ASCII (aturan METADATA): {teks!r}")

    env = {}
    for kunci in ("env_youtube_key", "env_brave_key", "env_searxng_url", "env_openalex_mailto"):
        v = _ambil(r, "riset", kunci, str)
        if not _ENV.match(v):
            raise KanalError(
                f"[riset] '{kunci}' harus NAMA variabel lingkungan (HURUF_BESAR), bukan kunci/URL. "
                "Jangan pernah menaruh kunci API di file."
            )
        env[kunci] = v
    riset = Riset(
        benih=_daftar_str(r, "riset", "benih"),
        hl=_ambil(r, "riset", "hl", str),
        gl=_ambil(r, "riset", "gl", str),
        maks_paralel=_ambil(r, "riset", "maks_paralel", int),
        maks_paralel_per_host=_ambil(r, "riset", "maks_paralel_per_host", int),
        jeda_min_detik=_ambil(r, "riset", "jeda_min_detik", float),
        cache_jam=_ambil(r, "riset", "cache_jam", float),
        maks_youtube_tema=_ambil(r, "riset", "maks_youtube_tema", int),
        user_agent=_ambil(r, "riset", "user_agent", str),
        derau=tuple(x.lower() for x in r.get("derau", []) if isinstance(x, str)),
        pesaing=_pesaing(r),
        **env,
    )
    if not 1 <= riset.maks_paralel <= 32 or not 1 <= riset.maks_paralel_per_host <= 8:
        raise KanalError("[riset] maks_paralel 1..32 dan maks_paralel_per_host 1..8 (sopan ke server)")
    if riset.jeda_min_detik < 0.1:
        raise KanalError("[riset] jeda_min_detik minimal 0.1 detik (jangan membanjiri server)")

    return Kanal(
        nama=_ambil(k, "kanal", "nama", str),
        bahasa=_ambil(k, "kanal", "bahasa", str),
        wilayah=_ambil(k, "kanal", "wilayah", str),
        zona_waktu=_ambil(k, "kanal", "zona_waktu", str),
        niche=_ambil(k, "kanal", "niche", str),
        slogan=_ambil(k, "kanal", "slogan", str),
        shorts_terakhir=_ambil(k, "kanal", "shorts_terakhir", int),
        long_terakhir=_ambil(k, "kanal", "long_terakhir", int),
        pilar=pilar,
        merek=merek,
        aturan=aturan,
        jadwal=jadwal,
        metadata=meta,
        riset=riset,
        sumber_kredibel=tuple(x.lower() for x in _daftar_str(sk, "sumber_kredibel", "domain")),
        path=path or ROOT / "kanal.toml",
    )


def muat_dari(path: Path | str) -> Kanal:
    p = Path(path)
    try:
        data = tomllib.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise KanalError(f"file pengaturan tidak ada: {p}") from e
    except tomllib.TOMLDecodeError as e:
        raise KanalError(f"kanal.toml rusak (TOML): {e}") from e
    return dari_dict(data, p)


@lru_cache(maxsize=4)
def _muat_cache(path: str, mtime: float) -> Kanal:
    return muat_dari(path)


def muat(path: Path | str | None = None) -> Kanal:
    """Pengaturan kanal (di-cache; otomatis dimuat ulang bila file berubah). Env KLIKTAHU_KANAL = path lain."""
    p = Path(path or os.environ.get("KLIKTAHU_KANAL") or ROOT / "kanal.toml")
    try:
        mt = p.stat().st_mtime
    except FileNotFoundError as e:
        raise KanalError(f"file pengaturan tidak ada: {p}") from e
    return _muat_cache(str(p), mt)


def _pesaing(r: dict) -> bool:
    """r = tabel [riset]."""
    v = r.get("pesaing", True)
    if not isinstance(v, bool):
        raise KanalError("[riset] pesaing harus true/false")
    return v


def ringkas(k: Kanal) -> list[tuple[str, str]]:
    """baris (label, nilai) untuk ditampilkan CLI/dasbor. Kunci API hanya 'ada'/'belum' (tidak pernah nilainya)."""
    ada = lambda n: "ada" if k.riset.rahasia(n) else "belum diisi"
    return [
        ("Kanal", f"{k.nama} ({k.niche}), bahasa {k.bahasa}-{k.wilayah}, zona {k.zona_waktu}"),
        ("Episode berikut", f"Ep{k.shorts_terakhir + 1:02d} (Shorts) / Long{k.long_terakhir + 1:02d}"),
        ("Pilar & bobot", ", ".join(f"{n} {b:.2f}" for n, b in k.pilar.items())),
        ("Diblokir", ", ".join(k.aturan.blokir)),
        ("Sensitif (dilarang di judul/tag)", ", ".join(k.aturan.sensitif)),
        (
            "Jadwal",
            f"{k.jadwal.shorts_per_minggu} Shorts/minggu, {k.jadwal.long_per_bulan} Long/bulan, "
            f"slot {' & '.join(k.jadwal.slot_wib)} WIB",
        ),
        (
            "Metadata",
            f"judul <= {k.metadata.maks_judul}, tag <= {k.metadata.maks_tag_karakter} karakter, "
            f"hashtag <= {k.metadata.maks_hashtag}: {' '.join(k.metadata.hashtag_wajib)}",
        ),
        ("Merek", f"{k.merek.font}, CREAM {k.merek.cream}, INK {k.merek.ink}, aksen {' '.join(k.merek.aksen)}"),
        (
            "Kunci API (env)",
            f"{k.riset.env_youtube_key}: "
            f"{ada(k.riset.env_youtube_key) if k.riset.pesaing else 'tidak dipakai (pesaing = false)'}, "
            f"{k.riset.env_brave_key}: {ada(k.riset.env_brave_key)}, "
            f"{k.riset.env_searxng_url}: {ada(k.riset.env_searxng_url)}",
        ),
    ]
