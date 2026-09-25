#!/usr/bin/env python3
"""analisis/v6_strategi.py - PAPAN STRATEGI 0-100 + kalender 7 episode + sekuel.

papan = 34 permintaan (v5 dinormalisasi) + 18 Wikipedia (pageview id.wikipedia 60 hari, tren 30 vs 30 hari)
      + 18 celah (1 - kejenuhan pesaing YouTube: jumlah/umur/median views) + 10 visual + 10 pilar + 10 momen
Plus: penambang SUDUT (frasa KENAPA/PADAHAL/APAKAH yang belum dipakai judul pesaing), generator HOOK
(daftar hindari: haram/halal/agama/dosa/harga/brand/game; benih > 5 kata dibuang), loop performa dari
performa.csv (views/retensi YouTube Studio -> bobot pilar). Keluaran: analisis/STRATEGI_V6.md.

Sumber Wikipedia/pesaing: online bila bisa; bila sandbox offline -> data manual (hasil web search agen)
analisis/data/manual_wiki.json & manual_pesaing.json; bila tidak ada -> NETRAL 0.5 (ditandai di laporan).

Pakai: python3 analisis/v6_strategi.py [--mode online|manual] [--performa analisis/performa.csv]
Uji  : python3 analisis/v6_strategi.py --uji
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import umum as U  # noqa: E402
import v5_realtime as V5  # noqa: E402

JAM_UNGGAH = ["11.30-12.30 WIB", "18.30-20.30 WIB"]


def _norm01(vals):
    lo, hi = min(vals), max(vals)
    return [0.5 if hi - lo < 1e-9 else (v - lo) / (hi - lo) for v in vals]


def bobot_pilar(path):
    """performa.csv: episode,pilar,views,retensi(%) -> bobot 0..1 per pilar (views x retensi rata-rata)."""
    if not path or not Path(path).exists():
        return {p: 0.5 for p in U.PILAR}, False
    agg = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            p = row.get("pilar", "").strip()
            try:
                v = float(row["views"]) * float(row["retensi"]) / 100.0
            except (KeyError, ValueError):
                continue
            agg.setdefault(p, []).append(v)
    if not agg:
        return {p: 0.5 for p in U.PILAR}, False
    rata = {p: sum(v) / len(v) for p, v in agg.items()}
    mx = max(rata.values())
    return {p: round(0.25 + 0.75 * rata.get(p, 0) / mx, 3) if p in rata else 0.4 for p in U.PILAR}, True


def skor_wiki(d):
    """d = {views60, tren (rasio 30 hari terakhir / 30 hari sebelumnya)} -> 0..1."""
    import math
    v = min(1.0, math.log10(max(1, d.get("views60", 0))) / 5.0)  # 100k views/60 hari ~ 1.0
    tr = min(1.0, max(0.0, (d.get("tren", 1.0) - 0.7) / 0.9))
    return round(0.65 * v + 0.35 * tr, 3)


def skor_celah(d):
    """kejenuhan pesaing: banyak video, baru, views tinggi = jenuh. celah = 1 - kejenuhan."""
    jml = min(1.0, d.get("jumlah", 0) / 40.0)
    baru = 1.0 - min(1.0, d.get("umur_median_hari", 730) / 730.0)
    views = min(1.0, d.get("median_views", 0) / 500000.0)
    return round(1.0 - (0.45 * jml + 0.2 * baru + 0.35 * views), 3)


def sudut(tema, v3, judul_pesaing):
    tj = " ".join(U.norm(j) for j in judul_pesaing)
    out = []
    for f in v3[tema]["frasa"]:
        w = f.split()
        if w and w[0] in ("kenapa", "padahal", "apakah") and len(w) >= 3:
            inti_frasa = " ".join(w[1:])
            if inti_frasa not in tj:
                out.append(f)
    return out[:3]


def hook(tema, v3):
    out = []
    for f in v3[tema]["frasa"]:
        w = f.split()
        if len(w) > 5 or any(h in f for h in U.HINDARI_HOOK):
            continue
        if w[0] == "kenapa":
            out.append(f"{f.capitalize()}? Padahal kamu melihatnya setiap hari.")
        elif w[0] == "apakah":
            out.append(f"{f.capitalize()}? Jawabannya tidak seperti yang kamu kira.")
        elif w[0] == "padahal":
            out.append(f"{f.capitalize()}... lalu kenapa?")
        if len(out) >= 2:
            break
    return [U.ascii_saja(h) for h in out]


def jalankan(mode="online", performa=None, hari_ini=None, data_dir=None, wiki=None, pesaing=None):
    hari_ini = hari_ini or dt.date.today()
    h5 = V5.jalankan(mode, hari_ini.strftime("%Y%m%d"), hari_ini, data_dir)
    v3 = h5["v3"]
    rows = h5["ranking"]
    if wiki is None:
        p = U.DATA / "manual_wiki.json"
        wiki = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    if pesaing is None:
        p = U.DATA / "manual_pesaing.json"
        pesaing = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    bp, ada_perf = bobot_pilar(performa)
    perm = _norm01([r["skor_views"] for r in rows])
    visn = _norm01([v3[r["tema"]]["vis"] for r in rows])
    papan = []
    for r, pn, vn in zip(rows, perm, visn):
        t = r["tema"]
        w = skor_wiki(wiki[t]) if t in wiki else 0.5
        c = skor_celah(pesaing[t]) if t in pesaing else 0.5
        vis = 0.5 * vn + 0.5 * U.TEMA[t][4]
        total = 34 * pn + 18 * w + 18 * c + 10 * vis + 10 * bp.get(r["pilar"], 0.5) + 10 * r["momen"]
        papan.append({**r, "permintaan": round(pn, 3), "wiki": w, "wiki_netral": t not in wiki, "celah": c,
                      "celah_netral": t not in pesaing, "visual": round(vis, 3), "pilar_w": bp.get(r["pilar"], 0.5),
                      "papan": round(total, 1), "sudut": sudut(t, v3, pesaing.get(t, {}).get("judul", [])),
                      "hook": hook(t, v3)})
    papan.sort(key=lambda x: -x["papan"])
    kal = kalender(papan, hari_ini)
    return {"tanggal": hari_ini.isoformat(), "mode": mode, "papan": papan, "kalender": kal, "performa": ada_perf,
            "metadata_top3": h5["metadata_top3"]}


def kalender(papan, hari_ini):
    """7 episode, satu pilar tidak dobel berturut-turut; tema bermomen dijadwalkan SEBELUM event-nya."""
    segar = [p for p in papan if p["status"] != "shorts"]
    pilih, sisa = [], list(segar)
    tgl = hari_ini + dt.timedelta(days=1)
    for i in range(7):
        kandidat = None
        for p in sisa:
            if pilih and p["pilar"] == pilih[-1]["pilar"] and len(sisa) > 1:
                continue
            kandidat = p
            break
        kandidat = kandidat or sisa[0]
        sisa.remove(kandidat)
        pilih.append({"tanggal": (tgl + dt.timedelta(days=i)).isoformat(), "jam": JAM_UNGGAH[i % 2],
                      "tema": kandidat["tema"], "pilar": kandidat["pilar"], "papan": kandidat["papan"],
                      "momen": kandidat.get("momen_event"), "sekuel": (kandidat["sudut"][1:2] or [""])[0]})
    return pilih


def tulis_md(h, path=None):
    ln = [f"# STRATEGI v6 - {h['tanggal']} (mode {h['mode']})", "",
          "Papan 0-100 = 34 permintaan + 18 Wikipedia + 18 celah pesaing + 10 visual + 10 pilar + 10 momen.",
          "(n) = komponen NETRAL 0.5 karena data belum ada (sandbox offline / data manual belum diisi).", "",
          "| # | tema | pilar | papan | permintaan | wiki | celah | visual | momen | sudut pembeda |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for i, p in enumerate(h["papan"][:15], 1):
        ln.append(f"| {i} | {p['tema']} | {p['pilar']} | **{p['papan']}** | {p['permintaan']:.2f} | {p['wiki']:.2f}"
                  f"{' (n)' if p['wiki_netral'] else ''} | {p['celah']:.2f}{' (n)' if p['celah_netral'] else ''} | "
                  f"{p['visual']:.2f} | {p['momen']:.2f} | {(p['sudut'] or ['-'])[0]} |")
    ln += ["", "## Kalender 7 episode", "", "| tanggal | jam unggah | tema | pilar | momen | sekuel |", "|---|---|---|---|---|---|"]
    for k in h["kalender"]:
        ln.append(f"| {k['tanggal']} | {k['jam']} | {k['tema']} | {k['pilar']} | {k['momen'] or '-'} | {k['sekuel'] or '-'} |")
    ln += ["", "## Hook (3 detik pertama) untuk 3 teratas", ""]
    for p in h["papan"][:3]:
        ln.append(f"- **{p['tema']}**: " + (" | ".join(p["hook"]) or "-"))
    ln += ["", f"Loop performa (performa.csv): {'AKTIF' if h['performa'] else 'belum ada data - bobot pilar netral'}"]
    p = Path(path) if path else U.DIR / "STRATEGI_V6.md"
    p.write_text("\n".join(ln) + "\n", encoding="utf-8")
    return p


def _uji():
    import shutil
    ok = True

    def cek(nama, kond, det=""):
        nonlocal ok
        ok &= bool(kond)
        print(f"  [{'OK' if kond else 'GAGAL'}] {nama} {det}")

    d = U.DATA / "_uji_v6"
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    perf = d / "performa.csv"
    perf.write_text("episode,pilar,views,retensi\nEp40,antariksa,90000,78\nEp41,tubuh,30000,60\nEp42,antariksa,120000,81\n",
                    encoding="utf-8")
    wiki = {"piramida": {"views60": 90000, "tren": 1.4}, "cegukan": {"views60": 4000, "tren": 0.8}}
    pes = {"piramida": {"jumlah": 60, "umur_median_hari": 120, "median_views": 800000,
                        "judul": ["Kenapa Piramida Dibangun? Misteri Mesir"]},
           "cegukan": {"jumlah": 5, "umur_median_hari": 900, "median_views": 20000, "judul": []}}
    h = jalankan("uji", str(perf), dt.date(2026, 9, 25), d, wiki, pes)
    p0 = h["papan"]
    cek("papan 0..100", all(0 <= p["papan"] <= 100 for p in p0), f"(maks {max(p['papan'] for p in p0)})")
    bp, ada = bobot_pilar(str(perf))
    cek("loop performa: antariksa > tubuh", ada and bp["antariksa"] > bp["tubuh"], str(bp))
    pk = {p["tema"]: p for p in p0}
    cek("celah: cegukan (sepi pesaing) > piramida (jenuh)", pk["cegukan"]["celah"] > pk["piramida"]["celah"])
    cek("wiki: piramida > cegukan", pk["piramida"]["wiki"] > pk["cegukan"]["wiki"])
    cek("sudut: frasa yang sudah dipakai judul pesaing tidak muncul",
        all("piramida dibangun" not in s for s in pk["piramida"]["sudut"]), str(pk["piramida"]["sudut"]))
    semua_hook = [x for p in p0 for x in p["hook"]]
    cek("hook bebas daftar hindari", not any(w in x.lower() for x in semua_hook for w in U.HINDARI_HOOK))
    k = h["kalender"]
    cek("kalender 7 episode, tema unik & segar", len(k) == 7 and len({x["tema"] for x in k}) == 7
        and all(U.tema_sudah(x["tema"]) != "shorts" for x in k))
    cek("jam unggah terbaik (WIB)", all(x["jam"] in JAM_UNGGAH for x in k))
    cek("pilar tidak dobel berturut-turut", all(k[i]["pilar"] != k[i + 1]["pilar"] for i in range(6)))
    cek("BLOKIR tidak masuk papan", not any(U.diblokir(p["tema"]) for p in p0))
    md = tulis_md(h, d / "STRATEGI_V6.md")
    cek("laporan STRATEGI_V6.md tertulis", md.exists() and "Kalender 7 episode" in md.read_text(encoding="utf-8"))
    shutil.rmtree(d, ignore_errors=True)
    print("V6 SELFTEST:", "LULUS" if ok else "GAGAL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", default="online", choices=["online", "manual", "uji"])
    ap.add_argument("--performa", default=str(U.DIR / "performa.csv"))
    ap.add_argument("--uji", action="store_true")
    a = ap.parse_args()
    if a.uji:
        raise SystemExit(_uji())
    try:
        h = jalankan(a.mode, a.performa)
    except U.Offline as e:
        raise SystemExit(f"[OFFLINE] {e} - pakai --mode manual")
    U.simpan(f"strategi_v6_{h['tanggal'].replace('-', '')}.json", h)
    print(f"-> {tulis_md(h)}")


if __name__ == "__main__":
    main()
