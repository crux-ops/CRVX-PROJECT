#!/usr/bin/env python3
"""check_layout.py - audit tata letak & margin SEBELUM render.

Untuk tiap adegan, render lapisan KONTEN saja (tanpa kamera/transisi/HUD/FX) di beberapa waktu, lalu:
  * ukur "tinta" (piksel yang beda dari latar pada T yang sama) di margin aman 40 px -> harus bersih
  * periksa kotak teks tercatat (diagrams.KOTAK_TEKS):
      - di dalam margin 40 px, tidak menabrak HUD (y >= 175)
      - teks penting tidak di y > 1640 (tertutup UI YouTube)
      - teks tidak di x > 950 pada y 1100-1700 (kolom tombol kanan)
  * zona y 180-650 harus terisi (tidak kosong) pada saat isi penuh
  * HUD sendiri di dalam margin
Hasil: tabel + montase beranotasi build/<slug>/check_layout.jpg. Gagal -> exit 1.

Pakai: python3 check_layout.py <slug> [--ss 1.0]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import diagrams as D  # noqa: E402
import mesin_util as mu  # noqa: E402
import render as R  # noqa: E402

MARGIN = 40
HUD_BAWAH = 175
BATAS_BAWAH = 1640
KOLOM_X, KOLOM_Y0, KOLOM_Y1 = 950, 1100, 1700
TOL_PX = 25  # toleransi tinta anti-alias di margin (piksel pada skala SS)


def render_konten(k, T):
    ctx = R.Ctx(k, T, int(round(T * R.ST["fps"])))
    D.KOTAK_TEKS.clear()
    bg = R.latar(T, ctx)
    img = bg.copy()
    if R.ST["v11"] is not None:
        R.ST["v11"].gambar_adegan(img, ctx)
    else:
        R.layout_dasar(img, ctx)
    return bg, img, list(D.KOTAK_TEKS), ctx


def cek_kotak(boxes):
    masalah = []
    for x0, y0, x1, y1, s in boxes:
        lbl = f"'{s[:22]}'"
        if x0 < MARGIN or x1 > 1080 - MARGIN or y1 > 1920 - MARGIN:
            masalah.append(f"teks {lbl} keluar margin ({x0:.0f},{y0:.0f},{x1:.0f},{y1:.0f})")
        if y0 < HUD_BAWAH:
            masalah.append(f"teks {lbl} menabrak HUD (y0={y0:.0f})")
        if y1 > BATAS_BAWAH:
            masalah.append(f"teks {lbl} di y>{BATAS_BAWAH} (y1={y1:.0f})")
        if x1 > KOLOM_X and y1 > KOLOM_Y0 and y0 < KOLOM_Y1:
            masalah.append(f"teks {lbl} di kolom tombol kanan (x1={x1:.0f}, y {y0:.0f}-{y1:.0f})")
    return masalah


def anotasi(img, boxes, ss):
    im = img.copy()
    d = ImageDraw.Draw(im, "RGBA")
    S = lambda v: v * ss  # noqa: E731
    W, H = im.size
    d.rectangle((0, 0, S(MARGIN), H), fill=(255, 0, 0, 40))
    d.rectangle((W - S(MARGIN), 0, W, H), fill=(255, 0, 0, 40))
    d.rectangle((0, H - S(MARGIN), W, H), fill=(255, 0, 0, 40))
    d.rectangle((0, S(BATAS_BAWAH), W, H), fill=(255, 0, 0, 28))
    d.rectangle((S(KOLOM_X), S(KOLOM_Y0), W, S(KOLOM_Y1)), fill=(255, 120, 0, 50))
    for x0, y0, x1, y1, s in boxes:
        bad = cek_kotak([(x0, y0, x1, y1, s)])
        d.rectangle((S(x0), S(y0), S(x1), S(y1)), outline=(220, 0, 0, 255) if bad else (0, 170, 60, 255),
                    width=max(1, int(2 * ss)))
    return im


def _uji():
    """uji negatif: pelanggaran sengaja HARUS terdeteksi, tata letak benar harus bersih."""
    kasus = [
        ((100, 1650, 400, 1700, "bawah"), "y>1640"),
        ((880, 1200, 1000, 1250, "kanan"), "kolom tombol kanan"),
        ((20, 500, 300, 560, "margin"), "keluar margin"),
        ((100, 120, 300, 170, "hud"), "menabrak HUD"),
        ((100, 700, 900, 800, "benar"), None),
        ((600, 1000, 1000, 1090, "kanan-atas-boleh"), None),
    ]
    ok = True
    for box, harap in kasus:
        m = cek_kotak([box])
        lulus = (not m) if harap is None else any(harap in x for x in m)
        ok &= lulus
        print(f"  [{'OK' if lulus else 'GAGAL'}] {box[4]:<18} -> {m if m else 'bersih'}")
    D.set_ss(1.0)
    bg = Image.new("RGB", (1080, 1920), D.CREAM)
    img = bg.copy()
    D.circ(img, 20, 900, 30, D.INK)
    diff = np.abs(np.asarray(img, np.int16) - np.asarray(bg, np.int16)).max(axis=2) > 24
    tinta = int(diff[:, :MARGIN].sum())
    lulus = tinta > TOL_PX
    ok &= lulus
    print(f"  [{'OK' if lulus else 'GAGAL'}] tinta margin terdeteksi ({tinta} px)")
    print("CHECK_LAYOUT SELFTEST:", "LULUS" if ok else "GAGAL")
    raise SystemExit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--ss", type=float, default=1.0)
    ap.add_argument("--uji", action="store_true")
    a = ap.parse_args()
    if a.uji:
        _uji()
    if not a.slug:
        ap.error("slug wajib (atau --uji)")
    R.siapkan(a.slug, ss=a.ss)
    ss = R.ST["ss"]
    tl = R.ST["tl"]
    semua_ok = True
    imgs, labels = [], []
    print(f"check_layout: {tl['slug']} ({len(tl['scenes'])} adegan, SS {ss})")
    for k, s in enumerate(tl["scenes"]):
        dur = s["dur"]
        waktu = sorted({round(min(dur - R.T_OUT - 0.03, x), 3) for x in
                        (s["lead_in"] + 0.5, dur * 0.35, dur * 0.6, dur * 0.85, dur - R.T_OUT - 0.03)})
        masalah = set()
        isi_atas = 0
        last = None
        for tt in waktu:
            bg, img, boxes, ctx = render_konten(k, s["start"] + tt)
            diff = np.abs(np.asarray(img, np.int16) - np.asarray(bg, np.int16)).max(axis=2) > 24
            m = int(round(MARGIN * ss))
            H, W = diff.shape
            tinta_margin = int(diff[:, :m].sum() + diff[:, W - m:].sum() + diff[H - m:, :].sum())
            if tinta_margin > TOL_PX:
                ys, xs = np.nonzero(np.concatenate([diff[:, :m], diff[:, W - m:]], axis=1))
                masalah.add(f"tinta di margin 40 px: {tinta_margin} px (t={tt:.2f})")
            masalah.update(cek_kotak(boxes))
            isi_atas = max(isi_atas, int(diff[int(180 * ss):int(650 * ss), :].sum()))
            last = (img, boxes)
        if isi_atas < 4000 * ss * ss:
            masalah.add(f"zona y 180-650 kosong (tinta {isi_atas} px)")
        ok = not masalah
        semua_ok &= ok
        print(f"  {s['id']:<10} {len(waktu)} waktu  {'BERSIH' if ok else 'MASALAH:'}")
        for mm in sorted(masalah):
            print(f"      - {mm}")
        imgs.append(anotasi(last[0], last[1], ss))
        labels.append(f"{s['id']} {'OK' if ok else 'MASALAH'}")
    # HUD
    ctx = R.Ctx(0, 0.5, 0)
    D.KOTAK_TEKS.clear()
    hud_img = Image.new("RGB", (R.ST["Wc"], R.ST["Hc"]), D.CREAM)
    R.hud(hud_img, 0.5, ctx)
    diff = np.abs(np.asarray(hud_img, np.int16) - np.array(D.CREAM, np.int16)).max(axis=2) > 24
    m = int(round(MARGIN * ss))
    hud_margin = int(diff[:m, :].sum() + diff[:, :m].sum() + diff[:, -m:].sum())
    hud_ok = hud_margin <= TOL_PX
    semua_ok &= hud_ok
    print(f"  {'HUD':<10} {'BERSIH' if hud_ok else f'MASALAH: tinta margin {hud_margin} px'}")
    out = R.ST["bdir"] / "check_layout.jpg"
    mu.sheet(imgs, labels, cols=min(5, len(imgs)), lebar=300, judul=f"check_layout {tl['slug']}", path=out)
    print(f"montase: {out}")
    print("CHECK_LAYOUT:", "BERSIH" if semua_ok else "GAGAL")
    raise SystemExit(0 if semua_ok else 1)


if __name__ == "__main__":
    main()
