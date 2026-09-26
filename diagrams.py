#!/usr/bin/env python3
"""diagrams.py - primitif gambar + visual adegan Shorts (registry VISUALS) + selftest.

Koordinat SELALU didesain di skala 1080x1920 lalu dikali S(v) = v*SS (supersample).
Primitif anti-alias berbasis SDF numpy (lingkaran, cincin/busur, kotak membulat, garis kapsul),
poligon/polyline via mask supersample 2x. Teks: mask ter-cache + alpha, kotak teks dicatat di KOTAK_TEKS
(dipakai check_layout untuk audit zona aman).

Poppins tidak punya glyph centang, bintang, superskrip -> centang(), bintang(), txt("10^8") menggambar bentuk.

Kontrak visual:  fn(img, t, dur, sc)   img = kanvas RGB (W0*SS x H0*SS), t = detik sejak awal adegan,
                 dur = durasi adegan, sc = dict adegan (accent, param opsional).
Gaya: elemen BESAR, label polos, selalu ada gerak (tidak ada frame diam > 1 s), warna aksen adegan.
Selftest:  python3 diagrams.py
"""
from __future__ import annotations

import math
import sys
import time
import zlib
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
W0, H0 = 1080, 1920
CREAM = (246, 241, 232)
INK = (24, 24, 31)
MUTED = (128, 122, 114)
PUTIH = (255, 255, 255)
PALET = {
    "biru": "#2F7BFF", "oranye": "#FF6B3D", "hijau": "#1FB57A", "ungu": "#7B5CFF",
    "kuning": "#FFB020", "merah": "#F0454A", "tosca": "#13B5C8", "pink": "#FF5FA2",
}
# panggung visual (koordinat desain). Teks penting: jangan x>950 pada y 1100-1700, jangan y>1640.
PANGGUNG = (60, 680, 1020, 1600)
PX, PY = 540, 1140

SS = 1.5
KOTAK_TEKS: list = []  # (x0, y0, x1, y1, teks) desain


def set_ss(v):
    global SS
    SS = float(v)


def S(v):
    return v * SS


def Si(v):
    return int(round(v * SS))


# ============================================================================ easing & waktu
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def seg(t, a, b):
    """progres 0..1 dari t antara a dan b."""
    if b <= a:
        return 1.0 if t >= b else 0.0
    return clamp((t - a) / (b - a))


def eo(u):
    u = clamp(u)
    return 1 - (1 - u) ** 3


def eio(u):
    u = clamp(u)
    return u * u * (3 - 2 * u)


def eob(u, s=1.70158):
    u = clamp(u)
    c3 = s + 1
    return 1 + c3 * (u - 1) ** 3 + s * (u - 1) ** 2


def pegas(u, zeta=0.42, omega=11.0):
    """pegas teredam 0->1 (overshoot lalu tenang). u dalam detik-ish (0..~1)."""
    if u <= 0:
        return 0.0
    wd = omega * math.sqrt(1 - zeta * zeta)
    return 1 - math.exp(-zeta * omega * u) * (math.cos(wd * u) + zeta * omega / wd * math.sin(wd * u))


def lerp(a, b, u):
    return a + (b - a) * u


def col(c):
    if isinstance(c, str):
        c = PALET.get(c, c).lstrip("#")
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    return tuple(int(v) for v in c[:3])


def campur(c1, c2, u):
    a, b = col(c1), col(c2)
    return tuple(int(round(a[i] + (b[i] - a[i]) * clamp(u))) for i in range(3))


def terang(c, u):
    return campur(c, PUTIH, u)


def gelap(c, u):
    return campur(c, INK, u)


def luminans(c):
    """luminans relatif WCAG 2.x (0..1) - untuk cek keterbacaan teks."""
    a = col(c)

    def _f(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    return 0.2126 * _f(a[0]) + 0.7152 * _f(a[1]) + 0.0722 * _f(a[2])


def kontras(c1, c2):
    """rasio kontras WCAG (1..21). Teks besar butuh >= 3.0, teks kecil >= 4.5."""
    la, lb = luminans(c1), luminans(c2)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def teks_terbaca(latar, batas=3.0):
    """pilih warna teks (PUTIH/INK) yang paling terbaca di atas `latar` (chip/stiker berlatar aksen)."""
    return PUTIH if kontras(latar, PUTIH) >= batas else INK


def rng(*kunci):
    return np.random.default_rng(zlib.crc32(":".join(map(str, kunci)).encode()))


# ============================================================================ alpha & mask
_LUT = [[int(v * q / 64 + 0.5) for v in range(256)] for q in range(65)]


def amask(mask, a):
    if a >= 0.995:
        return mask
    q = int(round(clamp(a) * 64))
    return mask.point(_LUT[q])


def tempel(img, warna, x0, y0, mask, a=1.0):
    """tempel warna solid lewat mask L di (x0,y0) piksel kanvas, dengan alpha a."""
    if a <= 0.004 or mask is None:
        return
    img.paste(col(warna), (int(x0), int(y0)), amask(mask, a))


def _grid(x0, y0, x1, y1):
    ys, xs = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    return xs + 0.5, ys + 0.5


def _bbox(img, x0, y0, x1, y1):
    W, H = img.size
    x0, y0 = max(0, int(math.floor(x0))), max(0, int(math.floor(y0)))
    x1, y1 = min(W, int(math.ceil(x1))), min(H, int(math.ceil(y1)))
    return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None


def _mask_from(alpha):
    return Image.fromarray((np.clip(alpha, 0, 1) * 255 + 0.5).astype(np.uint8), "L")


# ============================================================================ bentuk SDF (koordinat desain)
def circ(img, cx, cy, r, warna, a=1.0):
    if r <= 0 or a <= 0.004:
        return
    X, Y, R = S(cx), S(cy), S(r)
    bb = _bbox(img, X - R - 1, Y - R - 1, X + R + 1, Y + R + 1)
    if not bb:
        return
    xs, ys = _grid(*bb)
    d = np.sqrt((xs - X) ** 2 + (ys - Y) ** 2) - R
    tempel(img, warna, bb[0], bb[1], _mask_from(0.5 - d), a)


def ring(img, cx, cy, r, lebar, warna, a=1.0, a0=None, a1=None):
    """cincin; bila a0/a1 (derajat, 0 = atas, searah jarum jam) -> busur dengan ujung bulat."""
    if r <= 0 or lebar <= 0 or a <= 0.004:
        return
    X, Y, R, Wd = S(cx), S(cy), S(r), S(lebar) / 2
    busur = a0 is not None and a1 is not None and (a1 - a0) < 359.9
    if busur and a1 > a0:
        # kotak pembatas busur saja (bukan seluruh lingkaran) -> jauh lebih murah untuk busur pendek
        angs = np.radians(np.linspace(a0, a1, max(3, int((a1 - a0) / 10) + 2)))
        px_, py_ = X + R * np.sin(angs), Y - R * np.cos(angs)
        bb = _bbox(img, px_.min() - Wd - 2, py_.min() - Wd - 2, px_.max() + Wd + 2, py_.max() + Wd + 2)
    else:
        bb = _bbox(img, X - R - Wd - 1, Y - R - Wd - 1, X + R + Wd + 1, Y + R + Wd + 1)
    if not bb:
        return
    xs, ys = _grid(*bb)
    dx, dy = xs - X, ys - Y
    dist = np.sqrt(dx * dx + dy * dy)
    d = np.abs(dist - R) - Wd
    if a0 is not None and a1 is not None and (a1 - a0) < 359.9:
        if a1 <= a0:
            return
        ang = (np.degrees(np.arctan2(dx, -dy)) - a0) % 360.0
        inside = ang <= (a1 - a0)
        e = []
        for aa in (a0, a1):
            rad = math.radians(aa)
            ex, ey = X + R * math.sin(rad), Y - R * math.cos(rad)
            e.append(np.sqrt((xs - ex) ** 2 + (ys - ey) ** 2) - Wd)
        d = np.where(inside, d, np.minimum(e[0], e[1]))
    tempel(img, warna, bb[0], bb[1], _mask_from(0.5 - d), a)


@lru_cache(maxsize=256)
def _rrect_mask(w, h, r):
    """mask kotak membulat w x h (piksel int) radius r: interior penuh, sudut SDF (murah untuk panel besar)."""
    m = Image.new("L", (w, h), 255)
    r = int(min(r, w // 2, h // 2))
    if r >= 1:
        xs, ys = _grid(0, 0, r, r)
        d = np.sqrt((xs - r) ** 2 + (ys - r) ** 2) - r
        c = _mask_from(0.5 - np.where((xs < r) & (ys < r), d, -1))
        m.paste(c, (0, 0))
        m.paste(c.transpose(Image.FLIP_LEFT_RIGHT), (w - r, 0))
        m.paste(c.transpose(Image.FLIP_TOP_BOTTOM), (0, h - r))
        m.paste(c.transpose(Image.ROTATE_180), (w - r, h - r))
    return m


def rrect_mask(x0, y0, x1, y1, r):
    """-> (mask, px0, py0) untuk kotak membulat koordinat desain."""
    X0, Y0 = int(round(S(x0))), int(round(S(y0)))
    w, h = max(1, int(round(S(x1))) - X0), max(1, int(round(S(y1))) - Y0)
    return _rrect_mask(w, h, int(round(S(r)))), X0, Y0


def rrect(img, x0, y0, x1, y1, r, warna, a=1.0, garis=None, lebar=0):
    if a <= 0.004 or x1 <= x0 or y1 <= y0:
        return
    m, X0, Y0 = rrect_mask(x0, y0, x1, y1, r)
    if garis is not None and lebar > 0:
        tempel(img, garis, X0, Y0, m, a)
        mi, X1, Y1 = rrect_mask(x0 + lebar, y0 + lebar, x1 - lebar, y1 - lebar, max(0, r - lebar))
        tempel(img, warna, X1, Y1, mi, a)
    else:
        tempel(img, warna, X0, Y0, m, a)


@lru_cache(maxsize=128)
def _rrect_garis_mask(w, h, r, lw):
    """mask garis tepi kotak membulat (piksel int), ter-cache: panel statis tidak dihitung ulang tiap frame."""
    pad = int(math.ceil(lw / 2)) + 2
    xs, ys = _grid(0, 0, w + 2 * pad, h + 2 * pad)
    cx, cy = pad + w / 2, pad + h / 2
    hx, hy = w / 2 - r, h / 2 - r
    qx, qy = np.abs(xs - cx) - hx, np.abs(ys - cy) - hy
    d = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2) + np.minimum(np.maximum(qx, qy), 0) - r
    return _mask_from(0.5 - (np.abs(d) - lw / 2)), pad


def rrect_garis(img, x0, y0, x1, y1, r, warna, lebar, a=1.0):
    """hanya garis tepi kotak membulat (SDF, mask ter-cache per ukuran)."""
    X0, Y0 = int(round(S(x0))), int(round(S(y0)))
    w, h = int(round(S(x1))) - X0, int(round(S(y1))) - Y0
    if w <= 2 or h <= 2 or a <= 0.004:
        return
    m, pad = _rrect_garis_mask(w, h, float(min(round(S(r), 1), w / 2, h / 2)), float(round(S(lebar), 1)))
    tempel(img, warna, X0 - pad, Y0 - pad, m, a)


def _rrect_garis_lama(img, x0, y0, x1, y1, r, warna, lebar, a=1.0):
    """(versi tanpa cache, disimpan untuk referensi uji)"""
    X0, Y0, X1, Y1 = S(x0), S(y0), S(x1), S(y1)
    R, Wd = S(r), S(lebar) / 2
    bb = _bbox(img, X0 - Wd - 1, Y0 - Wd - 1, X1 + Wd + 1, Y1 + Wd + 1)
    if not bb:
        return
    xs, ys = _grid(*bb)
    cx, cy = (X0 + X1) / 2, (Y0 + Y1) / 2
    hx, hy = (X1 - X0) / 2 - R, (Y1 - Y0) / 2 - R
    qx, qy = np.abs(xs - cx) - hx, np.abs(ys - cy) - hy
    d = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2) + np.minimum(np.maximum(qx, qy), 0) - R
    tempel(img, warna, bb[0], bb[1], _mask_from(0.5 - (np.abs(d) - Wd)), a)


def line(img, x0, y0, x1, y1, lebar, warna, a=1.0):
    """garis kapsul anti-alias."""
    if a <= 0.004:
        return
    A, B = np.array([S(x0), S(y0)]), np.array([S(x1), S(y1)])
    Wd = S(lebar) / 2
    bb = _bbox(img, min(A[0], B[0]) - Wd - 1, min(A[1], B[1]) - Wd - 1,
               max(A[0], B[0]) + Wd + 1, max(A[1], B[1]) + Wd + 1)
    if not bb:
        return
    xs, ys = _grid(*bb)
    ab = B - A
    L2 = float(ab @ ab) or 1e-6
    h = np.clip(((xs - A[0]) * ab[0] + (ys - A[1]) * ab[1]) / L2, 0, 1)
    d = np.sqrt((xs - A[0] - h * ab[0]) ** 2 + (ys - A[1] - h * ab[1]) ** 2) - Wd
    tempel(img, warna, bb[0], bb[1], _mask_from(0.5 - d), a)


def _ss_mask(img, pts, lebar=None, tutup=False, fill=True, k=2):
    """mask poligon/polyline via supersample k lalu reduce. pts desain. -> (mask, x0, y0) atau None."""
    P = [(S(x), S(y)) for x, y in pts]
    pad = (S(lebar) if lebar else 0) + 2
    xs = [p[0] for p in P]
    ys = [p[1] for p in P]
    bb = _bbox(img, min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)
    if not bb:
        return None
    x0, y0, x1, y1 = bb
    m = Image.new("L", ((x1 - x0) * k, (y1 - y0) * k), 0)
    d = ImageDraw.Draw(m)
    Q = [((x - x0) * k, (y - y0) * k) for x, y in P]
    if fill:
        d.polygon(Q, fill=255)
    else:
        w = max(1, int(round(S(lebar) * k)))
        if tutup:
            Q = Q + [Q[0]]
        d.line(Q, fill=255, width=w, joint="curve")
        r = w / 2
        for qx, qy in (Q[0], Q[-1]):
            d.ellipse((qx - r, qy - r, qx + r, qy + r), fill=255)
    return m.reduce(k), x0, y0


def poly(img, pts, warna, a=1.0):
    if len(pts) < 3 or a <= 0.004:
        return
    r = _ss_mask(img, pts)
    if r:
        tempel(img, warna, r[1], r[2], r[0], a)


def polyline(img, pts, lebar, warna, a=1.0, tutup=False):
    if len(pts) < 2 or a <= 0.004:
        return
    r = _ss_mask(img, pts, lebar, tutup, fill=False)
    if r:
        tempel(img, warna, r[1], r[2], r[0], a)


def potong_jalur(pts, u):
    """bagian awal polyline sepanjang fraksi u (untuk garis yang 'menggambar diri')."""
    u = clamp(u)
    if u >= 1 or len(pts) < 2:
        return list(pts)
    seglen = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    tot = sum(seglen) * u
    out = [pts[0]]
    for i, L in enumerate(seglen):
        if tot <= L:
            f = tot / L if L else 0
            out.append((lerp(pts[i][0], pts[i + 1][0], f), lerp(pts[i][1], pts[i + 1][1], f)))
            return out
        tot -= L
        out.append(pts[i + 1])
    return out


def bezier(p0, p1, p2, p3=None, n=48):
    out = []
    for i in range(n + 1):
        u = i / n
        if p3 is None:
            x = (1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * p1[0] + u * u * p2[0]
            y = (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * p1[1] + u * u * p2[1]
        else:
            x = (1 - u) ** 3 * p0[0] + 3 * (1 - u) ** 2 * u * p1[0] + 3 * (1 - u) * u * u * p2[0] + u ** 3 * p3[0]
            y = (1 - u) ** 3 * p0[1] + 3 * (1 - u) ** 2 * u * p1[1] + 3 * (1 - u) * u * u * p2[1] + u ** 3 * p3[1]
        out.append((x, y))
    return out


def panah(img, pts, lebar, warna, u=1.0, a=1.0, kepala=None):
    """panah polyline yang menggambar diri (u 0..1) dengan kepala segitiga di ujung."""
    p = potong_jalur(pts, u)
    if len(p) < 2 or u <= 0.01:
        return
    polyline(img, p, lebar, warna, a)
    (xa, ya), (xb, yb) = p[-2], p[-1]
    ang = math.atan2(yb - ya, xb - xa)
    k = kepala or lebar * 3.2
    tip = (xb + math.cos(ang) * k * 0.35, yb + math.sin(ang) * k * 0.35)
    l1 = (tip[0] - k * math.cos(ang - 0.5), tip[1] - k * math.sin(ang - 0.5))
    l2 = (tip[0] - k * math.cos(ang + 0.5), tip[1] - k * math.sin(ang + 0.5))
    poly(img, [tip, l1, l2], warna, a)


# ============================================================================ glow (sprite radial numpy, tepi nol)
@lru_cache(maxsize=128)
def _glow_mask(rpx):
    n = 2 * rpx + 1
    xs, ys = _grid(0, 0, n, n)
    d = np.sqrt((xs - rpx - 0.5) ** 2 + (ys - rpx - 0.5) ** 2) / max(rpx, 1)
    a = np.exp(-(d * 2.2) ** 2) * np.clip(1 - d, 0, 1) ** 1.5  # tepi benar-benar nol (tanpa kotak)
    return _mask_from(a)


def glow(img, cx, cy, r, warna, a=0.5):
    if r <= 1 or a <= 0.004:
        return
    rpx = max(2, int(round(S(r) / 4)) * 4)
    m = _glow_mask(rpx)
    tempel(img, warna, S(cx) - rpx, S(cy) - rpx, m, a)


# ============================================================================ teks
FONT_FILE = {"B": "Poppins-Bold.ttf", "SB": "Poppins-SemiBold.ttf", "M": "Poppins-Medium.ttf",
             "R": "Poppins-Regular.ttf"}


@lru_cache(maxsize=256)
def font_px(w, px):
    return ImageFont.truetype(str(ROOT / "fonts" / FONT_FILE.get(w, w)), int(px))


def fpx(size):
    return max(4, int(round(S(size))))


@lru_cache(maxsize=4096)
def _txt_mask(s, w, px):
    """mask satu baris: tinggi = ascent+descent, baseline di y=ascent. -> (mask, lebar_advance, ascent)."""
    f = font_px(w, px)
    asc, desc = f.getmetrics()
    adv = f.getlength(s)
    l, t, r, b = f.getbbox(s, anchor="ls")
    padl = max(0, -l) + 2
    wid = int(math.ceil(max(adv, r) + padl + 2))
    m = Image.new("L", (max(1, wid), asc + desc + 2), 0)
    ImageDraw.Draw(m).text((padl, asc), s, font=f, fill=255, anchor="ls")
    return m, adv, asc, padl


def txt_w(s, size, w="B"):
    """lebar advance (desain)."""
    if "^" in s:
        return sum(txt_w(p, size * (0.6 if sup else 1), w) for p, sup in _pecah_sup(s))
    return font_px(w, fpx(size)).getlength(s) / SS


def cap_h(size, w="B"):
    f = font_px(w, fpx(size))
    l, t, r, b = f.getbbox("H", anchor="ls")
    return -t / SS


def _pecah_sup(s):
    """'10^8 km^2' -> [('10',F),('8',T),(' km',F),('2',T)]. Superskrip: ^ diikuti [-+]?angka/huruf pendek."""
    out, i, buf = [], 0, ""
    while i < len(s):
        if s[i] == "^" and i + 1 < len(s):
            if buf:
                out.append((buf, False))
                buf = ""
            j = i + 1
            if s[j] in "-+":
                j += 1
            while j < len(s) and (s[j].isalnum()):
                j += 1
            out.append((s[i + 1:j], True))
            i = j
        else:
            buf += s[i]
            i += 1
    if buf:
        out.append((buf, False))
    return out


def txt(img, s, x, y, size, w="B", warna=INK, a=1.0, anchor="ls", catat=True, jarak=0.0):
    """Teks satu baris. anchor: [l|m|r][t|m|s|b] (m vertikal = tengah tinggi huruf kapital).
    Mendukung superskrip '^' (digambar sebagai teks kecil terangkat). jarak = tracking tambahan (desain).
    -> kotak (x0,y0,x1,y1) desain."""
    if not s:
        return (x, y, x, y)
    if "^" in s:
        return _txt_sup(img, s, x, y, size, w, warna, a, anchor, catat)
    px = fpx(size)
    if jarak:
        return _txt_track(img, s, x, y, size, w, warna, a, anchor, catat, jarak)
    m, adv, asc, padl = _txt_mask(s, w, px)
    wd = adv / SS
    ch = cap_h(size, w)
    ha, va = anchor[0], anchor[1]
    xl = x - (wd / 2 if ha == "m" else wd if ha == "r" else 0)
    base = y + (ch / 2 if va == "m" else ch if va == "t" else -size * 0.28 if va == "b" else 0)
    X = S(xl) - padl
    Y = S(base) - asc
    if a > 0.004:
        tempel(img, warna, round(X), round(Y), m, a)
    box = (xl, base - ch * 1.02, xl + wd, base + size * 0.24)
    if catat and a > 0.05:
        KOTAK_TEKS.append((*box, s))
    return box


def _txt_track(img, s, x, y, size, w, warna, a, anchor, catat, jarak):
    widths = [txt_w(c, size, w) + jarak for c in s]
    tot = sum(widths) - jarak
    ha = anchor[0]
    xl = x - (tot / 2 if ha == "m" else tot if ha == "r" else 0)
    cx = xl
    box = None
    for c, wd in zip(s, widths):
        b = txt(img, c, cx, y, size, w, warna, a, "l" + anchor[1], catat=False)
        box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
        cx += wd
    if catat and a > 0.05 and box:
        KOTAK_TEKS.append((*box, s))
    return box


def _txt_sup(img, s, x, y, size, w, warna, a, anchor, catat):
    parts = _pecah_sup(s)
    tot = txt_w(s, size, w)
    ha, va = anchor[0], anchor[1]
    xl = x - (tot / 2 if ha == "m" else tot if ha == "r" else 0)
    ch = cap_h(size, w)
    base = y + (ch / 2 if va == "m" else ch if va == "t" else -size * 0.28 if va == "b" else 0)
    cx = xl
    for p, sup in parts:
        if sup:
            txt(img, p, cx + size * 0.03, base - ch * 0.48, size * 0.6, w, warna, a, "ls", catat=False)
            cx += txt_w(p, size * 0.6, w) + size * 0.05
        else:
            txt(img, p, cx, base, size, w, warna, a, "ls", catat=False)
            cx += txt_w(p, size, w)
    box = (xl, base - ch * 1.1, cx, base + size * 0.24)
    if catat and a > 0.05:
        KOTAK_TEKS.append((*box, s))
    return box


def wrap(s, size, max_w, w="B"):
    kata = s.split()
    baris, cur = [], ""
    for k in kata:
        uji = (cur + " " + k).strip()
        if txt_w(uji, size, w) <= max_w or not cur:
            cur = uji
        else:
            baris.append(cur)
            cur = k
    if cur:
        baris.append(cur)
    return baris


def fit_size(s, max_w, max_h, w="B", mulai=120, minim=28, maks_baris=3, lh=1.08):
    """ukuran font terbesar (int, desain) agar teks ter-wrap muat di max_w x max_h."""
    size = int(mulai)
    while size > minim:
        b = wrap(s, size, max_w, w)
        if len(b) <= maks_baris and len(b) * size * lh <= max_h and all(txt_w(x, size, w) <= max_w for x in b):
            return size, b
        size -= 2
    return minim, wrap(s, minim, max_w, w)


def paragraf(img, s, x, y, size, max_w, w="SB", warna=INK, a=1.0, anchor="m", lh=1.18):
    """blok teks ter-wrap, x = tengah (anchor m) atau kiri (l). y = baseline baris pertama."""
    out = []
    for i, b in enumerate(wrap(s, size, max_w, w)):
        out.append(txt(img, b, x, y + i * size * lh, size, w, warna, a, anchor + "s"))
    return out


# ============================================================================ bentuk ikon (tanpa glyph)
def centang(img, cx, cy, s, warna, lebar=None, u=1.0, a=1.0):
    """tanda centang digambar (u = progres menggambar)."""
    pts = [(cx - s * 0.42, cy + s * 0.02), (cx - s * 0.12, cy + s * 0.32), (cx + s * 0.46, cy - s * 0.34)]
    p = potong_jalur(pts, u)
    if len(p) >= 2:
        polyline(img, p, lebar or s * 0.16, warna, a)


def silang(img, cx, cy, s, warna, lebar=None, u=1.0, a=1.0):
    lw = lebar or s * 0.16
    u1, u2 = clamp(u * 2), clamp(u * 2 - 1)
    if u1 > 0:
        line(img, cx - s * .35, cy - s * .35, lerp(cx - s * .35, cx + s * .35, u1), lerp(cy - s * .35, cy + s * .35, u1), lw, warna, a)
    if u2 > 0:
        line(img, cx + s * .35, cy - s * .35, lerp(cx + s * .35, cx - s * .35, u2), lerp(cy - s * .35, cy + s * .35, u2), lw, warna, a)


def bintang_pts(cx, cy, r, n=5, dalam=0.46, rot=0.0):
    pts = []
    for i in range(2 * n):
        rr = r if i % 2 == 0 else r * dalam
        ang = math.radians(rot) + math.pi * i / n - math.pi / 2
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    return pts


def bintang(img, cx, cy, r, warna, a=1.0, n=5, dalam=0.46, rot=0.0):
    poly(img, bintang_pts(cx, cy, r, n, dalam, rot), warna, a)


def kilau4(img, cx, cy, r, warna, a=1.0, rot=0.0):
    """kilau 4 sudut (sparkle)."""
    poly(img, bintang_pts(cx, cy, r, 4, 0.22, rot), warna, a)


def hati(img, cx, cy, s, warna, a=1.0):
    pts = []
    for i in range(60):
        th = 2 * math.pi * i / 60
        x = 16 * math.sin(th) ** 3
        y = 13 * math.cos(th) - 5 * math.cos(2 * th) - 2 * math.cos(3 * th) - math.cos(4 * th)
        pts.append((cx + x * s / 34, cy - y * s / 34 - s * 0.05))
    poly(img, pts, warna, a)


def tetes(img, cx, cy, s, warna, a=1.0):
    pts = []
    for i in range(48):
        th = 2 * math.pi * i / 48
        r = s * 0.5
        x = r * math.sin(th) * (1 - math.cos(th)) * 0.55 * 1.6
        y = -r * math.cos(th) * 1.25
        pts.append((cx + x, cy + y))
    poly(img, pts, warna, a)


def petir(img, cx, cy, s, warna, a=1.0):
    p = [(0.10, -0.50), (-0.28, 0.06), (-0.02, 0.06), (-0.14, 0.50), (0.30, -0.10), (0.03, -0.10), (0.16, -0.50)]
    poly(img, [(cx + x * s, cy + y * s) for x, y in p], warna, a)


def matahari(img, cx, cy, r, warna, t=0.0, a=1.0, sinar=12):
    glow(img, cx, cy, r * 2.4, warna, 0.35 * a)
    for i in range(sinar):
        ang = 2 * math.pi * i / sinar + t * 0.35
        r0, r1 = r * 1.25, r * (1.55 + 0.12 * math.sin(t * 3 + i))
        line(img, cx + r0 * math.cos(ang), cy + r0 * math.sin(ang), cx + r1 * math.cos(ang), cy + r1 * math.sin(ang),
             r * 0.13, warna, a)
    circ(img, cx, cy, r, warna, a)
    circ(img, cx - r * 0.25, cy - r * 0.28, r * 0.35, terang(warna, 0.45), 0.55 * a)


def bulan_sabit(img, cx, cy, r, warna, latar, a=1.0):
    circ(img, cx, cy, r, warna, a)
    circ(img, cx + r * 0.42, cy - r * 0.18, r * 0.9, latar, a)


def bumi(img, cx, cy, r, t=0.0, a=1.0):
    circ(img, cx, cy, r, "#2F7BFF", a)
    rr = rng("bumi")
    for k in range(7):
        ang = rr.uniform(0, 6.28)
        off = ((rr.uniform(-0.6, 0.6) + t * 0.04) % 1.4) - 0.7
        x, y = cx + off * r * 1.1, cy + math.sin(ang) * r * 0.6
        rad = r * rr.uniform(0.16, 0.3)
        if math.dist((x, y), (cx, cy)) + rad * 0.5 < r:
            circ(img, x, y, rad, "#1FB57A", a * 0.95)
    ring(img, cx, cy, r, r * 0.05, PUTIH, 0.35 * a, 200, 320)


def mata(img, cx, cy, s, warna, t=0.0, a=1.0):
    pts = [(cx + s * 0.5 * math.cos(th), cy + s * 0.28 * math.sin(th) * (1 if th < math.pi else 1))
           for th in np.linspace(0, 2 * math.pi, 50)]
    poly(img, pts, PUTIH, a)
    polyline(img, pts, s * 0.05, INK, a, tutup=True)
    ox = math.sin(t * 1.5) * s * 0.08
    circ(img, cx + ox, cy, s * 0.17, warna, a)
    circ(img, cx + ox, cy, s * 0.08, INK, a)
    circ(img, cx + ox + s * 0.05, cy - s * 0.05, s * 0.03, PUTIH, a)


def jam(img, cx, cy, r, warna, t=0.0, a=1.0):
    circ(img, cx, cy, r, PUTIH, a)
    ring(img, cx, cy, r, r * 0.1, INK, a)
    for i in range(12):
        ang = math.pi * 2 * i / 12
        line(img, cx + r * 0.75 * math.sin(ang), cy - r * 0.75 * math.cos(ang), cx + r * 0.85 * math.sin(ang),
             cy - r * 0.85 * math.cos(ang), r * 0.05, MUTED, a)
    am = t * 2.0
    line(img, cx, cy, cx + r * 0.62 * math.sin(am), cy - r * 0.62 * math.cos(am), r * 0.07, warna, a)
    line(img, cx, cy, cx + r * 0.42 * math.sin(am / 12), cy - r * 0.42 * math.cos(am / 12), r * 0.09, INK, a)
    circ(img, cx, cy, r * 0.08, INK, a)


def atom(img, cx, cy, r, warna, t=0.0, a=1.0):
    for k in range(3):
        rot = k * math.pi / 3
        pts = [(cx + r * math.cos(th) * math.cos(rot) - r * 0.36 * math.sin(th) * math.sin(rot),
                cy + r * math.cos(th) * math.sin(rot) + r * 0.36 * math.sin(th) * math.cos(rot))
               for th in np.linspace(0, 2 * math.pi, 64)]
        polyline(img, pts, r * 0.045, INK, 0.8 * a, tutup=True)
        th = t * (1.6 + 0.3 * k) + k * 2
        ex = cx + r * math.cos(th) * math.cos(rot) - r * 0.36 * math.sin(th) * math.sin(rot)
        ey = cy + r * math.cos(th) * math.sin(rot) + r * 0.36 * math.sin(th) * math.cos(rot)
        circ(img, ex, ey, r * 0.08, warna, a)
    circ(img, cx, cy, r * 0.17, warna, a)


def salju(img, cx, cy, r, warna, t=0.0, a=1.0):
    rot = t * 0.3
    for i in range(6):
        ang = rot + math.pi * i / 3
        ex, ey = cx + r * math.cos(ang), cy + r * math.sin(ang)
        line(img, cx, cy, ex, ey, r * 0.1, warna, a)
        for f in (0.55, 0.78):
            bx, by = cx + r * f * math.cos(ang), cy + r * f * math.sin(ang)
            for sgn in (-1, 1):
                line(img, bx, by, bx + r * 0.22 * math.cos(ang + sgn * 0.8), by + r * 0.22 * math.sin(ang + sgn * 0.8),
                     r * 0.08, warna, a)


def api(img, cx, cy, s, warna, t=0.0, a=1.0):
    for k, (sc_, c) in enumerate(((1.0, warna), (0.62, "#FFB020"), (0.32, "#FFF1C1"))):
        pts = []
        for i in range(40):
            th = 2 * math.pi * i / 40
            wob = 1 + 0.06 * math.sin(t * 9 + i * 0.7 + k)
            x = math.sin(th) * 0.42 * (1 - 0.5 * max(0, -math.cos(th)))
            y = -math.cos(th) * 0.5 - 0.35 * max(0, -math.cos(th)) ** 2
            pts.append((cx + x * s * sc_ * wob, cy + s * 0.18 + y * s * sc_ * wob - s * 0.18 * (1 - sc_)))
        poly(img, pts, c, a)


IKON = {
    "centang": lambda im, x, y, r, c, t, a: centang(im, x, y, r * 1.5, c, a=a),
    "silang": lambda im, x, y, r, c, t, a: silang(im, x, y, r * 1.5, c, a=a),
    "bintang": lambda im, x, y, r, c, t, a: bintang(im, x, y, r, c, a, rot=math.sin(t) * 6),
    "hati": lambda im, x, y, r, c, t, a: hati(im, x, y, r * 1.8 * (1 + 0.06 * max(0, math.sin(t * 7))), c, a),
    "tetes": lambda im, x, y, r, c, t, a: tetes(im, x, y + math.sin(t * 2) * r * .05, r * 1.6, c, a),
    "petir": lambda im, x, y, r, c, t, a: petir(im, x, y, r * 1.9, c, a),
    "matahari": lambda im, x, y, r, c, t, a: matahari(im, x, y, r * 0.62, c, t, a),
    "bulan": lambda im, x, y, r, c, t, a: bulan_sabit(im, x, y, r * 0.85, c, CREAM, a),
    "bumi": lambda im, x, y, r, c, t, a: bumi(im, x, y, r * 0.9, t, a),
    "mata": lambda im, x, y, r, c, t, a: mata(im, x, y, r * 1.8, c, t, a),
    "jam": lambda im, x, y, r, c, t, a: jam(im, x, y, r * 0.9, c, t, a),
    "atom": lambda im, x, y, r, c, t, a: atom(im, x, y, r * 0.95, c, t, a),
    "salju": lambda im, x, y, r, c, t, a: salju(im, x, y, r * 0.9, c, t, a),
    "api": lambda im, x, y, r, c, t, a: api(im, x, y, r * 1.8, c, t, a),
    "kilau": lambda im, x, y, r, c, t, a: kilau4(im, x, y, r, c, a, rot=t * 20),
}


def ikon(img, nama, cx, cy, r, warna, t=0.0, a=1.0):
    f = IKON.get(nama)
    if f is None:
        txt(img, "?", cx, cy, r * 1.6, "B", warna, a, "mm")
    else:
        f(img, cx, cy, r, warna, t, a)


# ============================================================================ komponen kecil
def chip(img, s, x, y, size=34, warna="#2F7BFF", teks=PUTIH, a=1.0, anchor="m", w="B"):
    """label pil. x,y = tengah (anchor m) atau kiri (l). -> kotak desain."""
    tw = txt_w(s, size, w) + size * 0.12 * len(s) * 0
    pw, ph = tw + size * 1.2, size * 1.6
    x0 = x - pw / 2 if anchor == "m" else x
    rrect(img, x0, y - ph / 2, x0 + pw, y + ph / 2, ph / 2, warna, a)
    txt(img, s, x0 + pw / 2, y, size, w, teks, a, "mm")
    return (x0, y - ph / 2, x0 + pw, y + ph / 2)


def bayang_keras(img, fn, dx=10, dy=12, warna=INK, a=0.9):
    """panggil fn(offset_x, offset_y, warna, alpha) dua kali: bayangan keras lalu isi."""
    fn(dx, dy, warna, a * 0.9)


def partikel_lapangan(img, t, n, kotak, warna, seed, r=(3, 9), a=0.35, kec=18):
    x0, y0, x1, y1 = kotak
    rr = rng("pl", seed)
    px = rr.uniform(x0, x1, n)
    py = rr.uniform(y0, y1, n)
    ph = rr.uniform(0, 6.28, n)
    rad = rr.uniform(r[0], r[1], n)
    for i in range(n):
        yy = y0 + ((py[i] - y0 - t * kec * (0.5 + rad[i] / r[1])) % (y1 - y0))
        xx = px[i] + math.sin(t * 0.8 + ph[i]) * 14
        circ(img, xx, yy, rad[i], warna, a * (0.5 + 0.5 * math.sin(t * 1.3 + ph[i]) ** 2))


def gel_pts(x0, x1, y, amp, lam, fase, n=None):
    n = n or max(24, int((x1 - x0) / 6))
    return [(x, y + amp * math.sin(2 * math.pi * (x - x0) / lam - fase)) for x in np.linspace(x0, x1, n)]


def odometer(img, nilai, x, y, size, warna=INK, a=1.0, anchor="m", w="B", u=1.0, desimal=0, satuan=""):
    """angka bergulir per digit (format Indonesia: titik ribuan, koma desimal). u = progres (0..1)."""
    v = nilai * eo(u)
    s = format_id(v, desimal)
    tgt = format_id(nilai, desimal)
    s = s.rjust(len(tgt))
    tot = txt_w(tgt + satuan, size, w)
    x0 = x - (tot / 2 if anchor == "m" else tot if anchor == "r" else 0)
    cx = x0
    ch = cap_h(size, w)
    for i, c in enumerate(s):
        cw = txt_w(tgt[i] if i < len(tgt) else c, size, w)
        if c.isdigit():
            frac = 0.0
            if u < 1:
                # pecahan digit untuk gulir halus di digit paling kanan yang bergerak
                pos = len(s) - 1 - i
                raw = v / (10 ** max(0, pos - (desimal + (1 if desimal else 0)) * 0))
                frac = (raw % 1.0) if pos == 0 else 0.0
            dy = -frac * ch * 1.25
            txt(img, c, cx, y + dy, size, w, warna, a * (1 - frac * 0.6), "l" + "s", catat=False)
            if frac > 0.02:
                nxt = str((int(c) + 1) % 10)
                txt(img, nxt, cx, y + dy + ch * 1.25, size, w, warna, a * frac, "ls", catat=False)
        else:
            txt(img, c, cx, y, size, w, warna, a, "ls", catat=False)
        cx += cw
    if satuan:
        txt(img, satuan, cx, y, size, w, warna, a, "ls", catat=False)
    KOTAK_TEKS.append((x0, y - ch * 1.02, x0 + tot, y + size * 0.24, tgt + satuan))


def format_id(v, desimal=0):
    s = f"{abs(v):,.{desimal}f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if v < 0 else "") + s


# ============================================================================ VISUALS (generik, lintas episode)
def _aksen(sc):
    return col(sc.get("accent", "#2F7BFF"))


def _masuk(t, a=0.25, d=0.6):
    return eob(seg(t, a, a + d))


def v_langit(img, t, dur, sc):
    """jendela langit: gradien biru menguat, matahari bersinar, molekul udara melayang."""
    ac = _aksen(sc)
    u = _masuk(t, 0.15, 0.7)
    x0, y0, x1, y1 = 110, 720, 970, 1540
    cy = (y0 + y1) / 2
    s = 0.86 + 0.14 * u
    hx, hy = (x1 - x0) / 2 * s, (y1 - y0) / 2 * s
    X0, Y0, X1, Y1 = PX - hx, cy - hy, PX + hx, cy + hy
    rrect(img, X0 + 14, Y0 + 18, X1 + 14, Y1 + 18, 54, INK, 0.12 * u)
    # gradien langit ditempel lewat mask kotak membulat
    m, mx, my = rrect_mask(X0, Y0, X1, Y1, 54)
    k = eio(seg(t, 0.8, 3.2))
    atas = campur((226, 232, 240), ac, 0.25 + 0.55 * k)
    bawah = campur((246, 241, 232), terang(ac, 0.55), 0.3 + 0.5 * k)
    grad = np.linspace(0, 1, m.size[1])[:, None, None]
    arr = (np.array(atas)[None, None, :] * (1 - grad) + np.array(bawah)[None, None, :] * grad).astype(np.uint8)
    gimg = Image.fromarray(np.repeat(arr, m.size[0], axis=1), "RGB")
    img.paste(gimg, (mx, my), amask(m, u))
    matahari(img, X0 + hx * 0.55, Y0 + hy * 0.52, 62 * u, "#FFB020", t, u)
    rr = rng("langit", sc.get("id", ""))
    for i in range(26):
        bx = rr.uniform(X0 + 60, X1 - 60)
        by = rr.uniform(Y0 + 160, Y1 - 60)
        ph = rr.uniform(0, 6.28)
        xx = bx + math.sin(t * 0.9 + ph) * 22
        yy = by + math.cos(t * 0.7 + ph) * 16
        warna = ac if (i % 3 == 0 and k > 0.2) else PUTIH
        circ(img, xx, yy, 9 + 3 * math.sin(t * 2 + ph), warna, 0.85 * u)
    ring(img, PX, cy, 0, 1, INK, 0)  # no-op (jaga API)
    rrect_garis(img, X0, Y0, X1, Y1, 54, INK, 5, 0.9 * u)


def v_spektrum(img, t, dur, sc):
    """pita spektrum cahaya; pita 'sorot' berdenyut dan menghamburkan titik ke segala arah."""
    warna = ["#E8453C", "#FF8A2A", "#FFC928", "#3DBB5C", "#2F7BFF", "#4B4BD6", "#8A4FD8"]
    label = ["700", "620", "580", "530", "470", "440", "400"]
    sorot = int(sc.get("sorot", 4))
    n = len(warna)
    x0, x1 = 150, 930
    y_top, y_bot = 760, 1480
    lebar = (x1 - x0) / n
    for i in range(n):
        u = eob(seg(t, 0.2 + i * 0.07, 0.75 + i * 0.07))
        h = (y_bot - y_top) * u * (0.62 + 0.38 * (i + 1) / n)
        xa = x0 + i * lebar + 8
        xb = xa + lebar - 16
        denyut = 1 + (0.05 * math.sin(t * 6) if i == sorot else 0)
        rrect(img, xa, y_bot - h * denyut, xb, y_bot, 20, warna[i], 0.95 if i == sorot else 0.55)
        txt(img, label[i], (xa + xb) / 2, y_bot + 52, 28, "SB", MUTED, u, "ms")
    txt(img, "panjang gelombang (nm)", PX, y_bot + 100, 28, "M", MUTED, seg(t, 0.8, 1.3), "ms")
    # hamburan dari pita sorot
    cx = x0 + (sorot + 0.5) * lebar
    cy = y_top + 160
    k = seg(t, 1.2, 1.8)
    rr = rng("spek", sorot)
    for j in range(18):
        ang = rr.uniform(0, 2 * math.pi)
        spd = rr.uniform(120, 260)
        ph = (t * 0.6 + j / 18) % 1.0
        r = spd * ph
        circ(img, cx + math.cos(ang) * r, cy + math.sin(ang) * r * 0.8, 10 * (1 - ph) + 3, warna[sorot],
             k * (1 - ph) * 0.9)
    glow(img, cx, cy, 120, warna[sorot], 0.4 * k)


def v_angka(img, t, dur, sc):
    """angka besar bergulir (odometer) + satuan + label + cincin progres."""
    ac = _aksen(sc)
    nilai = float(sc.get("angka", 100))
    u = eo(seg(t, 0.4, min(dur * 0.55, 2.6)))
    a = seg(t, 0.2, 0.5)
    ring(img, PX, 1120, 330, 26, campur(CREAM, INK, 0.08), a)
    ring(img, PX, 1120, 330, 26, ac, a, 0, 360 * u)
    glow(img, PX, 1120, 360, ac, (0.16 + 0.06 * math.sin(t * 3.1)) * a)
    ang = t * 1.4  # titik mengorbit + garis putus berputar: tetap bergerak setelah hitungan selesai
    circ(img, PX + 330 * math.sin(ang), 1120 - 330 * math.cos(ang), 20, PUTIH, a)
    circ(img, PX + 330 * math.sin(ang), 1120 - 330 * math.cos(ang), 12, ac, a)
    for i in range(24):
        a0 = (i * 15 + t * 12) % 360
        ring(img, PX, 1120, 392, 6, ac, 0.25 * a, a0, a0 + 6)
    size = int(sc.get("angka_size", 150))
    try:
        import mesin_fx
        mesin_fx.odometer(img, nilai, PX, 1170, size, INK, a, "m", "B", u, int(sc.get("desimal", 0)))
    except ImportError:
        odometer(img, nilai, PX, 1170, size, INK, a, "m", "B", u, int(sc.get("desimal", 0)))
    if sc.get("satuan"):
        txt(img, sc["satuan"], PX, 1270, 54, "SB", ac, a, "ms")
    if sc.get("label"):
        paragraf(img, sc["label"], PX, 1530, 40, 800, "SB", INK, seg(t, 0.9, 1.4))


def v_banding(img, t, dur, sc):
    """dua (atau lebih) batang pembanding. sc['banding'] = [[label, nilai], ...]"""
    data = sc.get("banding", [["A", 30], ["B", 100]])
    ac = _aksen(sc)
    mx = max(v for _, v in data) or 1
    n = len(data)
    gap = 60
    bw = (820 - gap * (n - 1)) / n
    y_bot, hmax = 1450, 620
    for i, (lb, v) in enumerate(data):
        u = eob(seg(t, 0.3 + i * 0.35, 1.1 + i * 0.35))
        xa = 130 + i * (bw + gap)
        h = hmax * (v / mx) * u
        warna = ac if i == n - 1 else campur(ac, CREAM, 0.55)
        rrect(img, xa + 10, y_bot - h + 12, xa + bw + 10, y_bot + 12, 28, INK, 0.12 * u)
        rrect(img, xa, y_bot - h, xa + bw, y_bot, 28, warna, 1.0)
        if h > 60:  # kilau berjalan di batang (gerak terus, tidak pernah diam)
            ky = y_bot - h + ((t * 260 + i * 170) % max(h, 1))
            rrect(img, xa + 14, ky, xa + bw - 14, min(y_bot - 10, ky + 26), 13, PUTIH, 0.28 * u)
        if i == n - 1 and u > 0.5:
            glow(img, xa + bw / 2, y_bot - h, 170, warna, 0.16 + 0.08 * math.sin(t * 3.4))
        if u > 0.05:
            txt(img, format_id(v * min(1, u), 0 if float(v).is_integer() else 1), xa + bw / 2, y_bot - h - 30, 64, "B", INK,
                clamp(u), "ms")
        txt(img, lb, xa + bw / 2, y_bot + 70, 40, "SB", INK, seg(t, 0.3, 0.7), "ms")
    line(img, 110, y_bot + 2, 970, y_bot + 2, 6, INK, 0.8)


def v_ikon(img, t, dur, sc):
    """ikon besar di tengah + cincin berdenyut + titik orbit."""
    ac = _aksen(sc)
    u = _masuk(t, 0.2, 0.7)
    for k in range(3):
        ph = (t * 0.5 + k / 3) % 1.0
        ring(img, PX, PY, 170 + 230 * ph, 8, ac, 0.35 * (1 - ph) * u)
    circ(img, PX, PY, 250 * u, terang(ac, 0.82), 1.0)
    for i in range(6):
        ang = t * 0.7 + i * math.pi / 3
        circ(img, PX + math.cos(ang) * 330, PY + math.sin(ang) * 330, 12, ac, 0.8 * u)
    ikon(img, sc.get("ikon", "bintang"), PX, PY, 150 * u, ac, t, u)
    if sc.get("label"):
        paragraf(img, sc["label"], PX, 1540, 42, 820, "SB", INK, seg(t, 0.8, 1.3))


def v_orbit(img, t, dur, sc):
    ac = _aksen(sc)
    u = _masuk(t, 0.2, 0.7)
    cx, cy = PX, 1120
    rx, ry = 380, 150
    pts = [(cx + rx * math.cos(a_), cy + ry * math.sin(a_)) for a_ in np.linspace(0, 2 * math.pi, 120)]
    polyline(img, pts, 4, MUTED, 0.6 * u, tutup=True)
    ang = t * 1.1
    px, py = cx + rx * math.cos(ang), cy + ry * math.sin(ang)
    for k in range(14):
        a2 = ang - k * 0.06
        circ(img, cx + rx * math.cos(a2), cy + ry * math.sin(a2), 26 * (1 - k / 14), ac, 0.25 * (1 - k / 14) * u)
    depan = math.sin(ang) > 0
    if not depan:
        circ(img, px, py, 34 * u, ac, 1)
    matahari(img, cx, cy, 110 * u, "#FFB020", t, u)
    if depan:
        circ(img, px, py, 34 * u, ac, 1)
    if sc.get("label"):
        paragraf(img, sc["label"], PX, 1500, 42, 820, "SB", INK, seg(t, 0.8, 1.3))


def v_gelombang(img, t, dur, sc):
    ac = _aksen(sc)
    lam = [320, 200, 120]
    warna = [campur(ac, CREAM, 0.5), campur(ac, INK, 0.1), ac]
    for i, L in enumerate(lam):
        u = eo(seg(t, 0.2 + i * 0.3, 1.0 + i * 0.3))
        y = 860 + i * 250
        pts = gel_pts(120, 120 + 840 * u, y, 70, L, t * 5)
        if len(pts) > 1:
            polyline(img, pts, 12, warna[i], 1.0)
            circ(img, pts[-1][0], pts[-1][1], 14, warna[i], 1.0)
    if sc.get("label"):
        paragraf(img, sc["label"], PX, 1560, 42, 820, "SB", INK, seg(t, 0.8, 1.3))


def v_daftar(img, t, dur, sc):
    items = sc.get("items", ["Satu", "Dua", "Tiga"])
    ac = _aksen(sc)
    n = len(items)
    y0 = 1140 - (n - 1) * 115
    for i, it in enumerate(items):
        t0 = 0.3 + i * max(0.5, (dur * 0.6) / max(1, n))
        u = eob(seg(t, t0, t0 + 0.5))
        y = y0 + i * 230 + 4 * math.sin(t * 1.6 + i * 1.1) * seg(t, t0 + 0.5, t0 + 1.0)  # mengambang halus
        x = lerp(-300, 140, u)
        rrect(img, x + 10, y - 80 + 12, x + 790 + 10, y + 80 + 12, 40, INK, 0.12 * u)
        rrect(img, x, y - 80, x + 790, y + 80, 40, PUTIH, u, INK, 5)
        ph = (t * 0.6 + i * 0.33) % 1.0  # denyut cincin di lingkaran centang
        ring(img, x + 95, y, 52 + 34 * ph, 5, ac, 0.45 * (1 - ph) * seg(t, t0 + 0.6, t0 + 0.9))
        circ(img, x + 95, y, 52, ac, u)
        centang(img, x + 95, y + 4, 62, PUTIH, 13, seg(t, t0 + 0.25, t0 + 0.6), u)
        txt(img, it, x + 180, y, 46, "SB", INK, u, "lm")


def v_peringatan(img, t, dur, sc):
    """panel peringatan (topik kesehatan: 'bukan pengganti dokter')."""
    ac = col(sc.get("accent", "#F0454A"))
    u = _masuk(t, 0.2, 0.6)
    cy = 1080
    tri = [(PX, cy - 250 * u), (PX + 250 * u, cy + 190 * u), (PX - 250 * u, cy + 190 * u)]
    poly(img, [(x + 12, y + 14) for x, y in tri], INK, 0.15)
    poly(img, tri, ac, 1)
    txt(img, "!", PX, cy + 40, int(260 * max(u, 0.1)), "B", PUTIH, u, "mm", catat=False)
    pesan = sc.get("pesan", "Bukan pengganti dokter")
    paragraf(img, pesan, PX, 1420, 50, 820, "B", INK, seg(t, 0.6, 1.0))
    glow(img, PX, cy, 330, ac, 0.15 + 0.08 * math.sin(t * 4))


def v_rangkuman(img, t, dur, sc):
    """grid ikon + label untuk adegan rangkuman. sc['items'] = [[ikon, label], ...]"""
    items = sc.get("items", [["bintang", "Satu"], ["centang", "Dua"], ["hati", "Tiga"], ["petir", "Empat"]])
    ac = _aksen(sc)
    n = len(items)
    cols = 2 if n <= 4 else 3
    rows = int(math.ceil(n / cols))
    cw, chh = 820 / cols, 820 / max(rows, 2)
    cadangan = ["bintang", "centang", "kilau", "petir", "hati", "atom"]
    items = [it if isinstance(it, (list, tuple)) else [cadangan[k % len(cadangan)], str(it)]
             for k, it in enumerate(items)]
    for i, (ik, lb) in enumerate(items):
        r_, c_ = divmod(i, cols)
        cx = 130 + cw * (c_ + 0.5)
        cy = 760 + chh * (r_ + 0.5)
        t0 = 0.25 + i * 0.35
        u = eob(seg(t, t0, t0 + 0.5))
        rrect(img, cx - cw * 0.44 + 8, cy - chh * 0.42 + 10, cx + cw * 0.44 + 8, cy + chh * 0.42 + 10, 36, INK, 0.1 * u)
        rrect(img, cx - cw * 0.44, cy - chh * 0.42, cx + cw * 0.44, cy + chh * 0.42, 36, PUTIH, u, INK, 4)
        ikon(img, ik, cx, cy - 40, 70 * u, ac, t, u)
        txt(img, lb, cx, cy + chh * 0.28, 34, "SB", INK, u, "ms")


VISUALS = {
    "langit": v_langit, "spektrum": v_spektrum, "angka": v_angka, "banding": v_banding, "ikon": v_ikon,
    "orbit": v_orbit, "gelombang": v_gelombang, "daftar": v_daftar, "peringatan": v_peringatan,
    "rangkuman": v_rangkuman,
}


def daftar_visual():
    return sorted(VISUALS)


# ============================================================================ selftest
def _kanvas(ss):
    return Image.new("RGB", (int(round(W0 * ss)), int(round(H0 * ss))), CREAM)


def _uji(ss=1.0):
    set_ss(ss)
    sys.path.insert(0, str(ROOT))
    from mesin_util import sheet
    try:
        import mesin_v11  # noqa: F401  (mendaftarkan visual v11 + episode)
    except ImportError:
        pass
    ok = True
    imgs, labels = [], []
    contoh = {"accent": "#2F7BFF", "id": "uji", "angka": 12345, "satuan": "km", "label": "Label contoh",
              "banding": [["Kecil", 20], ["Besar", 75]], "items": ["Satu", "Dua", "Tiga"], "ikon": "bintang"}
    print(f"{'visual':<16}{'ms/frame':>9}  status")
    for nama in daftar_visual():
        fn = VISUALS[nama]
        dur = 6.0
        frames = []
        err = []
        t0 = time.time()
        for t in (0.3, 1.2, 2.5, 3.5, 5.8):
            KOTAK_TEKS.clear()
            im = _kanvas(ss)
            try:
                fn(im, t, dur, dict(contoh))
            except Exception as e:  # noqa: BLE001
                err.append(f"t={t}: {type(e).__name__}: {e}")
                break
            frames.append(im)
            for (x0, y0, x1, y1, s) in KOTAK_TEKS:
                if y1 > 1640 or x0 < 40 or x1 > 1040 or (x1 > 950 and y1 > 1100 and y0 < 1700):
                    err.append(f"teks '{s[:18]}' di zona terlarang ({x0:.0f},{y0:.0f},{x1:.0f},{y1:.0f})")
        ms = (time.time() - t0) / max(1, len(frames)) * 1000
        if len(frames) == 5:
            arr = [np.asarray(f, dtype=np.int16) for f in frames]
            if np.abs(arr[4] - np.asarray(_kanvas(ss), np.int16)).max() < 30:
                err.append("tidak menggambar apa pun")
            # gerak: t=2.5 vs 3.5 DAN t=3.5 vs 5.8 (setelah animasi masuk selesai) harus beda
            if np.abs(arr[2] - arr[3]).max() < 12 or np.abs(arr[3] - arr[4]).max() < 12:
                err.append("diam > 1 detik")
            imgs.append(frames[3])
            labels.append(nama)
        ok &= not err
        print(f"{nama:<16}{ms:9.0f}  {'OK' if not err else 'GAGAL: ' + '; '.join(sorted(set(err))[:3])}")
    if imgs:
        out = ROOT / "build" / "diagrams_selftest.jpg"
        sheet(imgs, labels, cols=5, lebar=260, judul="diagrams.py selftest (t=3.5 s)", path=out)
        print(f"montase: {out}")
    print("DIAGRAMS SELFTEST:", "LULUS" if ok else "GAGAL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(_uji(float(sys.argv[1]) if len(sys.argv) > 1 else 1.0))
