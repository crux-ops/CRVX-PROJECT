#!/usr/bin/env python3
"""analisis/v5_realtime.py - REAL-TIME: BFS kedalaman 2, VELOCITY, SUDAH-dibahas, KALENDER MOMEN, PABRIK METADATA.

  velocity   = pertumbuhan frasa vs snapshot sebelumnya (tema yang NAIK)
  momen      = event langit/musim dalam 45 hari (analisis/momen.json) -> 0..1
  skor_views = (jml + kuat + yt*2 + vis*0.8 + niat*0.6 + sains*2 + jaring*2) + velocity*4 + momen*6
Pabrik metadata (top-3): judul (3), deskripsi (baris pertama = kata kunci utama), hashtag, tag (<= 500 karakter),
semuanya ASCII dan dibentuk dari frasa autocomplete ASLI.
Keluaran: analisis/data/realtime_v5_<YYYYMMDD>.json + analisis/REALTIME_V5.md

Pakai: python3 analisis/v5_realtime.py [--mode online|manual]
Uji  : python3 analisis/v5_realtime.py --uji
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import umum as U  # noqa: E402
import v3_sapuan as V3  # noqa: E402
import v4_peta as V4  # noqa: E402


def _judul_kapital(f):
    kecil = {"di", "ke", "dan", "yang", "atau", "dari", "pada", "untuk", "itu"}
    w = f.split()
    return " ".join(x if (i and x in kecil) else x.capitalize() for i, x in enumerate(w))


def pabrik_metadata(tema, h3, peta=None):
    frasa = [f for f in h3["frasa"] if f.split()[0] in ("kenapa", "apakah", "bagaimana", "padahal")] or h3["frasa"]
    utama = frasa[0]
    inti = U.TEMA[tema][1][0]
    j1 = _judul_kapital(utama) + "? Ini Jawaban Sainsnya"
    j2 = _judul_kapital(frasa[1] if len(frasa) > 1 else utama) + "? Faktanya Mengejutkan"
    j3 = f"Fakta {inti.title()} yang Jarang Diketahui"
    judul = [U.ascii_saja(j)[:95] for j in (j1, j2, j3)]
    pilar = U.TEMA[tema][0]
    desk = [_judul_kapital(utama) + "?", "",
            f"Penjelasan ilmiah singkat tentang {inti}: dari nol sampai paham, dengan animasi tanpa ribet.", "",
            "Bab:", "0:00 Pertanyaan", "(timestamp diisi dari timeline.json)", "",
            "Sumber: (diisi saat riset - NASA/ESA/NOAA/NHS/Mayo Clinic/jurnal)"]
    if pilar == "tubuh":
        desk.append("Konten edukasi, bukan pengganti dokter.")
    tagar = ["#shorts", "#kliktahu", "#faktasains", "#" + "".join(inti.split())]
    tag, tot = [], 0
    for f in [inti, tema.replace("&", "dan")] + frasa + ((peta or {}).get("seri") or []):
        f = U.ascii_saja(f).strip()
        if f and f not in tag and tot + len(f) + 2 <= 500:
            tag.append(f)
            tot += len(f) + 2
    return {"judul": judul, "deskripsi": "\n".join(U.ascii_saja(x) for x in desk), "hashtag": " ".join(tagar),
            "tag": ", ".join(tag)}


def jalankan(mode="online", tanggal=None, hari_ini=None, data_dir=None, top_bfs=12):
    tanggal = tanggal or dt.date.today().strftime("%Y%m%d")
    hari_ini = hari_ini or dt.date.today()
    v3 = V3.sapuan(mode)
    prev = U.snapshot_sebelum("hasil_mendalam", tanggal, data_dir)
    prev_t = (prev or {}).get("tema", {})
    peta = {r["tema"]: r for r in V4.jalankan(mode, top_bfs, v3)}
    mom = U.momen(hari_ini)
    sudah = U.sudah_dibahas()
    rows = []
    for t, h in v3.items():
        st = U.tema_sudah(t, sudah)
        if st == "shorts":
            continue
        p = prev_t.get(t)
        vel = U.SKOR.v5_velocity(h["jml"], h["frasa"], p["jml"] if p else None, p.get("frasa", []) if p else None)
        ms, ev = U.momen_tema(t, mom)
        jaring = peta.get(t, {}).get("jaring", 0)
        sv = U.SKOR.v5_views(h, jaring, vel, ms)  # rumus prompt §8 (kliktahu/skor.py)
        rows.append({"tema": t, "pilar": h["pilar"], "status": st or "segar", "velocity": round(vel, 3),
                     "momen": ms, "momen_event": ev["nama"] if ev else None, "jaring": jaring,
                     "skor_views": round(sv, 2)})
    rows.sort(key=lambda r: -r["skor_views"])
    meta = {r["tema"]: pabrik_metadata(r["tema"], v3[r["tema"]], peta.get(r["tema"])) for r in rows[:3]}
    return {"tanggal": tanggal, "mode": mode, "ranking": rows, "metadata_top3": meta, "v3": v3}


def tulis_md(h):
    ln = [f"# REAL-TIME v5 - {h['tanggal']} (mode {h['mode']})", "",
          "| # | tema | pilar | status | velocity | momen | skor_views |", "|---|---|---|---|---|---|---|"]
    for i, r in enumerate(h["ranking"][:15], 1):
        m = f"{r['momen']:.2f} ({r['momen_event'][:40]})" if r["momen_event"] else "-"
        ln.append(f"| {i} | {r['tema']} | {r['pilar']} | {r['status']} | {r['velocity']:+.2f} | {m} | {r['skor_views']} |")
    ln += ["", "## Pabrik metadata (draft dari frasa autocomplete asli)", ""]
    for t, m in h["metadata_top3"].items():
        ln += [f"### {t}", "Judul:", *[f"- {j}" for j in m["judul"]], "", "Deskripsi:", "```", m["deskripsi"], "```",
               f"Hashtag: {m['hashtag']}", "", f"Tag: {m['tag']}", ""]
    p = U.DIR / "REALTIME_V5.md"
    p.write_text("\n".join(ln) + "\n", encoding="utf-8")
    return p


def _uji():
    import json
    import shutil
    ok = True

    def cek(nama, kond, det=""):
        nonlocal ok
        ok &= bool(kond)
        print(f"  [{'OK' if kond else 'GAGAL'}] {nama} {det}")

    d = U.DATA / "_uji_v5"
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    # snapshot kemarin palsu: 'pelangi' jauh lebih sedikit frasa -> velocity naik
    v3 = V3.sapuan("uji")
    kemarin = {t: {"jml": max(1, h["jml"] // (3 if t == "pelangi" else 1)), "frasa": h["frasa"][: (5 if t == "pelangi" else 999)]}
               for t, h in v3.items()}
    (d / "hasil_mendalam_20260924.json").write_text(json.dumps({"tema": kemarin}), encoding="utf-8")
    h = jalankan("uji", "20260925", dt.date(2026, 9, 25), d)
    rk = {r["tema"]: r for r in h["ranking"]}
    cek("tema SUDAH (Shorts) dikeluarkan", "kucing" not in rk and "petir" not in rk)
    cek("tema LONG tetap boleh (lubang hitam)", rk.get("lubang hitam", {}).get("status") == "long")
    cek("velocity: pelangi naik", rk["pelangi"]["velocity"] > 0.5, f"({rk['pelangi']['velocity']})")
    cek("momen: hari tanpa bayangan (11 Okt) terdongkrak", rk["hari tanpa bayangan"]["momen"] > 0.6,
        f"({rk['hari tanpa bayangan']['momen']})")
    r = rk["pelangi"]
    t3 = h["v3"]["pelangi"]
    exp = (t3["jml"] + t3["kuat"] + t3["yt"] * 2 + t3["vis"] * 0.8 + t3["niat"] * 0.6 + t3["sains"] * 2 + r["jaring"] * 2) \
        + r["velocity"] * 4 + r["momen"] * 6
    cek("rumus skor_views", abs(exp - r["skor_views"]) < 0.05)
    m = list(h["metadata_top3"].values())
    cek("metadata top-3 lengkap (3 judul, deskripsi, hashtag, tag)", len(m) == 3 and all(len(x["judul"]) == 3 and
        x["deskripsi"] and x["hashtag"] and x["tag"] for x in m))
    cek("metadata ASCII saja", all(U.ascii_saja(str(x)) == str(x) for x in m))
    cek("tag <= 500 karakter", all(len(x["tag"]) <= 500 for x in m), str([len(x["tag"]) for x in m]))
    cek("baris pertama deskripsi = kata kunci utama", all(x["deskripsi"].split("\n")[0].endswith("?") for x in m))
    shutil.rmtree(d, ignore_errors=True)
    print("V5 SELFTEST:", "LULUS" if ok else "GAGAL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", default="online", choices=["online", "manual", "uji"])
    ap.add_argument("--uji", action="store_true")
    a = ap.parse_args()
    if a.uji:
        raise SystemExit(_uji())
    try:
        h = jalankan(a.mode)
    except U.Offline as e:
        raise SystemExit(f"[OFFLINE] {e} - pakai --mode manual")
    U.simpan(f"hasil_mendalam_{h['tanggal']}.json", {"tanggal": h["tanggal"], "mode": a.mode, "tema": h["v3"]})
    U.simpan(f"realtime_v5_{h['tanggal']}.json", {k: v for k, v in h.items() if k != "v3"})
    print(f"-> {tulis_md(h)}")


if __name__ == "__main__":
    main()
