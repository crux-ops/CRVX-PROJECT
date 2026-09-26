#!/usr/bin/env python3
"""audio_util.py - pembantu audio bersama (baca/tulis WAV via ffmpeg, envelope, LUFS)."""
import json
import math
import os
import subprocess
import wave

import numpy as np

SR = 48000


def ffmpeg_exe():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def run(cmd, check=True):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if check and p.returncode != 0:
        raise RuntimeError("perintah gagal: %s\n%s" % (" ".join(cmd), p.stderr[-2000:]))
    return p


def read_audio(path, sr=SR, extra_af=None):
    """Baca audio apa pun -> float32 mono @ sr (lewat ffmpeg, agar format bebas)."""
    cmd = [ffmpeg_exe(), "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr)]
    if extra_af:
        cmd += ["-af", extra_af]
    cmd += ["-f", "f32le", "-"]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg gagal membaca %s: %s" % (path, p.stderr.decode()[-1000:]))
    return np.frombuffer(p.stdout, dtype=np.float32).copy()


def write_wav(path, x, sr=SR):
    x = np.clip(np.asarray(x, dtype=np.float32), -1, 1)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((x * 32767).astype("<i2").tobytes())


def db(x):
    return 20 * math.log10(max(float(x), 1e-9))


def envelope(x, hop_ms=10, sr=SR):
    """RMS per blok (dBFS)."""
    hop = int(sr * hop_ms / 1000)
    n = len(x) // hop
    if n == 0:
        return np.array([-120.0])
    blk = x[: n * hop].reshape(n, hop)
    rms = np.sqrt(np.mean(blk.astype(np.float64) ** 2, axis=1) + 1e-12)
    return 20 * np.log10(rms + 1e-9)


# ---------------------------------------------------------------- loudness (ITU-R BS.1770 sederhana, mono)

def _biquad(x, b, a):
    y = np.zeros_like(x, dtype=np.float64)
    x = x.astype(np.float64)
    x1 = x2 = y1 = y2 = 0.0
    b0, b1, b2 = b
    a0, a1, a2 = a
    for i in range(len(x)):
        xi = x[i]
        yi = (b0 * xi + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2) / a0
        x2, x1 = x1, xi
        y2, y1 = y1, yi
        y[i] = yi
    return y


def _k_weight(x, sr=SR):
    # tahap 1: shelf tinggi (+4 dB), tahap 2: high-pass 38 Hz  (koefisien BS.1770 di 48k)
    if sr != 48000:
        raise ValueError("K-weight dihitung untuk 48 kHz")
    b1 = (1.53512485958697, -2.69169618940638, 1.19839281085285)
    a1 = (1.0, -1.69065929318241, 0.73248077421585)
    b2 = (1.0, -2.0, 1.0)
    a2 = (1.0, -1.99004745483398, 0.99007225036621)
    # implementasi vektor (lfilter manual terlalu lambat untuk 3 menit -> pakai scipy-less trick: blok numba tidak ada,
    # jadi pakai fft-konvolusi respons impuls yang cukup panjang)
    imp = np.zeros(8192)
    imp[0] = 1.0
    h = _biquad(_biquad(imp, b1, a1), b2, a2)
    n = len(x) + len(h) - 1
    N = 1 << (n - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, N) * np.fft.rfft(h, N), N)[: len(x)]
    return y


def lufs(x, sr=SR):
    """Integrated loudness (mono, gating -70 LUFS absolut + relatif -10 LU)."""
    if len(x) < sr:
        return -70.0
    y = _k_weight(x, sr)
    blk = int(0.4 * sr)
    hop = int(0.1 * sr)
    n = (len(y) - blk) // hop + 1
    if n <= 0:
        return -70.0
    idx = np.arange(blk)[None, :] + hop * np.arange(n)[:, None]
    z = np.mean(y[idx] ** 2, axis=1)
    l = -0.691 + 10 * np.log10(z + 1e-12)
    m = l > -70
    if not m.any():
        return -70.0
    rel = -0.691 + 10 * np.log10(np.mean(z[m])) - 10
    m2 = l > rel
    if not m2.any():
        return -70.0
    return float(-0.691 + 10 * np.log10(np.mean(z[m2])))


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_json(p, d):
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def load_env(path):
    """Baca config.env (KEY=VAL, boleh beberapa per baris) -> dict; tidak menimpa env yang sudah ada."""
    d = {}
    if not os.path.exists(path):
        return d
    import shlex
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            for tok in shlex.split(line):
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    d[k.strip()] = v.strip()
    return d


def env_of(slug):
    base = os.path.join("episodes", slug)
    d = load_env(os.path.join(base, "config.env"))
    for k, v in d.items():
        os.environ.setdefault(k, v)
    return d
