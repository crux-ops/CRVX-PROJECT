#!/usr/bin/env python3
"""qc_mp4.py <mp4> [--slug s] - QC hasil akhir:
durasi = timeline (toleransi 0.35 s), VO tiap adegan utuh & mulai tepat (onset dalam +-0.15 s dari vo_start),
korelasi audio MP4 vs master >= 0.97, puncak < -0.1 dBFS, frame contoh + montase berlabel, audit margin."""
import os, re, subprocess, sys
import numpy as np
from PIL import Image
from audio_util import SR, db, envelope, ffmpeg_exe, load_json, read_audio
import mesin_util as U


def info(mp4):
    p = subprocess.run([ffmpeg_exe(), "-i", mp4], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", p.stderr)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    v = re.search(r"Video: (\w+).*?, (\d+)x(\d+).*?([\d.]+) fps", p.stderr)
    return dur, v.group(1), int(v.group(2)), int(v.group(3)), float(v.group(4))


def grab(mp4, t, out):
    subprocess.run([ffmpeg_exe(), "-v", "error", "-ss", "%.3f" % t, "-i", mp4, "-frames:v", "1", "-y", out], check=True)
    return Image.open(out).convert("RGB")


def main(mp4, slug):
    base = os.path.join("episodes", slug)
    tl = load_json(os.path.join(base, "timeline.json"))
    fails = []
    dur, codec, w, h, fps = info(mp4)
    print("MP4: %s %dx%d %.2f fps, %.2f s (timeline %.2f s)" % (codec, w, h, fps, dur, tl["total"]))
    if abs(dur - tl["total"]) > 0.35:
        fails.append("durasi meleset %.2f s" % (dur - tl["total"]))
    if (w, h) != (1080, 1920):
        fails.append("resolusi bukan 1080x1920")
    a = read_audio(mp4)
    m = read_audio(os.path.join(base, "build", "audio_master.wav"))
    n = min(len(a), len(m))
    c = float(np.corrcoef(a[:n], m[:n])[0, 1])
    pk = db(np.max(np.abs(a)))
    print("audio: korelasi vs master %.4f, puncak %.2f dBFS" % (c, pk))
    if c < 0.97:
        fails.append("korelasi audio %.3f < 0.97" % c)
    if pk >= -0.1:
        fails.append("puncak audio %.2f >= -0.1" % pk)
    env = envelope(a, 10)
    for s in tl["scenes"]:
        i0 = int(s["vo_start"] * 100)
        seg_ = env[max(0, i0 - 40): i0 + 60]
        on = np.where(seg_ > -35)[0]
        onset = (max(0, i0 - 40) + on[0]) / 100 if len(on) else None
        i1 = int((s["vo_start"] + s["vo_dur"]) * 100)
        tail = env[max(0, i1 - 25): i1]
        end_ok = len(tail) > 0 and np.max(tail) < -28   # akhir klip hening -> tidak terpotong
        ok = onset is not None and abs(onset - s["vo_start"]) <= 0.15 and end_ok
        print("  %-10s vo_start %7.2f onset %s akhir %s %s" % (s["id"], s["vo_start"],
              "%.2f" % onset if onset is not None else "-", "hening" if end_ok else "BERSUARA", "OK" if ok else "!!"))
        if not ok:
            fails.append("VO %s: onset/akhir tidak sesuai" % s["id"])
    os.makedirs("build/qc", exist_ok=True)
    frames = []
    bad_layout = 0
    for s in tl["scenes"]:
        for f in (0.3, 0.75):
            t = s["start"] + s["dur"] * f
            im = grab(mp4, t, "build/qc/_f.png")
            frames.append((t, im))
            rep = U.ink_report(im)
            if rep["pelanggaran"]:
                bad_layout += 1
                print("  margin t=%.2f: %s" % (t, rep["pelanggaran"]))
    if bad_layout:
        fails.append("audit margin: %d frame bermasalah" % bad_layout)
    U.sheet(frames, "build/qc/montase_qc.jpg", cols=6, thumb_w=240)
    frames[3][1].save("build/qc/frame_contoh.png")
    print("montase -> build/qc/montase_qc.jpg")
    if fails:
        print("QC MP4 GAGAL:", fails)
        return 1
    print("QC MP4 LULUS")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    slug = a[a.index("--slug") + 1] if "--slug" in a else os.environ.get("EPISODE_SLUG")
    sys.exit(main(a[0], slug))
