#!/usr/bin/env python3
"""sfx.py - katalog bunyi SINTETIS KlikTahu (numpy murni, tanpa file sampel / lisensi).

Semua bunyi deterministik (seed dari nama). API:
    render(nama) -> np.float32 mono 48 kHz, puncak dinormalisasi 0.9
    LEVEL[nama]  -> dB relatif (penyeimbang antar bunyi; dipakai master_audio)
    daftar()     -> nama bunyi tersedia

Uji / katalog:  python3 sfx.py        (render semua 2x, cek deterministik, tulis build/sfx/katalog.wav)
"""
from __future__ import annotations

import sys
import zlib
from functools import lru_cache
from pathlib import Path

import numpy as np

SR = 48000
TAU = 2 * np.pi


# ------------------------------------------------------------------------------------------ util
def _rng(nama, k=0):
    return np.random.default_rng(zlib.crc32(f"{nama}:{k}".encode()))


def _t(dur):
    return np.arange(int(round(dur * SR))) / SR


def _norm(x, peak=0.9):
    m = float(np.abs(x).max()) if len(x) else 0.0
    return (x * (peak / m)).astype(np.float32) if m > 1e-9 else x.astype(np.float32)


def _fade(x, fin=0.002, fout=0.01):
    x = x.copy()
    a, b = int(fin * SR), int(fout * SR)
    if a > 0:
        x[:a] *= np.sin(np.linspace(0, np.pi / 2, a)) ** 2
    if b > 0:
        x[-b:] *= np.cos(np.linspace(0, np.pi / 2, b)) ** 2
    return x


def _chirp(f, sr=SR):
    """f: array frekuensi per sampel -> sinus fase kontinu."""
    return np.sin(TAU * np.cumsum(f) / sr)


def _band(x, lo=None, hi=None, soft=0.25):
    """Filter pita fase-nol via FFT, tepi halus (lebar transisi 'soft' oktaf)."""
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    lf = np.log2(np.maximum(f, 1.0))
    m = np.ones_like(f)
    if lo:
        u = np.clip((lf - np.log2(lo) + soft) / (2 * soft), 0, 1)
        m *= u * u * (3 - 2 * u)
    if hi:
        u = np.clip((lf - np.log2(hi) + soft) / (2 * soft), 0, 1)
        m *= 1 - u * u * (3 - 2 * u)
    return np.fft.irfft(X * m, n=n)


def _noise_sweep(dur, fc, bw_oct, rng, N=1024, H=256):
    """Derau pita-sempit yang pusat frekuensinya bergerak (STFT overlap-add, Hann 75%).
    fc: fungsi u(0..1) -> Hz atau array; bw_oct: lebar pita (oktaf, Gaussian di log-f)."""
    n = int(round(dur * SR))
    nfr = int(np.ceil(n / H)) + 4
    win = np.hanning(N + 1)[:N]
    f = np.fft.rfftfreq(N, 1 / SR)
    lf = np.log2(np.maximum(f, 1.0))
    out = np.zeros(nfr * H + N)
    wsum = np.zeros_like(out)
    frames = np.fft.rfft(rng.standard_normal((nfr, N)), axis=1)
    for i in range(nfr):
        u = min(1.0, max(0.0, (i * H - N / 2) / max(1, n)))
        c = fc(u) if callable(fc) else fc
        bw = bw_oct(u) if callable(bw_oct) else bw_oct
        mask = np.exp(-0.5 * ((lf - np.log2(c)) / (bw / 2.0)) ** 2)
        seg = np.fft.irfft(frames[i] * mask, n=N) * win
        out[i * H:i * H + N] += seg
        wsum[i * H:i * H + N] += win ** 2
    y = out / np.maximum(np.sqrt(wsum), 1e-3)
    return y[N // 2:N // 2 + n]


def _env(n, a, d, shape=2.0):
    """Envelope naik a (detik) lalu turun d (detik), panjang n sampel."""
    t = np.arange(n) / SR
    e = np.where(t < a, (t / max(a, 1e-4)) ** 1.5, np.exp(-(t - a) / max(d, 1e-4) * shape))
    return e


def _dec(t, tau):
    return np.exp(-t / tau)


def _smooth_bump(u, peak=0.5):
    """Bentuk naik-turun halus 0..1..0 dengan puncak di 'peak' (u 0..1)."""
    a = np.clip(u / peak, 0, 1)
    b = np.clip((1 - u) / (1 - peak), 0, 1)
    return np.sin(np.pi / 2 * np.minimum(a, 1)) ** 2 * np.sin(np.pi / 2 * np.minimum(b, 1)) ** 2


# ------------------------------------------------------------------------------------------ bunyi
def s_whoosh():
    d, r = 0.55, _rng("whoosh")
    u = np.linspace(0, 1, int(d * SR))
    x = _noise_sweep(d, lambda v: 350 * (7.0 ** np.sin(np.pi * min(v * 1.05, 1))), 1.1, r)
    x = x * _smooth_bump(u, 0.58)
    x += 0.25 * _band(r.standard_normal(len(x)), 60, 300) * _smooth_bump(u, 0.6)
    return _fade(x, 0.004, 0.03)


def s_swish():
    d, r = 0.28, _rng("swish")
    u = np.linspace(0, 1, int(d * SR))
    x = _noise_sweep(d, lambda v: 5200 * (0.25 ** v), 0.9, r) * _smooth_bump(u, 0.25)
    return _fade(x, 0.002, 0.02)


def s_swish_up():
    d, r = 0.32, _rng("swish_up")
    u = np.linspace(0, 1, int(d * SR))
    x = _noise_sweep(d, lambda v: 700 * (8.0 ** v), 0.9, r) * _smooth_bump(u, 0.8)
    return _fade(x, 0.003, 0.02)


def s_pop():
    t = _t(0.13)
    f = 170 + 780 * np.exp(-t / 0.012)
    x = _chirp(f) * _env(len(t), 0.0015, 0.028, 1.0)
    click = _band(_rng("pop").standard_normal(len(t)), 1500, 9000) * _dec(t, 0.002)
    return _fade(x + 0.35 * click, 0.0005, 0.02)


def s_tick():
    t = _t(0.05)
    x = np.sin(TAU * 3200 * t) * _dec(t, 0.006)
    x += 0.5 * _band(_rng("tick").standard_normal(len(t)), 2500, 12000) * _dec(t, 0.0015)
    return _fade(x, 0.0003, 0.01)


def s_click():
    t = _t(0.04)
    x = 0.8 * _band(_rng("click").standard_normal(len(t)), 2000, 7000) * _dec(t, 0.0012)
    x += 0.5 * np.sin(TAU * 1800 * t) * _dec(t, 0.005)
    return _fade(x, 0.0002, 0.008)


def s_impact():
    t, r = _t(0.75), _rng("impact")
    sub = _chirp(38 + 30 * np.exp(-t / 0.08)) * _dec(t, 0.2)
    mid = np.sin(TAU * 120 * t) * _dec(t, 0.05)
    nz = _band(r.standard_normal(len(t)), 80, 1400) * _dec(t, 0.06)
    x = np.tanh(1.6 * (sub + 0.5 * mid + 0.6 * nz))
    return _fade(x, 0.001, 0.08)


def s_thud():
    t, r = _t(0.36), _rng("thud")
    x = _chirp(50 + 45 * np.exp(-t / 0.03)) * _dec(t, 0.075)
    x += 0.45 * _band(r.standard_normal(len(t)), 60, 600) * _dec(t, 0.03)
    return _fade(x, 0.001, 0.05)


def s_boom():
    t, r = _t(1.7), _rng("boom")
    x = _chirp(28 + 26 * np.exp(-t / 0.18)) * _dec(t, 0.55)
    x += 0.7 * _band(r.standard_normal(len(t)), 25, 320) * _dec(t, 0.45)
    x += 0.3 * _band(r.standard_normal(len(t)), 300, 2500) * _dec(t, 0.04)
    return _fade(np.tanh(1.4 * x), 0.002, 0.25)


def s_riser():
    d, r = 1.3, _rng("riser")
    t = _t(d)
    u = t / d
    nz = _noise_sweep(d, lambda v: 400 * (18.0 ** v), 1.4, r)
    f = 180 * (6.0 ** u)
    tone = sum(np.sin(TAU * np.cumsum(f * k) / SR) / k for k in (1, 2, 3, 4))
    x = (0.8 * nz + 0.25 * tone) * (u ** 2.2)
    return _fade(x, 0.01, 0.025)


def s_ding():
    t = _t(1.4)
    x = np.zeros_like(t)
    for ratio, amp, tau in ((1.0, 1.0, 0.9), (2.0, 0.3, 0.55), (2.76, 0.45, 0.35), (5.4, 0.18, 0.16),
                            (8.93, 0.08, 0.08)):
        x += amp * np.sin(TAU * 1320 * ratio * t) * _dec(t, tau)
    return _fade(x * _env(len(t), 0.002, 10, 0.0), 0.001, 0.1)


def s_glitch():
    r = _rng("glitch")
    parts = []
    for i in range(9):
        n = int(r.uniform(0.018, 0.04) * SR)
        t = np.arange(n) / SR
        k = i % 3
        if k == 0:
            seg = np.sign(np.sin(TAU * r.uniform(180, 1600) * t))
        elif k == 1:
            seg = np.round(r.standard_normal(n) * 3) / 3
        else:
            seg = np.sin(TAU * r.uniform(2000, 5000) * t) * (r.random() > 0.3)
        parts.append(seg * r.uniform(0.4, 1.0))
        if r.random() > 0.6:
            parts.append(np.zeros(int(0.01 * SR)))
    x = np.concatenate(parts)
    return _fade(_band(x, 120, 9000), 0.001, 0.01)


def s_zap():
    t = _t(0.3)
    fc = 2400 * (0.075 ** (t / 0.3))
    mod = np.sin(TAU * 60 * t) * 3.0
    x = np.sin(TAU * np.cumsum(fc) / SR + mod) * _dec(t, 0.09)
    x += 0.3 * np.sign(x) * _dec(t, 0.04)
    return _fade(x, 0.001, 0.03)


def s_door():
    r = _rng("door")
    a = _noise_sweep(0.3, lambda v: 2600 * (0.3 ** v), 1.0, r) * _smooth_bump(np.linspace(0, 1, int(0.3 * SR)), 0.4)
    t = _t(0.35)
    b = _chirp(70 + 60 * np.exp(-t / 0.02)) * _dec(t, 0.06) + 0.3 * _band(r.standard_normal(len(t)), 100, 900) * _dec(t, 0.02)
    x = np.zeros(int(0.62 * SR))
    x[:len(a)] += 0.6 * a
    s0 = int(0.26 * SR)
    x[s0:s0 + len(b)] += b[:len(x) - s0]
    return _fade(x, 0.002, 0.04)


def s_nging():
    t = _t(1.2)
    vib = 1 + 0.003 * np.sin(TAU * 5 * t)
    x = np.sin(TAU * np.cumsum(6000 * vib) / SR) + 0.35 * np.sin(TAU * 4000 * t)
    e = np.minimum(1, t / 0.15) * np.where(t > 0.8, np.cos((t - 0.8) / 0.4 * np.pi / 2) ** 2, 1)
    return _fade(x * e, 0.01, 0.05)


def s_retak():
    r = _rng("retak")
    x = np.zeros(int(0.5 * SR))
    times = np.sort(r.uniform(0, 0.3, 14))
    for i, tm in enumerate(times):
        n = int(r.uniform(0.002, 0.008) * SR)
        s0 = int(tm * SR)
        tt = np.arange(n) / SR
        burst = _band(r.standard_normal(n), 1500, 12000) * _dec(tt, 0.0015) * (1 - i / 18)
        x[s0:s0 + n] += burst[:len(x) - s0]
    t = _t(0.5)
    x += 0.35 * _band(r.standard_normal(len(t)), 100, 900) * _dec(t, 0.05)
    return _fade(x, 0.0005, 0.05)


def s_kecapi():
    t = _t(1.5)
    x = np.zeros_like(t)
    for s0, f0, amp in ((0.0, 587.3, 1.0), (0.09, 784.0, 0.8)):
        tt = np.clip(t - s0, 0, None)
        on = (t >= s0).astype(float)
        for h in range(1, 12):
            fh = f0 * h * (1 + 0.0007 * h * h)
            ah = amp * np.sin(np.pi * h * 0.18) / h
            x += on * ah * np.sin(TAU * fh * tt) * _dec(tt, 1.1 / (1 + 0.4 * h))
    return _fade(x, 0.0008, 0.12)


def s_kilau():
    r = _rng("kilau")
    t = _t(0.85)
    x = np.zeros_like(t)
    for _ in range(8):
        s0 = r.uniform(0, 0.5)
        f = r.uniform(3500, 8200)
        tt = np.clip(t - s0, 0, None)
        x += (t >= s0) * r.uniform(0.3, 1.0) * np.sin(TAU * f * tt) * _dec(tt, r.uniform(0.04, 0.09))
    x += 0.08 * _band(r.standard_normal(len(t)), 6000, 14000) * _smooth_bump(t / 0.85, 0.3)
    return _fade(x, 0.001, 0.08)


def s_gelembung():
    r = _rng("gelembung")
    t = _t(0.75)
    x = np.zeros_like(t)
    for _ in range(6):
        s0 = r.uniform(0, 0.55)
        f0 = r.uniform(320, 760)
        tt = np.clip(t - s0, 0, None)
        f = f0 * (1 + 1.2 * np.minimum(tt / 0.045, 1))
        x += (t >= s0) * np.sin(TAU * np.cumsum(f) / SR) * _dec(tt, 0.03) * r.uniform(0.5, 1)
    return _fade(x, 0.001, 0.05)


def s_gigit():
    r = _rng("gigit")
    x = np.zeros(int(0.45 * SR))
    for k in range(3):
        n = int(0.05 * SR)
        s0 = int(k * 0.11 * SR)
        tt = np.arange(n) / SR
        crack = (r.random(n) > 0.93).astype(float) * r.standard_normal(n) * 2
        burst = _band(r.standard_normal(n) + crack, 800, 3600) * _dec(tt, 0.018) * (1 - 0.2 * k)
        x[s0:s0 + n] += burst
    return _fade(x, 0.0005, 0.03)


def s_guntur():
    r = _rng("guntur")
    t = _t(3.0)
    crack = _band(r.standard_normal(len(t)), 900, 9000) * _dec(t, 0.05)
    lfo = _band(r.standard_normal(len(t)), None, 6)
    lfo = 0.6 + 0.4 * lfo / (np.abs(lfo).max() + 1e-9)
    rumble = _band(r.standard_normal(len(t)), 25, 260) * _dec(t, 1.0) * lfo
    mid = _band(r.standard_normal(len(t)), 200, 900) * _dec(t, 0.35)
    x = 0.35 * crack + 1.0 * rumble + 0.35 * mid
    x = np.tanh(1.1 * x / (np.abs(x).max() + 1e-9))
    return _fade(_band(x, None, 2500), 0.002, 0.4)


def s_detak():
    t = _t(0.8)
    x = np.zeros_like(t)
    for s0, f, amp in ((0.0, 55, 1.0), (0.28, 66, 0.75)):
        tt = np.clip(t - s0, 0, None)
        x += (t >= s0) * amp * _chirp(f + 30 * np.exp(-tt / 0.02)) * _dec(tt, 0.06)
    return _fade(_band(x, None, 400), 0.001, 0.05)


def s_laser():
    t = _t(0.35)
    f = 3500 * (0.14 ** (t / 0.35))
    ph = TAU * np.cumsum(f) / SR
    x = (np.sin(ph) + np.sin(3 * ph) / 3 + np.sin(5 * ph) / 5) * _dec(t, 0.1)
    return _fade(x, 0.0008, 0.03)


def s_angin():
    d, r = 2.2, _rng("angin")
    lfo = _band(r.standard_normal(int(d * SR)), None, 1.5)
    lfo = (lfo - lfo.min()) / (np.ptp(lfo) + 1e-9)
    x = _noise_sweep(d, lambda v: 300 + 600 * float(lfo[min(len(lfo) - 1, int(v * (len(lfo) - 1)))]), 1.6, r)
    x += 0.15 * _noise_sweep(d, lambda v: 1400 + 500 * np.sin(v * 5), 0.15, _rng("angin", 1))
    u = np.linspace(0, 1, len(x))
    return _fade(x * _smooth_bump(u, 0.4), 0.05, 0.2)


def s_sonar():
    t = _t(1.3)
    ping = np.sin(TAU * 1500 * t) * _dec(t, 0.12)
    echo = np.zeros_like(t)
    s0 = int(0.38 * SR)
    echo[s0:] = 0.35 * ping[: len(t) - s0]
    return _fade(ping + echo, 0.002, 0.1)


def s_blip():
    t = _t(0.08)
    x = _chirp(1200 + 700 * t / 0.08) * _env(len(t), 0.002, 0.03, 1.0)
    return _fade(x, 0.001, 0.01)


def s_desis():
    d, r = 0.8, _rng("desis")
    u = np.linspace(0, 1, int(d * SR))
    x = _band(r.standard_normal(len(u)), 3000, 14000) * _smooth_bump(u, 0.25)
    return _fade(x, 0.01, 0.05)


def s_pukul():
    """pukulan kayu/stempel (untuk stempel & chip)."""
    t, r = _t(0.25), _rng("pukul")
    x = np.sin(TAU * 230 * t) * _dec(t, 0.03) + 0.6 * _band(r.standard_normal(len(t)), 400, 3000) * _dec(t, 0.012)
    return _fade(x, 0.0005, 0.03)


def s_kertas():
    """kertas/kartu bergeser (untuk kartu bab)."""
    d, r = 0.4, _rng("kertas")
    u = np.linspace(0, 1, int(d * SR))
    grit = (r.random(len(u)) > 0.7) * r.standard_normal(len(u))
    x = _band(r.standard_normal(len(u)) * 0.4 + grit, 1500, 9000) * _smooth_bump(u, 0.35)
    return _fade(x, 0.005, 0.04)


KATALOG = {
    "whoosh": s_whoosh, "swish": s_swish, "swish_up": s_swish_up, "pop": s_pop, "tick": s_tick,
    "click": s_click, "impact": s_impact, "thud": s_thud, "boom": s_boom, "riser": s_riser,
    "ding": s_ding, "glitch": s_glitch, "zap": s_zap, "door": s_door, "nging": s_nging,
    "retak": s_retak, "kecapi": s_kecapi, "kilau": s_kilau, "gelembung": s_gelembung, "gigit": s_gigit,
    "guntur": s_guntur, "detak": s_detak, "laser": s_laser, "angin": s_angin,
    "sonar": s_sonar, "blip": s_blip, "desis": s_desis, "pukul": s_pukul, "kertas": s_kertas,
}

# dB relatif per bunyi (penyeimbang telinga). Master menambahkan dasar SFX (-16 dB) + ducking.
LEVEL = {
    "whoosh": -4, "swish": -6, "swish_up": -6, "pop": -6, "tick": -12, "click": -12, "impact": -2,
    "thud": -4, "boom": -1, "riser": -7, "ding": -9, "glitch": -9, "zap": -9, "door": -6, "nging": -18,
    "retak": -6, "kecapi": -9, "kilau": -11, "gelembung": -8, "gigit": -6, "guntur": -2, "detak": -3,
    "laser": -9, "angin": -8, "sonar": -10, "blip": -12, "desis": -13, "pukul": -8, "kertas": -10,
}


def daftar():
    return sorted(KATALOG)


@lru_cache(maxsize=None)
def _render_cached(nama):
    x = KATALOG[nama]()
    x = np.nan_to_num(np.asarray(x, dtype=np.float64))
    return _norm(x, 0.9)


def render(nama) -> np.ndarray:
    if nama not in KATALOG:
        raise KeyError(f"SFX tidak dikenal: {nama}. Tersedia: {', '.join(daftar())}")
    return _render_cached(nama).copy()


def gain(nama, dasar_db=0.0):
    return 10 ** ((LEVEL.get(nama, -8) + dasar_db) / 20.0)


# ------------------------------------------------------------------------------------------ uji
def _uji():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from mesin_util import tulis_wav, ROOT
    out_dir = ROOT / "build" / "sfx"
    out_dir.mkdir(parents=True, exist_ok=True)
    ok = True
    parts = []
    print(f"{'bunyi':<11} {'dur':>5} {'puncak':>7} {'rms':>7}  status")
    for nama in daftar():
        a = KATALOG[nama]()
        b = KATALOG[nama]()
        x = render(nama)
        dur = len(x) / SR
        rms = 20 * np.log10(np.sqrt(np.mean(x.astype(np.float64) ** 2)) + 1e-12)
        pk = 20 * np.log10(np.abs(x).max() + 1e-12)
        err = []
        if not np.array_equal(np.asarray(a), np.asarray(b)):
            err.append("tidak deterministik")
        if not np.isfinite(x).all():
            err.append("NaN/inf")
        if not (0.03 <= dur <= 4.0):
            err.append("durasi")
        if rms < -40:
            err.append("terlalu senyap")
        if np.abs(x).max() > 1.0:
            err.append("clip")
        if abs(x[0]) > 0.05 or abs(x[-1]) > 0.02:
            err.append("klik di tepi")
        if nama not in LEVEL:
            err.append("LEVEL belum diisi")
        ok &= not err
        print(f"{nama:<11} {dur:5.2f} {pk:7.1f} {rms:7.1f}  {'OK' if not err else 'GAGAL: ' + ', '.join(err)}")
        tulis_wav(out_dir / f"{nama}.wav", x * gain(nama, 6), SR, bits=16)
        parts += [x * gain(nama, 6), np.zeros(int(0.35 * SR), np.float32)]
    tulis_wav(out_dir / "katalog.wav", np.concatenate(parts), SR, bits=16)
    print(f"\n{len(KATALOG)} bunyi -> {out_dir}/katalog.wav")
    print("SFX SELFTEST:", "LULUS" if ok else "GAGAL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(_uji())
