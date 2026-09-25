"""kliktahu/teks.py - utilitas teks: normalisasi, BLOKIR/SENSITIF, ASCII, kemiripan (rapidfuzz), hashtag, tag.

Aturan pencocokan blokir: istilah >= 6 huruf dicocokkan sebagai POTONGAN kata ("berkeringat" -> blokir),
istilah pendek (mis. "iler") hanya kata utuh (agar "diler" tidak ikut terbuang). Frasa berspasi = potongan.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence

from rapidfuzz import fuzz, process

_GANTI = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201a": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u201e": '"',
    "\u2013": "-",
    "\u2014": "-",
    "\u2212": "-",
    "\u2026": "...",
    "\u00b7": "-",
    "\u2022": "-",
    "\u00a0": " ",
    "\u2009": " ",
    "\u200b": "",
    "\u00d7": "x",
    "\u00b0": " derajat",
    "\u2192": "->",
}
KECIL = {"di", "ke", "dan", "yang", "atau", "dari", "pada", "untuk", "itu", "ini", "dengan", "sih", "kah", "vs"}
# singkatan yang selalu KAPITAL ("kenapa ai butuh air" -> "Kenapa AI Butuh Air")
SINGKATAN = {
    "ai": "AI",
    "nasa": "NASA",
    "bmkg": "BMKG",
    "pvmbg": "PVMBG",
    "usgs": "USGS",
    "noaa": "NOAA",
    "esa": "ESA",
    "iss": "ISS",
    "dna": "DNA",
    "brin": "BRIN",
}
# nama diri (tempat, gunung, planet) -> huruf besar di kalimat hook ("kenapa tsunami palu" -> "Kenapa tsunami Palu")
NAMA_DIRI = {
    "palu",
    "donggala",
    "aceh",
    "jakarta",
    "indonesia",
    "jawa",
    "sumatera",
    "sumatra",
    "sulawesi",
    "kalimantan",
    "papua",
    "bali",
    "lombok",
    "flores",
    "semeru",
    "merapi",
    "krakatau",
    "sinabung",
    "lewotobi",
    "sahara",
    "andromeda",
    "chicxulub",
    "apophis",
    "atlantis",
    "borobudur",
    "stonehenge",
    "bermuda",
    "giza",
    "mesir",
    "mars",
    "saturnus",
    "yupiter",
    "jupiter",
    "venus",
    "merkurius",
    "neptunus",
    "uranus",
    "pluto",
}


def ascii_saja(s: str) -> str:
    """ubah ke ASCII: tanda kutip/pisah Unicode diganti padanannya, huruf beraksen dilepas aksennya, emoji dibuang."""
    for a, b in _GANTI.items():
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[ \t]+", " ", s)


def norm(s: str) -> str:
    """huruf kecil ASCII, hanya [0-9a-z spasi -], spasi tunggal. Apostrof DIBUANG (ka'bah -> kabah, jum'at -> jumat)."""
    s = ascii_saja(s).lower().strip().replace("'", "").replace("`", "")
    s = re.sub(r"[^0-9a-z\s\-]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _cocok(teks_norm: str, istilah: str) -> bool:
    ist = norm(istilah)
    if not ist:
        return False
    if " " in ist or len(ist) >= 6:
        return ist in teks_norm
    return re.search(rf"(?<![0-9a-z]){re.escape(ist)}(?![0-9a-z])", teks_norm) is not None


def kena(frasa: str, daftar: Iterable[str]) -> str | None:
    """istilah pertama dari daftar yang cocok dengan frasa (None bila bersih)."""
    f = norm(frasa)
    return next((x for x in daftar if _cocok(f, x)), None)


def diblokir(frasa: str, blokir: Iterable[str]) -> bool:
    return kena(frasa, blokir) is not None


def buang_blokir(items: Iterable[str], blokir: Sequence[str]) -> list[str]:
    """buang frasa terblokir DARI DATA (aturan keras §2.6)."""
    return [x for x in items if isinstance(x, str) and not diblokir(x, blokir)]


def sensitif(frasa: str, daftar: Iterable[str]) -> bool:
    f = norm(frasa)
    return any(re.search(rf"(?<![0-9a-z]){re.escape(norm(x))}(?![0-9a-z])", f) for x in daftar if norm(x))


def kata_utuh_semua(a: str, b: str) -> bool:
    """semua kata a muncul UTUH di b ('ai' tidak cocok dengan 'baterai')."""
    wb = set(norm(b.replace("&", " ")).split())
    wa = norm(a.replace("&", " ")).split()
    return bool(wa) and all(w in wb for w in wa)


def mirip(a: str, b: str) -> float:
    """kemiripan 0..1 (token_set_ratio rapidfuzz: urutan kata & kata tambahan tidak menghukum)."""
    return fuzz.token_set_ratio(norm(a), norm(b)) / 100.0


def paling_mirip(q: str, daftar: Sequence[str]) -> tuple[str | None, float]:
    if not daftar:
        return None, 0.0
    hasil = process.extractOne(norm(q), [norm(x) for x in daftar], scorer=fuzz.token_set_ratio)
    if not hasil:
        return None, 0.0
    return daftar[hasil[2]], hasil[1] / 100.0


def unik_fuzzy(items: Iterable[str], ambang: float = 0.9) -> list[str]:
    """pertahankan urutan, buang item yang terlalu mirip dengan item sebelumnya (dedup semantik ringan)."""
    out: list[str] = []
    for x in items:
        nx = norm(x)
        if not nx:
            continue
        if all(fuzz.ratio(nx, norm(y)) / 100.0 < ambang for y in out):
            out.append(x)
    return out


def slug(s: str) -> str:
    return re.sub(r"[^0-9a-z]+", "_", norm(s)).strip("_") or "x"


def kapital_judul(s: str) -> str:
    """Kapital Tiap Kata gaya judul Indonesia (kata sambung tetap kecil kecuali kata pertama)."""
    w = ascii_saja(s).split()
    out = []
    for i, x in enumerate(w):
        if x.isupper() and len(x) > 1:  # singkatan (NASA, AI) dipertahankan
            out.append(x)
        elif x.lower() in SINGKATAN:
            out.append(SINGKATAN[x.lower()])
        elif i and x.lower() in KECIL:
            out.append(x.lower())
        else:
            out.append(x[:1].upper() + x[1:].lower() if not any(c.isdigit() for c in x) else x)
    return " ".join(out)


def hashtag(s: str) -> str:
    """'hari tanpa bayangan' -> '#HariTanpaBayangan' (ASCII, tanpa spasi)."""
    bag = re.findall(r"[0-9A-Za-z]+", ascii_saja(s))
    return "#" + "".join(b[:1].upper() + b[1:] for b in bag) if bag else ""


def panjang_tag_youtube(tags: Sequence[str]) -> int:
    """hitungan karakter tag CARA YOUTUBE: tag berspasi dihitung + 2 (tanda kutip), ditambah koma pemisah."""
    if not tags:
        return 0
    return sum(len(t) + (2 if " " in t else 0) for t in tags) + (len(tags) - 1)


def kalimat(s: str) -> str:
    """huruf besar di awal kalimat + nama diri & singkatan ('kenapa tsunami palu' -> 'Kenapa tsunami Palu')."""
    w = s.strip().split(" ")
    w = [SINGKATAN.get(x, x[:1].upper() + x[1:] if x in NAMA_DIRI else x) for x in w]
    s = " ".join(w)
    return s[:1].upper() + s[1:] if s else s
