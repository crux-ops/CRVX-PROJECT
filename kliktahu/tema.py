"""kliktahu/tema.py - REGISTRI TEMA (satu sumber) untuk analisis v3-v7, database, dan metadata.

Tiap tema: pilar, kata kunci pencarian (kata[0] = inti), aspek (cabang v4), evergreen, visual bawaan 0..1,
nama Inggris (pencarian jurnal/OpenAlex/Wikipedia en), judul artikel Wikipedia bahasa Indonesia.
Judul wiki WAJIB judul KANONIK, bukan halaman alihan: pageview halaman alihan hampir nol ("Astronaut" 13/bulan vs
"Antariksawan" 250/bulan) dan API pageview tidak mengikuti alihan. Mode online tetap memeriksa alihan otomatis.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tema:
    nama: str
    pilar: str
    kata: tuple[str, ...]
    aspek: tuple[str, ...]
    ever: int
    visb: float
    en: str
    wiki: str

    @property
    def inti(self) -> str:
        return self.kata[0]


def _t(nama: str, pilar: str, kata: list[str], aspek: list[str], ever: int, visb: float, en: str, wiki: str) -> Tema:
    return Tema(nama, pilar, tuple(kata), tuple(aspek), ever, visb, en, wiki)


DAFTAR: list[Tema] = [
    # tubuh
    _t("cegukan", "tubuh", ["cegukan"], ["lama", "terus", "bayi", "malam"], 1, 0.6, "hiccups", "Cegukan"),
    _t(
        "uban & rambut",
        "tubuh",
        ["uban", "rambut rontok"],
        ["muda", "stres", "dicabut"],
        1,
        0.7,
        "hair greying",
        "Uban",
    ),
    _t("menguap", "tubuh", ["menguap"], ["menular", "ngantuk", "terus"], 1, 0.6, "yawning", "Menguap"),
    _t("bersin", "tubuh", ["bersin"], ["matahari", "terus", "ditahan"], 1, 0.6, "sneeze", "Bersin"),
    _t("merinding", "tubuh", ["merinding"], ["musik", "dingin", "takut"], 1, 0.6, "goose bumps", "Merinding"),
    _t("jantung", "tubuh", ["jantung"], ["berdebar", "berhenti", "detak"], 1, 0.8, "heart", "Jantung"),
    _t("otak", "tubuh", ["otak"], ["lupa", "deja vu", "lelah"], 1, 0.8, "human brain", "Otak"),
    _t("mimpi & tidur", "tubuh", ["mimpi", "tidur"], ["jatuh", "lupa", "ketindihan"], 1, 0.7, "dream sleep", "Mimpi"),
    _t(
        "tulang & sendi",
        "tubuh",
        ["tulang", "sendi berbunyi"],
        ["retak", "bunyi", "patah"],
        1,
        0.7,
        "joint cracking",
        "Sendi",
    ),
    _t("darah", "tubuh", ["darah"], ["merah", "golongan", "biru"], 1, 0.8, "blood", "Darah"),
    _t("kuku", "tubuh", ["kuku"], ["putih", "tumbuh", "belang"], 1, 0.6, "fingernail", "Kuku"),
    _t("lapar & haus", "tubuh", ["lapar", "perut keroncongan"], ["bunyi", "malam", "marah"], 1, 0.6, "hunger", "Lapar"),
    _t("mata", "tubuh", ["mata"], ["kedutan", "minus", "merah"], 1, 0.8, "human eye", "Mata"),
    _t("kulit & jerawat", "tubuh", ["jerawat", "kulit"], ["muncul", "keriput"], 1, 0.7, "acne", "Jerawat"),
    _t("gigi & mulut", "tubuh", ["gigi"], ["ngilu", "berlubang"], 1, 0.7, "tooth decay", "Gigi"),
    # antariksa
    _t(
        "lubang hitam",
        "antariksa",
        ["lubang hitam"],
        ["terdekat", "masuk", "cahaya"],
        1,
        1.0,
        "black hole",
        "Lubang_hitam",
    ),
    _t("aurora", "antariksa", ["aurora"], ["warna", "indonesia", "kutub"], 1, 1.0, "aurora", "Aurora"),
    _t("matahari", "antariksa", ["matahari"], ["panas", "mati", "badai"], 1, 1.0, "sun", "Matahari"),
    _t("bulan", "antariksa", ["bulan"], ["merah", "besar", "siang"], 1, 1.0, "moon", "Bulan"),
    _t("bintang", "antariksa", ["bintang"], ["jatuh", "mati", "terdekat"], 1, 1.0, "star", "Bintang"),
    _t(
        "meteor & komet",
        "antariksa",
        ["meteor", "komet", "hujan meteor"],
        ["jatuh", "warna"],
        1,
        1.0,
        "meteor shower",
        "Meteor",
    ),
    _t("planet mars", "antariksa", ["mars"], ["merah", "air", "hidup"], 1, 0.9, "mars planet", "Mars"),
    _t(
        "saturnus & cincin",
        "antariksa",
        ["saturnus", "cincin saturnus"],
        ["hilang", "terbuat"],
        1,
        1.0,
        "saturn rings",
        "Saturnus",
    ),
    _t("galaksi", "antariksa", ["galaksi", "bima sakti"], ["tabrakan", "pusat"], 1, 1.0, "galaxy", "Galaksi"),
    _t("astronot", "antariksa", ["astronot"], ["tidur", "makan", "melayang"], 1, 0.9, "astronaut", "Antariksawan"),
    _t(
        "alien",
        "antariksa",
        ["alien"],
        ["ada", "sinyal"],
        1,
        0.9,
        "extraterrestrial life",
        "Kehidupan_ekstraterestrial",
    ),
    _t("gerhana", "antariksa", ["gerhana"], ["matahari", "bulan merah"], 1, 1.0, "eclipse", "Gerhana"),
    _t("asteroid", "antariksa", ["asteroid"], ["menabrak", "dinosaurus"], 1, 0.9, "asteroid impact", "Asteroid"),
    # bumi
    _t(
        "hari tanpa bayangan",
        "bumi",
        ["hari tanpa bayangan", "bayangan hilang"],
        ["jam", "indonesia"],
        0,
        0.9,
        "zenith passage shadowless day",
        "Hari_tanpa_bayangan",
    ),
    _t("gempa bumi", "bumi", ["gempa"], ["malam", "terasa"], 1, 0.9, "earthquake", "Gempa_bumi"),
    _t(
        "gunung berapi",
        "bumi",
        ["gunung meletus", "gunung berapi"],
        ["lava", "tidur"],
        1,
        1.0,
        "volcano eruption",
        "Gunung_berapi",
    ),
    _t("tsunami", "bumi", ["tsunami"], ["surut", "tanda"], 1, 1.0, "tsunami", "Tsunami"),
    _t("petir", "bumi", ["petir", "kilat"], ["menyambar", "suara"], 1, 1.0, "lightning", "Petir"),
    _t("hujan & awan", "bumi", ["hujan", "awan"], ["bau", "melayang", "es"], 1, 0.9, "rain cloud", "Hujan"),
    _t("pelangi", "bumi", ["pelangi"], ["melengkung", "ganda", "malam"], 1, 1.0, "rainbow", "Pelangi"),
    _t("es & salju", "bumi", ["salju", "es"], ["putih", "indonesia", "mengapung"], 1, 1.0, "snow ice", "Salju"),
    _t("laut", "bumi", ["laut", "air laut"], ["asin", "biru", "dalam"], 1, 1.0, "ocean", "Laut"),
    _t(
        "angin & badai",
        "bumi",
        ["angin", "badai", "puting beliung"],
        ["berputar", "mata badai"],
        1,
        1.0,
        "tornado storm",
        "Badai",
    ),
    _t("gurun", "bumi", ["gurun"], ["dingin malam", "pasir"], 1, 0.9, "desert", "Gurun"),
    _t("gua", "bumi", ["gua", "stalaktit"], ["gelap", "terbentuk"], 1, 0.9, "cave stalactite", "Gua"),
    # hewan
    _t("ular & reptil", "hewan", ["ular", "reptil"], ["berbisa", "ganti kulit", "lidah"], 1, 1.0, "snake", "Ular"),
    _t("kucing", "hewan", ["kucing"], ["mendengkur", "jatuh"], 1, 0.9, "cat", "Kucing"),
    _t("anjing", "hewan", ["anjing"], ["menggonggong", "setia"], 1, 0.9, "dog", "Anjing"),
    _t("hiu", "hewan", ["hiu"], ["gigi", "tidur"], 1, 1.0, "shark", "Hiu"),
    _t("gurita", "hewan", ["gurita"], ["tiga jantung", "tinta", "pintar"], 1, 1.0, "octopus", "Gurita"),
    _t("lebah & semut", "hewan", ["lebah", "semut"], ["menyengat", "ratu"], 1, 0.9, "honey bee ant colony", "Lebah"),
    _t("burung", "hewan", ["burung"], ["terbang", "migrasi"], 1, 0.9, "bird migration", "Burung"),
    _t("gajah", "hewan", ["gajah"], ["ingatan", "kuburan"], 1, 0.9, "elephant", "Gajah"),
    _t("cicak", "hewan", ["cicak"], ["ekor putus", "menempel"], 1, 0.8, "gecko", "Cecak"),
    _t("dinosaurus", "hewan", ["dinosaurus"], ["punah", "burung"], 1, 1.0, "dinosaur", "Dinosaurus"),
    # teknologi
    _t(
        "baterai & hp",
        "teknologi",
        ["baterai", "hp panas"],
        ["cepat habis", "meledak"],
        1,
        0.8,
        "lithium ion battery",
        "Baterai",
    ),
    _t("internet & wifi", "teknologi", ["wifi", "internet"], ["lemot", "sinyal"], 1, 0.7, "wifi", "Wi-Fi"),
    _t("listrik & magnet", "teknologi", ["listrik", "magnet"], ["setrum", "kutub"], 1, 0.8, "magnetism", "Magnet"),
    _t(
        "pesawat",
        "teknologi",
        ["pesawat"],
        ["terbang", "turbulensi", "putih"],
        1,
        1.0,
        "airplane flight",
        "Pesawat_terbang",
    ),
    _t(
        "kulkas & microwave",
        "teknologi",
        ["microwave", "kulkas"],
        ["panas", "dingin"],
        1,
        0.8,
        "microwave oven",
        "Pemanggang_gelombang_mikro",
    ),
    _t(
        "ai",
        "teknologi",
        ["ai", "kecerdasan buatan"],
        ["berpikir", "bahaya"],
        1,
        0.7,
        "artificial intelligence",
        "Kecerdasan_buatan",
    ),
    # misteri
    _t(
        "piramida",
        "misteri",
        ["piramida"],
        ["dibangun", "mesir", "dalam"],
        1,
        1.0,
        "great pyramid giza",
        "Piramida_Giza",
    ),
    _t(
        "segitiga bermuda",
        "misteri",
        ["segitiga bermuda"],
        ["hilang", "misteri"],
        1,
        0.9,
        "bermuda triangle",
        "Segitiga_Bermuda",
    ),
    _t("stonehenge", "misteri", ["stonehenge"], ["dibangun", "batu"], 1, 0.9, "stonehenge", "Stonehenge"),
    _t("borobudur", "misteri", ["borobudur", "candi"], ["dibangun", "batu"], 1, 0.9, "borobudur", "Borobudur"),
    _t("deja vu", "misteri", ["deja vu"], ["pernah", "otak"], 1, 0.6, "deja vu", "D\u00e9j\u00e0_vu"),
    _t("atlantis", "misteri", ["atlantis"], ["tenggelam", "nyata"], 1, 0.9, "atlantis", "Atlantis"),
]

TEMA: dict[str, Tema] = {t.nama: t for t in DAFTAR}

# leksikon sinyal v3 (niat/sains/rel/kom/vis) - kata utuh
LEKS: dict[str, list[str]] = {
    "niat": ["kenapa", "mengapa", "bagaimana", "apa itu", "apakah", "cara", "penyebab", "proses", "terjadi"],
    "sains": [
        "ilmiah",
        "sains",
        "fakta",
        "penjelasan",
        "teori",
        "nasa",
        "penelitian",
        "fisika",
        "biologi",
        "kimia",
        "otak",
        "sel",
        "gravitasi",
        "cahaya",
        "energi",
        "atom",
        "reaksi",
        "suhu",
        "tekanan",
        "gelombang",
    ],
    "rel": [
        "saya",
        "aku",
        "kita",
        "kalau",
        "saat",
        "setiap",
        "sering",
        "tiba-tiba",
        "malam",
        "pagi",
        "tidur",
        "makan",
        "anak",
        "bayi",
        "rumah",
    ],
    "kom": ["apakah", "benarkah", "mitos", "atau", "lebih", "paling", "bisa", "boleh", "bahaya", "beneran", "benar"],
    "vis": [
        "warna",
        "bentuk",
        "terlihat",
        "cahaya",
        "besar",
        "kecil",
        "bergerak",
        "berputar",
        "meledak",
        "jatuh",
        "terbang",
        "menyala",
        "merah",
        "biru",
        "hijau",
        "hitam",
        "putih",
    ],
}

# kata -> tema untuk mencocokkan momen/berita/tren ke tema (selain kata kunci tema itu sendiri)
SINONIM_MOMEN: dict[str, list[str]] = {
    "gempa bumi": ["gempa", "earthquake", "seismik", "magnitudo"],
    "tsunami": ["tsunami", "peringatan dini tsunami"],
    "gunung berapi": ["erupsi", "gunung", "vulkanik", "volcano", "abu vulkanik", "awan panas"],
    "aurora": ["aurora", "badai geomagnetik", "geomagnetic", "kp"],
    "matahari": [
        "matahari",
        "solar flare",
        "suar matahari",
        "badai matahari",
        "equinox",
        "ekuinoks",
        "solstis",
        "kulminasi",
    ],
    "hari tanpa bayangan": ["hari tanpa bayangan", "kulminasi", "bayangan hilang"],
    "bulan": ["bulan purnama", "supermoon", "bulan baru", "blue moon", "fase bulan"],
    "gerhana": ["gerhana", "eclipse"],
    "meteor & komet": ["hujan meteor", "meteor", "komet", "comet", "bolide"],
    "asteroid": ["asteroid", "near-earth", "close approach", "neo"],
    "angin & badai": ["badai", "siklon", "topan", "puting beliung", "cyclone", "typhoon", "storm"],
    "hujan & awan": ["hujan", "musim hujan", "la nina", "el nino", "banjir"],
    "petir": ["petir", "kilat", "lightning"],
    "planet mars": ["mars"],
    "saturnus & cincin": ["saturnus", "saturn"],
    "astronot": ["astronot", "iss", "stasiun luar angkasa", "artemis", "spacex"],
    "ai": ["ai", "kecerdasan buatan", "chatgpt", "gemini"],
}


# tema BENCANA (ada korban jiwa nyata): nada HORMAT tanpa sensasi di hook/judul/deskripsi, rujuk info resmi & peringatan dini
BENCANA: dict[str, str] = {
    "gempa bumi": "BMKG (bmkg.go.id) & InaTEWS (inatews.bmkg.go.id)",
    "tsunami": "BMKG (bmkg.go.id) & InaTEWS (inatews.bmkg.go.id)",
    "gunung berapi": "PVMBG/MAGMA Indonesia (magma.esdm.go.id)",
    "angin & badai": "BMKG (bmkg.go.id)",
}


# alias relevansi: frasa autocomplete dianggap MEMBAHAS tema bila memuat kata kunci tema ATAU alias ini
# (Google sering menyelipkan kata lain: "kenapa lubang KNALPOT hitam" bukan soal lubang hitam -> dibuang)
ALIAS: dict[str, list[str]] = {
    "lubang hitam": ["black hole"],
    "deja vu": ["dejavu"],  # YouTube menulis "kenapa sering dejavu" (satu kata)
    "laut": ["lautan"],
    "gua": ["goa"],
    "cicak": ["cecak"],
    "astronot": ["antariksawan"],
    "gunung berapi": ["gunung bisa meletus", "gunung api", "erupsi", "gunung semeru", "gunung merapi"],
    "hari tanpa bayangan": ["bayangan"],
    "meteor & komet": ["bintang jatuh"],
    "planet mars": ["planet merah"],
    "saturnus & cincin": ["planet cincin"],
    "uban & rambut": ["rambut putih", "beruban"],
    "ai": ["artificial intelligence", "chatgpt"],
    "es & salju": ["musim salju"],
}


# TOLAK: frasa yang memuat istilah ini membahas MAKNA LAIN dari kata tema (homonim/nama diri) -> bukan tema ini.
# Hanya untuk tema bersangkutan ("masuk angin" bisa jadi topik tubuh kelak), berbeda dari [riset].derau global.
TOLAK: dict[str, list[str]] = {
    "angin & badai": ["angin duduk", "masuk angin", "angin bisa masuk", "angin ac", "angin kompresor"],
    "alien": ["alien stage", "fang", "lemon"],  # serial animasi / tokoh BoBoiBoy / julukan orang
    "ai": ["hoshino"],  # tokoh anime "Ai Hoshino"
    "gajah": ["kampung gajah"],  # taman rekreasi
    "atlantis": ["atlantis land"],  # taman rekreasi Surabaya
}

# KONTEKS: kata tema yang AMBIGU hanya dihitung bila frasa juga memuat salah satu kata konteks.
# "gua" = gua batu ATAU "aku" (bahasa gaul: "kenapa gua susah tidur", "kenapa gua ganteng").
KONTEKS: dict[str, dict[str, list[str]]] = {
    "gua": {
        "gua": [
            "terbentuk",
            "stalaktit",
            "stalagmit",
            "kapur",
            "karst",
            "kelelawar",
            "gelap",
            "dalam gua",
            "masuk gua",
            "purba",
            "pindul",
            "jomblang",
            "batu",
        ]
    },
}


def _ada(f: str, istilah: str) -> bool:
    import re

    from .teks import norm

    k = norm(istilah)
    return bool(k) and re.search(rf"(?<![0-9a-z]){re.escape(k)}(?![0-9a-z])", f) is not None


def relevan(frasa: str, t: Tema) -> bool:
    """frasa autocomplete MEMBAHAS tema t? (kata utuh; alias; tolak homonim; kata ambigu butuh konteks)"""
    from .teks import norm

    f = " " + norm(frasa) + " "
    if any(_ada(f, x) for x in TOLAK.get(t.nama, [])):
        return False
    konteks = KONTEKS.get(t.nama, {})
    for k in (*t.kata, *ALIAS.get(t.nama, [])):
        if not _ada(f, k):
            continue
        if k in konteks and not any(_ada(f, c) for c in konteks[k]):
            continue  # kata ambigu tanpa konteks ("kenapa gua jelek") -> coba kata kunci lain
        return True
    return False


def cari(nama_atau_kata: str) -> Tema | None:
    from .teks import norm

    n = norm(nama_atau_kata)
    if n in TEMA:
        return TEMA[n]
    for t in DAFTAR:
        if n == norm(t.nama) or n in (norm(k) for k in t.kata):
            return t
    return None
