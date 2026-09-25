#!/usr/bin/env python3
"""analisis/umum.py - bagian bersama mesin analisis KlikTahu (v3-v6).

* TEMA (~60) per pilar + kata inti/aspek, BENIH pertanyaan, leksikon sinyal (niat/sains/rel/kom/vis)
* BLOKIR total: kentut, ngiler, keringat & bau badan -> frasa DIBUANG dari data (bukan disembunyikan)
* ambil_saran(): Google / YouTube Autocomplete (online) ATAU fixture deterministik (--uji) ATAU data manual
  (hasil web search agen, analisis/data/manual_saran.json) - TIDAK pernah dijalankan sebagai cron di Actions.
* sudah_dibahas(): otomatis dari PUSTAKA.md (blok SUDAH_DIBAHAS) + folder pustaka/
* momen(): kalender event langit/musim (analisis/momen.json)
"""
from __future__ import annotations

import datetime as dt
import json
import re
import urllib.parse
import urllib.request
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR = Path(__file__).resolve().parent
DATA = DIR / "data"
FIXTURE = DIR / "fixture"

BLOKIR = ["kentut", "ngiler", "iler", "keringat", "bau badan", "bau ketiak", "ketiak bau", "buang angin", "flatus"]
BENIH = ["kenapa", "apakah", "bagaimana", "padahal", "tiba-tiba"]
PILAR = ["tubuh", "antariksa", "bumi", "hewan", "teknologi", "misteri"]

# tema: pilar, kata kunci pencarian (kata[0] = inti), aspek (untuk cabang v4), ever (evergreen 0/1), vis bawaan 0..1
TEMA = {
    # tubuh
    "cegukan": ("tubuh", ["cegukan"], ["lama", "terus", "bayi", "malam"], 1, 0.6),
    "uban & rambut": ("tubuh", ["uban", "rambut rontok"], ["muda", "stres", "dicabut"], 1, 0.7),
    "menguap": ("tubuh", ["menguap"], ["menular", "ngantuk", "terus"], 1, 0.6),
    "bersin": ("tubuh", ["bersin"], ["matahari", "terus", "ditahan"], 1, 0.6),
    "merinding": ("tubuh", ["merinding"], ["musik", "dingin", "takut"], 1, 0.6),
    "jantung": ("tubuh", ["jantung"], ["berdebar", "berhenti", "detak"], 1, 0.8),
    "otak": ("tubuh", ["otak"], ["lupa", "deja vu", "lelah"], 1, 0.8),
    "mimpi & tidur": ("tubuh", ["mimpi", "tidur"], ["jatuh", "lupa", "ketindihan"], 1, 0.7),
    "tulang & sendi": ("tubuh", ["tulang", "sendi berbunyi"], ["retak", "bunyi", "patah"], 1, 0.7),
    "darah": ("tubuh", ["darah"], ["merah", "golongan", "biru"], 1, 0.8),
    "kuku": ("tubuh", ["kuku"], ["putih", "tumbuh", "belang"], 1, 0.6),
    "lapar & haus": ("tubuh", ["lapar", "perut keroncongan"], ["bunyi", "malam", "marah"], 1, 0.6),
    "mata": ("tubuh", ["mata"], ["kedutan", "minus", "merah"], 1, 0.8),
    "kulit & jerawat": ("tubuh", ["jerawat", "kulit"], ["muncul", "keriput"], 1, 0.7),
    "gigi & mulut": ("tubuh", ["gigi"], ["ngilu", "berlubang"], 1, 0.7),
    # antariksa
    "lubang hitam": ("antariksa", ["lubang hitam"], ["terdekat", "masuk", "cahaya"], 1, 1.0),
    "aurora": ("antariksa", ["aurora"], ["warna", "indonesia", "kutub"], 1, 1.0),
    "matahari": ("antariksa", ["matahari"], ["panas", "mati", "badai"], 1, 1.0),
    "bulan": ("antariksa", ["bulan"], ["merah", "besar", "siang"], 1, 1.0),
    "bintang": ("antariksa", ["bintang"], ["jatuh", "mati", "terdekat"], 1, 1.0),
    "meteor & komet": ("antariksa", ["meteor", "komet", "hujan meteor"], ["jatuh", "warna"], 1, 1.0),
    "planet mars": ("antariksa", ["mars"], ["merah", "air", "hidup"], 1, 0.9),
    "saturnus & cincin": ("antariksa", ["saturnus", "cincin saturnus"], ["hilang", "terbuat"], 1, 1.0),
    "galaksi": ("antariksa", ["galaksi", "bima sakti"], ["tabrakan", "pusat"], 1, 1.0),
    "astronot": ("antariksa", ["astronot"], ["tidur", "makan", "melayang"], 1, 0.9),
    "alien": ("antariksa", ["alien"], ["ada", "sinyal"], 1, 0.9),
    "gerhana": ("antariksa", ["gerhana"], ["matahari", "bulan merah"], 1, 1.0),
    "asteroid": ("antariksa", ["asteroid"], ["menabrak", "dinosaurus"], 1, 0.9),
    # bumi
    "hari tanpa bayangan": ("bumi", ["hari tanpa bayangan", "bayangan hilang"], ["jam", "indonesia"], 0, 0.9),
    "gempa bumi": ("bumi", ["gempa"], ["malam", "terasa"], 1, 0.9),
    "gunung berapi": ("bumi", ["gunung meletus", "gunung berapi"], ["lava", "tidur"], 1, 1.0),
    "tsunami": ("bumi", ["tsunami"], ["surut", "tanda"], 1, 1.0),
    "petir": ("bumi", ["petir", "kilat"], ["menyambar", "suara"], 1, 1.0),
    "hujan & awan": ("bumi", ["hujan", "awan"], ["bau", "melayang", "es"], 1, 0.9),
    "pelangi": ("bumi", ["pelangi"], ["melengkung", "ganda", "malam"], 1, 1.0),
    "es & salju": ("bumi", ["salju", "es"], ["putih", "indonesia", "mengapung"], 1, 1.0),
    "laut": ("bumi", ["laut", "air laut"], ["asin", "biru", "dalam"], 1, 1.0),
    "angin & badai": ("bumi", ["angin", "badai", "puting beliung"], ["berputar", "mata badai"], 1, 1.0),
    "gurun": ("bumi", ["gurun"], ["dingin malam", "pasir"], 1, 0.9),
    "gua": ("bumi", ["gua", "stalaktit"], ["gelap", "terbentuk"], 1, 0.9),
    # hewan
    "ular & reptil": ("hewan", ["ular", "reptil"], ["berbisa", "ganti kulit", "lidah"], 1, 1.0),
    "kucing": ("hewan", ["kucing"], ["mendengkur", "jatuh"], 1, 0.9),
    "anjing": ("hewan", ["anjing"], ["menggonggong", "setia"], 1, 0.9),
    "hiu": ("hewan", ["hiu"], ["gigi", "tidur"], 1, 1.0),
    "gurita": ("hewan", ["gurita"], ["tiga jantung", "tinta", "pintar"], 1, 1.0),
    "lebah & semut": ("hewan", ["lebah", "semut"], ["menyengat", "ratu"], 1, 0.9),
    "burung": ("hewan", ["burung"], ["terbang", "migrasi"], 1, 0.9),
    "gajah": ("hewan", ["gajah"], ["ingatan", "kuburan"], 1, 0.9),
    "cicak": ("hewan", ["cicak"], ["ekor putus", "menempel"], 1, 0.8),
    "dinosaurus": ("hewan", ["dinosaurus"], ["punah", "burung"], 1, 1.0),
    # teknologi
    "baterai & hp": ("teknologi", ["baterai", "hp panas"], ["cepat habis", "meledak"], 1, 0.8),
    "internet & wifi": ("teknologi", ["wifi", "internet"], ["lemot", "sinyal"], 1, 0.7),
    "listrik & magnet": ("teknologi", ["listrik", "magnet"], ["setrum", "kutub"], 1, 0.8),
    "pesawat": ("teknologi", ["pesawat"], ["terbang", "turbulensi", "putih"], 1, 1.0),
    "kulkas & microwave": ("teknologi", ["microwave", "kulkas"], ["panas", "dingin"], 1, 0.8),
    "ai": ("teknologi", ["ai", "kecerdasan buatan"], ["berpikir", "bahaya"], 1, 0.7),
    # misteri
    "piramida": ("misteri", ["piramida"], ["dibangun", "mesir", "dalam"], 1, 1.0),
    "segitiga bermuda": ("misteri", ["segitiga bermuda"], ["hilang", "misteri"], 1, 0.9),
    "stonehenge": ("misteri", ["stonehenge"], ["dibangun", "batu"], 1, 0.9),
    "borobudur": ("misteri", ["borobudur", "candi"], ["dibangun", "batu"], 1, 0.9),
    "deja vu": ("misteri", ["deja vu"], ["pernah", "otak"], 1, 0.6),
    "atlantis": ("misteri", ["atlantis"], ["tenggelam", "nyata"], 1, 0.9),
}

LEKS = {
    "niat": ["kenapa", "mengapa", "bagaimana", "apa itu", "apakah", "cara", "penyebab", "proses", "terjadi"],
    "sains": ["ilmiah", "sains", "fakta", "penjelasan", "teori", "nasa", "penelitian", "fisika", "biologi", "kimia",
              "otak", "sel", "gravitasi", "cahaya", "energi", "atom", "reaksi", "suhu", "tekanan", "gelombang"],
    "rel": ["saya", "aku", "kita", "kalau", "saat", "setiap", "sering", "tiba-tiba", "malam", "pagi", "tidur",
            "makan", "anak", "bayi", "rumah"],
    "kom": ["apakah", "benarkah", "mitos", "atau", "lebih", "paling", "bisa", "boleh", "bahaya", "beneran", "benar"],
    "vis": ["warna", "bentuk", "terlihat", "cahaya", "besar", "kecil", "bergerak", "berputar", "meledak", "jatuh",
            "terbang", "menyala", "merah", "biru", "hijau", "hitam", "putih"],
}
HINDARI_HOOK = ["haram", "halal", "agama", "dosa", "harga", "murah", "brand", "merek", "game", "judi", "slot"]


def norm(s):
    s = s.lower().strip()
    s = re.sub(r"[^0-9a-z\s\-]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def diblokir(frasa):
    f = " " + norm(frasa) + " "
    return any((" " + b + " ") in f or f.strip().startswith(b) for b in BLOKIR)


def bersih(frasa):
    f = norm(frasa)
    if not f or len(f) < 6 or diblokir(f):
        return None
    return f


def punya(frasa, leks):
    f = " " + norm(frasa) + " "
    return any((" " + w + " ") in f for w in LEKS[leks])


# ------------------------------------------------------------------------------------------ sumber saran
class Offline(Exception):
    pass


def _http_saran(q, sumber):
    base = "https://suggestqueries.google.com/complete/search?client=firefox&hl=id&gl=id&q="
    url = base + urllib.parse.quote(q) + ("&ds=yt" if sumber == "youtube" else "")
    try:
        with urllib.request.urlopen(url, timeout=6) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        return [s for s in data[1]][:10]
    except Exception as e:  # noqa: BLE001
        raise Offline(str(e))


def _fixture_saran(q, sumber):
    """saran deterministik (untuk --uji): dibangun dari aspek tema + templat, termasuk frasa DIBLOKIR
    agar penyaring teruji. Sama setiap kali (seed crc32 kueri)."""
    rr = zlib.crc32(f"{sumber}:{q}".encode())
    kata = q.split(" ", 1)[1] if " " in q else q
    tema = next((k for k, v in TEMA.items() if any(kata.startswith(x) or x.startswith(kata) for x in v[1])), None)
    asp = TEMA[tema][2] if tema else ["itu", "terjadi"]
    tmpl = ["{q} {a}", "{q} {a} menurut sains", "{q} terjadi", "{q} bisa {a}", "{q} saat malam",
            "{q} setiap hari", "{q} warna {a}", "{q} berbahaya atau tidak", "{q} pada anak", "{q} {a} fakta ilmiah"]
    out = []
    for i in range(6 + rr % 4):
        a = asp[(rr >> (i + 1)) % len(asp)]
        out.append(tmpl[(rr + i * 7) % len(tmpl)].format(q=q, a=a))
    if rr % 5 == 0:
        out.insert(2, f"{q} kentut bau")  # harus dibuang BLOKIR
    if rr % 7 == 0:
        out.insert(4, f"{q} keringat dingin")  # harus dibuang BLOKIR
    return list(dict.fromkeys(out))[:10]


def _manual_saran():
    p = DATA / "manual_saran.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def ambil_saran(q, sumber="google", mode="online"):
    """mode: 'uji' (fixture), 'manual' (data web search agen), 'online' (HTTP; Offline bila gagal)."""
    if mode == "uji":
        return _fixture_saran(q, sumber)
    if mode == "manual":
        return _manual_saran().get(sumber, {}).get(q, [])
    return _http_saran(q, sumber)


def cek_online():
    try:
        _http_saran("kenapa langit biru", "google")
        return True
    except Offline:
        return False


# ------------------------------------------------------------------------------------------ pustaka & momen
def sudah_dibahas():
    """{frasa_tema: 'shorts'|'long'} dari PUSTAKA.md (blok SUDAH_DIBAHAS) + folder pustaka/.
    Entri berawalan 'Long:' = baru dibahas sebagai video panjang (masih boleh jadi Shorts dengan sudut baru)."""
    out = {}
    p = ROOT / "PUSTAKA.md"
    if p.exists():
        s = p.read_text(encoding="utf-8")
        m = re.search(r"SUDAH_DIBAHAS:MULAI.*?-->(.*?)<!--\s*SUDAH_DIBAHAS:SELESAI", s, re.S)
        if m:
            for ln in m.group(1).splitlines():
                ln = ln.strip().lstrip("-").strip()
                if ln:
                    jenis = "long" if ln.lower().startswith("long:") else "shorts"
                    out[norm(re.sub(r"(?i)^long:", "", ln).replace("(2x)", ""))] = jenis
    for d in (ROOT / "pustaka").glob("*/"):
        if d.is_dir():
            jenis = "long" if d.name.lower().startswith("long") else "shorts"
            out[norm(re.sub(r"^(ep|long)\d+_", "", d.name.lower()).replace("_", " "))] = jenis
    return out


def _kata_utuh(a, b):
    """semua kata a muncul UTUH di b (bukan substring: 'ai' tidak cocok dengan 'baterai')."""
    wb = set(b.replace("&", " ").split())
    wa = [w for w in a.replace("&", " ").split()]
    return bool(wa) and all(w in wb for w in wa)


def tema_sudah(tema, daftar=None):
    """-> 'shorts' (sudah jadi Shorts), 'long' (baru jadi video panjang), atau None (segar)."""
    daftar = sudah_dibahas() if daftar is None else daftar
    kunci = [norm(x) for x in [tema] + TEMA[tema][1]]
    hasil = None
    for d, jenis in daftar.items():
        dinti = d.split(" & ")[0].strip()
        for k in kunci:
            inti = k.split(" & ")[0].strip()
            if _kata_utuh(inti, d) or _kata_utuh(dinti, k):
                if jenis == "shorts":
                    return "shorts"
                hasil = "long"
    return hasil


def momen(hari_ini=None, jendela=45):
    """-> {tema_kata: (skor 0..1, event)} untuk event dalam jendela hari ke depan."""
    hari_ini = hari_ini or dt.date.today()
    data = json.loads((DIR / "momen.json").read_text(encoding="utf-8"))["events"]
    out = {}
    for ev in data:
        d = dt.date.fromisoformat(ev["tanggal"])
        sisa = (d - hari_ini).days
        if 0 <= sisa <= jendela:
            s = 1.0 - sisa / (jendela * 1.25)
            for t in ev["tema"]:
                if s > out.get(t, (0, None))[0]:
                    out[t] = (round(s, 3), ev)
    return out


def momen_tema(tema, peta):
    kata = [norm(tema)] + [norm(x) for x in TEMA[tema][1]]
    best = (0.0, None)
    for k, v in peta.items():
        if any(k in x or x in k for x in kata):
            if v[0] > best[0]:
                best = v
    return best


# ------------------------------------------------------------------------------------------ snapshot
def simpan(nama, obj):
    DATA.mkdir(parents=True, exist_ok=True)
    p = DATA / nama
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def snapshot_sebelum(prefix, tanggal, dir_=None):
    """snapshot terakhir dengan tanggal < tanggal (YYYYMMDD)."""
    d = dir_ or DATA
    kandidat = sorted(p for p in d.glob(f"{prefix}_*.json") if p.stem.split("_")[-1] < tanggal)
    return json.loads(kandidat[-1].read_text(encoding="utf-8")) if kandidat else None


def ascii_saja(s):
    return s.encode("ascii", "ignore").decode("ascii")
