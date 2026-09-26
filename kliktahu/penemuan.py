"""kliktahu/penemuan.py - PENEMUAN TOPIK (tahap 4 rencana upgrade 2026-09).

Registri tema (``tema.py``) sengaja DIBATASI: 62 tema yang sudah punya judul Wikipedia kanonik, aspek, alias, dan
aturan homonim. Batas itu menjaga kualitas sinyal (frasa "kenapa gua jelek" tidak tertukar dengan gua batu), tetapi
ia juga membutakan mesin terhadap topik baru yang sedang naik. Modul ini memperluas kandidat:

1. dari PERTANYAAN nyata (autocomplete): buang kata benih & kata fungsi, sisanya = calon frasa topik
2. dari SINYAL LIVE: artikel Wikipedia teratas harian, tren Google, momen (gempa/cuaca/astronomi), berita
3. cocokkan tiap kandidat ke NICHE kanal (6 pilar) lewat registri tema terdekat + leksikon pilar

Kandidat di luar registri DITANDAI (``di_registri=False``) dan diberi alasan yang bisa dibaca pemilik: sinyal
rincinya (pageview judul kanonik, aspek v4, alias) belum tersedia, jadi keyakinannya lebih rendah - bukan berarti
topik itu buruk. Tidak ada kandidat yang disembunyikan tanpa keterangan.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from . import teks
from .cari import BERITA, CUACA, MOMEN, SARAN, TREN, WIKI, Hasil
from .tema import ALIAS, DAFTAR, TEMA, TOLAK

BENIH = ("kenapa", "mengapa", "apakah", "bagaimana", "padahal", "tiba-tiba", "kapan", "dimana", "di mana", "siapa")
# kata fungsi bahasa Indonesia: tidak pernah menjadi inti topik
FUNGSI = {
    "yang",
    "dan",
    "di",
    "ke",
    "dari",
    "untuk",
    "pada",
    "dengan",
    "itu",
    "ini",
    "sih",
    "kok",
    "ya",
    "adalah",
    "bisa",
    "dapat",
    "akan",
    "sudah",
    "belum",
    "tidak",
    "bukan",
    "jadi",
    "juga",
    "lagi",
    "saja",
    "pun",
    "saat",
    "kalau",
    "jika",
    "karena",
    "sebab",
    "agar",
    "supaya",
    "tentang",
    "dalam",
    "atas",
    "bawah",
    "antara",
    "oleh",
    "terhadap",
    "kepada",
    "setelah",
    "sebelum",
    "ketika",
    "sambil",
    "meski",
    "walaupun",
    "tetapi",
    "namun",
    "lalu",
    "kemudian",
    "akhirnya",
    "ternyata",
    "rupanya",
    "memang",
    "sangat",
    "lebih",
    "paling",
    "semua",
    "setiap",
    "selalu",
    "sering",
    "kadang",
    "pernah",
    "harus",
    "perlu",
    "mungkin",
    "seharusnya",
    "begini",
    "begitu",
    "berapa",
    "kenapa",
    "mengapa",
    "apakah",
    "bagaimana",
    "padahal",
    "tiba",
    "orang",
    "kita",
    "kamu",
    "saya",
    "aku",
    "dia",
    "mereka",
    "badan",
    "tubuh",
    "manusia",
    "anak",
    "bayi",
    "hari",
    "malam",
    "pagi",
    "siang",
    "minggu",
    "bulan",
    "tahun",
    "waktu",
    "terus",
    "terjadi",
    "terjadinya",
    "bikin",
    "punya",
    "milik",
    "ada",
    "tiap",
    "eh",
    "loh",
    "dong",
    "nama",
    "jenis",
    "macam",
    "cara",
    "akibat",
}
PILAR_KATA: dict[str, tuple[str, ...]] = {
    "tubuh": (
        "tubuh",
        "otak",
        "jantung",
        "darah",
        "kulit",
        "mata",
        "telinga",
        "gigi",
        "perut",
        "paru",
        "otot",
        "tulang",
        "saraf",
        "hormon",
        "imun",
        "penyakit",
        "obat",
        "vitamin",
        "napas",
        "jantung",
        "lambung",
    ),
    "antariksa": (
        "bintang",
        "planet",
        "bulan",
        "matahari",
        "galaksi",
        "lubang",
        "hitam",
        "komet",
        "meteor",
        "asteroid",
        "roket",
        "satelit",
        "antariksa",
        "luar",
        "angkasa",
        "supernova",
        "aurora",
    ),
    "bumi": (
        "bumi",
        "gempa",
        "gunung",
        "tsunami",
        "cuaca",
        "hujan",
        "angin",
        "badai",
        "petir",
        "awan",
        "laut",
        "sungai",
        "tanah",
        "es",
        "salju",
        "gunung",
        "berapi",
        "iklim",
        "suhu",
        "pelangi",
        "gerhana",
    ),
    "hewan": (
        "hewan",
        "binatang",
        "kucing",
        "anjing",
        "burung",
        "ikan",
        "ular",
        "serangga",
        "dinosaurus",
        "hiu",
        "gajah",
        "semut",
        "lebah",
        "kupu",
        "paus",
    ),
    "teknologi": (
        "teknologi",
        "hp",
        "ponsel",
        "baterai",
        "internet",
        "sinyal",
        "listrik",
        "magnet",
        "komputer",
        "ai",
        "kecerdasan",
        "buatan",
        "mesin",
        "chip",
        "kamera",
        "wifi",
        "data",
        "algoritma",
        "ponsel",
        "gadget",
        "satelit",
        "nuklir",
    ),
    "misteri": (
        "misteri",
        "mitos",
        "legenda",
        "sejarah",
        "piramida",
        "atlantis",
        "hantu",
        "supranatural",
        "megalodon",
        "segitiga",
        "bermuda",
        "hilang",
        "mumi",
        "fosil",
        "kuno",
        "peradaban",
    ),
}
STOPWIKI = re.compile(r"\(([^)]*)\)")


@dataclass
class Kandidat:
    nama: str
    pilar: str
    skor_kecocokan: float  # 0..1 seberapa cocok dengan niche kanal
    bukti: list[str] = field(default_factory=list)
    sumber: set[str] = field(default_factory=set)
    tema_terdekat: str | None = None
    di_registri: bool = False
    catatan: str = ""
    metrik: float = 0.0  # sinyal kuantitatif terbaik yang dimiliki kandidat (views/traffic/urgensi)

    def baris(self) -> dict[str, Any]:
        return {
            "nama": self.nama,
            "pilar": self.pilar,
            "skor_kecocokan": round(self.skor_kecocokan, 3),
            "tema_terdekat": self.tema_terdekat,
            "di_registri": self.di_registri,
            "metrik": round(self.metrik, 2),
            "sumber": sorted(self.sumber),
            "bukti": self.bukti[:5],
            "catatan": self.catatan or None,
        }


def bersih_frasa(f: str) -> str:
    """buang tanda baca & kurung; sisakan kata."""
    return teks.norm(re.sub(r"[^\w\s]", " ", STOPWIKI.sub(" ", f)))


def inti_dari_pertanyaan(f: str, maks_kata: int = 3) -> str | None:
    """'kenapa air laut bisa asin sekali' -> 'air laut asin' (inti topiknya, bukan pertanyaannya)."""
    w = [x for x in bersih_frasa(f).split() if x]
    if not w:
        return None
    if w[0] in BENIH:
        w = w[1:]
    w = [x for x in w if x not in FUNGSI and len(x) > 2]
    if not w or len(w) > 6:
        return None
    return " ".join(w[:maks_kata])


def kandidat_dari_pertanyaan(frasa: Iterable[str], sumber: str = "saran") -> dict[str, Kandidat]:
    out: dict[str, Kandidat] = {}
    for f in frasa:
        inti = inti_dari_pertanyaan(f)
        if not inti:
            continue
        k = out.setdefault(inti, Kandidat(inti, "", 0.0, sumber={sumber}))
        if f not in k.bukti:
            k.bukti.append(f)
    return out


def pilar_dari_kata(nama: str) -> tuple[str, float]:
    """tebak pilar dari leksikon; (pilar, skor 0..1)."""
    w = set(bersih_frasa(nama).split())
    terbaik = ("", 0.0)
    for pilar, kata in PILAR_KATA.items():
        cocok = w & set(kata)
        if cocok:
            s = min(1.0, 0.5 + 0.25 * len(cocok))
            if s > terbaik[1]:
                terbaik = (pilar, s)
    return terbaik


# registri ternormalisasi (& -> spasi, apostrof dibuang) supaya "angin & badai" cocok dengan dirinya sendiri
TEMA_NORM: dict[str, str] = {teks.norm(nama): nama for nama in TEMA}

AMBANG_MIRIP = 0.62  # di bawah ini kemiripan hanya kebetulan ("sabun mandi cair" vs "saturnus cincin" ~ 0.50)


def tema_terdekat(nama: str) -> tuple[str | None, float]:
    """tema registri yang paling mirip & skor kemiripannya (kata utuh + kemiripan teks).

    Hasil di bawah `AMBANG_MIRIP` dianggap TIDAK mirip (None, 0.0) daripada dipaksa cocok.
    """
    n = teks.norm(nama)
    if n in TEMA_NORM:
        return TEMA_NORM[n], 1.0
    terbaik: tuple[str | None, float] = (None, 0.0)
    for t in DAFTAR:
        kunci = [teks.norm(t.nama), *(teks.norm(k) for k in t.kata)]
        s = max(teks.mirip(n, kk) for kk in kunci) / 100.0
        if any(teks.kata_utuh_semua(kk, n) for kk in kunci if len(kk) > 3):
            s = max(s, 0.85)
        if s > terbaik[1]:
            terbaik = (t.nama, s)
    return terbaik if terbaik[1] >= AMBANG_MIRIP else (None, 0.0)


def nilai_kecocokan(nama: str, kanal_niche: str = "") -> tuple[str, float, str | None, bool, str]:
    """-> (pilar, skor_kecocokan 0..1, tema_terdekat, di_registri, catatan)."""
    n = teks.norm(nama)
    terdekat, mirip = tema_terdekat(n)
    di_registri = n in TEMA_NORM
    pilar_leks, skor_leks = pilar_dari_kata(n)
    pilar = pilar_leks
    skor = skor_leks
    catatan = ""
    if terdekat:
        pilar_reg = TEMA[terdekat].pilar
        if skor_leks and pilar_leks != pilar_reg:
            # leksikon & registri beda pendapat -> menang registri, catat ketidakpastiannya
            catatan = f"pilar menurut leksikon '{pilar_leks}', menurut registri '{pilar_reg}' (dipakai registri)"
        pilar = pilar_reg
        skor = max(skor, 0.5 + 0.5 * mirip)
    if not pilar:
        skor = min(skor, 0.15)
        catatan = (catatan + "; " if catatan else "") + (
            "pilar tidak dikenali: tidak ada kata kunci pilar yang cocok dan tidak mirip tema di registri "
            "- kandidat ini di luar niche kanal"
        )
    if not di_registri:
        catatan = (catatan + "; " if catatan else "") + (
            "di luar registri tema: judul Wikipedia kanonik, aspek v4, dan alias belum tersedia "
            "-> sinyal rinci netral & keyakinan lebih rendah"
        )
    return pilar, min(1.0, skor), terdekat, di_registri, catatan


def dari_hasil(
    hasil: Sequence[Hasil],
    kanal_niche: str = "",
    minimal_bukti: int = 1,
) -> list[Kandidat]:
    """kandidat topik dari kumpulan temuan pencarian (pertanyaan + artikel + tren + momen + cuaca)."""
    kandidat: dict[str, Kandidat] = {}
    for h in hasil:
        if teks.diblokir(h.judul, ()) and False:  # placeholder (blokir butuh kanal; disaring di analisis.py)
            continue
        if h.jenis == SARAN:
            # dua lapis: (a) TEMA REGISTRI yang disebut frasa (kanonik: judul wiki, aspek, alias ikut tersedia),
            # (b) inti frasa apa adanya - jalur penemuan topik BARU yang belum ada di registri.
            for nama in tema_disebut(h.judul):
                k = kandidat.setdefault(nama, Kandidat(nama, "", 0.0, sumber={h.sumber}))
                k.bukti.append(h.judul)
                k.sumber.add(h.sumber)
                k.metrik = max(k.metrik, h.metrik or 0.0)
            inti = inti_dari_pertanyaan(h.judul)
            if not inti:
                continue
            k2 = kandidat.setdefault(inti, Kandidat(inti, "", 0.0, sumber={h.sumber}))
            k2.bukti.append(h.judul)
            k2.sumber.add(h.sumber)
            k2.metrik = max(k2.metrik, h.metrik or 0.0)
        elif h.jenis in (WIKI, TREN, BERITA):
            # judul berita/artikel TIDAK dijadikan nama topik mentah (bising: "Berita <kueri> ke-3 - Kompas").
            # Yang dipakai: TEMA REGISTRI yang disebut judulnya; sisanya hanya jadi bukti untuk kandidat lain.
            for nama in tema_disebut(h.judul) or [teks.norm(re.sub(r"\s*\d+.*$", "", h.judul))[:60]]:
                if len(nama.split()) > 5 or len(nama) < 4:
                    continue
                k = kandidat.setdefault(nama, Kandidat(nama, "", 0.0, sumber={h.sumber}))
                k.bukti.append(h.judul)
                k.sumber.add(h.sumber)
                k.metrik = max(k.metrik, h.metrik or 0.0)
        elif h.jenis in (MOMEN, CUACA):
            # momen bukan topik, tetapi MENUNJUK tema (gempa, tsunami, hujan, gunung api)
            for nama in _tema_dari_momen(h.judul):
                k = kandidat.setdefault(nama, Kandidat(nama, "", 0.0, sumber={h.sumber}))
                k.bukti.append(h.judul)
                k.sumber.add(h.sumber)
                k.metrik = max(k.metrik, h.metrik or 0.0)
    out = []
    for nama, k in kandidat.items():
        if len(k.bukti) < minimal_bukti:
            continue
        k.pilar, k.skor_kecocokan, k.tema_terdekat, k.di_registri, k.catatan = nilai_kecocokan(nama, kanal_niche)
        out.append(k)
    out.sort(key=lambda k: (-(0.55 * k.skor_kecocokan + 0.45 * min(1.0, len(k.bukti) / 6.0)), -k.metrik, k.nama))
    return out


def _tema_dari_momen(judul: str) -> list[str]:
    n = teks.norm(judul)
    peta = {
        "gempa": "gempa bumi",
        "tsunami": "tsunami",
        "gunung": "gunung berapi",
        "letusan": "gunung berapi",
        "erupsi": "gunung berapi",
        "badai": "angin & badai",
        "angin": "angin & badai",
        "hujan": "hujan & awan",
        "banjir": "banjir",
        "aurora": "aurora",
        "geomagnetik": "aurora",
        "asteroid": "asteroid",
        "gerhana": "gerhana",
        "supermoon": "bulan",
        "meteor": "meteor & komet",
        "kebakaran": "kebakaran hutan",
    }
    return [v for k, v in peta.items() if re.search(rf"(?<![0-9a-z]){k}(?![0-9a-z])", n)]


def gabung(daftar: Sequence[Kandidat]) -> list[Kandidat]:
    """gabung kandidat dengan nama sama dari beberapa sumber; bukti & sumber diunion."""
    out: dict[str, Kandidat] = {}
    for k in daftar:
        if k.nama in out:
            a = out[k.nama]
            a.bukti += [b for b in k.bukti if b not in a.bukti]
            a.sumber |= k.sumber
            a.metrik = max(a.metrik, k.metrik)
        else:
            out[k.nama] = k
    return sorted(
        out.values(), key=lambda k: (-(0.55 * k.skor_kecocokan + 0.45 * min(1.0, len(k.bukti) / 6.0)), k.nama)
    )


def tema_disebut(frasa: str) -> list[str]:
    """tema registri yang DISBUT frasa pencarian ini (kata utuh, multi-kata ikut dicocokkan).

    Dipakai agar kandidat memakai nama KANONIK registri ("gunung berapi"), bukan potongan pertanyaan
    ("gunung meletus lama"), sehingga judul Wikipedia, aspek, dan alias-nya ikut tersedia.
    """
    f = " " + bersih_frasa(frasa) + " "
    cocok: list[tuple[str, int]] = []
    for t in DAFTAR:
        kena_tolak = any(
            re.search(rf"(?<![0-9a-z]){re.escape(teks.norm(tolak))}(?![0-9a-z])", f) for tolak in TOLAK.get(t.nama, [])
        )
        if kena_tolak:
            continue  # homonim: "gua" = "aku" (gaul) -> bukan topik gua batu
        terpanjang = 0
        for kw in (t.nama, *t.kata, *ALIAS.get(t.nama, [])):
            nkw = teks.norm(kw)
            if len(nkw) < 4:
                continue
            if re.search(rf"(?<![0-9a-z]){re.escape(nkw)}(?![0-9a-z])", f):
                terpanjang = max(terpanjang, len(nkw))
        if terpanjang:
            cocok.append((t.nama, terpanjang))
    if not cocok:
        return []
    # kata kunci terpanjang menang: "kenapa gunung meletus TIDUR" = gunung berapi yang sedang tidur,
    # BUKAN topik mimpi & tidur ("tidur" 5 huruf vs "gunung meletus" 14 huruf).
    terbaik = max(p for _, p in cocok)
    return [n for n, p in cocok if p >= max(4, int(0.6 * terbaik))]


AMBANG_KANONIK = 0.85  # di atas ini kandidat dianggap nama lain dari tema registri


def kanonisasi(daftar: Sequence[Kandidat]) -> list[Kandidat]:
    """satukan kandidat yang sebenarnya topik yang sama dengan nama KANONIK registri.

    "gunung meletus" dan "gunung berapi" adalah topik yang sama; yang dipakai nama registri supaya judul
    Wikipedia kanonik, aspek v4, alias, dan aturan topik BENCANA ikut berlaku (bukan cuma namanya).
    """
    out: dict[str, Kandidat] = {}
    for k in daftar:
        out.setdefault(k.nama, k)
    for k in list(out.values()):
        if k.di_registri:
            continue
        terdekat, mirip = tema_terdekat(k.nama)
        if not terdekat or mirip < AMBANG_KANONIK:
            continue
        if terdekat not in out:
            kanon = Kandidat(terdekat, "", 0.0, bukti=list(k.bukti), sumber=set(k.sumber), metrik=k.metrik)
            kanon.pilar, kanon.skor_kecocokan, kanon.tema_terdekat, kanon.di_registri, kanon.catatan = nilai_kecocokan(
                terdekat
            )
            out[terdekat] = kanon
        else:
            tujuan = out[terdekat]
            tujuan.bukti += [b for b in k.bukti if b not in tujuan.bukti]
            tujuan.sumber |= k.sumber
            tujuan.metrik = max(tujuan.metrik, k.metrik)
        if terdekat != k.nama:
            out.pop(k.nama, None)
    hasil = []
    for k in out.values():
        if not k.skor_kecocokan:
            k.pilar, k.skor_kecocokan, k.tema_terdekat, k.di_registri, k.catatan = nilai_kecocokan(k.nama)
        hasil.append(k)
    return sorted(hasil, key=lambda k: (-(0.55 * k.skor_kecocokan + 0.45 * min(1.0, len(k.bukti) / 6.0)), k.nama))


def perluas_dari_registri(tema: str) -> list[str]:
    """pertanyaan turunan untuk tema yang SUDAH di registri (asal v4: 'kenapa <inti> <aspek>')."""
    t = TEMA.get(tema)
    if not t:
        return []
    return [f"kenapa {t.inti} {a}" for a in t.aspek] + [f"apakah {t.inti} {a}" for a in t.aspek[:2]]


def ringkas(daftar: Sequence[Kandidat], n: int = 15) -> list[str]:
    """baris laporan markdown (jujur tentang kandidat di luar registri)."""
    if not daftar:
        return ["- (tidak ada kandidat dari data yang tersedia)"]
    out = []
    for k in daftar[:n]:
        tanda = "" if k.di_registri else " *"
        out.append(
            f"- **{k.nama}** (pilar {k.pilar}, cocok {k.skor_kecocokan:.2f}"
            + (f", mirip {k.tema_terdekat}" if k.tema_terdekat and not k.di_registri else "")
            + f"){tanda} - {len(k.bukti)} bukti dari {', '.join(sorted(k.sumber))}"
            + (f" - {k.catatan}" if k.catatan else "")
        )
    if any(not k.di_registri for k in daftar[:n]):
        out.append("- * = di luar registri tema (sinyal rinci belum tersedia, keyakinan lebih rendah)")
    return out


def batas_registri(daftar: Sequence[Kandidat]) -> str:
    """penjelasan otomatis tentang batas cakupan penemuan (dipakai di laporan)."""
    n_reg = sum(1 for k in daftar if k.di_registri)
    return (
        f"{n_reg}/{len(daftar)} kandidat ada di registri tema ({len(DAFTAR)} tema). "
        "Registri menjaga kualitas sinyal (judul Wikipedia kanonik, alias, homonim) tetapi TIDAK mencakup semua "
        "topik: kandidat di luar registri tetap ditampilkan dengan keyakinan lebih rendah, dan bisa ditambahkan ke "
        "tema.py bila pemilik mau menjadikannya topik tetap."
    )
