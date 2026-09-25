"""kliktahu/metadata.py - GENERATOR METADATA (3 judul, deskripsi, hashtag, tag) dari hasil riset + LINT ketat.

Judul dibentuk dari frasa pencarian ASLI (autocomplete Google/YouTube hasil riset), diberi skor (kata kunci di
depan, panjang ideal layar HP, pola rasa penasaran yang jujur, beda dari judul pesaing) lalu dipilih 3 yang
BERAGAM (MMR). Deskripsi: baris pertama = kata kunci utama, bab/timestamp dari timeline.json, sumber kredibel,
disclaimer kesehatan bila perlu. Tag dihitung CARA YOUTUBE (<= 500). Semua ASCII (aturan METADATA pemilik).

Lint (`python3 -m kliktahu metadata cek <METADATA.md>`) dipakai tools/render_lokal.sh sebagai GERBANG:
render ditolak bila METADATA.md belum lengkap/valid (aturan keras: metadata lengkap SEBELUM render).
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

from . import ROOT, teks
from . import kanal as kanal_mod
from .tema import BENCANA, TEMA

TAG_MAKS_KARAKTER = 60  # batas aman per tag (frasa long-tail <= ~8 kata); total tetap <= 500 cara YouTube
PENASARAN = ("ternyata", "padahal", "rahasia", "jarang", "kenapa", "apakah", "bagaimana", "misteri", "jawaban")
UMPAN_BOHONG = ("100%", "dijamin", "pasti terbukti", "terbukti mutlak", "dokter kaget", "wajib tonton", "viral banget")
TEMPLAT = {
    "tanya": [
        "{F}? Ini Jawaban Sainsnya",
        "{F}? Ternyata Ini Penyebabnya",
        "{F}? Jawabannya Tidak Seperti Dugaanmu",
        "{F}? Begini Penjelasan Ilmiahnya",
    ],
    "inti": [
        "Fakta {I} yang Jarang Diketahui",
        "Rahasia di Balik {I} yang Bikin Kaget",
    ],
    "misteri": ["Misteri {I} Akhirnya Terjawab"],  # hanya pilar misteri (jujur: bukan untuk topik yang tidak misterius)
    "shorts": ["{F}? Ini Kata Sains"],
    "long": ["{F}? Penjelasan Lengkap dari Nol", "Semua Tentang {I}: Dari Nol Sampai Paham"],
    "momen": ["{M}: {F}?"],
}
# topik BENCANA (korban jiwa nyata): templat bernada sensasi dibuang, kata berikut GALAT di judul/deskripsi
TEMPLAT_SENSASI = {"Rahasia di Balik {I} yang Bikin Kaget", "{F}? Jawabannya Tidak Seperti Dugaanmu"}
KATA_SENSASI = ("seru", "bikin kaget", "ngeri", "mengerikan", "merinding", "heboh", "kiamat", "seram")


@dataclass
class Paket:
    format: str
    tema: str
    kata_kunci: str
    judul: list[str]
    deskripsi: str
    hashtag: list[str]
    tag: list[str]
    sumber: list[dict[str, Any]] = field(default_factory=list)
    skor_judul: list[float] = field(default_factory=list)
    galat: list[str] = field(default_factory=list)
    peringatan: list[str] = field(default_factory=list)
    final: bool = False

    @property
    def tag_karakter(self) -> int:
        return teks.panjang_tag_youtube(self.tag)

    @property
    def lulus(self) -> bool:
        return not self.galat

    def baris_db(self, topik_id: int | None, episode_id: int | None = None, run_id: int | None = None) -> dict:
        return {
            "topik_id": topik_id,
            "episode_id": episode_id,
            "run_id": run_id,
            "format": self.format,
            "kata_kunci": self.kata_kunci,
            "judul": self.judul,
            "judul_terpilih": self.judul[0] if self.judul else None,
            "deskripsi": self.deskripsi,
            "hashtag": self.hashtag,
            "tag": self.tag,
            "tag_karakter": self.tag_karakter,
            "sumber": self.sumber,
            "lint": self.galat + [f"peringatan: {p}" for p in self.peringatan],
            "lulus": self.lulus,
        }


# ================================================================================================ bahan
def _bersih(s: str) -> str:
    return re.sub(r"[<>]", "", teks.ascii_saja(s)).strip()


def frasa_layak(frasa: Sequence[str], k: kanal_mod.Kanal) -> list[str]:
    """frasa pencarian yang boleh dipakai di judul/tag: bersih, tidak diblokir, tidak sensitif, 2-8 kata."""
    out = []
    for f in frasa:
        f = teks.norm(f)
        if not f or teks.diblokir(f, k.aturan.blokir) or teks.sensitif(f, k.aturan.sensitif):
            continue
        if teks.kena(f, k.aturan.hindari_hook) or not 2 <= len(f.split()) <= 8:
            continue
        out.append(f)
    return teks.unik_fuzzy(out, 0.92)


def kata_kunci_utama(frasa: Sequence[str], inti: str) -> str:
    inti_n = teks.norm(inti)
    for awal in ("kenapa", "apakah", "bagaimana"):
        for f in frasa:
            if f.startswith(awal + " ") and inti_n in f and len(f.split()) <= 6:
                return f
    return next((f for f in frasa if inti_n in f), inti_n)


# ================================================================================================ judul
def skor_judul(j: str, kata_kunci: str, inti: str, format_: str, pesaing: Sequence[str], k: kanal_mod.Kanal) -> float:
    if not j or len(j) > k.metadata.maks_judul or not j.isascii() or re.search(r"[<>]", j):
        return -100.0
    if teks.diblokir(j, k.aturan.blokir) or teks.sensitif(j, k.aturan.sensitif) or teks.kena(j, k.aturan.hindari_hook):
        return -100.0
    jn = teks.norm(j)
    ideal = k.metadata.ideal_judul_shorts if format_ == "shorts" else k.metadata.ideal_judul_long
    s = 2.0 if len(j) <= ideal else 2.0 - 0.08 * (len(j) - ideal)
    if len(j) < 25:
        s -= 1.0
    if teks.norm(inti) in jn[:40]:
        s += 2.0
    kk = " ".join(teks.norm(kata_kunci).split()[:3])
    if kk and jn.startswith(kk):
        s += 1.5
    if "?" in j or any(w in jn.split() for w in PENASARAN):
        s += 1.0
    if re.search(r"\d", j):
        s += 0.3
    kapital = [w for w in re.findall(r"[A-Za-z]{3,}", j) if w.isupper()]
    s -= max(0, len(kapital) - 1) * 1.0
    if any(u in j.lower() for u in UMPAN_BOHONG):
        s -= 2.0
    if pesaing:
        _, mirip = teks.paling_mirip(j, list(pesaing))
        s += -2.0 if mirip > 0.85 else (0.8 if mirip < 0.6 else 0.0)
    return round(s, 3)


def kandidat_judul(
    frasa: Sequence[str],
    inti: str,
    format_: str,
    momen: str | None = None,
    tambahan: Sequence[str] = (),
    pilar: str = "",
    hormat: bool = False,
) -> list[str]:
    """hormat=True (topik bencana): templat sensasional tidak dipakai."""
    I = teks.kapital_judul(inti)
    out = [_bersih(x) for x in tambahan]

    def pakai(daftar: list[str]) -> list[str]:
        return [t for t in daftar if not (hormat and t in TEMPLAT_SENSASI)]

    tanya = [f for f in frasa if f.split()[0] in ("kenapa", "apakah", "bagaimana")][:8] or list(frasa[:3])
    for f in tanya:
        F = teks.kapital_judul(f)
        out += [t.format(F=F, I=I) for t in pakai(TEMPLAT["tanya"] + TEMPLAT[format_])]
        if momen and len(f.split()) >= 4:  # judul momen hanya untuk pertanyaan SPESIFIK (bukan "{M}: Kenapa Tsunami?")
            out += [t.format(M=teks.kapital_judul(momen), F=F) for t in TEMPLAT["momen"]]
    out += [t.format(I=I) for t in pakai(TEMPLAT["inti"] + (TEMPLAT["misteri"] if pilar == "misteri" else []))]
    return list(dict.fromkeys(_bersih(x) for x in out if x))


def _inti_judul(j: str) -> str:
    """bagian pertanyaan/inti judul - dua judul dengan inti sama = pilihan yang sama. Judul momen '{M}: {F}?' -> F
    (pertanyaannya), selain itu bagian sebelum '?' atau ':'."""
    if ":" in j:
        kanan = j.split(":", 1)[1]
        if "?" in kanan:
            return teks.norm(kanan.split("?", 1)[0])
    return teks.norm(re.split(r"[?:]", j, maxsplit=1)[0])


_FUNGSI = {
    "kenapa",
    "mengapa",
    "apakah",
    "bagaimana",
    "padahal",
    "ada",
    "bisa",
    "keluar",
    "terjadi",
    "yang",
    "itu",
    "ini",
    "sih",
    "kok",
    "jadi",
    "di",
    "ke",
    "dan",
    "dengan",
    "saat",
    "sama",
    "punya",
    "memiliki",
    "tidak",
    "gak",
}


_SINONIM = {
    "kilat": "petir",
    "halilintar": "petir",
    "petirnya": "petir",
    "barengan": "bersamaan",
    "serentak": "bersamaan",
    "apinya": "api",
    "lahar": "lava",
    "gatal": "gatal",
    "menular": "menular",
    "berwarna": "warna",
}


def _kata_sudut(j: str, inti: str) -> set[str]:
    """kata PEMBEDA sudut sebuah judul: bagian pertanyaan tanpa kata inti & kata fungsi ('ada petir' = {'petir'})."""
    buang = set(teks.norm(inti).split()) | _FUNGSI
    return {_SINONIM.get(w, w) for w in _inti_judul(j).split() if w not in buang and len(w) > 2}


def _mirip_judul(a: str, b: str, inti: str = "") -> float:
    if _inti_judul(a) == _inti_judul(b):
        return 1.0
    ka, kb = _kata_sudut(a, inti), _kata_sudut(b, inti)
    if (not ka and not kb and "?" in a and "?" in b) or (ka & kb):
        return 1.0  # sudut sama walau kata kerjanya beda ("ada petir" vs "keluar petir")
    return 0.6 * teks.mirip(a, b)


def pilih_beragam(
    kandidat: list[tuple[str, float]], n: int = 3, lam: float = 3.0, inti: str = ""
) -> list[tuple[str, float]]:
    """MMR: skor tinggi TAPI tidak mirip judul yang sudah terpilih (3 pilihan benar-benar berbeda sudutnya)."""
    sisa = sorted([c for c in kandidat if c[1] > -50], key=lambda c: -c[1])
    pilih: list[tuple[str, float]] = []
    while sisa and len(pilih) < n:
        terbaik = max(
            sisa, key=lambda c: c[1] - lam * max((_mirip_judul(c[0], p[0], inti) for p in pilih), default=0.0)
        )
        pilih.append(terbaik)
        sisa.remove(terbaik)
    return pilih


# ================================================================================================ hashtag & tag
def buat_hashtag(tema: str, inti: str, format_: str, k: kanal_mod.Kanal) -> list[str]:
    out = list(k.metadata.hashtag_wajib)
    for h in (teks.hashtag(inti), teks.hashtag(tema.replace("&", " ")) if "&" not in tema else ""):
        if h and h.lower() not in (x.lower() for x in out) and len(h) <= 30:
            out.append(h)
    if format_ == "shorts":
        out.append(k.metadata.hashtag_shorts)
    return out[: k.metadata.maks_hashtag]


def buat_tag(
    kata_kunci: str, inti: str, tema: str, frasa: Sequence[str], k: kanal_mod.Kanal, tambahan: Sequence[str] = ()
) -> list[str]:
    calon = [
        kata_kunci,
        inti,
        tema.replace("&", "dan"),
        *tambahan,
        *frasa,
        f"fakta {inti}",
        f"{inti} menurut sains",
        "fakta sains",
        "sains indonesia",
        k.nama.lower(),
    ]
    out: list[str] = []
    for c in calon:
        c = teks.norm(c)
        if (
            not c
            or len(c) > TAG_MAKS_KARAKTER
            or teks.diblokir(c, k.aturan.blokir)
            or teks.sensitif(c, k.aturan.sensitif)
        ):
            continue
        if any(fuzz.ratio(c, x) >= 92 for x in out):  # hampir identik saja (subset BUKAN duplikat)
            continue
        if teks.panjang_tag_youtube([*out, c]) <= k.metadata.maks_tag_karakter:
            out.append(c)
    return out


# ================================================================================================ deskripsi
def _mmss(detik: float) -> str:
    d = int(round(detik))
    return f"{d // 3600}:{d % 3600 // 60:02d}:{d % 60:02d}" if d >= 3600 else f"{d // 60}:{d % 60:02d}"


def bab_dari_timeline(konten: dict[str, Any], timeline: dict[str, Any]) -> list[tuple[float, str]]:
    lab = {}
    n_fakta = 0
    for sc in konten.get("scenes", []):
        tp = sc.get("type")
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
) -> str:
    kk = teks.kalimat(kata_kunci)
    baris = [kk + ("?" if kk.split()[0].lower() in ("kenapa", "apakah", "bagaimana") and not kk.endswith("?") else "")]
    bencana = BENCANA.get(tema)
    if hook and "?" in hook and teks.norm(hook.split("?", 1)[0]) == teks.norm(baris[0]):
        hook = hook.split("?", 1)[1].strip()  # hook mengulang pertanyaan baris 1 -> ambil sisanya saja
    if hook:
        baris.append(_bersih(hook))
    elif bencana:  # korban jiwa nyata -> tanpa "lebih seru"
        baris.append("Ini penjelasan sainsnya - pengetahuan yang membantu kita lebih siap.")
    else:
        baris.append("Jawabannya ada di sains - dan lebih seru dari yang kamu kira.")
    baris += [
        "",
        _bersih(ringkas)
        if ringkas
        else (
            f"Di video ini {inti} dijelaskan dari nol: apa yang sebenarnya terjadi, kenapa bisa begitu, "
            + ("dan apa yang perlu kita tahu agar lebih siap." if bencana else "dan fakta yang jarang diketahui.")
            + " Animasi sederhana, tanpa ribet."
        ),
    ]
    baris += ["", "Bab:"]
    baris += [f"{_mmss(t)} {lab}" for t, lab in bab] if bab else ["0:00 (timestamp diisi dari timeline.json)"]
    baris += ["", "Sumber:"]
    baris += (
        [_baris_sumber(s) for s in sumber] if sumber else ["- (diisi saat riset: NASA/ESA/NOAA/NHS/Mayo Clinic/jurnal)"]
    )
    if bencana:
        baris += ["", f"Info resmi & peringatan dini: {bencana}. Ikuti arahan petugas setempat."]
    if TEMA.get(tema) and TEMA[tema].pilar in k.aturan.pilar_kesehatan:
        baris += ["", k.aturan.disclaimer_kesehatan]
    baris += ["", k.metadata.cta, "", " ".join(hashtag)]
    return "\n".join(_bersih(b) if b else "" for b in baris).strip() + "\n"


# ================================================================================================ rakit
def buat(
    tema: str,
    frasa: Sequence[str],
    format_: str = "shorts",
    k: kanal_mod.Kanal | None = None,
    kata_kunci: str | None = None,
    hook: str | None = None,
    pesaing_judul: Sequence[str] = (),
    sumber: Sequence[dict[str, Any]] = (),
    konten: dict[str, Any] | None = None,
    timeline: dict[str, Any] | None = None,
    momen: str | None = None,
    judul_tambahan: Sequence[str] = (),
    ringkas: str | None = None,
    final: bool = False,
) -> Paket:
    k = k or kanal_mod.muat()
    t = TEMA.get(tema)
    inti = t.inti if t else tema
    fr = frasa_layak(frasa, k)
    kk = teks.norm(kata_kunci) if kata_kunci else kata_kunci_utama(fr, inti)
    calon = kandidat_judul(fr, inti, format_, momen, judul_tambahan, t.pilar if t else "", hormat=tema in BENCANA)
    bernilai = [(j, skor_judul(j, kk, inti, format_, pesaing_judul, k)) for j in calon]
    pilih = pilih_beragam(bernilai, 3, inti=inti)
    tagar = buat_hashtag(tema, inti, format_, k)
    bab = bab_dari_timeline(konten, timeline) if konten and timeline else []
    src = list(sumber) or (sumber_dari_konten(konten) if konten else [])
    desk = buat_deskripsi(kk, inti, tema, format_, k, hook, ringkas, bab, src, tagar)
    p = Paket(
        format_,
        tema,
        kk,
        [j for j, _ in pilih],
        desk,
        tagar,
        buat_tag(kk, inti, tema, fr, k),
        src,
        [s for _, s in pilih],
    )
    p.final = final
    p.galat, p.peringatan = lint(p, k, final=final, pilar=t.pilar if t else None)
    return p


# ================================================================================================ lint
def lint(p: Paket, k: kanal_mod.Kanal, final: bool = True, pilar: str | None = None) -> tuple[list[str], list[str]]:
    g: list[str] = []
    w: list[str] = []
    if len(p.judul) != 3:
        g.append(f"harus 3 pilihan judul (ada {len(p.judul)})")
    for i, j in enumerate(p.judul, 1):
        if not j.isascii():
            g.append(f"judul {i} tidak ASCII")
        if len(j) > k.metadata.maks_judul:
            g.append(f"judul {i} > {k.metadata.maks_judul} karakter")
        if re.search(r"[<>]", j):
            g.append(f"judul {i} memuat < atau > (ditolak YouTube)")
        if teks.diblokir(j, k.aturan.blokir):
            g.append(f"judul {i} memuat topik DIBLOKIR")
        if teks.sensitif(j, k.aturan.sensitif):
            g.append(f"judul {i} memuat kata sensitif")
        ideal = k.metadata.ideal_judul_shorts if p.format == "shorts" else k.metadata.ideal_judul_long
        if len(j) > ideal:
            w.append(f"judul {i} {len(j)} karakter (> ideal {ideal}, bisa terpotong di HP)")
    g += lint_deskripsi(p.deskripsi, p.format, k, final, pilar, p.judul[0] if p.judul else "")
    if p.tema in BENCANA:
        for nama, isi in [*[(f"judul {i}", j) for i, j in enumerate(p.judul, 1)], ("deskripsi", p.deskripsi)]:
            kena = [x for x in KATA_SENSASI if re.search(rf"(?<![0-9a-z]){x}(?![0-9a-z])", teks.norm(isi))]
            if kena:
                g.append(f"{nama}: topik bencana tidak boleh bernada sensasi ({', '.join(kena)})")
    g += lint_hashtag(p.hashtag, p.format, k, w)
    g += lint_tag(p.tag, k)
    return g, w


def lint_deskripsi(d: str, format_: str, k: kanal_mod.Kanal, final: bool, pilar: str | None, judul1: str) -> list[str]:
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


def _detik(s: str) -> int:
    bag = [int(x) for x in s.split(":")]
    return bag[0] * 3600 + bag[1] * 60 + bag[2] if len(bag) == 3 else bag[0] * 60 + bag[1]


def lint_hashtag(h: Sequence[str], format_: str, k: kanal_mod.Kanal, w: list[str]) -> list[str]:
    g = []
    if not 1 <= len(h) <= k.metadata.maks_hashtag:
        g.append(f"hashtag harus 1..{k.metadata.maks_hashtag} (ada {len(h)})")
    for x in h:
        if not re.match(r"^#[A-Za-z0-9]{2,40}$", x):
            g.append(f"hashtag tidak sah: '{x}' (ASCII huruf/angka tanpa spasi)")
        if teks.diblokir(x, k.aturan.blokir) or teks.sensitif(x, k.aturan.sensitif):
            g.append(f"hashtag terlarang: '{x}'")
    rendah = [x.lower() for x in h]
    for x in k.metadata.hashtag_wajib:
        if x.lower() not in rendah:
            g.append(f"hashtag wajib hilang: {x}")
    if format_ == "shorts" and k.metadata.hashtag_shorts.lower() not in rendah:
        w.append(f"Shorts tanpa {k.metadata.hashtag_shorts}")
    return g


def lint_tag(tag: Sequence[str], k: kanal_mod.Kanal) -> list[str]:
    g = []
    if not tag:
        g.append("tag kosong")
    n = teks.panjang_tag_youtube(tag)
    if n > k.metadata.maks_tag_karakter:
        g.append(f"tag {n} karakter (hitungan YouTube) > {k.metadata.maks_tag_karakter}")
    for t in tag:
        if not t.isascii() or re.search(r"[<>,]", t):
            g.append(f"tag tidak sah: '{t}'")
        if teks.diblokir(t, k.aturan.blokir) or teks.sensitif(t, k.aturan.sensitif):
            g.append(f"tag terlarang: '{t}'")
    return g


# ================================================================================================ berkas MD
def tulis_md(p: Paket, path: Path | str, judul_halaman: str, catatan: str = "") -> Path:
    path = Path(path)
    status = "LULUS" if p.lulus else "GAGAL: " + "; ".join(p.galat)
    isi = [
        f"# METADATA - {_bersih(judul_halaman)}",
        "",
        f'> Dibuat oleh kliktahu/metadata.py. Format {p.format}. Kata kunci utama: "{p.kata_kunci}". '
        f"Lint {'final' if p.final else 'draf (lint final butuh bab dari timeline.json)'}: {status}."
        f"{(' ' + _bersih(catatan)) if catatan else ''}",
        "",
        "## 1. Judul (3 pilihan)",
        *[f"{i}. {j}" for i, j in enumerate(p.judul, 1)],
        "",
        "## 2. Deskripsi",
        "```text",
        p.deskripsi.rstrip("\n"),
        "```",
        "",
        "## 3. Hashtag",
        " ".join(p.hashtag),
        "",
        f"## 4. Tag ({p.tag_karakter}/500 karakter hitungan YouTube)",
        ", ".join(p.tag),
        "",
    ]
    if p.peringatan:
        isi += ["<!-- peringatan: " + " | ".join(_bersih(x) for x in p.peringatan) + " -->", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(isi), encoding="ascii", errors="strict")
    return path


def urai_md(s: str) -> dict[str, Any]:
    bag = {m.group(1): m.start() for m in re.finditer(r"(?m)^## ([1-4])\.", s)}
    if set(bag) != {"1", "2", "3", "4"}:
        raise ValueError(
            "METADATA.md harus punya 4 blok: '## 1. Judul', '## 2. Deskripsi', '## 3. Hashtag', '## 4. Tag'"
        )
    urut = sorted(bag.items(), key=lambda kv: kv[1])
    blok = {}
    for i, (n, a) in enumerate(urut):
        b = urut[i + 1][1] if i + 1 < len(urut) else len(s)
        blok[n] = s[a:b].split("\n", 1)[1] if "\n" in s[a:b] else ""
    judul = [re.sub(r"^\d\.\s*", "", ln).strip() for ln in blok["1"].splitlines() if re.match(r"^\d\.\s", ln)]
    m = re.search(r"```[a-z]*\n(.*?)```", blok["2"], re.S)
    desk = m.group(1) if m else blok["2"].strip()
    hashtag = re.findall(r"#\S+", re.sub(r"<!--.*?-->", "", blok["3"], flags=re.S))
    tag_txt = " ".join(ln for ln in re.sub(r"<!--.*?-->", "", blok["4"], flags=re.S).splitlines() if ln.strip())
    tag = [t.strip() for t in tag_txt.split(",") if t.strip()]
    return {"judul": judul, "deskripsi": desk, "hashtag": hashtag, "tag": tag}


def cek_md(
    path: Path | str,
    format_: str = "shorts",
    pilar: str | None = None,
    k: kanal_mod.Kanal | None = None,
    tema: str | None = None,
) -> tuple[list[str], list[str]]:
    """lint METADATA.md. Tema (bila tidak diberikan) dibaca dari content.json di folder yang sama -> pilar ikut
    diturunkan, sehingga gerbang render juga menegakkan disclaimer kesehatan & nada hormat topik bencana."""
    k = k or kanal_mod.muat()
    if tema is None:
        kj = Path(path).with_name("content.json")
        try:
            tema = json.loads(kj.read_text(encoding="utf-8")).get("topik") if kj.exists() else None
        except (ValueError, AttributeError):
            tema = None
    if tema in TEMA and not pilar:
        pilar = TEMA[tema].pilar
    raw = Path(path).read_bytes()
    try:
        s = raw.decode("ascii")
    except UnicodeDecodeError:
        return [f"{path}: berkas tidak ASCII (aturan METADATA)"], []
    try:
        d = urai_md(s)
    except ValueError as e:
        return [str(e)], []
    p = Paket(format_, tema if tema in TEMA else "", "", d["judul"], d["deskripsi"], d["hashtag"], d["tag"])
    return lint(p, k, final=True, pilar=pilar)


def tulis_siap_tempel(p: Paket, path: Path | str, kode: str, k: kanal_mod.Kanal, jam: str | None = None) -> Path:
    path = Path(path)
    isi = [
        f"# SIAP TEMPEL - {kode}",
        "",
        "Salin apa adanya ke YouTube Studio.",
        "",
        "## Judul (terpilih)",
        p.judul[0] if p.judul else "-",
        "",
        "## Deskripsi",
        "```text",
        p.deskripsi.rstrip("\n"),
        "```",
        "",
        "## Tag",
        ", ".join(p.tag),
        "",
        "## Komentar sematan",
        _bersih(k.metadata.komentar_sematan),
        "",
        "## Jam unggah (WIB)",
        jam or " atau ".join(k.jadwal.slot_wib),
        "",
        "## Judul cadangan",
        *[f"- {j}" for j in p.judul[1:]],
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(isi), encoding="ascii", errors="strict")
    return path


def muat_json(p: Path) -> dict[str, Any] | None:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def konteks_episode(slug: str, format_: str) -> tuple[dict[str, Any], dict[str, Any] | None, Path]:
    """(content.json, timeline.json | None, folder episode)."""
    d = ROOT / ("episodes" if format_ == "shorts" else "long") / slug
    konten = muat_json(d / "content.json")
    if konten is None:
        raise FileNotFoundError(f"{d}/content.json tidak ada")
    tl = muat_json(ROOT / "build" / (slug if format_ == "shorts" else f"long/{slug}") / "timeline.json")
    return konten, tl, d
