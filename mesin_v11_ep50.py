#!/usr/bin/env python3
"""mesin_v11_ep50.py - adegan Ep50 "Kenapa Kamu Cegukan?" (fungsi sc_*50 + tabel beat).
Area konten fact: y 480..1560, x 40..1040 (x < 950 untuk y > 1100). Semua koordinat desain 1080x1920.
"""
import math

import diagrams as D
import render as R
from diagrams import register
from mesin_v11 import beat, chip, daftar_beats, label, pulse_ring, sticker
from render import CREAM, INK, MUTED, WHITE, clamp, eio, eo, eob, mix, seg

# ------------------------------------------------------------------ tabel beat (fraksi durasi adegan, sfx)
daftar_beats("intro_cegukan", {"muncul": (0.02, None), "hik1": (0.30, "hik"), "hik2": (0.52, "hik"),
                               "hik3": (0.71, "hik"), "sinyal": (0.84, "sinyal")})
daftar_beats("diafragma50", {"muncul": (0.05, "whoosh"), "hirup": (0.28, "napas"), "hembus": (0.46, "napas"),
                             "kedut": (0.70, "hik"), "kedut2": (0.86, "hik")})
daftar_beats("pitasuara50", {"muncul": (0.05, "whoosh"), "kedut": (0.22, "denyut"), "tutup": (0.36, "hik"),
                             "gelombang": (0.40, "pop"), "ulang": (0.72, "hik")})
daftar_beats("refleks50", {"muncul": (0.05, "whoosh"), "naik": (0.24, "sinyal"), "otak": (0.42, "zap"),
                           "turun": (0.52, "sinyal"), "kedut": (0.66, "hik"), "nyala": (0.84, "glitch")})
daftar_beats("pemicu50", {"k1": (0.10, "pop"), "k2": (0.22, "pop"), "k3": (0.36, "pop"), "k4": (0.50, "pop"),
                          "k5": (0.62, "pop"), "saraf": (0.80, "sinyal")})
daftar_beats("janin50", {"muncul": (0.05, "whoosh"), "angka": (0.12, "tick"), "denyut": (0.28, "denyut"),
                         "otak": (0.42, "kilau"), "amfibi": (0.66, "gelembung"), "insang": (0.78, "gelembung")})
daftar_beats("rekor50", {"muncul": (0.05, "whoosh"), "cek1": (0.16, "ding"), "cek2": (0.30, "ding"),
                         "putus": (0.46, "zap"), "rekor": (0.66, "impact"), "angka": (0.70, "riser")})
daftar_beats("rangkuman50", {"s1": (0.06, "pop"), "s2": (0.20, "pop"), "s3": (0.34, "pop"),
                             "jam": (0.62, "thud"), "dokter": (0.80, "ding")})
daftar_beats("outro_default", {"hik": (0.35, "hik")})


def _acc(sc):
    return R.hex2rgb(sc.get("accent", "#E4572E"))


def _b(sc, name, dur):
    """waktu absolut (detik) beat bernama."""
    return beat(sc.get("visual", ""), name) * dur


def _spasm(t, tb, strength=1.0):
    """amplitudo kedutan: lonjakan cepat lalu meluruh 0.45 s."""
    d = t - tb
    if d < 0 or d > 0.5:
        return 0.0
    return strength * math.exp(-d * 7) * (1 if d > 0.02 else d / 0.02)


# ------------------------------------------------------------------ intro

@register("intro_cegukan")
def sc_intro50(img, t, dur, sc):
    acc = _acc(sc)
    u = eo(seg(t, _b(sc, "muncul", dur), _b(sc, "muncul", dur) + 0.7))
    cx, cy = 540, 1210
    spasm = sum(_spasm(t, _b(sc, k, dur)) for k in ("hik1", "hik2", "hik3"))
    breathe = 0.5 + 0.5 * math.sin(t * 1.6)
    R.glow(img, (cx, cy), 420, acc, 0.18 * u)
    D.lungs(img, (cx, cy - 80 + 40 * (1 - u)), 520 * u, expand=breathe - 0.6 * spasm, color=mix(acc, WHITE, 0.55), alpha=u)
    D.dome(img, (cx, cy + 150), 640 * u, sag=breathe * 0.7 - 0.5 * spasm, color=acc, alpha=u, spasm=spasm)
    for k in ("hik1", "hik2", "hik3"):
        tb = _b(sc, k, dur)
        pos = {"hik1": (300, 1000), "hik2": (800, 1090), "hik3": (330, 1470)}[k]
        sticker(img, t, tb, pos, "HIK!", acc, 52, rot=-12 if k != "hik2" else 9, life=1.6)
        D.burst(img, pos, seg(t, tb, tb + 0.5), acc, 10, 110, 9)
    ts = _b(sc, "sinyal", dur)
    if t > ts:
        k = eo(seg(t, ts, ts + 0.6))
        pts = R.bezier((cx, 700), (860, 780), (900, 1100), (cx + 150, 1330), 40, k)
        if len(pts) > 1:
            R.line(img, pts, INK, 6, 0.9)
            R.circ(img, pts[-1], 14, fill=acc, outline=WHITE, width=4)
        label(img, (700, 690), "SINYAL SALAH", 26, INK, "lm", "SemiBold", k, bg=WHITE)


# ------------------------------------------------------------------ f1 diafragma

@register("diafragma50")
def sc_diafragma50(img, t, dur, sc):
    acc = _acc(sc)
    t0 = _b(sc, "muncul", dur)
    u = eo(seg(t, t0, t0 + 0.7))
    cx, cy = 520, 1000
    th, tb = _b(sc, "hirup", dur), _b(sc, "hembus", dur)
    # siklus napas: sebelum hirup -> netral; hirup -> sag 1, hembus -> sag 0; lalu napas pelan
    if t < th:
        sag, exp_ = 0.35, 0.3
    elif t < tb:
        k = eio(seg(t, th, th + 1.6))
        sag, exp_ = 0.35 + 0.65 * k, 0.3 + 0.7 * k
    else:
        k = eio(seg(t, tb, tb + 1.6))
        base = 1 - k
        sag = 0.35 + 0.65 * base + 0.25 * k * (0.5 + 0.5 * math.sin((t - tb) * 1.8))
        exp_ = 0.3 + 0.7 * base + 0.3 * k * (0.5 + 0.5 * math.sin((t - tb) * 1.8))
    spasm = _spasm(t, _b(sc, "kedut", dur)) + _spasm(t, _b(sc, "kedut2", dur))
    R.glow(img, (cx, cy + 60), 460, acc, 0.16 * u)
    # rongga dada (panel kaca lembut)
    R.rrect(img, (cx - 380, cy - 440, cx + 380, cy + 420), 120, fill=WHITE, alpha=0.35 * u)
    R.rrect(img, (cx - 380, cy - 440, cx + 380, cy + 420), 120, outline=mix(acc, CREAM, 0.4), width=3, alpha=u)
    D.lungs(img, (cx, cy - 120), 500 * u, expand=exp_ - 0.5 * spasm, color=mix(acc, WHITE, 0.55), alpha=u)
    D.dome(img, (cx, cy + 250), 620 * u, sag=sag - 0.6 * spasm, color=acc, alpha=u, spasm=spasm)
    # panah arah gerak diafragma
    if th <= t < tb + 1.2:
        down = t < tb
        k = eio(seg(t, th, th + 0.6)) if down else eio(seg(t, tb, tb + 0.6))
        ay0, ay1 = (cy + 150, cy + 330) if down else (cy + 330, cy + 150)
        for sx in (-250, 250):
            R.arrow(img, [(cx + sx, ay0), (cx + sx, ay0 + (ay1 - ay0) * k)], INK, 7, 20, 0.9)
        label(img, (cx, cy + 400), "TURUN = TARIK NAPAS" if down else "NAIK = HEMBUS", 26, INK, "mm", "SemiBold", k, bg=WHITE)
    lb = eo(seg(t, t0 + 0.6, t0 + 1.0))
    label(img, (cx - 250, cy - 400), "PARU-PARU", 28, INK, "lm", "SemiBold", lb, bg=WHITE)
    label(img, (cx + 60, cy + 300), "DIAFRAGMA", 28, WHITE, "lm", "Bold", lb, bg=acc)
    tk = _b(sc, "kedut", dur)
    sticker(img, t, tk, (300, 1430), "KEDUT!", acc, 50, rot=-10)
    D.burst(img, (300, 1430), seg(t, tk, tk + 0.5), acc, 12, 130, 10)
    sticker(img, t, _b(sc, "kedut2", dur), (690, 1300), "TANPA PERINTAH", INK, 30, rot=6)


# ------------------------------------------------------------------ f2 pita suara

@register("pitasuara50")
def sc_pitasuara50(img, t, dur, sc):
    acc = _acc(sc)
    t0 = _b(sc, "muncul", dur)
    u = eo(seg(t, t0, t0 + 0.7))
    cx, cy = 520, 980
    tk, tt, tu = _b(sc, "kedut", dur), _b(sc, "tutup", dur), _b(sc, "ulang", dur)
    # lingkaran tenggorokan (pandangan dari atas)
    R.glow(img, (cx, cy), 400, acc, 0.15 * u)
    R.circ(img, (cx, cy), 330 * u, fill=mix(acc, WHITE, 0.8), outline=INK, width=6)
    R.circ(img, (cx, cy), 285 * u, fill=mix(acc, WHITE, 0.62), outline=mix(acc, INK, 0.3), width=3)
    # bukaan glotis: 1 = terbuka, 0 = tertutup
    def opening(tc):
        d = t - tc
        if d < 0:
            return 1.0
        if d < 0.06:
            return 1 - d / 0.06
        if d < 1.4:
            return 0.0
        return eo(seg(d, 1.4, 2.2))
    op = min(opening(tt), opening(tu))
    if t < tk:
        op = 0.55 + 0.25 * math.sin(t * 2.5)
    gap = 120 * op
    # lipatan pita suara = cakram daging; celah glotis = bentuk lensa gelap yang membuka/menutup
    R.circ(img, (cx, cy), 250 * u, fill=mix(acc, WHITE, 0.3), outline=INK, width=4)
    left = R.bezier((cx, cy - 235), (cx - gap * 1.4, cy - 120), (cx - gap * 1.4, cy + 120), (cx, cy + 235), 30)
    right = R.bezier((cx, cy + 235), (cx + gap * 1.4, cy + 120), (cx + gap * 1.4, cy - 120), (cx, cy - 235), 30)
    lens = left + right
    if op > 0.02:
        R.poly(img, lens, fill=(40, 30, 50), alpha=u)
    R.line(img, lens + [lens[0]], INK, 7, u)
    # garis tepi lipatan (tekstur)
    for sgn in (-1, 1):
        R.ring(img, (cx + sgn * 40, cy), 200, mix(acc, INK, 0.3), 3, 250 if sgn < 0 else 70, 290 if sgn < 0 else 110, 0.5 * u)
    # aliran udara: partikel naik lewat celah (berhenti saat tertutup)
    if op > 0.05:
        for i in range(10):
            p = (t * 0.9 + i * 0.1) % 1.0
            px = cx + (i % 5 - 2) * gap * 0.35
            py = cy + 300 - p * 600
            R.circ(img, (px, py), 7, fill=INK, alpha=0.5 * op * u)
    lb = eo(seg(t, t0 + 0.6, t0 + 1.0))
    label(img, (cx, cy - 360), "PITA SUARA (dari atas)", 26, INK, "mm", "SemiBold", lb, bg=WHITE)
    # penghitung 35 ms
    if t >= tk:
        k = seg(t, tk, tt)
        ms = int(35 * k)
        R.rrect(img, (80, 1380, 500, 1500), 30, fill=INK)
        R.text(img, (290, 1440), "%d ms" % ms, 56, "Bold", WHITE, "mm", track=True)
        label(img, (290, 1540), "kedut -> pita menutup", 24, MUTED, "mm", "Medium", 1.0)
    # penutupan: gelombang bunyi HIK
    for tc in (tt, tu):
        d = t - tc
        if 0 <= d < 1.2:
            k = d / 1.2
            for j in range(3):
                R.ring(img, (cx, cy), 60 + (j * 90 + 300 * k), acc, 10, 0, 360, (1 - k) * (0.9 - j * 0.25))
        sticker(img, t, tc, (800, 700), "HIK!", acc, 56, rot=10, life=1.3)
    tg = _b(sc, "gelombang", dur)
    label(img, (760, 1440), "udara terhenti", 26, INK, "mm", "SemiBold", eo(seg(t, tg, tg + 0.4)), bg=WHITE)


# ------------------------------------------------------------------ f3 busur refleks

@register("refleks50")
def sc_refleks50(img, t, dur, sc):
    acc = _acc(sc)
    t0 = _b(sc, "muncul", dur)
    u = eo(seg(t, t0, t0 + 0.7))
    bx, by = 520, 640          # batang otak
    dx, dy = 520, 1330         # diafragma
    sx, sy = 780, 1130         # lambung
    tn, to_, td, tk, ty = [_b(sc, k, dur) for k in ("naik", "otak", "turun", "kedut", "nyala")]
    nyala = t >= ty
    flick = 0.5 + 0.5 * math.sin(t * 18) if nyala else 0.0
    R.glow(img, (bx, by), 300, acc, (0.2 + 0.4 * flick) * u)
    # jalur saraf: frenikus (kiri, ke diafragma) & vagus (kanan, lewat lambung)
    fren = R.bezier((bx - 40, by + 120), (bx - 260, by + 300), (bx - 260, dy - 200), (dx - 200, dy - 30), 50)
    vag = R.bezier((bx + 40, by + 120), (bx + 300, by + 300), (sx + 60, sy - 200), (sx, sy - 60), 50)
    vag2 = R.bezier((sx - 60, sy + 40), (sx - 200, sy + 120), (dx + 150, dy - 120), (dx + 60, dy - 30), 30)
    dr = eo(seg(t, t0 + 0.3, t0 + 1.3))
    for path, col in ((fren, mix(acc, INK, 0.2)), (vag, acc), (vag2, acc)):
        n = max(2, int(len(path) * dr))
        R.line(img, path[:n], col, 10, u)
        R.line(img, path[:n], WHITE, 3, 0.6 * u)
    D.brain_stem(img, (bx, by), 240 * u, glowk=flick, color=acc, alpha=u)
    D.stomach(img, (sx, sy), 220 * u, full=0.55, color=mix(acc, WHITE, 0.2), alpha=u)
    spasm = _spasm(t, tk) + (0.5 * flick if nyala else 0)
    D.dome(img, (dx, dy), 560 * u, sag=0.4, color=(46, 134, 171), alpha=u, spasm=spasm)
    lb = eo(seg(t, t0 + 0.8, t0 + 1.2))
    label(img, (bx, by - 170), "BATANG OTAK", 26, INK, "mm", "SemiBold", lb, bg=WHITE)
    label(img, (150, 900), "SARAF FRENIKUS", 24, INK, "lm", "SemiBold", lb, bg=WHITE)
    label(img, (sx, sy + 150), "SARAF VAGUS", 24, WHITE, "mm", "Bold", lb, bg=acc)
    label(img, (dx, dy + 80), "DIAFRAGMA", 26, INK, "mm", "SemiBold", lb, bg=WHITE)
    # sinyal berjalan: naik lewat vagus (lambung -> otak), turun lewat frenikus (otak -> diafragma)
    def dot(path, k, rev=False):
        i = int(clamp(k) * (len(path) - 1))
        p = path[len(path) - 1 - i] if rev else path[i]
        R.glow(img, p, 60, acc, 0.9)
        R.circ(img, p, 16, fill=WHITE, outline=acc, width=5)
    if tn <= t < to_:
        dot(vag, seg(t, tn, to_), rev=True)
    if td <= t < tk:
        dot(fren, seg(t, td, tk))
    if nyala:
        # sinyal berulang otomatis (loop cepat)
        k = ((t - ty) * 0.9) % 1.0
        dot(vag, k, rev=True)
        dot(fren, (k + 0.5) % 1.0)
    sticker(img, t, to_, (800, 560), "SINYAL!", acc, 44, rot=8, life=1.5)
    sticker(img, t, tk, (250, 1480), "KEDUT", acc, 46, rot=-8)
    sticker(img, t, ty, (720, 1470), "MENYALA SENDIRI", INK, 28, rot=5)


# ------------------------------------------------------------------ f4 pemicu

@register("pemicu50")
def sc_pemicu50(img, t, dur, sc):
    acc = _acc(sc)
    cards = [("k1", "MAKAN CEPAT", (280, 700)), ("k2", "SODA", (760, 700)), ("k3", "LAMBUNG PENUH", (280, 1060)),
             ("k4", "SUHU MENDADAK", (760, 1060)), ("k5", "TERTAWA / GUGUP", (280, 1420))]
    for key, nm, (cx, cy) in cards:
        tb = _b(sc, key, dur)
        k = eob(seg(t, tb, tb + 0.45), 1.6)
        if k <= 0:
            continue
        w, h = 400 * k, 300 * k
        R.shadow(img, (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), 40, 14, 0.18, 10)
        R.rrect(img, (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), 40, fill=WHITE, outline=mix(acc, CREAM, 0.3), width=3)
        D.burst(img, (cx, cy), seg(t, tb, tb + 0.5), acc, 10, 190, 9)
        ic = (cx, cy - 30)
        if k > 0.6:
            if key == "k1":
                # piring + garpu bergerak cepat
                R.circ(img, (ic[0] - 20, ic[1]), 62, fill=mix(acc, WHITE, 0.7), outline=INK, width=5)
                R.circ(img, (ic[0] - 20, ic[1]), 36, fill=acc)
                fx = ic[0] + 75 + 10 * math.sin(t * 14)
                R.line(img, [(fx, ic[1] - 70), (fx, ic[1] + 70)], INK, 8)
                for j in (-12, 0, 12):
                    R.line(img, [(fx + j, ic[1] - 70), (fx + j, ic[1] - 35)], INK, 6)
            elif key == "k2":
                D.glass_soda(img, ic, 150, fizz=1.0, t=t, color=acc)
            elif key == "k3":
                D.stomach(img, ic, 190, full=0.95 + 0.04 * math.sin(t * 5), color=acc)
            elif key == "k4":
                D.thermometer(img, (ic[0] - 50, ic[1]), 150, level=0.5 + 0.45 * math.sin(t * 3), color=acc)
                # butir es & api sederhana
                R.poly(img, [(ic[0] + 60, ic[1] - 40), (ic[0] + 95, ic[1] - 20), (ic[0] + 95, ic[1] + 20),
                             (ic[0] + 60, ic[1] + 40), (ic[0] + 25, ic[1] + 20), (ic[0] + 25, ic[1] - 20)],
                       fill=(200, 230, 250), outline=INK, width=4)
            else:
                # "HA HA" kinetik + petir gugup
                for j, s in enumerate(("HA", "HA")):
                    sc_ = 1 + 0.12 * math.sin(t * 9 + j * 1.5)
                    R.text(img, (ic[0] - 60 + j * 110, ic[1] - 10), s, 52, "Bold", acc, "mm", scale=sc_)
                z = [(ic[0] + 130, ic[1] - 60), (ic[0] + 105, ic[1] - 5), (ic[0] + 135, ic[1] - 5), (ic[0] + 110, ic[1] + 60)]
                R.line(img, z, INK, 7, 0.6 + 0.4 * math.sin(t * 20))
        lk = seg(t, tb + 0.3, tb + 0.6)
        R.text(img, (cx, cy + 105), nm, R.fit_size(nm, w - 30, 26, 18, "SemiBold"), "SemiBold", INK, "mm", alpha=lk, track=lk >= 1)
    # panel kanan bawah: saraf terusik
    ts = _b(sc, "saraf", dur)
    k = eo(seg(t, ts, ts + 0.6))
    if k > 0:
        cx, cy = 760, 1420
        R.rrect(img, (cx - 190 * k, cy - 140 * k, cx + 190 * k, cy + 140 * k), 40, fill=acc)
        for j in range(3):
            D.wave(img, cx - 150, cx + 150, cy - 40 + j * 40, 14, 3, t * 9 + j, WHITE, 5, k * (0.9 - j * 0.2))
        R.text(img, (cx, cy + 85), "SARAF TERUSIK", 24, "Bold", WHITE, "mm", alpha=k, track=k >= 1)


# ------------------------------------------------------------------ f5 janin & evolusi

@register("janin50")
def sc_janin50(img, t, dur, sc):
    acc = _acc(sc)
    t0 = _b(sc, "muncul", dur)
    ta, tdn, tot, tam, tin = [_b(sc, k, dur) for k in ("angka", "denyut", "otak", "amfibi", "insang")]
    u = eo(seg(t, t0, t0 + 0.7))
    # atas: rahim abstrak (lingkaran hangat) dengan kubah diafragma mini yang berdenyut
    cx, cy = 400, 800
    R.glow(img, (cx, cy), 330, acc, 0.22 * u)
    R.circ(img, (cx, cy), 250 * u, fill=mix(acc, WHITE, 0.82), outline=acc, width=8)
    R.circ(img, (cx, cy), 205 * u, outline=mix(acc, WHITE, 0.4), width=3)
    pulse = _spasm(t, tdn) + sum(_spasm(t, tdn + 1.1 * j) for j in range(1, 4))
    D.lungs(img, (cx, cy - 40), 170 * u, expand=0.4 - pulse, color=mix(acc, WHITE, 0.5), alpha=u)
    D.dome(img, (cx, cy + 60), 220 * u, sag=0.5 - 0.5 * pulse, color=acc, alpha=u, thick=14, spasm=pulse)
    # penghitung minggu
    if t >= ta:
        k = eo(seg(t, ta, ta + 1.2))
        R.rrect(img, (700, 690, 1000, 900), 36, fill=INK)
        D.counter_text(img, (850, 765), int(9 * k), 84, WHITE)
        R.text(img, (850, 850), "MINGGU", 26, "SemiBold", (200, 200, 210), "mm", track=True)
    # otak belajar: kilau + garis ke label
    if t >= tot:
        k = eo(seg(t, tot, tot + 0.6))
        for j in range(5):
            D.burst(img, (cx, cy - 190), ((t - tot) * 0.7 + j * 0.2) % 1.0, acc, 6, 90, 7, seed=j)
        label(img, (700, 980), "otak belajar bernapas", 28, INK, "lm", "SemiBold", k, bg=WHITE)
    # bawah: leluhur amfibi: lengkung insang + gelombang air
    if t >= tam:
        k = eo(seg(t, tam, tam + 0.8))
        gx, gy = 470, 1350
        R.rrect(img, (60, 1160, 900, 1560), 60, fill=mix((46, 134, 171), WHITE, 0.8), alpha=k)
        for j in range(3):
            D.wave(img, 80, 880, 1200 + j * 24, 8, 4, t * 2 + j, (46, 134, 171), 4, k * 0.5)
        # tubuh kecebong abstrak (lonjong + ekor bergelombang) - objek, bukan tokoh
        R.circ(img, (gx - 120, gy + 20), 70 * k, fill=(46, 134, 171), outline=INK, width=5)
        tail = [(gx - 60 + i * 12, gy + 20 + 22 * math.sin(t * 8 + i * 0.5) * (i / 20)) for i in range(20)]
        R.line(img, tail, (46, 134, 171), 16 * k)
        # lengkung insang berdenyut
        ki = eo(seg(t, tin, tin + 0.5))
        for j in range(3):
            R.ring(img, (gx - 120, gy + 20), 40 + j * 16, INK, 5, 300, 420, ki * (1 - j * 0.2) * (0.6 + 0.4 * math.sin(t * 6 + j)))
        label(img, (620, 1300), "LELUHUR AMFIBI", 26, INK, "mm", "SemiBold", k, bg=WHITE)
        label(img, (620, 1420), "bernapas dengan insang", 24, MUTED, "mm", "Medium", ki)
        sticker(img, t, tin, (760, 1180), "HIPOTESIS", INK, 24, rot=6)


# ------------------------------------------------------------------ f6 cara & rekor

@register("rekor50")
def sc_rekor50(img, t, dur, sc):
    acc = _acc(sc)
    t0 = _b(sc, "muncul", dur)
    c1, c2, tp, tr, tang = [_b(sc, k, dur) for k in ("cek1", "cek2", "putus", "rekor", "angka")]
    u = eo(seg(t, t0, t0 + 0.6))
    # kartu cara rumahan
    for j, (tb, nm, sub) in enumerate(((c1, "TAHAN NAPAS", "CO2 naik"), (c2, "AIR DINGIN", "rangsang vagus"))):
        k = eob(seg(t, tb - 0.4, tb), 1.5)
        if k <= 0:
            continue
        x0, y0 = 60, 620 + j * 200
        R.shadow(img, (x0, y0, x0 + 700, y0 + 160), 36, 12, 0.15, 8)
        R.rrect(img, (x0, y0, x0 + 700 * k, y0 + 160), 36, fill=WHITE, outline=mix(acc, CREAM, 0.4), width=3)
        R.text(img, (x0 + 140, y0 + 60), nm, 36, "Bold", INK, "lm", alpha=k, track=k >= 1)
        R.text(img, (x0 + 140, y0 + 112), sub, 24, "Medium", MUTED, "lm", alpha=k, track=k >= 1)
        kc = seg(t, tb, tb + 0.35)
        R.circ(img, (x0 + 75, y0 + 80), 44, fill=acc if kc > 0 else mix(acc, WHITE, 0.6))
        if kc > 0:
            R.check_mark(img, (x0 + 75, y0 + 80), 46, WHITE, 9, kc)
    # panah CO2 naik di kanan kartu
    if t >= c1:
        for i in range(3):
            p = (t * 0.6 + i * 0.33) % 1.0
            R.arrow(img, [(880, 760 - p * 60), (880, 700 - p * 60)], acc, 6, 16, (1 - p) * 0.9)
        label(img, (880, 830), "CO2", 24, INK, "mm", "Bold", 1.0, bg=WHITE)
    # refleks terputus: garis sinyal patah
    if t >= tp:
        k = eo(seg(t, tp, tp + 0.5))
        y = 1050
        R.line(img, [(100, y), (420 - 40 * k, y)], INK, 8, 0.9)
        R.line(img, [(520 + 40 * k, y), (860, y)], INK, 8, 0.9)
        R.text(img, (470, y), "X", 60, "Bold", acc, "mm", scale=0.6 + 0.4 * k)
        label(img, (470, 1110), "REFLEKS TERPUTUS", 26, WHITE, "mm", "Bold", k, bg=acc)
    # sebelum kartu rekor: partikel lembut agar area bawah tidak kosong
    if t < tr:
        D.particles(img, (100, 1180, 860, 1540), t, 14, acc, 9, 0.35 * u, seed=4)
    # rekor dunia: odometer 68 tahun
    if t >= tr:
        k = eob(seg(t, tr, tr + 0.45), 1.6)
        cx, cy = 480, 1370
        R.shadow(img, (cx - 400, cy - 150, cx + 400, cy + 150), 50, 16, 0.2, 10)
        R.rrect(img, (cx - 400 * k, cy - 150 * k, cx + 400 * k, cy + 150 * k), 50, fill=INK)
        ka = seg(t, tang, tang + 1.4)
        val = int(round(68 * eo(ka)))
        R.text(img, (cx - 250, cy - 10), str(val), 150, "Bold", WHITE, "mm", track=ka >= 1)
        R.text(img, (cx - 40, cy - 40), "TAHUN", 44, "Bold", acc, "lm", alpha=k, track=k >= 1)
        R.text(img, (cx - 40, cy + 20), "tanpa henti", 28, "Medium", (200, 200, 210), "lm", alpha=k, track=k >= 1)
        # bilah 1922-1990
        if ka > 0:
            R.rrect(img, (cx - 250, cy + 80, cx + 250, cy + 96), 8, fill=(70, 70, 80))
            R.rrect(img, (cx - 250, cy + 80, cx - 250 + 500 * eo(ka), cy + 96), 8, fill=acc)
            R.text(img, (cx - 250, cy + 120), "1922", 22, "SemiBold", (200, 200, 210), "lm", track=True)
            R.text(img, (cx + 250, cy + 120), "1990", 22, "SemiBold", (200, 200, 210), "rm", track=True)
        sticker(img, t, tr + 0.2, (740, 1225), "REKOR", acc, 40, rot=10)
        D.burst(img, (cx, cy), seg(t, tr, tr + 0.6), acc, 14, 420, 12)


# ------------------------------------------------------------------ rangkuman

@register("rangkuman50")
def sc_rangkuman50(img, t, dur, sc):
    acc = _acc(sc)
    s1, s2, s3, tj, tdk = [_b(sc, k, dur) for k in ("s1", "s2", "s3", "jam", "dokter")]
    steps = [(s1, "1", "DIAFRAGMA KEDUT", (46, 134, 171)), (s2, "2", "PITA SUARA MENUTUP", (123, 44, 191)),
             (s3, "3", "SARAF TERUSIK", (244, 162, 89))]
    for j, (tb, num, nm, col) in enumerate(steps):
        k = eob(seg(t, tb, tb + 0.45), 1.5)
        if k <= 0:
            continue
        y0 = 600 + j * 190
        R.shadow(img, (60, y0, 900, y0 + 140), 34, 12, 0.15, 8)
        R.rrect(img, (60, y0, 60 + 840 * k, y0 + 140), 34, fill=WHITE, outline=mix(col, CREAM, 0.3), width=3)
        R.circ(img, (140, y0 + 70), 46 * k, fill=col)
        R.text(img, (140, y0 + 70), num, 40 * k, "Bold", WHITE, "mm")
        R.text(img, (220, y0 + 70), nm, 34, "Bold", INK, "lm", alpha=k, track=k >= 1)
        if j < 2:
            ka = eo(seg(t, tb + 0.3, tb + 0.7))
            R.arrow(img, [(140, y0 + 125), (140, y0 + 125 + 50 * ka)], INK, 6, 16, ka)
        # ikon mini kanan
        if k > 0.7:
            if j == 0:
                D.dome(img, (800, y0 + 90), 130, sag=0.4, color=col, thick=12, spasm=0.6 * (0.5 + 0.5 * math.sin(t * 12)))
            elif j == 1:
                g = 12 * (0.5 + 0.5 * math.sin(t * 5))
                R.line(img, [(800, y0 + 25), (800 - g, y0 + 70), (800, y0 + 115)], col, 8)
                R.line(img, [(800, y0 + 25), (800 + g, y0 + 70), (800, y0 + 115)], col, 8)
            else:
                D.wave(img, 740, 860, y0 + 70, 18, 2.5, t * 8, col, 6)
    # kartu 48 jam
    if t >= tj:
        k = eob(seg(t, tj, tj + 0.5), 1.6)
        cx, cy = 480, 1370
        R.shadow(img, (cx - 420, cy - 150, cx + 420, cy + 150), 50, 16, 0.2, 10)
        R.rrect(img, (cx - 420 * k, cy - 150 * k, cx + 420 * k, cy + 150 * k), 50, fill=acc)
        D.clock(img, (cx - 290, cy), 95 * k, frac=seg(t, tj, tj + 2.0), color=acc)
        R.text(img, (cx - 160, cy - 45), "> 48 JAM", 62, "Bold", WHITE, "lm", alpha=k, track=k >= 1)
        kd = eo(seg(t, tdk, tdk + 0.4))
        R.text(img, (cx - 160, cy + 35), "periksa ke dokter", 34, "SemiBold", WHITE, "lm", alpha=kd, track=kd >= 1)
        R.text(img, (cx - 160, cy + 90), "bisa tanda masalah lain", 24, "Medium", (255, 235, 225), "lm", alpha=kd, track=kd >= 1)
        # tanda seru (bentuk)
        if kd > 0:
            ex = cx + 300
            R.rrect(img, (ex - 14, cy - 90, ex + 14, cy + 20), 14, fill=WHITE, alpha=kd)
            R.circ(img, (ex, cy + 60), 18 * kd, fill=WHITE)


# ------------------------------------------------------------------ outro

@register("outro_default")
def sc_outro_default(img, t, dur, sc):
    acc = _acc(sc)
    th = _b(sc, "hik", dur)
    k = eo(seg(t, th - 0.3, th + 0.4))
    if k <= 0:
        return
    cx, cy = 540, 1300
    sp = _spasm(t, th) + _spasm(t, th + 2.4) + _spasm(t, th + 4.7)
    R.glow(img, (cx, cy), 260, acc, 0.15 * k)
    D.lungs(img, (cx, cy - 60), 260 * k, expand=0.5 + 0.3 * math.sin(t * 1.5) - 0.5 * sp, color=mix(acc, WHITE, 0.55), alpha=k)
    D.dome(img, (cx, cy + 70), 340 * k, sag=0.5 + 0.3 * math.sin(t * 1.5) - 0.5 * sp, color=acc, alpha=k, thick=16, spasm=sp)
    for j, tb in enumerate((th, th + 2.4, th + 4.7)):
        sticker(img, t, tb, (300 + j * 220, 1170 + (j % 2) * 30), "HIK!", acc, 36, rot=-10 + j * 8, life=1.5)
