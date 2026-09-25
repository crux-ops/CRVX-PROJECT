"""python3 -m kliktahu <perintah> - NAVIGASI satu pintu untuk lapisan data/riset/metadata/perencana/dasbor.

kanal     cek | lihat                        pengaturan kanal (kanal.toml)
db        init | status | ekspor | impor | bersihkan-blokir
skema     tulis | cek                        turunan skema (SQLite, Postgres/Bolt, JSON Schema, TypeScript)
riset     [--mode online|agen|uji] [--agen FILE] [--tema a,b]      riset real-time + keputusan + metadata
putuskan                                     tampilkan keputusan riset terakhir
metadata  buat ... | cek FILE                generator & lint METADATA.md
pustaka   daftar | cari | tambah | status | sinkron | impor-studio | duplikat
rencana   [--minggu 4] | kunci TGL JAM FORMAT   kalender konten + ICS
momen     [--hari 60]                        momen (kurasi + astronomi + live dari riset terakhir)
astro     [--tahun N] [--kota NAMA]          hitungan astronomi offline
dasbor    [--png] [--md]                     dasbor kanal (terminal + laporan)
sinkron   cek | dorong | tarik               cermin Bolt Database / Supabase (env var)
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from . import ROOT, __version__


def _tgl(s: str | None) -> dt.date | None:
    return dt.date.fromisoformat(s) if s else None


def cmd_kanal(a: argparse.Namespace) -> int:
    from . import kanal

    try:
        k = kanal.muat(a.file)
    except kanal.KanalError as e:
        print(f"[GAGAL] {e}")
        return 2
    print(f"kanal.toml SAH ({k.path})")
    for lab, val in kanal.ringkas(k):
        print(f"  {lab:<34} {val}")
    return 0


def cmd_db(a: argparse.Namespace) -> int:
    from . import pustaka
    from .db import DB

    with DB(a.path) as db:
        if a.aksi == "init":
            print("tema baru:", db.seed_tema(), "| status:", pustaka.sinkron_status(db))
        elif a.aksi == "ekspor":
            print("ekspor:", db.ekspor(dengan_snapshot=a.snapshot))
        elif a.aksi == "impor":
            print("impor:", db.impor())
        elif a.aksi == "bersihkan-blokir":
            print("dibersihkan:", db.bersihkan_blokir())
        print(f"basis data {db.path} (skema v{db.versi}):", db.statistik())
    return 0


def cmd_skema(a: argparse.Namespace) -> int:
    from . import skema

    if a.aksi == "tulis":
        print("ditulis:", skema.tulis() or "(semua sudah sinkron)")
        return 0
    beda = skema.cek()
    print(
        "SKEMA SINKRON"
        if not beda
        else f"[GAGAL] turunan skema melenceng: {beda} -> jalankan: python3 -m kliktahu skema tulis"
    )
    return 0 if not beda else 1


def cmd_riset(a: argparse.Namespace) -> int:
    from .db import DB
    from .riset import mesin
    from .riset.http import Offline

    tema = [t.strip() for t in a.tema.split(",")] if a.tema else None
    db_path = a.db or (str(ROOT / "data" / "_uji" / "kliktahu_uji.db") if a.mode == "uji" else None)
    try:
        with DB(db_path) as db:
            h = mesin.jalankan(a.mode, _tgl(a.tanggal), db=db, agen=a.agen, tema=tema)
    except Offline as e:
        print(f"[OFFLINE] {e}")
        return 3
    k = h.keputusan
    if k:
        print(
            f"\nKEPUTUSAN{' (SEMENTARA)' if k.sementara else ''}: {k.tema} ({k.pilar}) - {k.format.upper()} - peluang "
            f"{k.peluang} - keyakinan {k.keyakinan:.0%}"
            + (
                (
                    f" - tayang SECEPATNYA (paling cepat {k.tayang_paling_lambat})"
                    if k.segera
                    else f" - tayang paling lambat {k.tayang_paling_lambat}"
                )
                if k.tayang_paling_lambat
                else ""
            )
        )
        for x in k.alasan:
            print("  -", x)
        for x in k.peringatan:
            print("  !", x)
    print("laporan:", h.laporan)
    return 0


def cmd_putuskan(a: argparse.Namespace) -> int:
    p = ROOT / "laporan" / "riset_terakhir.json"
    if not p.exists():
        print("belum ada riset (jalankan: python3 -m kliktahu riset)")
        return 1
    d = json.loads(p.read_text(encoding="utf-8"))
    print(json.dumps(d["keputusan"], ensure_ascii=False, indent=1))
    return 0


def cmd_metadata(a: argparse.Namespace) -> int:
    from . import kanal
    from . import metadata as M

    k = kanal.muat()
    if a.aksi == "cek":
        g, w = M.cek_md(a.file, a.format, a.pilar, k, tema=a.tema)
        for x in w:
            print("  peringatan:", x)
        for x in g:
            print("  GALAT:", x)
        print("METADATA LULUS" if not g else f"METADATA GAGAL ({len(g)} galat)")
        return 0 if not g else 1
    from .db import DB
    from .tema import TEMA

    with DB(a.db) as db:
        tema = a.tema
        konten = tl = None
        folder = None
        if a.episode:
            konten, tl, folder = M.konteks_episode(a.episode, a.format)
            tema = tema or konten.get("topik")
        if not tema or tema not in TEMA:
            print(f"[GAGAL] --tema wajib dan harus ada di registri tema (atau field 'topik' di content.json): {tema!r}")
            return 2
        t = db.topik(tema)
        frasa: list[str] = []
        pes: list[str] = []
        hook: str | None = None
        momen: str | None = None
        sumber = M.sumber_dari_konten(konten) if konten else []
        run = db.run_terakhir()
        if run and t:
            for r in db.skor_run(run["id"]):
                if r["topik_id"] == t["id"]:
                    sg = r["sinyal"]
                    # sudut riset DULUAN -> judul kandidat memuat sudut pembeda yang sama dengan laporan keputusan
                    frasa = list(dict.fromkeys([*sg.get("sudut", []), *sg.get("frasa", [])]))
                    hook = (sg.get("hook") or [None])[0]
                    if sg.get("momen", 0) >= 0.5 and sg.get("momen_nama"):
                        from .momen import nama_pendek

                        momen = nama_pendek(sg["momen_nama"])
        if t and not sumber:
            sumber = [s for s in db.sumber_topik(t["id"]) if s["kredibel"]][:4]
        p = M.buat(
            tema,
            frasa or [f"kenapa {TEMA[tema].inti}"],
            a.format,
            k,
            konten=konten,
            timeline=tl,
            pesaing_judul=pes,
            sumber=sumber,
            final=bool(a.episode),
            kata_kunci=a.kata_kunci,
            judul_tambahan=a.judul or [],
            hook=hook,
            momen=momen,
        )
        for x in p.peringatan:
            print("  peringatan:", x)
        for x in p.galat:
            print("  GALAT:", x)
        print("Judul:", *[f"\n  {i}. {j}" for i, j in enumerate(p.judul, 1)])
        print(f"Hashtag: {' '.join(p.hashtag)}\nTag ({p.tag_karakter}/500): {', '.join(p.tag)}")
        if a.keluar:  # DRAF: hanya satu berkas, tanpa folder pustaka/ (folder pustaka = topik dianggap sudah dibahas)
            out = M.tulis_md(
                p,
                Path(a.keluar),
                f"DRAF {tema} ({a.format}) - belum dipesan pemilik",
                "Draf dari riset; bab/timestamp final dibuat setelah naskah & VO.",
            )
            db.simpan_metadata(p.baris_db(t["id"] if t else None, None))
            db.commit()
            print("draf ditulis:", out)
        if a.tulis:
            kode = a.kode or (db.kode_berikut(a.format))
            tujuan = folder or ROOT / "pustaka" / f"{kode}_{tema.replace(' & ', '_').replace(' ', '_')}"
            M.tulis_md(p, Path(tujuan) / "METADATA.md", f"{kode} {tema} ({a.format})")
            pus = ROOT / "pustaka" / f"{kode}_{tema.replace(' & ', '_').replace(' ', '_').title()}"
            M.tulis_md(p, pus / "METADATA.md", f"{kode} {tema} ({a.format})")
            M.tulis_siap_tempel(p, pus / "SIAP_TEMPEL.md", kode, k)
            e = db.episode(kode)
            db.simpan_metadata(p.baris_db(t["id"] if t else None, e["id"] if e else None))
            db.commit()
            print("ditulis:", Path(tujuan) / "METADATA.md", "dan", pus)
        return 0 if p.lulus else 1


def cmd_pustaka(a: argparse.Namespace) -> int:
    from . import pustaka
    from .db import DB

    with DB(a.db) as db:
        if a.aksi == "sinkron":
            print("status topik:", pustaka.sinkron_status(db))
            print("ditulis:", pustaka.tulis_md(db))
        elif a.aksi == "daftar":
            for e in db.daftar("episode", urut="kode"):
                print(f"{e['kode']:<7} {e['format']:<6} {e['status']:<7} {e.get('judul') or '-'}")
            print(
                f"topik: {len(db.daftar_topik('segar'))} segar, {len(db.daftar_topik('dibahas'))} dibahas, "
                f"{len(db.daftar_topik('long'))} long"
            )
        elif a.aksi == "cari":
            for r in db.cari(" ".join(a.arg)):
                print(f"[{r['jenis']}] {r['kunci']}: {r['judul']} ... {r['cuplik']}")
        elif a.aksi == "tambah":
            kode = db.tambah_episode(a.format, a.tema, a.kode, slug=a.slug, judul=a.judul, status="ide")
            print("episode ditambahkan:", kode)
            pustaka.tulis_md(db)
        elif a.aksi == "status":
            kode, status = a.arg[0], a.arg[1]
            f = {"status": status}
            if a.youtube_id:
                f["youtube_id"] = a.youtube_id
            if status == "rilis":
                f["tayang"] = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            db.ubah_episode(kode, **f)
            pustaka.tulis_md(db)
            print(kode, "->", status)
        elif a.aksi == "impor-studio":
            print("baris performa diimpor:", pustaka.impor_studio(db, a.arg[0]))
        elif a.aksi == "duplikat":
            for nama, s, st in pustaka.duplikat(db, " ".join(a.arg)):
                print(f"{s:.2f}  {nama}  ({st})")
    return 0


def cmd_rencana(a: argparse.Namespace) -> int:
    from . import perencana
    from .db import DB, hari_ini_wib

    with DB(a.db) as db:
        if a.aksi == "kunci":
            tg, jam, fmt = a.arg
            n = db.con.execute(
                "UPDATE rencana SET status = 'terkunci' WHERE tanggal = ? AND jam = ? AND format = ?", (tg, jam, fmt)
            ).rowcount
            db.commit()
            print("dikunci:", n)
            return 0 if n else 1
        hari = _tgl(a.tanggal) or hari_ini_wib()
        rows = perencana.susun(db, hari, a.minggu)
        run = db.run_terakhir()
        md = perencana.tulis_md(
            rows,
            ROOT / "laporan" / "KALENDER.md",
            hari,
            f"run riset #{run['id']} {run['tanggal']} ({run['mode']})" if run else "",
        )
        ics = perencana.tulis_ics(rows, ROOT / "laporan" / "kalender.ics", hari, db.kanal.nama)
        for r in rows[:14]:
            print(
                f"{r['tanggal']} {r['jam']} {r['format']:<6} {r['episode_kode']:<7} {r['judul_kerja']:<22} {r['alasan']}"
            )
        print(f"{len(rows)} slot -> {md} , {ics}")
    return 0


def cmd_momen(a: argparse.Namespace) -> int:
    from . import momen
    from .db import DB, hari_ini_wib

    hari = _tgl(a.tanggal) or hari_ini_wib()
    with DB(a.db) as db:
        live = [
            momen.Momen(
                dt.date.fromisoformat(m["tanggal"]), m["nama"], m["tema"], m["jenis"], m["sumber"], m["urgensi"]
            )
            for m in db.momen_antara(hari - dt.timedelta(days=3), hari + dt.timedelta(days=a.hari))
            if m["jenis"] in ("live", "agen")
        ]
    for m in momen.semua(hari, a.hari, live):
        print(
            f"{m.tanggal} {m.jenis:<6} skor {momen.skor_momen(m, hari):.2f}  {m.nama}  -> {', '.join(momen.ke_tema(m)[:3])}"
        )
    return 0


def cmd_astro(a: argparse.Namespace) -> int:
    from . import astro

    th = a.tahun
    wib = dt.timezone(dt.timedelta(hours=7))
    for n, t in astro.ekuinoks_solstis(th).items():
        print(f"{n:<20} {t.astimezone(wib):%Y-%m-%d %H:%M} WIB")
    for t, d in astro.supermoon(th):
        print(f"supermoon            {t.astimezone(wib):%Y-%m-%d %H:%M} WIB  ({d:,.0f} km)")
    for n, t, z in astro.hujan_meteor(th):
        print(f"meteor {n:<13} {t.astimezone(wib):%Y-%m-%d %H:%M} WIB  (ZHR ~{z})")
    for kt in astro.KOTA:
        if a.kota and kt.nama.lower() != a.kota.lower():
            continue
        print(
            f"tanpa bayangan {kt.nama:<12}",
            ", ".join(f"{t:%d-%m %H:%M:%S} {kt.zona}" for t in astro.hari_tanpa_bayangan(kt, th)),
        )
    return 0


def cmd_dasbor(a: argparse.Namespace) -> int:
    from . import dasbor
    from .db import DB

    with DB(a.db) as db:
        d = dasbor.kumpulkan(db, _tgl(a.tanggal))
        if not a.diam:
            dasbor.terminal(d)
        (ROOT / "laporan").mkdir(exist_ok=True)
        (ROOT / "laporan" / "DASBOR.md").write_text(dasbor.markdown(d), encoding="utf-8")
        if a.png:
            print("png:", dasbor.png(d, Path(a.png), db.kanal))
    print("laporan/DASBOR.md ditulis")
    return 0


def cmd_sinkron(a: argparse.Namespace) -> int:
    from . import sinkron
    from .db import DB

    kfg = sinkron.dari_env()
    if not kfg:
        print(
            "Bolt Database / Supabase belum dikonfigurasi. Set variabel lingkungan (JANGAN di file):\n"
            f"  URL: salah satu {sinkron.ENV_URL}\n  KEY: salah satu {sinkron.ENV_KEY}\n"
            "Skema awan: skema/postgres.sql atau supabase/migrations/."
        )
        return 1
    kl = sinkron.KlienBolt(*kfg)
    with DB(a.db) as db:
        if a.aksi == "cek":
            print(json.dumps(kl.cek(), indent=1))
        elif a.aksi == "dorong":
            print("didorong:", sinkron.dorong(db, kl))
        else:
            print("ditarik:", sinkron.tarik(db, kl))
    return 0


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python3 -m kliktahu", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--versi", action="version", version=f"kliktahu {__version__}")
    sub = ap.add_subparsers(dest="perintah", required=True)

    def s(nama: str, fn, bantuan: str) -> argparse.ArgumentParser:
        p = sub.add_parser(nama, help=bantuan)
        p.set_defaults(fn=fn)
        p.add_argument("--db", default=None, help="path basis data (bawaan data/kliktahu.db)")
        return p

    p = s("kanal", cmd_kanal, "cek/lihat kanal.toml")
    p.add_argument("aksi", nargs="?", default="cek", choices=["cek", "lihat"])
    p.add_argument("--file", default=None)
    p = s("db", cmd_db, "basis data")
    p.add_argument(
        "aksi", nargs="?", default="status", choices=["init", "status", "ekspor", "impor", "bersihkan-blokir"]
    )
    p.add_argument("--path", default=None)
    p.add_argument("--snapshot", action="store_true", help="ekspor juga snapshot pencarian")
    p = s("skema", cmd_skema, "turunan skema")
    p.add_argument("aksi", nargs="?", default="cek", choices=["tulis", "cek"])
    p = s("riset", cmd_riset, "riset real-time")
    p.add_argument("--mode", default="online", choices=["online", "agen", "uji"])
    p.add_argument("--agen", default=None, help="berkas data agen (mode agen)")
    p.add_argument("--tema", default=None, help="subset tema, pisah koma")
    p.add_argument("--tanggal", default=None)
    s("putuskan", cmd_putuskan, "keputusan riset terakhir")
    p = s("metadata", cmd_metadata, "generator & lint metadata")
    p.add_argument("aksi", choices=["buat", "cek"])
    p.add_argument("file", nargs="?")
    p.add_argument("--tema", default=None)
    p.add_argument("--format", default="shorts", choices=["shorts", "long"])
    p.add_argument("--episode", default=None, help="slug episode (content.json + timeline.json) -> mode FINAL")
    p.add_argument("--kode", default=None)
    p.add_argument("--pilar", default=None)
    p.add_argument("--kata-kunci", default=None)
    p.add_argument("--judul", action="append", help="judul kandidat tambahan dari agen (dinilai bersama)")
    p.add_argument("--tulis", action="store_true", help="tulis METADATA.md + SIAP_TEMPEL.md episode (mode final)")
    p.add_argument("--keluar", default=None, help="tulis DRAF METADATA ke path ini saja (tanpa folder pustaka/)")
    p = s("pustaka", cmd_pustaka, "perpustakaan episode")
    p.add_argument("aksi", choices=["daftar", "cari", "tambah", "status", "sinkron", "impor-studio", "duplikat"])
    p.add_argument("arg", nargs="*")
    p.add_argument("--format", default="shorts", choices=["shorts", "long"])
    p.add_argument("--tema", default=None)
    p.add_argument("--kode", default=None)
    p.add_argument("--slug", default=None)
    p.add_argument("--judul", default=None)
    p.add_argument("--youtube-id", default=None)
    p = s("rencana", cmd_rencana, "kalender konten")
    p.add_argument("aksi", nargs="?", default="susun", choices=["susun", "kunci"])
    p.add_argument("arg", nargs="*")
    p.add_argument("--minggu", type=int, default=4)
    p.add_argument("--tanggal", default=None)
    p = s("momen", cmd_momen, "daftar momen")
    p.add_argument("--hari", type=int, default=60)
    p.add_argument("--tanggal", default=None)
    p = s("astro", cmd_astro, "astronomi offline")
    p.add_argument("--tahun", type=int, default=dt.date.today().year)
    p.add_argument("--kota", default=None)
    p = s("dasbor", cmd_dasbor, "dasbor kanal")
    p.add_argument("--png", nargs="?", const=str(ROOT / "laporan" / "dasbor.png"), default=None)
    p.add_argument("--diam", action="store_true")
    p.add_argument("--tanggal", default=None)
    p = s("sinkron", cmd_sinkron, "Bolt Database / Supabase")
    p.add_argument("aksi", nargs="?", default="cek", choices=["cek", "dorong", "tarik"])
    return ap


def main(argv: list[str] | None = None) -> int:
    a = parser().parse_args(argv)
    return int(a.fn(a) or 0)


if __name__ == "__main__":
    sys.exit(main())
