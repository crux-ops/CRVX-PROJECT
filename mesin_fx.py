#!/usr/bin/env python3
"""mesin_fx.py - lapisan FX 2026 bersama (Shorts + Long). numpy + PIL saja, deterministik.

Finishing per frame : bloom ADAPTIF dua skala -> grade (preset krem/sinema/netral: kurva S + split-toning)
                      -> lensa (aberasi kromatik radial tipis) -> vinyet -> grain film deterministik.
Gerak              : nois (derau 1D organik), spring, zoom_blur, blur_arah, kamera (drift + dorongan beat).
Material           : kaca_cair (Liquid Glass), bayang lembut ter-cache, kilau, bokeh 2.5D, mesh_latar, odometer.
Transisi fase      : 14 jenis (zoomthru, tinta, cahaya, speed, glint, split, zoom, bands, iris, rise, punch,
                      slide, glitch, whip). transisi(img, jenis, fase, u, aksen): fase 'keluar' (akhir adegan A)
                      atau 'masuk' (awal adegan B); intensitas memuncak TEPAT di titik potong -> potongan
                      tersembunyi, dan di ujung fase efek = identitas (tanpa loncatan).
Saklar             : KT_FX=0 (matikan semua FX), KT_BLOOM (pengali kekuatan bloom, bawaan 1.0).
Jebakan (dicatat)  : radius GaussianBlur harus float biasa; ImageChops.screen lambat (pakai add/blend);
                      jendela odometer >= tinggi glyph (~0.87*fsz Poppins-Bold); ukuran font int; dash int.
Selftest           : python3 mesin_fx.py
"""
from __future__ import annotations

import math
import os
import sys
import time
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import diagrams as D  # noqa: E402

AKTIF = os.environ.get("KT_FX", "1") != "0"
BLOOM = float(os.environ.get("KT_BLOOM", "1.0") or 1.0)
BIL = Image.BILINEAR


# ============================================================================ derau & pegas
def _h(i, seed):
    v = math.sin(i * 12.9898 + seed * 78.233) * 43758.5453
    return v - math.floor(v)


def nois(x, seed=0, oktaf=2):
    """derau nilai 1D halus (-1..1), untuk kamera genggam organik (bukan sinus)."""
    tot, amp, fr, norm = 0.0, 1.0, 1.0, 0.0
    for o in range(oktaf):
        xx = x * fr
        i = math.floor(xx)
        f = xx - i
        a, b = _h(i, seed + o * 17) * 2 - 1, _h(i + 1, seed + o * 17) * 2 - 1
        u = f * f * f * (f * (f * 6 - 15) + 10)
        tot += amp * (a + (b - a) * u)
        norm += amp
        amp *= 0.5
        fr *= 2.0
    return tot / norm


def spring(t, zeta=0.45, omega=12.0):
    return D.pegas(t, zeta, omega)


# ============================================================================ finishing
PRESET = {
    "krem": dict(bloom=0.20, s=0.07, bayang=(0.006, 0.002, -0.004), sorot=(0.008, 0.003, -0.008), sat=1.05,
                 vin=0.09, grain=1.5, ca=0.0011),
    "sinema": dict(bloom=0.34, s=0.12, bayang=(-0.012, 0.010, 0.030), sorot=(0.030, 0.010, -0.020), sat=1.08,
                   vin=0.30, grain=3.0, ca=0.0016),
    "netral": dict(bloom=0.15, s=0.03, bayang=(0, 0, 0), sorot=(0, 0, 0), sat=1.0, vin=0.05, grain=1.0, ca=0.0),
}


@lru_cache(maxsize=8)
def _lut(preset):
    p = PRESET[preset]
    x = np.linspace(0, 1, 256)
    y = x + p["s"] * 2 * (x * x * (3 - 2 * x) - x)
    out = []
    for c in range(3):
        yc = y + (1 - y) ** 2 * p["bayang"][c] + y ** 2 * p["sorot"][c]
        out += list(np.clip(np.round(yc * 255), 0, 255).astype(int))
    return out


def bloom(img, kuat=0.2):
    """bloom adaptif: adegan terang -> ambang naik & kekuatan turun (tidak membakar krem/putih)."""
    W, H = img.size
    sw, sh = max(8, W // 4), max(8, H // 4)
    small = img.resize((sw, sh), BIL)
    a = np.asarray(small, np.float32) / 255.0
    lum = a @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    m = float(lum.mean())
    p90 = float(np.percentile(lum, 90))
    terang = float((lum > 0.82).mean())
    # ambang naik mengikuti rata-rata DAN persentil-90 (frame setengah krem/setengah warna tetap aman);
    # kekuatan turun sebanding porsi piksel terang -> latar krem/langit terang tidak pernah terbakar
    thr = max(0.70 + 0.25 * m, min(0.97, p90 - 0.01))
    k = kuat * BLOOM * max(0.0, 1.12 - m) ** 1.4 * (1 - terang) ** 2
    if k < 0.004:
        return img
    b = (np.clip((lum - thr) / (1 - thr), 0, 1)[..., None] * a * 255).astype(np.uint8)
    bi = Image.fromarray(b, "RGB")
    b1 = bi.filter(ImageFilter.GaussianBlur(float(sw * 0.010)))
    b2 = bi.resize((max(4, sw // 4), max(4, sh // 4)), BIL).filter(ImageFilter.GaussianBlur(float(sw * 0.012)))
    mix = Image.blend(b1, b2.resize((sw, sh), BIL), 0.5)
    g = min(6.0, k * 4.0)
    mix = mix.point([min(255, int(v * g)) for v in range(256)] * 3)
    return ImageChops.add(img, mix.resize((W, H), BIL))


@lru_cache(maxsize=8)
def _radial(W, H, mulai=0.35, pw=2.0):
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xs - W / 2) / (W / 2)) ** 2 + ((ys - H / 2) / (H / 2)) ** 2) / math.sqrt(2)
    m = np.clip((r - mulai) / (1 - mulai), 0, 1) ** pw
    return Image.fromarray((m * 255).astype(np.uint8), "L")


def lensa(img, ca=0.0012):
    """aberasi kromatik radial tipis (hanya di pinggir; tengah tetap tajam)."""
    if ca <= 0:
        return img
    W, H = img.size
    dx, dy = max(1, int(round(W * ca))), max(1, int(round(H * ca)))
    r, g, b = img.split()
    r2 = r.resize((W + 2 * dx, H + 2 * dy), BIL).crop((dx, dy, dx + W, dy + H))
    b3 = b.copy()
    b3.paste(b.resize((W - 2 * dx, H - 2 * dy), BIL), (dx, dy))
    return Image.composite(Image.merge("RGB", (r2, g, b3)), img, _radial(W, H))


@lru_cache(maxsize=8)
def _vin(W, H, kuat):
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xs - W / 2) / (W / 2)) ** 2 * 0.9 + ((ys - H / 2) / (H / 2)) ** 2 * 0.75)
    u = np.clip((r - 0.55) / 0.75, 0, 1)
    v = 1 - kuat * u * u * (3 - 2 * u)
    a = (v * 255).astype(np.uint8)
    return Image.fromarray(np.dstack([a, a, a]), "RGB")


def vinyet(img, kuat=0.1):
    if kuat <= 0:
        return img
    return ImageChops.multiply(img, _vin(img.size[0], img.size[1], round(kuat, 3)))


@lru_cache(maxsize=4)
def _grain_tex(W, H):
    return np.random.default_rng(20260925).normal(0, 1, (H + 64, W + 64)).astype(np.float32)


def grain(img, fi, sigma=1.5):
    """grain film deterministik per frame (luma), juga berfungsi sebagai dither anti-banding."""
    if sigma <= 0:
        return img
    W, H = img.size
    tex = _grain_tex(W, H)
    r = np.random.default_rng(int(fi) * 7919 + 13)
    ox, oy = (int(v) for v in r.integers(0, 64, 2))
    n = np.round(tex[oy:oy + H, ox:ox + W] * sigma).astype(np.int16)
    a = np.asarray(img, np.int16) + n[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


def finishing(img, preset="krem", fi=0, ctx=None):
    if not AKTIF:
        return img
    p = PRESET.get(preset, PRESET["krem"])
    img = bloom(img, p["bloom"])
    img = img.point(_lut(preset))
    if abs(p["sat"] - 1) > 1e-3:
        img = ImageEnhance.Color(img).enhance(p["sat"])
    img = lensa(img, p["ca"])
    img = vinyet(img, p["vin"])
    return grain(img, fi, p["grain"])


# ============================================================================ gerak
def affine(img, z=1.0, rot=0.0, dx=0.0, dy=0.0, cx=None, cy=None, resample=BIL, isi=None):
    """skala z & rotasi rot (derajat) terhadap (cx,cy), lalu geser (dx,dy) piksel."""
    W, H = img.size
    cx = W / 2 if cx is None else cx
    cy = H / 2 if cy is None else cy
    th = math.radians(rot)
    c, s = math.cos(th) / z, math.sin(th) / z
    a, b, d, e = c, s, -s, c
    cc = cx - a * (cx + dx) - b * (cy + dy)
    f = cy - d * (cx + dx) - e * (cy + dy)
    kw = {"fillcolor": isi} if isi is not None else {}
    return img.transform((W, H), Image.AFFINE, (a, b, cc, d, e, f), resample, **kw)


def zoom_blur(img, kuat=0.2, n=None, cx=None, cy=None):
    """blur zoom radial (rata-rata beberapa salinan berskala) di resolusi 1/2.
    Jumlah salinan mengikuti kekuatan agar tidak tampak bertingkat (salinan hantu)."""
    if kuat <= 0.003:
        return img
    W, H = img.size
    n = n or int(D.clamp(kuat * 50, 4, 16))
    h = img.resize((W // 2, H // 2), BIL)
    acc = h
    for i in range(1, n):
        z = 1 + kuat * i / (n - 1)
        sc = affine(h, z, cx=None if cx is None else cx / 2, cy=None if cy is None else cy / 2)
        acc = Image.blend(acc, sc, 1.0 / (i + 1))
    langkah = kuat / max(1, n - 1) * max(W, H) / 4  # geser antar salinan di tepi (px, res 1/2)
    if langkah > 1.5:
        acc = acc.filter(ImageFilter.GaussianBlur(float(min(langkah * 0.5, 12.0))))
    return acc.resize((W, H), BIL)


def blur_arah(img, dx, dy, n=None):
    """blur gerak searah (dx,dy piksel total) di resolusi 1/2; tepi dibungkus (untuk whip).
    Jumlah salinan ~ panjang/10 px agar mulus (tanpa salinan hantu)."""
    if abs(dx) + abs(dy) < 1:
        return img
    W, H = img.size
    L = math.hypot(dx, dy)
    n = n or int(D.clamp(L / 12, 4, 18))
    h = img.resize((W // 2, H // 2), BIL)
    acc = h
    for i in range(1, n):
        f = i / (n - 1) - 0.5
        sh = ImageChops.offset(h, int(round(dx / 2 * f)), int(round(dy / 2 * f)))
        acc = Image.blend(acc, sh, 1.0 / (i + 1))
    langkah = L / 2 / max(1, n - 1)  # jarak antar salinan (px, resolusi 1/2) -> haluskan agar tak bertingkat
    if langkah > 1.5:
        acc = acc.filter(ImageFilter.GaussianBlur(float(langkah * 0.6)))
    return acc.resize((W, H), BIL)


def _punch(d):
    if d < 0:
        return 0.0
    if d < 0.045:
        return D.eo(d / 0.045)
    return math.exp(-(d - 0.045) / 0.13)


def kamera(img, T, ctx=None, beats=(), ss=1.5, kuat=1.0, dasar_zoom=1.035):
    """napas/genggam organik (nois) + dorongan zoom pada beat berat + guncang hook intro (sc.shake)."""
    if not AKTIF:
        return img
    dx = nois(T * 0.33, 11) * 7 * ss * kuat
    dy = nois(T * 0.29, 23) * 7 * ss * kuat
    rot = nois(T * 0.21, 37) * 0.28 * kuat
    z = dasar_zoom + 0.008 * nois(T * 0.17, 41)
    for b in beats:
        if -0.05 < T - b < 0.7:
            z += 0.028 * _punch(T - b)
    if ctx is not None:
        sh = float(ctx.sc.get("shake", 0) or 0)
        if sh and ctx.t < 0.9:
            k = (1 - ctx.t / 0.9) ** 2
            dx += sh * 9 * ss * k * nois(T * 13, 5)
            dy += sh * 9 * ss * k * nois(T * 13, 6)
            rot += sh * 0.6 * k * nois(T * 11, 7)
    return affine(img, z, rot, dx, dy)


def kamera_box(T, ctx=None, beats=(), W=1620, H=2880, ss=1.5, kuat=1.0, dasar_zoom=1.035):
    """kamera sebagai KOTAK SUMBER untuk Image.resize(box=...): zoom + geser digabung ke downscale LANCZOS
    (satu resampling, tanpa transform mahal). Rotasi hanya saat guncang hook (sc.shake). -> (box, rot)."""
    if not AKTIF:
        return (0, 0, W, H), 0.0
    dx = nois(T * 0.33, 11) * 7 * ss * kuat
    dy = nois(T * 0.29, 23) * 7 * ss * kuat
    z = dasar_zoom + 0.008 * nois(T * 0.17, 41)
    rot = 0.0
    for b in beats:
        if -0.05 < T - b < 0.7:
            z += 0.028 * _punch(T - b)
    if ctx is not None:
        sh = float(ctx.sc.get("shake", 0) or 0)
        if sh and ctx.t < 0.9:
            k = (1 - ctx.t / 0.9) ** 2
            dx += sh * 9 * ss * k * nois(T * 13, 5)
            dy += sh * 9 * ss * k * nois(T * 13, 6)
            rot = sh * 0.6 * k * nois(T * 11, 7)
    hw, hh = W / (2 * z), H / (2 * z)
    cx = min(max(W / 2 - dx, hw), W - hw)
    cy = min(max(H / 2 - dy, hh), H - hh)
    return (cx - hw, cy - hh, cx + hw, cy + hh), rot


# ============================================================================ material
@lru_cache(maxsize=64)
def _bayang_mask(w, h, r, blur):
    pad = int(blur * 2.2) + 2
    m = Image.new("L", (w + 2 * pad, h + 2 * pad), 0)
    m.paste(D._rrect_mask(w, h, r), (pad, pad))
    return m.filter(ImageFilter.GaussianBlur(float(blur))), pad


def bayang(img, x0, y0, x1, y1, r=40, blur=26, dx=0, dy=20, a=0.16, warna=D.INK):
    """bayangan lembut ter-cache untuk kotak membulat (koordinat desain)."""
    w, h = int(round(D.S(x1 - x0))), int(round(D.S(y1 - y0)))
    m, pad = _bayang_mask(w, h, int(round(D.S(r))), int(round(D.S(blur))))
    D.tempel(img, warna, round(D.S(x0 + dx)) - pad, round(D.S(y0 + dy)) - pad, m, a)


def kilau(img, x0, y0, x1, y1, r, u, a=0.22, lebar=0.18):
    """sapuan kilau diagonal melintasi kotak membulat; u = posisi 0..1."""
    m, X0, Y0 = D.rrect_mask(x0, y0, x1, y1, r)
    w, h = m.size
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    p = (xs / w + ys / h * 0.35) / 1.35
    c = -lebar + u * (1 + 2 * lebar)
    band = np.clip(1 - np.abs(p - c) / lebar, 0, 1) ** 2
    band = Image.fromarray((band * 255).astype(np.uint8), "L")
    D.tempel(img, D.PUTIH, X0, Y0, ImageChops.multiply(band, m), a)


def kaca_cair(img, x0, y0, x1, y1, r=46, t=0.0, tint=(255, 255, 255), a=1.0, kabur=10.0, bias=1.06):
    """panel Liquid Glass: latar diburamkan + dibiaskan (magnifikasi tepi), rona tipis, kilap tepi, sapuan kilau."""
    if a <= 0.01:
        return
    m, X0, Y0 = D.rrect_mask(x0, y0, x1, y1, r)
    w, h = m.size
    W, H = img.size
    bx0, by0 = max(0, X0), max(0, Y0)
    bx1, by1 = min(W, X0 + w), min(H, Y0 + h)
    if bx1 <= bx0 or by1 <= by0:
        return
    crop = img.crop((X0, Y0, X0 + w, Y0 + h))
    small = crop.resize((max(4, w // 4), max(4, h // 4)), BIL).filter(ImageFilter.GaussianBlur(float(kabur / 4)))
    big = small.resize((int(w * bias), int(h * bias)), BIL)
    ox, oy = (big.size[0] - w) // 2, (big.size[1] - h) // 2
    glass = big.crop((ox, oy, ox + w, oy + h))
    glass = Image.blend(glass, Image.new("RGB", (w, h), D.col(tint)), 0.30)
    grad = Image.linear_gradient("L").resize((w, h), BIL).point(lambda v: int((255 - v) * 0.35))
    glass.paste(D.PUTIH, (0, 0), grad)
    img.paste(glass, (X0, Y0), D.amask(m, a))
    D.rrect_garis(img, x0 + 1.5, y0 + 1.5, x1 - 1.5, y1 - 1.5, r - 1.5, D.PUTIH, 3, 0.75 * a)
    D.rrect_garis(img, x0, y0, x1, y1, r, D.INK, 1.6, 0.10 * a)
    kilau(img, x0, y0, x1, y1, r, (t * 0.18) % 1.4 - 0.2, 0.20 * a)


def bokeh(img, t, n=10, warna=D.PUTIH, seed=0, kotak=(0, 0, 1080, 1920), a=0.10, r=(30, 90), kec=10):
    """bokeh 2.5D: lingkaran lembut dengan parallax (besar = dekat = lebih cepat)."""
    x0, y0, x1, y1 = kotak
    rr = D.rng("bokeh", seed)
    for i in range(n):
        rad = rr.uniform(*r)
        dep = rad / r[1]
        x = rr.uniform(x0, x1) + math.sin(t * 0.3 + i) * 20 * dep
        y = y0 + (rr.uniform(0, y1 - y0) - t * kec * dep) % (y1 - y0)
        D.glow(img, x, y, rad * 1.6, warna, a * 0.6)
        D.circ(img, x, y, rad, warna, a * 0.35)


def mesh_latar(size, T, aksen=(47, 123, 255), seed="kt", dasar=D.CREAM, kuat=0.10):
    """latar mesh gradient bergerak: krem + 4 gumpal rona aksen sangat tipis, dihitung di resolusi rendah."""
    W, H = size
    lw, lh = 54, 96
    ys, xs = np.mgrid[0:lh, 0:lw].astype(np.float32)
    xs /= lw
    ys /= lh
    base = np.array(dasar, np.float32)
    out = np.broadcast_to(base, (lh, lw, 3)).copy()
    ak = np.array(D.col(aksen), np.float32)
    sd = sum(ord(c) for c in str(seed))
    warna = [ak, np.array(D.campur(aksen, "#FFB020", 0.5), np.float32),
             np.array(D.campur(aksen, D.PUTIH, 0.6), np.float32), np.array(D.campur(aksen, "#FF5FA2", 0.4), np.float32)]
    for k in range(4):
        cx = 0.5 + 0.45 * nois(T * 0.05 + k * 3.1, sd + k)
        cy = 0.5 + 0.48 * nois(T * 0.04 + k * 5.7, sd + 10 + k)
        rad = 0.32 + 0.08 * nois(T * 0.07, sd + 20 + k)
        g = np.exp(-(((xs - cx) / rad) ** 2 + ((ys - cy) / (rad * 0.62)) ** 2))
        wk = (kuat if k == 0 else kuat * 0.7) * g[..., None]
        out = out * (1 - wk) + warna[k] * wk
    im = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")
    return im.resize((W // 6, H // 6), Image.BICUBIC).resize((W, H), BIL)  # 2 tahap: halus & murah


# ---------------------------------------------------------------------------- odometer
@lru_cache(maxsize=32)
def _strip_digit(w, px):
    """strip vertikal 0..9,0 untuk satu font/ukuran. -> (mask, tinggi_sel)."""
    f = D.font_px(w, px)
    asc, desc = f.getmetrics()
    sel = int(math.ceil(px * 1.18))  # >= tinggi glyph (~0.87*px) + ruang
    lebar = int(math.ceil(max(f.getlength(str(d)) for d in range(10)))) + 4
    m = Image.new("L", (lebar, sel * 11), 0)
    d = ImageDraw.Draw(m)
    for i in range(11):
        d.text((lebar / 2, i * sel + sel * 0.5 + px * 0.36), str(i % 10), font=f, fill=255, anchor="ms")
    return m, sel, lebar


def odometer(img, nilai, x, y, size, warna=D.INK, a=1.0, anchor="m", w="B", u=1.0, desimal=0, satuan=""):
    """angka bergulir per digit seperti odometer asli (digit atas bergerak saat digit bawah 9->0).
    Format Indonesia (titik ribuan, koma desimal). x,y = titik jangkar, y = baseline."""
    v = float(nilai) * D.eo(u)
    tgt = D.format_id(float(nilai), desimal)
    px = D.fpx(size)
    strip, sel, lebar = _strip_digit(w, px)
    lebar_d = lebar / D.SS
    # lebar total (digit pakai lebar sel seragam)
    tot = sum(lebar_d if c.isdigit() else D.txt_w(c, size, w) for c in tgt) + (D.txt_w(" " + satuan, size * 0.55, "SB") if satuan else 0)
    xl = x - (tot / 2 if anchor == "m" else tot if anchor == "r" else 0)
    skala = 10 ** desimal
    vi = v * skala
    ndig = sum(c.isdigit() for c in tgt)
    cx, pos = xl, ndig - 1
    ch = D.cap_h(size, w)
    for c in tgt:
        if c.isdigit():
            q = vi / (10 ** pos)
            dig = math.floor(q) % 10
            frac = q - math.floor(q)
            if pos == 0:
                roll = frac
            else:
                low = (vi / (10 ** (pos - 1))) % 10
                roll = D.clamp(low - 9.0)
            yy = int(round((dig + roll) * sel))
            win = strip.crop((0, yy, lebar, yy + sel))
            top = D.S(y) - sel * 0.5 - px * 0.36
            if not (pos >= 1 and vi < 10 ** pos and dig == 0 and roll == 0 and u < 1):
                D.tempel(img, warna, round(D.S(cx)), round(top), win, a)
            cx += lebar_d
            pos -= 1
        else:
            D.txt(img, c, cx, y, size, w, warna, a, "ls", catat=False)
            cx += D.txt_w(c, size, w)
    if satuan:
        D.txt(img, satuan, cx + D.txt_w(" ", size * 0.55, "SB"), y, size * 0.55, "SB", warna, a, "ls", catat=False)
    D.KOTAK_TEKS.append((xl, y - ch * 1.05, xl + tot, y + size * 0.24, tgt + satuan))


# ============================================================================ transisi fase
def _warna(c):
    return D.col(c)


def _mask_lr(W, H, fn, f=4):
    """mask dihitung di resolusi 1/f lalu diperbesar (murah)."""
    w, h = max(2, W // f), max(2, H // f)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    a = np.clip(fn(xs / w, ys / h, w, h), 0, 1)
    return Image.fromarray((a * 255).astype(np.uint8), "L").resize((W, H), BIL)


def _isi(img, warna, mask):
    return Image.composite(Image.new("RGB", img.size, warna), img, mask)


def _flash(img, a, warna=(255, 252, 246)):
    if a <= 0.004:
        return img
    return Image.blend(img, Image.new("RGB", img.size, warna), D.clamp(a))


def _t_zoomthru(img, e, fase, ak, seed):
    z = 1 + (1.2 if fase == "keluar" else 0.9) * e ** 2.2
    out = zoom_blur(affine(img, z), 0.35 * e)
    return _flash(out, 0.9 * D.eio(D.seg(e, 0.55, 1.0)))


def _t_whip(img, e, fase, ak, seed):
    W, H = img.size
    sgn = -1 if fase == "keluar" else 1
    sh = ImageChops.offset(img, int(sgn * e ** 2 * W * 0.55), 0)
    return blur_arah(sh, e * W * 0.22, 0)


def _t_tinta(img, e, fase, ak, seed):
    W, H = img.size
    c = D.eio(e)
    gelap = D.gelap(ak, 0.35)

    def tepi(xs, ys, w, h, lead):
        cc = D.clamp(c + lead)
        wav = 0.035 * np.sin(xs * 9.0 + seed * 1.7) + 0.02 * np.sin(xs * 23.0 + seed)
        if fase == "keluar":
            edge = 1.0 - cc * 1.2 + wav
            return (ys - edge) * h / 3.0
        edge = cc * 1.2 - 0.2 + wav
        return (edge - ys) * h / 3.0

    out = _isi(img, gelap, _mask_lr(W, H, lambda x, y, w, h: tepi(x, y, w, h, 0.10)))
    return _isi(out, ak, _mask_lr(W, H, lambda x, y, w, h: tepi(x, y, w, h, 0.0)))


def _t_iris(img, e, fase, ak, seed):
    W, H = img.size
    rmax = math.hypot(W, H) / 2
    r = (1 - D.eio(e)) * rmax

    def fn(xs, ys, w, h):
        d = np.sqrt(((xs - 0.5) * W) ** 2 + ((ys - 0.5) * H) ** 2)
        return (d - r) / 6.0

    out = _isi(img, ak, _mask_lr(W, H, fn))

    def cincin(xs, ys, w, h):
        d = np.sqrt(((xs - 0.5) * W) ** 2 + ((ys - 0.5) * H) ** 2)
        return 1 - np.abs(d - r) / (0.012 * W)

    if 0.02 < e < 0.98:
        out = Image.composite(Image.new("RGB", img.size, D.PUTIH), out, amask_img(_mask_lr(W, H, cincin), 0.8 * e))
    return out


def amask_img(m, a):
    return D.amask(m, a)


@lru_cache(maxsize=4)
def _leak(W, H):
    w, h = W // 8, H // 8
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    xs /= w
    ys /= h
    a = np.exp(-(((xs - 0.95) / 0.55) ** 2 + ((ys - 0.05) / 0.45) ** 2))
    b = np.exp(-(((xs - 0.1) / 0.5) ** 2 + ((ys - 0.9) / 0.4) ** 2)) * 0.6
    rgb = np.dstack([a * 255 + b * 255, a * 170 + b * 120, a * 90 + b * 170])
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB").resize((W, H), Image.BICUBIC)


def _t_cahaya(img, e, fase, ak, seed):
    W, H = img.size
    k = e ** 1.4
    leak = _leak(W, H).point([int(v * k) for v in range(256)] * 3)
    out = ImageChops.add(img, leak)
    return _flash(out, 0.85 * D.eio(D.seg(e, 0.6, 1.0)))


def _t_speed(img, e, fase, ak, seed):
    W, H = img.size
    out = zoom_blur(affine(img, 1 + 0.25 * e ** 2), 0.3 * e)
    lay = Image.new("L", (W // 2, H // 2), 0)
    d = ImageDraw.Draw(lay)
    rr = D.rng("speed", seed)
    cx, cy = W / 4, H / 4
    for i in range(60):
        ang = rr.uniform(0, 2 * math.pi)
        r0 = rr.uniform(0.25, 0.6) * H / 2 * (1 - 0.4 * e)
        L = rr.uniform(0.2, 0.5) * H / 2 * e
        d.line((cx + math.cos(ang) * r0, cy + math.sin(ang) * r0, cx + math.cos(ang) * (r0 + L),
                cy + math.sin(ang) * (r0 + L)), fill=255, width=max(1, int(rr.uniform(1, 4))))
    out = Image.composite(Image.new("RGB", img.size, D.PUTIH), out, D.amask(lay.resize((W, H), BIL), 0.75 * e))
    return _flash(out, 0.8 * D.eio(D.seg(e, 0.7, 1.0)))


def _t_glint(img, e, fase, ak, seed):
    W, H = img.size
    pos = (-0.25 + 0.85 * e) if fase == "keluar" else (1.45 - 0.85 * e)  # sapuan menerus melewati potongan

    def fn(xs, ys, w, h):
        p = (xs * 0.8 + ys * 0.45) / 1.25
        return np.maximum(1 - np.abs(p - pos) / 0.16, 0.6 * (1 - np.abs(p - pos + 0.13) / 0.03))

    out = _flash(img, 0.22 * e * e)
    out = Image.composite(Image.new("RGB", img.size, D.PUTIH), out, D.amask(_mask_lr(W, H, fn), 0.95))
    return _flash(out, 0.88 * D.eio(D.seg(e, 0.62, 1.0)))


def _t_split(img, e, fase, ak, seed):
    W, H = img.size
    g = D.eio(e)
    off = int(g * H * 0.52)
    out = Image.new("RGB", img.size, ak)
    top = img.crop((0, 0, W, H // 2))
    bot = img.crop((0, H // 2, W, H))
    out.paste(top, (0, -off))
    out.paste(bot, (0, H // 2 + off))
    return out


def _t_zoom(img, e, fase, ak, seed):
    if fase == "keluar":
        out = affine(img, 1 + 0.18 * D.eio(e))
    else:
        out = affine(img, 1 - 0.10 * D.eio(e), isi=D.CREAM)
    return _flash(out, D.eio(e) ** 1.2, D.CREAM)


def _t_bands(img, e, fase, ak, seed):
    W, H = img.size
    out = img.copy()
    n = 6
    bh = H / n
    for i in range(n):
        p = D.eio(D.clamp(e * 1.45 - i * 0.075))
        if p <= 0:
            continue
        wv = int(W * p)
        warna = ak if i % 2 == 0 else D.gelap(ak, 0.25)
        x0 = 0 if (i % 2 == 0) == (fase == "keluar") else W - wv
        out.paste(warna, (x0, int(i * bh), x0 + wv, int((i + 1) * bh) + 1))
    return out


def _t_rise(img, e, fase, ak, seed):
    W, H = img.size
    g = D.eio(e)
    dy = -g * g * H * 0.30 if fase == "keluar" else g * g * H * 0.22
    out = affine(img, 1.0, 0, 0, dy, isi=D.CREAM)
    return _flash(out, g ** 1.3, D.CREAM)


def _t_punch(img, e, fase, ak, seed):
    if fase == "keluar":
        out = affine(img, 1 - 0.11 * D.eio(e), isi=D.CREAM)
    else:
        out = zoom_blur(affine(img, 1 + 0.18 * e ** 2), 0.10 * e)
    return _flash(out, 0.92 * D.eio(D.seg(e, 0.42, 1.0)))


def _t_slide(img, e, fase, ak, seed):
    W, H = img.size
    g = D.eio(e)
    out = Image.new("RGB", img.size, ak)
    if fase == "keluar":
        out.paste(img, (int(-g * W), 0))
    else:
        out.paste(img, (int(g * W), 0))
    return out


def _t_glitch(img, e, fase, ak, seed):
    W, H = img.size
    k = int(round(e * 8))
    r, g, b = img.split()
    s = int(e * W * 0.04)
    out = Image.merge("RGB", (ImageChops.offset(r, s, 0), g, ImageChops.offset(b, -s, 0)))
    rr = D.rng("glitch", seed, k)
    for _ in range(int(6 + 18 * e)):
        y0 = int(rr.uniform(0, H))
        hh = int(rr.uniform(0.01, 0.07) * H)
        dx = int(rr.uniform(-0.2, 0.2) * W * e)
        strip = out.crop((0, y0, W, min(H, y0 + hh)))
        out.paste(ImageChops.offset(strip, dx, 0), (0, y0))
    if e > 0.45:  # batang warna digital (aksen / tinta), makin rapat menuju potongan
        for _ in range(int(20 * D.seg(e, 0.45, 1.0))):
            y0 = int(rr.uniform(0, H))
            hh = int(rr.uniform(0.008, 0.05) * H)
            x0 = int(rr.uniform(-0.3, 0.7) * W)
            out.paste(ak if rr.random() < 0.7 else D.INK, (max(0, x0), y0, min(W, x0 + int(rr.uniform(0.3, 1.0) * W)), y0 + hh))
    if e > 0.8:
        out = Image.blend(out, Image.new("RGB", img.size, ak), 0.85 * D.eio(D.seg(e, 0.8, 1.0)))
    return out


TRANS = {
    "zoomthru": _t_zoomthru, "tinta": _t_tinta, "cahaya": _t_cahaya, "speed": _t_speed, "glint": _t_glint,
    "split": _t_split, "zoom": _t_zoom, "bands": _t_bands, "iris": _t_iris, "rise": _t_rise, "punch": _t_punch,
    "slide": _t_slide, "glitch": _t_glitch, "whip": _t_whip,
}


def transisi(img, jenis, fase, u, aksen=(47, 123, 255), seed=0):
    """fase 'keluar': u 0->1 menuju titik potong; 'masuk': u 0->1 menjauhi titik potong."""
    u = D.clamp(u)
    e = u if fase == "keluar" else 1 - u
    if e <= 0.002:
        return img
    return TRANS.get(jenis, _t_zoom)(img, e, fase, _warna(aksen), seed)


# ============================================================================ selftest
def _uji():
    from mesin_util import sheet
    D.set_ss(1.0)
    ok = True

    def cek(nama, kond, det=""):
        nonlocal ok
        ok &= bool(kond)
        print(f"  [{'OK' if kond else 'GAGAL'}] {nama} {det}")

    base = mesh_latar((1080, 1920), 3.0, "#2F7BFF")
    D.rrect(base, 140, 700, 940, 1300, 50, D.PUTIH)
    D.txt(base, "UJI FX", 540, 480, 120, "B", D.INK, 1, "ms")
    D.circ(base, 540, 1000, 160, "#2F7BFF")
    print("1) finishing")
    t0 = time.time()
    fin = finishing(base, "krem", 7)
    ms = (time.time() - t0) * 1000
    a, b = np.asarray(base, np.float32), np.asarray(fin, np.float32)
    cek("ukuran tetap", fin.size == base.size)
    cek("adegan terang tidak terbakar/gelap berlebihan", -8.0 < b.mean() - a.mean() < 2.0,
        f"(selisih rata2 {b.mean() - a.mean():+.2f})")
    separo = Image.new("RGB", (1080, 1920), D.CREAM)
    separo.paste(D.col("#2F7BFF"), (0, 0, 1080, 960))  # kasus nyata: penutup transisi setengah layar
    bs = bloom(separo, PRESET["krem"]["bloom"])
    naik = float(np.asarray(bs, np.float32)[1300:1800, 100:980].mean() - np.asarray(separo, np.float32)[1300:1800, 100:980].mean())
    cek("frame setengah biru: area krem tidak terbakar", naik < 2.0, f"(krem naik {naik:+.2f})")
    cek("putih tidak clip melebar", (b >= 254.5).mean() < (a >= 254.5).mean() + 0.02)
    cek(f"cepat (< 400 ms @1080x1920)", ms < 400, f"({ms:.0f} ms)")
    gelap = Image.new("RGB", (1080, 1920), (12, 14, 24))
    D.circ(gelap, 540, 960, 60, D.PUTIH)
    fb = finishing(gelap, "sinema", 3)
    ring_px = np.asarray(fb, np.float32)[960, 540 + 110]
    cek("adegan gelap: bloom terlihat", ring_px.mean() > 20, f"(piksel dekat sorot {ring_px.mean():.0f})")
    g1, g2 = np.asarray(grain(base, 1, 2)), np.asarray(grain(base, 1, 2))
    cek("grain deterministik", np.array_equal(g1, g2))
    cek("grain beda per frame", not np.array_equal(g1, np.asarray(grain(base, 2, 2))))
    print("2) transisi (identitas di ujung fase, tertutup di titik potong)")
    ak = D.col("#FF6B3D")
    imgs, labels = [], []
    for j in TRANS:
        t0 = time.time()
        k0 = transisi(base, j, "keluar", 0.0, ak)
        m1 = transisi(base, j, "masuk", 1.0, ak)
        d0 = float(np.abs(np.asarray(k0, np.int16) - np.asarray(base, np.int16)).mean())
        d1 = float(np.abs(np.asarray(m1, np.int16) - np.asarray(base, np.int16)).mean())
        mid_k = transisi(base, j, "keluar", 0.6, ak)
        cut_k = transisi(base, j, "keluar", 1.0, ak)
        cut_m = transisi(base, j, "masuk", 0.0, ak)
        mid_m = transisi(base, j, "masuk", 0.4, ak)
        ms = (time.time() - t0) / 6 * 1000
        beda = float(np.abs(np.asarray(mid_k, np.int16) - np.asarray(base, np.int16)).mean())
        kontinu = float(np.abs(np.asarray(cut_k, np.int16) - np.asarray(cut_m, np.int16)).mean())
        good = d0 < 0.5 and d1 < 0.5 and beda > 3 and cut_k.size == base.size
        ok &= good
        print(f"  [{'OK' if good else 'GAGAL'}] {j:<9} identitas {d0:.2f}/{d1:.2f}  efek {beda:5.1f}  "
              f"selisih potong {kontinu:5.1f}  {ms:4.0f} ms")
        imgs += [mid_k, cut_k, mid_m]
        labels += [f"{j} keluar .6", f"{j} potong", f"{j} masuk .4"]
    out = Path(__file__).resolve().parent / "build" / "mesin_fx_transisi.jpg"
    sheet(imgs, labels, cols=6, lebar=170, judul="mesin_fx transisi", path=out)
    print(f"montase: {out}")
    print("3) material & odometer")
    im = mesh_latar((1080, 1920), 1.0, "#7B5CFF")
    D.circ(im, 400, 800, 200, "#FF6B3D")
    kaca_cair(im, 150, 650, 930, 1150, 50, 2.0)
    bayang(im, 200, 1300, 880, 1500, 40)
    D.rrect(im, 200, 1300, 880, 1500, 40, D.PUTIH)
    odometer(im, 1234567, 540, 1440, 110, D.INK, 1, "m", "B", 0.73)
    bokeh(im, 2.0, 8, D.PUTIH, 1)
    im.save(Path(__file__).resolve().parent / "build" / "mesin_fx_material.png")
    cek("material & odometer tergambar", True)
    print("MESIN_FX SELFTEST:", "LULUS" if ok else "GAGAL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(_uji())
