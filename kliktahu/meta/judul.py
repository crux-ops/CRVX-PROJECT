"""kliktahu/meta/judul.py - PEMBUAT JUDUL (tahap 7 rencana upgrade 2026-09).

Judul dibentuk dari SUDUT riset dan frasa pencarian ASLI, lalu dinilai:

* kata kunci di depan, panjang ideal layar HP (Shorts 60, Long 70), maksimal 100 (batas keras YouTube)
* rasa penasaran yang JUJUR: tidak menjanjikan angka/fakta yang tidak didukung bukti yang terkumpul
* beragam: tiga pilihan harus beda SUDUT, bukan beda kata (MMR dengan kemiripan sudut)
* uji duplikasi: judul yang inti pertanyaannya sama dianggap pilihan yang sama walau kata kerjanya beda
* uji bahasa: judul harus terbaca sebagai bahasa Indonesia (bukan campuran Inggris)
* aturan keras pemilik: ASCII, tanpa topik diblokir, tanpa kata sensitif, tanpa kata hindari_hook,
  dan topik bencana tanpa nada sensasi (mode hormat)

Semua fungsi MURNI (tanpa I/O) kecuali pembacaan berkas di `__main__`.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from rapidfuzz import fuzz

from .. import kanal as kanal_mod
from .. import teks
from ..tema import BENCANA

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
    "misteri": ["Misteri {I} Akhirnya Terjawab"],
    "shorts": ["{F}? Ini Kata Sains"],
    "long": ["{F}? Penjelasan Lengkap dari Nol", "Semua Tentang {I}: Dari Nol Sampai Paham"],
    "momen": ["{M}: {F}?"],
    # tahap 7: variasi yang dikunci ke SUDUT riset (bukan sekadar mengulang kata kunci)
    "sudut": [
        "{S}: Ini Penjelasan Sainsnya",
        "Ternyata Begini - {S}",
    ],
}
TEMPLAT_SENSASI = {"Rahasia di Balik {I} yang Bikin Kaget", "{F}? Jawabannya Tidak Seperti Dugaanmu"}
KATA_SENSASI = ("seru", "bikin kaget", "ngeri", "mengerikan", "merinding", "heboh", "kiamat", "seram")
KATA_KORBAN = ("korban", "tewas", "meninggal", "mayat", "jenazah")
# kata bahasa asing yang menandakan judul tidak berbahasa Indonesia (judul channel = bahasa Indonesia)
KATA_ASING = {
    "the",
    "of",
    "and",
    "how",
    "why",
    "what",
    "when",
    "where",
    "is",
    "are",
    "you",
    "your",
    "with",
    "for",
    "this",
    "that",
    "from",
    "into",
    "about",
    "does",
    "do",
    "will",
    "can",
    "explained",
    "facts",
    "amazing",
    "secret",
    "truth",
    "real",
    "top",
    "best",
    "must",
    "watch",
    "video",
    "shorts",
    "part",
}
MAKS_KATA_JUDUL = 14


@dataclass
class NilaiJudul:
    judul: str
    skor: float
    alasan: list[str] = field(default_factory=list)
    peringatan: list[str] = field(default_factory=list)


def _bersih(s: str) -> str:
    return re.sub(r"[<>]", "", teks.ascii_saja(s)).strip()


def frasa_layak(frasa: Sequence[str], k: kanal_mod.Kanal, tema: str = "") -> list[str]:
    """frasa pencarian yang boleh dipakai di judul/tag: bersih, tidak diblokir, tidak sensitif, 2-8 kata, tanpa
    token satu huruf yang tak bermakna ('kenapa tsunami pakai t'); topik bencana: tanpa kata korban (mode hormat)."""
    out = []
    for f in frasa:
        f = teks.norm(f)
        if not f or teks.diblokir(f, k.aturan.blokir) or teks.sensitif(f, k.aturan.sensitif):
            continue
        if teks.kena(f, k.aturan.hindari_hook) or not 2 <= len(f.split()) <= 8:
            continue
        if any(len(w) == 1 and not w.isdigit() for w in f.split()):
            continue
        if tema in BENCANA and any(w in KATA_KORBAN for w in f.split()):
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


def bahasa_ok(j: str) -> tuple[bool, list[str]]:
    """judul harus terbaca sebagai bahasa Indonesia. >= 2 kata asing (bukan nama diri) = peringatan."""
    w = [x.lower() for x in re.findall(r"[A-Za-z]{2,}", j)]
    asing = [x for x in w if x in KATA_ASING]
    return (len(asing) < 2, asing)


def angka_tanpa_bukti(j: str, bukti: Sequence[Any] | None) -> list[str]:
    """angka/klaim angka di judul yang TIDAK muncul di teks bukti manapun -> jangan diklaim dulu.

    `bukti` = daftar objek apa pun yang punya atribut/kunci 'judul' atau 'teks' (Bukti, dict, str).
    """
    # jam ("08:21") dan tanggal ("2026-09-26") dibaca utuh: kalau dipecah, "08" dianggap
    # angka yang tidak ada di bukti padahal "08:21" ada di sana (peringatan palsu).
    j_tanpa_waktu = re.sub(r"\d{1,2}:\d{2}(?::\d{2})?", " ", j)
    j_tanpa_waktu = re.sub(r"\d{4}-\d{2}-\d{2}", " ", j_tanpa_waktu)
    angka = re.findall(r"(?<![\w.])(\d+(?:[.,]\d+)?)", j_tanpa_waktu)
    if not angka or bukti is None:
        return []
    korpus = " ".join(_teks_bukti(b) for b in bukti).lower()
    if not korpus:
        return angka
    return [a for a in angka if a.replace(",", ".") not in korpus and a not in korpus]


def _teks_bukti(b: Any) -> str:
    if isinstance(b, str):
        return b
    if isinstance(b, dict):
        return " ".join(str(b.get(k, "")) for k in ("judul", "teks", "penerbit"))
    return " ".join(str(getattr(b, k, "")) for k in ("judul", "teks", "penerbit"))


def skor_judul(
    j: str,
    kata_kunci: str,
    inti: str,
    format_: str,
    pesaing: Sequence[str],
    k: kanal_mod.Kanal,
    bukti: Sequence[Any] | None = None,
    hormat: bool = False,
) -> NilaiJudul:
    """nilai satu judul. -100 = ditolak; kalimat alasan ikut dikembalikan supaya bisa diaudit."""
    alasan: list[str] = []
    peringatan: list[str] = []
    if not j or len(j) > k.metadata.maks_judul or not j.isascii() or re.search(r"[<>]", j):
        return NilaiJudul(j, -100.0, ["ditolak: kosong/non-ASCII/memuat <> / lebih dari batas"])
    if teks.diblokir(j, k.aturan.blokir) or teks.sensitif(j, k.aturan.sensitif) or teks.kena(j, k.aturan.hindari_hook):
        return NilaiJudul(j, -100.0, ["ditolak: memuat topik diblokir / kata sensitif / kata yang dihindari"])
    if len(j.split()) > MAKS_KATA_JUDUL:
        return NilaiJudul(j, -100.0, [f"ditolak: lebih dari {MAKS_KATA_JUDUL} kata (judul tidak terbaca di HP)"])
    jn = teks.norm(j)
    ideal = k.metadata.ideal_judul_shorts if format_ == "shorts" else k.metadata.ideal_judul_long
    s = 2.0 if len(j) <= ideal else 2.0 - 0.08 * (len(j) - ideal)
    if len(j) < 25:
        s -= 1.0
        alasan.append("terlalu pendek (<25 karakter, kurang memberi konteks)")
    if teks.norm(inti) in jn[:40]:
        s += 2.0
        alasan.append("kata kunci inti ada di 40 karakter pertama (baik untuk pencarian)")
    kk = " ".join(teks.norm(kata_kunci).split()[:3])
    if kk and jn.startswith(kk):
        s += 1.5
        alasan.append("diawali frasa kunci utama")
    if "?" in j or any(w in jn.split() for w in PENASARAN):
        s += 1.0
    if re.search(r"\d", j):
        s += 0.3
        tanpa = angka_tanpa_bukti(j, bukti)
        if bukti is not None and tanpa:
            s -= 1.5
            peringatan.append(
                f"angka {', '.join(tanpa)} tidak ditemukan di teks bukti - pastikan benar sebelum dipakai"
            )
    kapital = [w for w in re.findall(r"[A-Za-z]{3,}", j) if w.isupper()]
    s -= max(0, len(kapital) - 1) * 1.0
    if any(u in j.lower() for u in UMPAN_BOHONG):
        s -= 2.0
        peringatan.append("mengandung umpan bohong")
    if hormat and any(re.search(rf"(?<![0-9a-z]){x}(?![0-9a-z])", jn) for x in KATA_SENSASI):
        s -= 2.0
        peringatan.append("topik bencana: kata bernada sensasi tidak dipakai")
    ok_bahasa, asing = bahasa_ok(j)
    if not ok_bahasa:
        s -= 1.5
        peringatan.append(f"campuran bahasa asing ({', '.join(asing[:4])}) - kanal berbahasa Indonesia")
    if pesaing:
        _, mirip = teks.paling_mirip(j, list(pesaing))
        s += -2.0 if mirip > 0.85 else (0.8 if mirip < 0.6 else 0.0)
        if mirip > 0.85:
            peringatan.append("hampir sama dengan judul yang sudah ramai")
    if not alasan:
        alasan.append("panjang & struktur wajar, tanpa pemicu skor khusus")
    return NilaiJudul(j, round(s, 3), alasan, peringatan)


def kandidat_judul(
    frasa: Sequence[str],
    inti: str,
    format_: str,
    momen: str | None = None,
    tambahan: Sequence[str] = (),
    pilar: str = "",
    hormat: bool = False,
    sudut: Sequence[str] = (),
) -> list[str]:
    """susun kandidat judul. `hormat` (topik bencana) membuang templat sensasional; `sudut` memberi variasi
    yang dikunci ke sudut pembeda hasil riset (tahap 7)."""
    I = teks.kapital_judul(inti)
    out = [_bersih(x) for x in tambahan]

    def pakai(daftar: list[str]) -> list[str]:
        return [t for t in daftar if not (hormat and t in TEMPLAT_SENSASI)]

    tanya = [f for f in frasa if f.split()[0] in ("kenapa", "apakah", "bagaimana")][:8] or list(frasa[:3])
    for f in tanya:
        F = teks.kapital_judul(f)
        out += [t.format(F=F, I=I) for t in pakai(TEMPLAT["tanya"] + TEMPLAT[format_])]
        if momen and len(f.split()) >= 4:
            out += [t.format(M=teks.kapital_judul(momen), F=F) for t in TEMPLAT["momen"]]
    for s in list(sudut)[:3]:
        if len(s.split()) >= 3 and not teks.sensitif(s, ()):  # penyaring sensitif dilakukan pemanggil
            S = teks.kapital_judul(s)
            out += [t.format(S=S) for t in pakai(TEMPLAT["sudut"])]
    out += [t.format(I=I) for t in pakai(TEMPLAT["inti"] + (TEMPLAT["misteri"] if pilar == "misteri" else []))]
    return list(dict.fromkeys(_bersih(x) for x in out if x))


def _inti_judul(j: str) -> str:
    """bagian pertanyaan/inti judul - dua judul dengan inti sama = pilihan yang sama."""
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
}


def _kata_sudut(j: str, inti: str) -> set[str]:
    buang = set(teks.norm(inti).split()) | _FUNGSI
    return {_SINONIM.get(w, w) for w in _inti_judul(j).split() if w not in buang and len(w) > 2}


def mirip_judul(a: str, b: str, inti: str = "") -> float:
    """kemiripan SUDUT dua judul (1.0 = pilihan yang sama walau kata kerjanya beda)."""
    if _inti_judul(a) == _inti_judul(b):
        return 1.0
    ka, kb = _kata_sudut(a, inti), _kata_sudut(b, inti)
    if (not ka and not kb and "?" in a and "?" in b) or (ka & kb):
        return 1.0
    return 0.6 * teks.mirip(a, b)


def pilih_beragam(
    kandidat: list[tuple[str, float]], n: int = 3, lam: float = 3.0, inti: str = ""
) -> list[tuple[str, float]]:
    """MMR: skor tinggi TAPI tidak mirip judul yang sudah terpilih (3 pilihan benar-benar beda sudutnya)."""
    sisa = sorted([c for c in kandidat if c[1] > -50], key=lambda c: -c[1])
    pilih: list[tuple[str, float]] = []
    while sisa and len(pilih) < n:
        terbaik = max(sisa, key=lambda c: c[1] - lam * max((mirip_judul(c[0], p[0], inti) for p in pilih), default=0.0))
        pilih.append(terbaik)
        sisa.remove(terbaik)
    return pilih


def duplikat(judul: Sequence[str], ambang: float = 0.9) -> list[tuple[str, str, float]]:
    """uji duplikasi: pasangan judul yang kemiripannya melewati ambang (fuzz.ratio, bukan token_set)."""
    out = []
    for i, a in enumerate(judul):
        for b in judul[i + 1 :]:
            r = fuzz.ratio(teks.norm(a), teks.norm(b))
            if r >= ambang * 100:
                out.append((a, b, r / 100.0))
    return out


def buat(
    frasa: Sequence[str],
    inti: str,
    format_: str,
    k: kanal_mod.Kanal,
    kata_kunci: str,
    pesaing: Sequence[str] = (),
    momen: str | None = None,
    pilar: str = "",
    hormat: bool = False,
    sudut: Sequence[str] = (),
    judul_tetap: Sequence[str] = (),
    bukti: Sequence[Any] | None = None,
    n: int = 3,
) -> tuple[list[str], list[float], list[str]]:
    """-> (judul terpilih, skor, peringatan). `judul_tetap` (dari episode) tetap dinilai & diuji duplikasinya."""
    tetap = [_bersih(j) for j in judul_tetap if isinstance(j, str) and j.strip()]
    if len(tetap) >= n:
        nilai = [skor_judul(j, kata_kunci, inti, format_, pesaing, k, bukti, hormat) for j in tetap[:n]]
        return [x.judul for x in nilai], [x.skor for x in nilai], _kumpul(nilai)
    calon = kandidat_judul(frasa, inti, format_, momen, tetap, pilar, hormat, sudut)
    bernilai = [(j, skor_judul(j, kata_kunci, inti, format_, pesaing, k, bukti, hormat)) for j in calon]
    pasangan = [(n_.judul, n_.skor) for _, n_ in bernilai]
    pilih = pilih_beragam(pasangan, n, inti=inti)
    return [j for j, _ in pilih], [s for _, s in pilih], _kumpul([n_ for _, n_ in bernilai])


def _kumpul(nilai: Sequence[NilaiJudul]) -> list[str]:
    out: list[str] = []
    for n_ in nilai:
        for p in n_.peringatan:
            if p not in out:
                out.append(p)
    return out
