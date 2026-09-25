#!/usr/bin/env python3
"""analisis/v4_peta.py - PEMETA PELUANG: pohon tema -> cabang konteks -> daun kedalaman 2 -> rencana SERI.

Cabang: "kenapa <inti> <aspek>", "apakah <inti> <aspek>", "kapan <inti> bahaya" + frasa panjang terbaik v3.
  skor_keluarga = skor_tumbuh + jaring*2.5 + kedalaman*1.5 + peluang*2
    jaring    = jumlah cabang yang punya daun
    kedalaman = rata-rata kedalaman tercapai (1..2)
    peluang   = jumlah frasa long-tail (>= 5 kata)
Keluaran: analisis/data/peta_v4_<YYYYMMDD>.json + analisis/PETA_V4.md

Pakai: python3 analisis/v4_peta.py [--mode online|manual] [--top 15]
Uji  : python3 analisis/v4_peta.py --uji
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import umum as U  # noqa: E402
import v3_sapuan as V3  # noqa: E402


def cabang(tema, h3=None):
    inti = U.TEMA[tema][1][0]
    aspek = U.TEMA[tema][2]
    out = [f"kenapa {inti} {a}" for a in aspek] + [f"apakah {inti} {a}" for a in aspek[:2]] + [f"kapan {inti} bahaya"]
    if h3:
        out += [f for f in h3.get("frasa", []) if len(f.split()) >= 4][:3]
    return list(dict.fromkeys(U.norm(c) for c in out if not U.diblokir(c)))


def petakan(tema, h3, mode):
    cab = []
    for c in cabang(tema, h3):
        d1 = [f for f in (U.bersih(s) for s in U.ambil_saran(c, "google", mode)) if f and f != c]
        d2 = []
        for leaf in d1[:2]:
            d2 += [f for f in (U.bersih(s) for s in U.ambil_saran(leaf, "google", mode)) if f and f not in d1]
        cab.append({"cabang": c, "d1": d1[:8], "d2": list(dict.fromkeys(d2))[:8], "kedalaman": 2 if d2 else (1 if d1 else 0)})
    punya = [c for c in cab if c["d1"]]
    jaring = len(punya)
    kedalaman = sum(c["kedalaman"] for c in punya) / max(1, jaring)
    semua = {f for c in cab for f in c["d1"] + c["d2"]}
    peluang = sum(1 for f in semua if len(f.split()) >= 5)
    skor = h3["skor_tumbuh"] + jaring * 2.5 + kedalaman * 1.5 + peluang * 2
    seri = [c["cabang"] for c in sorted(punya, key=lambda c: -(len(c["d1"]) + len(c["d2"])))[:4]]
    return {"tema": tema, "pilar": h3["pilar"], "jaring": jaring, "kedalaman": round(kedalaman, 2), "peluang": peluang,
            "skor_keluarga": round(skor, 2), "seri": seri, "cabang": cab}


def jalankan(mode="online", top=15, v3=None):
    v3 = v3 or V3.sapuan(mode)
    sudah = U.sudah_dibahas()
    kandidat = [t for t, h in sorted(v3.items(), key=lambda kv: -kv[1]["skor_tumbuh"])
                if U.tema_sudah(t, sudah) != "shorts"][:top]
    return sorted((petakan(t, v3[t], mode) for t in kandidat), key=lambda r: -r["skor_keluarga"])


def tulis_md(hasil, tanggal):
    ln = [f"# PETA PELUANG v4 - {tanggal}", "", "| # | tema | pilar | jaring | kedalaman | long-tail | skor keluarga |",
          "|---|---|---|---|---|---|---|"]
    for i, r in enumerate(hasil, 1):
        ln.append(f"| {i} | {r['tema']} | {r['pilar']} | {r['jaring']} | {r['kedalaman']} | {r['peluang']} | {r['skor_keluarga']} |")
    ln += ["", "## Rencana SERI (4 episode per keluarga teratas)", ""]
    for r in hasil[:5]:
        ln.append(f"- **{r['tema']}**: " + " / ".join(r["seri"]))
    p = U.DIR / "PETA_V4.md"
    p.write_text("\n".join(ln) + "\n", encoding="utf-8")
    return p


def _uji():
    ok = True

    def cek(nama, kond, det=""):
        nonlocal ok
        ok &= bool(kond)
        print(f"  [{'OK' if kond else 'GAGAL'}] {nama} {det}")

    hasil = jalankan("uji", 10)
    cek("10 keluarga terpetakan", len(hasil) == 10)
    cek("tanpa tema yang sudah jadi Shorts", all(U.tema_sudah(r["tema"]) != "shorts" for r in hasil))
    r = hasil[0]
    v3 = V3.sapuan("uji")
    exp = v3[r["tema"]]["skor_tumbuh"] + r["jaring"] * 2.5 + r["kedalaman"] * 1.5 + r["peluang"] * 2
    cek("rumus skor keluarga", abs(exp - r["skor_keluarga"]) < 0.05, f"({r['tema']}: {r['skor_keluarga']})")
    cek("kedalaman 2 tercapai", any(c["kedalaman"] == 2 for c in r["cabang"]))
    cek("rencana seri 2-4 episode", 2 <= len(r["seri"]) <= 4, str(r["seri"]))
    semua = [f for x in hasil for c in x["cabang"] for f in c["d1"] + c["d2"]]
    cek("BLOKIR tidak ada di daun", not any(U.diblokir(f) for f in semua))
    print("V4 SELFTEST:", "LULUS" if ok else "GAGAL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", default="online", choices=["online", "manual", "uji"])
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--uji", action="store_true")
    a = ap.parse_args()
    if a.uji:
        raise SystemExit(_uji())
    tanggal = dt.date.today().strftime("%Y%m%d")
    try:
        hasil = jalankan(a.mode, a.top)
    except U.Offline as e:
        raise SystemExit(f"[OFFLINE] {e} - pakai --mode manual")
    U.simpan(f"peta_v4_{tanggal}.json", {"tanggal": tanggal, "hasil": hasil})
    print(f"-> {tulis_md(hasil, tanggal)}")


if __name__ == "__main__":
    main()
