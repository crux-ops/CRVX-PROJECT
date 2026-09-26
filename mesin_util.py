#!/usr/bin/env python3
"""mesin_util.py - preview_times, ink_report (audit tinta di zona margin), sheet (montase berlabel)."""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "Poppins-SemiBold.ttf")

# zona aman Shorts (skala 1080x1920)
MARGIN = 40
Y_MAX_TEKS = 1640          # di bawah ini tertutup UI YouTube
X_MAX_KANAN = 950          # kolom tombol kanan pada y 1100-1700
BG_TOL = 26                # selisih warna dari latar krem yang dianggap "tinta"


def preview_times(timeline, per_scene=2):
    ts = []
    for s in timeline["scenes"]:
        for k in range(per_scene):
            ts.append(round(s["start"] + s["dur"] * (k + 0.5) / per_scene, 2))
    return ts


def ink_report(img, bg=(246, 241, 232), boxes=None):
    """Ukur tinta (piksel jauh dari warna latar) di zona terlarang. Mengembalikan dict rasio + daftar pelanggaran."""
    a = np.asarray(img.convert("RGB"), dtype=np.int16)
    H, W = a.shape[:2]
    sx, sy = W / 1080, H / 1920
    diff = np.abs(a - np.array(bg, dtype=np.int16)).max(axis=2)
    ink = diff > BG_TOL
    def zone(x0, y0, x1, y1):
        x0, x1 = int(x0 * sx), int(x1 * sx)
        y0, y1 = int(y0 * sy), int(y1 * sy)
        z = ink[y0:y1, x0:x1]
        return float(z.mean()) if z.size else 0.0
    rep = {
        "margin_kiri": zone(0, 160, MARGIN, 1640),
        "margin_kanan": zone(1080 - MARGIN, 160, 1080, 1100),
        "margin_atas": zone(0, 0, 1080, 30),
        "bawah_ui": zone(0, Y_MAX_TEKS, 1080, 1920),
        "kolom_kanan": zone(X_MAX_KANAN, 1100, 1080, 1700),
        "isi_150_650": zone(MARGIN, 150, 1080 - MARGIN, 650),
    }
    bad = []
    # latar mesh sengaja berwarna lembut, jadi ambang rasio longgar untuk zona dekoratif, ketat untuk teks tercatat
    if rep["bawah_ui"] > 0.06:
        bad.append("tinta di bawah y1640: %.1f%%" % (rep["bawah_ui"] * 100))
    if rep["kolom_kanan"] > 0.06:
        bad.append("tinta di kolom kanan (x>950, y1100-1700): %.1f%%" % (rep["kolom_kanan"] * 100))
    if rep["margin_kiri"] > 0.05 or rep["margin_kanan"] > 0.05:
        bad.append("tinta di margin 40 px: kiri %.1f%% kanan %.1f%%" % (rep["margin_kiri"] * 100, rep["margin_kanan"] * 100))
    if rep["isi_150_650"] < 0.01:
        bad.append("zona y150-650 kosong")
    for b in boxes or []:
        x0, y0, x1, y1 = b
        if y1 > Y_MAX_TEKS:
            bad.append("kotak teks melewati y1640: %s" % str(tuple(int(v) for v in b)))
        if x0 < MARGIN or x1 > 1080 - MARGIN:
            bad.append("kotak teks melewati margin: %s" % str(tuple(int(v) for v in b)))
        if y1 > 1100 and x1 > X_MAX_KANAN:
            bad.append("kotak teks masuk kolom kanan: %s" % str(tuple(int(v) for v in b)))
    rep["pelanggaran"] = bad
    return rep


def sheet(frames, path, cols=None, thumb_w=360, guides=True):
    """Montase berlabel dari [(t, PIL.Image)]. Menggambar garis zona aman bila guides."""
    n = len(frames)
    cols = cols or min(6, max(1, n))
    rows = (n + cols - 1) // cols
    w0, h0 = frames[0][1].size
    th = int(thumb_w * h0 / w0)
    pad = 8
    out = Image.new("RGB", (cols * (thumb_w + pad) + pad, rows * (th + pad + 26) + pad), (30, 30, 34))
    f = ImageFont.truetype(FONT, 18)
    for i, (t, im) in enumerate(frames):
        x = pad + (i % cols) * (thumb_w + pad)
        y = pad + (i // cols) * (th + pad + 26)
        tm = im.resize((thumb_w, th), Image.LANCZOS)
        if guides:
            d = ImageDraw.Draw(tm, "RGBA")
            sy = th / 1920
            sx = thumb_w / 1080
            d.line([(0, 1640 * sy), (thumb_w, 1640 * sy)], fill=(255, 0, 0, 140), width=1)
            d.rectangle([(950 * sx, 1100 * sy), (thumb_w, 1700 * sy)], outline=(255, 0, 0, 120), width=1)
            d.rectangle([(40 * sx, 40 * sy), (thumb_w - 40 * sx, th - 40 * sy)], outline=(0, 200, 255, 90), width=1)
        out.paste(tm, (x, y))
        ImageDraw.Draw(out).text((x, y + th + 4), "t=%.2fs" % t, font=f, fill=(230, 230, 230))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    out.save(path, quality=85)
    return out
