"""kliktahu/meta/tag.py - TAG (tahap 10 rencana upgrade 2026-09).

Tag bukan "kunci ranking": YouTube menyebut tag sebagai metadata deskriptif (bukan faktor utama penempatan),
dan modul ini TIDAK menjanjikan apa pun tentang peringkat. Yang dilakukan:

* urutan: kata kunci utama & variasi pencarian NYATA (frasa autocomplete hasil riset) di depan
* deduplikasi dengan `fuzz.ratio` (>= 92 = hampir identik); `token_set_ratio` TIDAK dipakai karena menganggap
  subset = identik (pelajaran 25-09: "kenapa gunung meletus" dianggap sama dengan "... ada petir")
* relevansi: tag harus menyebut kata inti/topik, atau berasal dari frasa pencarian asli topik itu
* batas platform: total <= 500 karakter dihitung CARA YOUTUBE (koma + tanda kutip untuk tag berspasi)
* aturan keras: ASCII, tanpa koma/tanda kutip di dalam tag, tanpa topik diblokir, tanpa kata sensitif

Tag diisi dari data, bukan dikarang: tanpa frasa riset, hanya kata inti + frasa wajib kanal yang dipakai.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from rapidfuzz import fuzz

from .. import kanal as kanal_mod
from .. import teks

MAKS_KARAKTER_PER_TAG = 60
AMBANG_SAMA = 92
POLA = re.compile(r"^[\x20-\x21\x23-\x2B\x2D-\x7E]+$")  # ASCII tanpa koma (,) dan tanpa kutip (")


def panjang(tag: Sequence[str]) -> int:
    return teks.panjang_tag_youtube(tag)


def urut_relevan(calon: Sequence[str], kata_kunci: str, inti: str) -> list[str]:
    """urutkan calon tag: yang mengandung kata kunci/inti lebih dulu, lalu yang lebih pendek."""
    kk, it = teks.norm(kata_kunci), teks.norm(inti)

    def kunci(t: str) -> tuple[int, int, str]:
        n = teks.norm(t)
        skor = 0 if kk and (n.startswith(kk) or kk in n) else (1 if it and it in n else 2)
        return (skor, len(n), n)

    return sorted(calon, key=kunci)


def buat_tag(
    kata_kunci: str,
    inti: str,
    tema: str,
    frasa: Sequence[str],
    k: kanal_mod.Kanal,
    tambahan: Sequence[str] = (),
    hashtag: Sequence[str] = (),
) -> tuple[list[str], list[str]]:
    """-> (tag, peringatan). Diisi dari kata kunci + variasi pencarian nyata; berhenti di batas 500 karakter."""
    peringatan: list[str] = []
    htg = [re.sub(r"^#", "", x).replace("_", " ") for x in hashtag if len(x) > 3]
    calon = [
        kata_kunci,
        inti,
        tema.replace("&", "dan"),
        *tambahan,
        *frasa,
        *htg,
        f"fakta {inti}",
        f"{inti} menurut sains",
        "fakta sains",
        "sains indonesia",
        k.nama.lower(),
    ]
    calon = urut_relevan([c for c in calon if c and str(c).strip()], kata_kunci, inti)
    out: list[str] = []
    for c in calon:
        c = teks.norm(str(c))
        if (
            not c
            or len(c) > MAKS_KARAKTER_PER_TAG
            or teks.diblokir(c, k.aturan.blokir)
            or teks.sensitif(c, k.aturan.sensitif)
        ):
            continue
        if any(fuzz.ratio(c, x) >= AMBANG_SAMA for x in out):
            continue
        if panjang([*out, c]) <= k.metadata.maks_tag_karakter:
            out.append(c)
        else:
            peringatan.append(
                f"batas {k.metadata.maks_tag_karakter} karakter tercapai: {len(calon) - len(out)} calon tag "
                "tertinggal (YouTube menghitung koma + tanda kutip untuk tag berspasi)"
            )
            break
    if not any(teks.norm(inti) in teks.norm(t) for t in out):
        peringatan.append(f"tidak ada tag yang memuat kata inti '{inti}' - kata kunci utama sebaiknya ada di tag")
    return out, peringatan


def lint(tag: Sequence[str], k: kanal_mod.Kanal) -> list[str]:
    g: list[str] = []
    if not tag:
        g.append("tag kosong")
    n = panjang(tag)
    if n > k.metadata.maks_tag_karakter:
        g.append(f"tag {n} karakter (hitungan YouTube) > {k.metadata.maks_tag_karakter}")
    for t in tag:
        if not t.isascii() or re.search(r"[<>,]", t):
            g.append(f"tag tidak sah: '{t}' (tanpa koma, tanpa tanda < >)")
        if len(t) > MAKS_KARAKTER_PER_TAG:
            g.append(f"tag > {MAKS_KARAKTER_PER_TAG} karakter: '{t}'")
        if teks.diblokir(t, k.aturan.blokir) or teks.sensitif(t, k.aturan.sensitif):
            g.append(f"tag terlarang: '{t}'")
    if len(set(teks.norm(t) for t in tag)) != len(tag):
        g.append("ada tag ganda setelah normalisasi")
    return g


def jelaskan(tag: Sequence[str], k: kanal_mod.Kanal) -> list[str]:
    """baris laporan yang jujur: tag bukan penentu ranking."""
    return [
        f"{len(tag)} tag, {panjang(tag)}/{k.metadata.maks_tag_karakter} karakter (hitungan YouTube).",
        "Tag adalah metadata deskriptif: modul ini TIDAK menjanjikan kenaikan ranking atau tayangan.",
        "Urutan: kata kunci utama, lalu variasi frasa pencarian nyata (autocomplete Google/YouTube).",
    ]
