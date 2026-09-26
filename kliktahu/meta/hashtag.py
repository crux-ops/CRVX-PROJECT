"""kliktahu/meta/hashtag.py - HASHTAG (tahap 9 rencana upgrade 2026-09).

Aturan yang ditegakkan (sumber resmi YouTube Help "Hashtag", diperiksa 26 September 2026):
* hashtag = '#' + huruf/angka, TANPA spasi dan tanpa tanda baca; tidak boleh hanya angka
* maksimal 15 hashtag per video - YouTube MENGABAIKAN SEMUA hashtag bila lebih dari itu (bukan cuma kelebihannya)
* hashtag tidak boleh menyesatkan; yang tidak relevan dengan isi video bisa dikenai sanksi
* hashtag pendek & sedikit (3-5) lebih rapi di Shorts; wajib kanal (#KlikTahu, #FaktaSains) selalu ada

Yang DILARANG modul ini: menumpuk hashtag yang sedang tren tetapi tidak ada hubungannya dengan topik
(trend-stuffing). Tiap hashtag harus bisa dipertanggungjawabkan: kata inti, nama tema, atau pilar.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from .. import kanal as kanal_mod
from .. import teks

POLA = re.compile(r"^#[A-Za-z0-9]{2,40}$")
MAKS_YOUTUBE = 15  # lebih dari ini = SEMUA hashtag diabaikan YouTube


def hashtag(s: str) -> str:
    return teks.hashtag(s)


def relevan(h: str, kata: Sequence[str]) -> bool:
    """hashtag menyebut kata inti/topik/pilar? (huruf kecil, tanpa '#')."""
    n = re.sub(r"^#", "", h).lower()
    n_underscore = n
    for k in kata:
        kk = teks.norm(k)
        if not kk:
            continue
        if kk.replace(" ", "") and kk.replace(" ", "") in n_underscore.replace("_", ""):
            return True
        for w in kk.split():
            if len(w) >= 4 and w in n:
                return True
    return False


def buat_hashtag(
    tema: str,
    inti: str,
    format_: str,
    k: kanal_mod.Kanal,
    tambahan: Sequence[str] = (),
    blokir: Sequence[str] = (),
    sensitif: Sequence[str] = (),
) -> tuple[list[str], list[str]]:
    """-> (daftar hashtag, peringatan). Singkat, relevan, tanpa tren yang tidak berkaitan."""
    peringatan: list[str] = []
    out = list(k.metadata.hashtag_wajib)
    kata_konteks = [inti, tema, *tambahan]

    def tambah(nama: str) -> None:
        h = hashtag(nama)
        if not h or not POLA.match(h) or len(h) > 30:
            return
        if h.lower() in (x.lower() for x in out):
            return
        if teks.diblokir(h, blokir) or teks.sensitif(h, sensitif):
            peringatan.append(f"hashtag '{h}' dibuang (terlarang oleh aturan kanal)")
            return
        if len(out) >= k.metadata.maks_hashtag:
            return
        out.append(h)

    tambah(inti)
    if "&" not in tema:
        tambah(tema)
    for t in tambahan:
        tambah(t)  # hanya yang relevan: panggillah dengan kata kunci topik, bukan tren umum
    if format_ == "shorts":
        out.append(k.metadata.hashtag_shorts)
    out = out[: k.metadata.maks_hashtag]
    if len(out) > MAKS_YOUTUBE:
        peringatan.append(f"lebih dari {MAKS_YOUTUBE} hashtag - YouTube mengabaikan SEMUA hashtag video ini")
        out = out[:MAKS_YOUTUBE]
    for h in out:
        if h.lower() in (x.lower() for x in k.metadata.hashtag_wajib) or h == k.metadata.hashtag_shorts:
            continue
        if not relevan(h, kata_konteks):
            peringatan.append(f"hashtag '{h}' tidak ada hubungannya dengan '{inti}' - jangan dipakai (trend-stuffing)")
    return out, peringatan


def lint(h: Sequence[str], format_: str, k: kanal_mod.Kanal, w: list[str], konteks: Sequence[str] = ()) -> list[str]:
    g: list[str] = []
    if not 1 <= len(h) <= k.metadata.maks_hashtag:
        g.append(f"hashtag harus 1..{k.metadata.maks_hashtag} (ada {len(h)})")
    if len(h) > MAKS_YOUTUBE:
        g.append(f"hashtag lebih dari {MAKS_YOUTUBE} - YouTube mengabaikan SEMUA hashtag video ini")
    for x in h:
        if not POLA.match(x):
            g.append(f"hashtag tidak sah: '{x}' (harus '#' + huruf/angka ASCII tanpa spasi)")
        elif re.sub(r"^#", "", x).isdigit():
            g.append(f"hashtag hanya angka: '{x}' (ditolak YouTube)")
        if teks.diblokir(x, k.aturan.blokir) or teks.sensitif(x, k.aturan.sensitif):
            g.append(f"hashtag terlarang: '{x}'")
    rendah = [x.lower() for x in h]
    for x in k.metadata.hashtag_wajib:
        if x.lower() not in rendah:
            g.append(f"hashtag wajib hilang: {x}")
    if format_ == "shorts" and k.metadata.hashtag_shorts.lower() not in rendah:
        w.append(f"Shorts tanpa {k.metadata.hashtag_shorts}")
    if len(set(rendah)) != len(rendah):
        g.append("ada hashtag ganda (huruf besar/kecil dibedakan)")
    if konteks:
        for x in h:
            if x.lower() in (y.lower() for y in (*k.metadata.hashtag_wajib, k.metadata.hashtag_shorts)):
                continue
            if not relevan(x, konteks):
                w.append(f"hashtag '{x}' tidak relevan dengan topik (risiko dianggap menyesatkan)")
    return g
