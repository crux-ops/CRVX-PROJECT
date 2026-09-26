#!/usr/bin/env python3
"""mesin_v11_ep51.py - modul adegan Ep51: kenapa gunung meletus ada petir (petir vulkanik).

Pola sama dengan mesin_v11_ep50.py: tabel beat BERNAMA {nama: (fraksi_durasi, sfx)} -> satu sumber untuk animasi,
SFX, dan dorongan kamera. Fraksi beat diambil dari penyelarasan kata VO NYATA
(`python3 tools/waktu_kata.py ep51_gunung_petir`), jadi gambar muncul tepat saat katanya diucapkan.
Semua gambar = ILUSTRASI skematik (bukan peta/ukuran sebenarnya), tanpa tokoh/wajah; nada hormat tanpa dramatisasi.

Fakta & sumber (dikumpulkan 26-09-2026):
  * Petir vulkanik = "badai kotor": muatan lahir di dalam kolom abu (bukan awan hujan), bisa tanpa es
    (Mather & Harrison - tinjauan "Electrical Charging of Volcanic Plumes"; Wikipedia/Cimarelli & Genareau 2022).
  * Fractoemission: saat magma/batu pecah jadi abu, permukaan baru melepas elektron/ion -> muatan dekat kawah
    (dominan untuk kolom kaya silikat).
  * Triboelektrifikasi: abu saling bertabrakan/bergesekan menukar muatan; dibuktikan di laboratorium
    (Cimarelli dkk. 2014, Geology 42:79-82, doi:10.1130/G34802.1).
  * Muatan es/hidrometeor di kolom tinggi: kolom yang melewati level beku (~-20 C) baru memunculkan petir
    (studi USGS erupsi Bogoslof; es menabrak es seperti di awan badai).
  * Bukti fisik: butiran kaca hasil sambaran (LIVS), 1-100 mikron (Genareau dkk. 2015, Geology 43:319-322,
    doi:10.1130/G36255.1).
  * Hunga Tonga 15 Jan 2022: ~590.000 sambaran terdeteksi jaringan GLD360 (Vaisala) dalam 3 hari; puncak
    2.615 sambaran/menit selama ~5 menit; cincin petir ~250 km (Van Eaton dkk. 2023, GRL,
    doi:10.1029/2022GL102341). Anak Krakatau Des 2018: ~340.000 sambaran dalam seminggu (GLD360 via Reuters).
  * Momen: erupsi menerus Anak Krakatau 4 Sep 23.07 WIB - 6 Sep 00.04 WIB 2026 (~25 jam), kolom ~13-17 km,
    Level III Siaga, radius 3 km (PVMBG/ESDM siaran pers 050.Pers/04/SJI/2026; BRIN via BBC Indonesia).
"""
from __future__ import annotations

import math

from PIL import Image

import diagrams as D
import mesin_v11 as V

# ------------------------------------------------------------------ palet
ABU = (150, 146, 142)
ABU_TUA = (96, 94, 92)
ABU_MUDA = (214, 210, 204)
MAGMA = (255, 122, 46)
MAGMA_TUA = (198, 62, 24)
PIJAR = (255, 196, 92)
BATU = (122, 108, 98)
BATU_TUA = (74, 66, 60)
LANGIT = (214, 232, 255)
ES = (150, 216, 245)
ES_TUA = (46, 150, 205)
KACA = (178, 232, 214)
MERAH = (229, 72, 77)
HIJAU = (31, 181, 122)
PANEL = (238, 233, 224)
# keterangan kecil di latar terang: D.MUTED hanya 3.5-4.25:1 (WCAG teks kecil >= 4.5:1) -> abu tua
MUTED_TUA = D.gelap(D.MUTED, 0.4)

PX0, PY0, PX1, PY1 = 90, 660, 990, 1540   # panel adegan fact (zona sama dengan Ep50)


# ------------------------------------------------------------------ util umum
def _klip_mulai(img, x0, y0, x1, y1, r, pad=180):
    """simpan area panel (+pad); semua yang digambar sesudahnya dipotong ke kotak membulat oleh _klip_selesai."""
    W, H = img.size
    X0, Y0 = max(0, int(D.S(x0 - pad))), max(0, int(D.S(y0 - pad)))
    X1, Y1 = min(W, int(D.S(x1 + pad)) + 1), min(H, int(D.S(y1 + pad)) + 1)
    simpan = img.crop((X0, Y0, X1, Y1))
    m, mx, my = D.rrect_mask(x0, y0, x1, y1, r)
    mask = Image.new("L", simpan.size, 0)
    mask.paste(m, (mx - X0, my - Y0))
    return simpan, mask, X0, Y0, X1, Y1


def _klip_selesai(img, k):
    simpan, mask, X0, Y0, X1, Y1 = k
    simpan.paste(img.crop((X0, Y0, X1, Y1)), (0, 0), mask)
    img.paste(simpan, (X0, Y0))


def _panel(img, x0=PX0, y0=PY0, x1=PX1, y1=PY1, r=48, isi=PANEL, a=1.0):
    D.rrect(img, x0 + 12, y0 + 16, x1 + 12, y1 + 16, r, D.INK, 0.10 * a)
    D.rrect(img, x0, y0, x1, y1, r, isi, a)


def _bingkai(img, x0=PX0, y0=PY0, x1=PX1, y1=PY1, r=48, a=1.0):
    D.rrect_garis(img, x0, y0, x1, y1, r, D.INK, 4, 0.85 * a)


def _petir_jalur(x0, y0, x1, y1, n=8, amp=26.0, seed=0):
    """jalur petir zig-zag deterministik dari (x0,y0) ke (x1,y1)."""
    rr = D.rng("petir51", seed)
    pts = []
    for i in range(n + 1):
        u = i / n
        x = x0 + (x1 - x0) * u + (0.0 if i in (0, n) else rr.uniform(-amp, amp))
        pts.append((x, y0 + (y1 - y0) * u))
    return pts


def _petir(img, x0, y0, x1, y1, warna, a=1.0, lebar=7, seed=0, glow=True):
    if a <= 0.02:
        return
    pts = _petir_jalur(x0, y0, x1, y1, seed=seed)
    if glow:
        D.glow(img, (x0 + x1) / 2, (y0 + y1) / 2, 150, warna, 0.20 * a)
    D.polyline(img, pts, lebar + 8, warna, 0.18 * a)
    D.polyline(img, pts, lebar, D.PUTIH, a)


def _kolom_abu(cx, y_atas, y_bawah, w_atas, w_bawah, t, seed=0, goyang=10.0, n=16):
    """poligon kolom abu yang bergoyang (y_atas < y_bawah)."""
    kiri, kanan = [], []
    for i in range(n + 1):
        u = i / n
        y = y_atas + (y_bawah - y_atas) * u
        w = w_atas + (w_bawah - w_atas) * u
        off = goyang * math.sin(u * 5.2 + t * 1.5 + seed)
        buncit = 1.0 + 0.16 * math.sin(u * 8.0 - t * 2.0 + seed * 1.7)
        kiri.append((cx + off - w * buncit / 2, y))
        kanan.append((cx + off + w * buncit / 2, y))
    return kiri + list(reversed(kanan))


def _gunung(img, cx, y_dasar, lebar, tinggi, warna=BATU, warna_tua=BATU_TUA, kawah=90, a=1.0):
    """siluet kerucut gunung + kawah di puncak."""
    pts = [(cx - lebar / 2, y_dasar), (cx - kawah, y_dasar - tinggi), (cx + kawah, y_dasar - tinggi),
           (cx + lebar / 2, y_dasar)]
    D.poly(img, [(x + 6, y + 10) for x, y in pts], D.INK, 0.10 * a)
    D.poly(img, pts, warna, a)
    D.poly(img, [(cx - kawah, y_dasar - tinggi), (cx + kawah, y_dasar - tinggi),
                 (cx + lebar / 2, y_dasar), (cx + 40, y_dasar)], warna_tua, 0.55 * a)
    return y_dasar - tinggi


def _muatan(img, cx, cy, r, tanda, warna, a=1.0):
    """tanda muatan + / - di dalam lingkaran."""
    D.circ(img, cx, cy, r, warna, a)
    lw = max(3, int(r * 0.26))
    D.line(img, cx - r * 0.45, cy, cx + r * 0.45, cy, lw, D.PUTIH, a)
    if tanda == "+":
        D.line(img, cx, cy - r * 0.45, cx, cy + r * 0.45, lw, D.PUTIH, a)


def _kartu(img, x0, y0, x1, y1, u, r=34, isi=D.PUTIH):
    if u <= 0.01:
        return
    D.rrect(img, x0 + 6, y0 + 10, x1 + 6, y1 + 10, r, D.INK, 0.09 * u)
    D.rrect(img, x0, y0, x1, y1, r, isi, u, D.INK, 4)


# ================================================================== intro: letusan + petir di kolom abu
V_PETIR = "petir51"
B_PETIR = {
    "letus": (0.05, "boom"),    # "Letusan gunung..."
    "petir": (0.22, "zap"),     # "...menyalakan petir"
    "cerah": (0.34, "kilau"),   # "langitnya cerah"
    "cuaca": (0.56, "click"),   # "bukan cuaca yang menyulutnya"
    "listrik": (0.81, "riser"),  # "dari mana listrik sebesar itu"
    "datang": (0.89, "pop"),    # "datang?"
}


def sc_petir51(img, t, dur, sc):
    ak = D.col(sc.get("accent", "#8A5CF6"))
    tL, tP, tC, tW, tE, tD = (V.bt(V_PETIR, k, dur) for k in ("letus", "petir", "cerah", "cuaca", "listrik",
                                                              "datang"))
    _panel(img)
    k = _klip_mulai(img, PX0, PY0, PX1, PY1, 48)
    # langit cerah + matahari (kontras dengan "petir") - latar tampil sejak frame 0
    us = 1.0
    u_pop = D.eo(D.seg(t, 0.10, 0.80))
    D.poly(img, [(PX0 - 40, 1180), (540, 720), (PX1 + 40, 1180), (PX1 + 40, 1620), (PX0 - 40, 1620)],
           D.terang(LANGIT, 0.45), 0.55 * us)
    D.matahari(img, 250, 820, 74, PIJAR, t, 0.95 * u_pop)
    if t > tC:
        uk = D.eo(D.seg(t, tC, tC + 0.5))
        D.chip(img, "LANGIT CERAH", 250, 950, 28, D.INK, D.PUTIH, uk)
        for j in range(4):
            D.kilau4(img, 190 + j * 40, 760 + (j % 2) * 46, 13 - j, PIJAR, 0.7 * uk * (1 - 0.35 * math.sin(t * 3 + j)))
    # tanah + gunung
    D.poly(img, [(PX0 - 40, 1400), (PX1 + 40, 1400), (PX1 + 40, 1620), (PX0 - 40, 1620)], D.terang(BATU, 0.35), us)
    puncak = _gunung(img, 620, 1400, 640, 330, a=us)
    # kolom abu tumbuh dari kawah
    ur = D.eo(D.seg(t, tL, tL + 1.9))
    if ur > 0.01:
        y_atas = 1400 - 330 - 520 * ur
        kolom = _kolom_abu(620, y_atas, puncak + 26, 150 + 90 * ur, 110, t, seed=3)
        D.poly(img, kolom, ABU, 0.30 * ur)
        D.poly(img, _kolom_abu(620, y_atas + 30, puncak + 26, 96 + 56 * ur, 70, t, seed=5), ABU_TUA, 0.22 * ur)
        D.partikel_lapangan(img, t, 34, (440, y_atas - 20, 800, puncak + 20), ABU_TUA, "abu", (4, 13), 0.35 * ur, 26)
        D.glow(img, 620, puncak, 90, MAGMA, 0.55 * ur)
    # petir di dalam kolom (menyala berulang, pertama tepat di kata "petir")
    if t > tP:
        for j in range(4):
            tw = (t - tP) - j * 1.15
            if 0 < tw < 0.42:
                a = (1 - tw / 0.42) * (1.0 if j == 0 else 0.75)
                y0 = 1400 - 330 - 520 * ur + 40 + j * 26
                _petir(img, 620 - 40 + 30 * (j % 2), y0, 620 + 26 - 34 * (j % 2), y0 + 210, ak, a, 7, seed=11 + j)
    # awan hujan dicoret (bukan cuaca)
    if t > tW:
        uw = D.eob(D.seg(t, tW, tW + 0.45))
        cx, cy = 250, 1160
        D.circ(img, cx - 52, cy + 10, 46, ABU_MUDA, 0.95 * uw)
        D.circ(img, cx, cy - 16, 58, ABU_MUDA, 0.95 * uw)
        D.circ(img, cx + 54, cy + 12, 44, ABU_MUDA, 0.95 * uw)
        for j in range(3):
            D.tetes(img, cx - 44 + j * 44, cy + 78 + 10 * math.sin(t * 3 + j), 20, LANGIT, 0.85 * uw)
        D.silang(img, cx, cy + 6, 132, MERAH, 10, uw)
        D.txt(img, "BUKAN CUACA", cx, cy + 140, 30, "B", D.INK, uw, "ms")
    _klip_selesai(img, k)
    _bingkai(img)
    V.stiker(img, "?", 830, 1180, t, tD, 96, ak, rot=-6)
    if t > tE:  # penanda jumlah sumber listrik muncul di akhir intro
        V.chip_pop(img, "ADA 3 SUMBER", 790, 726, t, tE, 30, ak)


# ================================================================== f1: badai kotor (bukan awan hujan)
V_BADAI = "badai51"
B_BADAI = {
    "kolom": (0.17, "whoosh"),   # "di dalam kolom abu letusan"
    "badai": (0.41, "guntur"),   # "menjulukinya badai kotor"
    "air": (0.59, "click"),      # "bukan tetes air"
    "batu": (0.72, "thud"),      # "jutaan butir batu dan abu panas"
    "tabrak": (0.87, "tick"),    # "saling bertabrakan"
}


def sc_badai51(img, t, dur, sc):
    ak = D.col(sc.get("accent", "#4E7BFF"))
    tK, tB, tA, tT, tX = (V.bt(V_BADAI, k, dur) for k in ("kolom", "badai", "air", "batu", "tabrak"))
    _panel(img)
    k = _klip_mulai(img, PX0, PY0, PX1, PY1, 48)
    # kartu KIRI: awan hujan (dicoret)
    u1 = D.eo(D.seg(t, 0.05, 0.65))
    _kartu(img, 120, 700, 520, 1500, u1)
    D.txt(img, "AWAN HUJAN", 320, 770, 34, "B", D.INK, u1, "ms")
    D.txt(img, "tetes air + es", 320, 822, 27, "M", MUTED_TUA, u1, "ms")
    cx, cy = 320, 1010
    D.circ(img, cx - 66, cy + 14, 56, ABU_MUDA, 0.95 * u1)
    D.circ(img, cx, cy - 20, 70, ABU_MUDA, 0.95 * u1)
    D.circ(img, cx + 66, cy + 16, 54, ABU_MUDA, 0.95 * u1)
    if t > tA:
        ua = D.eo(D.seg(t, tA, tA + 0.5))
        for j in range(5):
            yy = 1120 + ((t - tA) * 150 + j * 46) % 210
            D.tetes(img, cx - 96 + j * 48, yy, 22, LANGIT, 0.9 * ua)
        D.silang(img, cx, cy + 30, 170, MERAH, 12, ua)
    # kartu KANAN: kolom abu (betul)
    u2 = D.eo(D.seg(t, tK, tK + 0.7))
    _kartu(img, 560, 700, 960, 1500, u2)
    D.txt(img, "KOLOM ABU", 760, 770, 34, "B", D.INK, u2, "ms")
    D.txt(img, "batu + abu panas", 760, 822, 27, "M", MUTED_TUA, u2, "ms")
    if u2 > 0.01:
        kolom = _kolom_abu(760, 880, 1360, 130, 96, t, seed=7, goyang=7.0)
        D.poly(img, kolom, ABU, 0.35 * u2)
        D.poly(img, _kolom_abu(760, 900, 1360, 84, 62, t, seed=9, goyang=7.0), ABU_TUA, 0.25 * u2)
        rr = D.rng("butir51")
        for j in range(46):
            x = 760 + rr.uniform(-108, 108)
            y = 890 + ((rr.uniform(0, 470) + (t - tK) * (36 + 30 * (j % 5))) % 460)
            r = rr.uniform(4, 12)
            D.circ(img, x, y, r, BATU if j % 3 else BATU_TUA, 0.9 * u2)
        if t > tB:
            ub = D.eo(D.seg(t, tB, tB + 0.4))
            for j in range(3):
                tw = (t - tB) - j * 0.85
                if 0 < tw < 0.38:
                    _petir(img, 760 - 30, 940 + j * 90, 760 + 34, 1120 + j * 90, ak, (1 - tw / 0.38), 6, seed=21 + j)
            D.glow(img, 760, 1080, 200, ak, 0.28 * ub)
        if t > tX:  # percikan tabrakan antarbutir
            ux = D.eo(D.seg(t, tX, tX + 0.45))
            for j in range(5):
                ang = t * 2.2 + j * 1.26
                D.kilau4(img, 760 + 92 * math.cos(ang), 1120 + 150 * math.sin(ang), 15, PIJAR,
                         0.85 * ux * (0.5 + 0.5 * math.sin(t * 7 + j)))
    if t > tX:
        D.chip(img, "BADAI KOTOR", 760, 1430, 30, D.INK, D.PUTIH, D.eob(D.seg(t, tX, tX + 0.4)))
    _klip_selesai(img, k)
    _bingkai(img)


# ================================================================== f2: batu pecah melepas elektron
V_PECAH = "pecah51"
B_PECAH = {
    "kawah": (0.20, "boom"),     # "ada di mulut kawah"
    "abu": (0.40, "desis"),      # "dihancurkan jadi abu halus"
    "pecah": (0.55, "retak"),    # "setiap kali batu pecah"
    "elektron": (0.69, "zap"),   # "permukaan barunya melepas elektron"
    "listrik": (0.88, "ding"),   # "langsung bermuatan listrik"
}
PECAHAN = [(-64, -34, 20), (-14, -60, 24), (40, -30, 18), (-40, 26, 16), (26, 34, 14), (72, 8, 12)]


def sc_pecah51(img, t, dur, sc):
    ak = D.col(sc.get("accent", "#FF8A4C"))
    tK, tA, tP, tE, tL = (V.bt(V_PECAH, k, dur) for k in ("kawah", "abu", "pecah", "elektron", "listrik"))
    _panel(img)
    k = _klip_mulai(img, PX0, PY0, PX1, PY1, 48)
    cx, cy = 540, 1250
    # saluran magma + kawah
    uk = D.eo(D.seg(t, 0.05, 0.7))
    D.poly(img, [(cx - 150, 1500), (cx - 44, cy - 20), (cx + 44, cy - 20), (cx + 150, 1500)], BATU_TUA, 0.9 * uk)
    uy = D.eo(D.seg(t, tK, tK + 0.9)) if t > tK else 0.0
    if uy > 0:
        y0 = 1500 - (1500 - (cy - 10)) * uy
        D.poly(img, [(cx - 150 + (150 - 40) * uy, 1500), (cx - 40, y0), (cx + 40, y0),
                     (cx + 150 - (150 - 40) * uy, 1500)], MAGMA, 0.95 * uy)
        D.glow(img, cx, cy, 120, MAGMA, 0.5 * uy * (0.7 + 0.3 * math.sin(t * 5)))
    # bongkahan batu di mulut kawah -> pecah
    up = D.eo(D.seg(t, tP - 0.15, tP + 0.5)) if t > tP - 0.15 else 0.0
    r0 = 92.0
    if t < tP:
        D.poly(img, [(cx + r0 * math.cos(a), cy - 60 + r0 * 0.8 * math.sin(a))
                     for a in [i * 2 * math.pi / 7 for i in range(7)]], BATU, uk)
        D.polyline(img, [(cx - 30, cy - 96), (cx + 4, cy - 62), (cx - 18, cy - 26)], 5, BATU_TUA, 0.8 * uk)
    else:
        for i, (dx, dy, r) in enumerate(PECAHAN):
            u = D.eob(D.clamp(up + i * 0.05), 1.4)
            x, y = cx + dx * (0.35 + 1.5 * u), cy - 60 + dy * (0.35 + 1.5 * u)
            pts = [(x + r * math.cos(a + i), y + r * 0.82 * math.sin(a + i))
                   for a in [j * 2 * math.pi / 5 for j in range(5)]]
            D.poly(img, pts, BATU if i % 2 else BATU_TUA, 0.98)
            V.ledakan(img, cx, cy - 60, t - tP - i * 0.03, MAGMA, seed=i, n=6, jarak=70, dur=0.4)
    # abu halus naik
    if t > tA:
        ua = D.eo(D.seg(t, tA, tA + 0.6))
        D.poly(img, _kolom_abu(cx, cy - 330, cy - 40, 120, 70, t, seed=13, goyang=6.0), ABU, 0.28 * ua)
        D.partikel_lapangan(img, t, 40, (cx - 130, cy - 340, cx + 130, cy - 20), ABU_TUA, "abu51", (3, 10),
                            0.42 * ua, 40)
    # elektron / muatan lepas dari permukaan baru
    if t > tE:
        ue = D.eo(D.seg(t, tE, tE + 0.55))
        for j, (dx, dy, r) in enumerate(PECAHAN):
            x, y = cx + dx * 1.85, cy - 60 + dy * 1.85
            _muatan(img, x + 34 * math.cos(t * 2 + j), y - 30 * math.sin(t * 1.7 + j), 20,
                    "+" if j % 2 else "-", ak if j % 2 else BATU_TUA, ue)
            D.line(img, x, y, x + 30 * math.cos(t * 2 + j), y - 28 * math.sin(t * 1.7 + j), 3, ak, 0.5 * ue)
    _klip_selesai(img, k)
    _bingkai(img)
    if t > tL:
        V.chip_pop(img, "MUATAN LISTRIK", 540, 730, t, tL, 30, ak)


# ================================================================== f3: abu bergesekan (triboelektrik)
V_GESEK = "gesek51"
B_GESEK = {
    "gesekan": (0.16, "swish"),   # "Sumber kedua adalah gesekan"
    "tabrak": (0.32, "click"),    # "saling bertabrakan"
    "balon": (0.54, "pop"),       # "persis balon"
    "rambut": (0.62, "swish"),    # "yang digosok ke rambut"
    "muatan": (0.88, "riser"),    # "semakin besar muatannya"
}
BUTIR = [(-170, -60, 46), (-40, -120, 38), (90, -70, 52), (180, 30, 34), (20, 60, 44), (-110, 90, 40)]


def sc_gesek51(img, t, dur, sc):
    ak = D.col(sc.get("accent", "#F5A623"))
    tG, tT, tB, tR, tM = (V.bt(V_GESEK, k, dur) for k in ("gesekan", "tabrak", "balon", "rambut", "muatan"))
    _panel(img)
    k = _klip_mulai(img, PX0, PY0, PX1, PY1, 48)
    cx, cy = 540, 1050
    # pusaran butir abu
    ug = D.eo(D.seg(t, 0.05, 0.7))
    for j in range(3):
        D.ring(img, cx, cy, 170 + j * 62, 3, ABU, 0.28 * ug)
    if t > tT:
        ut = D.eo(D.seg(t, tT, tT + 0.5))
        for i, (dx, dy, r) in enumerate(BUTIR):
            ang = t * 0.9 + i * 1.05
            x = cx + dx * math.cos(ang * 0.35) + 16 * math.sin(t * 1.6 + i)
            y = cy + dy + 14 * math.cos(t * 1.3 + i * 2)
            D.circ(img, x + 6, y + 8, r, D.INK, 0.10 * ut)
            D.circ(img, x, y, r, BATU if i % 2 else BATU_TUA, ut)
            D.circ(img, x - r * 0.3, y - r * 0.34, r * 0.26, D.terang(BATU, 0.4), 0.7 * ut)
            _muatan(img, x + r * 0.72, y - r * 0.72, 17, "+" if i % 2 else "-", ak if i % 2 else BATU_TUA,
                    0.95 * ut)
        for j in range(4):  # percikan tabrakan
            ang = t * 2.6 + j * 1.57
            D.kilau4(img, cx + 150 * math.cos(ang), cy + 120 * math.sin(ang), 16, PIJAR,
                     0.8 * ut * (0.4 + 0.6 * abs(math.sin(t * 6 + j))))
    # kartu analogi: balon digosok ke rambut
    if t > tB:
        ub = D.eob(D.seg(t, tB, tB + 0.45))
        _kartu(img, 130, 1290, 620, 1490, ub)
        bx, by = 250, 1380
        D.circ(img, bx, by, 52 * ub, MERAH, 0.9)
        D.circ(img, bx - 16, by - 18, 14, D.terang(MERAH, 0.5), 0.8 * ub)
        for j in range(7):  # helaian rambut
            x0 = 360 + j * 22
            D.polyline(img, [(x0, 1440), (x0 + 12 * math.sin(t * 3 + j), 1360),
                             (x0 + 22 * math.sin(t * 2.4 + j), 1310)], 5, BATU_TUA, 0.85 * ub)
        D.panah(img, [(330, 1380), (420, 1380)], 12, D.INK, ub, 0.9)
        D.txt(img, "GESEK = MUATAN", 380, 1330, 28, "B", D.INK, ub, "mm")
        if t > tR:
            ur = D.eo(D.seg(t, tR, tR + 0.4))
            for j in range(4):
                D.kilau4(img, bx + 44 * math.cos(j * 1.6 + t), by + 44 * math.sin(j * 1.6 + t), 13, PIJAR, 0.8 * ur)
    # meter muatan naik
    if t > tM:
        um = D.eo(D.seg(t, tM, tM + 0.9))
        x0, x1, y = 660, 950, 1390
        D.rrect(img, x0, y - 26, x1, y + 26, 26, D.campur(PANEL, D.INK, 0.10), um)
        D.rrect(img, x0, y - 26, x0 + (x1 - x0) * um, y + 26, 26, ak, um)
        D.txt(img, "MUATAN", x0, y - 56, 28, "B", D.INK, um, "ls")
        D.txt(img, "MUATAN MAKIN BESAR", x0, y + 66, 24, "M", MUTED_TUA, um, "ls")
    _klip_selesai(img, k)
    _bingkai(img)


# ================================================================== f4: es di puncak kolom
V_ES = "es51"
B_ES = {
    "tinggi": (0.13, "riser"),   # "baru muncul di ketinggian"
    "beku": (0.38, "kilau"),     # "uap air membeku"
    "tabrak": (0.50, "click"),   # "butiran es saling bertabrakan"
    "badai": (0.62, "whoosh"),   # "seperti di awan badai"
    "julang": (0.84, "swish_up"),  # "menjulang"
    "km": (0.92, "ding"),        # "sampai lima belas kilometer"
}
KM_MAKS = 20.0
YA, YB = 730, 1490    # y atas (KM_MAKS) -> y bawah (0 km)


def _y_km(km):
    return YB - (YB - YA) * (km / KM_MAKS)


def sc_es51(img, t, dur, sc):
    ak = D.col(sc.get("accent", "#3FC0E8"))
    tT, tB, tX, tW, tJ, tK = (V.bt(V_ES, k, dur) for k in ("tinggi", "beku", "tabrak", "badai", "julang", "km"))
    _panel(img)
    k = _klip_mulai(img, PX0, PY0, PX1, PY1, 48)
    x0, x1 = 190, 900
    ut = D.eo(D.seg(t, 0.05, 0.7))
    # sumbu ketinggian
    D.line(img, x0, YA, x0, YB, 5, D.INK, 0.35 * ut)
    for km in range(0, 21, 5):
        y = _y_km(km)
        D.line(img, x0 - 16, y, x0 + 16, y, 4, D.INK, 0.3 * ut)
        D.txt(img, f"{km} km", x0 - 26, y, 26, "M", MUTED_TUA, ut, "rm")
    # gradien suhu: hangat di bawah, dingin di atas
    for i in range(20):
        u = i / 20
        y = YA + (YB - YA) * u
        D.rrect(img, x0 + 8, y, x0 + 40, y + (YB - YA) / 20 + 2, 0, D.campur(LANGIT, PIJAR, u * 0.8), 0.55 * ut)
    # garis titik beku
    ybeku = _y_km(7.0)
    if t > tB:
        ub = D.eo(D.seg(t, tB, tB + 0.6))
        D.line(img, x0 + 46, ybeku, x1, ybeku, 5, ES_TUA, 0.9 * ub)
        D.txt(img, "UDARA DI BAWAH TITIK BEKU", x0 + 56, ybeku - 22, 27, "B", ES_TUA, ub, "ls")
    # kolom abu: tinggi tumbuh (Anak Krakatau ~15 km di akhir adegan)
    km_now = 6.0 + 11.0 * (D.eo(D.seg(t, tT, tT + 1.2)) if t < tJ else D.eo(D.seg(t, tJ, tJ + 1.6)))
    km_now = min(km_now, 17.0) if t >= tJ else min(km_now, 9.0)
    u = D.eo(D.seg(t, tT, tT + 1.4))
    if u > 0.01:
        cx = 640
        y_atas = _y_km(km_now)
        D.poly(img, _kolom_abu(cx, y_atas, YB - 10, 190, 110, t, seed=17, goyang=8.0), ABU, 0.32 * u)
        D.poly(img, _kolom_abu(cx, y_atas + 24, YB - 10, 120, 70, t, seed=19, goyang=8.0), ABU_TUA, 0.24 * u)
        # payung kolom di puncak
        D.poly(img, [(cx - 240, y_atas + 26), (cx - 120, y_atas - 34), (cx + 130, y_atas - 40),
                     (cx + 250, y_atas + 20), (cx, y_atas + 60)], ABU, 0.30 * u)
        # es di atas garis beku
        if t > tX:
            ux = D.eo(D.seg(t, tX, tX + 0.5))
            rr = D.rng("es51")
            for j in range(26):
                xx = cx + rr.uniform(-170, 170)
                yy = y_atas + rr.uniform(-30, max(10.0, ybeku - y_atas + 10))
                if yy > ybeku - 6:
                    continue
                D.salju(img, xx + 8 * math.sin(t * 1.4 + j), yy + 6 * math.cos(t * 1.1 + j), rr.uniform(9, 17),
                        ES_TUA, t * 30 + j * 20, 0.9 * ux)
            for j in range(4):
                ang = t * 2.0 + j * 1.57
                D.kilau4(img, cx + 130 * math.cos(ang), (y_atas + ybeku) / 2 + 70 * math.sin(ang), 15, ES,
                         0.85 * ux * (0.4 + 0.6 * abs(math.sin(t * 6 + j))))
        if t > tW:
            uw = D.eo(D.seg(t, tW, tW + 0.6))
            for j in range(2):
                tw = (t - tW) - j * 0.9
                if 0 < tw < 0.4:
                    _petir(img, cx - 40, y_atas + 40, cx + 30, ybeku - 20, ak, (1 - tw / 0.4) * uw, 6, seed=31 + j)
    _klip_selesai(img, k)
    _bingkai(img)
    if t > tK:
        uk = D.eob(D.seg(t, tK, tK + 0.45))
        y15 = _y_km(15.0)
        D.line(img, x1 - 190, y15, x1 + 6, y15, 4, MERAH, 0.9 * uk)
        D.chip(img, "ANAK KRAKATAU · 15 KM", x1 - 96, y15 - 52, 28, MERAH, D.PUTIH, uk)


# ================================================================== f5: butiran kaca (bukti fisik)
V_KACA = "kaca51"
B_KACA = {
    "tanah": (0.10, "thud"),     # "Buktinya ada di tanah"
    "petir": (0.19, "zap"),      # "Sambaran petir"
    "kaca": (0.34, "kilau"),     # "butiran kaca bundar"
    "rambut": (0.51, "swish"),   # "lebih tipis dari sehelai rambut"
    "jatuh": (0.62, "whoosh"),   # "jatuh bersama hujan abu"
    "sidik": (0.75, "ding"),     # "sidik jari letusan"
}


def sc_kaca51(img, t, dur, sc):
    ak = D.col(sc.get("accent", "#22C1A6"))
    tT, tP, tK, tR, tJ, tS = (V.bt(V_KACA, k, dur) for k in ("tanah", "petir", "kaca", "rambut", "jatuh",
                                                             "sidik"))
    _panel(img)
    k = _klip_mulai(img, PX0, PY0, PX1, PY1, 48)
    ut = D.eo(D.seg(t, 0.05, 0.7))
    # tanah + abu jatuh di kiri
    D.poly(img, [(PX0 - 40, 1330), (PX1 + 40, 1330), (PX1 + 40, 1620), (PX0 - 40, 1620)],
           D.terang(BATU, 0.4), ut)
    D.polyline(img, D.gel_pts(PX0 - 40, PX1 + 40, 1330, 8, 220, 0.4), 6, BATU_TUA, 0.6 * ut)
    if t > tJ:
        uj = D.eo(D.seg(t, tJ, tJ + 0.6))
        rr = D.rng("hujanabu51")
        for j in range(40):
            x = rr.uniform(PX0 + 20, 470)
            y = 700 + ((rr.uniform(0, 620) + (t - tJ) * 190) % 620)
            D.circ(img, x, y, rr.uniform(3, 9), ABU_TUA, 0.7 * uj)
    # butiran abu di tanah + satu yang disorot
    for j, (bx, by) in enumerate([(180, 1400), (250, 1440), (330, 1390), (410, 1450), (150, 1470), (300, 1490)]):
        D.circ(img, bx, by, 13 if j else 17, BATU_TUA, ut)
    if t > tT:
        ua = D.eo(D.seg(t, tT, tT + 0.4))
        D.ring(img, 180, 1400, 34 + 8 * math.sin(t * 3), 5, ak, 0.85 * ua)
    # garis pembesar ke lingkaran besar di kanan
    if t > tP:
        up = D.eo(D.seg(t, tP, tP + 0.5))
        D.line(img, 196, 1392, 560, 1110, 4, ak, 0.55 * up)
        D.line(img, 196, 1412, 560, 1290, 4, ak, 0.55 * up)
    cx, cy, R = 700, 1110, 130
    if t > tK:
        uk = D.eob(D.seg(t, tK, tK + 0.55), 1.4)
        D.circ(img, cx + 8, cy + 12, R * uk, D.INK, 0.12 * uk)
        D.circ(img, cx, cy, R * uk, KACA, 0.95 * uk)
        D.circ(img, cx - R * 0.34, cy - R * 0.38, R * 0.26, D.PUTIH, 0.85 * uk)
        D.ring(img, cx, cy, R * 0.86, 6, D.terang(ak, 0.25), 0.5 * uk)
        D.glow(img, cx, cy, R * 1.7, ak, 0.22 * uk)
        D.txt(img, "BUTIRAN KACA", cx, cy + R + 62, 32, "B", D.INK, uk, "ms")
    # pembanding ukuran: rambut vs butiran
    if t > tR:
        ur = D.eo(D.seg(t, tR, tR + 0.6))
        y = 1408
        D.line(img, 560, y, 900, y, 8, BATU_TUA, 0.9 * ur)
        D.txt(img, "RAMBUT  ~70 µm", 730, y - 34, 26, "B", D.INK, ur, "ms")
        D.circ(img, 730, y + 62, 22 * ur, KACA, ur)
        D.txt(img, "BUTIRAN  ~50 µm", 730, y + 112, 26, "B", D.INK, ur, "ms")
    _klip_selesai(img, k)
    _bingkai(img)
    if t > tS:
        V.chip_pop(img, "SIDIK JARI LETUSAN", 540, 730, t, tS, 30, ak)


# ================================================================== f6: rekor sambaran
V_REKOR = "rekor51"
B_REKOR = {
    "letusan": (0.16, "boom"),   # "Letusan Hunga Tonga"
    "hunga": (0.18, "thud"),     # "Hunga Tonga tahun dua ribu dua puluh dua"
    "memicu": (0.29, "riser"),   # "memicu hampir..."
    "sambaran": (0.45, "zap"),   # "...ribu sambaran"
    "hari": (0.55, "ding"),      # "dalam tiga hari"
    "anak": (0.63, "thud"),      # "Anak Krakatau tahun dua ribu delapan belas"
    "minggu": (0.92, "ding"),    # "dalam seminggu"
}
BATAS = 600000.0


def sc_rekor51(img, t, dur, sc):
    ak = D.col(sc.get("accent", "#FF6E6E"))
    tL, tH, tM, tS, tD, tA, tG = (V.bt(V_REKOR, k, dur) for k in ("letusan", "hunga", "memicu", "sambaran",
                                                                  "hari", "anak", "minggu"))
    _panel(img)
    k = _klip_mulai(img, PX0, PY0, PX1, PY1, 48)
    # odometer besar
    uo = D.eo(D.seg(t, tM, tD + 0.4))
    ua = D.eo(D.seg(t, 0.05, 0.6))
    if ua > 0:
        D.odometer(img, 590000, 540, 900, 132, D.INK, ua, "m", "B", uo, 0, "")
        D.txt(img, "SAMBARAN PETIR · HUNGA TONGA 2022", 540, 990, 30, "B", D.INK, ua, "ms")
        D.txt(img, "terdeteksi jaringan petir global (GLD360) dalam 3 hari", 540, 1036, 26, "M", MUTED_TUA,
              ua, "ms")
    if t > tS:
        for j in range(3):
            tw = (t - tS) - j * 0.5
            if 0 < tw < 0.34:
                _petir(img, 250 + j * 40, 760, 320 + j * 40, 880, ak, (1 - tw / 0.34), 6, seed=41 + j)
                _petir(img, 800 - j * 30, 780, 740 - j * 30, 900, ak, (1 - tw / 0.34) * 0.8, 6, seed=51 + j)
    # dua batang pembanding
    x0, x1 = 200, 940
    for i, (nama, nilai, ket, tt) in enumerate([
            ("HUNGA TONGA 2022", 590000, "3 hari", tM),
            ("ANAK KRAKATAU 2018", 340000, "1 minggu", tA)]):
        y = 1170 + i * 150
        if t < tt:
            continue
        u = D.eo(D.seg(t, tt, tt + 1.0))
        D.txt(img, nama, x0, y - 34, 30, "B", D.INK, u, "ls")
        D.rrect(img, x0, y, x1, y + 58, 29, D.campur(PANEL, D.INK, 0.10), u)
        D.rrect(img, x0, y, x0 + (x1 - x0) * (nilai / BATAS) * u, y + 58, 29, ak if i == 0 else BATU, u)
        lebar = (x1 - x0) * (nilai / BATAS) * u
        D.txt(img, D.format_id(nilai) + f"  ·  {ket}", x0 + lebar - 16, y + 29, 27, "B",
              D.teks_terbaca(ak if i == 0 else BATU), u, "rm")
    _klip_selesai(img, k)
    _bingkai(img)
    if t > tG:
        V.chip_pop(img, "REKOR TEREKAM", 540, 730, t, tG, 30, ak)


# ================================================================== rangkuman: tiga sumber listrik
V_TIGA = "tiga51"
B_TIGA = {
    "tiga": (0.07, "pop"),        # "ada tiga sumber listrik"
    "pecah": (0.23, "retak"),     # "batu yang pecah"
    "gesek": (0.33, "swish"),     # "abu yang bergesekan"
    "tabrak": (0.43, "click"),    # "es yang bertabrakan"
    "petir": (0.64, "zap"),       # "memakai petir"
    "pantau": (0.69, "sonar"),    # "memantau erupsi dari kejauhan"
}
KARTU3 = [(700, 900), (930, 1130), (1160, 1360)]
TEKS3 = [("BATU PECAH", "fractoemission · dekat kawah"),
         ("ABU BERGESEKAN", "tabrakan antarbutir abu"),
         ("ES BERTABRAKAN", "di atas titik beku")]


def _ikon_pecah(img, cx, cy, t, u):
    for i, (dx, dy, r) in enumerate([(-26, -18, 22), (16, -22, 18), (-6, 22, 20), (30, 16, 14)]):
        j = 10 * math.sin(t * 3 + i)
        pts = [(cx + dx * 1.3 + j + r * math.cos(a + i), cy + dy * 1.3 + r * 0.8 * math.sin(a + i))
               for a in [m * 2 * math.pi / 5 for m in range(5)]]
        D.poly(img, pts, BATU if i % 2 else BATU_TUA, u)
    D.kilau4(img, cx, cy, 15, MAGMA, 0.85 * u, rot=t * 30)


def _ikon_gesek(img, cx, cy, t, u):
    for i in range(4):
        ang = t * 1.6 + i * 1.57
        x, y = cx + 30 * math.cos(ang), cy + 26 * math.sin(ang)
        D.circ(img, x, y, 20, BATU if i % 2 else BATU_TUA, u)
        _muatan(img, x + 14, y - 14, 11, "+" if i % 2 else "-", MAGMA if i % 2 else BATU_TUA, u)
    D.kilau4(img, cx, cy, 13, PIJAR, 0.9 * u * (0.5 + 0.5 * math.sin(t * 6)), rot=t * 40)


def _ikon_es(img, cx, cy, t, u):
    D.salju(img, cx - 24, cy - 8, 26, ES_TUA, t * 25, u)
    D.salju(img, cx + 26, cy + 10, 20, ES_TUA, -t * 20, u)
    D.kilau4(img, cx, cy - 34, 13, ES, 0.9 * u, rot=t * 35)


IKON3 = (_ikon_pecah, _ikon_gesek, _ikon_es)


def sc_tiga51(img, t, dur, sc):
    ak = D.col(sc.get("accent", "#9B7BFF"))
    tT, t1, t2, t3, tP, tM = (V.bt(V_TIGA, k, dur) for k in ("tiga", "pecah", "gesek", "tabrak", "petir",
                                                             "pantau"))
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
            D.txt(img, sub, 462, cy + 40, 27, "M", MUTED_TUA, uk, "ls")
            V.ledakan(img, 170, cy, t - muncul[i], ak, seed=i, n=10, jarak=90, dur=0.45)
        den = 1.0 + (0.12 * math.sin((t - tM) * 8) if t > tM else 0.0)
        D.circ(img, 170, cy, 34 * u0 * den, ak, u0)
        D.txt(img, str(i + 1), 170, cy + 2, 40, "B", D.PUTIH, u0, "mm")
    if t > tM:  # ketiganya menyatu jadi alat pantau
        us = D.eo(D.seg(t, tM, tM + 0.6))
        c1, c3 = (KARTU3[0][0] + KARTU3[0][1]) / 2, (KARTU3[2][0] + KARTU3[2][1]) / 2
        D.line(img, 170, c1 + 36, 170, c1 + 36 + (c3 - c1 - 72) * us, 8, ak, 0.9)
        for ya, yb in KARTU3:
            D.glow(img, 170, (ya + yb) / 2, 90, ak, 0.25 * us)
        for j in range(3):  # gelombang pantauan
            ph = ((t - tM) * 0.7 + j / 3) % 1.0
            D.ring(img, 540, 1470, 40 + 240 * ph, 6, ak, 0.5 * (1 - ph) * us)
    if t > tP:
        up = D.eob(D.seg(t, tP, tP + 0.45))
        D.circ(img, 540, 1470, 30 * up, D.INK, 0.9 * up)
        D.circ(img, 540, 1470, 12 * up, ak, up)


VISUALS_EP = {
    V_PETIR: sc_petir51,
    V_BADAI: sc_badai51,
    V_PECAH: sc_pecah51,
    V_GESEK: sc_gesek51,
    V_ES: sc_es51,
    V_KACA: sc_kaca51,
    V_REKOR: sc_rekor51,
    V_TIGA: sc_tiga51,
}
BEAT_TABEL_EP = {
    V_PETIR: B_PETIR,
    V_BADAI: B_BADAI,
    V_PECAH: B_PECAH,
    V_GESEK: B_GESEK,
    V_ES: B_ES,
    V_KACA: B_KACA,
    V_REKOR: B_REKOR,
    V_TIGA: B_TIGA,
}
