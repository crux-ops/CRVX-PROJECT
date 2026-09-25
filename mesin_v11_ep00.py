#!/usr/bin/env python3
"""mesin_v11_ep00.py - modul adegan episode DEMO (uji mesin, bukan rilis): hamburan cahaya / langit biru.

Pola modul episode (tiru untuk mesin_v11_epNN.py):
  * tabel beat BERNAMA {nama: (fraksi_durasi, sfx)} -> satu sumber untuk animasi, SFX, kamera
  * fungsi gambar sc_<nama>NN(img, t, dur, sc) membaca waktu beat lewat V.bt(visual, nama, dur)
  * VISUALS_EP & BEAT_TABEL_EP diekspor; mesin_v11 mengimpor modul ini otomatis.
Fakta: cahaya biru (gelombang pendek) dihamburkan molekul udara lebih kuat daripada merah (hamburan
Rayleigh) - NASA Space Place "Why is the sky blue?".
"""
from __future__ import annotations

import math

import diagrams as D
import mesin_v11 as V

VIS = "hamburan00"
B00 = {
    "sinar": (0.10, "whoosh"),    # berkas cahaya matahari menggambar diri
    "molekul": (0.28, "pop"),     # molekul udara muncul
    "hambur": (0.46, "kilau"),    # biru terhambur ke segala arah
    "mata": (0.68, "ding"),       # mata menangkap biru dari segala arah
}
MOL = [(560, 1080, 0), (330, 950, 25), (770, 900, -30), (420, 1270, 60), (810, 1250, 15), (640, 1410, -50),
       (250, 1180, 80), (905, 1070, 40)]
PITA = ["#E8453C", "#FFC928", "#3DBB5C", None]  # None = warna aksen (biru)


def _molekul(img, x, y, r, rot, warna, a):
    if r <= 0.5:
        return
    dx, dy = math.cos(math.radians(rot)) * r * 0.55, math.sin(math.radians(rot)) * r * 0.55
    for s in (-1, 1):
        D.circ(img, x + s * dx, y + s * dy, r * 0.62, warna, a)
    D.circ(img, x - dx - r * 0.2, y - dy - r * 0.22, r * 0.17, D.PUTIH, 0.55 * a)


def sc_hamburan00(img, t, dur, sc):
    ak = D.col(sc.get("accent", "#2F7BFF"))
    tS, tM, tH, tE = (V.bt(VIS, k, dur) for k in ("sinar", "molekul", "hambur", "mata"))
    kb = D.eio(D.seg(t, tH, tH + 1.4))
    x0, y0, x1, y1 = 90, 700, 990, 1500
    D.rrect(img, x0 + 12, y0 + 16, x1 + 12, y1 + 16, 56, D.INK, 0.10)
    D.rrect(img, x0, y0, x1, y1, 56, D.campur((238, 233, 224), D.terang(ak, 0.74), kb))
    D.rrect_garis(img, x0, y0, x1, y1, 56, D.INK, 4, 0.85)
    D.txt(img, "udara", x1 - 40, y0 + 62, 30, "SB", D.MUTED, D.seg(t, tM, tM + 0.4), "rs")
    # matahari
    sx, sy = 210, 805
    D.matahari(img, sx, sy, 56, "#FFB020", t, D.eob(D.seg(t, 0.05, 0.55)))
    # berkas cahaya (pita 4 warna) menuju molekul utama lalu terus
    hx, hy = MOL[0][0], MOL[0][1]
    ex, ey = 960, 1400
    L1 = math.dist((sx, sy), (hx, hy))
    ux, uy = (hx - sx) / L1, (hy - sy) / L1
    nx, ny = -uy, ux
    u1 = D.eo(D.seg(t, tS, tS + 0.45))
    u2 = D.eo(D.seg(t, tS + 0.35, tS + 0.75))
    for i, c in enumerate(PITA):
        o = (i - 1.5) * 7
        warna = ak if c is None else D.col(c)
        a0 = (sx + ux * 78 + nx * o, sy + uy * 78 + ny * o)
        a1 = (hx + nx * o, hy + ny * o)
        a2 = (ex + nx * o, ey + ny * o)
        if u1 > 0:
            D.polyline(img, D.potong_jalur([a0, a1], u1), 6, warna, 0.95)
        lanjut = 1.0 if c is not None else (1 - kb)
        if u2 > 0 and lanjut > 0.02:
            D.polyline(img, D.potong_jalur([a1, a2], u2), 6, warna, 0.95 * lanjut)
    if u1 > 0.2:  # foton berjalan di sepanjang berkas (tidak pernah diam)
        ph = (t * 0.8) % 1.0
        D.glow(img, sx + (hx - sx) * ph, sy + (hy - sy) * ph, 60, D.PUTIH, 0.55 * u1)
    # molekul udara
    for i, (mx, my, rot) in enumerate(MOL):
        tt = tM + i * 0.06
        s = D.eob(D.seg(t, tt, tt + 0.35))
        jx, jy = 4 * math.sin(t * 7 + i * 1.3), 3 * math.cos(t * 6 + i)
        _molekul(img, mx + jx, my + jy, 27 * s, rot + t * 25, (86, 94, 122), s)
        V.ledakan(img, mx, my, t - tt, ak, seed=i, n=9, jarak=70, dur=0.45)
    # hamburan biru ke segala arah
    if t > tH:
        th = t - tH
        D.glow(img, hx, hy, 170, ak, 0.35 * D.seg(th, 0, 0.3))
        n = 9
        for j in range(n):
            ang = 2 * math.pi * j / n + 0.25
            L = 185 + 30 * math.sin(j * 1.7)
            c, s_ = math.cos(ang), math.sin(ang)
            uu = D.eo(D.clamp((th - j * 0.035) / 0.35))
            D.panah(img, [(hx + c * 42, hy + s_ * 42), (hx + c * L, hy + s_ * L)], 8, ak, uu, 0.95)
            ph = (th * 0.9 + j / n) % 1.0
            D.circ(img, hx + c * (42 + (L + 40) * ph), hy + s_ * (42 + (L + 40) * ph), 9 * (1 - ph) + 3, ak,
                   (1 - ph) * 0.9 * D.seg(th, 0.3, 0.6))
        for i, (mx, my, _) in enumerate(MOL[1:], 1):  # hamburan sekunder kecil
            ph = (th * 0.7 + i * 0.13) % 1.0
            D.ring(img, mx, my, 30 + 60 * ph, 4, ak, 0.5 * (1 - ph) * D.seg(th, 0.4, 0.9))
    # mata menangkap biru dari segala arah
    ue = D.eob(D.seg(t, tE, tE + 0.45))
    if ue > 0.01:
        mx_, my_ = 235, 1400
        D.circ(img, mx_, my_, 100 * ue, D.PUTIH, 0.9)
        D.mata(img, mx_, my_, 150 * ue, ak, t, ue)
        for j, (qx, qy, _) in enumerate((MOL[3], MOL[6], MOL[0])):
            uu = D.eo(D.seg(t, tE + 0.15 + j * 0.1, tE + 0.5 + j * 0.1))
            D.panah(img, D.bezier((qx, qy), ((qx + mx_) / 2, qy - 40), (mx_ + 60, my_ - 40)), 6, ak, uu, 0.85)
        D.txt(img, "biru datang dari segala arah", 540, 1572, 38, "SB", D.INK, D.seg(t, tE + 0.3, tE + 0.7), "ms")


VISUALS_EP = {VIS: sc_hamburan00}
BEAT_TABEL_EP = {VIS: B00}
