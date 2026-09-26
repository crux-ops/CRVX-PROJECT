#!/usr/bin/env python3
"""mesin_v11.py - paket motion "EDITOR" KlikTahu (Shorts).

Isi:
  * Tipografi kinetik: judul kata-per-kata (skala 1.5 -> 1 dengan pegas, terangkat dari balik mask + blur
    vertikal sebanding kecepatan) + sapuan STABILO di belakang kata kunci `hl`.
  * Stiker tebal: outline putih + bayangan keras + pop overshoot + goyang. Chip label. Penanda "FAKTA n/N".
  * Gerak & cahaya: glow, panah bezier menggambar diri, gelombang berjalan, busur pancaran, ledakan partikel.
  * BEATS = SATU sumber kebenaran: BEATS[visual] = [(fraksi_durasi, sfx), ...]. Fungsi gambar memakai fraksi
    yang SAMA (lewat bt()), jadi animasi, SFX (master_audio) dan dorongan kamera (render) jatuh di frame sama.
    events(content, timeline) -> daftar event SFX (transisi + tipografi + beat visual).
  * Layout adegan v11: intro / fact / outro (gambar_adegan).
  * Modul episode `mesin_v11_epNN.py` (fungsi sc_*NN + tabel beat bernama) diimpor otomatis HANYA bila
    __name__ != "__main__" (hindari impor melingkar). Modul episode mengisi VISUALS_EP & BEAT_TABEL_EP.
Selftest: python3 mesin_v11.py
"""
from __future__ import annotations

import importlib
import math
import os
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import diagrams as D  # noqa: E402
import mesin_util as mu  # noqa: E402

ROOT = Path(__file__).resolve().parent
INK, CREAM, MUTED, PUTIH = D.INK, D.CREAM, D.MUTED, D.PUTIH

# ============================================================================ waktu tipografi (dipakai layout DAN events)
TIPO = {
    "intro_baris": (-0.14, 0.28),  # awal tiap baris hook; negatif = kata pertama sudah tampil di frame 0
    "stagger": 0.075,              # jeda antar kata
    "fakta_penanda": 0.12,
    "fakta_chip": 0.30,
    "fakta_judul": 0.44,
    "stabilo_tunda": 0.24,         # stabilo mulai sekian detik setelah kata kunci mendarat
    "stabilo_dur": 0.34,
    "outro_baris": (0.10, 0.34),
    "outro_cta": 0.95,
}
TRANS_SFX = {
    "zoomthru": "whoosh", "tinta": "swish", "cahaya": "kilau", "speed": "whoosh", "glint": "kilau",
    "split": "swish_up", "zoom": "whoosh", "bands": "swish", "iris": "swish_up", "rise": "swish_up",
    "punch": "impact", "slide": "swish", "glitch": "glitch", "whip": "swish",
}
BERAT = {"impact", "thud", "boom", "guntur", "pukul", "detak"}  # beat berat -> dorongan kamera

BEATS: dict = {}       # visual -> [(fraksi, sfx), ...]
BEAT_TABEL: dict = {}  # visual -> {nama: (fraksi, sfx)}


def daftar_beat(visual, tabel):
    BEAT_TABEL[visual] = dict(tabel)
    BEATS[visual] = sorted(tabel.values())


def bt(visual, nama, dur):
    """waktu beat bernama (detik sejak awal adegan) - dipakai fungsi gambar."""
    return BEAT_TABEL[visual][nama][0] * dur


# ============================================================================ util gambar
def _vblur(mask, r):
    """blur vertikal (box, radius r px) untuk mask L kecil."""
    r = int(round(r))
    if r < 1:
        return mask
    a = np.asarray(mask, np.float32)
    pad = np.pad(a, ((r, r), (0, 0)), mode="constant")
    c = np.cumsum(pad, axis=0)
    c = np.vstack([np.zeros((1, a.shape[1]), np.float32), c])
    out = (c[2 * r + 1:] - c[:-2 * r - 1]) / (2 * r + 1)
    return Image.fromarray(np.clip(out[:a.shape[0]], 0, 255).astype(np.uint8), "L")


def _stabilo(img, x0, x1, base, size, warna, q, a=1.0, seed=0):
    """sapuan stabilo di belakang kata (q = progres 0..1, kiri->kanan), ujung sedikit kasar."""
    if q <= 0.01:
        return
    ch = D.cap_h(size)
    pad = size * 0.10
    xa = x0 - pad
    xb = xa + (x1 - x0 + 2 * pad) * D.clamp(q)
    y0, y1 = base - ch * 0.78, base + size * 0.14
    D.rrect(img, xa, y0 + size * 0.03, xb, y1, size * 0.10, warna, 0.92 * a)
    D.rrect(img, xa + size * 0.06, y0 - size * 0.02, max(xa + size * 0.07, xb - size * 0.05), y1 - size * 0.06,
            size * 0.12, warna, 0.55 * a)


def _norm(s):
    return "".join(ch for ch in s.upper() if ch.isalnum())


# ============================================================================ tipografi kinetik
def tata_judul(teks, size, max_w, max_h, w="B", maks_baris=3, lh=1.06):
    """-> (size_final, [(kata, x_kiri, baris_idx), ...], lebar_baris[]) posisi relatif (x terpusat 0)."""
    size, baris = D.fit_size(teks, max_w, max_h, w, int(size), 36, maks_baris, lh)
    kata = []
    for bi, b in enumerate(baris):
        lw = D.txt_w(b, size, w)
        x = -lw / 2
        for k in b.split():
            kata.append((k, x, bi))
            x += D.txt_w(k + " ", size, w)
    return size, kata, len(baris)


def indeks_hl(kata, hl):
    target = {_norm(x) for x in (hl or "").split() if _norm(x)}
    return [i for i, (k, _, _) in enumerate(kata) if _norm(k) in target]


def waktu_stabilo(t0, idx_hl, stagger=None):
    stg = TIPO["stagger"] if stagger is None else stagger
    return t0 + (min(idx_hl) if idx_hl else 0) * stg + TIPO["stabilo_tunda"]


def judul_kinetik(img, teks, cx, y0, size, t, t0, aksen, hl="", w="B", warna=INK, max_w=940, max_h=300,
                  maks_baris=3, lh=1.06, stabilo=True, warna_stabilo=None, stagger=None, a=1.0):
    """Judul kata-per-kata. y0 = baseline baris pertama. -> (size, jumlah_baris)."""
    stg = TIPO["stagger"] if stagger is None else stagger
    size, kata, nb = tata_judul(teks, size, max_w, max_h, w, maks_baris, lh)
    idx = set(indeks_hl(kata, hl))
    ch = D.cap_h(size, w)
    wst = warna_stabilo or D.campur(aksen, CREAM, 0.34)
    # 1) stabilo (di belakang)
    if stabilo and idx:
        for bi in range(nb):
            ids = [i for i in sorted(idx) if kata[i][2] == bi]
            if not ids:
                continue
            ts = waktu_stabilo(t0, ids, stg)
            q = D.eo(D.seg(t, ts, ts + TIPO["stabilo_dur"]))
            k0, k1 = kata[ids[0]], kata[ids[-1]]
            base = y0 + bi * size * lh
            _stabilo(img, cx + k0[1], cx + k1[1] + D.txt_w(k1[0], size, w), base, size, wst, q, a)
    # 2) kata
    for i, (k, xl, bi) in enumerate(kata):
        tw = t - (t0 + i * stg)
        base = y0 + bi * size * lh
        wd = D.txt_w(k, size, w)
        if tw <= 0:
            continue
        p = D.pegas(tw, 0.55, 17.0)
        sk = 1.5 - 0.5 * p
        naik = 1 - D.eo(tw / 0.30)
        off = naik * size * 0.95
        vel = abs(3 * (1 - min(1, tw / 0.30)) ** 2 / 0.30 * size * 0.95)  # turunan offset
        alpha = D.clamp(tw / 0.07) * a
        warna_k = warna
        if sk > 0.999 and off < 0.2:
            D.txt(img, k, cx + xl, base, size, w, warna_k, alpha, "ls")
            continue
        px = max(4, int(round(D.S(size) * sk)))
        m, adv, asc, padl = D._txt_mask(k, w, px)
        br = min(D.S(vel) * 0.012, D.S(size) * 0.12)
        if br >= 1:
            m = _vblur(m, br)
        chs = ch * sk
        cxw = cx + xl + wd / 2
        cy_cap = base - ch / 2 + off
        X = D.S(cxw) - adv / 2 - padl
        Y = D.S(cy_cap + chs / 2) - asc
        # JENDELA kata: bawah = dasar kotak baris (kata terangkat dari baliknya), atas = sedikit di atas
        # huruf kapital, kiri/kanan = slot kata + sedikit ruang -> kata berskala 1.5 tidak menumpuk tetangga
        pad = size * 0.10
        wx0, wx1 = D.S(cx + xl - pad), D.S(cx + xl + wd + pad)
        wy0, wy1 = D.S(base - ch * 1.40), D.S(base + size * 0.30)
        cx0 = int(max(0, wx0 - X))
        cy0 = int(max(0, wy0 - Y))
        cx1 = int(min(m.size[0], wx1 - X))
        cy1 = int(min(m.size[1], wy1 - Y))
        if cx1 <= cx0 or cy1 <= cy0:
            continue
        m = m.crop((cx0, cy0, cx1, cy1))
        D.tempel(img, warna_k, round(X) + cx0, round(Y) + cy0, m, alpha)
        if alpha > 0.05:
            D.KOTAK_TEKS.append((cx + xl, base - ch * 1.02, cx + xl + wd, base + size * 0.24, k))
    return size, nb


# ============================================================================ stiker, penanda, efek
@lru_cache(maxsize=64)
def _stiker_sprite(teks, px, bg, fg, ikon, ss):
    f = D.font_px("B", px)
    m, adv, asc, padl = D._txt_mask(teks, "B", px)
    ikw = int(px * 0.9) if ikon else 0
    padx, pady = int(px * 0.55), int(px * 0.34)
    cap = -f.getbbox("H", anchor="ls")[1]
    w = int(adv + 2 * padx + ikw)
    h = int(cap + 2 * pady + px * 0.18)
    o = max(3, int(px * 0.16))
    sh = max(3, int(px * 0.12))
    W, H = w + 2 * o + sh + 4, h + 2 * o + sh + 4
    konten = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    box = D._rrect_mask(w, h, int(h * 0.32))
    konten.paste(bg, (o, o), box)
    ty = o + pady + cap - asc + int(px * 0.05)
    konten.paste(fg, (o + padx + ikw - padl, ty), m)
    if ikon == "plus":
        cxp, cyp, L = o + padx + ikw * 0.35, o + h / 2, ikw * 0.30
        t_ = max(2, int(px * 0.13))
        konten.paste(fg, (int(cxp - L), int(cyp - t_ / 2), int(cxp + L), int(cyp + t_ / 2)))
        konten.paste(fg, (int(cxp - t_ / 2), int(cyp - L), int(cxp + t_ / 2), int(cyp + L)))
    alpha = konten.getchannel("A")
    garis = alpha.filter(ImageFilter.GaussianBlur(float(o * 0.55))).point(lambda v: 255 if v > 28 else int(v * 9))
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bay = Image.new("RGBA", (W, H), D.INK + (0,))
    bay.putalpha(garis.point(lambda v: int(v * 0.92)))
    out.alpha_composite(bay, (sh, sh))
    putih = Image.new("RGBA", (W, H), PUTIH + (0,))
    putih.putalpha(garis)
    out.alpha_composite(putih)
    out.alpha_composite(konten)
    return out


def stiker(img, teks, cx, cy, t, t0, size=46, warna="#FF6B3D", fg=None, rot=-5.0, ikon=None, a=1.0, goyang=True):
    """stiker tebal (outline putih + bayangan keras) dengan pop overshoot + goyang.

    fg=None -> warna teks dipilih otomatis agar kontras >= 3.0 terhadap latar aksen (teks putih di atas aksen
    terang pernah tidak terbaca; lihat AGEN.md §7 RENDER Ep50).
    """
    tw = t - t0
    if tw <= 0 or a <= 0.01:
        return None
    if fg is None:
        fg = D.teks_terbaca(D.col(warna))
    s = D.eob(D.clamp(tw / 0.32), 2.2)
    r = rot + (7.5 * math.exp(-4.0 * tw) * math.sin(15 * tw) if goyang else 0) + 1.1 * math.sin(t * 2.2)
    spr = _stiker_sprite(teks, D.fpx(size), D.col(warna), D.col(fg), ikon, D.SS)
    if s <= 0.02:
        return None
    w, h = spr.size
    spr = spr.resize((max(2, int(w * s)), max(2, int(h * s))), Image.BICUBIC).rotate(r, Image.BICUBIC, expand=True)
    if a < 0.99:
        spr.putalpha(D.amask(spr.getchannel("A"), a))
    X, Y = D.S(cx) - spr.size[0] / 2, D.S(cy) - spr.size[1] / 2
    img.paste(spr.convert("RGB"), (int(round(X)), int(round(Y))), spr.getchannel("A"))
    bw, bh = w / D.SS / 2, h / D.SS / 2
    box = (cx - bw, cy - bh, cx + bw, cy + bh)
    if tw > 0.1:
        D.KOTAK_TEKS.append((*box, teks))
    return box


def chip_pop(img, teks, cx, cy, t, t0, size=30, warna="#2F7BFF", fg=None):
    """chip label dengan pop. fg=None -> pilih PUTIH/INK otomatis (kontras >= 3.0 terhadap aksen)."""
    tw = t - t0
    if tw <= 0:
        return
    if fg is None:
        fg = D.teks_terbaca(D.col(warna))
    s = D.eob(D.clamp(tw / 0.3))
    a = D.clamp(tw / 0.12)
    tw_ = D.txt_w(teks, size)
    pw, ph = (tw_ + size * 1.3) * s, size * 1.7 * s
    D.rrect(img, cx - pw / 2 + 5, cy - ph / 2 + 6, cx + pw / 2 + 5, cy + ph / 2 + 6, ph / 2, INK, 0.9 * a)
    D.rrect(img, cx - pw / 2, cy - ph / 2, cx + pw / 2, cy + ph / 2, ph / 2, warna, a)
    if s > 0.6:
        D.txt(img, teks, cx, cy, size * min(1.0, s), "B", fg, a, "mm")


def penanda_fakta(img, n, total, x, y, aksen, t, t0):
    """'FAKTA n/N' + segmen progres (n terisi, segmen aktif berdenyut)."""
    u = D.eo(D.seg(t, t0, t0 + 0.35))
    if u <= 0:
        return
    teks = f"FAKTA {n}/{total}"
    D.txt(img, teks, x - (1 - u) * 30, y, 30, "B", INK, u, "lm")
    x0 = x + D.txt_w(teks, 30) + 22
    for i in range(total):
        xa = x0 + i * 40
        if xa + 32 > 1020:
            break
        isi = i < n
        warna = aksen if isi else D.campur(CREAM, INK, 0.16)
        hh = 9 + (3 * (0.5 + 0.5 * math.sin(t * 6)) if i == n - 1 else 0)
        D.rrect(img, xa, y - hh / 2, xa + 32 * D.eo(D.seg(t, t0 + 0.05 * i, t0 + 0.05 * i + 0.3)), y + hh / 2,
                hh / 2, warna, u)


def busur_pancaran(img, cx, cy, t, warna, n=3, r0=60, r1=330, a0=-55, a1=55, lebar=10, kec=0.7, a=0.8):
    for k in range(n):
        ph = (t * kec + k / n) % 1.0
        D.ring(img, cx, cy, r0 + (r1 - r0) * ph, lebar * (1 - 0.5 * ph), warna, a * (1 - ph), a0, a1)


def ledakan(img, cx, cy, ts, warna, seed=0, n=16, jarak=170, dur=0.65, a=1.0):
    """ledakan partikel saat elemen muncul (ts = detik sejak muncul)."""
    if not (0 <= ts < dur):
        return
    u = ts / dur
    rr = D.rng("ledak", seed)
    for i in range(n):
        ang = rr.uniform(0, 2 * math.pi)
        spd = rr.uniform(0.5, 1.0)
        r = jarak * spd * D.eo(u)
        x, y = cx + math.cos(ang) * r, cy + math.sin(ang) * r + 60 * u * u
        sz = rr.uniform(5, 12) * (1 - u)
        if i % 3 == 0:
            D.kilau4(img, x, y, sz * 1.8, warna, a * (1 - u), rot=ang * 57)
        else:
            D.circ(img, x, y, sz, warna, a * (1 - u))
    D.ring(img, cx, cy, jarak * 1.05 * D.eo(u), 7 * (1 - u) + 1, warna, 0.55 * a * (1 - u))


def gelombang_jalan(img, x0, x1, y, amp, lam, t, warna, lebar=8, kec=4.0, a=1.0, u=1.0):
    pts = D.gel_pts(x0, x0 + (x1 - x0) * D.clamp(u), y, amp, lam, t * kec)
    if len(pts) > 1:
        D.polyline(img, pts, lebar, warna, a)


def panah_bezier(img, p0, p1, p2, p3, lebar, warna, u, a=1.0):
    D.panah(img, D.bezier(p0, p1, p2, p3), lebar, warna, u, a)


# ============================================================================ layout adegan
def _fx():
    try:
        import mesin_fx
        return mesin_fx if mesin_fx.AKTIF else None
    except ImportError:
        return None


JUDUL_MAX_H, JUDUL_PUSAT = 300, 500


def y_judul(judul, lh=1.06):
    """baseline baris pertama agar blok judul terpusat di zona y 340-660."""
    size, kata, nb = tata_judul(judul, 104, 950, JUDUL_MAX_H, "B", 3, lh)
    return JUDUL_PUSAT - (nb - 1) * size * lh / 2 + D.cap_h(size) / 2


INTRO_MAJU = 0.45  # visual generik (tanpa BEATS) di intro dimajukan agar frame 0 sudah berisi


def layout_intro(img, ctx):
    sc, t = ctx.sc, ctx.t
    vis = D.VISUALS.get(sc.get("visual", ""))
    if vis:
        vis(img, t + (0.0 if sc.get("visual") in BEATS else INTRO_MAJU), ctx.dur, sc)
    lines = (sc.get("lines") or ["", ""])[:2]
    t1, t2 = TIPO["intro_baris"]
    s1, _ = judul_kinetik(img, lines[0], 540, 360, 104, t, t1, ctx.aksen, "", max_w=960, max_h=130, maks_baris=1,
                          stabilo=False)
    if len(lines) > 1:
        hl = sc.get("hl") or lines[1].split()[-1]
        judul_kinetik(img, lines[1], 540, 360 + s1 * 1.12 + 22, 104, t, t2, ctx.aksen, hl, max_w=960,
                      max_h=130, maks_baris=1)
    if sc.get("stiker"):
        stiker(img, sc["stiker"], 820, 250, t, 1.0, 40, ctx.aksen, rot=6)


def layout_fact(img, ctx):
    sc, t = ctx.sc, ctx.t
    vis = D.VISUALS.get(sc.get("visual", ""))
    if vis:
        vis(img, t, ctx.dur, sc)
    if ctx.fakta_no:
        penanda_fakta(img, ctx.fakta_no, ctx.fakta_total, 62, 222, ctx.aksen, t, TIPO["fakta_penanda"])
    if sc.get("badge"):
        chip_pop(img, sc["badge"], 540, 300, t, TIPO["fakta_chip"], 30, ctx.aksen)
    judul = sc.get("title") or sc.get("hl", "")
    judul_kinetik(img, judul, 540, y_judul(judul), 104, t, TIPO["fakta_judul"], ctx.aksen, sc.get("hl", ""),
                  max_w=950, max_h=JUDUL_MAX_H, maks_baris=3)


def _logo(img, cx, cy, size, aksen, t, a=1.0):
    r = size * 0.62
    D.glow(img, cx - D.txt_w("KlikTahu", size) / 2 - r * 0.9, cy, r * 2.4, aksen, 0.25 * a)
    lx = cx - (D.txt_w("KlikTahu", size) + r * 2.6) / 2
    D.circ(img, lx + r, cy, r, aksen, a)
    D.circ(img, lx + r, cy, r * 0.38, PUTIH, a)
    D.ring(img, lx + r, cy, r * (1.25 + 0.15 * math.sin(t * 3)), 4, aksen, 0.45 * a)
    D.txt(img, "Klik", lx + r * 2.6, cy, size, "B", INK, a, "lm")
    D.txt(img, "Tahu", lx + r * 2.6 + D.txt_w("Klik", size), cy, size, "B", aksen, a, "lm")


def layout_outro(img, ctx):
    sc, t = ctx.sc, ctx.t
    ak = ctx.aksen
    lines = (sc.get("lines") or ["SEKARANG", "KAMU TAHU"])[:2]
    b1, b2 = TIPO["outro_baris"]
    judul_kinetik(img, lines[0], 540, 410, 84, t, b1, ak, "", max_w=940, max_h=110, maks_baris=1, stabilo=False)
    if len(lines) > 1:
        judul_kinetik(img, lines[1], 540, 580, 136, t, b2, ak, lines[1], max_w=960, max_h=160, maks_baris=1)
    tc = TIPO["outro_cta"]
    for k in range(2):
        ph = ((t - tc) * 0.8 + k * 0.5) % 1.0
        if t > tc + 0.3:
            D.ring(img, 540, 800, 120 + 150 * ph, 6, ak, 0.35 * (1 - ph))
    stiker(img, sc.get("cta", "IKUTI"), 540, 800, t, tc, 60, ak, rot=-4, ikon="plus")
    ledakan(img, 540, 800, t - tc - 0.05, ak, 7, 18, 230)
    a = D.eo(D.seg(t, 1.3, 1.7))
    _logo(img, 540, 1060, 70, ak, t, a)
    if sc.get("foot"):
        D.txt(img, sc["foot"], 540, 1240, 40, "SB", INK, D.eo(D.seg(t, 1.5, 1.9)), "ms")
    if sc.get("foot2"):
        D.txt(img, sc["foot2"], 540, 1318, 32, "M", MUTED, D.eo(D.seg(t, 1.65, 2.05)), "ms")
    if sc.get("src"):
        a3 = D.eo(D.seg(t, 1.8, 2.2))
        wsrc = min(820, D.txt_w(sc["src"], 28, "M") + 60)
        D.rrect(img, 540 - wsrc / 2, 1440, 540 + wsrc / 2, 1506, 33, PUTIH, 0.8 * a3)
        D.txt(img, sc["src"], 540, 1473, 28, "M", MUTED, a3, "mm")
    rr = D.rng("outro", sc.get("id", ""))
    for i in range(10):
        x, y0 = rr.uniform(90, 990), rr.uniform(700, 1500)
        y = y0 - ((t * 40 + i * 70) % 300)
        D.kilau4(img, x, y, rr.uniform(8, 16), ak if i % 2 else "#FFB020", 0.5 * D.seg(t, 1.0, 1.5),
                 rot=t * 30 + i * 20)


def caption(img, ctx):
    """caption VO (bawaan MATI, aturan keras §2.1). Potongan 4 kata, waktu merata sepanjang VO."""
    kata = ctx.sc.get("vo", "").split()
    if not kata:
        return
    tv = ctx.t - ctx.lead
    if tv < 0 or tv > ctx.vo_dur:
        return
    n = 4
    potong = [" ".join(kata[i:i + n]) for i in range(0, len(kata), n)]
    i = min(len(potong) - 1, int(tv / ctx.vo_dur * len(potong)))
    s = potong[i]
    size = min(44, D.fit_size(s, 820, 60, "B", 44, 24, 1)[0])
    wv = D.txt_w(s, size) + 50
    D.rrect(img, 540 - wv / 2, 1530, 540 + wv / 2, 1600, 30, INK, 0.85)
    D.txt(img, s, 540, 1565, size, "B", PUTIH, 1, "mm")


def gambar_adegan(img, ctx):
    tipe = ctx.sc.get("type", "fact")
    if tipe == "intro":
        layout_intro(img, ctx)
    elif tipe == "outro":
        layout_outro(img, ctx)
    else:
        layout_fact(img, ctx)
    if os.environ.get("CAPTION", "0") == "1":
        caption(img, ctx)


# ============================================================================ events (SFX + beat)
def events(content, timeline):
    ev = []
    for k, (sc, ts) in enumerate(zip(content["scenes"], timeline["scenes"])):
        st, dur, sid = ts["start"], ts["dur"], sc["id"]
        tipe = sc.get("type", "fact")
        if k > 0:
            j = mu.jenis_transisi(content, k)
            ev.append({"t": st - 0.10, "sfx": TRANS_SFX.get(j, "whoosh"), "scene": sid, "sumber": f"transisi:{j}",
                       "gain_db": 0.0, "berat": j == "punch"})
        if tipe == "intro":
            t1, t2 = TIPO["intro_baris"]
            ev.append({"t": st + max(0.0, t1 + 0.03), "sfx": "pop", "scene": sid, "sumber": "judul1", "gain_db": -3.0})
            lines = sc.get("lines") or []
            if len(lines) > 1:
                ev.append({"t": st + t2 + 0.03, "sfx": "pop", "scene": sid, "sumber": "judul2", "gain_db": -5.0})
                _, kata, _ = tata_judul(lines[1], 104, 960, 130, "B", 1)
                idx = indeks_hl(kata, sc.get("hl") or lines[1].split()[-1])
                if idx:
                    ev.append({"t": st + waktu_stabilo(t2, idx), "sfx": "swish", "scene": sid, "sumber": "stabilo",
                               "gain_db": -9.0})
        elif tipe == "fact":
            ev.append({"t": st + TIPO["fakta_chip"], "sfx": "pop", "scene": sid, "sumber": "chip", "gain_db": -5.0})
            judul = sc.get("title") or sc.get("hl", "")
            _, kata, _ = tata_judul(judul, 104, 950, JUDUL_MAX_H, "B", 3)
            idx = indeks_hl(kata, sc.get("hl", ""))
            if idx:
                ev.append({"t": st + waktu_stabilo(TIPO["fakta_judul"], idx), "sfx": "swish", "scene": sid,
                           "sumber": "stabilo", "gain_db": -9.0})
        elif tipe == "outro":
            tc = st + TIPO["outro_cta"]
            ev.append({"t": tc, "sfx": "pop", "scene": sid, "sumber": "cta", "gain_db": 0.0})
            ev.append({"t": tc + 0.22, "sfx": "ding", "scene": sid, "sumber": "cta", "gain_db": -2.0})
        for frac, s in BEATS.get(sc.get("visual", ""), []):
            ev.append({"t": st + frac * dur, "sfx": s, "scene": sid, "sumber": f"beat:{sc.get('visual')}",
                       "gain_db": 0.0, "berat": s in BERAT})
    ev.sort(key=lambda e: e["t"])
    out = []
    for e in ev:
        e.setdefault("berat", e["sfx"] in BERAT)
        e["t"] = round(max(0.0, e["t"]), 4)
        if out and e["sfx"] == out[-1]["sfx"] and e["t"] - out[-1]["t"] < 0.06:
            continue
        out.append(e)
    return out


# ============================================================================ modul episode
def muat_episode_modul():
    """impor semua mesin_v11_ep*.py: VISUALS_EP -> diagrams.VISUALS, BEAT_TABEL_EP -> BEATS."""
    dimuat = []
    for p in sorted(ROOT.glob("mesin_v11_ep*.py")):
        mod = importlib.import_module(p.stem)
        D.VISUALS.update(getattr(mod, "VISUALS_EP", {}))
        for vis, tab in getattr(mod, "BEAT_TABEL_EP", {}).items():
            daftar_beat(vis, tab)
        dimuat.append(p.stem)
    return dimuat


if __name__ != "__main__":
    MODUL_EPISODE = muat_episode_modul()


# ============================================================================ selftest
def _uji():
    import time

    import mesin_v11 as M  # impor sebagai modul (memuat episode; hindari impor melingkar di __main__)
    import sfx as SFX
    from mesin_util import sheet
    D.set_ss(1.0)
    ok = True

    def cek(nama, kond, det=""):
        nonlocal ok
        ok &= bool(kond)
        print(f"  [{'OK' if kond else 'GAGAL'}] {nama} {det}")

    print(f"modul episode dimuat: {M.MODUL_EPISODE}")
    print("1) konsistensi BEATS (satu sumber kebenaran)")
    for vis, lst in M.BEATS.items():
        cek(f"visual '{vis}' terdaftar", vis in D.VISUALS)
        cek(f"beat '{vis}' fraksi 0..1 & SFX ada", all(0 < f < 1 and s in SFX.KATALOG for f, s in lst), str(lst))
    for s in list(TRANS_SFX.values()):
        cek(f"SFX transisi '{s}' ada", s in SFX.KATALOG)

    class C:  # konteks palsu
        pass

    def ctx(sc, t, dur=6.0, no=1):
        c = C()
        c.sc, c.t, c.dur, c.lead, c.vo_dur = sc, t, dur, 0.6, dur - 1.5
        c.aksen = D.col(sc.get("accent", "#2F7BFF"))
        c.fakta_no, c.fakta_total = no, 7
        return c

    adegan = [
        {"id": "intro", "type": "intro", "visual": "langit", "accent": "#2F7BFF",
         "lines": ["UDARA ITU BENING", "KENAPA LANGIT BIRU?"]},
        {"id": "f1", "type": "fact", "visual": "spektrum", "accent": "#7B5CFF", "badge": "HAMBURAN RAYLEIGH",
         "title": "BIRU PALING MUDAH DIHAMBURKAN", "hl": "BIRU"},
        {"id": "f2", "type": "fact", "visual": "angka", "accent": "#1FB57A", "badge": "JARAK", "hl": "40 TRILIUN KM",
         "angka": 40, "satuan": "triliun km"},
        {"id": "outro", "type": "outro", "accent": "#FF6B3D", "lines": ["SEKARANG", "KAMU TAHU"], "cta": "IKUTI",
         "foot": "Fakta sains & misteri, tiap hari", "foot2": "Simpan video ini · bagikan ke teman",
         "src": "Sumber: NASA Space Place"},
    ]
    for vis in M.BEATS:
        adegan.append({"id": vis, "type": "fact", "visual": vis, "accent": "#2F7BFF", "badge": "EPISODE",
                       "title": f"VISUAL {vis.upper()}", "hl": "VISUAL"})
    print("2) layout adegan (kinetik, stiker, penanda, zona teks)")
    imgs, labels = [], []
    for sc in adegan:
        t0 = time.time()
        frames = []
        err = []
        for t in (0.25, 0.6, 1.4, 3.0, 5.2):
            D.KOTAK_TEKS.clear()
            im = Image.new("RGB", (1080, 1920), CREAM)
            try:
                gambar_adegan(im, ctx(sc, t))
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                err.append(f"{type(e).__name__}: {e}")
                break
            frames.append(im)
            for (x0, y0, x1, y1, s) in D.KOTAK_TEKS:
                if y1 > 1640 or x0 < 40 or x1 > 1040 or y0 < 175 or (x1 > 950 and y1 > 1100 and y0 < 1700):
                    err.append(f"teks '{s[:16]}' zona terlarang ({x0:.0f},{y0:.0f},{x1:.0f},{y1:.0f})")
        ms = (time.time() - t0) / max(1, len(frames)) * 1000
        if len(frames) == 5:
            a = [np.asarray(f, np.int16) for f in frames]
            if np.abs(a[3] - a[4]).max() < 12:
                err.append("diam > 1 detik")
            imgs += [frames[1], frames[3]]
            labels += [f"{sc['id']} t=0.6", f"{sc['id']} t=3.0"]
        cek(f"{sc['id']:<12} ({ms:.0f} ms/frame)", not err, "; ".join(sorted(set(err))[:3]))
    print("3) events()")
    tl = {"scenes": []}
    st = 0.0
    for sc in adegan:
        tl["scenes"].append({"id": sc["id"], "start": st, "dur": 6.0})
        st += 6.0
    ev = M.events({"scenes": adegan}, tl)
    cek("event terurut & di dalam timeline", all(0 <= e["t"] <= st for e in ev) and
        all(ev[i]["t"] <= ev[i + 1]["t"] for i in range(len(ev) - 1)), f"({len(ev)} event)")
    cek("SFX event dikenal", all(e["sfx"] in SFX.KATALOG for e in ev))
    out = ROOT / "build" / "mesin_v11_selftest.jpg"
    sheet(imgs, labels, cols=6, lebar=220, judul="mesin_v11 selftest", path=out)
    print(f"montase: {out}")
    print("MESIN_V11 SELFTEST:", "LULUS" if ok else "GAGAL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(_uji())
