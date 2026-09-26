"""kliktahu/meta/ - PAKET METADATA: judul, deskripsi, hashtag, tag (tahap 7-10 rencana upgrade 2026-09).

Empat modul terpisah supaya tiap bagian bisa diuji sendiri:

    meta/judul.py      3 judul beragam sudut, dinilai, diuji duplikasi & bahasa, tanpa klaim tanpa bukti
    meta/deskripsi.py  ringkasan setia bukti + bab dari timeline + sumber ber-provenance + tanggal riset
    meta/hashtag.py    relevan, singkat, sesuai aturan platform (maks 15 atau SEMUA diabaikan)
    meta/tag.py        kata kunci + variasi pencarian nyata, dedup, batas 500 karakter cara YouTube

`kliktahu/metadata.py` tetap menjadi perakit (Paket + lint + berkas MD) dan memakai modul-modul ini,
jadi hanya ada SATU implementasi untuk tiap aturan.
"""

from __future__ import annotations

from . import deskripsi, hashtag, judul, tag

__all__ = ["deskripsi", "hashtag", "judul", "tag"]
