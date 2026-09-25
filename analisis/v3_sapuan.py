#!/usr/bin/env python3
"""analisis/v3_sapuan.py - SAPUAN MENDALAM topik (Google + YouTube Autocomplete).

Benih "kenapa/apakah/bagaimana/padahal/tiba-tiba" x ~60 tema -> frasa bersih (BLOKIR dibuang dari data).
Sinyal per tema: jml, kuat (posisi saran), niat, yt (muncul di YouTube), sains, rel (pengalaman pribadi),
kom (mengundang komentar), vis (bisa diperlihatkan), ever (evergreen).
  skor        = jml + kuat*0.7 + niat*0.9 + sains*3 + yt*0.3
  skor_tumbuh = skor + rel*1.2 + kom*1.5 + vis*0.8 + ever*3
Snapshot harian: analisis/data/hasil_mendalam_<YYYYMMDD>.json

Pakai: python3 analisis/v3_sapuan.py [--mode online|manual] [--tanggal YYYYMMDD]
Uji  : python3 analisis/v3_sapuan.py --uji      (fixture offline, wajib lulus)
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import umum as U  # noqa: E402


def sapuan(mode="online", log=True):
    hasil = {}
    for tema, (pilar, kata, aspek, ever, visb) in U.TEMA.items():
        frasa = {}
        for benih in U.BENIH:
            for k in kata:
                q = f"{benih} {k}"
                for sumber in ("google", "youtube"):
                    try:
                        sar = U.ambil_saran(q, sumber, mode)
                    except U.Offline:
                        raise
                    for pos, s in enumerate(sar):
                        f = U.bersih(s)
                        if not f:
                            continue
                        e = frasa.setdefault(f, {"pos": pos, "yt": False, "google": False})
                        e["pos"] = min(e["pos"], pos)
                        e[sumber if sumber == "google" else "yt"] = True
        n = len(frasa)
        sig = {
            "jml": n,
            "kuat": round(sum((10 - e["pos"]) / 10 for e in frasa.values()), 2),
            "niat": sum(U.punya(f, "niat") for f in frasa),
            "yt": sum(e["yt"] for e in frasa.values()),
            "sains": sum(U.punya(f, "sains") for f in frasa),
            "rel": sum(U.punya(f, "rel") for f in frasa),
            "kom": sum(U.punya(f, "kom") for f in frasa),
            "vis": sum(U.punya(f, "vis") for f in frasa) + visb,
            "ever": ever,
        }
        skor = sig["jml"] + sig["kuat"] * 0.7 + sig["niat"] * 0.9 + sig["sains"] * 3 + sig["yt"] * 0.3
        tumbuh = skor + sig["rel"] * 1.2 + sig["kom"] * 1.5 + sig["vis"] * 0.8 + sig["ever"] * 3
        hasil[tema] = {"pilar": pilar, **sig, "skor": round(skor, 2), "skor_tumbuh": round(tumbuh, 2),
                       "frasa": sorted(frasa, key=lambda f: frasa[f]["pos"])[:40]}
    return hasil


def laporan(hasil, sudah, top=15):
    rank = sorted(hasil.items(), key=lambda kv: -kv[1]["skor_tumbuh"])
    print(f"{'#':>2} {'tema':<22}{'pilar':<11}{'jml':>4}{'skor':>8}{'tumbuh':>8}  status")
    for i, (t, h) in enumerate(rank[:top], 1):
        st = {"shorts": "SUDAH", "long": "LONG (boleh Shorts)"}.get(U.tema_sudah(t, sudah), "segar")
        print(f"{i:>2} {t:<22}{h['pilar']:<11}{h['jml']:>4}{h['skor']:>8.1f}{h['skor_tumbuh']:>8.1f}  {st}")
    return rank


def _uji():
    ok = True

    def cek(nama, kond, det=""):
        nonlocal ok
        ok &= bool(kond)
        print(f"  [{'OK' if kond else 'GAGAL'}] {nama} {det}")

    h1 = sapuan("uji")
    h2 = sapuan("uji")
    semua = [f for h in h1.values() for f in h["frasa"]]
    cek("semua tema tersapu", len(h1) == len(U.TEMA), f"({len(h1)} tema)")
    cek("~1.900 frasa (skala sapuan)", len(semua) > 900, f"({len(semua)} frasa bersih)")
    cek("BLOKIR dibuang dari data (tidak ada kentut/keringat)", not any(U.diblokir(f) for f in semua))
    cek("deterministik", h1 == h2)
    t = "piramida"
    h = h1[t]
    skor = h["jml"] + h["kuat"] * 0.7 + h["niat"] * 0.9 + h["sains"] * 3 + h["yt"] * 0.3
    cek("rumus skor", abs(skor - h["skor"]) < 0.02, f"({h['skor']})")
    tum = skor + h["rel"] * 1.2 + h["kom"] * 1.5 + h["vis"] * 0.8 + h["ever"] * 3
    cek("rumus skor_tumbuh", abs(tum - h["skor_tumbuh"]) < 0.02, f"({h['skor_tumbuh']})")
    sudah = U.sudah_dibahas()
    cek("daftar SUDAH dari PUSTAKA.md terbaca", "kucing" in sudah and any("gempa" in s for s in sudah), f"({len(sudah)})")
    cek("tema sudah dibahas dikenali", U.tema_sudah("kucing", sudah) == "shorts" and U.tema_sudah("piramida", sudah) is None)
    cek("kata utuh (ai != baterai)", U.tema_sudah("ai", sudah) is None, str(U.tema_sudah("ai", sudah)))
    cek("lubang hitam = LONG (boleh Shorts)", U.tema_sudah("lubang hitam", sudah) == "long")
    d = Path(__file__).resolve().parent / "data" / "_uji"
    d.mkdir(parents=True, exist_ok=True)
    (d / "hasil_mendalam_20990101.json").write_text("{}", encoding="utf-8")
    cek("snapshot tulis/baca", U.snapshot_sebelum("hasil_mendalam", "20990102", d) == {})
    import shutil
    shutil.rmtree(d, ignore_errors=True)
    laporan(h1, sudah, 5)
    print("V3 SELFTEST:", "LULUS" if ok else "GAGAL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", default="online", choices=["online", "manual", "uji"])
    ap.add_argument("--tanggal", default=dt.date.today().strftime("%Y%m%d"))
    ap.add_argument("--uji", action="store_true")
    a = ap.parse_args()
    if a.uji:
        raise SystemExit(_uji())
    try:
        hasil = sapuan(a.mode)
    except U.Offline as e:
        raise SystemExit(f"[OFFLINE] autocomplete tidak terjangkau ({e}). Pakai --mode manual (data web search "
                         f"agen di analisis/data/manual_saran.json).")
    p = U.simpan(f"hasil_mendalam_{a.tanggal}.json", {"tanggal": a.tanggal, "mode": a.mode, "tema": hasil})
    laporan(hasil, U.sudah_dibahas())
    print(f"snapshot -> {p}")


if __name__ == "__main__":
    main()
