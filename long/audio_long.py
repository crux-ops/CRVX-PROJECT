#!/usr/bin/env python3
"""long/audio_long.py - master audio video panjang.

VO (vo_track) -> -14 LUFS + limiter puncak -1.2 (true-peak) -> stem audio_master_vo.wav
SFX dari BEATS terkunci ke KATA (visual.py) + transisi/kartu bab -> duck saat VO bicara -> tambah di atas
-> limiter puncak -1.2 -> audio_master.wav (+ events.json).
QC "VO tidak turun": limiter akhir tidak boleh menekan VO > 0.5 dB (rms bagian bicara).

Pakai: python3 long/audio_long.py --slug <folder>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "long"))
import master_audio as MA  # noqa: E402
import mesin_long as L  # noqa: E402
import mesin_util as mu  # noqa: E402

SR = mu.SR


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    a = ap.parse_args()
    ep, content, cfg, bdir = mu.muat_episode(a.slug, "long")
    tl = json.loads((bdir / "timeline.json").read_text(encoding="utf-8"))
    words = json.loads((bdir / "align.json").read_text(encoding="utf-8"))
    vis = L.muat_visual(ep)
    target, ceil_db = cfg.f("LUFS", -14.0), cfg.f("PUNCAK", -1.2)
    vo = mu.baca_wav(bdir / "vo_track.wav")
    vo_m, lufs_vo, gr_vo = MA.normalisasi_lufs(vo, target, ceil_db)
    mu.tulis_wav(bdir / "audio_master_vo.wav", vo_m)
    ev = L.events_long(content, tl, words, getattr(vis, "BEATS", []))
    mu.tulis_json(bdir / "events.json", {"sumber": "long", "events": ev})
    bus = MA.lapisan_sfx(ev, len(vo_m), cfg.f("SFX_DASAR", -16.0)) * MA.amplop_duck(vo_m, cfg.f("SFX_DUCK", -7.0))
    pre = vo_m + bus
    mix, gr = mu.limiter_puncak(pre, SR, ceil_db)
    mu.tulis_wav(bdir / "audio_master.wav", mix)
    lufs, tp = mu.ukur_lufs(mix)
    aktif = mu.env_db(vo_m, SR, 0.010) > -40
    n = int(0.010 * SR)

    def rms(x):
        y = np.zeros(len(aktif) * n, np.float32)
        y[:len(x)] = x[:len(y)]
        return float(10 * np.log10(np.mean(y.reshape(-1, n)[aktif].astype(np.float64) ** 2) + 1e-12))

    turun = rms(pre) - rms(mix)
    pk = float(mu.db(np.abs(mix).max()))
    print(f"audio_long: VO {lufs_vo:.1f} LUFS | {len(ev)} SFX | hasil {lufs:.2f} LUFS, puncak {pk:.2f} dBFS, "
          f"true-peak {tp:.2f}, limiter akhir {gr:.2f} dB, VO turun {turun:.2f} dB")
    gagal = []
    if abs(lufs - target) > 1.0:
        gagal.append("loudness")
    if pk > ceil_db + 0.05:
        gagal.append("puncak")
    if turun > 0.5:
        gagal.append("VO turun")
    if gagal:
        mu.gagal("QC audio_long: " + ", ".join(gagal), 6)
    print("AUDIO LONG: LULUS (VO tidak turun)")


if __name__ == "__main__":
    main()
