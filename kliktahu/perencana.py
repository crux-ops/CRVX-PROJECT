"""kliktahu/perencana.py - PERENCANA TOPIK: kalender konten N minggu + deteksi momen + berkas ICS.

* slot Shorts per minggu & Long per bulan dari kanal.toml, jam unggah terbaik (WIB)
* topik BERMOMEN dijadwalkan `momen_hari_sebelum` hari SEBELUM event (bukan sesudah)
* sisa slot diisi peringkat PELUANG v7 riset terakhir; pilar tidak dobel berturut-turut
* Long: topik dengan pohon pertanyaan lebar & dalam (v4) dan evergreen
* entri 'terkunci'/'selesai' milik pemilik tidak pernah ditimpa; hasil = usulan
Keluaran: laporan/KALENDER.md + laporan/kalender.ics (impor ke Google Calendar) + tabel rencana di basis data.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path
from typing import Any

from . import ROOT, momen, skor, teks
from .db import DB, hari_ini_wib
from .tema import TEMA

LAPORAN = ROOT / "laporan"
URUT_HARI = (0, 2, 4, 1, 3, 5, 6)  # Sen, Rab, Jum, Sel, Kam, Sab, Min


def _peringkat(db: DB) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    run = db.run_terakhir() or db.run_terakhir(mode=("uji",))
    if not run:
        return [], None
    return [r for r in db.skor_run(run["id"]) if r["status_topik"] != "dibahas"], run


def slot(k: Any, mulai: dt.date, minggu: int) -> list[dict[str, str]]:
    out = []
    hari = sorted(URUT_HARI[: k.jadwal.shorts_per_minggu]) if k.jadwal.shorts_per_minggu <= 7 else list(range(7))
    per_hari = max(1, -(-k.jadwal.shorts_per_minggu // 7))
    for i in range(minggu * 7):
        d = mulai + dt.timedelta(days=i)
        if d.weekday() in hari:
            for j in range(per_hari):
                out.append(
                    {
                        "tanggal": d.isoformat(),
                        "jam": k.jadwal.slot_wib[(i + j) % len(k.jadwal.slot_wib)],
                        "format": "shorts",
                    }
                )
    if k.jadwal.long_per_bulan:
        jarak = max(7, 28 // k.jadwal.long_per_bulan)
        sabtu = [
            mulai + dt.timedelta(days=i) for i in range(minggu * 7) if (mulai + dt.timedelta(days=i)).weekday() == 5
        ]
        terakhir = None
        for d in sabtu:
            if terakhir is None or (d - terakhir).days >= jarak:
                out.append({"tanggal": d.isoformat(), "jam": k.jadwal.slot_wib[-1], "format": "long"})
                terakhir = d
    return sorted(out, key=lambda s: (s["tanggal"], s["jam"], s["format"]))


def susun(db: DB, hari_ini: dt.date | None = None, minggu: int = 4, simpan: bool = True) -> list[dict[str, Any]]:
    k = db.kanal
    hari_ini = hari_ini or hari_ini_wib()
    mulai = hari_ini + dt.timedelta(days=1)
    akhir = mulai + dt.timedelta(days=minggu * 7 - 1)
    rank, run = _peringkat(db)
    live = [
        momen.Momen(dt.date.fromisoformat(m["tanggal"]), m["nama"], m["tema"], m["jenis"], m["sumber"], m["urgensi"])
        for m in db.momen_antara(hari_ini - dt.timedelta(days=3), akhir)
        if m["jenis"] in ("live", "agen")
    ]
    daftar_m = momen.semua(hari_ini, minggu * 7 + 30, live)
    slots = slot(k, mulai, minggu)
    kunci = {(r["tanggal"], r["jam"], r["format"]) for r in db.daftar("rencana", "status IN ('terkunci', 'selesai')")}
    bebas = [s for s in slots if (s["tanggal"], s["jam"], s["format"]) not in kunci]
    dipakai: set[str] = {teks.norm(r["judul_kerja"] or "") for r in db.daftar("rencana", "status = 'terkunci'")}
    isi: dict[int, dict[str, Any]] = {}

    # 1) topik bermomen -> slot Shorts terdekat SEBELUM (event - N hari). Syarat: momen kuat (>= 0.5 atau live),
    #    peluang v7 minimal median kandidat, dan SATU topik terbaik per event (tidak menumpuk satu momen).
    ambang = sorted(r["v7_peluang"] for r in rank)[len(rank) // 2] if rank else 0.0
    event_dipakai: set[tuple[str, str]] = set()
    for r in rank:
        nama = r["nama"]
        if nama not in TEMA or teks.norm(nama) in dipakai:
            continue
        s_m, m = momen.skor_tema(nama, daftar_m, hari_ini, k.jadwal.jendela_momen_hari)
        if not m or (s_m < 0.5 and m.jenis not in ("live", "agen")) or r["v7_peluang"] < ambang:
            continue
        kunci_ev = (m.tanggal.isoformat(), teks.norm(m.nama.split(":")[0]))
        if kunci_ev in event_dipakai:
            continue
        target = m.tanggal - dt.timedelta(days=k.jadwal.momen_hari_sebelum)
        pilihan = [
            i
            for i, s in enumerate(bebas)
            if s["format"] == "shorts" and i not in isi and dt.date.fromisoformat(s["tanggal"]) <= max(target, mulai)
        ]
        if not pilihan:
            continue
        i = pilihan[-1]
        event_dipakai.add(kunci_ev)
        isi[i] = {
            **bebas[i],
            "tema": nama,
            "skor": r["v7_peluang"],
            "momen": m,
            "alasan": f"momen: {m.nama} ({m.tanggal}); peluang {r['v7_peluang']:.1f}",
        }
        dipakai.add(teks.norm(nama))
    # 2) Long: pohon pertanyaan lebar & dalam
    for i, s in enumerate(bebas):
        if s["format"] != "long" or i in isi:
            continue
        cocok = [
            r
            for r in rank
            if teks.norm(r["nama"]) not in dipakai
            and r["nama"] in TEMA
            and skor.format_saran(
                r["sinyal"].get("jaring", 0), r["sinyal"].get("kedalaman", 0), TEMA[r["nama"]].ever, r["v7_peluang"]
            )
            == "long"
        ]
        cocok = cocok or [
            r for r in rank if teks.norm(r["nama"]) not in dipakai and r["nama"] in TEMA and TEMA[r["nama"]].ever
        ]
        if cocok:
            r = cocok[0]
            isi[i] = {
                **s,
                "tema": r["nama"],
                "skor": r["v7_peluang"],
                "momen": None,
                "alasan": f"deep-dive evergreen; peluang {r['v7_peluang']:.1f}, jaring v4 {r['sinyal'].get('jaring', 0)}",
            }
            dipakai.add(teks.norm(r["nama"]))
    # 3) sisa Shorts: peringkat v7, pilar tidak dobel berturut-turut
    sisa = [r for r in rank if r["nama"] in TEMA and teks.norm(r["nama"]) not in dipakai]
    pilar_lalu = None
    for i, s in enumerate(bebas):
        if i in isi:
            pilar_lalu = TEMA[isi[i]["tema"]].pilar
            continue
        if s["format"] != "shorts" or not sisa:
            continue
        r = next((x for x in sisa if TEMA[x["nama"]].pilar != pilar_lalu), sisa[0])
        sisa.remove(r)
        isi[i] = {
            **s,
            "tema": r["nama"],
            "skor": r["v7_peluang"],
            "momen": None,
            "alasan": f"peringkat #{r['peringkat']} peluang {r['v7_peluang']:.1f}",
        }
        pilar_lalu = TEMA[r["nama"]].pilar
    # kode episode berurutan menurut tanggal
    kode_s, kode_l = db.kode_berikut("shorts"), db.kode_berikut("long")
    ns, nl = int(kode_s[2:]), int(kode_l[4:])
    rows = []
    for i in sorted(isi, key=lambda i: (bebas[i]["tanggal"], bebas[i]["jam"])):
        e = isi[i]
        if e["format"] == "shorts":
            kode, ns = f"Ep{ns:02d}", ns + 1
        else:
            kode, nl = f"Long{nl:02d}", nl + 1
        t = db.topik(e["tema"])
        mid = None
        if e.get("momen") is not None:
            mm = db.ambil("momen", tanggal=e["momen"].tanggal.isoformat(), nama=e["momen"].nama)
            mid = mm["id"] if mm else None
        rows.append(
            {
                "tanggal": e["tanggal"],
                "jam": e["jam"],
                "format": e["format"],
                "topik_id": t["id"] if t else None,
                "episode_kode": kode,
                "judul_kerja": e["tema"],
                "alasan": e["alasan"],
                "momen_id": mid,
                "skor": round(e["skor"], 2),
                "status": "usulan",
            }
        )
    if simpan:
        db.ganti_rencana_usulan(mulai, akhir, rows)
    return rows


def tulis_md(rows: list[dict[str, Any]], path: Path, hari_ini: dt.date, run_ket: str = "") -> Path:
    L = [
        f"# KALENDER KONTEN KlikTahu - disusun {hari_ini}",
        "",
        "Usulan perencana (status 'usulan'); kunci slot dengan `python3 -m kliktahu rencana kunci <tanggal> <jam> <format>`."
        + (f" Dasar peringkat: {run_ket}." if run_ket else ""),
        "",
        "| tanggal | hari | jam WIB | format | kode | topik | alasan |",
        "|---|---|---|---|---|---|---|",
    ]
    nama_hari = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]
    for r in rows:
        d = dt.date.fromisoformat(r["tanggal"])
        L.append(
            f"| {r['tanggal']} | {nama_hari[d.weekday()]} | {r['jam']} | {r['format']} | {r['episode_kode']} | "
            f"{r['judul_kerja']} | {r['alasan']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return path


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _lipat(baris: str) -> list[str]:
    """lipat baris ICS maksimal 75 oktet (RFC 5545 §3.1)."""
    b = baris.encode("utf-8")
    out, i, pertama = [], 0, True
    while i < len(b):
        n = 75 if pertama else 74
        j = min(len(b), i + n)
        while j < len(b) and (b[j] & 0xC0) == 0x80:
            j -= 1
        out.append(("" if pertama else " ") + b[i:j].decode("utf-8"))
        i, pertama = j, False
    return out or [""]


def tulis_ics(rows: list[dict[str, Any]], path: Path, hari_ini: dt.date, nama_kanal: str = "KlikTahu") -> Path:
    wib = dt.timezone(dt.timedelta(hours=7))
    L = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//{nama_kanal}//Perencana Konten//ID",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{nama_kanal} - Rencana Konten",
        "X-WR-TIMEZONE:Asia/Jakarta",
    ]
    stamp = f"{hari_ini:%Y%m%d}T000000Z"
    for r in rows:
        jj, mm = (int(x) for x in r["jam"].split(":"))
        d = dt.date.fromisoformat(r["tanggal"])
        mulai = dt.datetime(d.year, d.month, d.day, jj, mm, tzinfo=wib).astimezone(dt.UTC)
        uid = hashlib.sha1(f"{r['tanggal']}|{r['jam']}|{r['format']}".encode()).hexdigest()[:16]
        ringkas = f"{nama_kanal} {r['episode_kode']} ({r['format']}): {r['judul_kerja']}"
        L += [
            "BEGIN:VEVENT",
            f"UID:{uid}@kliktahu",
            f"DTSTAMP:{stamp}",
            f"DTSTART:{mulai:%Y%m%dT%H%M%SZ}",
            "DURATION:PT30M",
            f"SUMMARY:{_esc(ringkas)}",
            f"DESCRIPTION:{_esc(r['alasan'] or '')}",
            f"CATEGORIES:{nama_kanal},{r['format'].capitalize()}",
            "END:VEVENT",
        ]
    L.append("END:VCALENDAR")
    isi = "\r\n".join(x for b in L for x in _lipat(b)) + "\r\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(isi.encode("utf-8"))
    return path
