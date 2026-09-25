#!/usr/bin/env python3
"""build_timeline.py - timeline.json dari durasi VO + ekor per tipe adegan.

dur_adegan = lead_in + durasi_VO + tail_<tipe>, dibulatkan KE ATAS ke kelipatan frame (1/FPS),
sehingga jumlah frame video = jumlah sampel audio / (SR/FPS) persis.

QC:
  * total > MAXDUR                               -> exit 2
  * "jeda sempit": hening setelah bicara (tail + hening akhir klip) harus >= lead_in + 0.3 s,
    supaya fase keluar transisi jatuh di hening dan penonton sempat bernapas  -> exit 5
    (bisa dilewati sadar dengan JEDA_SEMPIT_OK=1)

Pakai: python3 build_timeline.py <slug>      -> build/<slug>/timeline.json
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mesin_util as mu  # noqa: E402

JEDA_MARGIN = 0.30


def durasi_wav(path):
    return len(mu.baca_wav(path)) / mu.SR


def bangun(slug, jenis="shorts"):
    ep, content, cfg, bdir = mu.muat_episode(slug, jenis)
    fps = cfg.i("FPS", 60)
    maxdur = cfg.f("MAXDUR", 178)
    lead = float(content.get("lead_in", 0.6))
    info_p = bdir / "audio_proc" / "info.json"
    info = json.loads(info_p.read_text(encoding="utf-8")) if info_p.exists() else {}
    t_frame = 0
    scenes, masalah = [], []
    for sc in content["scenes"]:
        sid, tipe = sc["id"], sc.get("type", "fact")
        wav = bdir / "audio_proc" / f"{sid}.wav"
        if not wav.exists():
            mu.gagal(f"{wav} belum ada - jalankan process_audio.py dulu")
        vo = durasi_wav(wav)
        tail = float(content.get(f"tail_{tipe}", content.get("tail_fact", 0.9)))
        if "tail" in sc:
            tail = float(sc["tail"])
        nfr = int(math.ceil((lead + vo + tail) * fps - 1e-6))
        start = t_frame / fps
        dur = nfr / fps
        hen = float(info.get(sid, {}).get("hening_akhir_s", 0.25))
        jeda = (dur - lead - vo) + hen
        if jeda < lead + JEDA_MARGIN - 1e-6:
            masalah.append(f"{sid}: jeda setelah bicara {jeda:.2f}s < lead_in+0.3 ({lead + JEDA_MARGIN:.2f}s)")
        scenes.append({
            "id": sid, "type": tipe, "start": round(start, 6), "dur": round(dur, 6),
            "frames": [t_frame, t_frame + nfr], "lead_in": lead,
            "vo_start": round(start + lead, 6), "vo_dur": round(vo, 4),
            "bicara_akhir": round(start + lead + vo - hen, 4), "jeda_setelah": round(jeda, 3),
        })
        t_frame += nfr
    total = t_frame / fps
    tl = {"slug": cfg.s("EPISODE_SLUG") or ep.name, "jenis": jenis, "fps": fps, "sr": mu.SR,
          "total": round(total, 6), "frames": t_frame, "lead_in": lead, "maxdur": maxdur, "scenes": scenes}
    mu.tulis_json(bdir / "timeline.json", tl)
    print(f"build_timeline: {len(scenes)} adegan, total {total:.2f} s ({t_frame} frame @ {fps} fps), "
          f"MAXDUR {maxdur:.0f} s")
    for s in scenes:
        print(f"  {s['id']:<10} {s['type']:<6} start {s['start']:7.2f}  dur {s['dur']:6.2f}  vo {s['vo_dur']:5.2f}"
              f"  jeda {s['jeda_setelah']:.2f}")
    if total > maxdur:
        mu.gagal(f"total {total:.2f} s > MAXDUR {maxdur:.0f} s (persingkat naskah, jangan potong WAV)", 2)
    if masalah and os.environ.get("JEDA_SEMPIT_OK") != "1":
        mu.gagal("QC jeda sempit:\n  " + "\n  ".join(masalah), 5)
    print("TIMELINE: LULUS")
    return tl


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    bangun(sys.argv[1], "long" if "--long" in sys.argv else "shorts")
