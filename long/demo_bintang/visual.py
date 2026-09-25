#!/usr/bin/env python3
"""long/demo_bintang/visual.py - visual DEMO video panjang (2 bab, uji mesin Long).

Pola (tiru untuk long/<slug>/visual.py):
  VIS   = {bab_id: fungsi(img, C)}           C = mesin_long.Ctx (C.w / C.tt / C.u / C.win)
  BEATS = [(bab_id, kata, n, sfx[, off[, gain_db]])]  -> SFX & dorongan kamera DIKUNCI KE KATA
  opsional: latar(size, t, C) -> Image, overlay(img, t, C)
Fakta: Proxima Centauri ~4,2 tahun cahaya (~40 triliun km) - NASA.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "long"))
import diagrams as D  # noqa: E402
import mesin_fx as FX  # noqa: E402
import mesin_long as L  # noqa: E402
import mesin_v11 as V  # noqa: E402

BEATS = [
    ("bab1", "Proxima", 1, "ding"),
    ("bab1", "Jaraknya", 1, "whoosh"),
    ("bab1", "empat", 1, "pop"),
    ("bab1", "triliun", 1, "impact"),
    ("bab2", "cahaya", 1, "swish"),
    ("bab2", "empat", 1, "tick"),
    ("bab2", "menatap", 1, "kilau"),
    ("bab2", "masa", 1, "pukul"),
]


def _bintang(img, x, y, r, warna, t, a=1.0):
    if r <= 1 or a <= 0.01:
        return
    D.glow(img, x, y, r * 3.4, warna, 0.38 * a)
    D.circ(img, x, y, r, warna, a)
    D.circ(img, x - r * 0.3, y - r * 0.3, r * 0.45, D.terang(warna, 0.55), 0.5 * a)
    D.ring(img, x, y, r * (1.3 + 0.1 * math.sin(t * 2.2)), max(2.0, r * 0.05), warna, 0.45 * a)


def bab1(img, C):
    t, ak = C.t, C.aksen
    V.judul_kinetik(img, "BINTANG TERDEKAT", 960, 250, 96, t, 2.0, ak, "TERDEKAT", warna=D.PUTIH, max_w=1400,
                    max_h=120, maks_baris=1, warna_stabilo=D.gelap(ak, 0.2))
    us = D.eob(C.tt(1.3, 0.6))
    _bintang(img, 420, 610, 92 * us, "#FFB020", t, us)
    L.teks(img, "Matahari", 420, 780, 40, "SB", D.PUTIH, us, "ms")
    up = D.eob(C.tt("Proxima", 0.6))
    _bintang(img, 1500, 610, 44 * up, "#FF5A3C", t, up)
    L.callout(img, 1500, 610, 1770, 455, "Proxima Centauri", t, C.T("Proxima") + 0.25, D.col("#FF5A3C"), 32,
              kiri=False)
    uj = D.eo(C.tt("Jaraknya", 0.9))
    if uj > 0:
        x1 = 540 + (1430 - 540) * uj
        n = int((x1 - 540) / 36)
        for i in range(n):
            xa = 540 + i * 36
            D.line(img, xa, 610, min(x1, xa + 20), 610, 5, D.PUTIH, 0.75)
        D.circ(img, x1, 610, 8, ak)
    L.penghitung(img, 4.2, 985, 560, 88, C, ("empat", 1), 1.2, " tahun cahaya", 1, D.PUTIH)
    L.penghitung(img, 40, 985, 720, 64, C, ("empat", 2), 1.0, " triliun km", 0, D.terang(ak, 0.35))
    V.stiker(img, "SANGAT JAUH", 1500, 830, t, C.T("triliun") + 0.25, 36, ak, rot=5)


def bab2(img, C):
    t, ak = C.t, C.aksen
    V.judul_kinetik(img, "CAHAYA DARI MASA LALU", 960, 250, 90, t, 2.0, ak, "MASA LALU", warna=D.PUTIH,
                    max_w=1500, max_h=120, maks_baris=1, warna_stabilo=D.gelap(ak, 0.25))
    _bintang(img, 1560, 620, 42, "#FF5A3C", t)
    L.teks(img, "Proxima", 1560, 740, 34, "SB", D.PUTIH, 1, "ms")
    D.bumi(img, 360, 620, 66, t)
    L.teks(img, "Bumi", 360, 740, 34, "SB", D.PUTIH, 1, "ms")
    u = C.win("cahaya", ("lalu", 1))
    if C.sudah("cahaya"):
        x = 1500 - (1500 - 440) * D.eio(u)
        for k in range(10):
            xx = x + k * 18 * (1 if u < 1 else 0)
            D.circ(img, xx, 620, 11 * (1 - k / 10), D.PUTIH, 0.5 * (1 - k / 10))
        D.glow(img, x, 620, 70, D.terang(ak, 0.4), 0.7)
        D.circ(img, x, 620, 12, D.PUTIH)
        FX.odometer(img, 4.2, 960, 850, 72, D.PUTIH, D.clamp(C.tt("cahaya", 0.3)), "m", "B", u, 1, " tahun")
    if C.sudah("menatap"):
        rr = D.rng("tatap")
        for i in range(12):
            ph = (t * 0.7 + i / 12) % 1.0
            D.kilau4(img, rr.uniform(200, 1720), rr.uniform(360, 960), 16 * (1 - ph) + 4, D.PUTIH,
                     0.8 * (1 - ph) * C.tt("menatap", 0.4), rot=t * 40 + i * 30)
    L.stempel(img, "MASA LALU", 960, 470, t, C.T("masa"), "#FF5FA2", 60, -6)


VIS = {"bab1": bab1, "bab2": bab2}
