#!/usr/bin/env python3
"""long/render_long.py - CLI render video panjang 16:9.

  python3 long/render_long.py --slug <folder> --align              # align.json dari audio_proc + naskah
  python3 long/render_long.py --slug <folder> --check              # audit tata letak (zona aman 16:9) + montase
  python3 long/render_long.py --slug <folder> --sheet 3.0,12.5     # montase pratinjau (atau --sheet auto)
  python3 long/render_long.py --slug <folder> --range LO:HI --out x.mp4   # render + encode langsung
  python3 long/render_long.py --slug <folder> --pipe --range LO:HI        # rgb24 ke stdout (render_lokal.sh)

Lapisan frame: latar (default antariksa / latar(img,t,C) khusus) -> VIS[bab](img, C) -> overlay opsional
-> kartu bab (awal bab) -> kamera (kotak LANCZOS) -> transisi bab (zoomthru/tinta/whip/iris bergilir)
-> HUD (res output) -> unsharp 3x3 -> finishing 'sinema'.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from multiprocessing import Pool
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "long"))
import diagrams as D  # noqa: E402
import mesin_fx as FX  # noqa: E402
import mesin_long as L  # noqa: E402
import mesin_util as mu  # noqa: E402

ST: dict = {}
AMAN = (96, 54)  # zona aman judul 16:9 (5% tiap sisi)


def siapkan(slug, butuh_align=True):
    ep, content, cfg, bdir = mu.muat_episode(slug, "long")
    tl_p = bdir / "timeline.json"
    if not tl_p.exists():
        mu.gagal(f"{tl_p} belum ada (process_audio --long -> build_timeline --long)")
    tl = json.loads(tl_p.read_text(encoding="utf-8"))
    ss = cfg.f("SS", 1.25)
    D.set_ss(ss)
    ST.clear()
    ST.update(ep=ep, content=content, cfg=cfg, bdir=bdir, tl=tl, ss=ss, fps=cfg.i("FPS", 30),
              sharpen=cfg.i("SHARPEN", 40), Wc=int(round(L.W0 * ss)), Hc=int(round(L.H0 * ss)))
    ST["vis"] = L.muat_visual(ep)
    al_p = bdir / "align.json"
    if butuh_align:
        if not al_p.exists():
            mu.gagal(f"{al_p} belum ada - jalankan --align dulu")
        ST["words"] = json.loads(al_p.read_text(encoding="utf-8"))
        ev_p = bdir / "events.json"
        ev = json.loads(ev_p.read_text(encoding="utf-8"))["events"] if ev_p.exists() else \
            L.events_long(content, tl, ST["words"], getattr(ST["vis"], "BEATS", []))
        ST["beats"] = sorted(e["t"] for e in ev if e.get("berat"))
    return ST


def buat_align():
    bdir, content, tl = ST["bdir"], ST["content"], ST["tl"]
    out = {}
    for sc, ts in zip(content["scenes"], tl["scenes"]):
        x = mu.baca_wav(bdir / "audio_proc" / f"{sc['id']}.wav")
        out[sc["id"]] = L.align(x, sc["vo"], mu.SR, offset=ts["lead_in"])
    mu.tulis_json(bdir / "align.json", out)
    print(f"align: {sum(len(v) for v in out.values())} kata di {len(out)} bab -> {bdir / 'align.json'}")
    for bab, ws in out.items():
        print(f"  {bab}: " + " ".join(f"{w['kata']}@{w['t0']:.2f}" for w in ws[:8]) + (" ..." if len(ws) > 8 else ""))
    # validasi BEATS: semua kata beat harus ada (KeyError = gagal keras)
    ST["words"] = out
    beats = getattr(ST["vis"], "BEATS", [])
    ev = L.events_long(content, tl, out, beats)
    print(f"  BEATS kata: {len(beats)} OK, total event {len(ev)}")


def ctx_di(T, fi=0):
    tl = ST["tl"]
    k = len(tl["scenes"]) - 1
    for i, s in enumerate(tl["scenes"]):
        if T < s["start"] + s["dur"] - 1e-9:
            k = i
            break
    ts = tl["scenes"][k]
    sc = ST["content"]["scenes"][k]
    return L.Ctx(k, T - ts["start"], sc, ts, ST["words"].get(sc["id"], []), ST["content"], ST["fps"], fi)


def gambar_konten(img, C):
    vis = ST["vis"]
    fn = getattr(vis, "VIS", {}).get(C.sc["id"])
    if fn:
        fn(img, C)
    if hasattr(vis, "overlay"):
        vis.overlay(img, C.t, C)


def render_frame(fi):
    T = fi / ST["fps"]
    C = ctx_di(T, fi)
    D.KOTAK_TEKS.clear()
    size = (ST["Wc"], ST["Hc"])
    vis = ST["vis"]
    img = vis.latar(size, T, C) if hasattr(vis, "latar") else L.latar_default(size, T, C, C.aksen)
    gambar_konten(img, C)
    if C.t < L.KARTU_DUR:
        u = D.eo(D.seg(C.t, 0.0, 0.35)) * (1 - D.eio(D.seg(C.t, L.KARTU_DUR - 0.45, L.KARTU_DUR)))
        img = L.kartu_bab(img, C.k + 1, C.sc.get("judul", ""), u, C.aksen, C.t)
    box, rot = FX.kamera_box(T, None, ST["beats"], size[0], size[1], ST["ss"], kuat=0.8,
                             dasar_zoom=1.02 + 0.03 * C.u)
    img = img.resize((L.W0, L.H0), Image.LANCZOS, box=box)
    D.set_ss(1.0)
    try:
        k, t, n = C.k, C.t, len(ST["tl"]["scenes"])
        fase = None
        if k > 0 and t < L.T_IN:
            fase, u, j, km = "masuk", t / L.T_IN, L.TRANS_BAB[(k - 1) % 4], k
        elif k < n - 1 and t > C.dur - L.T_OUT:
            fase, u, j, km = "keluar", (t - (C.dur - L.T_OUT)) / L.T_OUT, L.TRANS_BAB[k % 4], k + 1
        if fase:
            ak = D.col(ST["content"]["scenes"][km].get("accent", "#2F7BFF"))
            img = FX.transisi(img, j, fase, u, ak, seed=km)
        L.hud(img, T, C, ST["tl"], ST["content"])
    finally:
        D.set_ss(ST["ss"])
    if ST["sharpen"] > 0:
        from render import _kernel_tajam
        img = img.filter(_kernel_tajam(ST["sharpen"]))
    return FX.finishing(img, "sinema", fi, C)


def _raw(fi):
    return render_frame(fi).tobytes()


def _img(T):
    return render_frame(int(round(T * ST["fps"])))


def cek_layout():
    """audit: teks di dalam zona aman 5%, tidak menabrak HUD (y<90), montase beranotasi."""
    tl = ST["tl"]
    masalah = []
    imgs, labels = [], []
    for k, s in enumerate(tl["scenes"]):
        for f in (0.2, 0.45, 0.7, 0.93):
            T = s["start"] + max(L.KARTU_DUR + 0.1, s["dur"] * f)
            T = min(T, s["start"] + s["dur"] - L.T_OUT - 0.05)
            C = ctx_di(T)
            D.KOTAK_TEKS.clear()
            img = L.latar_default((ST["Wc"], ST["Hc"]), T, C, C.aksen)
            gambar_konten(img, C)
            for x0, y0, x1, y1, tx in D.KOTAK_TEKS:
                if x0 < AMAN[0] or x1 > L.W0 - AMAN[0] or y0 < 90 or y1 > L.H0 - AMAN[1]:
                    masalah.append(f"{s['id']} t={T:.2f}: teks '{tx[:20]}' di luar zona aman "
                                   f"({x0:.0f},{y0:.0f},{x1:.0f},{y1:.0f})")
            if f == 0.7:
                imgs.append(img.resize((L.W0 // 2, L.H0 // 2)))
                labels.append(f"{s['id']} {T:.1f}s")
    mu.sheet(imgs, labels, cols=min(3, len(imgs)), lebar=520, judul=f"check long {tl['slug']}",
             path=ST["bdir"] / "check_layout.jpg")
    for m in sorted(set(masalah)):
        print("  -", m)
    print("CHECK LONG:", "BERSIH" if not masalah else "GAGAL")
    return not masalah


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--align", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--sheet", default="")
    ap.add_argument("--range", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--pipe", action="store_true")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    if a.align:
        siapkan(a.slug, butuh_align=False)
        buat_align()
        return
    siapkan(a.slug)
    if a.check:
        raise SystemExit(0 if cek_layout() else 1)
    tl = ST["tl"]
    if a.sheet:
        tt = mu.preview_times(tl, 9) if a.sheet == "auto" else [(float(x), f"t={float(x):.1f}") for x in a.sheet.split(",")]
        with Pool(min(a.jobs, len(tt))) as pool:
            imgs = pool.map(_img, [x for x, _ in tt])
        out = ST["bdir"] / "pratinjau.jpg"
        mu.sheet(imgs, [f"{lb} ({x:.1f}s)" for x, lb in tt], cols=3, lebar=560, judul=f"{tl['slug']} pratinjau", path=out)
        (mu.ROOT / "pratinjau").mkdir(exist_ok=True)
        mu.sheet(imgs, [f"{lb} ({x:.1f}s)" for x, lb in tt], cols=3, lebar=560, judul=f"{tl['slug']} pratinjau",
                 path=mu.ROOT / "pratinjau" / f"long_{tl['slug']}_pratinjau.jpg")
        print(f"pratinjau -> {out}")
        return
    total = tl["frames"]
    lo, hi = 0, total
    if a.range:
        s_lo, s_hi = a.range.split(":")
        lo, hi = int(s_lo or 0), min(total, int(s_hi or total))
    frames = list(range(lo, hi))
    t0 = time.time()
    if a.pipe:
        with Pool(a.jobs) as pool:
            for b in pool.imap(_raw, frames, chunksize=2):
                sys.stdout.buffer.write(b)
        sys.stdout.buffer.flush()
    elif a.out:
        cfg = ST["cfg"]
        cmd = [mu.ffmpeg_exe(), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{L.W0}x{L.H0}",
               "-r", str(ST["fps"]), "-i", "-", "-c:v", "libx264", "-preset", cfg.s("PRESET", "slow"), "-tune",
               cfg.s("TUNE", "animation"), "-pix_fmt", "yuv420p", "-b:v", cfg.s("VBITRATE", "9000k"), a.out]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        with Pool(a.jobs) as pool:
            for b in pool.imap(_raw, frames, chunksize=2):
                p.stdin.write(b)
        p.stdin.close()
        p.wait()
    el = time.time() - t0
    print(f"render long {len(frames)} frame dalam {el:.1f} s ({el / max(1, len(frames)):.3f} s/frame)", file=sys.stderr)


if __name__ == "__main__":
    main()
