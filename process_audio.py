#!/usr/bin/env python3
"""process_audio.py - rapikan VO TANPA memotong isi + penyamaan pace + QC keutuhan.

Urutan per klip (episodes/<slug>/audio_raw/<id>.wav -> build/<slug>/audio_proc/<id>.wav):
  1. baca -> 48 kHz mono float, buang DC.
  2. ukur pace mentah = kata / durasi bicara (batas bicara = amplop > SIL_DB, ambang sangat rendah).
  3. atempo (ffmpeg, WSOLA) pada SELURUH klip -> "referensi"; faktor = TARGET_WPS*speed_adegan / pace,
     dibatasi [ATEMPO_MIN, ATEMPO_MAX].
  4. buang HANYA hening awal/akhir referensi, sisakan pad PAD_AWAL (80 ms) / PAD_AKHIR (250 ms).
     Fade sangat pendek hanya di dalam area hening pad (bukan di suara).
  5. kompresi lembut (2:1 di atas -20 dBFS, maks 6 dB, tanpa expander/gate), normalisasi puncak -3 dBFS.
  6. QC: mulai <= 0.30 s | akhir klip hening | tanpa clipping | pace <= 2.10 kata/detik |
         ISI HILANG <= 30 ms (amplop hasil vs referensi, disejajarkan) -> gagal = exit 3 |
         tempo utuh (durasi bicara referensi ~= mentah / faktor).
TIDAK ADA gate, expander, atau peredam napas (aturan keras §2.3). REDAM_NAPAS diabaikan.

Pakai:  python3 process_audio.py <slug> [--only intro,f1]
Uji:    python3 process_audio.py --uji
Env:    TARGET_WPS (1.90) ATEMPO_MIN (0.88) ATEMPO_MAX (1.08) SIL_DB (-49) PAD_AWAL (0.08) PAD_AKHIR (0.25)
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mesin_util as mu  # noqa: E402

SR = mu.SR
QC_MULAI_MAKS = 0.30
QC_PACE_MAKS = 2.10
QC_HILANG_MAKS_MS = 30.0
EXIT_HILANG = 3
EXIT_QC_LAIN = 4


# -------------------------------------------------------------------------------------- inti
def batas_bicara(x, thr_db, frame=0.002):
    """(i0, i1) sampel pertama & terakhir yang amplop-puncaknya > thr_db. None bila senyap total."""
    e = mu.env_db(x, SR, frame, "peak")
    idx = np.nonzero(e > thr_db)[0]
    if len(idx) == 0:
        return None
    n = int(round(frame * SR))
    return int(idx[0] * n), int(min(len(x), (idx[-1] + 1) * n))


def atempo(x, f):
    if abs(f - 1.0) < 0.004:
        return x.copy()
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "in.wav"
        mu.tulis_wav(src, x, SR)
        cmd = [mu.ffmpeg_exe(), "-v", "error", "-i", str(src), "-af", f"atempo={f:.5f}",
               "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"]
        out = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(out, dtype="<f4").astype(np.float32).copy()


def kompres_lembut(x, thr_db=-20.0, ratio=2.0, maks_db=6.0, att=0.010, rel=0.120, frame=0.005):
    """Kompresor RMS halus. HANYA mengurangi di atas ambang; di bawah ambang gain = 1 (tanpa expander)."""
    lv = mu.env_db(x, SR, frame, "rms")
    gr = np.clip((lv - thr_db) * (1 - 1 / ratio), 0, maks_db)
    a = np.exp(-frame / att)
    r = np.exp(-frame / rel)
    sm = np.zeros_like(gr)
    g = 0.0
    for i, v in enumerate(gr):
        c = a if v > g else r
        g = c * g + (1 - c) * v
        sm[i] = g
    n = int(round(frame * SR))
    tc = (np.arange(len(sm)) + 0.5) * n
    gain_db = np.interp(np.arange(len(x)), tc, sm)
    return (x * 10 ** (-gain_db / 20)).astype(np.float32)


def normal_puncak(x, target_db=-3.0):
    m = float(np.abs(x).max())
    return (x * (10 ** (target_db / 20) / m)).astype(np.float32) if m > 1e-9 else x


def isi_hilang_ms(ref, out, offset, sil_db=-49.0, toleransi=15.0, frame=0.005):
    """Bandingkan amplop PUNCAK hasil vs referensi (disejajarkan per sampel: out[i] <-> ref[i+offset]).
    Frame 'isi' = amplop referensi > SIL_DB+3 (ambang yang sama dengan pemotong hening, jadi ekor lirih
    ikut dijaga). Isi dianggap hilang bila di hasil teredam > toleransi dB (setelah koreksi selisih gain
    median akibat normalisasi/kompresi). -> (ms, daftar_waktu_detik)."""
    al = np.zeros(len(ref), dtype=np.float32)
    a0 = max(0, offset)
    b0 = max(0, -offset)
    n = min(len(ref) - a0, len(out) - b0)
    if n > 0:
        al[a0:a0 + n] = out[b0:b0 + n]
    rd = mu.env_db(ref, SR, frame, "peak")
    ad = mu.env_db(al, SR, frame, "peak")
    isi = (rd > sil_db + 3) & (rd > rd.max() - 55)
    if not isi.any():
        return 0.0, []
    kuat = isi & (rd > rd.max() - 20)
    off = float(np.median((ad - rd)[kuat])) if kuat.any() else 0.0
    # tanpa toleransi waktu: hasil = potongan referensi yang sama persis (hanya gain halus berbeda),
    # jadi frame 5 ms sebanding langsung -> kehilangan terukur ~ kehilangan nyata (+-5 ms)
    hilang = isi & (ad < rd + off - toleransi)
    t = (np.nonzero(hilang)[0] * frame).round(3).tolist()
    return float(hilang.sum() * frame * 1000.0), t


def proses_klip(raw, teks, cfg, speed=1.0):
    """-> (out, info). Tidak menulis file."""
    sil = cfg.f("SIL_DB", -49.0)
    pad_a = cfg.f("PAD_AWAL", 0.08)
    pad_b = cfg.f("PAD_AKHIR", 0.25)
    tmin, tmax = cfg.f("ATEMPO_MIN", 0.88), cfg.f("ATEMPO_MAX", 1.08)
    target = cfg.f("TARGET_WPS", 1.90) * float(speed or 1.0)
    raw = (raw - float(np.mean(raw))).astype(np.float32)
    kata = mu.hitung_kata(teks)
    b = batas_bicara(raw, sil)
    if b is None:
        raise ValueError("klip senyap total")
    dur_bicara = (b[1] - b[0]) / SR
    wps_raw = kata / max(dur_bicara, 1e-3)
    faktor = float(np.clip(target / wps_raw, tmin, tmax)) if target > 0 else 1.0
    ref = atempo(raw, faktor)
    br = batas_bicara(ref, sil)
    i0 = br[0] - int(round(pad_a * SR))
    i1 = br[1] + int(round(pad_b * SR))
    pre = max(0, -i0)
    post = max(0, i1 - len(ref))
    out = np.concatenate([np.zeros(pre, np.float32), ref[max(0, i0):min(len(ref), i1)],
                          np.zeros(post, np.float32)])
    offset = i0  # out[i] <-> ref[i + i0]
    # fade HANYA di area pad hening
    fa = min(int(0.005 * SR), max(1, br[0] - max(0, i0)))
    out[:fa] *= np.linspace(0, 1, fa, dtype=np.float32)
    fb = int(0.030 * SR)
    out[-fb:] *= np.linspace(1, 0, fb, dtype=np.float32) ** 2
    out = normal_puncak(out, -3.0)
    out = kompres_lembut(out)
    out = normal_puncak(out, -3.0)
    info = {"kata": kata, "wps_mentah": round(wps_raw, 3), "faktor": round(faktor, 4),
            "dur_mentah": round(len(raw) / SR, 3), "dur": round(len(out) / SR, 3), "_offset": offset}
    return out, ref, raw, info


def qc_klip(out, ref, raw, info, cfg):
    sil = cfg.f("SIL_DB", -49.0)
    res = {}
    b = batas_bicara(out, sil)
    res["mulai_s"] = round(b[0] / SR, 3) if b else None
    res["hening_akhir_s"] = round((len(out) - b[1]) / SR, 3) if b else None
    tail = out[-int(0.15 * SR):]
    res["akhir_db"] = round(float(mu.db(np.abs(tail).max())), 1)
    res["puncak_db"] = round(float(mu.db(np.abs(out).max())), 2)
    dur_b = (b[1] - b[0]) / SR if b else 1e-3
    res["pace"] = round(info["kata"] / max(dur_b, 1e-3), 3)
    ms, tt = isi_hilang_ms(ref, out, info["_offset"], sil)
    res["isi_hilang_ms"] = round(ms, 1)
    res["isi_hilang_di"] = tt[:10]
    # tempo utuh: durasi aktif referensi ~= mentah / faktor
    act = lambda x: float((mu.env_db(x, SR, 0.010) > -45).sum()) * 0.010  # noqa: E731
    exp_ = act(raw) / info["faktor"]
    got = act(ref)
    res["tempo_dev_s"] = round(got - exp_, 3)
    gagal = []
    if res["mulai_s"] is None or res["mulai_s"] > QC_MULAI_MAKS:
        gagal.append("mulai>0.30s")
    if res["akhir_db"] > sil + 6 or (res["hening_akhir_s"] or 0) < 0.15:
        gagal.append("akhir tidak hening (terpotong?)")
    if res["puncak_db"] > -0.1:
        gagal.append("clipping")
    if res["pace"] > QC_PACE_MAKS:
        gagal.append(f"pace {res['pace']}>2.10")
    if abs(got - exp_) > max(0.08, 0.08 * exp_):
        gagal.append("tempo tidak utuh")
    hilang = ms > QC_HILANG_MAKS_MS
    if hilang:
        gagal.append(f"ISI HILANG {ms:.0f} ms")
    res["gagal"] = gagal
    res["lulus"] = not gagal
    res["_hilang"] = hilang
    return res


# -------------------------------------------------------------------------------------- episode
def proses_episode(slug, only=None):
    ep, content, cfg, bdir = mu.muat_episode(slug)
    if cfg.b("REDAM_NAPAS"):
        print("[PERINGATAN] REDAM_NAPAS diabaikan: peredam napas dilarang (aturan keras §2.3).")
    pdir = bdir / "audio_proc"
    pdir.mkdir(parents=True, exist_ok=True)
    info_path = pdir / "info.json"
    semua = {}
    if info_path.exists():
        import json
        semua = json.loads(info_path.read_text(encoding="utf-8"))
    print(f"process_audio: {ep.name}  TARGET_WPS={cfg.f('TARGET_WPS')} ATEMPO=[{cfg.f('ATEMPO_MIN')},"
          f"{cfg.f('ATEMPO_MAX')}] SIL_DB={cfg.f('SIL_DB', -49)}")
    print(f"{'id':<10}{'kata':>5}{'pace0':>7}{'faktor':>7}{'dur':>7}{'mulai':>7}{'pace':>6}{'puncak':>7}"
          f"{'hilang':>8}  status")
    ada_hilang = ada_gagal = False
    for sc in content["scenes"]:
        sid = sc["id"]
        if only and sid not in only:
            continue
        src = ep / "audio_raw" / f"{sid}.wav"
        if not src.exists():
            print(f"{sid:<10} FILE TIDAK ADA: {src}")
            ada_gagal = True
            continue
        raw = mu.baca_wav(src)
        out, ref, raw, info = proses_klip(raw, sc.get("vo", ""), cfg, sc.get("speed", 1.0))
        q = qc_klip(out, ref, raw, info, cfg)
        mu.tulis_wav(pdir / f"{sid}.wav", out)
        info.pop("_offset")
        hil = q.pop("_hilang")
        semua[sid] = {**info, **q}
        ada_hilang |= hil
        ada_gagal |= not q["lulus"]
        print(f"{sid:<10}{info['kata']:>5}{info['wps_mentah']:>7.2f}{info['faktor']:>7.3f}{info['dur']:>7.2f}"
              f"{q['mulai_s']:>7.2f}{q['pace']:>6.2f}{q['puncak_db']:>7.1f}{q['isi_hilang_ms']:>7.0f}ms  "
              f"{'OK' if q['lulus'] else 'GAGAL: ' + '; '.join(q['gagal'])}")
    mu.tulis_json(info_path, semua)
    if ada_hilang:
        mu.gagal("QC isi hilang > 30 ms. Rekam ulang klip (jangan dipotong).", EXIT_HILANG)
    if ada_gagal:
        mu.gagal("QC audio gagal (lihat tabel).", EXIT_QC_LAIN)
    print("QC AUDIO: LULUS (isi utuh)")


# -------------------------------------------------------------------------------------- uji
def _sintetis(seed=7):
    """Ucapan sintetis: suku kata harmonik + konsonan lembut + jeda frasa + ekor lirih.
    -> (x, teks, jumlah_kata)."""
    r = np.random.default_rng(seed)
    parts = [np.zeros(int(0.40 * SR), np.float32)]
    words = 0
    for frasa in range(3):
        for w in range(int(r.integers(3, 5))):
            words += 1
            if r.random() < 0.4:  # konsonan desis lirih (-32 dB) di awal kata
                n = int(0.05 * SR)
                parts.append((r.standard_normal(n) * 0.025 * np.hanning(n)).astype(np.float32))
            for s in range(int(r.integers(2, 4))):
                n = int(r.uniform(0.12, 0.22) * SR)
                t = np.arange(n) / SR
                f0 = r.uniform(105, 140) * (1 + 0.05 * np.sin(2 * np.pi * 3 * t))
                ph = 2 * np.pi * np.cumsum(f0) / SR
                v = sum(np.sin(h * ph) / h ** 1.2 for h in range(1, 14))
                env = np.sin(np.pi * np.linspace(0, 1, n)) ** 0.7
                parts.append((0.35 * v * env).astype(np.float32))
            parts.append(np.zeros(int(0.045 * SR), np.float32))
        parts.append(np.zeros(int(r.uniform(0.30, 0.55) * SR), np.float32))
    # ekor lirih (-38 dB) - harus TETAP ada
    n = int(0.18 * SR)
    t = np.arange(n) / SR
    parts.append((0.012 * np.sin(2 * np.pi * 120 * t) * np.exp(-t / 0.06)).astype(np.float32))
    parts.append(np.zeros(int(0.60 * SR), np.float32))
    x = np.concatenate(parts)
    teks = " ".join(["kata"] * words)
    return x, teks, words


def _uji():
    cfg = mu.Cfg(mu.DEFAULT_SHORTS)
    hasil = []

    def cek(nama, kondisi, detail=""):
        hasil.append(kondisi)
        print(f"  [{'OK' if kondisi else 'GAGAL'}] {nama} {detail}")

    print("1) ucapan sintetis (suku kata, konsonan lirih, jeda, ekor lirih)")
    x, teks, nk = _sintetis()
    out, ref, raw, info = proses_klip(x, teks, cfg)
    q = qc_klip(out, ref, raw, info, cfg)
    cek("isi hilang = 0 ms", q["isi_hilang_ms"] == 0.0, f"({q['isi_hilang_ms']} ms)")
    cek("mulai <= 0.30 s", q["mulai_s"] <= 0.30, f"({q['mulai_s']} s)")
    cek("akhir hening", q["akhir_db"] < -43, f"({q['akhir_db']} dB)")
    cek("tanpa clipping", q["puncak_db"] <= -0.1, f"({q['puncak_db']} dB)")
    cek("pace <= 2.10", q["pace"] <= 2.10, f"({q['pace']} kata/s, faktor {info['faktor']})")
    cek("QC klip lulus", q["lulus"], str(q["gagal"]))
    # ekor lirih harus tetap ada: energi di sekitar akhir bicara referensi
    cek("ekor lirih -38 dB dipertahankan", q["hening_akhir_s"] <= 0.30, f"(hening akhir {q['hening_akhir_s']} s)")

    print("2) uji negatif: QC harus MENDETEKSI potongan")
    ekuat = mu.env_db(out, SR, 0.010, "peak")
    pusat = int(np.argmax(ekuat)) * int(0.010 * SR)
    rusak = out.copy()
    rusak[pusat - int(0.06 * SR):pusat + int(0.06 * SR)] = 0.0
    ms, _ = isi_hilang_ms(ref, rusak, info["_offset"])
    q1 = qc_klip(rusak, ref, raw, info, cfg)
    cek("lubang 120 ms di tengah suku kata terdeteksi", ms >= 100 and not q1["lulus"], f"({ms:.0f} ms)")
    rd = mu.env_db(ref, SR, 0.005, "peak")
    akhir_isi = (int(np.nonzero(rd > -46)[0][-1]) + 1) * int(0.005 * SR) - info["_offset"]
    tanpa_ekor = out[: akhir_isi - int(0.06 * SR)].copy()
    tanpa_ekor = np.concatenate([tanpa_ekor, np.zeros(int(0.25 * SR), np.float32)])
    q2 = qc_klip(tanpa_ekor, ref, raw, info, cfg)
    cek("60 ms ekor lirih dibuang terdeteksi", not q2["lulus"] and q2["isi_hilang_ms"] >= 50,
        f"({q2['isi_hilang_ms']} ms) {q2['gagal']}")
    bk = batas_bicara(out, -20)
    potong = out[: bk[1] - int(0.10 * SR)].copy()
    q3 = qc_klip(potong, ref, raw, info, cfg)
    cek("akhir terpotong di tengah kata terdeteksi", not q3["lulus"], str(q3["gagal"]))
    geser = np.concatenate([np.zeros(int(0.5 * SR), np.float32), out])
    q4 = qc_klip(geser, ref, raw, {**info, "_offset": info["_offset"] - int(0.5 * SR)}, cfg)
    cek("mulai terlambat 0.58 s terdeteksi", not q4["lulus"], str(q4["gagal"]))

    ref_wav = mu.ROOT / "suara" / "referensi_narator.wav"
    if ref_wav.exists():
        print("3) klip TTS asli (suara narator terkunci)")
        teks = ("Kenapa aurora hanya muncul di dekat kutub, padahal Matahari menyinari seluruh Bumi? Jawabannya "
                "ada pada medan magnet Bumi. Medan ini membelokkan partikel bermuatan dari Matahari ke arah "
                "kutub, lalu membuat gas di atmosfer atas menyala hijau dan ungu.")
        out, ref, raw, info = proses_klip(mu.baca_wav(ref_wav), teks, cfg)
        q = qc_klip(out, ref, raw, info, cfg)
        cek("TTS isi hilang = 0 ms", q["isi_hilang_ms"] == 0.0, f"({q['isi_hilang_ms']} ms)")
        cek("TTS QC lulus", q["lulus"], f"pace {info['wps_mentah']} -> {q['pace']} (faktor {info['faktor']}),"
            f" mulai {q['mulai_s']} s, {q['gagal']}")
        mu.tulis_wav(mu.ROOT / "build" / "uji_audio" / "referensi_proc.wav", out)
    ok = all(hasil)
    print("PROCESS_AUDIO SELFTEST:", "LULUS" if ok else "GAGAL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--only", default="")
    ap.add_argument("--uji", action="store_true")
    a = ap.parse_args()
    if a.uji:
        raise SystemExit(_uji())
    if not a.slug:
        ap.error("slug wajib (atau --uji)")
    proses_episode(a.slug, set(filter(None, a.only.split(","))) or None)


if __name__ == "__main__":
    main()
