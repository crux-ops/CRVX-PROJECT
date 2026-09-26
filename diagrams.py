#!/usr/bin/env python3
"""diagrams.py - primitif gambar objek + registry VISUALS (nama -> fungsi(img, t, dur, sc)).

Gaya: elemen BESAR, label polos, selalu ada gerak (tidak ada frame diam > 1 detik), warna aksen adegan.
Modul episode (mesin_v11_epNN) mendaftarkan visualnya ke VISUALS lewat `register(nama)(fn)`.
`python3 diagrams.py` = selftest: render semua visual di beberapa t -> build/diagrams_selftest.jpg
"""
import math
import os

import render as R
from render import INK, MUTED, WHITE, CREAM, S, clamp, eo, eio, eob, seg, mix

VISUALS = {}


def register(name):
    def deco(fn):
        VISUALS[name] = fn
        return fn
    return deco


def get(name):
    return VISUALS.get(name)


# --------------------------------------------------------------- objek anatomi & ikon (koordinat desain)

def lungs(img, c, w, expand=0.0, color=(233, 128, 110), alpha=1.0, outline=INK):
    """Sepasang paru-paru sederhana (dua lobus membulat). expand 0..1 = mengembang."""
    x, y = c
    k = 1 + 0.10 * expand
    lw, lh = w * 0.42 * k, w * 0.62 * k
    gap = w * 0.06
    for sgn in (-1, 1):
        cx = x + sgn * (gap + lw / 2)
        pts = []
        for i in range(40):
            a = -math.pi / 2 + i * 2 * math.pi / 40
            # bentuk lonjong, sedikit lebih lebar di bawah
            rx = lw / 2 * (1 + 0.18 * math.sin(a)) if math.sin(a) > 0 else lw / 2 * 0.85
            ry = lh / 2
            pts.append((cx + rx * math.cos(a), y + ry * math.sin(a)))
        R.poly(img, pts, fill=color, outline=None, alpha=alpha)
        R.line(img, pts + [pts[0]], outline, 5, alpha)
        # garis bronkus
        for j in range(3):
            yy = y - lh * 0.25 + j * lh * 0.22
            R.line(img, [(cx - sgn * lw * 0.05, yy), (cx + sgn * lw * 0.28, yy + lh * 0.08)], mix(color, INK, 0.35), 4, alpha)
    # trakea
    R.rrect(img, (x - w * 0.045, y - lh / 2 - w * 0.22, x + w * 0.045, y - lh * 0.1), w * 0.04, fill=(240, 222, 210), outline=INK, width=4, alpha=alpha)
    for j in range(4):
        yy = y - lh / 2 - w * 0.18 + j * w * 0.07
        R.line(img, [(x - w * 0.045, yy), (x + w * 0.045, yy)], INK, 3, alpha)


def dome(img, c, w, sag=0.0, color=(228, 87, 46), alpha=1.0, thick=26, spasm=0.0):
    """Diafragma: lembaran kubah. sag 0 = kubah tinggi (hembus), 1 = turun/mendatar (hirup). spasm = kedutan."""
    x, y = c
    h = w * (0.24 - 0.16 * sag)
    pts = []
    for i in range(41):
        u = i / 40
        xx = x - w / 2 + u * w
        yy = y - h * math.sin(math.pi * u)
        if spasm > 0:
            yy += spasm * w * 0.05 * math.sin(u * math.pi * 6) * math.sin(math.pi * u)
        pts.append((xx, yy))
    R.line(img, pts, color, thick, alpha)
    R.line(img, pts, mix(color, WHITE, 0.4), max(2, thick * 0.25), alpha)


def stomach(img, c, w, full=0.5, color=(244, 162, 89), alpha=1.0):
    """Lambung: kantung membulat, tingkat isi 0..1."""
    x, y = c
    box = (x - w / 2, y - w * 0.36, x + w / 2, y + w * 0.36)
    R.rrect(img, box, w * 0.3, fill=mix(color, WHITE, 0.35), outline=INK, width=5, alpha=alpha)
    # isi (gelombang)
    if full > 0:
        lvl = box[3] - (box[3] - box[1]) * clamp(full)
        pts = [(box[0] + i / 24 * w, lvl + 6 * math.sin(i * 0.8)) for i in range(25)]
        pts = [(max(box[0], min(box[2], px)), py) for px, py in pts]
        R.poly(img, pts + [(box[2], box[3]), (box[0], box[3])], fill=color, alpha=alpha * 0.85)
        R.rrect(img, box, w * 0.3, outline=INK, width=5, alpha=alpha)


def thermometer(img, c, h, level=0.5, color=(215, 38, 61), alpha=1.0):
    x, y = c
    w = h * 0.22
    R.rrect(img, (x - w / 2, y - h / 2, x + w / 2, y + h / 2 - w * 0.6), w / 2, fill=WHITE, outline=INK, width=5, alpha=alpha)
    R.circ(img, (x, y + h / 2 - w * 0.2), w * 0.75, fill=color, outline=INK, width=5, alpha=alpha)
    top = y - h / 2 + w * 0.6
    bot = y + h / 2 - w * 0.6
    lv = bot - (bot - top) * clamp(level)
    R.rrect(img, (x - w * 0.2, lv, x + w * 0.2, bot + w * 0.3), w * 0.2, fill=color, alpha=alpha)
    for j in range(5):
        yy = top + j * (bot - top) / 4
        R.line(img, [(x + w * 0.6, yy), (x + w * 0.95, yy)], INK, 3, alpha)


def glass_soda(img, c, h, fizz=0.0, t=0.0, color=(46, 134, 171), alpha=1.0):
    x, y = c
    w = h * 0.6
    pts = [(x - w / 2, y - h / 2), (x + w / 2, y - h / 2), (x + w * 0.38, y + h / 2), (x - w * 0.38, y + h / 2)]
    R.poly(img, pts, fill=mix(color, WHITE, 0.75), alpha=alpha)
    R.line(img, pts + [pts[0]], INK, 5, alpha)
    lvl = y - h * 0.25
    R.poly(img, [(x - w * 0.47, lvl), (x + w * 0.47, lvl), (x + w * 0.38, y + h / 2), (x - w * 0.38, y + h / 2)], fill=color, alpha=alpha * 0.8)
    for i in range(10):
        p = (t * (0.5 + 0.1 * i) + i * 0.37) % 1.0
        bx = x - w * 0.3 + (i * 0.11 % 1) * w * 0.6
        by = y + h / 2 - p * (h / 2 + lvl - y + h * 0.3 * fizz)
        R.circ(img, (bx, by), 5 + 3 * (i % 3), outline=WHITE, width=2, alpha=alpha * (0.4 + 0.6 * fizz))


def clock(img, c, r, frac=0.0, color=(228, 87, 46), alpha=1.0):
    R.circ(img, c, r, fill=WHITE, outline=INK, width=6, alpha=alpha)
    R.ring(img, c, r * 0.82, color, r * 0.16, -90, -90 + 360 * clamp(frac), alpha)
    a = -math.pi / 2 + 2 * math.pi * frac
    R.line(img, [c, (c[0] + r * 0.6 * math.cos(a), c[1] + r * 0.6 * math.sin(a))], INK, 8, alpha)
    R.circ(img, c, r * 0.07, fill=INK, alpha=alpha)


def brain_stem(img, c, w, glowk=0.0, color=(244, 162, 89), alpha=1.0):
    """Batang otak sederhana: kubah otak kecil + batang, tanpa wajah."""
    x, y = c
    if glowk > 0:
        R.glow(img, (x, y), w * 0.9, color, 0.5 * glowk)
    R.circ(img, (x, y - w * 0.05), w * 0.42, fill=mix(color, WHITE, 0.6), outline=INK, width=5, alpha=alpha)
    # lipatan
    for j in range(3):
        R.ring(img, (x + (j - 1) * w * 0.16, y - w * 0.08), w * 0.13, INK, 4, 200, 340, alpha)
    R.rrect(img, (x - w * 0.09, y + w * 0.3, x + w * 0.09, y + w * 0.75), w * 0.08, fill=mix(color, WHITE, 0.4), outline=INK, width=5, alpha=alpha)


def wave(img, x0, x1, y, amp, freq, phase, color, width=6, alpha=1.0, decay=False):
    pts = []
    n = 60
    for i in range(n + 1):
        u = i / n
        xx = x0 + (x1 - x0) * u
        a = amp * (1 - u if decay else 1)
        pts.append((xx, y + a * math.sin(2 * math.pi * freq * u + phase)))
    R.line(img, pts, color, width, alpha)


def burst(img, c, u, color, n=12, r=120, size=8, seed=0):
    """Ledakan partikel saat elemen muncul. u 0..1."""
    if u <= 0 or u >= 1:
        return
    for i in range(n):
        a = i * 2 * math.pi / n + seed
        d = r * eo(u)
        R.circ(img, (c[0] + d * math.cos(a), c[1] + d * math.sin(a)), size * (1 - u), fill=color, alpha=1 - u)


def particles(img, area, t, n=18, color=INK, size=6, alpha=0.5, seed=1, dy=-40):
    """Partikel naik pelan (untuk latar area)."""
    x0, y0, x1, y1 = area
    import numpy as np
    rng = np.random.default_rng(seed)
    for i in range(n):
        px = rng.uniform(x0, x1) + 20 * math.sin(t * 0.7 + i)
        py = y1 - ((rng.uniform(0, 1) + t * (0.02 + 0.02 * (i % 3))) % 1.0) * (y1 - y0)
        R.circ(img, (px, py), size * rng.uniform(0.5, 1.2), fill=color, alpha=alpha)


def counter_text(img, xy, value, size, color=INK, suffix="", anchor="mm", weight="Bold", track=True):
    """Angka format Indonesia (titik ribuan)."""
    s = "{:,}".format(int(value)).replace(",", ".") + suffix
    return R.text(img, xy, s, size, weight, color, anchor, track=track)


# --------------------------------------------------------------- visual generik (cadangan)

@register("partikel")
def vis_partikel(img, t, dur, sc):
    acc = R.hex2rgb(sc.get("accent", "#E4572E"))
    particles(img, (80, 500, 1000, 1500), t, 24, acc, 10, 0.6)
    R.glow(img, (540, 1000), 260, acc, 0.35 + 0.1 * math.sin(t * 2))


@register("gelombang")
def vis_gelombang(img, t, dur, sc):
    acc = R.hex2rgb(sc.get("accent", "#E4572E"))
    for j in range(4):
        wave(img, 80, 1000, 900 + j * 90, 40 - j * 6, 2 + j * 0.5, t * (2 + j), mix(acc, CREAM, j * 0.2), 10 - j)


def _selftest():
    import mesin_v11  # noqa: F401  (mendaftarkan visual episode)
    R.setup(os.environ.get("KT_SLUG", "ep50_cegukan"), 0.5, 0)
    frames = []
    import mesin_util
    for name, fn in VISUALS.items():
        for u in (0.15, 0.55, 0.9):
            sc = dict(id="x", type="fact", visual=name, accent="#E4572E", badge="UJI", hl="UJI")
            img = R.Image.new("RGB", (R.Si(1080), R.Si(1920)), CREAM)
            fn(img, u * 12, 12, sc)
            frames.append((u * 12, img))
    mesin_util.sheet(frames, "build/diagrams_selftest.jpg", cols=6, thumb_w=240)
    print("diagrams selftest OK: %d visual -> build/diagrams_selftest.jpg" % len(VISUALS))


if __name__ == "__main__":
    _selftest()
