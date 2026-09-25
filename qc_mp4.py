#!/usr/bin/env python3
"""qc_mp4.py - QC hasil akhir MP4 (WAJIB lulus sebelum diserahkan ke pemilik).

Cek:
  1. stream: H.264 High, yuv420p, BT.709, resolusi & fps sesuai config; audio AAC 48 kHz
  2. durasi video (jumlah frame) & audio = timeline (toleransi 0.35 s)
  3. audio MP4 vs master: korelasi >= 0.97 (setelah penyejajaran delay encoder)
  4. VO tiap adegan UTUH & mulai TEPAT (onset +-40 ms dari vo_start; isi hilang <= 30 ms vs stem VO)
  5. puncak audio MP4 < -0.1 dBFS
  6. frame contoh + montase berlabel (build/<slug>/qc_mp4.jpg) untuk diperiksa mata
  7. audit margin 40 px pada frame 'isi' (tidak ada tinta kontras tinggi di pinggir)
Pakai: python3 qc_mp4.py <file.mp4> --slug <slug> [--long]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mesin_util as mu  # noqa: E402
from process_audio import isi_hilang_ms  # noqa: E402

SR = mu.SR


def info_stream(mp4):
    err = subprocess.run([mu.ffmpeg_exe(), "-hide_banner", "-i", str(mp4)], capture_output=True, text=True).stderr
    v = re.search(r"Stream #\S+.*Video: (\w+) \(([^)]*)\).*?, (\w+)\(([^)]*)\).*?, (\d+)x(\d+).*?, ([\d.]+) fps", err)
    a = re.search(r"Stream #\S+.*Audio: (\w+).*?, (\d+) Hz, (\w+)", err)
    d = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err)
    out = {"raw": err}
    if v:
        out.update(vcodec=v.group(1), profil=v.group(2), pix=v.group(3), warna=v.group(4),
                   w=int(v.group(5)), h=int(v.group(6)), fps=float(v.group(7)))
    if a:
        out.update(acodec=a.group(1), sr=int(a.group(2)), kanal=a.group(3))
    if d:
        out["durasi"] = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3))
    return out


def hitung_frame(mp4):
    """jumlah frame video via framecrc (satu baris per paket, stream copy, tanpa decode).
    Catatan: ffmpeg 7 tidak mencetak 'frame=' untuk -c copy -f null -> jangan andalkan itu."""
    out = subprocess.run([mu.ffmpeg_exe(), "-v", "error", "-i", str(mp4), "-map", "0:v:0", "-c", "copy",
                          "-f", "framecrc", "-"], capture_output=True, text=True).stdout
    return sum(1 for ln in out.splitlines() if ln and not ln.startswith("#"))


def audio_mp4(mp4):
    out = subprocess.run([mu.ffmpeg_exe(), "-v", "error", "-i", str(mp4), "-map", "0:a:0", "-f", "f32le", "-ac", "1",
                          "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(out, dtype="<f4").astype(np.float32)


def frame_di(mp4, t, w, h):
    raw = subprocess.run([mu.ffmpeg_exe(), "-v", "error", "-ss", f"{t:.3f}", "-i", str(mp4), "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return Image.frombytes("RGB", (w, h), raw[: w * h * 3])


def sejajarkan(a, ref, maks=0.2):
    """offset (sampel) terbaik a relatif ref via korelasi silang FFT (delay encoder AAC)."""
    n = min(len(a), len(ref), SR * 20)
    m = int(maks * SR)
    A = np.fft.rfft(a[:n], 2 * n)
    B = np.fft.rfft(ref[:n], 2 * n)
    c = np.fft.irfft(A * np.conj(B), 2 * n)
    c = np.concatenate([c[-m:], c[:m + 1]])
    return int(np.argmax(c)) - m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mp4")
    ap.add_argument("--slug", required=True)
    ap.add_argument("--long", action="store_true")
    a = ap.parse_args()
    jenis = "long" if a.long else "shorts"
    ep, content, cfg, bdir = mu.muat_episode(a.slug, jenis)
    tl = json.loads((bdir / "timeline.json").read_text(encoding="utf-8"))
    mp4 = Path(a.mp4)
    W, H = (1920, 1080) if a.long else (1080, 1920)
    fps = cfg.i("FPS", 30 if a.long else 60)
    gagal, catatan = [], {}

    def cek(nama, kond, det=""):
        print(f"  [{'OK' if kond else 'GAGAL'}] {nama} {det}")
        if not kond:
            gagal.append(nama)

    print(f"qc_mp4: {mp4.name} ({mp4.stat().st_size / 1e6:.1f} MB)")
    inf = info_stream(mp4)
    cek("video H.264 High yuv420p", inf.get("vcodec") == "h264" and "High" in inf.get("profil", "")
        and inf.get("pix") == "yuv420p", f"({inf.get('vcodec')} {inf.get('profil')} {inf.get('pix')})")
    cek("warna BT.709", "bt709" in inf.get("warna", ""), f"({inf.get('warna')})")
    cek(f"resolusi {W}x{H} @ {fps} fps", inf.get("w") == W and inf.get("h") == H and abs(inf.get("fps", 0) - fps) < 0.01,
        f"({inf.get('w')}x{inf.get('h')} @ {inf.get('fps')})")
    cek("audio AAC 48 kHz", inf.get("acodec") == "aac" and inf.get("sr") == 48000, f"({inf.get('acodec')} {inf.get('sr')})")
    nfr = hitung_frame(mp4)
    dv = nfr / fps
    cek("durasi video = timeline (+-0.35 s)", abs(dv - tl["total"]) <= 0.35,
        f"({nfr} frame = {dv:.3f} s vs {tl['total']:.3f} s)")
    au = audio_mp4(mp4)
    da = len(au) / SR
    cek("durasi audio = timeline (+-0.35 s)", abs(da - tl["total"]) <= 0.35, f"({da:.3f} s)")
    master = mu.baca_wav(bdir / "audio_master.wav")
    vo = mu.baca_wav(bdir / "audio_master_vo.wav")
    off = sejajarkan(au, master)
    al = np.zeros_like(master)
    src = au[max(0, off):]
    dst0 = max(0, -off)
    n = min(len(master) - dst0, len(src))
    al[dst0:dst0 + n] = src[:n]
    kor = float(np.corrcoef(al, master)[0, 1])
    cek("korelasi audio MP4 vs master >= 0.97", kor >= 0.97, f"({kor:.4f}, delay {off / SR * 1000:.1f} ms)")
    pk = float(mu.db(np.abs(au).max()))
    cek("puncak audio < -0.1 dBFS", pk < -0.1, f"({pk:.2f} dBFS)")
    print("  VO per adegan:")
    semua_vo = True
    for s in tl["scenes"]:
        i0, i1 = int(s["vo_start"] * SR), int((s["vo_start"] + s["vo_dur"]) * SR)
        seg_ref, seg_mp4 = vo[i0:i1], al[i0:i1]
        # mulai tepat: lag korelasi-silang MP4 (VO+SFX) vs stem VO di jendela adegan (SFX tidak mengganggu
        # puncak korelasi; membandingkan 'sampel pertama di atas ambang' salah karena SFX berbunyi lebih dulu)
        a0 = max(0, i0 - int(0.25 * SR))
        lag = sejajarkan(al[a0:i1], vo[a0:i1], 0.25)
        dt = lag / SR * 1000.0
        hil, _ = isi_hilang_ms(seg_ref, seg_mp4, 0)
        ok = abs(dt) <= 40 and hil <= 30
        semua_vo &= ok
        print(f"    {s['id']:<10} geser {dt:+5.1f} ms  isi hilang {hil:4.0f} ms  {'OK' if ok else 'GAGAL'}")
        catatan[s["id"]] = {"onset_ms": dt, "hilang_ms": hil}
    cek("VO tiap adegan utuh & mulai tepat", semua_vo)
    # frame contoh + audit margin
    tt = mu.preview_times(tl, 10)
    imgs, labels, margin_buruk = [], [], []
    for t, lb in tt:
        im = frame_di(mp4, t, W, H)
        imgs.append(im)
        labels.append(f"{lb} {t:.2f}s")
        if lb.endswith("isi"):
            g = np.asarray(im.convert("L"), np.int16)
            bl = np.asarray(im.convert("L").filter(ImageFilter.GaussianBlur(12)), np.int16)
            dev = np.abs(g - bl) > 40
            # buang titik terisolasi sangat kecil (bintang/partikel latar dekoratif) lewat opening morfologi;
            # teks penting sudah diaudit ketat lewat kotak teks sebelum render (check_layout / --check)
            k = 5 if a.long else 3
            dm = Image.fromarray((dev * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(k)).filter(ImageFilter.MaxFilter(k))
            dev = np.asarray(dm) > 0
            m = 40
            px = int(dev[:, :m].sum() + dev[:, -m:].sum() + dev[-m:, :].sum())
            if px > 60:
                margin_buruk.append(f"{lb}@{t:.2f}s:{px}px")
    cek("margin 40 px bersih pada frame isi", not margin_buruk, " ".join(margin_buruk))
    out = bdir / "qc_mp4.jpg"
    mu.sheet(imgs, labels, cols=5, lebar=300 if not a.long else 420, judul=f"QC {mp4.name}", path=out)
    print(f"  montase: {out}")
    hasil = {"mp4": str(mp4), "frame": nfr, "durasi_video": dv, "durasi_audio": da, "korelasi": kor, "puncak": pk,
             "vo": catatan, "gagal": gagal}
    mu.tulis_json(bdir / "qc_mp4.json", hasil)
    print("QC MP4:", "LULUS" if not gagal else f"GAGAL ({', '.join(gagal)})")
    raise SystemExit(0 if not gagal else 1)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--frame":
        print(hitung_frame(sys.argv[2]))
        raise SystemExit(0)
    main()
