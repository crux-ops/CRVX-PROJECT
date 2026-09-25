#!/usr/bin/env python3
"""build_audio.py - susun VO terjadwal jadi satu track (build/<slug>/vo_track.wav).

Tiap klip diletakkan tepat di start_adegan + lead_in (sampel-akurat), lalu seluruh track dinormalisasi
ke puncak -2.5 dBFS. QC: klip tidak boleh melewati batas adegannya (tidak tumpang tindih).

Pakai: python3 build_audio.py <slug> [--long]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mesin_util as mu  # noqa: E402

PUNCAK_TRACK = -2.5


def susun(slug, jenis="shorts"):
    ep, content, cfg, bdir = mu.muat_episode(slug, jenis)
    tl = json.loads((bdir / "timeline.json").read_text(encoding="utf-8"))
    sr = mu.SR
    n = int(round(tl["total"] * sr))
    track = np.zeros(n, dtype=np.float32)
    for s in tl["scenes"]:
        clip = mu.baca_wav(bdir / "audio_proc" / f"{s['id']}.wav")
        i0 = int(round(s["vo_start"] * sr))
        batas = int(round((s["start"] + s["dur"]) * sr))
        if i0 + len(clip) > batas:
            mu.gagal(f"klip {s['id']} melewati batas adegan ({(i0 + len(clip) - batas) / sr:.3f} s)")
        track[i0:i0 + len(clip)] += clip
    pk = float(np.abs(track).max())
    track *= 10 ** (PUNCAK_TRACK / 20) / max(pk, 1e-9)
    mu.tulis_wav(bdir / "vo_track.wav", track, sr)
    print(f"build_audio: {len(tl['scenes'])} klip -> vo_track.wav ({n / sr:.2f} s, puncak {PUNCAK_TRACK} dBFS)")
    return track


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    susun(sys.argv[1], "long" if "--long" in sys.argv else "shorts")
