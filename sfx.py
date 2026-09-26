#!/usr/bin/env python3
"""sfx.py - katalog bunyi sintetis KlikTahu (numpy saja, tanpa sampel/lisensi).

Semua fungsi mengembalikan array float32 mono, SR = 48000, puncak <= 1.0.
`LEVEL[nama]` = gain relatif (dB) yang dipakai master_audio/audio_long.
`python3 sfx.py` = katalog uji: render semua bunyi ke build/sfx_katalog.wav + cek NaN/klip.
"""
import math
import os
import sys
import wave

import numpy as np

SR = 48000
_RNG_SEED = 20260926


def _rng(seed=0):
    return np.random.default_rng(_RNG_SEED + seed)


def _t(dur):
    return np.arange(int(dur * SR), dtype=np.float32) / SR


def _env(n, a=0.005, d=0.1, s=0.0, r=0.1, hold=0.0):
    """Envelope ADSR sederhana (detik)."""
    a_n, d_n, r_n, h_n = [max(1, int(x * SR)) for x in (a, d, r, hold)]
    e = np.zeros(n, dtype=np.float32)
    i = 0
    seg = np.linspace(0, 1, a_n, dtype=np.float32)[: n - i]
    e[i:i + len(seg)] = seg
    i += len(seg)
    seg = np.linspace(1, s, d_n, dtype=np.float32)[: max(0, n - i)]
    e[i:i + len(seg)] = seg
    i += len(seg)
    seg = np.full(h_n, s, dtype=np.float32)[: max(0, n - i)]
    e[i:i + len(seg)] = seg
    i += len(seg)
    seg = np.linspace(s, 0, r_n, dtype=np.float32)[: max(0, n - i)]
    e[i:i + len(seg)] = seg
    return e


def _fade(x, ms_in=2, ms_out=15):
    n = len(x)
    a = min(n, int(SR * ms_in / 1000))
    b = min(n, int(SR * ms_out / 1000))
    if a > 0:
        x[:a] *= np.linspace(0, 1, a, dtype=np.float32)
    if b > 0:
        x[-b:] *= np.linspace(1, 0, b, dtype=np.float32)
    return x


def _norm(x, peak=0.9):
    m = float(np.max(np.abs(x))) if len(x) else 0.0
    if m > 1e-9:
        x = x * (peak / m)
    return _fade(x.astype(np.float32))


def _lowpass(x, fc):
    """One-pole lowpass (cepat, cukup untuk SFX)."""
    fc = float(np.clip(fc, 20, SR / 2 - 100))
    a = math.exp(-2 * math.pi * fc / SR)
    y = np.empty_like(x)
    acc = 0.0
    b = 1 - a
    for i in range(len(x)):
        acc = b * x[i] + a * acc
        y[i] = acc
    return y


def _lowpass_fast(x, fc):
    """Lowpass via FFT (untuk klip panjang)."""
    n = len(x)
    if n < 8:
        return x
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    H = 1.0 / np.sqrt(1 + (f / max(20.0, fc)) ** 4)
    return np.fft.irfft(X * H, n).astype(np.float32)


def _bandpass_fast(x, lo, hi, order=2):
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    Hh = 1.0 / np.sqrt(1 + (f / max(20.0, hi)) ** (2 * order))
    Hl = 1.0 - 1.0 / np.sqrt(1 + (f / max(10.0, lo)) ** (2 * order))
    return np.fft.irfft(X * Hh * Hl, n).astype(np.float32)


def _sweep_noise(dur, f0, f1, bw=0.6, seed=1, curve=1.0):
    """Derau yang difilter band-pass dengan frekuensi pusat menyapu f0 -> f1."""
    n = int(dur * SR)
    noise = _rng(seed).standard_normal(n).astype(np.float32)
    # bagi menjadi blok, filter tiap blok dengan pusat berbeda (cukup halus untuk SFX)
    out = np.zeros(n, dtype=np.float32)
    blk = 1024
    hop = blk // 2
    win = np.hanning(blk).astype(np.float32)
    for st in range(0, n - blk, hop):
        p = (st / max(1, n - blk)) ** curve
        fc = f0 * (f1 / f0) ** p
        seg = noise[st:st + blk] * win
        out[st:st + blk] += _bandpass_fast(seg, fc / (1 + bw), fc * (1 + bw))
    return out


def _tone(dur, f0, f1=None, wave_="sine", seed=0):
    t = _t(dur)
    if f1 is None:
        f1 = f0
    # sapuan eksponensial
    k = math.log(f1 / f0) if f0 > 0 and f1 > 0 else 0.0
    if abs(k) < 1e-6:
        ph = 2 * math.pi * f0 * t
    else:
        ph = 2 * math.pi * f0 * (np.exp(k * t / dur) - 1) * dur / k
    if wave_ == "sine":
        return np.sin(ph).astype(np.float32)
    if wave_ == "tri":
        return (2 / math.pi * np.arcsin(np.sin(ph))).astype(np.float32)
    if wave_ == "saw":
        return ((ph / math.pi) % 2 - 1).astype(np.float32)
    return np.sign(np.sin(ph)).astype(np.float32)


# ---------------------------------------------------------------- katalog

def whoosh(dur=0.55):
    x = _sweep_noise(dur, 300, 2600, bw=0.7, seed=1, curve=0.8)
    n = len(x)
    x *= _env(n, a=0.12 * dur, d=0.5 * dur, s=0.35, r=0.38 * dur)
    return _norm(x)


def swish(dur=0.32):
    x = _sweep_noise(dur, 1800, 600, bw=0.8, seed=2)
    x *= _env(len(x), a=0.03, d=0.12, s=0.2, r=0.15)
    return _norm(x)


def swish_up(dur=0.32):
    x = _sweep_noise(dur, 500, 3200, bw=0.8, seed=3)
    x *= _env(len(x), a=0.04, d=0.1, s=0.3, r=0.16)
    return _norm(x)


def pop(dur=0.12):
    x = _tone(dur, 520, 140) * _env(int(dur * SR), a=0.002, d=0.06, s=0.0, r=0.05)
    click = _rng(4).standard_normal(int(0.004 * SR)).astype(np.float32) * 0.4
    x[: len(click)] += click
    return _norm(x)


def tick(dur=0.05):
    x = _rng(5).standard_normal(int(dur * SR)).astype(np.float32)
    x = _bandpass_fast(x, 2500, 7000)
    x *= _env(len(x), a=0.001, d=0.03, s=0.0, r=0.02)
    return _norm(x, 0.7)


def click(dur=0.04):
    x = _tone(dur, 2400, 1800) * _env(int(dur * SR), a=0.001, d=0.02, s=0.0, r=0.02)
    return _norm(x, 0.7)


def impact(dur=0.5):
    n = int(dur * SR)
    body = _tone(dur, 140, 42) * _env(n, a=0.002, d=0.25, s=0.1, r=0.25)
    noise = _rng(6).standard_normal(n).astype(np.float32)
    noise = _lowpass_fast(noise, 1800) * _env(n, a=0.001, d=0.08, s=0.0, r=0.1)
    return _norm(body + 0.5 * noise)


def thud(dur=0.35):
    n = int(dur * SR)
    x = _tone(dur, 95, 40) * _env(n, a=0.003, d=0.2, s=0.05, r=0.15)
    return _norm(x)


def boom(dur=1.1):
    n = int(dur * SR)
    x = _tone(dur, 70, 30) * _env(n, a=0.005, d=0.6, s=0.2, r=0.5)
    noise = _lowpass_fast(_rng(7).standard_normal(n).astype(np.float32), 400)
    x += 0.5 * noise * _env(n, a=0.002, d=0.3, s=0.05, r=0.6)
    return _norm(x)


def riser(dur=1.4):
    x = _sweep_noise(dur, 200, 4000, bw=0.5, seed=8, curve=1.4)
    t = _tone(dur, 110, 880, "saw") * 0.25
    x = x + t
    x *= _env(len(x), a=0.85 * dur, d=0.05, s=0.9, r=0.1 * dur)
    return _norm(x, 0.85)


def ding(dur=0.9):
    n = int(dur * SR)
    t = _t(dur)
    x = (np.sin(2 * math.pi * 1320 * t) + 0.5 * np.sin(2 * math.pi * 2640 * t) +
         0.25 * np.sin(2 * math.pi * 3960 * t)).astype(np.float32)
    x *= np.exp(-t * 5.0).astype(np.float32)
    return _norm(x, 0.8)


def glitch(dur=0.28):
    n = int(dur * SR)
    r = _rng(9)
    x = np.zeros(n, dtype=np.float32)
    seg = int(0.012 * SR)
    for st in range(0, n, seg):
        f = r.choice([440, 880, 1760, 2200, 3300])
        x[st:st + seg] = _tone(seg / SR, f, f, "square")[: n - st] * r.uniform(0.2, 1.0)
    x *= _env(n, a=0.002, d=0.1, s=0.5, r=0.08)
    return _norm(x, 0.7)


def zap(dur=0.22):
    n = int(dur * SR)
    x = _tone(dur, 3200, 180, "saw") * _env(n, a=0.002, d=0.12, s=0.0, r=0.08)
    return _norm(x, 0.8)


def door(dur=0.5):
    n = int(dur * SR)
    x = _tone(dur, 60, 45) * _env(n, a=0.004, d=0.3, s=0.0, r=0.15)
    x += 0.4 * _lowpass_fast(_rng(10).standard_normal(n).astype(np.float32), 900) * _env(n, 0.001, 0.05, 0.0, 0.05)
    return _norm(x)


def nging(dur=1.2):
    n = int(dur * SR)
    t = _t(dur)
    x = np.sin(2 * math.pi * 4200 * t).astype(np.float32) * _env(n, a=0.02, d=0.6, s=0.3, r=0.5)
    return _norm(x, 0.5)


def retak(dur=0.4):
    n = int(dur * SR)
    r = _rng(11)
    x = np.zeros(n, dtype=np.float32)
    for _ in range(9):
        p = int(r.uniform(0, n * 0.7))
        L = int(SR * r.uniform(0.003, 0.012))
        x[p:p + L] += r.standard_normal(min(L, n - p)).astype(np.float32) * r.uniform(0.3, 1.0)
    x = _bandpass_fast(x, 800, 6000)
    return _norm(x, 0.8)


def kecapi(dur=0.9):
    n = int(dur * SR)
    t = _t(dur)
    x = np.zeros(n, dtype=np.float32)
    for i, f in enumerate([523.25, 659.25, 783.99, 1046.5]):
        st = int(i * 0.07 * SR)
        seg = np.sin(2 * math.pi * f * t[: n - st]) * np.exp(-t[: n - st] * 4)
        x[st:] += seg.astype(np.float32)
    return _norm(x, 0.75)


def kilau(dur=0.7):
    n = int(dur * SR)
    t = _t(dur)
    r = _rng(12)
    x = np.zeros(n, dtype=np.float32)
    for i in range(7):
        f = r.uniform(2000, 6000)
        st = int(i * 0.05 * SR)
        seg = np.sin(2 * math.pi * f * t[: n - st]) * np.exp(-t[: n - st] * 12)
        x[st:] += seg.astype(np.float32) * 0.5
    return _norm(x, 0.6)


def gelembung(dur=0.25):
    n = int(dur * SR)
    x = _tone(dur, 300, 1200) * _env(n, a=0.005, d=0.15, s=0.0, r=0.08)
    return _norm(x, 0.7)


def gigit(dur=0.18):
    n = int(dur * SR)
    x = _lowpass_fast(_rng(13).standard_normal(n).astype(np.float32), 2500)
    x *= _env(n, a=0.001, d=0.05, s=0.2, r=0.1)
    x += _tone(dur, 200, 90) * _env(n, 0.001, 0.08, 0.0, 0.05) * 0.8
    return _norm(x, 0.8)


def guntur(dur=2.0):
    n = int(dur * SR)
    r = _rng(14)
    x = _lowpass_fast(r.standard_normal(n).astype(np.float32), 250)
    mod = 0.6 + 0.4 * np.sin(2 * math.pi * r.uniform(1.5, 3.0) * _t(dur) + r.uniform(0, 6))
    x *= mod.astype(np.float32) * _env(n, a=0.05, d=0.8, s=0.4, r=1.0)
    return _norm(x)


def detak(dur=0.5):
    n = int(dur * SR)
    a = _tone(0.12, 80, 45) * _env(int(0.12 * SR), 0.002, 0.08, 0.0, 0.03)
    x = np.zeros(n, dtype=np.float32)
    x[: len(a)] += a
    p = int(0.17 * SR)
    x[p:p + len(a)] += a * 0.8
    return _norm(x)


def laser(dur=0.3):
    n = int(dur * SR)
    x = _tone(dur, 2200, 300, "tri") * _env(n, 0.002, 0.15, 0.1, 0.1)
    return _norm(x, 0.75)


def angin(dur=2.5):
    n = int(dur * SR)
    r = _rng(15)
    x = _bandpass_fast(r.standard_normal(n).astype(np.float32), 200, 900)
    mod = 0.5 + 0.5 * np.sin(2 * math.pi * 0.4 * _t(dur))
    x *= mod.astype(np.float32) * _env(n, a=0.6, d=0.5, s=0.7, r=1.0)
    return _norm(x, 0.7)


def hik(dur=0.16):
    """Bunyi 'hik' sintetis: hisapan udara pendek + penutupan glotis (klik rendah)."""
    n = int(dur * SR)
    x = _bandpass_fast(_rng(16).standard_normal(n).astype(np.float32), 600, 2600)
    x *= _env(n, a=0.02, d=0.05, s=0.0, r=0.02)
    stop = _tone(0.03, 260, 120) * _env(int(0.03 * SR), 0.001, 0.02, 0.0, 0.01)
    p = int(0.075 * SR)
    x[p:p + len(stop)] += stop[: max(0, n - p)] * 1.2
    return _norm(x, 0.8)


def napas(dur=0.9):
    n = int(dur * SR)
    x = _bandpass_fast(_rng(17).standard_normal(n).astype(np.float32), 300, 1800)
    x *= _env(n, a=0.35 * dur, d=0.2 * dur, s=0.5, r=0.4 * dur)
    return _norm(x, 0.55)


def denyut(dur=0.35):
    n = int(dur * SR)
    x = _tone(dur, 160, 70) * _env(n, 0.003, 0.15, 0.0, 0.1)
    return _norm(x, 0.8)


def sinyal(dur=0.45):
    """Sinyal saraf: rentetan blip cepat menaik."""
    n = int(dur * SR)
    x = np.zeros(n, dtype=np.float32)
    for i in range(6):
        st = int(i * 0.06 * SR)
        L = int(0.035 * SR)
        f = 900 + i * 220
        x[st:st + L] += _tone(L / SR, f, f * 1.1) * _env(L, 0.002, 0.02, 0.0, 0.012)
    return _norm(x, 0.7)


CATALOG = {
    "whoosh": whoosh, "swish": swish, "swish_up": swish_up, "pop": pop, "tick": tick, "click": click,
    "impact": impact, "thud": thud, "boom": boom, "riser": riser, "ding": ding, "glitch": glitch,
    "zap": zap, "door": door, "nging": nging, "retak": retak, "kecapi": kecapi, "kilau": kilau,
    "gelembung": gelembung, "gigit": gigit, "guntur": guntur, "detak": detak, "laser": laser,
    "angin": angin, "hik": hik, "napas": napas, "denyut": denyut, "sinyal": sinyal,
}

# gain relatif per bunyi (dB), ditambahkan pada level dasar master (-16 dB)
LEVEL = {
    "whoosh": 0, "swish": -3, "swish_up": -3, "pop": -2, "tick": -8, "click": -9, "impact": 2, "thud": 0,
    "boom": 2, "riser": -1, "ding": -4, "glitch": -5, "zap": -4, "door": 0, "nging": -10, "retak": -3,
    "kecapi": -4, "kilau": -7, "gelembung": -5, "gigit": -2, "guntur": 0, "detak": -1, "laser": -5,
    "angin": -6, "hik": -1, "napas": -8, "denyut": -1, "sinyal": -6,
}

_CACHE = {}


def get(name):
    """Ambil bunyi (ter-cache). Nama tak dikenal -> 'pop'."""
    fn = CATALOG.get(name, CATALOG["pop"])
    if name not in _CACHE:
        _CACHE[name] = fn()
    return _CACHE[name]


def write_wav(path, x, sr=SR):
    x = np.clip(x, -1, 1)
    pcm = (x * 32767).astype("<i2")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def _selftest():
    parts = []
    gap = np.zeros(int(0.35 * SR), dtype=np.float32)
    bad = 0
    for name in CATALOG:
        x = get(name)
        ok = np.isfinite(x).all() and float(np.max(np.abs(x))) <= 1.0 and len(x) > 100
        print(f"{name:10s} {len(x)/SR:5.2f}s peak={float(np.max(np.abs(x))):.2f} {'OK' if ok else 'GAGAL'}")
        bad += 0 if ok else 1
        parts += [x, gap]
    out = np.concatenate(parts)
    write_wav("build/sfx_katalog.wav", out)
    print("katalog ->", "build/sfx_katalog.wav", f"{len(out)/SR:.1f}s", "GAGAL" if bad else "SEMUA OK")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(_selftest())
