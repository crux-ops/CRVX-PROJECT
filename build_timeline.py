#!/usr/bin/env python3
"""build_timeline.py <slug> - timeline.json dari durasi VO + ekor per tipe adegan.
durasi adegan = lead_in + durasi VO + tail_<tipe>. Total > MAXDUR -> exit 2. Ekor < lead_in+0.3 -> QC "jeda sempit".
Keluaran: episodes/<slug>/timeline.json {fps, total, scenes:[{id,type,start,dur,vo_dur,vo_start}]}
"""
import os, sys
from audio_util import SR, env_of, load_json, read_audio, save_json


def main(slug):
    env_of(slug)
    base = os.path.join("episodes", slug)
    c = load_json(os.path.join(base, "content.json"))
    maxdur = float(os.environ.get("MAXDUR", "178"))
    lead = float(c.get("lead_in", 0.6))
    tails = {"intro": c.get("tail_intro", 0.8), "fact": c.get("tail_fact", 0.9), "outro": c.get("tail_outro", 1.2)}
    t = 0.0
    scenes = []
    warn = []
    for sc in c["scenes"]:
        wav = os.path.join(base, "audio_proc", sc["id"] + ".wav")
        vo = len(read_audio(wav)) / SR
        tail = float(sc.get("tail", tails.get(sc["type"], 0.9)))
        if tail < lead + 0.3 - 1e-6:
            warn.append("%s: ekor %.2f < lead_in+0.3" % (sc["id"], tail))
        dur = lead + vo + tail
        scenes.append(dict(id=sc["id"], type=sc["type"], start=round(t, 3), dur=round(dur, 3),
                           vo_dur=round(vo, 3), vo_start=round(t + lead, 3)))
        t += dur
    tl = dict(fps=int(os.environ.get("FPS", "60")), total=round(t, 3), lead_in=lead, scenes=scenes)
    save_json(os.path.join(base, "timeline.json"), tl)
    for s in scenes:
        print("%-10s %7.2f  dur %6.2f  vo %6.2f" % (s["id"], s["start"], s["dur"], s["vo_dur"]))
    print("TOTAL %.2f s (batas %.0f)" % (t, maxdur))
    for w in warn:
        print("QC jeda sempit:", w)
    if t > maxdur:
        print("GAGAL: total melebihi MAXDUR")
        return 2
    return 1 if warn else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
