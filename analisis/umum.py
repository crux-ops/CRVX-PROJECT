#!/usr/bin/env python3
"""analisis/umum.py - bagian bersama mesin analisis KlikTahu (v3-v6), kini lapisan tipis di atas paket kliktahu/.

* TEMA, LEKS          -> kliktahu/tema.py (satu registri untuk v3-v7, basis data, metadata)
* BLOKIR/BENIH/HOOK   -> kanal.toml (pengaturan kanal; blokir kentut/ngiler/keringat & bau badan WAJIB)
* ambil_saran()       -> Google/YouTube Autocomplete lewat kliktahu/riset (retry, rate limit, cache) ATAU fixture
                         deterministik (--uji) ATAU data manual/agen (hasil web search agen)
* sudah_dibahas()     -> kliktahu/pustaka.py (PUSTAKA.md + folder pustaka/)
* momen()             -> kliktahu/momen.py (kalender kurasi + astronomi terhitung)
* rumus skor          -> kliktahu/skor.py (dipakai v3-v6 dan mesin riset v7; port TypeScript identik)
TIDAK pernah dijalankan sebagai cron di GitHub Actions.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR = Path(__file__).resolve().parent
DATA = DIR / "data"
FIXTURE = DIR / "fixture"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kliktahu import kanal as _kanal  # noqa: E402
from kliktahu import momen as _momen  # noqa: E402
from kliktahu import pustaka as _pustaka  # noqa: E402
from kliktahu import skor as SKOR  # noqa: E402,F401 - dipakai v3-v6
from kliktahu import teks as _teks  # noqa: E402
from kliktahu import tema as _tema  # noqa: E402

_K = _kanal.muat()
BLOKIR = list(_K.aturan.blokir)
BENIH = list(_K.riset.benih)
PILAR = list(_kanal.PILAR_SAH)
HINDARI_HOOK = list(_K.aturan.hindari_hook)
# bentuk lama (tuple) dipertahankan untuk v3-v6: pilar, kata kunci (kata[0] = inti), aspek, evergreen, visual bawaan
TEMA = {n: (t.pilar, list(t.kata), list(t.aspek), t.ever, t.visb) for n, t in _tema.TEMA.items()}
LEKS = _tema.LEKS


def norm(s):
    return _teks.norm(s)


def diblokir(frasa):
    return _teks.diblokir(frasa, BLOKIR)


def bersih(frasa):
    f = norm(frasa)
    if not f or len(f) < 6 or diblokir(f):
        return None
    return f


def punya(frasa, leks):
    f = " " + norm(frasa) + " "
    return any((" " + w + " ") in f for w in LEKS[leks])


# ------------------------------------------------------------------------------------------ sumber saran
class Offline(Exception):
    pass


_KLIEN = None


def _http_saran(q, sumber):
    """Autocomplete asli lewat klien riset kliktahu (HTTP/2, retry+backoff, rate limit per host, cache 12 jam)."""
    global _KLIEN
    from kliktahu.riset import http as _H
    from kliktahu.riset import sumber as _S
    if _KLIEN is None:
        _KLIEN = _H.KlienRiset(_K)
    try:
        return _S.saran(_KLIEN, q, sumber)
    except (_H.Offline, _H.GagalHTTP) as e:
        raise Offline(str(e)) from e


def _fixture_saran(q, sumber):
    """saran deterministik (untuk --uji): dibangun dari aspek tema + templat, termasuk frasa DIBLOKIR
    agar penyaring teruji. Sama setiap kali (seed crc32 kueri)."""
    rr = zlib.crc32(f"{sumber}:{q}".encode())
    kata = q.split(" ", 1)[1] if " " in q else q
    tema = next((k for k, v in TEMA.items() if any(kata.startswith(x) or x.startswith(kata) for x in v[1])), None)
    asp = TEMA[tema][2] if tema else ["itu", "terjadi"]
    tmpl = ["{q} {a}", "{q} {a} menurut sains", "{q} terjadi", "{q} bisa {a}", "{q} saat malam",
            "{q} setiap hari", "{q} warna {a}", "{q} berbahaya atau tidak", "{q} pada anak", "{q} {a} fakta ilmiah"]
    out = []
    for i in range(6 + rr % 4):
        a = asp[(rr >> (i + 1)) % len(asp)]
        out.append(tmpl[(rr + i * 7) % len(tmpl)].format(q=q, a=a))
    if rr % 5 == 0:
        out.insert(2, f"{q} kentut bau")  # harus dibuang BLOKIR
    if rr % 7 == 0:
        out.insert(4, f"{q} keringat dingin")  # harus dibuang BLOKIR
    return list(dict.fromkeys(out))[:10]


def _manual_saran():
    """data manual/agen: analisis/data/manual_saran.json ATAU bagian 'saran' berkas agen terbaru (data/agen/*.json)."""
    p = DATA / "manual_saran.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    agen = sorted((DATA / "agen").glob("*.json"))
    return json.loads(agen[-1].read_text(encoding="utf-8")).get("saran", {}) if agen else {}


def ambil_saran(q, sumber="google", mode="online"):
    """mode: 'uji' (fixture), 'manual' (data web search agen), 'online' (HTTP; Offline bila gagal)."""
    if mode == "uji":
        return _fixture_saran(q, sumber)
    if mode == "manual":
        return _manual_saran().get(sumber, {}).get(q, [])
    return _http_saran(q, sumber)


def cek_online():
    try:
        _http_saran("kenapa langit biru", "google")
        return True
    except Offline:
        return False


# ------------------------------------------------------------------------------------------ pustaka & momen
def sudah_dibahas():
    """{frasa_tema: 'shorts'|'long'} dari PUSTAKA.md (blok SUDAH_DIBAHAS) + folder pustaka/."""
    out = dict(_pustaka.sudah_dibahas())
    for d in (ROOT / "pustaka").glob("*/"):
        if d.is_dir():
            jenis = "long" if d.name.lower().startswith("long") else "shorts"
            out[norm(re.sub(r"^(ep|long)\d+_", "", d.name.lower()).replace("_", " "))] = jenis
    return out


def tema_sudah(tema, daftar=None):
    """-> 'shorts' (sudah jadi Shorts), 'long' (baru jadi video panjang), atau None (segar). Kata utuh."""
    daftar = sudah_dibahas() if daftar is None else daftar
    st = _pustaka.status_tema(_tema.TEMA[tema], daftar)
    return {"dibahas": "shorts", "long": "long"}.get(st)


def momen(hari_ini=None, jendela=45):
    """-> {kunci_tema: (skor 0..1, event)}: kalender kurasi (momen.json) + astronomi terhitung (kliktahu/astro)."""
    hari_ini = hari_ini or dt.date.today()
    out = {}
    for ev in _momen.semua(hari_ini, jendela):
        s = _momen.skor_momen(ev, hari_ini, jendela)
        if s <= 0:
            continue
        e = {"tanggal": ev.tanggal.isoformat(), "nama": ev.nama, "tema": ev.tema, "sumber": ev.sumber}
        for t in {*(_momen.ke_tema(ev)), *(norm(x) for x in ev.tema)}:
            if s > out.get(t, (0, None))[0]:
                out[t] = (round(s, 3), e)
    return out


def momen_tema(tema, peta):
    if norm(tema) in peta:
        return peta[norm(tema)]
    kata = [norm(tema)] + [norm(x) for x in TEMA[tema][1]]
    best = (0.0, None)
    for k, v in peta.items():
        if any(k in x or x in k for x in kata):
            if v[0] > best[0]:
                best = v
    return best


# ------------------------------------------------------------------------------------------ snapshot
def simpan(nama, obj):
    DATA.mkdir(parents=True, exist_ok=True)
    p = DATA / nama
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def snapshot_sebelum(prefix, tanggal, dir_=None):
    """snapshot terakhir dengan tanggal < tanggal (YYYYMMDD)."""
    d = dir_ or DATA
    kandidat = sorted(p for p in d.glob(f"{prefix}_*.json") if p.stem.split("_")[-1] < tanggal)
    return json.loads(kandidat[-1].read_text(encoding="utf-8")) if kandidat else None


def ascii_saja(s):
    return s.encode("ascii", "ignore").decode("ascii")
