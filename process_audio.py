#!/usr/bin/env python3
"""process_audio.py <slug> - rapikan VO TANPA memotong isi.

Langkah per klip (episodes/<slug>/audio_raw/<id>.wav -> episodes/<slug>/audio_proc/<id>.wav):
  1. buang hening HANYA di awal/akhir (ambang -48 dBFS, pad 80 ms awal / 250 ms akhir)
  2. samakan pace ke TARGET_WPS kata/detik via atempo (batas ATEMPO_MIN..ATEMPO_MAX)
  3. kompresi lembut (ratio 2:1 di atas -18 dBFS, tanpa gate/expander), puncak -3 dBFS
  4. QC: onset <= 0.30 s, akhir hening, tanpa clipping, pace <= 2.10, ISI HILANG <= 30 ms (exit 3 bila gagal)
Env: SPEED (fallback bila tidak ada teks), TARGET_WPS, ATEMPO_MIN (0.88), ATEMPO_MAX (1.08), REDAM_NAPAS (0 = mati).
"""
import os
import sys

import numpy as np

from audio_util import SR, db, env_of, envelope, load_json, read_audio, save_json, write_wav

TRIM_DB = -48.0
PAD_IN = 0.08
PAD_OUT = 0.25
SPEECH_DB = -40.0  # ambang "ada isi" untuk QC keutuhan


def trim_silence(x):
    env = envelope(x, 10)
    idx = np.where(env > TRIM_DB)[0]
    if len(idx) == 0:
        return x, 0.0, 0.0
    hop = int(SR * 0.01)
    a = max(0, idx[0] * hop - int(PAD_IN * SR))
    b = min(len(x), (idx[-1] + 1) * hop + int(PAD_OUT * SR))
    return x[a:b], a / SR, (len(x) - b) / SR


def soft_compress(x, thr_db=-18.0, ratio=2.0, att=0.005, rel=0.12):
    """Kompresor feed-forward lembut. Tidak ada gate: gain tidak pernah < 1 di bawah ambang."""
    thr = 10 ** (thr_db / 20)
    a_att = np.exp(-1 / (SR * att))
    a_rel = np.exp(-1 / (SR * rel))
    # envelope puncak per blok 1 ms untuk kecepatan, lalu interpolasi
    hop = 48
    n = len(x) // hop
    pk = np.abs(x[: n * hop]).reshape(n, hop).max(axis=1)
    env = np.zeros(n)
    e = 0.0
    a_att_b = a_att ** hop
    a_rel_b = a_rel ** hop
    for i in range(n):
        v = pk[i]
        e = a_att_b * e + (1 - a_att_b) * v if v > e else a_rel_b * e + (1 - a_rel_b) * v
        env[i] = e
    gain = np.ones(n)
    over = env > thr
    gain[over] = (thr / env[over]) ** (1 - 1 / ratio)
    g = np.interp(np.arange(len(x)) / hop, np.arange(n), gain, right=gain[-1] if n else 1.0)
    return (x * g).astype(np.float32)


def speech_mask(x, hop_ms=10):
    return envelope(x, hop_ms) > SPEECH_DB


def content_loss_ms(ref, out, factor, hop_ms=10, tol_hops=3):
    """Berapa ms isi (blok bersuara) di referensi yang TIDAK ditemukan di hasil (setelah skala waktu)."""
    mr = speech_mask(ref, hop_ms)
    mo = speech_mask(out, hop_ms)
    lost = 0
    for i in np.where(mr)[0]:
        j = int(round(i / factor))
        lo, hi = max(0, j - tol_hops), min(len(mo), j + tol_hops + 1)
        if hi <= lo or not mo[lo:hi].any():
            lost += 1
    return lost * hop_ms


def main(slug):
    env_of(slug)
    base = os.path.join("episodes", slug)
    content = load_json(os.path.join(base, "content.json"))
    speed = float(os.environ.get("SPEED", "1.0"))
    target = float(os.environ.get("TARGET_WPS", "0") or 0)
    amin = float(os.environ.get("ATEMPO_MIN", "0.88"))
    amax = float(os.environ.get("ATEMPO_MAX", "1.08"))
    redam = os.environ.get("REDAM_NAPAS", "0") == "1"
    if redam:
        print("PERINGATAN: REDAM_NAPAS diminta tetapi dimatikan permanen (aturan pemilik).")
    outdir = os.path.join(base, "audio_proc")
    os.makedirs(outdir, exist_ok=True)
    report = {}
    fail = []
    for sc in content["scenes"]:
        sid = sc["id"]
        src = os.path.join(base, "audio_raw", sid + ".wav")
        if not os.path.exists(src):
            fail.append((sid, "file VO tidak ada"))
            continue
        raw = read_audio(src)
        trimmed, cut_a, cut_b = trim_silence(raw)
        dur0 = len(trimmed) / SR
        words = len(sc.get("vo", "").split())
        wps0 = words / dur0 if dur0 > 0 else 0
        if words and target > 0:
            factor = target / wps0 if wps0 > 0 else speed
        else:
            factor = speed
        factor *= float(sc.get("speed", 1.0))
        factor = float(np.clip(factor, amin, amax))
        # atempo lewat ffmpeg (kualitas WSOLA), baca kembali sebagai float
        tmp = os.path.join(outdir, "_" + sid + "_trim.wav")
        write_wav(tmp, trimmed)
        y = read_audio(tmp, extra_af="atempo=%.4f" % factor)
        os.remove(tmp)
        y = soft_compress(y)
        pk = float(np.max(np.abs(y))) if len(y) else 0
        if pk > 0:
            y *= 10 ** (-3.0 / 20) / pk
        # QC
        env = envelope(y, 10)
        on = np.where(env > SPEECH_DB)[0]
        onset = (on[0] * 0.01) if len(on) else 99
        tail_env = envelope(y[-int(0.15 * SR):], 10) if len(y) > SR * 0.2 else np.array([-120.0])
        tail_ok = bool(np.max(tail_env) < -30)
        dur = len(y) / SR
        pace = words / dur if dur > 0 else 0
        loss = content_loss_ms(trimmed, y, factor)
        clip = float(np.max(np.abs(y))) >= 0.99
        issues = []
        if onset > 0.30:
            issues.append("onset %.2fs > 0.30" % onset)
        if not tail_ok:
            issues.append("akhir klip tidak hening (terpotong?)")
        if clip:
            issues.append("clipping")
        if words and pace > 2.10:
            issues.append("pace %.2f > 2.10" % pace)
        if loss > 30:
            issues.append("ISI HILANG %d ms > 30" % loss)
        write_wav(os.path.join(outdir, sid + ".wav"), y)
        report[sid] = dict(dur_raw=round(len(raw) / SR, 3), dur=round(dur, 3), cut_awal=round(cut_a, 3),
                           cut_akhir=round(cut_b, 3), words=words, wps_raw=round(wps0, 3), factor=round(factor, 4),
                           pace=round(pace, 3), onset=round(onset, 3), isi_hilang_ms=loss, issues=issues)
        print("%-10s raw %6.2fs -> %6.2fs  x%.3f  pace %.2f k/d  onset %.2f  hilang %3d ms  %s" % (
            sid, len(raw) / SR, dur, factor, pace, onset, loss, "OK" if not issues else "; ".join(issues)))
        if issues:
            fail.append((sid, "; ".join(issues)))
    save_json(os.path.join(outdir, "report.json"), report)
    total = sum(r["dur"] for r in report.values())
    print("total VO %.1f s, %d klip" % (total, len(report)))
    if fail:
        print("QC GAGAL:", fail)
        return 3
    print("QC audio BERSIH")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
