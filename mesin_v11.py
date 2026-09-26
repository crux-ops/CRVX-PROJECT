#!/usr/bin/env python3
"""mesin_v11.py - paket motion "EDITOR" Shorts KlikTahu.

- Tipografi kinetik: judul kata-per-kata (skala 1.5 -> 1 pegas, terangkat dari balik mask + blur vertikal),
  sapuan STABILO di belakang kata kunci `hl`, stiker tebal (outline putih + bayangan keras + pop overshoot + goyang),
  chip label, penanda "FAKTA n/7".
- BEATS = satu sumber kebenaran: BEATS[visual] = [(fraksi_durasi, jenis_sfx), ...]. Fungsi gambar memakai fraksi
  yang sama (lewat `beat(visual, nama)`), jadi animasi, SFX, dan dorongan kamera jatuh di frame yang sama.
- events(content, timeline) -> [(detik, sfx)] dipakai master_audio dan render (punch kamera).
- Modul episode `mesin_v11_epNN.py` diimpor otomatis bila __name__ != "__main__" (hindari impor melingkar).
`python3 mesin_v11.py` = selftest (render intro/fact/outro dummy -> build/v11_selftest.jpg).
"""
import glob
import importlib
import math
import os

import diagrams as D
import mesin_fx as FX
import render as R
from render import CREAM, INK, MUTED, WHITE, clamp, eio, eo, eob, mix, seg

BEATS = {}          # visual -> [(frac, sfx)]
BEAT_NAMES = {}     # visual -> {nama: frac}
PUNCH = {"impact", "thud", "boom", "hik", "pop", "door", "gigit", "denyut", "retak", "zap"}
STAGGER = 0.11      # jeda antar kata judul kinetik


def daftar_beats(visual, tabel):
    """tabel = {nama: (frac, sfx)}; sfx None = beat visual tanpa bunyi."""
    BEAT_NAMES[visual] = {k: v[0] for k, v in tabel.items()}
    BEATS[visual] = [(v[0], v[1]) for v in tabel.values() if v[1]]


def beat(visual, nama, default=0.5):
    return BEAT_NAMES.get(visual, {}).get(nama, default)


# --------------------------------------------------------------- tipografi kinetik

def kinetic_words(img, t, t0, words, y, size, color=INK, weight="Bold", hl=None, accent=(228, 87, 46),
                  max_w=1000, align="m", x=540, track=True):
    """Satu baris kata-per-kata. Mengembalikan daftar bbox. hl = set kata (upper) yang diberi stabilo."""
    widths = [R.text_size(w, size, weight)[0] for w in words]
    sp = R.text_size(" ", size, weight)[0] * 1.1
    total = sum(widths) + sp * (len(words) - 1)
    if align == "m":
        cx = x - total / 2
    elif align == "l":
        cx = x
    else:
        cx = x - total
    boxes = []
    hl = hl or set()
    # stabilo dulu (di belakang)
    for i, w in enumerate(words):
        ts = t0 + i * STAGGER
        if w.upper().strip(",.?!") in hl:
            u = eo(seg(t, ts + 0.15, ts + 0.5))
            if u > 0:
                h = size * 0.5
                yc = y + size * 0.62
                R.rrect(img, (cx - 10, yc - h / 2, cx - 10 + (widths[i] + 20) * u, yc + h / 2), 10, fill=accent, alpha=0.5)
        cx += widths[i] + sp
    cx = (x - total / 2) if align == "m" else (x if align == "l" else x - total)
    for i, w in enumerate(words):
        ts = t0 + i * STAGGER
        u = seg(t, ts, ts + 0.42)
        if u <= 0:
            cx += widths[i] + sp
            continue
        k = FX.spring(u * 0.6, 0.42, 16)   # 0->1 dengan overshoot ringan
        scale = 1.5 - 0.5 * min(1.0, k)
        rise = (1 - eo(u)) * size * 0.5
        blur = (1 - eo(u)) * 6
        a = min(1.0, u * 2.2)
        b = R.text(img, (cx + widths[i] / 2, y + rise), w, size, weight, color, "ma", alpha=a, scale=scale,
                   blur=blur if u < 0.6 else 0, track=track and u > 0.9)
        if b:
            boxes.append(b)
        cx += widths[i] + sp
    return boxes


def kinetic_title(img, t, t0, lines, y, size, color=INK, hl=None, accent=(228, 87, 46), gap=1.08, weight="Bold",
                  max_w=1000, x=540, align="m"):
    """Beberapa baris; stagger berlanjut antar baris. Ukuran otomatis dikecilkan agar muat max_w."""
    hlset = set(w.upper().strip(",.?!") for w in (hl or "").split())
    for ln in lines:
        size = R.fit_size(ln, max_w, size, 40, weight)
    n = 0
    boxes = []
    for j, ln in enumerate(lines):
        words = ln.split()
        boxes += kinetic_words(img, t, t0 + n * STAGGER, words, y + j * size * gap, size, color, weight, hlset,
                               accent, max_w, align, x)
        n += len(words)
    return boxes, t0 + n * STAGGER


def sticker(img, t, t0, c, txt, accent, size=44, rot=-6.0, color=WHITE, wobble=True, track=True, life=None):
    """Stiker tebal: kapsul aksen + outline putih + bayangan keras; pop overshoot + goyang."""
    u = seg(t, t0, t0 + 0.35)
    if u <= 0:
        return None
    if life is not None and t > t0 + life:
        u2 = 1 - seg(t, t0 + life, t0 + life + 0.25)
        if u2 <= 0:
            return None
    else:
        u2 = 1.0
    k = eob(u, 2.2) * u2
    w, h = R.text_size(txt, size, "Bold")
    pw, ph = (w + 56) * k, (h + 40) * k
    ang = rot + (2.5 * math.sin(t * 6 + c[0]) if wobble else 0)
    x, y = c
    lay = R.Image.new("RGBA", (R.Si(pw + 80), R.Si(ph + 80)), (0, 0, 0, 0))
    ss = R.SS
    d = R.ImageDraw.Draw(lay)
    ox, oy = 40 * ss, 40 * ss
    d.rounded_rectangle((ox + 6 * ss, oy + 8 * ss, ox + pw * ss + 6 * ss, oy + ph * ss + 8 * ss), ph / 2 * ss, fill=INK + (255,))
    d.rounded_rectangle((ox, oy, ox + pw * ss, oy + ph * ss), ph / 2 * ss, fill=accent + (255,), outline=WHITE + (255,), width=int(5 * ss))
    f = R.font("Bold", R.Si(size * k))
    d.text(((ox + pw * ss / 2), (oy + ph * ss / 2)), txt, font=f, fill=color + (255,), anchor="mm")
    lay = lay.rotate(ang, R.Image.BICUBIC, expand=True)
    img.paste(lay, (int(x * ss - lay.width / 2), int(y * ss - lay.height / 2)), lay)
    box = (x - lay.width / ss / 2, y - lay.height / ss / 2, x + lay.width / ss / 2, y + lay.height / ss / 2)
    if track and "boxes" in R.CTX and u >= 1:
        R.CTX["boxes"].append(box)
    return box


def chip(img, t, t0, xy, txt, accent, size=26, fill=None, color=None, track=True):
    """Chip label kecil (kapsul) yang masuk geser."""
    u = eo(seg(t, t0, t0 + 0.4))
    if u <= 0:
        return None
    w, h = R.text_size(txt, size, "SemiBold")
    x, y = xy
    x -= 40 * (1 - u)
    fill = fill or accent
    color = color or WHITE
    R.rrect(img, (x, y, x + w + 40, y + h + 26), (h + 26) / 2, fill=fill, alpha=u)
    return R.text(img, (x + 20 + w / 2, y + (h + 26) / 2), txt, size, "SemiBold", color, "mm", alpha=u, track=track and u >= 1)


def fakta_marker(img, t, t0, n, total, x=1028, y=238, color=MUTED):
    u = eo(seg(t, t0, t0 + 0.4))
    if u <= 0:
        return
    s = "FAKTA %d/%d" % (n, total)
    R.text(img, (x + 30 * (1 - u), y), s, 24, "SemiBold", color, "rm", alpha=u, track=u >= 1)


def label(img, xy, txt, size=28, color=INK, anchor="mm", weight="SemiBold", alpha=1.0, bg=None, track=True):
    """Label polos, opsional latar kapsul putih agar terbaca di atas diagram."""
    if alpha <= 0:
        return None
    if bg is not None:
        w, h = R.text_size(txt, size, weight)
        x, y = xy
        if anchor[0] == "m":
            x0 = x - w / 2
        elif anchor[0] == "l":
            x0 = x
        else:
            x0 = x - w
        y0 = y - h / 2 if anchor[1] == "m" else y
        R.rrect(img, (x0 - 16, y0 - 10, x0 + w + 16, y0 + h + 10), (h + 20) / 2, fill=bg, alpha=alpha * 0.92)
    return R.text(img, xy, txt, size, weight, color, anchor, alpha=alpha, track=track)


def pulse_ring(img, c, r, color, t, period=1.2, width=6, n=2):
    for k in range(n):
        u = ((t / period) + k / n) % 1.0
        R.ring(img, c, r * (1 + 0.6 * u), color, width, 0, 360, (1 - u) * 0.8)


# --------------------------------------------------------------- komposisi adegan

def draw_intro(img, t, dur, sc, content):
    acc = R.hex2rgb(sc.get("accent", "#E4572E"))
    vis = D.get(sc.get("visual"))
    if vis:
        vis(img, t, dur, sc)
    lines = sc.get("lines", [content.get("title", "")])
    # hook besar: dua baris, kata pertama muncul ~0.15 s (hook <= 3 detik)
    kinetic_title(img, t, 0.15, lines, 560, 128, INK, hl=lines[-1].split()[-1], accent=acc, gap=1.05)
    # sub-chip judul channel
    chip(img, t, 0.9, (40, 210), content.get("header_badge", "FAKTA SAINS"), acc, 26)


def draw_fact(img, t, dur, sc, content, idx, nfact):
    acc = R.hex2rgb(sc.get("accent", "#E4572E"))
    chip(img, t, 0.1, (40, 210), sc.get("badge", ""), acc, 26)
    fakta_marker(img, t, 0.2, idx, nfact)
    hl = sc.get("hl", "")
    if hl:
        kinetic_title(img, t, 0.35, [hl], 300, 96, INK, hl=hl, accent=acc, gap=1.0)
    vis = D.get(sc.get("visual"))
    if vis:
        vis(img, t, dur, sc)
    else:
        D.vis_partikel(img, t, dur, sc)


def draw_outro(img, t, dur, sc, content):
    acc = R.hex2rgb(sc.get("accent", "#2E86AB"))
    vis = D.get(sc.get("visual", "outro_default"))
    lines = sc.get("lines", ["SEKARANG", "KAMU TAHU"])
    kinetic_title(img, t, 0.2, lines, 470, 132, INK, hl=lines[-1], accent=acc, gap=1.02)
    # CTA kapsul berdenyut
    u = eob(seg(t, 1.2, 1.6), 1.8)
    if u > 0:
        cx, cy = 540, 890
        pulse_ring(img, (cx, cy), 150, acc, t, 1.4, 5)
        w = 320 * u
        R.rrect(img, (cx - w / 2, cy - 54 * u, cx + w / 2, cy + 54 * u), 54 * u, fill=acc)
        R.text(img, (cx, cy), sc.get("cta", "IKUTI"), 48 * u, "Bold", WHITE, "mm", track=u >= 1)
    a1 = eo(seg(t, 1.8, 2.3))
    label(img, (540, 1010 + 20 * (1 - a1)), sc.get("foot", ""), 34, INK, "mm", "SemiBold", a1)
    a2 = eo(seg(t, 2.2, 2.7))
    label(img, (540, 1070 + 20 * (1 - a2)), sc.get("foot2", ""), 28, MUTED, "mm", "Medium", a2)
    if vis:
        vis(img, t, dur, sc)
    a3 = eo(seg(t, 3.0, 3.6))
    src = sc.get("src", "")
    if src:
        lines_src = R.wrap(src, 24, 840, "Medium")
        for j, ln in enumerate(lines_src):
            label(img, (540, 1500 + j * 34), ln, 24, MUTED, "mm", "Medium", a3)


def draw_scene(img, t, dur, sc, i, content, timeline):
    typ = sc.get("type", "fact")
    if typ == "intro":
        draw_intro(img, t, dur, sc, content)
    elif typ == "outro":
        draw_outro(img, t, dur, sc, content)
    else:
        facts = [s for s in content["scenes"] if s.get("type") == "fact"]
        idx = facts.index(sc) + 1
        draw_fact(img, t, dur, sc, content, idx, len(facts))


# --------------------------------------------------------------- events (SFX + punch kamera)

def events(content, timeline):
    ev = []
    scenes = content["scenes"]
    facts = [s for s in scenes if s.get("type") == "fact"]
    for i, (sc, ts) in enumerate(zip(scenes, timeline["scenes"])):
        st, dur = ts["start"], ts["dur"]
        typ = sc.get("type", "fact")
        if i > 0:
            name = sc.get("trans") or FX.URUTAN_TRANSISI[i % len(FX.URUTAN_TRANSISI)]
            ev.append((st - R.TRANS_DUR / 2 + 0.05, FX.SFX_TRANSISI.get(name, "whoosh")))
        if typ == "intro":
            ev.append((st + 0.02, "impact"))
            words = sum(len(l.split()) for l in sc.get("lines", []))
            for k in range(words):
                ev.append((st + 0.15 + k * STAGGER, "tick"))
            ev.append((st + 0.9, "swish_up"))
        elif typ == "outro":
            words = sum(len(l.split()) for l in sc.get("lines", []))
            for k in range(words):
                ev.append((st + 0.2 + k * STAGGER, "tick"))
            ev.append((st + 1.2, "ding"))
            ev.append((st + 1.8, "kilau"))
        else:
            ev.append((st + 0.1, "swish_up"))
            words = len(sc.get("hl", "").split())
            for k in range(words):
                ev.append((st + 0.35 + k * STAGGER, "tick"))
        for frac, sfx in BEATS.get(sc.get("visual", ""), []):
            ev.append((st + frac * dur, sfx))
    ev.sort()
    return ev


# --------------------------------------------------------------- impor modul episode

if __name__ != "__main__":
    _here = os.path.dirname(os.path.abspath(__file__))
    for _p in sorted(glob.glob(os.path.join(_here, "mesin_v11_ep*.py"))):
        importlib.import_module(os.path.splitext(os.path.basename(_p))[0])


def _selftest():
    import mesin_util
    import mesin_v11 as M   # modul sebenarnya (bukan __main__), sudah memuat mesin_v11_ep*
    R.setup(os.environ.get("KT_SLUG", "ep50_cegukan"), 0.5, 0)
    content, tl = R.CTX["content"], R.CTX["timeline"]
    frames = []
    for t in mesin_util.preview_times(tl, 2):
        frames.append((t, R.render_frame(t, True, int(t * 60))))
    mesin_util.sheet(frames, "build/v11_selftest.jpg", cols=6, thumb_w=240)
    ev = M.events(content, tl)
    assert len(M.BEATS) > 0, "BEATS episode tidak termuat"
    assert all(0 <= t <= tl["total"] for t, _ in ev), "event di luar timeline"
    print("mesin_v11 selftest OK: %d frame, %d events -> build/v11_selftest.jpg" % (len(frames), len(ev)))


if __name__ == "__main__":
    _selftest()
