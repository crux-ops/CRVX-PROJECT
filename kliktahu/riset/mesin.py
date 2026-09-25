"""kliktahu/riset/mesin.py - MESIN RISET REAL-TIME v7 (menyeluruh): sapuan -> peta -> momen -> detail -> skor -> keputusan.

Alur satu run:
 1. status topik dari PUSTAKA.md + episode rilis (tidak menyarankan yang sudah dibahas)
 2. SAPUAN v3: benih (kenapa/apakah/bagaimana/padahal/tiba-tiba) x kata kunci tiap tema x Google + YouTube Autocomplete
 3. PETA v4: BFS kedalaman 2 untuk tema teratas (cabang konteks -> daun) -> jaring, kedalaman, long-tail, SERI
 4. MOMEN: kalender kurasi + astronomi terhitung + umpan live (BMKG, USGS, NOAA, JPL, EONET)
 5. DETAIL tema teratas: Wikipedia (pageview 60 hari), berita (Google News RSS), Google Trends harian,
    pesaing YouTube (Data API, bila ada kunci), sumber ilmiah (OpenAlex / Europe PMC), pertanyaan web (opsional)
 6. SKOR rumus prompt v3/v4/v5/v6 + v7 PELUANG & KEYAKINAN (kliktahu/skor.py)
 7. KEPUTUSAN niche/topik/format + PABRIK METADATA 3 teratas + laporan + snapshot/skor ke basis data (+ ekspor JSONL)
Mode: online (internet langsung) | uji (internet palsu deterministik, jalur HTTP penuh) | agen (data web search agen)
"""

from __future__ import annotations

import datetime as dt
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any

from .. import ROOT, __version__, momen, pustaka, teks
from .. import metadata as meta_mod
from .. import skor as S
from ..db import DB, hari_ini_wib
from ..tema import ALIAS, BENCANA, LEKS, TEMA, relevan
from . import sumber as SB
from .agen import SumberAgen
from .agen import muat as muat_agen
from .http import GagalHTTP, KlienRiset, Offline
from .keputusan import Keputusan, putuskan

LAPORAN = ROOT / "laporan"
PILAR = ("tubuh", "antariksa", "bumi", "hewan", "teknologi", "misteri")


class SumberOnline:
    """penyedia data lewat HTTP (internet asli, atau transport fixture pada mode uji)."""

    def __init__(
        self, klien: KlienRiset, hari_ini: dt.date, mode: str = "online", kunci_youtube: str | None = None
    ) -> None:
        self.k = klien
        self.hari_ini = hari_ini
        self.mode = mode
        r = klien.kanal.riset
        self.kunci_yt = kunci_youtube or r.rahasia(r.env_youtube_key)
        self.sekarang = (
            dt.datetime.now(dt.UTC)
            if mode == "online"
            else dt.datetime(hari_ini.year, hari_ini.month, hari_ini.day, 9, tzinfo=dt.UTC)
        )

    def punya_saran(self, tema: str) -> bool:
        return True

    def saran(self, q: str, sumber: str) -> list[str] | None:
        return SB.saran(self.k, q, sumber)

    def wiki(self, tema: str) -> dict | None:
        t = TEMA[tema]
        try:
            judul = SB.wiki_kanonik(self.k, t.wiki) or t.wiki  # ikuti alihan (registri bisa usang)
        except Exception:  # API MediaWiki gagal -> pakai judul registri apa adanya
            judul = t.wiki
        w = SB.wiki_views(self.k, judul, self.hari_ini)
        if w is None:
            cadangan = SB.wiki_judul(self.k, t.inti)
            w = SB.wiki_views(self.k, cadangan, self.hari_ini) if cadangan else None
        return w

    def berita(self, tema: str) -> dict | None:
        return SB.berita(self.k, TEMA[tema].inti, self.sekarang)

    def tren(self) -> list[dict] | None:
        return SB.tren_harian(self.k, self.k.kanal.wilayah)

    def pesaing(self, tema: str) -> dict | None:
        if not self.kunci_yt:
            return None
        t = TEMA[tema]
        return SB.youtube_pesaing(self.k, f"kenapa {t.inti}", self.kunci_yt, self.hari_ini)

    def pesaing_tersedia(self) -> bool:
        return bool(self.kunci_yt)

    def momen_live(self) -> tuple[list[momen.Momen], list[str]]:
        return SB.momen_live(self.k, self.hari_ini)

    def sumber_ilmiah(self, tema: str) -> list[dict] | None:
        t = TEMA[tema]
        out = SB.openalex(self.k, t.en)
        if t.pilar in self.k.kanal.aturan.pilar_kesehatan:
            out += SB.europepmc(self.k, t.en)
        return out

    def tanya(self, tema: str) -> list[str]:
        w = SB.web_cari(self.k, f"kenapa {TEMA[tema].inti}")
        return [x["tanya"] for x in (w or {}).get("tanya", []) if x.get("tanya")]


@dataclass
class HasilRiset:
    run_id: int
    tanggal: str
    mode: str
    baris: list[dict[str, Any]]
    momen: list[momen.Momen]
    statistik: dict[str, Any]
    keputusan: Keputusan | None
    metadata: dict[str, meta_mod.Paket] = field(default_factory=dict)
    laporan: Path | None = None


def _punya(f: str, leks: str) -> bool:
    ff = " " + f + " "
    return any(" " + w + " " in ff for w in LEKS[leks])


def _bersih(s: str, blokir: tuple[str, ...]) -> str | None:
    f = teks.norm(s)
    if not f or len(f) < 6 or teks.diblokir(f, blokir):
        return None
    return f


def _cabang(tema: str, frasa: list[str], blokir: tuple[str, ...]) -> list[str]:
    t = TEMA[tema]
    out = (
        [f"kenapa {t.inti} {a}" for a in t.aspek]
        + [f"apakah {t.inti} {a}" for a in t.aspek[:2]]
        + [f"kapan {t.inti} bahaya"]
        + [f for f in frasa if len(f.split()) >= 4][:3]
    )
    return list(dict.fromkeys(teks.norm(c) for c in out if not teks.diblokir(c, blokir)))


def jalankan(
    mode: str = "online",
    hari_ini: dt.date | None = None,
    db: DB | None = None,
    agen: Path | str | None = None,
    tema: list[str] | None = None,
    klien: KlienRiset | None = None,
    top_bfs: int = 12,
    top_detail: int = 15,
    folder_laporan: Path | None = None,
    log: Callable[[str], None] = print,
    ekspor: bool | None = None,
) -> HasilRiset:
    t0 = time.perf_counter()
    hari_ini = hari_ini or hari_ini_wib()
    db = db or DB()
    k = db.kanal
    blokir = k.aturan.blokir
    if mode == "agen":
        if not agen:
            raise ValueError("mode agen butuh berkas data agen (--agen <file.json>)")
        src: Any = SumberAgen(muat_agen(agen), hari_ini)
    elif mode in ("online", "uji"):
        if klien is None:
            if mode == "uji":
                from .fixture import transport_uji

                klien = KlienRiset(k, transport=transport_uji(hari_ini), pakai_cache=False, tidur=lambda s: None)
            else:
                klien = KlienRiset(k)
        src = SumberOnline(klien, hari_ini, mode, kunci_youtube="UJI-BUKAN-KUNCI" if mode == "uji" else None)
    else:
        raise ValueError(f"mode tidak dikenal: {mode}")

    st_pustaka = pustaka.sinkron_status(db)
    run_id = db.mulai_run(mode, hari_ini)
    stat: dict[str, Any] = {"versi": __version__, "status_pustaka": st_pustaka, "sumber": {}}
    topik = {t["nama"]: t for t in db.daftar("topik")}
    semua_tema = [x for x in (tema or list(TEMA)) if x in TEMA]
    kandidat = [x for x in semua_tema if src.punya_saran(x)]
    tanpa_data = sorted(set(semua_tema) - set(kandidat))
    log(
        f"[riset] run #{run_id} mode {mode} {hari_ini} - {len(kandidat)} tema"
        + (f" ({len(tanpa_data)} tanpa data agen dilewati)" if tanpa_data else "")
    )

    # ------------------------------------------------------------------ 2. sapuan v3
    kueri = [
        (x, f"{b} {kw}", s)
        for x in kandidat
        for b in k.riset.benih
        for kw in TEMA[x].kata
        for s in ("google", "youtube")
    ]
    if klien is not None:
        hasil = klien.banyak({f"{s}|{q}": partial(src.saran, q, s) for _, q, s in kueri})
    else:
        hasil = {f"{s}|{q}": src.saran(q, s) for _, q, s in kueri}
    gagal_saran = [v for v in hasil.values() if isinstance(v, Exception)]
    if kueri and len(gagal_saran) == len(hasil):
        db.selesai_run(
            run_id, {**stat, "galat": str(gagal_saran[0])}, catatan="GAGAL: sumber autocomplete tidak terjangkau"
        )
        raise Offline(
            f"autocomplete tidak terjangkau ({gagal_saran[0]}). Di sandbox Arena gunakan --mode agen "
            "dengan data web search agen, atau jalankan di komputer dengan internet biasa."
        )
    stat["sumber"]["autocomplete"] = f"ok ({len(hasil) - len(gagal_saran)}/{len(hasil)} kueri)"
    frasa: dict[str, dict[str, dict[str, Any]]] = {x: {} for x in kandidat}
    dibuang = 0
    for x, q, s in kueri:
        v = hasil.get(f"{s}|{q}")
        if not isinstance(v, list):
            continue
        db.simpan_snapshot(
            run_id, f"{s}_saran", q, {"items": v}, 200 if mode != "agen" else 0, topik_id=topik.get(x, {}).get("id")
        )
        for pos, sgs in enumerate(v):
            f = _bersih(sgs, blokir)
            if not f:
                continue
            if not relevan(f, TEMA[x]) or (k.riset.derau and teks.kena(f, k.riset.derau)):
                dibuang += 1  # derau (esports/film) atau tidak membahas tema ("lubang KNALPOT hitam")
                continue
            e = frasa[x].setdefault(f, {"pos": pos, "yt": False, "google": False})
            e["pos"] = min(e["pos"], pos)
            e["yt" if s == "youtube" else "google"] = True
    db.commit()
    stat["frasa_dibuang_derau_relevansi"] = dibuang

    baris: dict[str, dict[str, Any]] = {}
    for x in kandidat:
        fr = frasa[x]
        urut = sorted(fr, key=lambda f: (fr[f]["pos"], not fr[f]["yt"], f))
        sig = {
            "jml": float(len(fr)),
            "kuat": round(S.kuat(e["pos"] for e in fr.values()), 2),
            "niat": float(sum(_punya(f, "niat") for f in fr)),
            "yt": float(sum(e["yt"] for e in fr.values())),
            "sains": float(sum(_punya(f, "sains") for f in fr)),
            "rel": float(sum(_punya(f, "rel") for f in fr)),
            "kom": float(sum(_punya(f, "kom") for f in fr)),
            "vis": float(sum(_punya(f, "vis") for f in fr)) + TEMA[x].visb,
            "ever": float(TEMA[x].ever),
        }
        sens = [f for f in urut if teks.sensitif(f, k.aturan.sensitif)]
        baris[x] = {
            "tema": x,
            "slug": teks.slug(x),
            "pilar": TEMA[x].pilar,
            "status": (topik.get(x) or {}).get("status", "segar"),
            "sinyal": {**sig, "frasa": urut[:30]},
            "v3_skor": S.v3_skor(sig),
            "frasa_sensitif": sens,
            "dominan_sensitif": bool(urut) and len(sens) / len(urut) >= 0.5,
        }
        baris[x]["v3_tumbuh"] = S.v3_tumbuh(sig, baris[x]["v3_skor"])
        if baris[x]["status"] in ("antre", "arsip"):
            baris[x]["status"] = "segar" if baris[x]["status"] == "antre" else "dibahas"

    # ------------------------------------------------------------------ 3. peta v4 (BFS kedalaman 2)
    segar = [x for x in sorted(baris, key=lambda x: -baris[x]["v3_tumbuh"]) if baris[x]["status"] != "dibahas"]
    bfs = segar[:top_bfs] if klien is not None else []
    cab = {x: _cabang(x, baris[x]["sinyal"]["frasa"], blokir) for x in bfs}
    if bfs and klien is not None:
        d1 = klien.banyak({f"{x}|{c}": partial(src.saran, c, "google") for x in bfs for c in cab[x]})
        daun = {}
        for x in bfs:
            for c in cab[x]:
                v = d1.get(f"{x}|{c}")
                lst = [f for f in (_bersih(s, blokir) for s in v) if f and f != c] if isinstance(v, list) else []
                daun[(x, c)] = lst
        d2 = klien.banyak(
            {f"{x}|{c}|{lf}": partial(src.saran, lf, "google") for (x, c), lst in daun.items() for lf in lst[:2]}
        )
        for x in bfs:
            punya, semua_f, kd = [], set(), []
            for c in cab[x]:
                l1 = daun[(x, c)]
                l2: list[str] = []
                for lf in l1[:2]:
                    v = d2.get(f"{x}|{c}|{lf}")
                    if isinstance(v, list):
                        l2 += [f for f in (_bersih(s, blokir) for s in v) if f and f not in l1]
                if l1:
                    punya.append((c, len(l1) + len(set(l2))))
                    kd.append(2 if l2 else 1)
                semua_f |= set(l1) | set(l2)
            jaring = len(punya)
            kedalaman = sum(kd) / max(1, jaring)
            peluang = sum(1 for f in semua_f if len(f.split()) >= 5)
            baris[x].update(
                jaring=jaring,
                kedalaman=round(kedalaman, 2),
                peluang=peluang,
                v4_keluarga=S.v4_keluarga(baris[x]["v3_tumbuh"], jaring, kedalaman, peluang),
                seri=[c for c, _ in sorted(punya, key=lambda z: -z[1])[:4]],
            )
        stat["sumber"]["peta_v4"] = f"ok ({len(bfs)} tema)"

    # ------------------------------------------------------------------ 4. momen
    live, gagal_live = src.momen_live()
    for g in gagal_live:
        log(f"[riset] umpan momen gagal: {g}")
    stat["sumber"]["momen_live"] = f"ok ({len(live)} peristiwa)" + (f", gagal: {len(gagal_live)}" if gagal_live else "")
    semua_momen = momen.semua(hari_ini, 120, live)
    for m in semua_momen:
        if not teks.diblokir(m.nama, blokir):
            db.upsert_momen(m.baris_db())
    db.commit()
    prev = db.run_terakhir(sebelum_id=run_id, tanggal_sebelum=hari_ini.isoformat())
    prev_sig = {r["nama"]: r["sinyal"] for r in db.skor_run(prev["id"])} if prev else {}
    stat["velocity_dari_run"] = prev["id"] if prev else None
    for x, r in baris.items():
        ms, ev = momen.skor_tema(x, semua_momen, hari_ini, k.jadwal.jendela_momen_hari)
        p = prev_sig.get(x)
        vel = S.v5_velocity(
            r["sinyal"]["jml"], r["sinyal"]["frasa"], p["jml"] if p else None, p.get("frasa") if p else None
        )
        r.update(
            momen=ms,
            momen_nama=ev.nama if ev else None,
            momen_tanggal=ev.tanggal.isoformat() if ev else None,
            momen_selesai=ev.selesai.isoformat() if ev and ev.selesai else None,
            momen_jenis=ev.jenis if ev else None,
            velocity=vel if p else None,
            v5_views=S.v5_views(r["sinyal"], r.get("jaring", 0), vel, ms),
        )

    # ------------------------------------------------------------------ 5. detail real-time
    calon = [x for x in sorted(baris, key=lambda x: -baris[x]["v5_views"]) if baris[x]["status"] != "dibahas"]
    detail = calon[:top_detail] if klien is not None else calon  # data agen lokal: semua kandidat didetailkan
    tren = None
    try:
        tren = src.tren()
        stat["sumber"]["google_trends"] = "ok" if tren is not None else "tidak ada data"
    except (Offline, GagalHTTP) as e:
        stat["sumber"]["google_trends"] = f"gagal: {e}"
    tugas: dict[str, Callable[[], Any]] = {}
    for x in detail:
        tugas[f"wiki|{x}"] = partial(src.wiki, x)
        tugas[f"berita|{x}"] = partial(src.berita, x)
    if src.pesaing_tersedia():
        for x in detail[: k.riset.maks_youtube_tema]:
            tugas[f"pesaing|{x}"] = partial(src.pesaing, x)
    for x in detail[:6]:
        tugas[f"ilmiah|{x}"] = partial(src.sumber_ilmiah, x)
    for x in detail[:3]:
        tugas[f"tanya|{x}"] = partial(src.tanya, x)
    if klien is not None:
        det = klien.banyak(tugas)
    else:
        det = {}
        for kk, fn in tugas.items():
            try:
                det[kk] = fn()
            except Exception as e:
                det[kk] = e
    for jenis in ("wiki", "berita", "pesaing", "ilmiah", "tanya"):
        vals = [v for kk, v in det.items() if kk.startswith(jenis + "|")]
        ok = sum(1 for v in vals if v is not None and not isinstance(v, Exception))
        err = [v for v in vals if isinstance(v, Exception)]
        stat["sumber"][jenis] = (
            "tidak dikonfigurasi" if not vals else f"ok ({ok}/{len(vals)})" + (f", gagal: {err[0]}" if err else "")
        )
    for x in detail:
        r = baris[x]
        for jenis in ("wiki", "berita", "pesaing", "ilmiah", "tanya"):
            v = det.get(f"{jenis}|{x}")
            r[jenis] = None if isinstance(v, Exception) else v
            if v is not None and not isinstance(v, Exception) and jenis in ("wiki", "berita", "pesaing"):
                db.simpan_snapshot(
                    run_id,
                    {"wiki": "wikipedia", "pesaing": "youtube"}.get(jenis, jenis),
                    x,
                    v,
                    200 if mode != "agen" else 0,
                    topik_id=topik.get(x, {}).get("id"),
                )
        if r.get("ilmiah"):
            dom = k.sumber_kredibel
            for s in r["ilmiah"]:
                s["kredibel"] = bool(s.get("kredibel")) or SB.kredibel(s.get("url", ""), dom)
            if topik.get(x):
                db.simpan_sumber(topik[x]["id"], r["ilmiah"])
        if tren:
            kunci = [teks.norm(y) for y in (x, *TEMA[x].kata)]
            cocok = [
                tt["traffic"]
                for tt in tren
                if any(teks.kata_utuh_semua(kk, tt["judul"]) for kk in kunci if len(kk) > 3)
            ]
            r["tren_traffic"] = max(cocok) if cocok else None
    db.commit()

    # ------------------------------------------------------------------ 6. skor v6 + v7
    rows = [baris[x] for x in calon]
    perm = S.norm01([r["v5_views"] for r in rows])
    visn = S.norm01([r["sinyal"]["vis"] for r in rows])
    perf = db.performa_pilar()
    rata = {p: v["tayangan_median"] * max(v["retensi_rata"], 1.0) / 100.0 for p, v in perf.items()}
    bp = S.bobot_pilar(rata, PILAR)
    semua_sudah = pustaka.daftar_sudah(db)
    for r, pn, vn in zip(rows, perm, visn):
        t = TEMA[r["tema"]]
        w = S.skor_wiki(r["wiki"]["views60"], r["wiki"]["tren"]) if r.get("wiki") else 0.5
        pes = r.get("pesaing")
        cel = S.skor_celah(pes["jumlah"], pes["umur_median_hari"], pes["median_views"]) if pes else 0.5
        vis = 0.5 * vn + 0.5 * t.visb
        pw = bp.get(t.pilar, 0.5) * k.pilar.get(t.pilar, 1.0)
        r["v6_papan"] = S.v6_papan(pn, w, cel, vis, pw, r["momen"])
        mirip = (
            max(
                (teks.mirip(r["tema"], s) if not teks.kata_utuh_semua(r["tema"], s) else 1.0 for s in semua_sudah),
                default=0.0,
            )
            if r["status"] == "segar"
            else 0.0
        )
        n_kred = sum(1 for s in (r.get("ilmiah") or []) if s.get("kredibel")) if r.get("ilmiah") is not None else None
        kom = {
            "permintaan": (pn, 1.0 if r["sinyal"]["jml"] > 0 else 0.0),
            "minat": (w, 1.0) if r.get("wiki") else None,
            "momentum": S.momentum(
                r.get("velocity"),
                (r.get("berita") or {}).get("rasio") if r.get("berita") else None,
                r.get("tren_traffic"),
                r["wiki"].get("lonjakan_z") if r.get("wiki") else None,
            ),
            "celah": S.celah_v7(cel if pes else None, pes.get("rasio_outlier") if pes else None),
            "kecocokan": S.kecocokan(vis, pw, t.ever, bool(perf)),
            "waktu": (r["momen"], 1.0),
            "kesegaran": S.kesegaran(r["status"], mirip if mirip < 1.0 else 0.0),
            "bukti": S.bukti(n_kred),
        }
        r["v7_peluang"], r["keyakinan"], r["komponen"] = S.v7_peluang(kom)
        r["sudut"] = _sudut(r, k)
        r["hook"] = _hook(r, k)
    rows.sort(key=lambda r: -r["v7_peluang"])
    for i, r in enumerate(rows, 1):
        r["peringkat"] = i
    db.simpan_skor(
        run_id,
        [
            {
                "topik_id": topik[r["tema"]]["id"],
                "peringkat": r["peringkat"],
                "status_topik": r["status"],
                "v3_skor": round(r["v3_skor"], 3),
                "v3_tumbuh": round(r["v3_tumbuh"], 3),
                "v4_keluarga": round(r["v4_keluarga"], 3) if "v4_keluarga" in r else None,
                "v5_views": round(r["v5_views"], 3),
                "v6_papan": round(r["v6_papan"], 2),
                "v7_peluang": round(r["v7_peluang"], 2),
                "keyakinan": round(r["keyakinan"], 3),
                "komponen": {kk: round(v, 4) for kk, v in r["komponen"].items()},
                "sinyal": {
                    **r["sinyal"],
                    "momen": r["momen"],
                    "momen_nama": r.get("momen_nama"),
                    "momen_tanggal": r.get("momen_tanggal"),
                    "velocity": r.get("velocity"),
                    "jaring": r.get("jaring", 0),
                    "kedalaman": r.get("kedalaman", 0),
                    "seri": r.get("seri", []),
                    "sudut": r.get("sudut", []),
                    "hook": r.get("hook", []),
                },
            }
            for r in rows
            if r["tema"] in topik
        ],
    )

    # ------------------------------------------------------------------ 7. keputusan + metadata + laporan
    kep = putuskan(rows, k, hari_ini)
    paket: dict[str, meta_mod.Paket] = {}
    for r in [r for r in rows if r["status"] != "dibahas" and not r.get("dominan_sensitif")][:3]:
        fmt = kep.format if kep and kep.tema == r["tema"] else "shorts"
        src_ilm = [s for s in (r.get("ilmiah") or []) if s.get("kredibel")][:4]
        p = meta_mod.buat(
            r["tema"],
            r["sinyal"]["frasa"],
            fmt,
            k,
            hook=(r.get("hook") or [None])[0],
            pesaing_judul=(r.get("pesaing") or {}).get("judul", []),
            sumber=src_ilm,
            momen=_momen_pendek(r) if r.get("momen", 0) >= 0.5 else None,
        )
        paket[r["tema"]] = p
        db.simpan_metadata(p.baris_db(topik.get(r["tema"], {}).get("id"), run_id=run_id))
    db.commit()
    stat.update(
        tema_dianalisis=len(kandidat),
        tema_tanpa_data=tanpa_data,
        kueri_saran=len(kueri),
        http=dict(klien.stat) if klien is not None else {},
        host_offline=sorted(klien.host_mati) if klien is not None else [],
        durasi_detik=round(time.perf_counter() - t0, 1),
        data_agen=getattr(src, "diambil", None),
    )
    db.selesai_run(run_id, stat)
    hasil_r = HasilRiset(run_id, hari_ini.isoformat(), mode, rows, semua_momen, stat, kep, paket)
    folder = folder_laporan or (LAPORAN if mode != "uji" else LAPORAN / "_uji")
    hasil_r.laporan = tulis_laporan(hasil_r, folder)
    if ekspor if ekspor is not None else mode != "uji":
        db.ekspor()
    log(f"[riset] selesai {stat['durasi_detik']} s -> {hasil_r.laporan}")
    return hasil_r


def _momen_pendek(r: dict[str, Any], maks: int = 40) -> str:
    return momen.nama_pendek(r.get("momen_nama") or "", maks)


# kata pengisi: "kenapa tsunami BISA TERJADI" = kata kunci inti, bukan sudut pembeda
_PENGISI = {"bisa", "terjadi", "terjadinya", "itu", "sih", "ya", "adalah", "dapat", "sebenarnya", "yang", "ada", "kok"}
_BENIH_TANYA = {"kenapa", "mengapa", "padahal", "apakah", "bagaimana"}
# kata umum di nama momen yang bukan pembeda ("Peringatan 8 tahun ... (bahas sains dengan hormat)")
_UMUM_MOMEN = {
    "peringatan",
    "tahun",
    "hari",
    "bahas",
    "sains",
    "dengan",
    "hormat",
    "sedunia",
    "nasional",
    "internasional",
    "dunia",
    "pekan",
    "awal",
    "musim",
    "banyak",
    "wilayah",
    "perkiraan",
    "umum",
    "cek",
    "status",
    "terbaru",
    "beruntun",
    "sampai",
    "naik",
    "bukan",
    "prediksi",
    "imbauan",
    "mitigasi",
    "setelah",
    "sebulan",
    "memicu",
    "hingga",
    "terlihat",
    "dari",
    "untuk",
    "pada",
    "yang",
    "atau",
    "merilis",
    "skenario",
    "terburuk",
}


def _kata_tema(nama: str) -> set[str]:
    t = TEMA[nama]
    return {w for x in (t.nama, *t.kata, *ALIAS.get(nama, [])) for w in teks.norm(x.replace("&", " ")).split()}


def _generik(frasa: str, nama: str) -> bool:
    """frasa hanya berisi benih + kata tema + kata pengisi -> bukan sudut ('kenapa bisa terjadinya tsunami')."""
    return all(w in _BENIH_TANYA | _PENGISI | _kata_tema(nama) for w in frasa.split())


def _kata_momen(r: dict[str, Any]) -> set[str]:
    """kata pembeda dari nama momen yang relevan saat ini ('... tsunami Palu-Donggala 2018' -> {palu, donggala, gempa})."""
    if not r.get("momen_nama") or r.get("momen", 0) < 0.5:
        return set()
    kata = teks.norm(r["momen_nama"].replace("-", " ")).split()
    return {w for w in kata if len(w) >= 4 and not w.isdigit() and w not in _UMUM_MOMEN | _kata_tema(r["tema"])}


def _sudut(r: dict[str, Any], k: Any) -> list[str]:
    judul = (r.get("pesaing") or {}).get("judul", [])
    out = []
    for f in r["sinyal"]["frasa"]:
        w = f.split()
        # sudut = pertanyaan SPESIFIK (>= 4 kata), bukan kueri inti ('kenapa gunung meletus' = kata kunci, bukan sudut)
        if len(w) < 4 or w[0] not in ("kenapa", "padahal", "apakah") or teks.sensitif(f, k.aturan.sensitif):
            continue
        if _generik(f, r["tema"]):  # 'kenapa tsunami bisa terjadi' = kata kunci + pengisi
            continue
        if judul and teks.paling_mirip(" ".join(w[1:]), judul)[1] >= 0.75:
            continue
        out.append(f)
    # sudut yang menyambung momen saat ini didahulukan (Palu 28 Sep -> 'kenapa tsunami palu bisa terjadi')
    km = _kata_momen(r)
    out.sort(key=lambda f: not (km & set(f.split())))
    tanya = [teks.norm(q) for q in (r.get("tanya") or []) if not teks.sensitif(q, k.aturan.sensitif)]
    return (out + tanya)[:4]


def _hook(r: dict[str, Any], k: Any) -> list[str]:
    out = []
    bencana = r["tema"] in BENCANA  # ada korban jiwa nyata -> tanpa "lebih seru" / "tidak seperti yang kamu kira"
    for f in dict.fromkeys([*r.get("sudut", []), *r["sinyal"]["frasa"]]):
        w = f.split()
        if len(w) < 3 or len(w) > 5 or teks.kena(f, k.aturan.hindari_hook) or teks.sensitif(f, k.aturan.sensitif):
            continue
        if bencana and w[0] in ("kenapa", "apakah"):
            out.append(f"{teks.kalimat(f)}? Ini penjelasan ilmiahnya.")
        elif w[0] == "kenapa":
            # "setiap hari" hanya untuk pengalaman sehari-hari (cegukan, menguap), bukan gunung meletus / lubang hitam
            sehari = any(x in w for x in ("kita", "terus", "sering", "tiba", "saat", "badan", "kepala"))
            out.append(
                f"{teks.kalimat(f)}? "
                + (
                    "Padahal kamu mengalaminya hampir setiap hari."
                    if sehari
                    else "Jawabannya lebih seru dari yang kamu kira."
                )
            )
        elif w[0] == "apakah":
            out.append(f"{teks.kalimat(f)}? Jawabannya tidak seperti yang kamu kira.")
        elif w[0] == "padahal":
            out.append(f"{teks.kalimat(f)}... lalu kenapa?")
        if len(out) >= 2:
            break
    return [teks.ascii_saja(h) for h in out]


# ================================================================================================ laporan
def _f(x: float | None, n: int = 2) -> str:
    return "-" if x is None else f"{x:.{n}f}"


def tulis_laporan(h: HasilRiset, folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "arsip").mkdir(exist_ok=True)
    kep = h.keputusan
    L = [
        f"# RISET REAL-TIME v7 - {h.tanggal} (mode {h.mode}, run #{h.run_id})",
        "",
        "Peluang v7 (0-100) = 26 permintaan + 12 minat Wikipedia + 14 momentum + 16 celah pesaing + 12 kecocokan "
        "+ 10 momen + 5 kesegaran + 5 bukti ilmiah. Keyakinan = porsi bobot yang didukung data nyata "
        "(komponen tanpa data = netral 0.5). Kolom v3-v6 = rumus prompt pemilik (PROMPT_KLIKTAHU.txt §8).",
        "",
    ]
    if kep:
        L += [
            "## KEPUTUSAN" + (" (SEMENTARA - keyakinan rendah)" if kep.sementara else ""),
            "",
            f"**Topik: {kep.tema}** (pilar {kep.pilar}) - format **{kep.format.upper()}** - peluang **{kep.peluang}** "
            f"- keyakinan {kep.keyakinan:.0%}"
            + (
                (
                    f" - tayang **SECEPATNYA** (paling cepat {kep.tayang_paling_lambat}, momen sedang berlangsung)"
                    if kep.segera
                    else f" - tayang paling lambat **{kep.tayang_paling_lambat}**"
                )
                if kep.tayang_paling_lambat
                else ""
            ),
            "",
        ]
        if kep.sudut:
            L.append(f'- Sudut pembeda: "{kep.sudut}"')
        for hk in kep.hook:
            L.append(f'- Hook 3 detik: "{hk}"')
        if kep.seri:
            L.append("- Seri lanjutan (v4): " + "; ".join(kep.seri))
        L += ["", "Alasan:", *[f"- {a}" for a in kep.alasan]]
        if kep.peringatan:
            L += ["", "Peringatan:", *[f"- {p}" for p in kep.peringatan]]
        if kep.alternatif:
            L += [
                "",
                "Alternatif:",
                *[
                    f"- {a['tema']} ({a['pilar']}) peluang {a['peluang']}, keyakinan {a['keyakinan']:.0%}"
                    + (f', sudut "{a["sudut"]}"' if a.get("sudut") else "")
                    + (f", momen: {a['momen']}" if a.get("momen") else "")
                    + (f" - **{a['catatan']}**" if a.get("catatan") else "")
                    for a in kep.alternatif
                ],
            ]
        L += [
            "",
            "### Peta niche (pilar fokus)",
            "",
            "| pilar | tema dianalisis | peluang 3 teratas | permintaan | celah | contoh |",
            "|---|---|---|---|---|---|",
        ]
        for n in kep.niche:
            L.append(
                f"| {n['pilar']} | {n['n']} | {n['peluang_top3']} | {n['permintaan']:.2f} | {n['celah']:.2f} | "
                f"{', '.join(n['contoh'])} |"
            )
    L += [
        "",
        "## Papan peringkat",
        "",
        "| # | tema | pilar | status | PELUANG v7 | yakin | v6 papan | v5 views | v3 tumbuh | permintaan | minat | "
        "momentum | celah | momen | sudut |",
        "|" + "---|" * 15,
    ]
    for r in h.baris[:20]:
        kp = r["komponen"]
        L.append(
            f"| {r['peringkat']} | {r['tema']} | {r['pilar']} | {r['status']} | **{r['v7_peluang']:.1f}** | "
            f"{r['keyakinan']:.0%} | {r['v6_papan']:.1f} | {r['v5_views']:.1f} | {r['v3_tumbuh']:.1f} | "
            f"{kp['permintaan']:.2f} | {kp['minat']:.2f} | {kp['momentum']:.2f} | {kp['celah']:.2f} | "
            f"{_f(r['momen'])} | {(r.get('sudut') or ['-'])[0]} |"
        )
    L += ["", "## Momen 60 hari ke depan", "", "| tanggal | jenis | momen | tema |", "|---|---|---|---|"]
    batas = dt.date.fromisoformat(h.tanggal) + dt.timedelta(days=60)
    for m in h.momen:
        if m.tanggal <= batas:
            L.append(f"| {m.tanggal} | {m.jenis} | {m.nama} | {', '.join(momen.ke_tema(m)[:4]) or '-'} |")
    if h.metadata:
        L += ["", "## Pabrik metadata (draft dari frasa pencarian asli - final dibuat saat episode dipesan)", ""]
        for t, pk in h.metadata.items():
            L += [
                f"### {t} ({pk.format}) - lint {'LULUS' if pk.lulus else 'BELUM FINAL'}",
                "",
                "Judul:",
                *[f"{i}. {j}" for i, j in enumerate(pk.judul, 1)],
                "",
                "Deskripsi (draft):",
                "```text",
                pk.deskripsi.rstrip(),
                "```",
                f"Hashtag: {' '.join(pk.hashtag)}",
                "",
                f"Tag ({pk.tag_karakter}/500): {', '.join(pk.tag)}",
                "",
            ]
    s = h.statistik
    L += [
        "",
        "## Statistik run",
        "",
        f"- Tema dianalisis: {s.get('tema_dianalisis')} | kueri autocomplete: "
        f"{s.get('kueri_saran')} | durasi {s.get('durasi_detik')} s",
        f"- HTTP: {s.get('http')} | host tidak terjangkau: {', '.join(s.get('host_offline') or []) or '-'}",
        f"- Velocity dibanding run: {s.get('velocity_dari_run') or 'belum ada run sebelumnya (velocity netral)'}",
        *[f"- Sumber {kk}: {v}" for kk, v in s.get("sumber", {}).items()],
    ]
    if s.get("tema_tanpa_data"):
        L.append(f"- Tema tanpa data agen (tidak diperingkat): {', '.join(s['tema_tanpa_data'])}")
    isi = "\n".join(L) + "\n"
    p = folder / "RISET.md"
    p.write_text(isi, encoding="utf-8")
    (folder / "arsip" / f"RISET_{h.tanggal}_{h.mode}_run{h.run_id}.md").write_text(isi, encoding="utf-8")
    ringkas = {
        "run_id": h.run_id,
        "tanggal": h.tanggal,
        "mode": h.mode,
        "keputusan": kep.dict() if kep else None,
        "top": [
            {
                kk: r.get(kk)
                for kk in (
                    "peringkat",
                    "tema",
                    "pilar",
                    "status",
                    "v7_peluang",
                    "keyakinan",
                    "v6_papan",
                    "komponen",
                    "momen_nama",
                )
            }
            for r in h.baris[:20]
        ],
        "statistik": s,
    }
    (folder / "riset_terakhir.json").write_text(
        json.dumps(ringkas, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )
    return p
