"""kliktahu/pustaka.py - PERPUSTAKAAN EPISODE (Pustaka): status topik, episode, impor performa, PUSTAKA.md.

* SUDAH_DIBAHAS dibaca dari PUSTAKA.md (blok penanda) + episode berstatus 'rilis' di basis data
* PUSTAKA.md ditulis ulang dari basis data (tabel episode) TANPA menghapus arsip lama / blok SUDAH_DIBAHAS
* impor CSV YouTube Studio (header Inggris ATAU Indonesia) -> tabel performa -> loop bobot pilar di riset
* cek duplikat topik (kemiripan rapidfuzz) sebelum memesan episode baru
"""

from __future__ import annotations

import csv
import datetime as dt
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import ROOT, teks
from .db import DB, hari_ini_wib
from .tema import DAFTAR, TEMA, Tema

PUSTAKA_MD = ROOT / "PUSTAKA.md"
_BLOK = re.compile(r"(<!-- SUDAH_DIBAHAS:MULAI.*?-->)(.*?)(<!--\s*SUDAH_DIBAHAS:SELESAI\s*-->)", re.S)
PILAR_ARSIP = {  # topik arsip akun lama yang tidak ada di registri tema -> pilar
    "ngorok": "tubuh",
    "perut & pencernaan": "tubuh",
    "kram & kesemutan": "tubuh",
    "demam & imun": "tubuh",
    "mimisan & hidung": "tubuh",
    "pusing & migrain": "tubuh",
    "kuping berdenging": "tubuh",
    "jantung berdebar": "tubuh",
    "hantu & supranatural": "misteri",
    "gunung padang": "misteri",
    "megalodon": "hewan",
    "matahari & langit gelap": "antariksa",
    "bintang berkedip": "antariksa",
    "internet & sinyal": "teknologi",
    "laut terdalam": "bumi",
}


def sudah_dibahas(path: Path = PUSTAKA_MD) -> dict[str, str]:
    """{tema_norm: 'shorts'|'long'} dari blok SUDAH_DIBAHAS. 'Long:' = baru jadi video panjang."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    m = _BLOK.search(path.read_text(encoding="utf-8"))
    if not m:
        return out
    for ln in m.group(2).splitlines():
        ln = ln.strip().lstrip("-").strip()
        if not ln:
            continue
        jenis = "long" if ln.lower().startswith("long:") else "shorts"
        nama = teks.norm(re.sub(r"(?i)^long:", "", ln).replace("(2x)", "")).replace(" ", " ")
        out[nama] = jenis
    return out


def _nama_asli(path: Path = PUSTAKA_MD) -> dict[str, str]:
    """norm -> tulisan asli (dengan '&')."""
    out: dict[str, str] = {}
    m = _BLOK.search(path.read_text(encoding="utf-8")) if path.exists() else None
    for ln in m.group(2).splitlines() if m else []:
        ln = re.sub(r"(?i)^long:", "", ln.strip().lstrip("-").strip()).replace("(2x)", "").strip()
        if ln:
            out[teks.norm(ln)] = ln
    return out


def status_tema(t: Tema, sudah: dict[str, str]) -> str:
    """'dibahas' (sudah jadi Shorts) / 'long' (baru jadi video panjang) / 'segar'. Pencocokan KATA UTUH."""
    kunci = [teks.norm(x) for x in (t.nama, *t.kata)]
    hasil = "segar"
    for d, jenis in sudah.items():
        dinti = d.split(" & ")[0].strip()
        for k in kunci:
            inti = k.split(" & ")[0].strip()
            if teks.kata_utuh_semua(inti, d) or teks.kata_utuh_semua(dinti, k):
                if jenis == "shorts":
                    return "dibahas"
                hasil = "long"
    return hasil


def sinkron_status(db: DB, path: Path = PUSTAKA_MD) -> dict[str, int]:
    """registri tema + arsip PUSTAKA.md + episode rilis -> status topik di basis data."""
    db.seed_tema()
    sudah = sudah_dibahas(path)
    for e in db.daftar("episode", "status = 'rilis' AND topik_id IS NOT NULL"):
        trow = db.ambil("topik", id=e["topik_id"])
        if trow:
            sudah.setdefault(teks.norm(trow["nama"]), "shorts" if e["format"] == "shorts" else "long")
    hitung = {"segar": 0, "long": 0, "dibahas": 0, "arsip_baru": 0}
    for t in DAFTAR:
        st = status_tema(t, sudah)
        row = db.topik(teks.slug(t.nama))
        if row and row["status"] in ("antre", "arsip") and st == "segar":
            st = row["status"]
        if row and row["status"] != st:
            db.ubah("topik", row["id"], status=st)
        hitung[st if st in hitung else "segar"] += 1
    asli = _nama_asli(path)
    terdaftar = {teks.norm(t.nama) for t in DAFTAR} | {teks.norm(k) for t in DAFTAR for k in t.kata}
    for n, jenis in sudah.items():
        if n in terdaftar or db.topik(teks.slug(n)):
            continue
        nama = asli.get(n, n)
        if teks.diblokir(nama, db.kanal.aturan.blokir):
            continue
        db.upsert_topik(
            teks.slug(n),
            nama,
            PILAR_ARSIP.get(nama, "misteri"),
            [n],
            [],
            status="dibahas" if jenis == "shorts" else "long",
            catatan="arsip akun lama",
        )
        hitung["arsip_baru"] += 1
    db.commit()
    return hitung


def daftar_sudah(db: DB) -> list[str]:
    return [t["nama"] for t in db.daftar("topik", "status IN ('dibahas', 'long')")]


def duplikat(db: DB, q: str, n: int = 5) -> list[tuple[str, float, str]]:
    """topik/episode lama yang paling mirip dengan q -> [(nama, kemiripan 0..1, status)]."""
    calon = [(t["nama"], t["status"]) for t in db.daftar("topik", "status IN ('dibahas', 'long')")]
    calon += [(e["judul"], "episode " + e["kode"]) for e in db.daftar("episode", "judul IS NOT NULL")]
    from rapidfuzz import fuzz

    hasil = []
    for nama, st in calon:
        utama = max(teks.mirip(q, nama), 1.0 if teks.kata_utuh_semua(q, nama) else 0.0)
        hasil.append((nama, utama, st, fuzz.token_sort_ratio(teks.norm(q), teks.norm(nama)) / 100.0))
    hasil.sort(key=lambda x: (-x[1], -x[3]))  # seri -> pilih yang paling lengkap cocoknya
    return [(a, b, c) for a, b, c, _ in hasil[:n]]


# ------------------------------------------------------------------------------------------------ impor performa
ALIAS = {
    "kode": ("content", "konten", "video id", "id video"),
    "judul": ("video title", "judul video"),
    "terbit": ("video publish time", "waktu publikasi video", "publish time"),
    "tayangan": ("views", "penayangan"),
    "durasi_tonton_jam": ("watch time (hours)", "waktu tonton (jam)"),
    "subscriber": ("subscribers", "subscriber", "pelanggan"),
    "impresi": ("impressions", "tayangan"),
    "ctr": ("impressions click-through rate (%)", "rasio klik-tayang tayangan (%)"),
    "rata_durasi": ("average view duration", "durasi rata-rata dilihat", "durasi penayangan rata-rata"),
    "persen_ditonton": ("average percentage viewed (%)", "persentase rata-rata dilihat (%)"),
}


def _angka(s: Any) -> float | None:
    s = str(s or "").strip().replace("%", "")
    if not s:
        return None
    if re.match(r"^\d+(:\d{2}){1,2}$", s):
        return float(sum(int(x) * 60**i for i, x in enumerate(reversed(s.split(":")))))
    s = s.replace(",", ".") if s.count(",") == 1 and "." not in s else s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _peta_kolom(header: Sequence[str]) -> dict[str, str]:
    h = {x.strip().lower(): x for x in header}
    out: dict[str, str] = {}
    for kunci, alias in ALIAS.items():
        for a in alias:
            if a in h and h[a] not in out.values():
                out[kunci] = h[a]
                break
    return out


def impor_studio(db: DB, path: Path | str, tanggal: dt.date | None = None) -> int:
    """CSV 'Table data' ekspor YouTube Studio (Analytics > Advanced mode > Export) -> tabel performa."""
    tanggal = tanggal or hari_ini_wib()
    with open(path, encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        peta = _peta_kolom(rd.fieldnames or [])
        if "tayangan" not in peta or ("kode" not in peta and "judul" not in peta):
            raise ValueError(f"bukan CSV YouTube Studio yang dikenal (kolom: {rd.fieldnames})")
        episode = db.daftar("episode")
        n = 0
        for r in rd:
            kode = (r.get(peta.get("kode", ""), "") or "").strip()
            judul = (r.get(peta.get("judul", ""), "") or "").strip()
            if kode.lower() in ("total", "") and not judul:
                continue
            if kode.lower() == "total":
                continue
            ep = next((e for e in episode if kode and e.get("youtube_id") == kode), None)
            if ep is None and judul:
                skor = [(teks.mirip(judul, e.get("judul") or ""), e) for e in episode if e.get("judul")]
                skor.sort(key=lambda x: -x[0])
                ep = skor[0][1] if skor and skor[0][0] >= 0.9 else None
            pilar = None
            if ep and ep.get("topik_id"):
                t = db.ambil("topik", id=ep["topik_id"])
                pilar = t["pilar"] if t else None
            db.upsert_performa(
                {
                    "episode_id": ep["id"] if ep else None,
                    "kode": (ep["kode"] if ep else kode or judul[:60]),
                    "judul": judul or None,
                    "tanggal": tanggal.isoformat(),
                    "tayangan": int(_angka(r.get(peta["tayangan"])) or 0),
                    "durasi_tonton_jam": _angka(r.get(peta.get("durasi_tonton_jam", ""))),
                    "rata_durasi_detik": _angka(r.get(peta.get("rata_durasi", ""))),
                    "persen_ditonton": _angka(r.get(peta.get("persen_ditonton", ""))),
                    "impresi": int(_angka(r.get(peta.get("impresi", ""))) or 0) or None,
                    "ctr": _angka(r.get(peta.get("ctr", ""))),
                    "subscriber": int(_angka(r.get(peta.get("subscriber", ""))) or 0),
                    "pilar": pilar,
                    "sumber": "studio_csv",
                }
            )
            n += 1
    db.commit()
    return n


def impor_performa_csv(db: DB, path: Path | str, tanggal: dt.date | None = None) -> int:
    """format lama analisis/performa.csv: episode,pilar,views,retensi."""
    tanggal = tanggal or hari_ini_wib()
    n = 0
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            p = (r.get("pilar") or "").strip()
            if p not in TEMA_PILAR or not r.get("episode"):
                continue
            db.upsert_performa(
                {
                    "kode": r["episode"].strip(),
                    "tanggal": tanggal.isoformat(),
                    "tayangan": int(_angka(r.get("views")) or 0),
                    "persen_ditonton": _angka(r.get("retensi")),
                    "pilar": p,
                    "sumber": "performa_csv",
                }
            )
            n += 1
    db.commit()
    return n


TEMA_PILAR = {t.pilar for t in TEMA.values()}


# ------------------------------------------------------------------------------------------------ PUSTAKA.md
def _tabel(rows: list[dict[str, Any]], kolom_kode: str) -> list[str]:
    out = [f"| {kolom_kode} | Status | Tanggal tayang | Topik | Judul terpilih | Folder |", "|---|---|---|---|---|---|"]
    if not rows:
        return out + ["| - | - | - | (belum ada) | - | - |"]
    for r in rows:
        out.append(
            f"| {r['kode']} | {r['status']} | {(r.get('tayang') or r.get('jadwal_tayang') or '-')[:10]} | "
            f"{r.get('topik') or '-'} | {r.get('judul') or '-'} | {r.get('slug') or '-'} |"
        )
    return out


def tulis_md(db: DB, path: Path = PUSTAKA_MD) -> Path:
    s = path.read_text(encoding="utf-8") if path.exists() else "# PUSTAKA KlikTahu - indeks episode\n"
    eps = []
    for e in db.daftar("episode", urut="kode"):
        t = db.ambil("topik", id=e["topik_id"]) if e.get("topik_id") else None
        eps.append({**e, "topik": t["nama"] if t else None})
    blok_s = "\n".join(_tabel([e for e in eps if e["format"] == "shorts"], "Ep"))
    blok_l = "\n".join(_tabel([e for e in eps if e["format"] == "long"], "Long"))
    s = re.sub(
        r"(## Episode baru \(setelah rebuild\)\n\n)(\|.*?\n)(?=\n## )",
        lambda m: m.group(1) + blok_s + "\n",
        s,
        flags=re.S,
    )
    s = re.sub(r"(## Video panjang baru\n\n)(\|.*?\n)(?=\n## )", lambda m: m.group(1) + blok_l + "\n", s, flags=re.S)
    m = _BLOK.search(s)
    if m:
        ada = sudah_dibahas(path)
        tambah = []
        for e in eps:
            if e["status"] == "rilis" and e.get("topik") and teks.norm(e["topik"]) not in ada:
                tambah.append(("- Long: " if e["format"] == "long" else "- ") + e["topik"])
        if tambah:
            isi = m.group(2).rstrip("\n") + "\n" + "\n".join(tambah) + "\n"
            s = s[: m.start(2)] + isi + s[m.end(2) :]
    path.write_text(s, encoding="utf-8")
    return path
