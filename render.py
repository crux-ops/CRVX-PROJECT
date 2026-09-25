#!/usr/bin/env python3
"""render.py - renderer Shorts KlikTahu (1080x1920, 60 fps).

Lapisan per frame (kanvas supersample SS):
  latar (mesh gradient bergerak + bg_element) -> konten adegan (layout tipe + visual registry)
  -> kamera (drift organik + dorongan pada beat) -> transisi fase keluar/masuk
  -> HUD (brand KlikTahu + badge tema + bilah progres bersegmen)  [HUD sengaja di atas kamera/transisi
     agar stabil & terbaca - elemen kontinuitas antar adegan]
  -> downscale LANCZOS ke 1080x1920 -> unsharp (SHARPEN) -> finishing FX (mesin_fx).

Mesin tampilan: content.mesin == "v11" -> mesin_v11 (tipografi kinetik EDITOR); selain itu layout dasar.
KT_FX=0 -> tanpa mesin_fx (latar polos, transisi pudar, tanpa finishing) = saklar darurat.
Deterministik: semua acak dari seed tetap; tidak memakai jam dinding.

CLI:
  python3 render.py <slug> [--fps F] [--ss S] [--sharpen P] [--jobs J] [--range LO:HI] [--outdir DIR]
  python3 render.py <slug> --pipe --range LO:HI        (rgb24 mentah ke stdout, untuk ffmpeg)
  python3 render.py <slug> --times auto --sheet        (montase pratinjau frame kunci)
  python3 render.py <slug> --times 1.0,4.2 --sheet out.jpg
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import diagrams as D  # noqa: E402
import mesin_util as mu  # noqa: E402

W0, H0 = D.W0, D.H0
ST: dict = {}  # state global per proses (diwariskan ke worker lewat fork)


# ============================================================================ muat
def _impor_mesin(content):
    fx = v11 = None
    if os.environ.get("KT_FX", "1") != "0":
        try:
            import mesin_fx as fx  # noqa: F811
        except ImportError:
            fx = None
    if content.get("mesin", "v11") == "v11":
        try:
            import mesin_v11 as v11  # noqa: F811
        except ImportError:
            v11 = None
    return fx, v11


def siapkan(slug, fps=None, ss=None, sharpen=None, fx_on=True):
    ep, content, cfg, bdir = mu.muat_episode(slug)
    tl_p = bdir / "timeline.json"
    if not tl_p.exists():
        mu.gagal(f"{tl_p} belum ada - jalankan prep audio dulu (process_audio -> build_timeline)")
    tl = json.loads(tl_p.read_text(encoding="utf-8"))
    ST.clear()
    ST.update(ep=ep, content=content, cfg=cfg, bdir=bdir, tl=tl,
              fps=int(fps or cfg.i("FPS", 60)), ss=float(ss or cfg.f("SS", 1.5)),
              sharpen=int(sharpen if sharpen is not None else cfg.i("SHARPEN", 52)))
    if not fx_on:
        os.environ["KT_FX"] = "0"
    D.set_ss(ST["ss"])
    fx, v11 = _impor_mesin(content)
    ST["fx"], ST["v11"] = fx, v11
    ev_p = bdir / "events.json"
    if ev_p.exists():
        ST["events"] = json.loads(ev_p.read_text(encoding="utf-8"))["events"]
    elif v11 is not None:
        ST["events"] = v11.events(content, tl)
    else:
        ST["events"] = []
    ST["beats"] = sorted(float(e["t"]) for e in ST["events"] if e.get("berat"))
    # nomor fakta
    n = 0
    fakta = {}
    for s in content["scenes"]:
        if s.get("type") == "fact":
            n += 1
            fakta[s["id"]] = n
    ST["fakta"], ST["fakta_total"] = fakta, n
    ST["Wc"], ST["Hc"] = int(round(W0 * ST["ss"])), int(round(H0 * ST["ss"]))
    return ST


class Ctx:
    """konteks adegan untuk layout & visual."""

    def __init__(self, k, T, fi):
        self.k = k
        self.content = ST["content"]
        self.sc = ST["content"]["scenes"][k]
        self.ts = ST["tl"]["scenes"][k]
        self.t = T - self.ts["start"]
        self.dur = self.ts["dur"]
        self.T = T
        self.fi = fi
        self.fps = ST["fps"]
        self.n = len(ST["tl"]["scenes"])
        self.aksen = D.col(self.sc.get("accent", "#2F7BFF"))
        self.lead = self.ts.get("lead_in", 0.6)
        self.vo_dur = self.ts["vo_dur"]
        self.fakta_no = ST["fakta"].get(self.sc["id"], 0)
        self.fakta_total = ST["fakta_total"]
        self.events = [e for e in ST["events"] if e.get("scene") == self.sc["id"]]


def adegan_di(T):
    sc = ST["tl"]["scenes"]
    for k, s in enumerate(sc):
        if T < s["start"] + s["dur"] - 1e-9:
            return k
    return len(sc) - 1


# ============================================================================ latar
_BASE: dict = {}


def latar(T, ctx):
    fx = ST["fx"]
    size = (ST["Wc"], ST["Hc"])
    if fx is not None:
        img = fx.mesh_latar(size, T, ctx.aksen, seed=ST["tl"].get("slug", "kt"))
    else:
        if "polos" not in _BASE:
            g = np.linspace(0, 1, size[1])[:, None, None]
            a = np.array(D.CREAM, np.float32)[None, None, :]
            b = np.array(D.campur(D.CREAM, D.MUTED, 0.10), np.float32)[None, None, :]
            arr = (a * (1 - g) + b * g).astype(np.uint8)
            _BASE["polos"] = Image.fromarray(np.repeat(arr, size[0], axis=1), "RGB")
        img = _BASE["polos"].copy()
    elemen_latar(img, T, ctx)
    return img


def elemen_latar(img, T, ctx):
    jenis = ctx.content.get("bg_element", "partikel")
    warna = D.campur(ctx.aksen, D.CREAM, 0.35)
    if jenis == "partikel":
        D.partikel_lapangan(img, T, 26, (20, 180, 1060, 1900), warna, "bg", (4, 11), 0.22, 16)
    elif jenis == "bintang":
        rr = D.rng("bgbintang")
        for i in range(34):
            x, y = rr.uniform(30, 1050), rr.uniform(180, 1880)
            ph = rr.uniform(0, 6.28)
            a = 0.10 + 0.14 * (0.5 + 0.5 * math.sin(T * 1.7 + ph))
            D.kilau4(img, x, y, rr.uniform(8, 16), warna, a, rot=T * 8 + ph * 20)
    elif jenis == "grid":
        off = (T * 12) % 60
        for gx in range(0, 1100, 60):
            for gy in range(180, 1920, 60):
                D.circ(img, gx + 30, gy + off, 2.6, warna, 0.28)
    elif jenis == "gelombang":
        for i in range(6):
            y = 300 + i * 280
            D.polyline(img, D.gel_pts(-20, 1100, y, 18, 420, T * 1.2 + i), 3, warna, 0.18)


# ============================================================================ layout dasar (cadangan non-v11)
def layout_dasar(img, ctx):
    sc, t = ctx.sc, ctx.t
    tipe = sc.get("type", "fact")
    vis = D.VISUALS.get(sc.get("visual", ""))
    if vis and tipe != "outro":
        vis(img, t, ctx.dur, sc)
    if tipe == "intro":
        for i, ln in enumerate(sc.get("lines", [])[:2]):
            u = D.eo(D.seg(t, 0.1 + i * 0.25, 0.6 + i * 0.25))
            size, _ = D.fit_size(ln, 940, 140, "B", 110, 50, 1)
            D.txt(img, ln, 540, 380 + i * 150 + (1 - u) * 40, size, "B", ctx.aksen if i else D.INK, u, "ms")
    elif tipe == "fact":
        u = D.eo(D.seg(t, 0.1, 0.5))
        if sc.get("badge"):
            D.chip(img, sc["badge"], 540, 250, 32, ctx.aksen, D.PUTIH, u)
        judul = sc.get("title") or sc.get("hl", "")
        size, baris = D.fit_size(judul, 940, 330, "B", 104, 44, 3)
        hl = set(sc.get("hl", "").upper().split())
        for i, b in enumerate(baris):
            y = 400 + i * size * 1.08
            x = 540 - D.txt_w(b, size) / 2
            for kata in b.split():
                w = D.txt_w(kata + " ", size)
                D.txt(img, kata, x, y + (1 - u) * 30, size, "B", ctx.aksen if kata.upper().strip(".,!?") in hl else D.INK,
                      u, "ls")
                x += w
    else:  # outro
        for i, ln in enumerate(sc.get("lines", ["SEKARANG", "KAMU TAHU"])[:2]):
            u = D.eob(D.seg(t, 0.1 + i * 0.2, 0.6 + i * 0.2))
            D.txt(img, ln, 540, 470 + i * 170, 120 if i else 90, "B", ctx.aksen if i else D.INK, u, "ms")
        u = D.eob(D.seg(t, 0.6, 1.1))
        D.chip(img, sc.get("cta", "IKUTI"), 540, 880, 56, ctx.aksen, D.PUTIH, u)
        a = D.seg(t, 0.9, 1.3)
        D.txt(img, sc.get("foot", ""), 540, 1300, 44, "SB", D.INK, a, "ms")
        D.txt(img, sc.get("foot2", ""), 540, 1390, 36, "M", D.MUTED, a, "ms")
        D.txt(img, sc.get("src", ""), 540, 1540, 30, "M", D.MUTED, a, "ms")


# ============================================================================ HUD
def hud(img, T, ctx):
    """brand + badge tema + bilah progres bersegmen (retensi)."""
    ac = ctx.aksen
    D.circ(img, 82, 96, 24, ac)
    D.circ(img, 82, 96, 9, D.PUTIH)
    D.txt(img, "Klik", 118, 96, 40, "B", D.INK, 1, "lm", catat=False)
    D.txt(img, "Tahu", 118 + D.txt_w("Klik", 40), 96, 40, "B", ac, 1, "lm", catat=False)
    badge = ctx.content.get("header_badge", "")
    if badge:
        wb = D.txt_w(badge, 26, "SB") + 44
        D.rrect(img, 1020 - wb, 74, 1020, 118, 22, D.INK, 0.9)
        D.txt(img, badge, 1020 - wb / 2, 96, 26, "SB", D.PUTIH, 1, "mm", catat=False)
    scs = ST["tl"]["scenes"]
    x0, x1, y, h, gap = 60, 1020, 152, 8, 8
    lebar = (x1 - x0 - gap * (len(scs) - 1)) / len(scs)
    for i, s in enumerate(scs):
        xa = x0 + i * (lebar + gap)
        D.rrect(img, xa, y, xa + lebar, y + h, h / 2, D.campur(D.CREAM, D.INK, 0.14))
        f = D.clamp((T - s["start"]) / s["dur"])
        if f > 0:
            D.rrect(img, xa, y, xa + max(h, lebar * f), y + h, h / 2, ac if i == ctx.k else D.INK)


# ============================================================================ kamera & transisi (cadangan)
def _kamera_dasar(img, T, ctx):
    s = 1.02 + 0.004 * math.sin(T * 0.7)
    dx = 4 * math.sin(T * 0.53) * ST["ss"]
    dy = 4 * math.cos(T * 0.41) * ST["ss"]
    W, H = img.size
    a = 1 / s
    data = (a, 0, W / 2 - a * (W / 2 + dx), 0, a, H / 2 - a * (H / 2 + dy))
    return img.transform(img.size, Image.AFFINE, data, Image.BILINEAR)


TRANSISI = ["zoomthru", "tinta", "cahaya", "speed", "glint", "split", "zoom", "bands", "iris", "rise", "punch",
            "slide", "glitch", "whip"]
T_OUT, T_IN = 0.22, 0.30


def jenis_transisi(k):
    """transisi MASUK ke adegan k (k>=1): field 'trans' eksplisit atau bergilir otomatis."""
    sc = ST["content"]["scenes"][k]
    return sc.get("trans") or TRANSISI[(k * 5 + 3) % len(TRANSISI)]


def terapkan_transisi(img, ctx):
    k, t, dur = ctx.k, ctx.t, ctx.dur
    fx = ST["fx"]
    fase = u = None
    if k > 0 and t < T_IN:
        fase, u, jenis = "masuk", t / T_IN, jenis_transisi(k)
    elif k < ctx.n - 1 and t > dur - T_OUT:
        fase, u, jenis = "keluar", (t - (dur - T_OUT)) / T_OUT, jenis_transisi(k + 1)
    if fase is None:
        return img
    if fx is not None:
        return fx.transisi(img, jenis, fase, u, ctx.aksen, seed=k)
    a = (1 - u) if fase == "masuk" else u
    return Image.blend(img, Image.new("RGB", img.size, D.CREAM), D.eio(a))


# ============================================================================ frame
def render_frame(fi):
    fps = ST["fps"]
    T = fi / fps
    k = adegan_di(T)
    ctx = Ctx(k, T, fi)
    D.KOTAK_TEKS.clear()
    img = latar(T, ctx)
    v11 = ST["v11"]
    if v11 is not None:
        v11.gambar_adegan(img, ctx)
    else:
        layout_dasar(img, ctx)
    fx = ST["fx"]
    if fx is not None:
        img = fx.kamera(img, T, ctx, ST["beats"], ST["ss"])
    else:
        img = _kamera_dasar(img, T, ctx)
    img = terapkan_transisi(img, ctx)
    hud(img, T, ctx)
    if img.size != (W0, H0):
        img = img.resize((W0, H0), Image.LANCZOS)
    if ST["sharpen"] > 0:
        img = img.filter(ImageFilter.UnsharpMask(radius=1.1, percent=ST["sharpen"], threshold=2))
    if fx is not None:
        img = fx.finishing(img, "krem", fi, ctx)
    return img


def _kerja_png(args):
    fi, outdir = args
    render_frame(fi).save(Path(outdir) / f"f_{fi:05d}.png", compress_level=1)
    return fi


def _kerja_raw(fi):
    return render_frame(fi).tobytes()


def _kerja_img(T):
    return render_frame(int(round(T * ST["fps"])))


# ============================================================================ CLI
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug")
    ap.add_argument("--fps", type=int)
    ap.add_argument("--ss", type=float)
    ap.add_argument("--sharpen", type=int)
    ap.add_argument("--jobs", type=int)
    ap.add_argument("--range", default="")
    ap.add_argument("--outdir", default="")
    ap.add_argument("--pipe", action="store_true")
    ap.add_argument("--times", default="")
    ap.add_argument("--sheet", nargs="?", const="auto", default=None)
    ap.add_argument("--nofx", action="store_true")
    a = ap.parse_args()
    siapkan(a.slug, a.fps, a.ss, a.sharpen, fx_on=not a.nofx)
    jobs = a.jobs or ST["cfg"].i("JOBS", os.cpu_count() or 2)
    total = ST["tl"]["frames"] if ST["fps"] == ST["tl"]["fps"] else int(round(ST["tl"]["total"] * ST["fps"]))
    t0 = time.time()
    if a.times:
        if a.times == "auto":
            tt = mu.preview_times(ST["tl"], 10)
        else:
            tt = [(float(x), f"t={float(x):.2f}") for x in a.times.split(",")]
        with Pool(min(jobs, len(tt))) as pool:
            imgs = pool.map(_kerja_img, [x for x, _ in tt])
        labels = [f"{lb} ({x:.2f}s)" for x, lb in tt]
        out = a.sheet if a.sheet not in (None, "auto") else str(ST["bdir"] / "pratinjau.jpg")
        mu.sheet(imgs, labels, cols=5, lebar=300, judul=f"{ST['tl']['slug']} - pratinjau", path=out)
        prat = mu.ROOT / "pratinjau"
        prat.mkdir(exist_ok=True)
        if a.sheet == "auto" or a.sheet is None:
            mu.sheet(imgs, labels, cols=5, lebar=300, judul=f"{ST['tl']['slug']} - pratinjau",
                     path=prat / f"{ST['tl']['slug']}_pratinjau.jpg")
        for (x, lb), im in zip(tt, imgs):
            im.save(ST["bdir"] / f"pratinjau_{x:07.2f}.png")
        print(f"pratinjau {len(imgs)} frame -> {out} ({time.time() - t0:.1f} s)", file=sys.stderr)
        return
    lo, hi = 0, total
    if a.range:
        s_lo, s_hi = a.range.split(":")
        lo = int(s_lo or 0)
        hi = min(total, int(s_hi or total))
    frames = list(range(lo, hi))
    if a.pipe:
        out = sys.stdout.buffer
        with Pool(jobs) as pool:
            for b in pool.imap(_kerja_raw, frames, chunksize=2):
                out.write(b)
        out.flush()
    else:
        outdir = Path(a.outdir or (ST["bdir"] / "frames"))
        outdir.mkdir(parents=True, exist_ok=True)
        with Pool(jobs) as pool:
            for i, _ in enumerate(pool.imap(_kerja_png, [(f, str(outdir)) for f in frames], chunksize=2)):
                if (i + 1) % 60 == 0:
                    el = time.time() - t0
                    print(f"  {i + 1}/{len(frames)} frame, {el / (i + 1):.2f} s/frame", file=sys.stderr)
    el = time.time() - t0
    print(f"render {len(frames)} frame [{lo}:{hi}] dalam {el:.1f} s ({el / max(1, len(frames)):.3f} s/frame, "
          f"jobs {jobs})", file=sys.stderr)


if __name__ == "__main__":
    main()
