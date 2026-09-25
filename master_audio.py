#!/usr/bin/env python3
"""master_audio.py - master -14 LUFS + lapisan SFX (ducking) + limiter puncak.

Urutan:
  1. vo_track -> gain ke LUFS target (-14, YouTube) -> limiter PUNCAK -1.2 dBFS (iterasi sampai +-0.2 LU)
     -> stem build/<slug>/audio_master_vo.wav
  2. lapisan SFX dari events (satu sumber kebenaran: mesin_v11.events -> juga dipakai render):
     dasar SFX_DASAR (-16 dB) + LEVEL per bunyi, ducking SFX_DUCK (-7 dB) saat VO bicara (amplop sidechain
     dari stem VO, attack 40 ms / release 350 ms). VO TIDAK pernah diturunkan.
  3. VO + SFX -> limiter puncak saja -> build/<slug>/audio_master.wav (+ events.json)
QC: loudness -14 +-1 LU | puncak <= -1.2 dBFS | "VO tidak turun" (limiter akhir tidak menekan VO > 0.5 dB).

Pakai: python3 master_audio.py <slug> [--long]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mesin_util as mu  # noqa: E402
import sfx  # noqa: E402

SR = mu.SR


def normalisasi_lufs(x, target=-14.0, ceiling=-1.2, iterasi=5):
    """Gain ke LUFS target + limiter puncak. -> (y, lufs, reduksi_limiter_dB)."""
    lufs, _ = mu.ukur_lufs(x)
    g = target - lufs
    y, gr = x, 0.0
    for _ in range(iterasi):
        y, gr = mu.limiter_puncak(x * 10 ** (g / 20), SR, ceiling)
        lufs, _ = mu.ukur_lufs(y)
        if abs(lufs - target) <= 0.2:
            break
        g += target - lufs
    return y, lufs, gr


def amplop_duck(vo, duck_db=-7.0, thr_db=-45.0, att=0.040, rel=0.350, frame=0.010):
    """Gain linear untuk bus SFX: turun duck_db saat VO aktif (amplop sidechain yang dihaluskan)."""
    e = mu.env_db(vo, SR, frame)
    target = np.where(e > thr_db, duck_db, 0.0)
    a, r = np.exp(-frame / att), np.exp(-frame / rel)
    sm = np.zeros_like(target)
    g = 0.0
    for i, v in enumerate(target):
        c = a if v < g else r  # menuju lebih rendah = attack
        g = c * g + (1 - c) * v
        sm[i] = g
    n = int(round(frame * SR))
    tc = (np.arange(len(sm)) + 0.5) * n
    return (10 ** (np.interp(np.arange(len(vo)), tc, sm) / 20)).astype(np.float32)


def lapisan_sfx(events, n, dasar_db=-16.0):
    """Bus SFX (belum di-duck). events: list dict {t, sfx, gain_db?}."""
    bus = np.zeros(n, dtype=np.float32)
    for ev in events:
        x = sfx.render(ev["sfx"]) * sfx.gain(ev["sfx"], dasar_db + float(ev.get("gain_db", 0.0)))
        i0 = int(round(float(ev["t"]) * SR))
        if i0 < 0:
            x, i0 = x[-i0:], 0
        m = min(len(x), n - i0)
        if m > 0:
            bus[i0:i0 + m] += x[:m]
    return bus


def events_dasar(content, timeline):
    """Cadangan bila mesin_v11 belum tersedia: whoosh di tiap pergantian adegan + pop saat judul muncul."""
    ev = []
    for k, s in enumerate(timeline["scenes"]):
        if k > 0:
            ev.append({"t": s["start"] - 0.12, "sfx": "whoosh", "scene": s["id"], "sumber": "transisi"})
        ev.append({"t": s["start"] + 0.25, "sfx": "pop", "scene": s["id"], "sumber": "judul"})
    return ev


def ambil_events(content, timeline):
    try:
        import mesin_v11
        return mesin_v11.events(content, timeline), "mesin_v11"
    except ImportError:
        return events_dasar(content, timeline), "dasar"


def master(slug, jenis="shorts"):
    ep, content, cfg, bdir = mu.muat_episode(slug, jenis)
    tl = json.loads((bdir / "timeline.json").read_text(encoding="utf-8"))
    target, ceil_db = cfg.f("LUFS", -14.0), cfg.f("PUNCAK", -1.2)
    dasar, duck = cfg.f("SFX_DASAR", -16.0), cfg.f("SFX_DUCK", -7.0)
    vo = mu.baca_wav(bdir / "vo_track.wav")
    vo_m, lufs_vo, gr_vo = normalisasi_lufs(vo, target, ceil_db)
    mu.tulis_wav(bdir / "audio_master_vo.wav", vo_m)
    events, sumber = ambil_events(content, tl)
    mu.tulis_json(bdir / "events.json", {"sumber": sumber, "events": events})
    bus = lapisan_sfx(events, len(vo_m), dasar) * amplop_duck(vo_m, duck)
    pre = vo_m + bus
    mix, gr = mu.limiter_puncak(pre, SR, ceil_db)
    mu.tulis_wav(bdir / "audio_master.wav", mix)
    # ---- QC
    lufs, tp = mu.ukur_lufs(mix)
    pk = float(mu.db(np.abs(mix).max()))
    aktif = mu.env_db(vo_m, SR, 0.010) > -40
    n = int(0.010 * SR)
    m = len(aktif) * n

    def rms_aktif(x):
        y = np.zeros(m, np.float32)
        y[:len(x)] = x[:m]
        fr = y.reshape(-1, n)[aktif]
        return float(10 * np.log10(np.mean(fr.astype(np.float64) ** 2) + 1e-12))

    turun = rms_aktif(pre) - rms_aktif(mix)
    kor = float(np.corrcoef(vo_m, mix)[0, 1])
    print(f"master_audio: VO {lufs_vo:.1f} LUFS (limiter VO {gr_vo:.2f} dB) | {len(events)} SFX ({sumber}) "
          f"dasar {dasar} dB duck {duck} dB")
    print(f"  hasil: {lufs:.2f} LUFS, puncak {pk:.2f} dBFS, true-peak {tp:.2f} dBTP, limiter akhir {gr:.2f} dB, "
          f"VO turun {turun:.2f} dB, korelasi VO~mix {kor:.3f}")
    gagal = []
    if abs(lufs - target) > 1.0:
        gagal.append(f"loudness {lufs:.2f} (target {target})")
    if pk > ceil_db + 0.05:
        gagal.append(f"puncak {pk:.2f} > {ceil_db}")
    if turun > 0.5:
        gagal.append(f"VO turun {turun:.2f} dB oleh limiter akhir")
    mu.tulis_json(bdir / "qc_master.json", {"lufs": lufs, "true_peak": tp, "puncak": pk, "limiter_akhir_db": gr,
                                            "vo_turun_db": turun, "korelasi_vo": kor, "n_sfx": len(events),
                                            "gagal": gagal})
    if gagal:
        mu.gagal("QC master: " + "; ".join(gagal), 6)
    print("MASTER AUDIO: LULUS")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    master(sys.argv[1], "long" if "--long" in sys.argv else "shorts")
