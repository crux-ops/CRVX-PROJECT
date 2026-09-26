"""kliktahu/meta/deskripsi.py - DESKRIPSI (tahap 8 rencana upgrade 2026-09).

Deskripsi harus SETIA pada bukti: hanya klaim yang statusnya didukung yang boleh masuk ringkasan; klaim yang
berstatus KONFLIK / TIDAK DIDUKUNG tidak diceritakan sebagai fakta. Bagian wajib:

1. baris pertama = kata kunci utama (penting untuk pencarian; di-lint agar nyambung dengan judul 1)
2. ringkasan yang lahir dari data (bukan hasil karangan), menyebut tanggal riset
3. bab/timestamp - HANYA bila timeline sudah ada (aturan keras: jangan membuat bab sebelum itu)
4. sumber dengan provenance: penerbit, judul, tahun, URL (atau DOI), dan tanggal diambil
5. disclaimer pilar kesehatan bila perlu; info resmi & nada hormat untuk topik bencana
6. ajakan (CTA) + hashtag

Panjang maksimal 5000 karakter (batas YouTube) dan ASCII saja (aturan pemilik §2.5).
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Sequence
from typing import Any

from .. import kanal as kanal_mod
from .. import teks
from ..tema import BENCANA

BAB_MIN_DETIK = 10.0  # syarat bab YouTube: tiap bab >= 10 detik, bab pertama 0:00, minimal 3 bab


def _bersih(s: str) -> str:
    return re.sub(r"[<>]", "", teks.ascii_saja(str(s))).strip()


def _mmss(detik: float) -> str:
    d = int(round(detik))
    return f"{d // 3600}:{d % 3600 // 60:02d}:{d % 60:02d}" if d >= 3600 else f"{d // 60}:{d % 60:02d}"


def bab_dari_timeline(konten: dict[str, Any], timeline: dict[str, Any]) -> list[tuple[float, str]]:
    """bab/timestamp dari timeline. Bab yang lebih pendek dari 10 detik digabung ke bab sebelumnya
    (YouTube menolak SEMUA bab bila ada yang < 10 detik)."""
    lab: dict[str, str] = {}
    n_fakta = 0
    for sc in konten.get("scenes", []):
        tp = sc.get("type")
        if sc.get("bab"):
            lab[sc["id"]] = str(sc["bab"])
            if tp == "fact":
                n_fakta += 1
            continue
        if tp == "intro":
            lab[sc["id"]] = "Pertanyaan"
        elif tp == "fact":
            n_fakta += 1
            lab[sc["id"]] = teks.kapital_judul((sc.get("badge") or sc.get("title") or f"Fakta {n_fakta}").lower())
        elif tp == "outro":
            lab[sc["id"]] = "Kesimpulan"
        elif tp == "bab":
            lab[sc["id"]] = teks.kapital_judul(sc.get("judul") or sc["id"])
    out = []
    for sc in timeline.get("scenes", []):
        if sc.get("id") in lab:
            out.append((float(sc["start"]), _bersih(lab[sc["id"]])))
    if out:
        out[0] = (0.0, out[0][1])
    total = float(timeline.get("total") or 0.0)
    if total > 0:
        rapi: list[tuple[float, str]] = []
        for i, (t0, nama) in enumerate(out):
            t1 = out[i + 1][0] if i + 1 < len(out) else total
            if rapi and t1 - t0 < BAB_MIN_DETIK:
                continue
            rapi.append((t0, nama))
        out = rapi
    return out


def sumber_dari_konten(konten: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(konten.get("sumber"), list):
        return [s if isinstance(s, dict) else {"judul": str(s)} for s in konten["sumber"]]
    for sc in konten.get("scenes", []):
        if sc.get("src"):
            return [{"judul": re.sub(r"(?i)^sumber:\s*", "", s).strip()} for s in sc["src"].split(";") if s.strip()]
    return []


def _baris_sumber(s: dict[str, Any]) -> str:
    bag = [s.get("penerbit"), s.get("judul"), f"({s['tahun']})" if s.get("tahun") else None, s.get("url")]
    return "- " + _bersih(" - ".join(str(b) for b in bag[:2] if b) + " " + " ".join(str(b) for b in bag[2:] if b))


def ringkasan_dari_klaim(
    klaim_terverifikasi: Sequence[Any], inti: str, bencana: str | None = None, maks: int = 3
) -> str:
    """ringkasan yang hanya memuat klaim berstatus DIDUKUNG/LEMAH. Klaim KONFLIK/TIDAK DIDUKUNG dibuang.

    `klaim_terverifikasi` = objek dengan atribut/kunci `teks`, `status`, `jenis` (lihat klaim.py).
    """
    boleh: list[str] = []
    for c in klaim_terverifikasi or []:
        st = getattr(c, "status", None) or (c.get("status") if isinstance(c, dict) else None)
        jn = getattr(c, "jenis", None) or (c.get("jenis") if isinstance(c, dict) else None)
        isi = getattr(c, "teks", None) or (c.get("teks") if isinstance(c, dict) else None)
        if not isi or jn == "sinyal_minat":
            continue
        if st in ("didukung", "lemah"):
            boleh.append(str(isi).rstrip("."))
        if len(boleh) >= maks:
            break
    if not boleh:
        return ""
    kalimat = ". ".join(boleh[:maks]).strip()
    return f"{kalimat[0].upper() + kalimat[1:]}."


def buat_deskripsi(
    kata_kunci: str,
    inti: str,
    tema: str,
    format_: str,
    k: kanal_mod.Kanal,
    hook: str | None = None,
    ringkas: str | None = None,
    bab: Sequence[tuple[float, str]] = (),
    sumber: Sequence[dict[str, Any]] = (),
    hashtag: Sequence[str] = (),
    tanggal_riset: str | None = None,
    status_sumber: str | None = None,
    pilar: str | None = None,
) -> str:
    kk = teks.kalimat(kata_kunci)
    baris = [kk + ("?" if kk.split()[0].lower() in ("kenapa", "apakah", "bagaimana") and not kk.endswith("?") else "")]
    bencana = BENCANA.get(tema)
    if hook and "?" in hook and teks.norm(hook.split("?", 1)[0]) == teks.norm(baris[0]):
        hook = hook.split("?", 1)[1].strip()
    if hook:
        baris.append(_bersih(hook))
    elif bencana:
        baris.append("Ini penjelasan sainsnya - pengetahuan yang membantu kita lebih siap.")
    else:
        baris.append("Jawabannya ada di sains - dan lebih seru dari yang kamu kira.")
    baris += ["", _bersih(ringkas) if ringkas else _ringkas_bawaan(inti, bencana)]
    baris += ["", "Bab:"]
    baris += [f"{_mmss(t)} {lab}" for t, lab in bab] if bab else ["0:00 (timestamp diisi dari timeline.json)"]
    baris += ["", "Sumber:"]
    baris += (
        [_baris_sumber(s) for s in sumber] if sumber else ["- (diisi saat riset: NASA/ESA/NOAA/NHS/Mayo Clinic/jurnal)"]
    )
    catatan: list[str] = []
    if tanggal_riset:
        catatan.append(f"Tanggal riset: {tanggal_riset}")
    if status_sumber:
        catatan.append(f"Status sumber: {status_sumber}")
    if catatan:
        baris += ["", _bersih(" | ".join(catatan))]
    if bencana:
        baris += ["", f"Info resmi & peringatan dini: {bencana}. Ikuti arahan petugas setempat."]
    if pilar and pilar in k.aturan.pilar_kesehatan:
        baris += ["", k.aturan.disclaimer_kesehatan]
    baris += ["", k.metadata.cta, "", " ".join(hashtag)]
    return "\n".join(_bersih(b) if b else "" for b in baris).strip() + "\n"


def _ringkas_bawaan(inti: str, bencana: str | None) -> str:
    return (
        f"Di video ini {inti} dijelaskan dari nol: apa yang sebenarnya terjadi, kenapa bisa begitu, "
        + ("dan apa yang perlu kita tahu agar lebih siap." if bencana else "dan fakta yang jarang diketahui.")
        + " Animasi sederhana, tanpa ribet."
    )


def _detik(s: str) -> int:
    bag = [int(x) for x in s.split(":")]
    return bag[0] * 3600 + bag[1] * 60 + bag[2] if len(bag) == 3 else bag[0] * 60 + bag[1]


def lint_deskripsi(
    d: str,
    format_: str,
    k: kanal_mod.Kanal,
    final: bool,
    pilar: str | None,
    judul1: str,
) -> list[str]:
    g = []
    if not d.strip():
        return ["deskripsi kosong"]
    if not d.isascii():
        g.append("deskripsi tidak ASCII")
    if len(d) > k.metadata.maks_deskripsi:
        g.append(f"deskripsi > {k.metadata.maks_deskripsi} karakter")
    if re.search(r"[<>]", d):
        g.append("deskripsi memuat < atau > (ditolak YouTube)")
    if teks.diblokir(d, k.aturan.blokir):
        g.append("deskripsi memuat topik DIBLOKIR")
    baris1 = d.strip().splitlines()[0]
    kata1 = {w for w in teks.norm(baris1).split() if len(w) >= 4}
    if judul1 and not kata1 & {w for w in teks.norm(judul1).split() if len(w) >= 4}:
        g.append("baris pertama deskripsi harus kata kunci utama (tidak nyambung dengan judul 1)")
    ts = [ln for ln in d.splitlines() if re.match(r"^\d{1,2}:\d{2}(:\d{2})? \S", ln)]
    if final:
        if "(timestamp diisi" in d:
            g.append("bab/timestamp belum diisi dari timeline.json")
        det = [_detik(ln.split()[0]) for ln in ts]
        if not det or det[0] != 0:
            g.append("bab harus dimulai 0:00")
        if det != sorted(det) or len(set(det)) != len(det):
            g.append("timestamp bab harus naik berurutan")
        min_bab = 3 if format_ == "long" else 2
        if len(det) < min_bab:
            g.append(f"minimal {min_bab} bab/timestamp")
        if format_ == "long" and any(b - a < 10 for a, b in zip(det, det[1:])):
            g.append("bab video panjang minimal berjarak 10 detik (syarat chapter YouTube)")
        if "(diisi saat riset" in d:
            g.append("sumber belum diisi")
    if not re.search(r"(?im)^sumber:", d):
        g.append("deskripsi wajib memuat bagian 'Sumber:'")
    if pilar and pilar in k.aturan.pilar_kesehatan and k.aturan.disclaimer_kesehatan.lower() not in d.lower():
        g.append(f"topik kesehatan wajib memuat: '{k.aturan.disclaimer_kesehatan}'")
    return g


def tanggal_hari_ini(hari: dt.date | None = None) -> str:
    return (hari or dt.datetime.now(dt.UTC).date()).isoformat()
