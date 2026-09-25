"""kliktahu/dasbor.py - DASBOR KANAL (tanpa aplikasi/server): terminal (rich) + laporan/DASBOR.md + laporan/dasbor.png.

Isi: ringkasan kanal & episode, status topik per pilar, keputusan riset terakhir, 10 peluang teratas (v7),
peta niche (permintaan vs celah), momen 60 hari, rencana 14 hari, performa per pilar, kesiapan kunci API
(hanya ada/belum - nilainya tidak pernah ditampilkan), kesegaran data.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from . import ROOT, momen
from . import kanal as kanal_mod
from .db import DB, hari_ini_wib
from .tema import TEMA

LAPORAN = ROOT / "laporan"
FONT = ROOT / "fonts"
PILAR = ("tubuh", "antariksa", "bumi", "hewan", "teknologi", "misteri")


def kumpulkan(db: DB, hari_ini: dt.date | None = None) -> dict[str, Any]:
    k = db.kanal
    hari_ini = hari_ini or hari_ini_wib()
    run = db.run_terakhir() or db.run_terakhir(mode=("uji",))
    top = db.skor_run(run["id"]) if run else []
    kep = None
    js = LAPORAN / ("_uji" if run and run["mode"] == "uji" else "") / "riset_terakhir.json"
    if run and js.exists():
        d = json.loads(js.read_text(encoding="utf-8"))
        kep = d.get("keputusan") if d.get("run_id") == run["id"] else None
    topik = db.daftar("topik")
    per_pilar = {p: {"segar": 0, "long": 0, "dibahas": 0, "lain": 0} for p in PILAR}
    for t in topik:
        per_pilar[t["pilar"]][t["status"] if t["status"] in ("segar", "long", "dibahas") else "lain"] += 1
    eps = db.daftar("episode", urut="kode")
    m60 = [m for m in momen.semua(hari_ini, 60) if m.tanggal >= hari_ini]
    live = db.daftar(
        "momen",
        "jenis IN ('live','agen') AND tanggal >= ?",
        ((hari_ini - dt.timedelta(days=3)).isoformat(),),
        urut="tanggal",
    )
    rencana = db.daftar(
        "rencana",
        "tanggal BETWEEN ? AND ?",
        (hari_ini.isoformat(), (hari_ini + dt.timedelta(days=14)).isoformat()),
        urut="tanggal, jam",
    )
    r = k.riset
    return {
        "hari_ini": hari_ini.isoformat(),
        "kanal": k.nama,
        "niche": k.niche,
        "berikut": {"shorts": db.kode_berikut("shorts"), "long": db.kode_berikut("long")},
        "statistik": db.statistik(),
        "per_pilar": per_pilar,
        "episode": {
            "total": len(eps),
            "rilis": sum(e["status"] == "rilis" for e in eps),
            "produksi": sum(e["status"] not in ("rilis", "arsip") for e in eps),
            "daftar": eps[-8:],
        },
        "run": run,
        "umur_data_hari": (hari_ini - dt.date.fromisoformat(run["tanggal"])).days if run else None,
        "keputusan": kep,
        "top": top[:20],
        "momen": m60[:12],
        "momen_live": live[:6],
        "rencana": rencana,
        "performa": db.performa_pilar(),
        "kunci": {
            r.env_youtube_key: bool(r.rahasia(r.env_youtube_key)),
            r.env_brave_key: bool(r.rahasia(r.env_brave_key)),
            r.env_searxng_url: bool(r.rahasia(r.env_searxng_url)),
        },
    }


# ------------------------------------------------------------------------------------------------ terminal
def terminal(d: dict[str, Any]) -> None:
    try:
        from rich import box
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
    except ImportError:  # pragma: no cover
        print(markdown(d))
        return
    c = Console()
    run = d["run"]
    kepala = (
        f"[bold]{d['kanal']}[/] - {d['niche']}   |   hari ini {d['hari_ini']}   |   berikutnya "
        f"[bold]{d['berikut']['shorts']}[/] & [bold]{d['berikut']['long']}[/]\n"
        f"Episode: {d['episode']['total']} (rilis {d['episode']['rilis']}, produksi {d['episode']['produksi']})   "
        f"Riset terakhir: "
        + (
            f"#{run['id']} {run['tanggal']} ({run['mode']}, umur {d['umur_data_hari']} hari)"
            if run
            else "[red]belum ada - jalankan: python3 -m kliktahu riset[/]"
        )
    )
    c.print(Panel(kepala, title="DASBOR KANAL", border_style="cyan"))
    if d["keputusan"]:
        kp = d["keputusan"]
        c.print(
            Panel(
                f"[bold green]{kp['tema']}[/] ({kp['pilar']}) - {kp['format'].upper()} - peluang {kp['peluang']} "
                f"- keyakinan {kp['keyakinan']:.0%}"
                + (f" - tayang <= {kp['tayang_paling_lambat']}" if kp.get("tayang_paling_lambat") else "")
                + "\n"
                + "\n".join("- " + a for a in kp["alasan"][:4]),
                title="KEPUTUSAN RISET",
                border_style="green",
            )
        )
    t = Table(title="Peluang teratas (v7)", box=box.SIMPLE_HEAVY)
    for kol in ("#", "tema", "pilar", "status", "peluang", "yakin", "v6", "momen"):
        t.add_column(kol)
    for r in d["top"][:10]:
        t.add_row(
            str(r["peringkat"]),
            r["nama"],
            r["pilar"],
            r["status_topik"],
            f"{r['v7_peluang']:.1f}",
            f"{r['keyakinan']:.0%}",
            f"{r['v6_papan']:.1f}",
            (r["sinyal"].get("momen_nama") or "-")[:38],
        )
    c.print(t)
    tp = Table(title="Topik per pilar", box=box.SIMPLE)
    for kol in ("pilar", "segar", "long", "dibahas"):
        tp.add_column(kol)
    for p, v in d["per_pilar"].items():
        tp.add_row(p, str(v["segar"]), str(v["long"]), str(v["dibahas"]))
    c.print(tp)
    tm = Table(title="Momen 60 hari", box=box.SIMPLE)
    for kol in ("tanggal", "jenis", "momen"):
        tm.add_column(kol)
    for m in d["momen"]:
        tm.add_row(str(m.tanggal), m.jenis, m.nama[:80])
    c.print(tm)
    if d["rencana"]:
        tr = Table(title="Rencana 14 hari", box=box.SIMPLE)
        for kol in ("tanggal", "jam", "format", "kode", "topik", "status"):
            tr.add_column(kol)
        for r in d["rencana"]:
            tr.add_row(
                r["tanggal"], r["jam"], r["format"], r["episode_kode"] or "-", r["judul_kerja"] or "-", r["status"]
            )
        c.print(tr)
    c.print(
        "Kunci API: " + ", ".join(f"{n} {'[green]ada[/]' if v else '[yellow]belum[/]'}" for n, v in d["kunci"].items())
    )


# ------------------------------------------------------------------------------------------------ markdown
def markdown(d: dict[str, Any]) -> str:
    run = d["run"]
    L = [
        f"# DASBOR KANAL {d['kanal']} - {d['hari_ini']}",
        "",
        f"- Niche: {d['niche']} | episode berikutnya: **{d['berikut']['shorts']}** (Shorts), **{d['berikut']['long']}** (Long)",
        f"- Episode di basis data: {d['episode']['total']} (rilis {d['episode']['rilis']}, produksi {d['episode']['produksi']})",
        "- Riset terakhir: "
        + (
            f"run #{run['id']} {run['tanggal']} mode {run['mode']} (umur {d['umur_data_hari']} hari)"
            if run
            else "belum ada"
        ),
        "- Kunci API: " + ", ".join(f"{n}: {'ada' if v else 'belum'}" for n, v in d["kunci"].items()),
        "",
    ]
    if d["keputusan"]:
        kp = d["keputusan"]
        L += [
            "## Keputusan riset",
            "",
            f"**{kp['tema']}** ({kp['pilar']}) - {kp['format']} - peluang {kp['peluang']} - "
            f"keyakinan {kp['keyakinan']:.0%}"
            + (f" - tayang paling lambat {kp['tayang_paling_lambat']}" if kp.get("tayang_paling_lambat") else ""),
            "",
            *[f"- {a}" for a in kp["alasan"]],
            "",
        ]
    L += [
        "## Peluang teratas (v7)",
        "",
        "| # | tema | pilar | status | peluang | yakin | v6 | momen |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in d["top"][:10]:
        L.append(
            f"| {r['peringkat']} | {r['nama']} | {r['pilar']} | {r['status_topik']} | {r['v7_peluang']:.1f} | "
            f"{r['keyakinan']:.0%} | {r['v6_papan']:.1f} | {r['sinyal'].get('momen_nama') or '-'} |"
        )
    L += ["", "## Topik per pilar", "", "| pilar | segar | long | dibahas |", "|---|---|---|---|"]
    L += [f"| {p} | {v['segar']} | {v['long']} | {v['dibahas']} |" for p, v in d["per_pilar"].items()]
    L += ["", "## Momen 60 hari", "", "| tanggal | jenis | momen |", "|---|---|---|"]
    L += [f"| {m.tanggal} | {m.jenis} | {m.nama} |" for m in d["momen"]]
    if d["rencana"]:
        L += [
            "",
            "## Rencana 14 hari",
            "",
            "| tanggal | jam | format | kode | topik | status |",
            "|---|---|---|---|---|---|",
        ]
        L += [
            f"| {r['tanggal']} | {r['jam']} | {r['format']} | {r['episode_kode'] or '-'} | {r['judul_kerja'] or '-'} | "
            f"{r['status']} |"
            for r in d["rencana"]
        ]
    if d["performa"]:
        L += [
            "",
            "## Performa per pilar (YouTube Studio)",
            "",
            "| pilar | video | tayangan median | retensi rata-rata |",
            "|---|---|---|---|",
        ]
        L += [
            f"| {p} | {int(v['n'])} | {int(v['tayangan_median'])} | {v['retensi_rata']:.1f}% |"
            for p, v in d["performa"].items()
        ]
    L += ["", "Basis data: " + ", ".join(f"{t} {n}" for t, n in d["statistik"].items())]
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------------------------------------ PNG
def _f(berat: str, ukuran: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT / f"Poppins-{berat}.ttf"), ukuran)


def _hex(h: str) -> tuple[int, int, int]:
    return (int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16))


def png(d: dict[str, Any], path: Path, k: kanal_mod.Kanal | None = None) -> Path:
    k = k or kanal_mod.muat()
    W, H = 1600, 1000
    CREAM, INK, MUTED = k.merek.cream, k.merek.ink, k.merek.muted
    warna = {p: _hex(k.merek.aksen[i % len(k.merek.aksen)]) for i, p in enumerate(PILAR)}
    im = Image.new("RGB", (W, H), CREAM)
    g = ImageDraw.Draw(im)
    putih = (255, 255, 255)

    def kartu(x: int, y: int, w: int, h: int, judul: str) -> None:
        g.rounded_rectangle((x + 4, y + 6, x + w + 4, y + h + 6), 22, fill=(228, 221, 208))
        g.rounded_rectangle((x, y, x + w, y + h), 22, fill=putih)
        g.text((x + 24, y + 18), judul, font=_f("SemiBold", 22), fill=INK)

    g.text((48, 30), d["kanal"], font=_f("Bold", 54), fill=INK)
    g.text(
        (48 + g.textlength(d["kanal"], font=_f("Bold", 54)) + 18, 52),
        f"Dasbor kanal - {d['hari_ini']}",
        font=_f("Medium", 26),
        fill=MUTED,
    )
    kanan = f"Berikutnya: {d['berikut']['shorts']}  |  {d['berikut']['long']}"
    g.text((W - 48 - g.textlength(kanan, font=_f("SemiBold", 26)), 52), kanan, font=_f("SemiBold", 26), fill=INK)

    run = d["run"]
    seg = sum(v["segar"] for v in d["per_pilar"].values())
    sudah = sum(v["dibahas"] + v["long"] for v in d["per_pilar"].values())
    yakin = (d["keputusan"] or {}).get("keyakinan")
    kpi = [
        ("Topik segar", str(seg)),
        ("Sudah dibahas", str(sudah)),
        ("Episode (rilis)", f"{d['episode']['total']} ({d['episode']['rilis']})"),
        ("Riset terakhir", f"#{run['id']} {run['mode']}" if run else "-"),
        ("Keyakinan data", f"{yakin:.0%}" if yakin is not None else "-"),
    ]
    cw = (W - 96 - 4 * 20) // 5
    for i, (lab, val) in enumerate(kpi):
        x = 48 + i * (cw + 20)
        kartu(x, 118, cw, 118, lab)
        g.text((x + 24, 160), val, font=_f("Bold", 40), fill=warna[PILAR[i % 6]])

    # peluang teratas
    kartu(48, 262, 760, 520, "Peluang teratas (v7, 0-100)")
    top = d["top"][:10]
    fn = _f("Medium", 21)
    lebar_nama = max([int(g.textlength(f"{r['peringkat']:>2}. {r['nama'][:24]}", font=fn)) for r in top] or [200])
    bx = 72 + lebar_nama + 18
    bw_maks = 760 - (bx - 48) - 76
    for i, r in enumerate(top):
        y = 312 + i * 43
        g.text((72, y), f"{r['peringkat']:>2}. {r['nama'][:24]}", font=fn, fill=INK)
        bw = int(bw_maks * r["v7_peluang"] / 100)
        g.rounded_rectangle((bx, y + 6, bx + bw_maks, y + 30), 12, fill=(238, 233, 224))
        g.rounded_rectangle((bx, y + 6, bx + max(24, bw), y + 30), 12, fill=warna[r["pilar"]])
        g.text((bx + bw_maks + 12, y + 2), f"{r['v7_peluang']:.0f}", font=_f("SemiBold", 21), fill=INK)
    ly, lx = 312 + 10 * 43 + 4, 72
    for p in PILAR:
        g.ellipse((lx, ly + 8, lx + 14, ly + 22), fill=warna[p])
        g.text((lx + 20, ly), p, font=_f("Regular", 17), fill=MUTED)
        lx += 20 + int(g.textlength(p, font=_f("Regular", 17))) + 22

    # peta niche (skala min-maks titik yang tampil agar sebaran terlihat)
    kartu(832, 262, 720, 520, "Peta niche: permintaan (x) vs celah pesaing (y)")
    x0, y0, pw, ph = 890, 320, 600, 400
    g.rectangle((x0, y0, x0 + pw, y0 + ph), outline=(225, 218, 205), width=2)
    g.line((x0 + pw // 2, y0, x0 + pw // 2, y0 + ph), fill=(225, 218, 205), width=2)
    g.line((x0, y0 + ph // 2, x0 + pw, y0 + ph // 2), fill=(225, 218, 205), width=2)
    g.text((x0 + pw - 150, y0 + 8), "PELUANG EMAS", font=_f("SemiBold", 17), fill=MUTED)
    g.text((x0, y0 + ph + 8), "permintaan rendah", font=_f("Regular", 16), fill=MUTED)
    g.text((x0 + pw - 128, y0 + ph + 8), "permintaan tinggi", font=_f("Regular", 16), fill=MUTED)
    tampil = sorted(d["top"][:20], key=lambda r: r["v7_peluang"])
    xs = [r["komponen"]["permintaan"] for r in tampil] or [0.0]
    ys = [r["komponen"]["celah"] for r in tampil] or [0.0]

    def sk(v: float, lo: float, hi: float) -> float:
        return 0.5 if hi - lo < 1e-6 else 0.06 + 0.88 * (v - lo) / (hi - lo)

    kotak: list[tuple[int, int, int, int]] = []
    for r in tampil:
        kp = r["komponen"]
        cx = x0 + int(sk(kp["permintaan"], min(xs), max(xs)) * pw)
        cy = y0 + ph - int(sk(kp["celah"], min(ys), max(ys)) * ph)
        rad = int(6 + r["v7_peluang"] / 8)
        g.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), fill=warna[r["pilar"]], outline=putih, width=2)
        if r["peringkat"] <= 5:
            lab = r["nama"][:20]
            fw = int(g.textlength(lab, font=_f("Medium", 17)))
            lx2 = cx + rad + 4 if cx + rad + 4 + fw < x0 + pw else cx - rad - 4 - fw
            ly2 = cy - 12
            while any(not (lx2 + fw < a or lx2 > c or ly2 + 22 < b or ly2 > e) for a, b, c, e in kotak):
                ly2 += 22
            kotak.append((lx2, ly2, lx2 + fw, ly2 + 22))
            g.text((lx2, ly2), lab, font=_f("Medium", 17), fill=INK)

    # momen + keputusan
    kartu(48, 806, 1504, 166, "Momen 60 hari & keputusan")
    mx = 72
    for m in d["momen"][:6]:
        pendek = m.nama.split("(")[0].strip()
        if ":" in pendek:
            a_, b_ = pendek.split(":", 1)
            pendek = f"{a_.strip()} - {(b_.split(',')[0].split() or [''])[0]}"
        teks_m = f"{m.tanggal:%d/%m} {pendek[:36]}"
        w = int(g.textlength(teks_m, font=_f("Medium", 17))) + 28
        if mx + w > W - 72:
            break
        g.rounded_rectangle((mx, 852, mx + w, 884), 16, fill=(238, 233, 224))
        g.text((mx + 14, 857), teks_m, font=_f("Medium", 17), fill=INK)
        mx += w + 12
    kp = d["keputusan"]
    kal = (
        f"Keputusan: {kp['tema']} ({kp['format']}) - peluang {kp['peluang']} - keyakinan {kp['keyakinan']:.0%}"
        + (f" - tayang paling lambat {kp['tayang_paling_lambat']}" if kp.get("tayang_paling_lambat") else "")
        if kp
        else "Keputusan: belum ada riset - jalankan python3 -m kliktahu riset"
    )
    g.text((72, 906), kal, font=_f("SemiBold", 24), fill=INK)
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, optimize=True)
    return path


def muat_tema_ada(nama: str) -> bool:
    return nama in TEMA
