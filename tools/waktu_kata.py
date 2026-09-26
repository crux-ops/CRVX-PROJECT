#!/usr/bin/env python3
"""tools/waktu_kata.py - waktu tiap kata VO per adegan (penyelarasan DP) -> fraksi durasi adegan.

BEAT di `mesin_v11_epNN.py` memakai fraksi durasi adegan, dan mesin_v11.events() mengubahnya jadi detik untuk
SFX + dorongan kamera. Supaya gambar muncul TEPAT saat katanya diucapkan, fraksi diambil dari penyelarasan kata
VO NYATA (`long/mesin_long.align`, sama seperti Long), bukan dikira-kira.

Pakai:
  python3 tools/waktu_kata.py <slug> [--long] [--kata kunci1,kunci2] [--json]
Butuh: `python3 process_audio.py <slug>` lalu `python3 build_timeline.py <slug>` (audio_proc/ + timeline.json).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mesin_util as mu
from long import mesin_long as L


def utama() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug")
    ap.add_argument("--long", action="store_true", help="episode video panjang (long/<slug>)")
    ap.add_argument("--kata", default="", help="daftar kata kunci (dipisah koma) untuk langsung dapat fraksinya")
    ap.add_argument("--json", action="store_true", help="keluaran JSON (kata, t0, fraksi)")
    a = ap.parse_args()

    ep_dir, content, cfg, bdir = mu.muat_episode(a.slug, "long" if a.long else "shorts")
    tlp = bdir / "timeline.json"
    if not tlp.exists():
        mu.gagal(f"timeline.json belum ada - jalankan dulu: process_audio.py {a.slug} && build_timeline.py {a.slug}")
    tl = json.loads(tlp.read_text(encoding="utf-8"))

    hasil = {}
    for sc, ts in zip(content["scenes"], tl["scenes"]):
        wav = bdir / "audio_proc" / f"{sc['id']}.wav"
        if not wav.exists():
            mu.gagal(f"VO hasil proses belum ada: {wav}")
        x = mu.baca_wav(wav)
        hasil[sc["id"]] = L.align(x, sc["vo"], mu.SR, offset=ts.get("lead_in", 0.6))

    kunci = [k.strip().lower() for k in a.kata.split(",") if k.strip()]
    if a.json:
        out = {}
        for sc, ts in zip(content["scenes"], tl["scenes"]):
            dur = ts["dur"]
            out[sc["id"]] = [{"kata": w["kata"], "t": round(w["t0"], 3), "fraksi": round(w["t0"] / dur, 4)}
                             for w in hasil[sc["id"]]]
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0

    for sc, ts in zip(content["scenes"], tl["scenes"]):
        dur = ts["dur"]
        kata = hasil[sc["id"]]
        print(f"\n== {sc['id']}  (dur {dur:.2f} s, {len(kata)} kata)")
        print("   " + "  ".join(f"{w['kata']}@{w['t0'] / dur:.3f}" for w in kata))
        for k in kunci:
            cocok = [w for w in kata if k in w["kata"].lower()]
            for w in cocok:
                print(f"   [{k}] '{w['kata']}' t={w['t0']:.2f}s fraksi={w['t0'] / dur:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(utama())
