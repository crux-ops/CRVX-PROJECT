#!/usr/bin/env python3
"""build_audio.py <slug> - susun VO terjadwal (start+lead_in) jadi satu track, puncak -2.5 dBFS.
Keluaran: episodes/<slug>/build/audio_vo.wav
"""
import os, sys
import numpy as np
from audio_util import SR, env_of, load_json, read_audio, write_wav


def main(slug):
    env_of(slug)
    base = os.path.join("episodes", slug)
    tl = load_json(os.path.join(base, "timeline.json"))
    n = int(round(tl["total"] * SR))
    out = np.zeros(n, dtype=np.float32)
    for s in tl["scenes"]:
        x = read_audio(os.path.join(base, "audio_proc", s["id"] + ".wav"))
        a = int(round(s["vo_start"] * SR))
        b = min(n, a + len(x))
        if b - a < len(x):
            print("PERINGATAN: VO %s melewati akhir timeline (%d sampel)" % (s["id"], len(x) - (b - a)))
        out[a:b] += x[: b - a]
    pk = float(np.max(np.abs(out)))
    if pk > 0:
        out *= 10 ** (-2.5 / 20) / pk
    write_wav(os.path.join(base, "build", "audio_vo.wav"), out)
    print("audio_vo.wav %.2f s, puncak %.2f dBFS" % (n / SR, 20 * np.log10(float(np.max(np.abs(out))) + 1e-9)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
