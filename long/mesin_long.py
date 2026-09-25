#!/usr/bin/env python3
"""long/mesin_long.py - mesin VIDEO PANJANG 16:9 KlikTahu (1920x1080, SS 1.25, 30 fps).

Terpisah dari Shorts tetapi meminjam primitifnya (diagrams, mesin_fx, mesin_v11).
  * align()  : penyelarasan kata dengan PEMROGRAMAN DINAMIS (jeda audio <-> tanda baca), lalu waktu kata di
               antara jangkar dibagi sebanding panjang kata. Beat visual & SFX dikunci ke KATA.
  * Ctx      : C.w("kata", n, off) waktu kata ke-n dalam bab (KeyError bila tidak ada), C.tt(x, d) progres
               animasi sejak x, C.u progres bab 0..1, C.win(a, b) progres di antara a dan b.
  * Komponen : latar (gradasi + nebula + bintang paralaks, atau latar(img,t,C) khusus), teks berbayang lembut,
               panel kaca cair, judul kinetik v2, stiker, stempel, chip, callout bergaris, penghitung angka
               format Indonesia (odometer), kartu bab (latar blur + angka outline), HUD (brand, chip bab,
               bilah progres bersegmen), bokeh.
  * Kamera   : napas halus + dorong pada beat berat + zoom pelan per bab. Transisi bab bergilir:
               zoomthru, tinta, whip, iris. Finishing preset 'sinema'.
Selftest: python3 long/mesin_long.py --uji
"""
from __future__ import annotations

import importlib.util
import json
import math
import re
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import diagrams as D  # noqa: E402
import mesin_fx as FX  # noqa: E402
import mesin_util as mu  # noqa: E402
import mesin_v11 as V  # noqa: E402

W0, H0 = 1920, 1080
MALAM = (9, 11, 24)
MALAM2 = (22, 26, 58)
PUTIH, INK = D.PUTIH, D.INK
TRANS_BAB = ["zoomthru", "tinta", "whip", "iris"]
T_OUT, T_IN = 0.30, 0.40
KARTU_DUR = 1.9  # kartu bab tampil di awal tiap bab (VO mulai di lead_in)


# ============================================================================ penyelarasan kata (DP)
def norm(k):
    return re.sub(r"[^0-9a-z]", "", k.lower().replace("é", "e"))


def _bobot_tanda(tok):
    if re.search(r"[.?!]['\")]*$", tok):
        return 3.0
    if re.search(r"[,;:]['\")]*$", tok) or tok.endswith("-"):
        return 2.0
    return 0.35


def align(x, teks, sr=48000, offset=0.0, min_jeda=0.10):
    """-> [{kata, norm, t0, t1}] (detik; + offset). x = klip VO hasil process_audio."""
    toks = [t for t in teks.split() if norm(t)]
    if not toks:
        return []
    fr = 0.01
    env = mu.env_db(x, sr, fr)
    aktif_lv = env[env > -80]
    thr = max(-46.0, (np.percentile(aktif_lv, 90) if len(aktif_lv) else -30) - 26.0)
    akt = env > thr
    idx = np.nonzero(akt)[0]
    if len(idx) == 0:
        return []
    s0, s1 = int(idx[0]), int(idx[-1]) + 1
    jeda = []
    i = s0
    while i < s1:
        if not akt[i]:
            j = i
            while j < s1 and not akt[j]:
                j += 1
            if (j - i) * fr >= min_jeda:
                jeda.append((i, j))
            i = j
        else:
            i += 1
    cw = np.array([len(norm(t)) + 2.0 for t in toks])
    m = len(toks)
    total_jeda = sum(b - a for a, b in jeda)
    bicara = max(1.0, (s1 - s0) - total_jeda)
    cum = np.cumsum(cw) / cw.sum()
    exp_b = cum[:-1] * bicara  # waktu-bicara harapan batas setelah kata j
    pw = np.array([_bobot_tanda(t) for t in toks[:-1]])
    st = []
    sblm = 0
    for a, b in jeda:
        st.append((a - s0) - sblm)
        sblm += b - a
    k, nb = len(jeda), m - 1
    NEG = -1e9
    M = np.full((k + 1, nb + 1), NEG)
    M[0, :] = 0.0
    bt = np.zeros((k + 1, nb + 1), np.int8)
    for ii in range(1, k + 1):
        M[ii, 0] = M[ii - 1, 0] - 0.4
        bt[ii, 0] = 1
        dlen = (jeda[ii - 1][1] - jeda[ii - 1][0]) * fr
        for jj in range(1, nb + 1):
            skor = pw[jj - 1] * min(1.0, dlen / 0.30) - 6.0 * abs(exp_b[jj - 1] - st[ii - 1]) / bicara
            pilihan = (M[ii - 1, jj] - 0.4, M[ii, jj - 1], M[ii - 1, jj - 1] + skor)
            c = int(np.argmax(pilihan))
            M[ii, jj] = pilihan[c]
            bt[ii, jj] = c + 1
    pasang = []
    ii, jj = k, nb
    while ii > 0 and jj > 0:
        c = bt[ii, jj]
        if c == 3:
            pasang.append((ii - 1, jj - 1))
            ii, jj = ii - 1, jj - 1
        elif c == 1:
            ii -= 1
        else:
            jj -= 1
    pasang.reverse()
    # jangkar: (indeks_kata_awal, waktu_awal) ... segmen kata dibagi sebanding cw
    jangkar = [(0, s0 * fr)]
    akhir = []
    for pi, bj in pasang:
        a, b = jeda[pi]
        akhir.append((bj, a * fr))
        jangkar.append((bj + 1, b * fr))
    akhir.append((m - 1, s1 * fr))
    out = [None] * m
    for (w0, ta), (w1, tb) in zip(jangkar, akhir):
        ws = list(range(w0, w1 + 1))
        if not ws:
            continue
        tot = sum(cw[w] for w in ws)
        t = ta
        for w in ws:
            d = (tb - ta) * cw[w] / tot
            out[w] = {"kata": toks[w], "norm": norm(toks[w]), "t0": round(t + offset, 3), "t1": round(t + d + offset, 3)}
            t += d
    return [o for o in out if o]


class Ctx:
    """konteks bab: waktu kata, progres, util animasi."""

    def __init__(self, k, t, scene, ts, words, content, fps=30, fi=0):
        self.k, self.t, self.sc, self.ts = k, t, scene, ts
        self.dur = ts["dur"]
        self.u = D.clamp(t / self.dur)
        self.words = words
        self.content = content
        self.fps, self.fi = fps, fi
        self.aksen = D.col(scene.get("accent", "#2F7BFF"))
        self.lead = ts.get("lead_in", 0.8)

    def w(self, kata, n=1, off=0.0):
        nk = norm(kata)
        hit = [x for x in self.words if x["norm"] == nk]
        if len(hit) < n:
            raise KeyError(f"kata '{kata}' ke-{n} tidak ada di {self.sc['id']} (ada {len(hit)})")
        return hit[n - 1]["t0"] + off

    def T(self, x):
        return float(x) if isinstance(x, (int, float)) else self.w(*x) if isinstance(x, tuple) else self.w(x)

    def tt(self, x, d=0.5):
        return D.clamp((self.t - self.T(x)) / d)

    def win(self, a, b):
        ta, tb = self.T(a), self.T(b)
        return D.clamp((self.t - ta) / max(1e-3, tb - ta))

    def sudah(self, x):
        return self.t >= self.T(x)


# ============================================================================ komponen
@lru_cache(maxsize=512)
def _bayang_teks(s, w, px, blur):
    m, adv, asc, padl = D._txt_mask(s, w, px)
    pad = int(blur * 2.5) + 2
    big = Image.new("L", (m.size[0] + 2 * pad, m.size[1] + 2 * pad), 0)
    big.paste(m, (pad, pad))
    return big.filter(ImageFilter.GaussianBlur(float(blur))), pad


def teks(img, s, x, y, size, w="B", warna=PUTIH, a=1.0, anchor="ls", bayang=0.55, catat=True):
    """teks dengan bayangan lembut (terbaca di latar apa pun)."""
    if not s or a <= 0.01:
        return None
    if bayang > 0:
        px = D.fpx(size)
        m, adv, asc, padl = D._txt_mask(s, w, px)
        sh, pad = _bayang_teks(s, w, px, max(2, int(px * 0.08)))
        wd = adv / D.SS
        ch = D.cap_h(size, w)
        ha, va = anchor[0], anchor[1]
        xl = x - (wd / 2 if ha == "m" else wd if ha == "r" else 0)
        base = y + (ch / 2 if va == "m" else ch if va == "t" else 0)
        D.tempel(img, INK, round(D.S(xl) - padl - pad + px * 0.03), round(D.S(base) - asc - pad + px * 0.06), sh,
                 bayang * a)
    return D.txt(img, s, x, y, size, w, warna, a, anchor, catat)


def panel_kaca(img, x0, y0, x1, y1, t, r=40, a=1.0, gelap=True):
    FX.kaca_cair(img, x0, y0, x1, y1, r, t, (40, 48, 86) if gelap else (255, 255, 255), a, kabur=14.0)


def stempel(img, s, cx, cy, t, t0, warna="#F0454A", size=54, rot=-8):
    """stempel karet: menghantam (skala 1.7 -> 1) + garis ganda, sedikit miring."""
    tw = t - t0
    if tw <= 0:
        return
    sk = 1 + 0.7 * (1 - D.eo(min(1, tw / 0.18)))
    a = D.clamp(tw / 0.08)
    tw_ = D.txt_w(s, size)
    lay = Image.new("L", (int(D.S(tw_ + size * 1.6)) + 8, int(D.S(size * 2.1)) + 8), 0)
    old = D.SS
    img_l = Image.new("RGB", lay.size, (0, 0, 0))
    D.rrect_garis(img_l, 4 / old, 4 / old, (lay.size[0] - 4) / old, (lay.size[1] - 4) / old, size * 0.3, PUTIH,
                  size * 0.09)
    D.rrect_garis(img_l, 4 / old + size * 0.16, 4 / old + size * 0.16, (lay.size[0] - 4) / old - size * 0.16,
                  (lay.size[1] - 4) / old - size * 0.16, size * 0.2, PUTIH, size * 0.04)
    D.txt(img_l, s, lay.size[0] / 2 / old, lay.size[1] / 2 / old, size, "B", PUTIH, 1, "mm", catat=False)
    m = img_l.convert("L")
    m = m.resize((max(2, int(m.size[0] * sk)), max(2, int(m.size[1] * sk))), Image.BICUBIC).rotate(rot, Image.BICUBIC,
                                                                                                    expand=True)
    D.tempel(img, warna, round(D.S(cx) - m.size[0] / 2), round(D.S(cy) - m.size[1] / 2), m, 0.92 * a)
    if tw > 0.1:
        D.KOTAK_TEKS.append((cx - tw_ / 2, cy - size * 0.6, cx + tw_ / 2, cy + size * 0.6, s))


def callout(img, tx, ty, lx, ly, s, t, t0, warna, size=34, kiri=True):
    """titik target -> garis siku menggambar diri -> label pil."""
    u = D.eo(D.seg(t, t0, t0 + 0.5))
    if u <= 0:
        return
    D.circ(img, tx, ty, 10 * min(1, u * 3), warna)
    D.ring(img, tx, ty, 18 + 6 * math.sin(t * 4), 3, warna, 0.6 * u)
    siku = (lx, ty) if abs(ly - ty) < 1 else (tx + (lx - tx) * 0.35, ly)
    pts = D.potong_jalur([(tx, ty), siku, (lx, ly)], u)
    if len(pts) > 1:
        D.polyline(img, pts, 3.5, warna, 0.95)
    a = D.seg(t, t0 + 0.35, t0 + 0.6)
    if a > 0:
        wv = D.txt_w(s, size, "SB") + size * 1.1
        x0 = lx if kiri else lx - wv
        D.rrect(img, x0, ly - size * 0.85, x0 + wv, ly + size * 0.85, size * 0.85, (20, 24, 46), 0.9 * a)
        D.rrect_garis(img, x0, ly - size * 0.85, x0 + wv, ly + size * 0.85, size * 0.85, warna, 2.5, a)
        D.txt(img, s, x0 + wv / 2, ly, size, "SB", PUTIH, a, "mm")


def penghitung(img, nilai, x, y, size, C, mulai, dur=1.6, satuan="", desimal=0, warna=PUTIH, anchor="m"):
    u = C.tt(mulai, dur)
    if C.t < C.T(mulai) - 0.05:
        return
    FX.odometer(img, nilai, x, y, size, warna, D.clamp(C.tt(mulai, 0.25)), anchor, "B", u, desimal, satuan)


@lru_cache(maxsize=16)
def _bintang_lapis(seed, n, lapis):
    rr = D.rng("bintang_long", seed, lapis)
    return rr.uniform(0, 1, (n, 2)), rr.uniform(0.6, 1.0, n), rr.uniform(0, 6.28, n)


def latar_default(size, t, C=None, aksen=(47, 123, 255)):
    """latar antariksa: gradasi + nebula (res rendah) + bintang paralaks 3 lapis (tanpa acak waktu)."""
    W, H = size
    lw, lh = 64, 36
    ys, xs = np.mgrid[0:lh, 0:lw].astype(np.float32)
    xs /= lw
    ys /= lh
    base = np.array(MALAM, np.float32) * (1 - ys[..., None]) + np.array(MALAM2, np.float32) * ys[..., None]
    ak = np.array(D.col(aksen), np.float32)
    for k in range(3):
        cx = 0.5 + 0.45 * FX.nois(t * 0.03 + k * 4.1, 70 + k)
        cy = 0.5 + 0.4 * FX.nois(t * 0.025 + k * 2.3, 80 + k)
        g = np.exp(-(((xs - cx) / 0.35) ** 2 + ((ys - cy) / 0.28) ** 2))[..., None]
        warna = ak if k == 0 else np.array(D.campur(aksen, "#FF5FA2", 0.5 + 0.2 * k), np.float32)
        base = base * (1 - 0.22 * g) + warna * 0.22 * g
    im = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB").resize((W // 8, H // 8), Image.BICUBIC)
    im = im.resize((W, H), Image.BILINEAR)
    for lapis, (n, kec, r) in enumerate(((140, 4, 1.4), (70, 10, 2.0), (26, 22, 2.8))):
        pos, br, ph = _bintang_lapis("kt", n, lapis)
        for i in range(n):
            x = (pos[i, 0] * (W0 + 200) - t * kec) % (W0 + 200) - 100
            y = pos[i, 1] * H0
            a = br[i] * (0.55 + 0.45 * math.sin(t * 1.5 + ph[i]))
            if lapis == 2:
                D.glow(im, x, y, r * 6, PUTIH, 0.18 * a)
            D.circ(im, x, y, r, PUTIH, a)
    return im


def kartu_bab(img, nomor, judul, u, aksen, t):
    """kartu bab: latar diburamkan + angka outline besar + judul + garis sapu. u = 0..1..0 (masuk/keluar)."""
    if u <= 0.01:
        return img
    W, H = img.size
    kab = img.resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(6.0)).resize((W, H), Image.BILINEAR)
    gel = Image.blend(kab, Image.new("RGB", (W, H), MALAM), 0.35)
    img = Image.blend(img, gel, D.eio(u))
    s = f"{nomor:02d}"
    px = D.fpx(300)
    m, adv, asc, padl = D._txt_mask(s, "B", px)
    tebal = max(3, int(px * 0.025))
    luar = m.filter(ImageFilter.MaxFilter(2 * tebal + 1))
    outline = ImageChops.subtract(luar, m)
    x = D.S(W0 / 2) - adv / 2 - padl
    y = D.S(H0 / 2 - 60 + (1 - D.eo(u)) * 60) - asc + D.S(D.cap_h(300)) / 2
    D.tempel(img, aksen, round(x), round(y), outline, D.eio(u))
    D.tempel(img, aksen, round(x), round(y), m, 0.12 * D.eio(u))
    teks(img, f"BAB {nomor}", W0 / 2, H0 / 2 + 170, 40, "SB", D.terang(aksen, 0.4), D.eio(u), "ms", catat=False)
    teks(img, judul.upper(), W0 / 2, H0 / 2 + 250, 64, "B", PUTIH, D.eio(u), "ms", catat=False)
    lw = D.txt_w(judul.upper(), 64) * D.eo(u)
    D.rrect(img, W0 / 2 - lw / 2, H0 / 2 + 280, W0 / 2 + lw / 2, H0 / 2 + 288, 4, aksen, D.eio(u))
    return img


def hud(img, T, C, timeline, content):
    """HUD Long: brand kiri atas, chip bab kanan atas, bilah progres bersegmen per bab (atas)."""
    ac = C.aksen
    # semua elemen HUD di dalam margin 40 px (x 48..1872)
    D.rrect(img, 48, 36, 48 + 60 + D.txt_w("KlikTahu", 30), 80, 22, (14, 16, 32), 0.72)
    D.circ(img, 72, 58, 13, ac)
    D.circ(img, 72, 58, 5, PUTIH)
    D.txt(img, "Klik", 94, 58, 30, "B", PUTIH, 1, "lm", catat=False)
    D.txt(img, "Tahu", 94 + D.txt_w("Klik", 30), 58, 30, "B", ac, 1, "lm", catat=False)
    lab = f"BAB {C.k + 1} · {C.sc.get('judul', '')}".upper()
    wl = D.txt_w(lab, 24, "SB") + 40
    D.rrect(img, 1872 - wl, 38, 1872, 78, 20, (14, 16, 32), 0.72)
    D.txt(img, lab, 1872 - wl / 2, 58, 24, "SB", PUTIH, 1, "mm", catat=False)
    scs = timeline["scenes"]
    x0, x1, y, h, gap = 48, 1872, 16, 6, 6  # bilah progres di atas (tepi atas memang area HUD)
    lebar = (x1 - x0 - gap * (len(scs) - 1)) / len(scs)
    for i, s in enumerate(scs):
        xa = x0 + i * (lebar + gap)
        D.rrect(img, xa, y, xa + lebar, y + h, 3, (60, 64, 90), 0.8)
        f = D.clamp((T - s["start"]) / s["dur"])
        if f > 0:
            D.rrect(img, xa, y, xa + max(h, lebar * f), y + h, 3, ac if i == C.k else PUTIH, 0.95)


def muat_visual(slug_dir):
    p = Path(slug_dir) / "visual.py"
    spec = importlib.util.spec_from_file_location(f"visual_{Path(slug_dir).name}", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def events_long(content, timeline, words, beats):
    """SFX Long: transisi bab + kartu bab + BEATS terkunci ke KATA: (bab_id, kata, n, sfx[, off[, gain]])."""
    ev = []
    ids = {s["id"]: i for i, s in enumerate(content["scenes"])}
    for k, ts in enumerate(timeline["scenes"]):
        st = ts["start"]
        if k > 0:
            j = TRANS_BAB[(k - 1) % len(TRANS_BAB)]
            ev.append({"t": st - 0.12, "sfx": V.TRANS_SFX.get(j, "whoosh"), "scene": ts["id"], "sumber": f"transisi:{j}"})
        ev.append({"t": st + 0.15, "sfx": "kertas", "scene": ts["id"], "sumber": "kartu_bab", "gain_db": -2.0})
        ev.append({"t": st + 0.32, "sfx": "pukul", "scene": ts["id"], "sumber": "kartu_bab", "gain_db": -6.0})
    for b in beats:
        bab, kata, n, s = b[0], b[1], b[2], b[3]
        off = b[4] if len(b) > 4 else 0.0
        gain = b[5] if len(b) > 5 else 0.0
        k = ids[bab]
        ts = timeline["scenes"][k]
        C = Ctx(k, 0, content["scenes"][k], ts, words[bab], content)
        ev.append({"t": ts["start"] + C.w(kata, n, off), "sfx": s, "scene": bab, "sumber": f"kata:{kata}",
                   "gain_db": gain, "berat": s in V.BERAT})
    for e in ev:
        e.setdefault("berat", e["sfx"] in V.BERAT)
        e.setdefault("gain_db", 0.0)
        e["t"] = round(max(0.0, e["t"]), 4)
    return sorted(ev, key=lambda e: e["t"])


# ============================================================================ selftest
def _uji():
    ok = True

    def cek(nama, kond, det=""):
        nonlocal ok
        ok &= bool(kond)
        print(f"  [{'OK' if kond else 'GAGAL'}] {nama} {det}")

    print("1) align (DP jeda <-> tanda baca) pada ucapan sintetis dengan waktu kata diketahui")
    sr = 48000
    rr = np.random.default_rng(3)
    teks_ = "Bintang terdekat bernama Proxima. Jaraknya sekitar empat tahun cahaya, sangat jauh sekali."
    toks = teks_.split()
    parts, benar, t = [np.zeros(int(0.1 * sr), np.float32)], [], 0.1
    for tok in toks:
        n = int((0.12 + 0.045 * len(norm(tok))) * sr)
        tt = np.arange(n) / sr
        f0 = rr.uniform(110, 140)
        v = sum(np.sin(2 * np.pi * f0 * h * tt) / h for h in range(1, 10)) * np.clip(np.sin(np.pi * tt / tt[-1]), 0, None) ** 0.6
        benar.append(t)
        parts.append((0.3 * v).astype(np.float32))
        t += n / sr
        gap = 0.45 if tok.endswith(".") else 0.30 if tok.endswith(",") else 0.03
        parts.append(np.zeros(int(gap * sr), np.float32))
        t += int(gap * sr) / sr
    x = np.concatenate(parts)
    hasil = align(x, teks_, sr)
    err = [abs(h["t0"] - b) for h, b in zip(hasil, benar)]
    cek("semua kata ter-align", len(hasil) == len(toks), f"({len(hasil)}/{len(toks)})")
    cek("galat rata-rata < 0.12 s", np.mean(err) < 0.12, f"({np.mean(err):.3f} s, maks {np.max(err):.3f} s)")
    sesudah_titik = [i + 1 for i, tk in enumerate(toks[:-1]) if tk.endswith((".", ","))]
    cek("kata setelah tanda baca tepat (< 0.06 s)", all(err[i] < 0.06 for i in sesudah_titik),
        str([round(err[i], 3) for i in sesudah_titik]))
    print("2) Ctx API")
    C = Ctx(0, 1.0, {"id": "bab1"}, {"dur": 10.0}, hasil, {})
    cek("C.w('proxima') ada", abs(C.w("Proxima") - hasil[3]["t0"]) < 1e-6)
    try:
        C.w("tidakada")
        cek("C.w kata tidak ada -> KeyError", False)
    except KeyError:
        cek("C.w kata tidak ada -> KeyError", True)
    cek("C.u / C.tt / C.win", abs(C.u - 0.1) < 1e-9 and 0 <= C.tt("bintang", 0.5) <= 1 and 0 <= C.win(0.5, 2.0) <= 1)
    print("MESIN_LONG SELFTEST:", "LULUS" if ok else "GAGAL")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--uji" in sys.argv:
        raise SystemExit(_uji())
    print(__doc__)
