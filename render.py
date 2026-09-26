#!/usr/bin/env python3
"""render.py - renderer Shorts KlikTahu (1080x1920). Semua koordinat didesain di skala 1080 lalu dikali S().

Lapisan frame: latar (mesh gradient) -> konten adegan (VISUALS registry) -> header (brand + badge) ->
bilah progres bersegmen -> kamera (drift + punch pada beat) -> transisi antar adegan -> finishing FX -> downscale+unsharp.

CLI:
  python3 render.py --slug ep50_cegukan --fps 60 --ss 1.5 --sharpen 52 --jobs 2 --range 0:600 --outdir build/frames
  python3 render.py --slug ep50_cegukan --times auto --sheet build/preview.jpg      (montase pratinjau)
  python3 render.py --slug ep50_cegukan --times 3.2,20.5 --outdir build/cek         (frame tunggal)
Deterministik: tidak ada jam dinding, seed tetap.
"""
import argparse
import math
import os
import sys
from functools import lru_cache
from multiprocessing import Pool

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import mesin_fx as FX
from audio_util import env_of, load_json

W, H = 1080, 1920
SS = 1.5
CREAM = (246, 241, 232)
INK = (24, 24, 31)
MUTED = (128, 122, 114)
WHITE = (255, 255, 255)
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
TRANS_DUR = 0.5

# --------------------------------------------------------------- konteks global (di-set per proses)
CTX = {}


def S(v):
    return v * SS


def Si(v):
    return int(round(v * SS))


# --------------------------------------------------------------- easing

def clamp(v, a=0.0, b=1.0):
    return a if v < a else b if v > b else v


def eo(u):
    u = clamp(u)
    return 1 - (1 - u) ** 3


def eio(u):
    u = clamp(u)
    return u * u * (3 - 2 * u)


def eob(u, k=1.70158):
    u = clamp(u)
    return 1 + (k + 1) * (u - 1) ** 3 + k * (u - 1) ** 2


def seg(t, a, b):
    """0..1 linier dari t=a sampai t=b (diklem)."""
    if b <= a:
        return 1.0 if t >= b else 0.0
    return clamp((t - a) / (b - a))


def hex2rgb(h):
    if isinstance(h, (tuple, list)):
        return tuple(h)
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, u):
    u = clamp(u)
    return tuple(int(round(a[i] + (b[i] - a[i]) * u)) for i in range(3))


# --------------------------------------------------------------- font & teks

@lru_cache(maxsize=256)
def font(weight="Bold", size=40):
    size = max(1, int(size))
    return ImageFont.truetype(os.path.join(FONT_DIR, "Poppins-%s.ttf" % weight), size)


def text_size(s, size, weight="Bold"):
    f = font(weight, Si(size))
    l, t, r, b = f.getbbox(s)
    return (r - l) / SS, (b - t) / SS


@lru_cache(maxsize=1024)
def _text_sprite(s, size_px, weight, fill, stroke, stroke_fill):
    f = font(weight, size_px)
    l, t, r, b = f.getbbox(s, stroke_width=stroke)
    pad = 4 + stroke
    im = Image.new("RGBA", (max(1, r - l + 2 * pad), max(1, b - t + 2 * pad)), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad - l, pad - t), s, font=f, fill=fill + (255,), stroke_width=stroke,
                            stroke_fill=(stroke_fill + (255,)) if stroke_fill else None)
    return im, (l - pad, t - pad)


def text(img, xy, s, size, weight="Bold", fill=INK, anchor="la", alpha=1.0, scale=1.0, rot=0.0, blur=0.0,
         stroke=0, stroke_fill=None, track=False):
    """Teks di koordinat desain (1080). anchor 'la'/'ma'/'ra' + 'm' tengah vertikal ('mm'). Mengembalikan bbox desain.
    alpha/scale/rot/blur memakai sprite ter-cache. Mencatat bbox ke CTX['boxes'] bila track=True."""
    if not s or alpha <= 0.001:
        return None
    x, y = S(xy[0]), S(xy[1])
    sp, (ox, oy) = _text_sprite(s, Si(size), weight, tuple(fill), int(stroke * SS), tuple(stroke_fill) if stroke_fill else None)
    w, h = sp.size
    if anchor[0] == "m":
        x -= (w + 2 * ox) / 2
    elif anchor[0] == "r":
        x -= w + ox
    else:
        x += ox
    if len(anchor) > 1 and anchor[1] == "m":
        y -= (h + 2 * oy) / 2
    else:
        y += oy
    if scale != 1.0 or rot != 0.0 or blur > 0:
        cx, cy = x + w / 2, y + h / 2
        if scale != 1.0:
            sp = sp.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.BILINEAR)
        if rot:
            sp = sp.rotate(rot, Image.BICUBIC, expand=True)
        if blur > 0:
            sp = sp.filter(ImageFilter.GaussianBlur(float(blur * SS)))
        w, h = sp.size
        x, y = cx - w / 2, cy - h / 2
    if alpha < 1:
        a = sp.getchannel("A").point(lambda v: int(v * alpha))
        sp = sp.copy()
        sp.putalpha(a)
    img.paste(sp, (int(x), int(y)), sp)
    box = (x / SS, y / SS, (x + w) / SS, (y + h) / SS)
    if track and "boxes" in CTX:
        CTX["boxes"].append(box)
    return box


def wrap(s, size, max_w, weight="Bold"):
    words = s.split()
    lines, cur = [], ""
    for w in words:
        cand = (cur + " " + w).strip()
        if text_size(cand, size, weight)[0] <= max_w or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit_size(s, max_w, size, min_size=20, weight="Bold"):
    while size > min_size and text_size(s, size, weight)[0] > max_w:
        size -= 2
    return size


# --------------------------------------------------------------- primitif bentuk

def _d(img):
    return ImageDraw.Draw(img, "RGBA")


def rrect(img, box, r, fill=None, outline=None, width=2, alpha=1.0):
    x0, y0, x1, y1 = [S(v) for v in box]
    if alpha < 1 and fill is not None:
        fill = tuple(fill) + (int(255 * alpha),)
    if alpha < 1 and outline is not None:
        outline = tuple(outline) + (int(255 * alpha),)
    _d(img).rounded_rectangle((x0, y0, x1, y1), S(r), fill=fill, outline=outline, width=Si(width))


def line(img, pts, fill=INK, width=4, alpha=1.0, joint="curve"):
    if alpha < 1:
        fill = tuple(fill) + (int(255 * alpha),)
    _d(img).line([(S(x), S(y)) for x, y in pts], fill=fill, width=max(1, Si(width)), joint=joint)


def circ(img, c, r, fill=None, outline=None, width=2, alpha=1.0):
    x, y = S(c[0]), S(c[1])
    r = S(r)
    if alpha < 1 and fill is not None:
        fill = tuple(fill) + (int(255 * alpha),)
    if alpha < 1 and outline is not None:
        outline = tuple(outline) + (int(255 * alpha),)
    _d(img).ellipse((x - r, y - r, x + r, y + r), fill=fill, outline=outline, width=Si(width))


def ring(img, c, r, color=INK, width=6, start=0, end=360, alpha=1.0):
    x, y = S(c[0]), S(c[1])
    r = S(r)
    if alpha < 1:
        color = tuple(color) + (int(255 * alpha),)
    _d(img).arc((x - r, y - r, x + r, y + r), start, end, fill=color, width=max(1, Si(width)))


def poly(img, pts, fill=None, outline=None, width=2, alpha=1.0):
    if alpha < 1 and fill is not None:
        fill = tuple(fill) + (int(255 * alpha),)
    _d(img).polygon([(S(x), S(y)) for x, y in pts], fill=fill, outline=outline, width=Si(width))


def bezier(p0, p1, p2, p3, n=40, upto=1.0):
    pts = []
    for i in range(int(n * clamp(upto)) + 1):
        u = i / n
        a = (1 - u) ** 3
        b = 3 * (1 - u) ** 2 * u
        c = 3 * (1 - u) * u * u
        d = u ** 3
        pts.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return pts


def arrow(img, pts, color=INK, width=6, head=22, alpha=1.0):
    """Panah mengikuti polyline (ujung panah di titik terakhir)."""
    if len(pts) < 2:
        return
    line(img, pts, color, width, alpha)
    (x0, y0), (x1, y1) = pts[-2], pts[-1]
    a = math.atan2(y1 - y0, x1 - x0)
    l = (x1 - head * math.cos(a - 0.5), y1 - head * math.sin(a - 0.5))
    r = (x1 - head * math.cos(a + 0.5), y1 - head * math.sin(a + 0.5))
    poly(img, [(x1, y1), l, r], fill=color, alpha=alpha)


def check_mark(img, c, size, color=WHITE, width=8, u=1.0):
    """Tanda centang digambar sebagai garis (Poppins tidak punya glyph centang)."""
    x, y = c
    p0 = (x - size * 0.45, y + size * 0.02)
    p1 = (x - size * 0.12, y + size * 0.35)
    p2 = (x + size * 0.5, y - size * 0.35)
    pts = [p0]
    if u < 0.5:
        k = u / 0.5
        pts.append((p0[0] + (p1[0] - p0[0]) * k, p0[1] + (p1[1] - p0[1]) * k))
    else:
        k = (u - 0.5) / 0.5
        pts += [p1, (p1[0] + (p2[0] - p1[0]) * k, p1[1] + (p2[1] - p1[1]) * k)]
    line(img, pts, color, width)


def star(img, c, r, color, alpha=1.0, rot=-90, n=5):
    pts = []
    for i in range(2 * n):
        a = math.radians(rot + i * 180 / n)
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((c[0] + rr * math.cos(a), c[1] + rr * math.sin(a)))
    poly(img, pts, fill=color, alpha=alpha)


def glow(img, c, r, color, alpha=1.0):
    FX.glow(img, (S(c[0]), S(c[1])), Si(r), color, alpha)


def shadow(img, box, r, blur=16, alpha=0.2, dy=10):
    FX.bayang(img, [S(v) for v in box], S(r), Si(blur), alpha, (0, Si(dy)))


def glass(img, box, r, tint=WHITE, tint_a=0.4, t=0.0):
    FX.kaca_cair(img, [S(v) for v in box], S(r), tint, tint_a, Si(10), t)


# --------------------------------------------------------------- lapisan tetap

def draw_bg(img, t, accent):
    bg = FX.mesh_latar(img.width, img.height, t, CREAM, accent, strength=0.07)
    img.paste(bg, (0, 0))


def draw_header(img, t, sc, content):
    """Brand pill kiri atas + badge tema kanan atas (y 60-130)."""
    u = eo(seg(t, 0.0, 0.5)) if CTX.get("scene_index", 0) == 0 else 1.0
    accent = hex2rgb(sc.get("accent", "#E4572E"))
    # brand
    bx = 40 - 60 * (1 - u)
    rrect(img, (bx, 62, bx + 226, 128), 33, fill=INK)
    circ(img, (bx + 36, 95), 13, fill=accent)
    text(img, (bx + 62, 95), "KlikTahu", 30, "Bold", WHITE, "lm")
    # badge tema
    badge = content.get("header_badge", "")
    if badge:
        bw = text_size(badge, 22, "SemiBold")[0] + 44
        x1 = 1040 + 60 * (1 - u)
        rrect(img, (x1 - bw, 68, x1, 122), 27, fill=WHITE, outline=(226, 220, 210), width=2)
        text(img, (x1 - bw / 2, 95), badge, 22, "SemiBold", MUTED, "mm")


def draw_progress(img, t_global, timeline, sc_index):
    """Bilah progres bersegmen per adegan (retensi), y 146-154."""
    scenes = timeline["scenes"]
    total_w = 1000
    gap = 6
    n = len(scenes)
    seg_w = (total_w - gap * (n - 1)) / n
    x = 40
    for i, s in enumerate(scenes):
        rrect(img, (x, 146, x + seg_w, 154), 4, fill=(222, 216, 206))
        if i < sc_index:
            f = 1.0
        elif i == sc_index:
            f = clamp((t_global - s["start"]) / s["dur"])
        else:
            f = 0.0
        if f > 0:
            rrect(img, (x, 146, x + seg_w * f, 154), 4, fill=INK)
        x += seg_w + gap


# --------------------------------------------------------------- kamera

def camera(img, t_local, t_global, sc, beats):
    """Drift organik + punch pada beat (skala 1.035 meluruh 0.35 s)."""
    z = 1.012 + 0.004 * FX.nois(t_global * 0.5, 3)
    dx = 6 * SS * FX.nois(t_global * 0.35, 1)
    dy = 6 * SS * FX.nois(t_global * 0.3, 2)
    punch = 0.0
    for bt in beats:
        d = t_global - bt
        if 0 <= d < 0.4:
            punch = max(punch, 0.035 * (1 - d / 0.4) ** 2)
    z += punch
    if sc.get("shake") and t_local < 0.6:
        k = (1 - t_local / 0.6) * float(sc.get("shake", 1))
        dx += 14 * SS * k * FX.nois(t_global * 40, 5)
        dy += 14 * SS * k * FX.nois(t_global * 40, 6)
    w, h = img.size
    cx, cy = w / 2, h / 2
    a = 1 / z
    # transform affine: keluaran(x,y) <- masukan(a*x + c, a*y + f)
    c = cx - a * cx - dx
    f = cy - a * cy - dy
    return img.transform((w, h), Image.AFFINE, (a, 0, c, 0, a, f), Image.BILINEAR)


# --------------------------------------------------------------- frame

def scene_at(timeline, tg):
    scenes = timeline["scenes"]
    for i, s in enumerate(scenes):
        if tg < s["start"] + s["dur"] or i == len(scenes) - 1:
            return i
    return len(scenes) - 1


def render_scene_image(i, tg):
    """Gambar penuh (sebelum transisi/finishing) untuk adegan i pada waktu global tg."""
    import mesin_v11 as M
    content, timeline = CTX["content"], CTX["timeline"]
    sc = content["scenes"][i]
    tsc = timeline["scenes"][i]
    tl = tg - tsc["start"]
    dur = tsc["dur"]
    CTX["scene_index"] = i
    img = Image.new("RGB", (Si(W), Si(H)), CREAM)
    accent = hex2rgb(sc.get("accent", "#E4572E"))
    draw_bg(img, tg, accent)
    M.draw_scene(img, tl, dur, sc, i, content, timeline)
    draw_header(img, tl, sc, content)
    draw_progress(img, tg, timeline, i)
    beats = CTX.get("beats", [])
    img = camera(img, tl, tg, sc, beats)
    return img


def render_frame(tg, finishing=True, frame_idx=0):
    content, timeline = CTX["content"], CTX["timeline"]
    i = scene_at(timeline, tg)
    scenes = timeline["scenes"]
    img = render_scene_image(i, tg)
    # transisi: [start_i - TD/2, start_i + TD/2] untuk i>0
    if i > 0:
        st = scenes[i]["start"]
        if tg < st + TRANS_DUR / 2:
            u = (tg - (st - TRANS_DUR / 2)) / TRANS_DUR
            A = render_scene_image(i - 1, tg)
            name = content["scenes"][i].get("trans") or FX.URUTAN_TRANSISI[i % len(FX.URUTAN_TRANSISI)]
            img = FX.TRANSISI[name](A, img, clamp(u))
    if i + 1 < len(scenes):
        st = scenes[i + 1]["start"]
        if tg >= st - TRANS_DUR / 2:
            u = (tg - (st - TRANS_DUR / 2)) / TRANS_DUR
            B = render_scene_image(i + 1, tg)
            name = content["scenes"][i + 1].get("trans") or FX.URUTAN_TRANSISI[(i + 1) % len(FX.URUTAN_TRANSISI)]
            img = FX.TRANSISI[name](img, B, clamp(u))
    out = img.resize((W, H), Image.LANCZOS) if SS != 1 else img
    sh = CTX.get("sharpen", 52)
    if sh > 0:
        out = out.filter(ImageFilter.UnsharpMask(radius=1.2, percent=int(sh), threshold=2))
    if finishing:
        out = FX.finishing(out, "krem", frame_idx)
    return out


# --------------------------------------------------------------- setup & CLI

def setup(slug, ss=None, sharpen=None):
    global SS
    env_of(slug)
    base = os.path.join("episodes", slug)
    content = load_json(os.path.join(base, "content.json"))
    timeline = load_json(os.path.join(base, "timeline.json"))
    SS = float(ss if ss is not None else os.environ.get("SS", "1.5"))
    CTX.update(content=content, timeline=timeline, slug=slug,
               sharpen=float(sharpen if sharpen is not None else os.environ.get("SHARPEN", "52")))
    import mesin_v11 as M
    CTX["beats"] = [t for t, _ in M.events(content, timeline)]
    return content, timeline


def _worker_init(slug, ss, sharpen):
    setup(slug, ss, sharpen)


def _render_one(args):
    idx, fps, outdir = args
    tg = idx / fps
    img = render_frame(tg, True, idx)
    img.save(os.path.join(outdir, "f_%05d.png" % idx), compress_level=1)
    return idx


def preview_times(timeline, per_scene=1):
    ts = []
    for s in timeline["scenes"]:
        for k in range(per_scene):
            ts.append(s["start"] + s["dur"] * (0.55 if per_scene == 1 else (k + 0.5) / per_scene))
    return ts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--fps", type=int, default=None)
    ap.add_argument("--ss", type=float, default=None)
    ap.add_argument("--sharpen", type=float, default=None)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--range", default=None, help="LO:HI indeks frame (HI eksklusif)")
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--times", default=None, help="'auto' atau daftar detik dipisah koma")
    ap.add_argument("--sheet", default=None, help="tulis montase berlabel ke file ini")
    ap.add_argument("--nofx", action="store_true")
    a = ap.parse_args()
    content, timeline = setup(a.slug, a.ss, a.sharpen)
    fps = a.fps or int(os.environ.get("FPS", "60"))
    if a.times:
        ts = preview_times(timeline, 2) if a.times == "auto" else [float(x) for x in a.times.split(",")]
        frames = []
        for t in ts:
            frames.append((t, render_frame(t, not a.nofx, int(t * fps))))
        if a.sheet:
            import mesin_util
            mesin_util.sheet(frames, a.sheet)
            print("montase ->", a.sheet)
        if a.outdir:
            os.makedirs(a.outdir, exist_ok=True)
            for t, im in frames:
                p = os.path.join(a.outdir, "t_%07.2f.png" % t)
                im.save(p)
                print("frame ->", p)
        return
    total = int(math.ceil(timeline["total"] * fps))
    lo, hi = 0, total
    if a.range:
        lo, hi = [int(x) for x in a.range.split(":")]
        hi = min(hi, total)
    outdir = a.outdir or os.path.join("episodes", a.slug, "build", "frames")
    os.makedirs(outdir, exist_ok=True)
    todo = [(i, fps, outdir) for i in range(lo, hi) if not os.path.exists(os.path.join(outdir, "f_%05d.png" % i))]
    print("render %d frame (%d..%d) dengan %d proses -> %s" % (len(todo), lo, hi, a.jobs, outdir), flush=True)
    import time
    t0 = time.time()
    done = 0
    with Pool(a.jobs, initializer=_worker_init, initargs=(a.slug, SS, CTX["sharpen"])) as pool:
        for _ in pool.imap_unordered(_render_one, todo, chunksize=4):
            done += 1
            if done % 100 == 0 or done == len(todo):
                el = time.time() - t0
                print("  %d/%d  %.2f s/frame  sisa ~%.0f menit" % (done, len(todo), el / done,
                                                                   el / done * (len(todo) - done) / 60), flush=True)
    print("selesai %d frame dalam %.0f s" % (done, time.time() - t0))


if __name__ == "__main__":
    # jalankan lewat modul `render` sebenarnya agar SS/CTX satu sumber dengan mesin yang mengimpornya
    import render as _self
    _self.main()
