#!/usr/bin/env python3
"""master_audio.py <slug> - master VO ke -14 LUFS (puncak -1.2 dBFS), lalu lapisan SFX dari events BEATS.
SFX: dasar -16 dB, ducking -7 dB saat VO bicara (sidechain envelope VO), limiter puncak saja (tanpa gate).
Keluaran: build/audio_master.wav (VO+SFX), build/audio_master_vo.wav (stem VO), build/events.json
"""
import os
import sys

import numpy as np

import sfx
from audio_util import SR, db, env_of, envelope, load_json, lufs, read_audio, save_json, write_wav

TARGET_LUFS = -14.0
PEAK_DB = -1.2
SFX_BASE_DB = -16.0
DUCK_DB = -7.0


def limiter(x, peak_db=PEAK_DB, look_ms=3, rel=0.08):
    """Limiter puncak dengan lookahead: hanya menurunkan gain saat melewati ambang."""
    thr = 10 ** (peak_db / 20)
    hop = int(SR * look_ms / 1000)
    n = len(x) // hop + 1
    pad = np.zeros(n * hop, dtype=np.float32)
    pad[: len(x)] = x
    pk = np.abs(pad).reshape(n, hop).max(axis=1)
    need = np.minimum(1.0, thr / np.maximum(pk, 1e-9))
    # gain harus turun sebelum puncak (lookahead 1 blok) dan pulih perlahan
    g = np.ones(n)
    a = np.exp(-hop / (SR * rel))
    cur = 1.0
    for i in range(n - 1, -1, -1):
        # jalan mundur untuk lookahead: gain blok i = min(need[i], need[i+1])
        tgt = min(need[i], need[i + 1] if i + 1 < n else 1.0)
        g[i] = tgt
    out = np.ones(n)
    for i in range(n):
        cur = g[i] if g[i] < cur else a * cur + (1 - a) * g[i]
        out[i] = cur
    gi = np.interp(np.arange(len(x)) / hop, np.arange(n), out)
    return (x * gi).astype(np.float32)


def duck_curve(vo, att=0.02, rel=0.25):
    """Gain SFX: 1 saat hening, 10^(DUCK/20) saat VO bicara; halus."""
    hop = int(SR * 0.01)
    env = envelope(vo, 10)
    talk = env > -45
    g_t = np.where(talk, 10 ** (DUCK_DB / 20), 1.0)
    a_att = np.exp(-0.01 / att)
    a_rel = np.exp(-0.01 / rel)
    out = np.zeros(len(g_t))
    cur = 1.0
    for i, v in enumerate(g_t):
        cur = a_att * cur + (1 - a_att) * v if v < cur else a_rel * cur + (1 - a_rel) * v
        out[i] = cur
    return np.interp(np.arange(len(vo)) / hop, np.arange(len(out)), out).astype(np.float32)


def main(slug):
    env_of(slug)
    base = os.path.join("episodes", slug)
    build = os.path.join(base, "build")
    content = load_json(os.path.join(base, "content.json"))
    tl = load_json(os.path.join(base, "timeline.json"))
    vo = read_audio(os.path.join(build, "audio_vo.wav"))
    L0 = lufs(vo)
    vo = vo * 10 ** ((TARGET_LUFS - L0) / 20)
    vo = limiter(vo)
    L1 = lufs(vo)
    print("VO: %.1f LUFS -> %.1f LUFS, puncak %.2f dBFS" % (L0, L1, db(np.max(np.abs(vo)))))
    write_wav(os.path.join(build, "audio_master_vo.wav"), vo)

    import mesin_v11
    evs = mesin_v11.events(content, tl)
    save_json(os.path.join(build, "events.json"), [dict(t=round(t, 3), sfx=n) for t, n in evs])
    bed = np.zeros(len(vo), dtype=np.float32)
    for t, name in evs:
        x = sfx.get(name) * 10 ** ((SFX_BASE_DB + sfx.LEVEL.get(name, 0)) / 20)
        a = int(t * SR)
        if a >= len(bed):
            continue
        b = min(len(bed), a + len(x))
        bed[a:b] += x[: b - a]
    bed *= duck_curve(vo)
    mix = limiter(vo + bed)
    write_wav(os.path.join(build, "audio_master.wav"), mix)
    # QC: VO tidak turun (korelasi mix vs stem tinggi), puncak
    c = float(np.corrcoef(mix, vo)[0, 1])
    print("SFX events: %d | mix %.1f LUFS, puncak %.2f dBFS, korelasi VO %.3f" % (
        len(evs), lufs(mix), db(np.max(np.abs(mix))), c))
    if c < 0.95:
        print("GAGAL: VO tertutup SFX (korelasi < 0.95)")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
