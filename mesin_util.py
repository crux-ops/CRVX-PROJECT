#!/usr/bin/env python3
"""mesin_util.py - utilitas bersama mesin KlikTahu.

Isi:
  * konfigurasi & path episode   : muat_episode(), baca_config(), konfig()
  * audio I/O & ukur              : ffmpeg_exe(), baca_wav(), tulis_wav(), ukur_lufs(), env_db()
  * pratinjau & audit visual      : preview_times(), ink_report(), sheet()

Hanya numpy + PIL + imageio-ffmpeg. Semua deterministik.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
FONTS = ROOT / "fonts"
SR = 48000  # sample rate kerja semua audio

# --------------------------------------------------------------------------------------------
# Konfigurasi
# --------------------------------------------------------------------------------------------
DEFAULT_SHORTS = {
    "FPS": "60", "SS": "1.5", "SHARPEN": "52",
    "SPEED": "1.09", "TARGET_WPS": "1.90", "MAXDUR": "178",
    "ATEMPO_MIN": "0.88", "ATEMPO_MAX": "1.08",
    "VBITRATE": "6400k", "MAXRATE": "11000k", "BUFSIZE": "16000k",
    "PRESET": "slow", "TUNE": "animation", "ABITRATE": "256k",
    "JOBS": "4", "CAPTION": "0",
}
DEFAULT_LONG = {
    "FPS": "30", "SS": "1.25", "SHARPEN": "40",
    "SPEED": "1.09", "TARGET_WPS": "1.90", "MAXDUR": "3600",
    "ATEMPO_MIN": "0.88", "ATEMPO_MAX": "1.08",
    "VBITRATE": "9000k", "MAXRATE": "14000k", "BUFSIZE": "20000k",
    "PRESET": "slow", "TUNE": "animation", "ABITRATE": "256k",
    "JOBS": "4", "CAPTION": "0",
}
# kunci yang boleh ditimpa lewat environment (env menang atas config.env)
ENV_KEYS = set(DEFAULT_SHORTS) | {"SIL_DB", "PAD_AWAL", "PAD_AKHIR", "REDAM_NAPAS", "KT_FX", "KT_BLOOM",
                                  "SFX_DASAR", "SFX_DUCK", "LUFS", "PUNCAK"}


def baca_config(path) -> dict:
    """Parser config.env: boleh beberapa KEY=VAL per baris, tanda kutip, komentar #."""
    d = {}
    p = Path(path)
    if not p.exists():
        return d
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for tok in shlex.split(line, comments=True):
            if "=" in tok:
                k, v = tok.split("=", 1)
                d[k.strip()] = v.strip()
    return d


class Cfg(dict):
    """dict dengan akses bertipe: cfg.f('SS'), cfg.i('FPS'), cfg.s('OUT_NAME')."""

    def f(self, k, d=0.0):
        try:
            return float(self.get(k, d))
        except (TypeError, ValueError):
            return float(d)

    def i(self, k, d=0):
        try:
            return int(float(self.get(k, d)))
        except (TypeError, ValueError):
            return int(d)

    def s(self, k, d=""):
        return str(self.get(k, d))

    def b(self, k, d=False):
        v = str(self.get(k, "1" if d else "0")).strip().lower()
        return v in ("1", "true", "ya", "yes", "on")


def konfig(ep_dir, jenis="shorts") -> Cfg:
    base = dict(DEFAULT_LONG if jenis == "long" else DEFAULT_SHORTS)
    base.update(baca_config(Path(ep_dir) / "config.env"))
    for k in ENV_KEYS:
        if k in os.environ and os.environ[k] != "":
            base[k] = os.environ[k]
    return Cfg(base)


def muat_episode(slug_or_path, jenis="shorts"):
    """-> (ep_dir, content, cfg, build_dir). slug dicari di episodes/ (shorts) atau long/ (long)."""
    p = Path(slug_or_path)
    if not p.exists():
        p = ROOT / ("long" if jenis == "long" else "episodes") / str(slug_or_path)
    if not (p / "content.json").exists():
        raise SystemExit(f"[mesin_util] content.json tidak ditemukan di {p}")
    content = json.loads((p / "content.json").read_text(encoding="utf-8"))
    cfg = konfig(p, jenis)
    slug = cfg.s("EPISODE_SLUG") or p.name
    bdir = ROOT / "build" / ("long" if jenis == "long" else "") / slug
    bdir = Path(os.path.normpath(bdir))
    bdir.mkdir(parents=True, exist_ok=True)
    return p, content, cfg, bdir


def hitung_kata(teks: str) -> int:
    """Jumlah kata yang diucapkan (token berisi huruf/angka)."""
    return len([w for w in re.split(r"\s+", teks.strip()) if re.search(r"[0-9A-Za-zÀ-ÿ]", w)])


# --------------------------------------------------------------------------------------------
# Audio
# --------------------------------------------------------------------------------------------
def ffmpeg_exe() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _baca_wav_cepat(path, sr):
    """Pembaca RIFF cepat untuk PCM16/float32 mono/stereo pada sr yang diminta; None bila tidak cocok."""
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return None
    pos, fmt, raw = 12, None, None
    while pos + 8 <= len(data):
        cid, size = data[pos:pos + 4], struct.unpack("<I", data[pos + 4:pos + 8])[0]
        body = data[pos + 8:pos + 8 + size]
        if cid == b"fmt ":
            fmt = struct.unpack("<HHIIHH", body[:16])
        elif cid == b"data":
            raw = body
        pos += 8 + size + (size & 1)
    if fmt is None or raw is None:
        return None
    tag, ch, rate, _, _, bits = fmt
    if rate != sr:
        return None
    if tag == 1 and bits == 16:
        x = np.frombuffer(raw[: len(raw) // 2 * 2], dtype="<i2").astype(np.float32) / 32768.0
    elif tag == 3 and bits == 32:
        x = np.frombuffer(raw[: len(raw) // 4 * 4], dtype="<f4").astype(np.float32)
    else:
        return None
    if ch > 1:
        x = x[: len(x) // ch * ch].reshape(-1, ch).mean(axis=1)
    return x


def baca_wav(path, sr=SR) -> np.ndarray:
    """Baca audio apa pun -> float32 mono pada sr (resample via ffmpeg bila perlu)."""
    x = _baca_wav_cepat(path, sr)
    if x is not None:
        return x.copy()
    cmd = [ffmpeg_exe(), "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"]
    out = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(out, dtype="<f4").astype(np.float32).copy()


def tulis_wav(path, x, sr=SR, bits=32):
    """Tulis WAV mono/stereo. bits=32 -> float32 (antara), bits=16 -> PCM16."""
    x = np.asarray(x, dtype=np.float32)
    ch = 1 if x.ndim == 1 else x.shape[1]
    if bits == 16:
        payload = (np.clip(x, -1.0, 1.0) * 32767.0).round().astype("<i2").tobytes()
        tag, bps = 1, 2
    else:
        payload = x.astype("<f4").tobytes()
        tag, bps = 3, 4
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(b"RIFF" + struct.pack("<I", 36 + len(payload)) + b"WAVE")
        fh.write(b"fmt " + struct.pack("<IHHIIHH", 16, tag, ch, sr, sr * ch * bps, ch * bps, bps * 8))
        fh.write(b"data" + struct.pack("<I", len(payload)) + payload)


def db(x):
    return 20.0 * np.log10(np.maximum(np.abs(x), 1e-9))


def env_db(x, sr=SR, frame=0.010, mode="rms"):
    """Envelope per-frame (dBFS). mode rms atau peak. Panjang = ceil(len/frame)."""
    n = max(1, int(round(frame * sr)))
    m = int(np.ceil(len(x) / n))
    pad = np.zeros(m * n, dtype=np.float32)
    pad[: len(x)] = x
    fr = pad.reshape(m, n)
    if mode == "peak":
        v = np.abs(fr).max(axis=1)
    else:
        v = np.sqrt((fr.astype(np.float64) ** 2).mean(axis=1))
    return db(v)


def ukur_lufs(x_or_path, sr=SR):
    """Loudness terintegrasi (LUFS) + true-peak (dBTP) via ffmpeg ebur128 (implementasi referensi)."""
    tmp = None
    path = x_or_path
    if not isinstance(x_or_path, (str, Path)):
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        tulis_wav(tmp.name, x_or_path, sr)
        path = tmp.name
    try:
        cmd = [ffmpeg_exe(), "-nostats", "-hide_banner", "-i", str(path),
               "-filter_complex", "ebur128=peak=true", "-f", "null", "-"]
        err = subprocess.run(cmd, capture_output=True, text=True).stderr
        summ = err[err.rfind("Summary:"):]
        mi = re.search(r"I:\s+(-?[\d.]+|-inf)\s+LUFS", summ)
        mp = re.search(r"Peak:\s+(-?[\d.]+|-inf)\s+dBFS", summ)
        lufs = float(mi.group(1)) if mi and mi.group(1) != "-inf" else -70.0
        tp = float(mp.group(1)) if mp and mp.group(1) != "-inf" else -120.0
        return lufs, tp
    finally:
        if tmp:
            os.unlink(tmp.name)


def sliding_min(x, w):
    """Minimum geser terpusat (jendela 2w+1) O(n) - algoritma van Herk/Gil-Werman, tervektor."""
    if w <= 0:
        return x.copy()
    k = 2 * w + 1
    n = len(x)
    padded = np.concatenate([np.full(w, np.inf, x.dtype), x, np.full(w + k, np.inf, x.dtype)])
    m = int(np.ceil(len(padded) / k))
    buf = np.full(m * k, np.inf, dtype=x.dtype)
    buf[: len(padded)] = padded
    blk = buf.reshape(m, k)
    pre = np.minimum.accumulate(blk, axis=1).ravel()
    suf = np.minimum.accumulate(blk[:, ::-1], axis=1)[:, ::-1].ravel()
    idx = np.arange(n)
    return np.minimum(suf[idx], pre[idx + k - 1])


def moving_avg(x, w):
    """Rata-rata geser terpusat jendela 2w+1 (cumsum)."""
    if w <= 0:
        return x.copy()
    k = 2 * w + 1
    c = np.cumsum(np.concatenate([np.full(w, x[0]), x, np.full(w, x[-1])]).astype(np.float64))
    c = np.concatenate([[0.0], c])
    return ((c[k:] - c[:-k]) / k).astype(np.float32)


def puncak_antar_sampel(x, L=4, K=16):
    """Amplop |x| termasuk puncak ANTAR sampel (true-peak, interpolasi sinc berjendela L kali).
    Nilai di n = maks(|x[n]|, |x(n + p/L)| untuk p=1..L-1)."""
    x = np.asarray(x, dtype=np.float32)
    a = np.abs(x)
    k = np.arange(-K // 2 + 1, K // 2 + 1)
    xp = np.concatenate([np.zeros(K, np.float32), x, np.zeros(K, np.float32)])
    for p in range(1, L):
        t = k - p / L
        h = np.sinc(t) * (0.5 + 0.5 * np.cos(np.pi * t / (K / 2 + 1)))
        h = (h / h.sum()).astype(np.float32)
        # y[n] = sum_j x[n + k_j] h_j
        c = np.correlate(xp, h, mode="valid")
        y = c[K + k[0]: K + k[0] + len(x)]
        np.maximum(a, np.abs(y), out=a)
    return a


def limiter_puncak(x, sr=SR, ceiling_db=-1.2, look=0.004, release=0.060, true_peak=True):
    """Limiter PUNCAK saja (tanpa gate/expander): gain hanya turun di sekitar sampel yang melewati ceiling.
    true_peak=True: puncak antar-sampel (interpolasi 4x) ikut dijaga -> aman setelah encode AAC.
    Tanpa overshoot: g = rata2_geser(min_geser(butuh, w), w) selalu <= butuh (setiap jendela rata-rata
    memuat titik n itu sendiri). Tahap rilis kedua (lebih lebar) juga <= tahap pertama.
    -> (y, reduksi_maks_dB)."""
    x = np.asarray(x, dtype=np.float32)
    c = 10 ** (ceiling_db / 20.0)
    amp = puncak_antar_sampel(x) if true_peak else np.abs(x)
    need = np.minimum(1.0, c / np.maximum(amp, 1e-9)).astype(np.float32)
    if need.min() >= 1.0:
        return x.copy(), 0.0
    w = max(1, int(look * sr))
    g = moving_avg(sliding_min(need, w), w)
    wr = int(release * sr / 2)
    if wr > w:
        g = moving_avg(sliding_min(g, wr), wr)
    y = (x * g).astype(np.float32)
    np.clip(y, -c, c, out=y)  # pengaman pembulatan numerik (sangat kecil)
    return y, float(-db(g.min()))


# --------------------------------------------------------------------------------------------
# Pratinjau & audit visual (dipakai render.py, check_layout.py, qc_mp4.py)
# --------------------------------------------------------------------------------------------
def preview_times(timeline: dict, n: int = 10):
    """Waktu frame kunci untuk montase: per adegan ambil titik 'isi penuh' (60-70% durasi) + awal
    visual (lead_in+0.9). Hasil n waktu (detik) + label."""
    out = []
    scenes = timeline["scenes"]
    for sc in scenes:
        a, d = sc["start"], sc["dur"]
        out.append((a + min(d * 0.35, sc.get("lead_in", 0.6) + 1.2), f"{sc['id']} awal"))
        out.append((a + d * 0.72, f"{sc['id']} isi"))
    if len(out) > n:
        # sisakan 'isi' setiap adegan dulu, lalu 'awal' sebanyak sisa kuota
        isi = [o for o in out if o[1].endswith("isi")]
        awal = [o for o in out if o[1].endswith("awal")]
        step = max(1, int(np.ceil(len(awal) / max(1, n - len(isi)))))
        out = sorted(isi + awal[::step], key=lambda o: o[0])[:n]
    return out


def ink_report(img, bg_rgb, zones, thr=38, min_px=60):
    """Ukur 'tinta' (piksel yang beda jelas dari latar) di zona terlarang.
    img: PIL RGB. zones: list (nama, x0, y0, x1, y1). bg_rgb: warna latar atau array latar (HxWx3).
    -> list dict {zona, px, bbox}. Zona bersih bila px < min_px."""
    a = np.asarray(img.convert("RGB"), dtype=np.int16)
    if isinstance(bg_rgb, np.ndarray):
        bg = bg_rgb.astype(np.int16)
    else:
        bg = np.array(bg_rgb, dtype=np.int16)[None, None, :]
    diff = np.abs(a - bg).max(axis=2) > thr
    rep = []
    for nama, x0, y0, x1, y1 in zones:
        sub = diff[int(y0):int(y1), int(x0):int(x1)]
        px = int(sub.sum())
        bbox = None
        if px:
            ys, xs = np.nonzero(sub)
            bbox = (int(xs.min() + x0), int(ys.min() + y0), int(xs.max() + x0), int(ys.max() + y0))
        rep.append({"zona": nama, "px": px, "bbox": bbox, "bersih": px < min_px})
    return rep


def sheet(images, labels, cols=4, lebar=360, judul=None, path=None):
    """Montase berlabel. images: list PIL. Hasil PIL (dan disimpan bila path)."""
    from PIL import Image, ImageDraw, ImageFont
    if not images:
        raise ValueError("sheet: tidak ada gambar")
    w0, h0 = images[0].size
    th = int(lebar * h0 / w0)
    rows = int(np.ceil(len(images) / cols))
    pad, lab = 12, 34
    top = 56 if judul else 0
    W = cols * lebar + (cols + 1) * pad
    H = top + rows * (th + lab) + (rows + 1) * pad
    out = Image.new("RGB", (W, H), (30, 30, 36))
    d = ImageDraw.Draw(out)
    try:
        f = ImageFont.truetype(str(FONTS / "Poppins-SemiBold.ttf"), 20)
        fj = ImageFont.truetype(str(FONTS / "Poppins-Bold.ttf"), 28)
    except OSError:
        f = fj = ImageFont.load_default()
    if judul:
        d.text((pad, 12), judul, font=fj, fill=(240, 240, 240))
    for i, (im, lb) in enumerate(zip(images, labels)):
        r, c = divmod(i, cols)
        x = pad + c * (lebar + pad)
        y = top + pad + r * (th + lab + pad)
        out.paste(im.convert("RGB").resize((lebar, th), Image.LANCZOS), (x, y))
        d.text((x + 2, y + th + 4), str(lb)[:40], font=f, fill=(230, 230, 230))
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        if str(path).lower().endswith((".jpg", ".jpeg")):
            out.save(path, quality=88)
        else:
            out.save(path)
    return out


def tulis_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def gagal(msg, code=1):
    print(f"[GAGAL] {msg}", file=sys.stderr)
    raise SystemExit(code)
