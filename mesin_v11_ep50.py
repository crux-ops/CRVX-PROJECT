#!/usr/bin/env python3
"""mesin_v11_ep50.py - modul adegan Ep50: kenapa tsunami Palu (28 September 2018) bisa terjadi.

Pola sama dengan mesin_v11_ep00.py: tabel beat BERNAMA {nama: (fraksi_durasi, sfx)} -> satu sumber untuk animasi,
SFX, dan dorongan kamera. Fraksi beat diambil dari penyelarasan kata VO NYATA (long/mesin_long.align pada
build/ep50_tsunami_palu/audio_proc), jadi gambar muncul tepat saat katanya diucapkan.
Semua gambar = ILUSTRASI skematik (bukan peta/ukuran sebenarnya), tanpa tokoh/wajah; nada hormat tanpa dramatisasi.

Fakta & sumber:
  * Mw 7,5, 28 Sep 2018; sesar geser mendatar Palu-Koro; dua sisi bergeser ~4 m; likuefaksi pantai, longsoran di
    setidaknya 9 tempat; < 20% tinggi tsunami dari proses tektonik (Sassa & Takagawa 2019, Landslides 16:195-200).
  * sesar mendatar ikut berperan besar + sumber tambahan longsoran (Ho dkk. 2021, Earth and Space Science, AGU).
  * teluk panjang, sempit, seperti corong; gelombang terperangkap (laporan ScienceDirect 2023; studi batimetri).
  * tsunami = gelombang dari perpindahan kolom air (NOAA). Evakuasi mandiri: guncangan kuat / ~20 detik atau lebih,
    jangan menunggu sirene, jauhi pantai & tepi sungai, ke tempat tinggi (BMKG, Sep 2026).
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

import diagrams as D
import mesin_v11 as V

# ------------------------------------------------------------------ palet
AIR = (104, 170, 245)
AIR_TUA = (47, 123, 255)
AIR_MUDA = (214, 232, 255)
PASIR = (236, 208, 150)
PASIR_TUA = (196, 160, 102)
TANAH = (205, 168, 116)
TANAH_TUA = (150, 112, 72)
DARAT = (228, 216, 184)
HIJAU = (150, 200, 128)
HIJAU_TUA = (31, 181, 122)
MERAH = (229, 72, 77)
ORANYE = (255, 107, 61)
PANEL = (238, 233, 224)
# keterangan kecil di atas pasir/tanah: D.MUTED hanya 3.1:1 (WCAG teks kecil butuh >= 4.5:1) -> abu tua ~5.6:1
MUTED_TUA = D.gelap(D.MUTED, 0.4)
ASPAL = (96, 96, 108)


# ------------------------------------------------------------------ util umum
def _klip_mulai(img, x0, y0, x1, y1, r, pad=180):
    """simpan area panel (+pad). Semua yang digambar sesudahnya dipotong ke kotak membulat oleh _klip_selesai."""
    W, H = img.size
    X0, Y0 = max(0, int(D.S(x0 - pad))), max(0, int(D.S(y0 - pad)))
    X1, Y1 = min(W, int(D.S(x1 + pad)) + 1), min(H, int(D.S(y1 + pad)) + 1)
    simpan = img.crop((X0, Y0, X1, Y1))
    m, mx, my = D.rrect_mask(x0, y0, x1, y1, r)
    mask = Image.new("L", simpan.size, 0)
    mask.paste(m, (mx - X0, my - Y0))
    return simpan, mask, X0, Y0, X1, Y1


def _klip_poly_mulai(img, pts, pad=180):
    """seperti _klip_mulai tetapi bentuknya poligon (mis. air teluk)."""
    W, H = img.size
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    X0, Y0 = max(0, int(D.S(min(xs) - pad))), max(0, int(D.S(min(ys) - pad)))
    X1, Y1 = min(W, int(D.S(max(xs) + pad)) + 1), min(H, int(D.S(max(ys) + pad)) + 1)
    simpan = img.crop((X0, Y0, X1, Y1))
    mask = Image.new("L", simpan.size, 0)
    ImageDraw.Draw(mask).polygon([(D.S(x) - X0, D.S(y) - Y0) for x, y in pts], fill=255)
    return simpan, mask, X0, Y0, X1, Y1


def _klip_selesai(img, k):
    simpan, mask, X0, Y0, X1, Y1 = k
    simpan.paste(img.crop((X0, Y0, X1, Y1)), (0, 0), mask)
    img.paste(simpan, (X0, Y0))


def _panel(img, x0, y0, x1, y1, r=48, isi=PANEL, a=1.0):
    D.rrect(img, x0 + 12, y0 + 16, x1 + 12, y1 + 16, r, D.INK, 0.10 * a)
    D.rrect(img, x0, y0, x1, y1, r, isi, a)


def _bingkai(img, x0, y0, x1, y1, r=48, a=1.0):
    D.rrect_garis(img, x0, y0, x1, y1, r, D.INK, 4, 0.85 * a)


def _muka(x0, x1, y, t, amp=5.0, lam=150.0, kec=1.4, n=56, benjol=None):
    """titik permukaan air beriak; benjol(x) = kenaikan permukaan (px, positif = naik)."""
    out = []
    for i in range(n + 1):
        x = x0 + (x1 - x0) * i / n
        yy = y + amp * math.sin(2 * math.pi * x / lam + t * kec)
        yy += 0.45 * amp * math.sin(2 * math.pi * x / (lam * 0.53) - t * kec * 1.3)
        if benjol is not None:
            yy -= benjol(x)
        out.append((x, yy))
    return out


def _air(img, pts, y_dasar, warna=AIR, a=0.95, garis=True):
    D.poly(img, pts + [(pts[-1][0], y_dasar), (pts[0][0], y_dasar)], warna, a)
    if garis:
        D.polyline(img, pts, 5, D.terang(warna, 0.55), 0.9 * a)


def _interp(garis, y):
    """x pada polyline garis (urut y naik) di ketinggian y."""
    for (xa, ya), (xb, yb) in zip(garis, garis[1:]):
        if ya <= y <= yb:
            u = 0.0 if yb == ya else (y - ya) / (yb - ya)
            return xa + (xb - xa) * u
    return garis[0][0] if y < garis[0][1] else garis[-1][0]


def _gedung(img, cx, cy, s, a=1.0):
    """ikon kota: tiga balok gedung."""
    for dx, h, w in ((-0.55, 0.9, 0.42), (0.0, 1.35, 0.5), (0.55, 1.05, 0.42)):
        D.rrect(img, cx + dx * s - w * s / 2, cy - h * s, cx + dx * s + w * s / 2, cy, 4, D.INK, 0.85 * a)
        for j in range(int(h * 3)):
            D.rrect(img, cx + dx * s - w * s * 0.22, cy - h * s + 8 + j * s * 0.3, cx + dx * s + w * s * 0.22,
                    cy - h * s + 8 + j * s * 0.3 + s * 0.1, 2, (255, 214, 120), 0.8 * a)


def _pin(img, x, y, s, warna, u, a=1.0):
    if u <= 0.01:
        return
    r = s * D.eob(u)
    D.circ(img, x + 3, y + 4, r, D.INK, 0.18 * a)
    D.circ(img, x, y, r, warna, a)
    D.circ(img, x, y, r * 0.42, D.PUTIH, a)


def _ombak_depan(img, x0, x1, y, t, a, lebar=12):
    """muka gelombang (tampak atas): garis putih bergelombang + cahaya."""
    D.polyline(img, D.gel_pts(x0, x1, y, 7, 210, t * 2.2), lebar, D.PUTIH, a)
    D.polyline(img, D.gel_pts(x0, x1, y + 16, 5, 180, t * 2.0 + 1), 5, D.PUTIH, 0.45 * a)


# ================================================================== intro: gempa mendatar, kok ada tsunami?
V_GESER = "geser50"
B_GESER = {
    "retak": (0.02, "retak"),   # garis sesar merekah (kata pertama "Gempa")
    "geser": (0.06, "thud"),    # dua blok bergeser mendatar ("seperti ini")
    "datang": (0.56, "whoosh"),  # muka gelombang datang ("tsunami tetap datang")
    "menit": (0.69, "tick"),    # "hanya dalam hitungan menit"
    "tanya": (0.84, "pop"),     # "Kenapa bisa begitu?"
}
POHON_KIRI = [(170, 1010), (250, 1120), (150, 1330), (330, 1420), (420, 1060), (230, 1480)]
POHON_KANAN = [(660, 1050), (870, 1000), (760, 1180), (920, 1390), (650, 1450), (830, 1500)]


def _sesar_titik(xm, y0, y1, n=12, amp=11.0, seed=0):
    rr = D.rng("sesar50", seed)
    return [(xm + (rr.uniform(-amp, amp) if 0 < i < n else 0.0), y0 + (y1 - y0) * i / n) for i in range(n + 1)]


def sc_geser50(img, t, dur, sc):
    ak = D.col(sc.get("accent", "#2F7BFF"))
    tR, tG, tD, tM, tT = (V.bt(V_GESER, k, dur) for k in ("retak", "geser", "datang", "menit", "tanya"))
    x0, y0, x1, y1 = 90, 660, 990, 1540
    xm = 540
    u = D.eio(D.seg(t, tG, tG + 1.4))
    guncang = 5.0 * math.sin(t * 43.0) * (1.0 - D.seg(t, tG, tG + 1.9)) * (1.0 if t > tG else 0.0)
    o = 34.0 * u + guncang          # blok kiri ke selatan (bawah), blok kanan ke utara (atas)
    _panel(img, x0, y0, x1, y1, 48, AIR)
    k = _klip_mulai(img, x0, y0, x1, y1, 48)
    for i in range(5):  # laut: riak tampak atas
        D.polyline(img, D.gel_pts(x0 - 30, x1 + 30, 690 + i * 48, 6, 190, t * 1.3 + i * 1.7), 4, AIR_MUDA, 0.5)
    sesar = _sesar_titik(xm, 900, 1620, seed=1)

    def pantai(xa, xb, dy, fase):
        return [(xa + (xb - xa) * i / 14, 925 + 9 * math.sin((xa + (xb - xa) * i / 14) / 68 + fase) + dy)
                for i in range(15)]

    kiri = pantai(x0 - 60, xm, o, 0.0)
    kanan = pantai(xm, x1 + 60, -o, 1.1)
    blok_kiri = kiri + [(x, y + o) for x, y in sesar] + [(x0 - 60, 1620 + o)]
    blok_kanan = kanan + [(x1 + 60, 1620 - o)] + [(x, y - o) for x, y in reversed(sesar)]
    D.poly(img, [(x + 6, y + 10) for x, y in blok_kiri], D.INK, 0.08)
    D.poly(img, blok_kiri, DARAT)
    D.poly(img, blok_kanan, D.terang(DARAT, 0.12))
    D.polyline(img, kiri, 6, PASIR_TUA, 0.9)
    D.polyline(img, kanan, 6, PASIR_TUA, 0.9)
    # jalan melintasi sesar -> terputus & bergeser (ciri khas sesar geser mendatar)
    yj = 1250
    for xa, xb, dy in ((x0 - 20, xm - 6, o), (xm + 6, x1 + 20, -o)):
        D.line(img, xa, yj + dy, xb, yj + dy, 26, ASPAL, 0.9)
        n = int((xb - xa) // 60)
        for j in range(n):
            xx = xa + 18 + j * 60
            D.line(img, xx, yj + dy, xx + 28, yj + dy, 5, D.PUTIH, 0.9)
    for (px, py), dy in [(p, o) for p in POHON_KIRI] + [(p, -o) for p in POHON_KANAN]:
        goy = 2.0 * math.sin(t * 2.3 + px)
        D.circ(img, px + goy, py + dy, 24, HIJAU, 0.95)
        D.circ(img, px + goy - 7, py + dy - 7, 9, D.terang(HIJAU, 0.4), 0.8)
    # garis sesar (merekah dari utara ke selatan) + lanjutan samar di bawah laut
    ur = D.eo(D.seg(t, tR - 0.25, tR + 0.45))
    tengah = [(x, y + (o if i % 2 else -o) * 0.0) for i, (x, y) in enumerate(sesar)]
    if ur > 0:
        D.polyline(img, D.potong_jalur(tengah, ur), 9, MERAH, 0.95)
        for j in range(6):
            yy = 690 + j * 38
            D.line(img, xm, yy, xm, yy + 20, 5, MERAH, 0.45 * ur)
    # denyut pusat gempa
    if t > tG:
        for j in range(3):
            ph = ((t - tG) * 0.8 + j / 3) % 1.0
            D.ring(img, xm, 1090, 20 + 150 * ph, 5, MERAH, 0.45 * (1 - ph))
    # panah gerak blok
    ua = D.eo(D.seg(t, tG + 0.25, tG + 0.9))
    if ua > 0:
        den = 0.85 + 0.15 * math.sin(t * 4)
        D.panah(img, [(300, 1040 + o), (300, 1180 + o)], 16, D.INK, ua, 0.9 * den)
        D.panah(img, [(790, 1400 - o), (790, 1260 - o)], 16, D.INK, ua, 0.9 * den)
    # muka gelombang tsunami datang ke pantai
    for j in range(2):
        tt = t - tD - j * 0.9
        if 0 < tt < 2.6:
            yy = 690 + 215 * D.eo(min(1.0, tt / 2.2))
            _ombak_depan(img, x0 - 30, x1 + 30, yy, t, 0.95 * D.seg(tt, 0, 0.25) * (1 - D.seg(tt, 2.0, 2.6)))
            D.glow(img, 540, yy, 260, D.PUTIH, 0.25 * (1 - D.seg(tt, 1.6, 2.6)))
    _klip_selesai(img, k)
    _bingkai(img, x0, y0, x1, y1, 48)
    # label waktu & tempat
    ap = D.eo(D.seg(t, 0.39 * dur, 0.39 * dur + 0.4))
    if ap > 0:
        D.chip(img, "PALU  ·  2018", 250, 722, 28, D.INK, D.PUTIH, ap)
    if t > tM:
        um = D.eob(D.seg(t, tM, tM + 0.4))
        D.circ(img, 580, 722, 30 * um, D.PUTIH, 0.95)
        D.jam(img, 580, 722, 26 * um, ak, t, um)
        V.chip_pop(img, "HITUNGAN MENIT", 780, 722, t, tM + 0.05, 28, ak)
    V.stiker(img, "?", 540, 1110, t, tT, 96, ak, rot=-6)


# ================================================================== f1: sesar Palu-Koro bergeser mendatar
V_SESAR = "sesar50"
B_SESAR = {
    "peta": (0.02, "swish"),    # skema teluk muncul
    "gempa": (0.22, "thud"),    # "gempa magnitudo tujuh koma lima"
    "sesar": (0.50, "retak"),   # "Sumbernya Sesar Palu-Koro" -> sesar merobek ke selatan
    "geser": (0.64, "swish"),   # "Dua sisi kerak bumi bergeser mendatar"
    "meter": (0.85, "ding"),    # "sekitar empat meter"
}
TELUK_KIRI = [(430, 800), (452, 880), (470, 960), (488, 1040), (500, 1120), (510, 1200), (522, 1280), (536, 1340)]
TELUK_KANAN = [(700, 800), (688, 880), (664, 960), (644, 1040), (628, 1120), (614, 1200), (602, 1280), (586, 1340)]
SESAR_F1 = [(285, 770), (370, 850), (452, 935), (520, 1030), (555, 1130), (563, 1240), (566, 1350), (572, 1460),
            (578, 1580)]


def sc_sesar50(img, t, dur, sc):
    ak = D.col(sc.get("accent", "#FF6B3D"))
    tP, tE, tS, tG, tM = (V.bt(V_SESAR, k, dur) for k in ("peta", "gempa", "sesar", "geser", "meter"))
    x0, y0, x1, y1 = 90, 700, 990, 1560
    up = D.eob(D.seg(t, tP - 0.1, tP + 0.45))
    if up <= 0.01:
        return
    _panel(img, x0, y0, x1, y1, 48, DARAT, up)
    k = _klip_mulai(img, x0, y0, x1, y1, 48)
    for bx, by, br in ((200, 1000, 90), (820, 1120, 110), (300, 1400, 80), (850, 1450, 70), (760, 880, 60)):
        D.circ(img, bx, by, br, HIJAU, 0.28)
    laut = [(330, y0 - 40), (x1 + 40, y0 - 40), (x1 + 40, 800), *TELUK_KANAN, (561, 1362),
            *reversed(TELUK_KIRI), (330, 800), (300, 760)]
    D.poly(img, laut, AIR)
    D.polyline(img, [*TELUK_KIRI], 5, PASIR_TUA, 0.8)
    D.polyline(img, [*TELUK_KANAN], 5, PASIR_TUA, 0.8)
    for i, y in enumerate(range(880, 1320, 80)):  # kilau air teluk
        xl, xr = _interp(TELUK_KIRI, y) + 16, _interp(TELUK_KANAN, y) - 16
        ph = (t * 0.6 + i * 0.37) % 1.0
        D.line(img, xl + (xr - xl) * 0.15 * ph, y, xr - (xr - xl) * 0.15 * (1 - ph), y, 4, AIR_MUDA, 0.55)
    for i in range(3):
        D.polyline(img, D.gel_pts(360, x1 + 30, 725 + i * 26, 4, 160, t * 1.2 + i), 3, AIR_MUDA, 0.5)
    # jalan melintasi sesar di selatan kota -> bergeser
    ug = D.eio(D.seg(t, tG, tG + 1.1))
    o = 16.0 * ug
    yj = 1498
    for xa, xb, dy in ((380, 566, o), (590, 780, -o)):
        D.line(img, xa, yj + dy, xb, yj + dy, 18, ASPAL, 0.9)
        for j in range(int((xb - xa) // 46)):
            D.line(img, xa + 12 + j * 46, yj + dy, xa + 32 + j * 46, yj + dy, 4, D.PUTIH, 0.85)
    # sesar merobek dari pusat gempa ke selatan (tampak sebagai garis merah putus-putus berjalan)
    us = D.eo(D.seg(t, tS - 0.1, tS + 1.3))
    if us > 0:
        jal = D.potong_jalur(SESAR_F1, us)
        D.polyline(img, jal, 8, MERAH, 0.95)
        ex, ey = jal[-1]
        if us < 1:
            D.glow(img, ex, ey, 70, MERAH, 0.55)
    _klip_selesai(img, k)
    _bingkai(img, x0, y0, x1, y1, 48, up)
    # kota Palu di ujung teluk
    _gedung(img, 561, 1405, 30, up)
    D.txt(img, "PALU", 561, 1452, 30, "B", D.INK, up, "ms")
    D.txt(img, "Sulawesi Tengah (ilustrasi)", 126, 968, 24, "M", MUTED_TUA, D.seg(t, 0.37 * dur, 0.37 * dur + 0.4), "ls")
    # pusat gempa + magnitudo
    if t > tE - 0.2:
        ue = D.eob(D.seg(t, tE - 0.15, tE + 0.3))
        for j in range(3):
            ph = ((t - tE) * 0.7 + j / 3) % 1.0
            D.ring(img, 285, 770, 18 + 120 * ph, 5, MERAH, 0.5 * (1 - ph) * ue)
        D.bintang(img, 285, 770, 30 * ue, MERAH, 1.0, rot=t * 20)
        D.circ(img, 285, 770, 7 * ue, D.PUTIH, 1.0)
        ub = D.eo(D.seg(t, tE, tE + 0.35))
        D.rrect(img, 150, 830, 400, 920, 26, D.PUTIH, 0.95 * ub, D.INK, 4)
        D.txt(img, "M", 207, 896, 52, "B", MERAH, ub, "ls")
        # odometer: y = BASELINE (sama dengan "M"), isi "M 7,5" dipusatkan di kotak 150..400
        D.odometer(img, 7.5, 261, 896, 56, D.INK, ub, "l", "B", D.seg(t, tE + 0.1, tE + 1.3), desimal=1)
    # label sesar
    if t > tS:
        ul = D.eo(D.seg(t, tS + 0.5, tS + 1.0))
        D.line(img, 600, 1060, 548, 1090, 4, D.INK, 0.8 * ul)
        V.chip_pop(img, "SESAR PALU-KORO", 770, 1040, t, tS + 0.5, 28, MERAH)
    # dua sisi bergeser: barat ke selatan, timur ke utara
    ua = D.eo(D.seg(t, tG, tG + 0.6))
    if ua > 0:
        den = 0.85 + 0.15 * math.sin(t * 4)
        D.panah(img, [(410, 1150), (410, 1290)], 16, D.INK, ua, 0.9 * den)
        D.panah(img, [(725, 1290), (725, 1150)], 16, D.INK, ua, 0.9 * den)
    if t > tM:
        um = D.eo(D.seg(t, tM, tM + 0.5))
        D.line(img, 612, yj - 16, 612, yj + 16, 4, D.INK, um)
        D.line(img, 600, yj - 16, 624, yj - 16, 4, D.INK, um)
        D.line(img, 600, yj + 16, 624, yj + 16, 4, D.INK, um)
        V.chip_pop(img, "SEKITAR 4 METER", 800, 1438, t, tM, 28, ak)


# ================================================================== f2: sesar naik vs sesar mendatar
V_NAIK = "naik50"
B_NAIK = {
    "naik": (0.03, "swish"),    # "Tsunami besar biasanya lahir dari sesar naik"
    "angkat": (0.27, "thud"),   # "Dasar laut terangkat tiba-tiba"
    "dorong": (0.37, "whoosh"),  # "mendorong seluruh kolom air"
    "datar": (0.60, "swish"),   # "Sesar mendatar"
    "geser": (0.66, "blip"),    # "menggeser dasar laut ke samping"
    "diam": (0.82, "ding"),     # "airnya nyaris tidak terangkat"
}


def sc_naik50(img, t, dur, sc):
    ak = D.col(sc.get("accent", "#8A5CF6"))
    tN, tA, tO, tD, tG, tI = (V.bt(V_NAIK, k, dur) for k in ("naik", "angkat", "dorong", "datar", "geser", "diam"))
    # ---------------- panel A: sesar naik (penampang)
    x0, y0, x1, y1 = 90, 700, 990, 1110
    ua = D.eob(D.seg(t, tN - 0.1, tN + 0.45))
    if ua > 0.01:
        _panel(img, x0, y0, x1, y1, 40, D.PUTIH, ua)
        k = _klip_mulai(img, x0, y0, x1, y1, 40)
        lift = 34.0 * D.eob(D.seg(t, tA, tA + 0.55))
        H = 44.0 * D.seg(t, tA, tA + 0.5)
        v = 230.0

        def benjol(x):
            if t < tO:
                return H * math.exp(-(((x - 560) / 120.0) ** 2))
            d = v * (t - tO)
            s_ = H * 0.62 * (1 - 0.25 * D.seg(t, tO, tO + 4))
            return s_ * (math.exp(-(((x - 560 - d) / 110.0) ** 2)) + math.exp(-(((x - 560 + d) / 110.0) ** 2)))

        pts = _muka(x0 - 30, x1 + 30, 800, t, 3.0, 170, 1.3, 64, benjol)
        _air(img, pts, 1160, AIR, 0.9)
        kiri = [(x0 - 40, 1010), (520, 1010), (470, 1160), (x0 - 40, 1160)]
        kanan = [(520 - 0.36 * lift, 1010 - lift), (x1 + 40, 1010 - lift), (x1 + 40, 1160), (470, 1160)]
        D.poly(img, kiri, TANAH)
        D.poly(img, kanan, D.terang(TANAH, 0.1))
        for dy in (40, 80):
            D.line(img, x0 - 40, 1010 + dy, 505 - dy * 0.35, 1010 + dy, 4, TANAH_TUA, 0.6)
            D.line(img, 520 - 0.36 * lift - dy * 0.35, 1010 + dy - lift, x1 + 40, 1010 + dy - lift, 4, TANAH_TUA, 0.6)
        D.line(img, 520 - 0.36 * lift, 1010 - lift, 470, 1160, 6, MERAH, 0.9)
        if t > tO:  # kolom air terdorong naik
            for j, xx in enumerate((470, 560, 650)):
                uu = D.eo(D.seg(t, tO + j * 0.08, tO + 0.6 + j * 0.08)) * (1 - D.seg(t, tO + 2.4, tO + 3.2))
                if uu > 0:
                    D.panah(img, [(xx, 985 - lift), (xx, 850)], 12, D.PUTIH, uu, 0.9)
        _klip_selesai(img, k)
        _bingkai(img, x0, y0, x1, y1, 40, ua)
        D.chip(img, "SESAR NAIK", 238, 746, 28, ak, D.PUTIH, ua)
        if t > tA:
            D.txt(img, "dasar laut terangkat", 950, 752, 28, "SB", D.INK, D.eo(D.seg(t, tA + 0.2, tA + 0.6)), "rs")
    # ---------------- panel B: sesar mendatar (blok diagram miring)
    x0, y0, x1, y1 = 90, 1150, 990, 1560
    ub = D.eob(D.seg(t, tN + 0.3, tN + 0.8))
    redup = 0.6 * (1 - D.seg(t, tD - 0.25, tD + 0.25))
    if ub > 0.01:
        _panel(img, x0, y0, x1, y1, 40, D.PUTIH, ub)
        k = _klip_mulai(img, x0, y0, x1, y1, 40)
        s = 42.0 * D.eio(D.seg(t, tG, tG + 1.3))
        dx = 90  # kemiringan blok (belakang bergeser kanan)
        yb, ym, yf, yd = 1330, 1400, 1470, 1528
        belakang = [(230 + s, yb), (930 + s, yb), (930 + s - dx * 0.5, ym), (230 + s - dx * 0.5, ym)]
        depan = [(185 - s, ym), (885 - s, ym), (885 - s - dx * 0.5, yf), (185 - s - dx * 0.5, yf)]
        D.poly(img, belakang, D.terang(TANAH, 0.12))
        D.poly(img, depan, TANAH)
        muka_depan = [(140 - s, yf), (840 - s, yf), (840 - s, yd), (140 - s, yd)]
        D.poly(img, muka_depan, TANAH_TUA, 0.95)
        for i in range(9):  # garis lurus melintasi sesar -> patah & bergeser
            xa = 270 + i * 76
            D.line(img, xa + s, yb + 4, xa + s - dx * 0.5, ym - 2, 5, TANAH_TUA, 0.8)
            D.line(img, xa - s - dx * 0.5, ym + 2, xa - s - dx, yf - 4, 5, TANAH_TUA, 0.8)
        D.line(img, 120, ym, 960, ym, 6, MERAH, 0.9)
        # air di atas: permukaan tetap datar
        atas = [(230, 1200), (930, 1200), (840, 1340), (140, 1340)]
        D.poly(img, atas, AIR, 0.35)
        for j in range(4):
            yy = 1225 + j * 30
            D.polyline(img, D.gel_pts(190 - j * 18, 900 - j * 18, yy, 2, 120, t * 1.5 + j), 3, AIR_TUA, 0.35)
        D.poly(img, [(140, 1340), (840, 1340), (840, yf), (140 - 0, yf)], AIR, 0.28)
        _klip_selesai(img, k)
        _bingkai(img, x0, y0, x1, y1, 40, ub)
        if redup > 0.01:
            D.rrect(img, x0, y0, x1, y1, 40, D.PUTIH, redup)
        D.chip(img, "SESAR MENDATAR", 262, 1196, 28, ak, D.PUTIH, ub * (1 - 0.5 * redup))
        ug = D.eo(D.seg(t, tG, tG + 0.6))
        if ug > 0:
            D.panah(img, [(640, 1368), (800, 1368)], 12, D.INK, ug, 0.9)
            D.panah(img, [(560, 1440), (400, 1440)], 12, D.INK, ug, 0.9)
        if t > tI:
            V.chip_pop(img, "AIR NYARIS TIDAK TERANGKAT", 540, 1268, t, tI, 28, AIR_TUA)


# ================================================================== f3: likuefaksi -> longsoran pantai -> gelombang
V_CAIR = "likuefaksi50"
B_CAIR = {
    "guncang": (0.05, "detak"),     # "Tapi guncangan kuat"
    "pasir": (0.16, "pop"),         # "pasir jenuh air"
    "cair": (0.26, "gelembung"),    # "mencair, disebut likuefaksi"
    "runtuh": (0.45, "retak"),      # "Tanah pantai runtuh"
    "luncur": (0.54, "whoosh"),     # "meluncur ke laut"
    "sembilan": (0.63, "tick"),     # "setidaknya di sembilan tempat"
    "gelombang": (0.76, "swish"),   # "tiap longsoran mendorong air menjadi gelombang"
}
BAJI = [(420, 930), (600, 930), (720, 1044), (600, 1080), (500, 1010)]
LERENG = [(600, 930), (1030, 1338)]
PIN9 = [(842, 760), (848, 792), (856, 826), (868, 856), (888, 872), (909, 858), (920, 826), (927, 792), (934, 760)]


def _di_dalam(x, y, poly):
    dalam = False
    for (xa, ya), (xb, yb) in zip(poly, poly[1:] + poly[:1]):
        if (ya > y) != (yb > y) and x < xa + (y - ya) * (xb - xa) / (yb - ya):
            dalam = not dalam
    return dalam


BUTIR = [(x, y) for y in range(944, 1076, 24) for x in range(430, 716, 24)
         if _di_dalam(x + (12 if (y // 24) % 2 else 0), y, BAJI)]


def sc_likuefaksi50(img, t, dur, sc):
    ak = D.col(sc.get("accent", "#F4B400"))
    tG, tP, tC, tR, tL, tS, tW = (V.bt(V_CAIR, k, dur)
                                  for k in ("guncang", "pasir", "cair", "runtuh", "luncur", "sembilan", "gelombang"))
    x0, y0, x1, y1 = 90, 700, 990, 1540
    up = D.eob(D.seg(t, -0.1, 0.4))
    if up <= 0.01:
        return
    env = D.seg(t, tG, tG + 0.3) * (1 - D.seg(t, tL + 0.6, tL + 1.4))
    jx = 4.5 * math.sin(t * 51.0) * env
    _panel(img, x0, y0, x1, y1, 48, PANEL, up)
    k = _klip_mulai(img, x0, y0, x1, y1, 48)
    # luncuran baji di sepanjang lereng
    ul = D.eio(D.seg(t, tL, tL + 1.7))
    arah = (0.725, 0.689)
    jarak = 190.0 * ul

    def geser(p):
        f = 0.75 + 0.5 * (p[0] - 420) / 300
        return (p[0] + arah[0] * jarak * f + jx, p[1] + arah[1] * jarak * f * 0.92)

    xc = 690 + arah[0] * jarak
    A = 58.0 * D.seg(t, tL + 0.3, tL + 1.0)
    vw = 62.0

    def benjol(x):
        if t < tW:
            return A * math.exp(-(((x - xc) / 90.0) ** 2))
        d = vw * (t - tW)
        return A * 0.9 * math.exp(-(((x - xc - d) / 100.0) ** 2)) + A * 0.35 * math.exp(-(((x - xc) / 80.0) ** 2))

    pts = _muka(430, x1 + 40, 930, t, 3.0, 150, 1.4, 70, benjol)
    _air(img, pts, 1600, AIR, 0.92)
    if A > 2:
        puncak = [(x, y) for x, y in pts if benjol(x) > A * 0.35]
        if len(puncak) > 1:
            D.polyline(img, puncak, 8, D.PUTIH, 0.9)
            if t > tW:
                px_, py_ = max(puncak, key=lambda q: -q[1])
                ua_ = D.eo(D.seg(t, tW, tW + 0.5))
                D.panah(img, [(px_ - 40, py_ - 34), (px_ + 50, py_ - 34)], 8, D.INK, ua_, 0.75)
    darat = [(x0 - 40, 930), (420, 930), (500, 1010), (600, 1080), (720, 1044), (1030, 1338), (1030, 1600),
             (x0 - 40, 1600)]
    D.poly(img, [(x + jx, y) for x, y in darat], TANAH)
    for dy, xe in ((70, 455), (150, 555), (250, 720)):
        D.line(img, x0 - 40 + jx, 930 + dy, xe + jx, 930 + dy, 4, TANAH_TUA, 0.45)
    # baji pasir jenuh air (butir bergetar, air di sela)
    baji = [geser(p) for p in BAJI]
    D.poly(img, baji, D.campur(PASIR, AIR, 0.28 + 0.25 * D.seg(t, tC, tC + 0.8)))
    cair = D.seg(t, tC, tC + 1.0)
    rr = D.rng("butir50")
    for bx, by in BUTIR:
        ph = rr.uniform(0, 6.28)
        gx = geser((bx, by))
        g = (3.0 * env + 2.5 * cair) * math.sin(t * 13 + ph)
        D.circ(img, gx[0] + g, gx[1] + 2.0 * math.cos(t * 11 + ph) * cair, 8.5 - 1.5 * cair, PASIR_TUA, 0.9)
    D.polyline(img, [geser(p) for p in BAJI] + [geser(BAJI[0])], 3, PASIR_TUA, 0.7)
    # retakan di belakang baji
    ur = D.eo(D.seg(t, tR, tR + 0.5))
    if ur > 0:
        D.polyline(img, D.potong_jalur([(420 + jx, 930), (500 + jx, 1010), (600 + jx, 1080)], ur), 7, TANAH_TUA, 0.95)
    # getaran permukaan
    if env > 0.05:
        for gx0 in (170, 290, 390):
            D.polyline(img, [(gx0 + i * 9, 905 + (6 if i % 2 else -6) * env) for i in range(7)], 3, D.INK, 0.5 * env)
    _klip_selesai(img, k)
    _bingkai(img, x0, y0, x1, y1, 48, up)
    # kaca pembesar: butir menempel + air di sela -> butir terlepas (mencair)
    uz = D.eob(D.seg(t, tP, tP + 0.45))
    if uz > 0.01:
        cx, cy, R = 245, 1225, 140 * uz
        D.line(img, cx + R * 0.7, cy - R * 0.7, 470, 985, 5, D.INK, 0.7 * uz)
        D.circ(img, cx + 8, cy + 10, R + 6, D.INK, 0.15)
        kz = _klip_mulai(img, cx - R, cy - R, cx + R, cy + R, R, pad=60)
        D.circ(img, cx, cy, R, AIR, 1.0)
        rz = D.rng("zoom50")
        sp = 1.0 + 0.32 * cair
        for iy in range(-4, 5):
            for ix in range(-4, 5):
                ox = (ix + (0.5 if iy % 2 else 0.0)) * 58 * sp * uz
                oy = iy * 50 * sp * uz
                ph = rz.uniform(0, 6.28)
                gx = ox + (5 * env + 9 * cair) * math.sin(t * 3.1 + ph)
                gy = oy + 9 * cair * math.cos(t * 2.7 + ph)
                if math.hypot(gx, gy) > R + 30:
                    continue
                D.circ(img, cx + gx, cy + gy, 27 * uz, PASIR, 1.0)
                D.circ(img, cx + gx - 8 * uz, cy + gy - 8 * uz, 8 * uz, D.terang(PASIR, 0.5), 0.8)
        _klip_selesai(img, kz)
        D.ring(img, cx, cy, R, 7, D.INK, 0.9 * uz)
        lab = "butir pasir + air" if t < tC + 0.3 else "butir terlepas: MENCAIR"
        # label terpanjang (331 px) tetap DI DALAM panel: tepi kiri >= x0 + 26 (dulu keluar bingkai 11 px);
        # kedua keadaan label memakai posisi yang sama (tidak melompat saat teks berganti)
        lx = max(cx, x0 + 26 + D.txt_w("butir terlepas: MENCAIR", 28, "SB") / 2)
        D.txt(img, lab, lx, cy + R + 50, 28, "SB", D.INK, uz, "ms")  # kontras 7.9:1 di atas TANAH
    # 9 lokasi longsoran pantai (skema teluk kecil)
    if t > tS - 0.3:
        us = D.eob(D.seg(t, tS - 0.3, tS + 0.1))
        D.rrect(img, 650, 718, 962, 902, 28, D.PUTIH, 0.95 * us, D.INK, 4)
        D.txt(img, "SETIDAKNYA", 672, 768, 22, "SB", D.MUTED, us, "ls")
        D.odometer(img, 9, 672, 830, 64, D.gelap(ak, 0.3), us, "l", "B", D.seg(t, tS, tS + 1.0))
        D.txt(img, "LOKASI", 720, 830, 30, "B", D.INK, us, "ls")
        teluk = [(836, 730), (862, 730), (873, 800), (888, 840), (906, 800), (916, 730), (946, 730), (940, 820),
                 (905, 880), (870, 882), (840, 820)]
        D.poly(img, teluk, AIR, 0.9 * us)
        for i, (px, py) in enumerate(PIN9):
            _pin(img, px, py, 8, MERAH, D.seg(t, tS + i * 0.11, tS + i * 0.11 + 0.25))


# ================================================================== f4: dua studi -> jawabannya gabungan
V_PORSI = "porsi50"
B_PORSI = {
    "a": (0.03, "swish"),      # "Satu studi internasional memperkirakan"
    "persen": (0.19, "tick"),  # "kurang dari dua puluh persen tinggi gelombang"
    "b": (0.46, "swish"),      # "Studi lain menemukan"
    "besar": (0.60, "pop"),    # "sesar di dasar teluk tetap berperan besar"
    "debat": (0.73, "click"),  # "Porsinya masih diperdebatkan"
    "gabung": (0.84, "ding"),  # "jawabannya gabungan"
}


def _kartu(img, x0, y0, x1, y1, u):
    D.rrect(img, x0 + 10, y0 + 14, x1 + 10, y1 + 14, 36, D.INK, 0.10 * u)
    D.rrect(img, x0, y0, x1, y1, 36, D.PUTIH, u, D.INK, 4)


def sc_porsi50(img, t, dur, sc):
    tA, tP, tB, tS, tD, tG = (V.bt(V_PORSI, k, dur) for k in ("a", "persen", "b", "besar", "debat", "gabung"))
    ua = D.eob(D.seg(t, tA - 0.1, tA + 0.45))
    if ua > 0.01:
        _kartu(img, 110, 712, 970, 1042, ua)
        D.txt(img, "STUDI 2019", 150, 778, 40, "B", D.INK, ua, "ls")
        D.txt(img, "jurnal Landslides", 150, 820, 28, "M", D.MUTED, ua, "ls")
        D.rrect(img, 150, 868, 930, 940, 36, (236, 232, 226), ua)
        up = D.eo(D.seg(t, tP, tP + 1.3))
        if up > 0:
            xs = 150 + 780 * 0.18 * min(1.0, up / 0.35)
            D.rrect(img, 150, 868, max(186, xs), 940, 36, ORANYE, ua)
            if up > 0.35:
                D.rrect(img, xs - 30, 868, xs + (930 - xs) * (up - 0.35) / 0.65, 940, 36, AIR_TUA, ua)
                D.rrect(img, xs - 30, 868, xs + 4, 940, 0, ORANYE, ua)
            D.txt(img, "SESAR < 20%", 150, 1000, 30, "B", ORANYE, D.seg(t, tP + 0.2, tP + 0.6), "ls")
            D.txt(img, "LONGSORAN: MAYORITAS", 930, 1000, 30, "B", AIR_TUA, D.seg(t, tP + 0.9, tP + 1.3), "rs")
    ub = D.eob(D.seg(t, tA + 0.4, tA + 0.9))
    redup = 0.62 * (1 - D.seg(t, tB - 0.25, tB + 0.25))
    if ub > 0.01:
        _kartu(img, 110, 1082, 970, 1412, ub)
        D.txt(img, "STUDI 2021", 150, 1148, 40, "B", D.INK, ub, "ls")
        D.txt(img, "jurnal AGU", 150, 1190, 28, "M", D.MUTED, ub, "ls")
        if redup > 0.01:
            D.rrect(img, 110, 1082, 970, 1412, 36, D.PUTIH, redup * ub)
        if t > tS:
            V.chip_pop(img, "SESAR: BERPERAN BESAR", 390, 1262, t, tS, 32, ORANYE)
            V.chip_pop(img, "+ LONGSORAN", 290, 1346, t, tS + 0.35, 28, AIR_TUA)
    if t > tD:  # diperdebatkan: panah bolak-balik antara dua studi
        ud = D.eo(D.seg(t, tD, tD + 0.5)) * (1 - D.seg(t, tG, tG + 0.4))
        if ud > 0:
            ph = math.sin((t - tD) * 5.0)
            D.panah(img, [(860, 1030), (860, 1100)], 10, D.INK, ud, 0.8 * (0.6 + 0.4 * ph))
            D.panah(img, [(900, 1100), (900, 1030)], 10, D.INK, ud, 0.8 * (0.6 - 0.4 * ph))
    if t > tG:  # gabungan: satu batang oranye + biru, stiker
        ug = D.eo(D.seg(t, tG, tG + 0.6))
        D.rrect(img, 250, 1488, 830, 1532, 22, AIR_TUA, ug)
        D.rrect(img, 250, 1488, 250 + 580 * 0.42, 1532, 22, ORANYE, ug)
        D.rrect(img, 250 + 580 * 0.42 - 22, 1488, 250 + 580 * 0.42, 1532, 0, ORANYE, ug)
        D.txt(img, "sesar + longsoran", 540, 1575, 28, "SB", D.INK, ug, "ms")
        V.stiker(img, "GABUNGAN", 540, 1462, t, tG + 0.1, 50, HIJAU_TUA, rot=-4)


# ================================================================== f5: teluk sempit seperti corong
V_TELUK = "teluk50"
B_TELUK = {
    "teluk": (0.03, "swish"),       # "Bentuk Teluk Palu ikut memperparah"
    "corong": (0.18, "pop"),        # "panjang dan sempit seperti corong"
    "gelombang": (0.33, "whoosh"),  # "gelombang terperangkap"
    "pantul": (0.45, "swish"),      # "memantul"
    "tumpuk": (0.51, "thud"),       # "dan menumpuk"
    "menit": (0.63, "tick"),        # "air tiba hanya beberapa menit"
    "meter": (0.79, "blip"),        # "hingga sekitar sepuluh meter"
}
TK = [(300, 700), (330, 780), (370, 860), (410, 940), (440, 1020), (465, 1100), (485, 1180), (500, 1260), (512, 1340),
      (524, 1400)]
TN = [(820, 700), (790, 780), (750, 860), (715, 940), (685, 1020), (660, 1100), (640, 1180), (622, 1260), (608, 1340),
      (596, 1400)]
SUMBER5 = [(575, 900), (452, 1060), (652, 1142), (503, 1290)]


def sc_teluk50(img, t, dur, sc):
    ak = D.col(sc.get("accent", "#2F7BFF"))
    tT, tC, tG, tP, tU, tM, tE = (V.bt(V_TELUK, k, dur)
                                  for k in ("teluk", "corong", "gelombang", "pantul", "tumpuk", "menit", "meter"))
    x0, y0, x1, y1 = 90, 700, 990, 1560
    ut = D.eob(D.seg(t, tT - 0.1, tT + 0.45))
    if ut <= 0.01:
        return
    _panel(img, x0, y0, x1, y1, 48, DARAT, ut)
    k = _klip_mulai(img, x0, y0, x1, y1, 48)
    for bx, by, br in ((180, 900, 90), (900, 960, 100), (230, 1420, 90), (880, 1400, 80)):
        D.circ(img, bx, by, br, HIJAU, 0.28)
    air_teluk = [(300, y0 + 2), (820, y0 + 2), *TN, (560, 1428), *reversed(TK)]
    D.poly(img, air_teluk, AIR)
    _klip_selesai(img, k)
    # gelombang di dalam teluk (dipotong ke bentuk air)
    kw = _klip_poly_mulai(img, air_teluk)
    for i, y in enumerate(range(760, 1400, 70)):
        xl, xr = _interp(TK, y) + 14, _interp(TN, y) - 14
        ph = (t * 0.5 + i * 0.31) % 1.0
        D.line(img, xl + (xr - xl) * 0.2 * ph, y, xr - (xr - xl) * 0.2 * (1 - ph), y, 4, AIR_MUDA, 0.5)
    if t > tG:
        for j, (sx, sy) in enumerate(SUMBER5):
            for m in range(3):
                tt = (t - tG - j * 0.18 - m * 0.55) % 1.65
                if t - tG - j * 0.18 - m * 0.55 < 0:
                    continue
                D.ring(img, sx, sy, 20 + 170 * tt, 7, D.PUTIH, 0.75 * (1 - tt / 1.65))
    if t > tU:  # menumpuk di ujung teluk
        uu = D.seg(t, tU, tU + 0.8)
        for m in range(4):
            ph = ((t - tU) * 0.9 + m / 4) % 1.0
            D.ring(img, 560, 1420, 150 - 120 * ph, 8, D.PUTIH, 0.8 * uu * ph)
        D.glow(img, 560, 1390, 170, D.PUTIH, (0.25 + 0.1 * math.sin(t * 5)) * uu)
    _klip_selesai(img, kw)
    D.polyline(img, TK, 5, PASIR_TUA, 0.85 * ut)
    D.polyline(img, TN, 5, PASIR_TUA, 0.85 * ut)
    _bingkai(img, x0, y0, x1, y1, 48, ut)
    _gedung(img, 560, 1470, 28, ut)
    D.txt(img, "PALU", 560, 1522, 30, "B", D.INK, ut, "ms")
    # lebar di mulut vs sempit di ujung (corong)
    uc = D.eo(D.seg(t, tC, tC + 0.6))
    if uc > 0:
        D.panah(img, [(560, 760), (338, 760)], 8, D.INK, uc, 0.85)
        D.panah(img, [(560, 760), (782, 760)], 8, D.INK, uc, 0.85)
        D.txt(img, "lebar", 560, 742, 26, "SB", D.INK, uc, "ms")
        D.panah(img, [(560, 1330), (518, 1330)], 6, D.INK, uc, 0.85)
        D.panah(img, [(560, 1330), (602, 1330)], 6, D.INK, uc, 0.85)
        D.txt(img, "sempit", 660, 1340, 26, "SB", D.INK, uc, "ls")
    # memantul di antara dinding teluk
    up = D.eo(D.seg(t, tP, tP + 1.6))
    if up > 0:
        zig = [(560, 800), (412, 930), (690, 1030), (478, 1150), (632, 1250), (560, 1370)]
        D.panah(img, zig, 9, ak, up, 0.9 * (1 - 0.5 * D.seg(t, tP + 4.5, tP + 6.0)))
    # tiba dalam beberapa menit
    if t > tM:
        um = D.eob(D.seg(t, tM, tM + 0.4))
        D.circ(img, 660, 1470, 34 * um, D.PUTIH, 0.95)
        D.jam(img, 660, 1470, 30 * um, D.INK, t, um)
        V.chip_pop(img, "BEBERAPA MENIT", 812, 1470, t, tM + 0.05, 26, ak)  # tepi kanan <= 950 (kolom tombol)
    # hingga sekitar 10 meter (pengukur di daratan kiri)
    if t > tE - 0.2:
        ue = D.eo(D.seg(t, tE - 0.2, tE + 0.2))
        D.rrect(img, 136, 1010, 196, 1410, 30, D.PUTIH, 0.95 * ue, D.INK, 4)
        lv = D.eo(D.seg(t, tE, tE + 1.4))
        D.rrect(img, 144, 1402 - 384 * lv, 188, 1402, 22, AIR_TUA, ue)
        for j in range(6):
            yy = 1402 - j * 384 / 5
            D.line(img, 196, yy, 212, yy, 3, D.INK, 0.8 * ue)
        D.txt(img, "~", 222, 1022, 40, "B", D.INK, ue, "ls")  # pusat tinta "~" = pusat angka
        D.odometer(img, 10, 248, 1026, 44, D.INK, ue, "l", "B", lv, satuan=" m")
        D.txt(img, "di beberapa titik", 222, 1076, 24, "M", MUTED_TUA, ue, "ls")


# ================================================================== f6: pelajaran - evakuasi mandiri
V_SELAMAT = "selamat50"
B_SELAMAT = {
    "pantai": (0.14, "swish"),     # "kalau berada di pantai"
    "gempa": (0.26, "detak"),      # "merasakan gempa kuat"
    "detik": (0.40, "tick"),       # "guncangan sekitar dua puluh detik atau lebih"
    "sirene": (0.58, "click"),     # "jangan menunggu sirene"
    "jauhi": (0.68, "swish_up"),   # "Segera jauhi pantai dan tepi sungai"
    "tinggi": (0.85, "ding"),      # "menuju tempat tinggi"
}


def sc_selamat50(img, t, dur, sc):
    ak = D.col(sc.get("accent", "#E5484D"))
    tP, tG, tD, tS, tJ, tT = (V.bt(V_SELAMAT, k, dur) for k in ("pantai", "gempa", "detik", "sirene", "jauhi", "tinggi"))
    x0, y0, x1, y1 = 90, 700, 990, 1560
    up = D.eob(D.seg(t, -0.1, 0.45))
    if up <= 0.01:
        return
    env = D.seg(t, tG, tG + 0.25) * (1 - D.seg(t, tG + 2.2, tG + 3.0))
    jx = 4.0 * math.sin(t * 47.0) * env
    _panel(img, x0, y0, x1, y1, 48, (232, 240, 250), up)
    k = _klip_mulai(img, x0, y0, x1, y1, 48)
    laut = _muka(x0 - 40, 440, 1262, t, 5.0, 140, 1.6, 40)
    _air(img, laut, y1 + 40, AIR, 0.95)
    tanah = [(380 + jx, 1262), (560 + jx, 1222), (598 + jx, 1252), (648 + jx, 1252), (672 + jx, 1218),
             (840 + jx, 966), (x1 + 40 + jx, 1100), (x1 + 40, y1 + 40), (380, y1 + 40)]
    D.poly(img, tanah, HIJAU)
    D.poly(img, [(380 + jx, 1262), (560 + jx, 1222), (598 + jx, 1252), (598 + jx, y1 + 40), (380, y1 + 40)], PASIR)
    D.poly(img, [(598 + jx, 1252), (648 + jx, 1252), (648 + jx, 1300), (598 + jx, 1300)], AIR, 0.95)
    D.polyline(img, tanah[:7], 5, HIJAU_TUA, 0.8)
    if env > 0.05:  # getaran
        for gx0, gy0 in ((460, 1200), (700, 1150), (800, 1030)):
            D.polyline(img, [(gx0 + i * 9, gy0 + (7 if i % 2 else -7) * env) for i in range(8)], 4, D.INK, 0.6 * env)
    _klip_selesai(img, k)
    _bingkai(img, x0, y0, x1, y1, 48, up)
    # label tempat
    ul = D.eo(D.seg(t, tP, tP + 0.5))
    if ul > 0:
        D.txt(img, "pantai", 470, 1300, 28, "SB", D.INK, ul, "ms")
        D.txt(img, "sungai", 623, 1345, 24, "SB", D.INK, ul, "ms")
    # guncangan ~20 detik atau lebih (stopwatch + angka)
    if t > tD - 0.2:
        ud = D.eob(D.seg(t, tD - 0.2, tD + 0.25))
        D.circ(img, 230, 830, 66 * ud, D.PUTIH, 0.95)
        D.ring(img, 230, 830, 66 * ud, 7, D.INK, ud)
        D.rrect(img, 218, 752 - 10 * ud, 242, 764, 4, D.INK, ud)
        prog = D.seg(t, tD, tD + 2.0)
        sud = -math.pi / 2 + 2 * math.pi * prog * 1.5
        D.line(img, 230, 830, 230 + 46 * ud * math.cos(sud), 830 + 46 * ud * math.sin(sud), 6, ak, ud)
        D.circ(img, 230, 830, 8 * ud, ak, ud)
        D.odometer(img, 20, 320, 862, 96, D.INK, ud, "l", "B", prog)
        D.txt(img, "DETIK", 440, 834, 34, "B", D.INK, ud, "ls")
        D.txt(img, "atau lebih", 440, 868, 26, "M", MUTED_TUA, ud, "ls")  # bagian pesan keselamatan: 6.6:1 (MUTED 3.7:1)
    # jangan tunggu sirene
    if t > tS - 0.2:
        us = D.eob(D.seg(t, tS - 0.2, tS + 0.2))
        cx, cy = 668, 812
        D.rrect(img, cx - 42 * us, cy + 18, cx + 42 * us, cy + 38, 6, D.INK, us)
        D.circ(img, cx, cy + 18, 36 * us, (255, 196, 64), us)
        D.rrect(img, cx - 36 * us, cy + 18, cx + 36 * us, cy + 22, 0, (255, 196, 64), us)
        for j in range(2):
            ph = ((t - tS) * 1.2 + j * 0.5) % 1.0
            D.ring(img, cx, cy + 10, 50 + 40 * ph, 4, (255, 170, 40), 0.5 * (1 - ph) * us, 200, 340)
        D.silang(img, cx, cy + 10, 110 * us, ak, 14, D.seg(t, tS + 0.1, tS + 0.4), 0.95)
        V.chip_pop(img, "JANGAN TUNGGU SIRENE", 600, 916, t, tS + 0.15, 26, ak)
    # jauhi pantai & tepi sungai -> ke tempat tinggi
    uj = D.eo(D.seg(t, tJ, tJ + 1.1))
    if uj > 0:
        V.panah_bezier(img, (470, 1228), (560, 1120), (690, 1010), (812, 985), 16, HIJAU_TUA, uj)
        V.chip_pop(img, "JAUHI PANTAI", 250, 1420, t, tJ + 0.1, 26, D.INK)
        V.chip_pop(img, "JAUHI TEPI SUNGAI", 640, 1420, t, tJ + 0.45, 26, D.INK)
    if t > tT - 0.2:
        ut = D.eob(D.seg(t, tT - 0.2, tT + 0.25))
        D.line(img, 846, 968, 846, 968 - 96 * ut, 6, D.INK, ut)
        kib = 4 * math.sin(t * 6)
        D.poly(img, [(846, 872), (906, 888 + kib), (846, 904)], HIJAU_TUA, ut)
        D.centang(img, 900, 1030, 60 * ut, HIJAU_TUA, 12, D.seg(t, tT + 0.15, tT + 0.5), 0.95)
        V.chip_pop(img, "TEMPAT TINGGI", 770, 1100, t, tT + 0.1, 26, HIJAU_TUA)


# ================================================================== rangkuman: tiga penyebab sekaligus
V_TIGA = "tiga50"
B_TIGA = {
    "tiga": (0.21, "blip"),   # "karena tiga hal sekaligus"
    "k1": (0.37, "pop"),      # "gerakan sesar di dasar teluk"
    "k2": (0.51, "pop"),      # "longsoran tanah pantai yang mencair"
    "k3": (0.73, "pop"),      # "dan teluk sempit yang menumpuk gelombang"
    "satu": (0.88, "ding"),   # akhir kalimat: tiga-tiganya sekaligus
}
KARTU3 = [(722, 976), (1006, 1260), (1290, 1544)]
TEKS3 = [("GERAKAN SESAR", "di dasar teluk"), ("LONGSORAN PANTAI", "tanah yang mencair"),
         ("TELUK SEMPIT", "gelombang menumpuk")]


def _ikon_sesar(img, cx, cy, t, u):
    o = 12 * math.sin(t * 2.4)
    D.rrect(img, cx - 84, cy - 70 + o, cx - 2, cy + 70 + o, 10, DARAT, u)
    D.rrect(img, cx + 2, cy - 70 - o, cx + 84, cy + 70 - o, 10, D.terang(DARAT, 0.15), u)
    D.line(img, cx, cy - 80, cx, cy + 80, 6, MERAH, u)
    D.panah(img, [(cx - 43, cy - 30), (cx - 43, cy + 30)], 10, D.INK, u, 0.85)
    D.panah(img, [(cx + 43, cy + 30), (cx + 43, cy - 30)], 10, D.INK, u, 0.85)


def _ikon_longsor(img, cx, cy, t, u):
    ph = (t * 0.55) % 1.0
    D.poly(img, [(cx + 20, cy - 10), (cx + 95, cy - 10), (cx + 95, cy + 80), (cx - 95, cy + 80), (cx - 95, cy + 40)],
           AIR, 0.9 * u)
    D.poly(img, [(cx - 95, cy - 40), (cx - 30, cy - 40), (cx + 60, cy + 80), (cx - 95, cy + 80)], TANAH, u)
    d = 70 * D.eio(ph)
    D.poly(img, [(cx - 55 + d * 0.7, cy - 40 + d * 0.6), (cx - 25 + d * 0.7, cy - 40 + d * 0.6),
                 (cx + 5 + d * 0.7, cy - 5 + d * 0.6), (cx - 40 + d * 0.7, cy - 12 + d * 0.6)], PASIR_TUA, u)
    if ph > 0.55:
        D.polyline(img, D.gel_pts(cx + 20, cx + 95, cy - 12 - 10 * D.seg(ph, 0.55, 0.8), 4, 50, t * 4), 4,
                   D.PUTIH, 0.9 * u)


def _ikon_teluk(img, cx, cy, t, u):
    D.poly(img, [(cx - 90, cy - 75), (cx + 90, cy - 75), (cx + 16, cy + 75), (cx - 16, cy + 75)], AIR, 0.95 * u)
    for m in range(3):
        ph = (t * 0.7 + m / 3) % 1.0
        yy = cy - 70 + 130 * ph
        w = 80 - 64 * ph
        D.line(img, cx - w, yy, cx + w, yy, 5, D.PUTIH, 0.85 * u * (1 - 0.4 * ph))
    D.glow(img, cx, cy + 70, 50, D.PUTIH, 0.3 * u)


IKON3 = (_ikon_sesar, _ikon_longsor, _ikon_teluk)


def sc_tiga50(img, t, dur, sc):
    ak = D.col(sc.get("accent", "#FF6B3D"))
    tT, t1, t2, t3, tS = (V.bt(V_TIGA, k, dur) for k in ("tiga", "k1", "k2", "k3", "satu"))
    muncul = (t1, t2, t3)
    for i, (ya, yb) in enumerate(KARTU3):
        cy = (ya + yb) / 2
        u0 = D.eo(D.seg(t, tT + i * 0.12, tT + i * 0.12 + 0.4))
        if u0 <= 0.01:
            continue
        uk = D.eob(D.seg(t, muncul[i], muncul[i] + 0.45))
        D.rrect_garis(img, 110, ya, 970, yb, 34, D.MUTED, 3, 0.5 * u0 * (1 - uk))
        if uk > 0.01:
            D.rrect(img, 120, ya + 12, 980, yb + 12, 34, D.INK, 0.10 * uk)
            D.rrect(img, 110, ya, 970, yb, 34, D.PUTIH, uk, D.INK, 4)
            D.rrect(img, 232, cy - 100, 432, cy + 100, 24, (240, 236, 229), uk)
            kz = _klip_mulai(img, 232, cy - 100, 432, cy + 100, 24, pad=6)
            IKON3[i](img, 332, cy, t, uk)
            _klip_selesai(img, kz)
            judul, sub = TEKS3[i]
            D.txt(img, judul, 462, cy - 6, 40, "B", D.INK, uk, "ls")
            D.txt(img, sub, 462, cy + 40, 28, "M", D.MUTED, uk, "ls")
            V.ledakan(img, 170, cy, t - muncul[i], ak, seed=i, n=10, jarak=90, dur=0.45)
        den = 1.0 + (0.12 * math.sin((t - tS) * 8) if t > tS else 0.0)
        D.circ(img, 170, cy, 34 * u0 * den, ak, u0)
        D.txt(img, str(i + 1), 170, cy + 2, 40, "B", D.PUTIH, u0, "mm")
    if t > tS:  # tiga-tiganya sekaligus: garis penghubung + cahaya
        us = D.eo(D.seg(t, tS, tS + 0.6))
        c1, c3 = (KARTU3[0][0] + KARTU3[0][1]) / 2, (KARTU3[2][0] + KARTU3[2][1]) / 2
        D.line(img, 170, c1 + 36, 170, c1 + 36 + (c3 - c1 - 72) * us, 8, ak, 0.9)
        for ya, yb in KARTU3:
            D.glow(img, 170, (ya + yb) / 2, 90, ak, 0.25 * us)


VISUALS_EP = {
    V_GESER: sc_geser50,
    V_SESAR: sc_sesar50,
    V_NAIK: sc_naik50,
    V_CAIR: sc_likuefaksi50,
    V_PORSI: sc_porsi50,
    V_TELUK: sc_teluk50,
    V_SELAMAT: sc_selamat50,
    V_TIGA: sc_tiga50,
}
BEAT_TABEL_EP = {
    V_GESER: B_GESER,
    V_SESAR: B_SESAR,
    V_NAIK: B_NAIK,
    V_CAIR: B_CAIR,
    V_PORSI: B_PORSI,
    V_TELUK: B_TELUK,
    V_SELAMAT: B_SELAMAT,
    V_TIGA: B_TIGA,
}
