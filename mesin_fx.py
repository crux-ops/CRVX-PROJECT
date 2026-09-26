#!/usr/bin/env python3
"""mesin_fx.py - lapisan FX 2026 bersama (Shorts + Long). numpy + PIL saja.

Finishing per frame: bloom ADAPTIF (dua skala) -> grade (preset krem/sinema/netral) -> lensa (aberasi kromatik
radial tipis) -> vinyet -> grain film deterministik per frame.
Gerak: zoom_blur, blur_arah, nois (derau 1D halus untuk kamera organik), spring.
Material: mesh_latar, glow_sprite (tepi nol), bayang lembut, kaca_cair, kilau, bokeh.
Transisi (fase keluar/masuk, 0..1): zoomthru, whip, tinta, iris, cahaya, split, bands, rise, slide, glitch, punch, zoom.
Saklar: KT_FX=0 (matikan finishing), KT_BLOOM (kekuatan bloom, bawaan 1.0).
"""
import math
import os
from functools import lru_cache

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

FX_ON = os.environ.get("KT_FX", "1") != "0"
BLOOM_K = float(os.environ.get("KT_BLOOM", "1.0"))


# ---------------------------------------------------------------- matematika gerak

def clamp(v, a=0.0, b=1.0):
    return a if v < a else b if v > b else v


def spring(t, zeta=0.35, omega=14.0):
    """Respons pegas teredam 0->1 (overshoot ringan). t detik."""
    if t <= 0:
        return 0.0
    wd = omega * math.sqrt(max(1e-6, 1 - zeta * zeta))
    return 1 - math.exp(-zeta * omega * t) * (math.cos(wd * t) + zeta * omega / wd * math.sin(wd * t))


_NOIS_TABLE = np.random.default_rng(7).standard_normal(4096).astype(np.float32)


def nois(t, seed=0, speed=1.0):
    """Derau 1D halus (interpolasi kosinus tabel tetap) di rentang kira-kira -1..1. Deterministik."""
    x = t * speed + seed * 97.31
    i = int(math.floor(x))
    f = x - i
    f = 0.5 - 0.5 * math.cos(math.pi * f)
    a = _NOIS_TABLE[i % 4096]
    b = _NOIS_TABLE[(i + 1) % 4096]
    return float((a + (b - a) * f) * 0.6)


# ---------------------------------------------------------------- latar

def _lerp_rgb(a, b, u):
    return tuple(int(round(a[i] + (b[i] - a[i]) * u)) for i in range(3))


def mesh_latar(w, h, t, base=(246, 241, 232), accent=(228, 87, 46), strength=0.10, seed=1):
    """Mesh gradient bergerak: beberapa blob warna aksen lembut di atas warna dasar, dihitung di resolusi kecil."""
    sw, sh = 96, 96 * h // w
    ys, xs = np.mgrid[0:sh, 0:sw].astype(np.float32)
    xs /= sw
    ys /= sh
    img = np.zeros((sh, sw, 3), dtype=np.float32) + np.array(base, dtype=np.float32)
    acc = np.array(accent, dtype=np.float32)
    cols = [acc, np.array([255, 255, 255], dtype=np.float32), acc * 0.5 + np.array(base) * 0.5]
    for k in range(3):
        cx = 0.5 + 0.42 * nois(t * 0.11, seed + k * 3)
        cy = 0.5 + 0.42 * nois(t * 0.09, seed + k * 3 + 1)
        r = 0.32 + 0.1 * nois(t * 0.07, seed + k * 3 + 2)
        d2 = (xs - cx) ** 2 + (ys - cy) ** 2
        a = np.exp(-d2 / (2 * r * r)) * (strength if k != 1 else strength * 1.6)
        img = img * (1 - a[..., None]) + cols[k] * a[..., None]
    small = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    return small.resize((w, h), Image.BICUBIC)


# ---------------------------------------------------------------- sprite & material

@lru_cache(maxsize=64)
def glow_sprite(radius, color, power=1.6):
    """Sprite glow radial RGBA dengan tepi NOL (numpy), ter-cache."""
    r = int(radius)
    n = 2 * r + 1
    y, x = np.mgrid[-r:r + 1, -r:r + 1].astype(np.float32)
    d = np.sqrt(x * x + y * y) / max(1, r)
    a = np.clip(1 - d, 0, 1) ** power
    a[d >= 1] = 0
    rgba = np.zeros((n, n, 4), dtype=np.uint8)
    rgba[..., 0] = color[0]
    rgba[..., 1] = color[1]
    rgba[..., 2] = color[2]
    rgba[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def glow(img, xy, radius, color, alpha=1.0):
    """Tempel glow aditif-lembut di img (RGB) pada pusat xy."""
    sp = glow_sprite(int(radius), tuple(color))
    if alpha < 1:
        a = sp.getchannel("A").point(lambda v: int(v * alpha))
        sp = sp.copy()
        sp.putalpha(a)
    x, y = int(xy[0] - radius), int(xy[1] - radius)
    img.paste(sp, (x, y), sp)


@lru_cache(maxsize=32)
def _shadow_sprite(w, h, rad, blur, alpha):
    pad = blur * 3
    im = Image.new("L", (w + 2 * pad, h + 2 * pad), 0)
    ImageDraw.Draw(im).rounded_rectangle((pad, pad, pad + w, pad + h), rad, fill=int(255 * alpha))
    return im.filter(ImageFilter.GaussianBlur(float(blur))), pad


def bayang(img, box, rad, blur=18, alpha=0.22, offset=(0, 10), color=(24, 24, 31)):
    """Bayangan lembut ter-cache untuk panel persegi membulat."""
    x0, y0, x1, y1 = [int(v) for v in box]
    m, pad = _shadow_sprite(x1 - x0, y1 - y0, int(rad), int(blur), round(alpha, 2))
    col = Image.new("RGB", m.size, color)
    img.paste(col, (x0 - pad + offset[0], y0 - pad + offset[1]), m)


def kaca_cair(img, box, rad, tint=(255, 255, 255), tint_a=0.35, blur=14, t=0.0):
    """Liquid Glass: area latar diburamkan + sedikit dibiaskan, lapisan tint, kilap tepi, sapuan kilau bergerak."""
    x0, y0, x1, y1 = [int(v) for v in box]
    ext = 24
    crop = img.crop((x0 - ext, y0 - ext, x1 + ext, y1 + ext)).filter(ImageFilter.GaussianBlur(float(blur)))
    # pembiasan: geser sedikit isi sesuai gradien vertikal (murah: offset 2 px)
    crop = ImageChops.blend(crop, ImageChops.offset(crop, 2, 3), 0.5)
    w, h = x1 - x0, y1 - y0
    mask = Image.new("L", (w + 2 * ext, h + 2 * ext), 0)
    ImageDraw.Draw(mask).rounded_rectangle((ext, ext, ext + w, ext + h), rad, fill=255)
    tinted = Image.blend(crop, Image.new("RGB", crop.size, tint), tint_a)
    img.paste(tinted, (x0 - ext, y0 - ext), mask)
    # kilap tepi + kilau bergerak
    ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.rounded_rectangle((1, 1, w - 2, h - 2), rad, outline=(255, 255, 255, 150), width=2)
    d.rounded_rectangle((3, 3, w - 4, h - 4), rad - 2 if rad > 2 else rad, outline=(255, 255, 255, 60), width=1)
    p = (t * 0.25) % 1.6 - 0.3
    sx = int(p * (w + h))
    d.polygon([(sx, 0), (sx + 60, 0), (sx + 60 - h, h), (sx - h, h)], fill=(255, 255, 255, 40))
    ov.putalpha(ImageChops.multiply(ov.getchannel("A"), mask.crop((ext, ext, ext + w, ext + h))))
    img.paste(ov, (x0, y0), ov)


def kilau(img, xy, size, color=(255, 255, 255), alpha=1.0, rot=0.0):
    """Bintang kilau 4 sisi (bentuk, bukan glyph)."""
    x, y = xy
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    pts = []
    for i in range(8):
        a = rot + i * math.pi / 4
        r = size if i % 2 == 0 else size * 0.22
        pts.append((x + r * math.cos(a), y + r * math.sin(a)))
    d.polygon(pts, fill=color + (int(255 * alpha),))
    img.paste(ov, (0, 0), ov)


def bokeh(img, t, n=14, color=(255, 255, 255), seed=3, area=None, rmax=60, alpha=0.35, speed=1.0):
    """Lingkaran bokeh 2.5D melayang pelan (paralaks menurut ukuran)."""
    W, H = img.size
    x0, y0, x1, y1 = area or (0, 0, W, H)
    rng = np.random.default_rng(seed)
    for i in range(n):
        r = rng.uniform(0.25, 1.0)
        bx = rng.uniform(x0, x1) + 40 * nois(t * 0.2 * speed, seed * 10 + i) * (1.5 - r)
        by = (rng.uniform(y0, y1) - t * 12 * speed * r - y0) % (y1 - y0) + y0
        glow(img, (bx, by), int(rmax * r), color, alpha * (0.4 + 0.6 * r))


# ---------------------------------------------------------------- blur gerak

def zoom_blur(img, strength=0.06, steps=6, center=None):
    W, H = img.size
    cx, cy = center or (W / 2, H / 2)
    acc = np.asarray(img, dtype=np.float32)
    for i in range(1, steps + 1):
        s = 1 + strength * i / steps
        sub = img.resize((int(W * s), int(H * s)), Image.BILINEAR)
        ox, oy = int(cx * s - cx), int(cy * s - cy)
        sub = sub.crop((ox, oy, ox + W, oy + H))
        acc += np.asarray(sub, dtype=np.float32)
    return Image.fromarray(np.clip(acc / (steps + 1), 0, 255).astype(np.uint8))


def blur_arah(img, dx, dy, steps=6):
    acc = np.asarray(img, dtype=np.float32)
    for i in range(1, steps + 1):
        f = i / steps
        acc += np.asarray(ImageChops.offset(img, int(dx * f), int(dy * f)), dtype=np.float32)
    return Image.fromarray(np.clip(acc / (steps + 1), 0, 255).astype(np.uint8))


# ---------------------------------------------------------------- finishing

@lru_cache(maxsize=4)
def _vinyet_mask(w, h, strength):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = (x / w - 0.5) * 2
    ny = (y / h - 0.5) * 2
    d = np.sqrt(nx * nx * 0.8 + ny * ny)
    m = 1 - strength * np.clip((d - 0.55) / 0.9, 0, 1) ** 1.6
    return m[..., None]


@lru_cache(maxsize=1)
def _grain_tile(n=512):
    return np.random.default_rng(11).standard_normal((n, n)).astype(np.float32)


@lru_cache(maxsize=8)
def _grade_lut(preset):
    x = np.arange(256, dtype=np.float32) / 255
    if preset == "krem":
        # kurva S sangat ringan + split toning (bayangan sedikit dingin, sorotan hangat)
        s = x + 0.045 * np.sin(2 * math.pi * (x - 0.5)) * -1
        s = np.clip(s, 0, 1)
        r = np.clip(s + 0.010 * (x ** 2), 0, 1)
        g = s
        b = np.clip(s + 0.012 * (1 - x) ** 2 - 0.006 * x ** 2, 0, 1)
    elif preset == "sinema":
        s = np.clip(x + 0.09 * np.sin(2 * math.pi * (x - 0.5)) * -1, 0, 1)
        r = np.clip(s + 0.02 * x ** 2, 0, 1)
        g = s
        b = np.clip(s + 0.03 * (1 - x) ** 2, 0, 1)
    else:
        r = g = b = x
    return np.stack([r, g, b], axis=0) * 255


def bloom(img, k=1.0):
    """Bloom adaptif dua skala: adegan terang -> ambang naik & kekuatan turun (tidak membakar krem/putih)."""
    if k <= 0:
        return img
    W, H = img.size
    small = img.resize((W // 4, H // 4), Image.BILINEAR)
    a = np.asarray(small, dtype=np.float32)
    lum = a.mean(axis=2)
    mean = float(lum.mean()) / 255
    thr = 170 + 60 * clamp((mean - 0.5) / 0.4)   # adegan krem terang -> ambang ~215
    strength = 0.22 * (1 - 0.6 * clamp((mean - 0.5) / 0.4)) * k
    m = np.clip((lum - thr) / (255 - thr), 0, 1)
    hi = Image.fromarray(np.clip(a * m[..., None], 0, 255).astype(np.uint8))
    b1 = hi.filter(ImageFilter.GaussianBlur(4.0))
    b2 = hi.filter(ImageFilter.GaussianBlur(14.0))
    bl = ImageChops.add(b1, b2, scale=2.0).resize((W, H), Image.BILINEAR)
    return Image.blend(img, ImageChops.add(img, bl), strength)


def lensa(img, amount=1.5):
    """Aberasi kromatik radial tipis: kanal R/B digeser ke luar hanya di pinggir (mask radial)."""
    W, H = img.size
    r, g, b = img.split()
    s = 1 + amount / 1000
    def scl(ch, s_):
        w2, h2 = int(W * s_), int(H * s_)
        c = ch.resize((w2, h2), Image.BILINEAR)
        return c.crop(((w2 - W) // 2, (h2 - H) // 2, (w2 - W) // 2 + W, (h2 - H) // 2 + H))
    r2 = scl(r, s)
    # b tidak digeser (murah); mask radial mencampur r asli vs r2 di pinggir
    m = _lensa_mask(W, H)
    r = Image.composite(r2, r, m)
    return Image.merge("RGB", (r, g, b))


@lru_cache(maxsize=4)
def _lensa_mask(w, h):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((x / w - 0.5) * 2) ** 2 + ((y / h - 0.5) * 2) ** 2)
    m = np.clip((d - 0.5) / 0.7, 0, 1) ** 1.5
    return Image.fromarray((m * 255).astype(np.uint8))


def finishing(img, preset="krem", frame=0, grain=0.018, vinyet_k=0.16, bloom_k=None):
    if not FX_ON:
        return img
    W, H = img.size
    img = bloom(img, BLOOM_K if bloom_k is None else bloom_k)
    img = lensa(img)
    lut = _grade_lut(preset)
    img = img.point([int(round(v)) for v in np.concatenate([lut[0], lut[1], lut[2]])])
    a = np.asarray(img, dtype=np.float32)
    a *= _vinyet_mask(W, H, round(vinyet_k, 3))
    if grain > 0:
        g = _grain_tile()
        n = g.shape[0]
        ox, oy = (frame * 131) % n, (frame * 71) % n
        tile = np.roll(np.roll(g, ox, axis=1), oy, axis=0)
        reps = (H // n + 1, W // n + 1)
        big = np.tile(tile, reps)[:H, :W]
        a += big[..., None] * (grain * 255)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


# ---------------------------------------------------------------- transisi (A = adegan keluar, B = adegan masuk, u 0..1)

def _ease(u):
    return u * u * (3 - 2 * u)


def trans_zoomthru(A, B, u):
    W, H = A.size
    if u < 0.5:
        s = 1 + 0.9 * _ease(u * 2)
        img = zoom_blur(A, 0.05 + 0.15 * u * 2, 5)
        img = img.resize((int(W * s), int(H * s)), Image.BILINEAR).crop(((int(W * s) - W) // 2, (int(H * s) - H) // 2,
                                                                          (int(W * s) - W) // 2 + W, (int(H * s) - H) // 2 + H))
        return Image.blend(img, Image.new("RGB", (W, H), (255, 255, 255)), 0.7 * (u * 2) ** 2)
    v = (u - 0.5) * 2
    s = 1.6 - 0.6 * _ease(v)
    img = zoom_blur(B, 0.15 * (1 - v), 5)
    img = img.resize((int(W * s), int(H * s)), Image.BILINEAR).crop(((int(W * s) - W) // 2, (int(H * s) - H) // 2,
                                                                      (int(W * s) - W) // 2 + W, (int(H * s) - H) // 2 + H))
    return Image.blend(img, Image.new("RGB", (W, H), (255, 255, 255)), 0.7 * (1 - v) ** 2)


def trans_whip(A, B, u):
    W, H = A.size
    e = _ease(u)
    dx = int(-W * e)
    canvas = Image.new("RGB", (W, H))
    canvas.paste(A, (dx, 0))
    canvas.paste(B, (dx + W, 0))
    k = math.sin(math.pi * u)
    return blur_arah(canvas, int(-70 * k), 0, 5) if k > 0.15 else canvas


def trans_slide(A, B, u):
    W, H = A.size
    e = _ease(u)
    dy = int(-H * e)
    canvas = Image.new("RGB", (W, H))
    canvas.paste(A, (0, dy))
    canvas.paste(B, (0, dy + H))
    return canvas


def trans_tinta(A, B, u, seed=5):
    """Wipe tepi bergelombang (tinta) dari bawah ke atas."""
    W, H = A.size
    x = np.arange(W, dtype=np.float32) / W
    edge = H * (1 - u * 1.3) + H * 0.12 * (np.sin(x * 9 + seed) * 0.6 + np.sin(x * 23 + seed * 2) * 0.4)
    y = np.arange(H, dtype=np.float32)[:, None]
    m = np.clip((y - edge[None, :]) / 18 + 0.5, 0, 1)
    mask = Image.fromarray((m * 255).astype(np.uint8))
    out = Image.composite(B, A, mask)
    # tepi tinta: garis gelap tipis
    edge_m = Image.fromarray((np.clip(1 - np.abs(y - edge[None, :]) / 10, 0, 1) * 255).astype(np.uint8))
    out.paste(Image.new("RGB", (W, H), (24, 24, 31)), (0, 0), edge_m)
    return out


def trans_iris(A, B, u):
    W, H = A.size
    m = Image.new("L", (W, H), 0)
    r = _ease(u) * math.hypot(W, H) * 0.55
    ImageDraw.Draw(m).ellipse((W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r), fill=255)
    m = m.filter(ImageFilter.GaussianBlur(6.0))
    return Image.composite(B, A, m)


def trans_cahaya(A, B, u):
    """Light leak: kilat hangat menyapu, silang di puncaknya."""
    W, H = A.size
    base = Image.blend(A, B, _ease(u))
    k = math.sin(math.pi * u)
    leak = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(leak)
    cx = int(W * (u * 1.4 - 0.2))
    d.rectangle((0, 0, W, H), fill=(int(255 * k * 0.55), int(200 * k * 0.55), int(120 * k * 0.55)))
    out = ImageChops.add(base, leak)
    glow(out, (cx, H * 0.35), int(W * 0.6), (255, 240, 200), 0.8 * k)
    return out


def trans_split(A, B, u):
    W, H = A.size
    e = _ease(u)
    canvas = B.copy()
    top = A.crop((0, 0, W, H // 2))
    bot = A.crop((0, H // 2, W, H))
    canvas.paste(top, (0, int(-H / 2 * e)))
    canvas.paste(bot, (0, int(H / 2 + H / 2 * e)))
    return canvas


def trans_bands(A, B, u, n=6):
    W, H = A.size
    canvas = B.copy()
    bh = H // n + 1
    for i in range(n):
        ui = clamp((u * 1.6 - i * 0.1))
        band = A.crop((0, i * bh, W, (i + 1) * bh))
        dx = int((W if i % 2 == 0 else -W) * _ease(ui))
        canvas.paste(band, (dx, i * bh))
    return canvas


def trans_rise(A, B, u):
    W, H = A.size
    e = _ease(u)
    canvas = A.copy()
    s = 0.9 + 0.1 * e
    b = B.resize((int(W * s), int(H * s)), Image.BILINEAR)
    canvas.paste(b, ((W - b.width) // 2, int(H * (1 - e)) + (H - b.height) // 2 * int(e > 0.99)))
    return canvas


def trans_glitch(A, B, u, seed=9):
    W, H = A.size
    rng = np.random.default_rng(seed + int(u * 40))
    canvas = B.copy() if u > 0.5 else A.copy()
    src = A if u > 0.5 else B
    k = math.sin(math.pi * u)
    for _ in range(int(3 + 10 * k)):
        y0 = int(rng.uniform(0, H))
        h = int(rng.uniform(8, 70))
        dx = int(rng.uniform(-90, 90) * k)
        canvas.paste(src.crop((0, y0, W, y0 + h)), (dx, y0))
    if k > 0.3:
        r, g, b = canvas.split()
        canvas = Image.merge("RGB", (ImageChops.offset(r, int(6 * k), 0), g, ImageChops.offset(b, int(-6 * k), 0)))
    return canvas


def trans_punch(A, B, u):
    W, H = A.size
    if u < 0.35:
        s = 1 + 0.12 * (u / 0.35)
        a = A.resize((int(W * s), int(H * s)), Image.BILINEAR)
        return a.crop(((a.width - W) // 2, (a.height - H) // 2, (a.width - W) // 2 + W, (a.height - H) // 2 + H))
    v = (u - 0.35) / 0.65
    s = 1.15 - 0.15 * _ease(v)
    b = B.resize((int(W * s), int(H * s)), Image.BILINEAR)
    return b.crop(((b.width - W) // 2, (b.height - H) // 2, (b.width - W) // 2 + W, (b.height - H) // 2 + H))


def trans_zoom(A, B, u):
    W, H = A.size
    e = _ease(u)
    s = 1 + 0.25 * e
    a = A.resize((int(W * s), int(H * s)), Image.BILINEAR)
    a = a.crop(((a.width - W) // 2, (a.height - H) // 2, (a.width - W) // 2 + W, (a.height - H) // 2 + H))
    return Image.blend(a, B, e)


def trans_speed(A, B, u):
    k = math.sin(math.pi * u)
    base = Image.blend(A, B, _ease(u))
    return blur_arah(base, 0, int(-120 * k), 6) if k > 0.1 else base


def trans_glint(A, B, u):
    W, H = A.size
    base = Image.blend(A, B, _ease(u))
    k = math.sin(math.pi * u)
    x = int(W * (-0.3 + 1.6 * u))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(ov).polygon([(x, 0), (x + 120, 0), (x + 120 - H * 0.4, H), (x - H * 0.4, H)],
                               fill=(255, 255, 255, int(200 * k)))
    base.paste(ov, (0, 0), ov)
    return base


TRANSISI = {
    "zoomthru": trans_zoomthru, "whip": trans_whip, "slide": trans_slide, "tinta": trans_tinta, "iris": trans_iris,
    "cahaya": trans_cahaya, "split": trans_split, "bands": trans_bands, "rise": trans_rise, "glitch": trans_glitch,
    "punch": trans_punch, "zoom": trans_zoom, "speed": trans_speed, "glint": trans_glint,
}
URUTAN_TRANSISI = ["zoomthru", "tinta", "cahaya", "speed", "glint", "split", "zoom", "bands", "iris", "rise",
                   "punch", "slide", "glitch", "whip"]
SFX_TRANSISI = {
    "zoomthru": "whoosh", "whip": "swish", "slide": "swish_up", "tinta": "swish", "iris": "pop", "cahaya": "kilau",
    "split": "swish", "bands": "glitch", "rise": "swish_up", "glitch": "glitch", "punch": "impact", "zoom": "whoosh",
    "speed": "whoosh", "glint": "kilau",
}


def _selftest():
    W, H = 360, 640
    A = Image.new("RGB", (W, H), (246, 241, 232))
    ImageDraw.Draw(A).ellipse((60, 160, 300, 400), fill=(228, 87, 46))
    B = Image.new("RGB", (W, H), (200, 230, 255))
    ImageDraw.Draw(B).rectangle((80, 200, 280, 440), fill=(24, 24, 31))
    os.makedirs("build", exist_ok=True)
    sheet = Image.new("RGB", (W * 5, H * 3), (0, 0, 0))
    for i, name in enumerate(URUTAN_TRANSISI):
        out = TRANSISI[name](A, B, 0.45)
        assert out.size == (W, H), name
        sheet.paste(out, ((i % 5) * W, (i // 5) * H))
    f = finishing(mesh_latar(W, H, 1.0), "krem", 3)
    assert f.size == (W, H)
    sheet.paste(f, (4 * W, 2 * H))
    sheet.save("build/fx_selftest.jpg", quality=80)
    print("mesin_fx selftest OK -> build/fx_selftest.jpg")


if __name__ == "__main__":
    _selftest()
