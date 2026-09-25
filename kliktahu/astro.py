"""kliktahu/astro.py - ASTRONOMI OFFLINE untuk deteksi momen (tanpa internet, tanpa pustaka tambahan).

Algoritma Jean Meeus, "Astronomical Algorithms" (2nd ed.) + persamaan matahari NOAA:
* posisi Matahari (bujur tampak, deklinasi, persamaan waktu)           - ketelitian ~0.01 derajat
* ekuinoks & solstis (iterasi bujur Matahari = 0/90/180/270)            - ~ +-15 menit
* fase Bulan (bab 49, koreksi lengkap + planet)                         - ~ beberapa menit
* jarak Bulan (bab 47, 32 suku terbesar) -> SUPERMOON                    - ~ +-300 km
* HARI TANPA BAYANGAN (Matahari tepat di zenit) per kota Indonesia     - cocok dengan tabel BMKG
* puncak HUJAN METEOR dari bujur Matahari J2000 (kalender IMO)          - ~ +-0.5 hari
Semua waktu keluaran UTC (datetime sadar zona) kecuali disebut lain.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass

UTC = dt.UTC
ZONA = {"WIB": 7, "WITA": 8, "WIT": 9}
DELTA_T = 69.5 / 86400.0  # TT - UT (detik -> hari), berlaku ~2020-2035 (galat < 2 s)
_r = math.radians


def jd(t: dt.datetime) -> float:
    """Julian Day (UT) dari datetime (naif dianggap UTC)."""
    if t.tzinfo is not None:
        t = t.astimezone(UTC)
    y, m = t.year, t.month
    d = t.day + (t.hour + (t.minute + (t.second + t.microsecond / 1e6) / 60) / 60) / 24
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + b - 1524.5


def dari_jd(j: float) -> dt.datetime:
    """datetime UTC dari Julian Day (Meeus bab 7)."""
    j += 0.5
    z = int(j)
    f = j - z
    if z < 2299161:
        a = z
    else:
        al = int((z - 1867216.25) / 36524.25)
        a = z + 1 + al - al // 4
    b = a + 1524
    c = int((b - 122.1) / 365.25)
    d = int(365.25 * c)
    e = int((b - d) / 30.6001)
    hari = b - d - int(30.6001 * e) + f
    bulan = e - 1 if e < 14 else e - 13
    tahun = c - 4716 if bulan > 2 else c - 4715
    hh = int(hari)
    detik = round((hari - hh) * 86400)
    return dt.datetime(tahun, bulan, hh, tzinfo=UTC) + dt.timedelta(seconds=detik)


@dataclass(frozen=True)
class Matahari:
    bujur: float  # bujur ekliptika TAMPAK (derajat, ekuinoks tanggal itu)
    bujur_j2000: float  # bujur geometris dirujuk ke J2000 (untuk kalender hujan meteor IMO)
    deklinasi: float  # derajat
    eot: float  # persamaan waktu (menit): jam matahari - jam rata-rata


def matahari(jde: float) -> Matahari:
    T = (jde - 2451545.0) / 36525.0
    L0 = (280.46646 + 36000.76983 * T + 0.0003032 * T * T) % 360
    M = 357.52911 + 35999.05029 * T - 0.0001537 * T * T
    e = 0.016708634 - 0.000042037 * T - 0.0000001267 * T * T
    Mr = _r(M)
    C = (
        (1.914602 - 0.004817 * T - 0.000014 * T * T) * math.sin(Mr)
        + (0.019993 - 0.000101 * T) * math.sin(2 * Mr)
        + 0.000289 * math.sin(3 * Mr)
    )
    benar = L0 + C
    om = 125.04 - 1934.136 * T
    tampak = benar - 0.00569 - 0.00478 * math.sin(_r(om))
    eps0 = 23 + (26 + (21.448 - T * (46.815 + T * (0.00059 - T * 0.001813))) / 60) / 60
    eps = eps0 + 0.00256 * math.cos(_r(om))
    dek = math.degrees(math.asin(math.sin(_r(eps)) * math.sin(_r(tampak))))
    y = math.tan(_r(eps / 2)) ** 2
    L0r = _r(L0)
    eot = 4 * math.degrees(
        y * math.sin(2 * L0r)
        - 2 * e * math.sin(Mr)
        + 4 * e * y * math.sin(Mr) * math.cos(2 * L0r)
        - 0.5 * y * y * math.sin(4 * L0r)
        - 1.25 * e * e * math.sin(2 * Mr)
    )
    j2000 = (benar - 1.3969713 * T) % 360  # presesi umum sejak J2000
    return Matahari(tampak % 360, j2000, dek, eot)


def _cari_bujur(target: float, jde0: float, j2000: bool = False) -> float:
    """JDE saat bujur Matahari = target (iterasi Meeus: koreksi 58 hari x sin(selisih))."""
    j = jde0
    for _ in range(50):
        m = matahari(j)
        lon = m.bujur_j2000 if j2000 else m.bujur
        d = 58.0 * math.sin(_r(target - lon))
        j += d
        if abs(d) < 1e-6:
            break
    return j


def ekuinoks_solstis(tahun: int) -> dict[str, dt.datetime]:
    awal = {
        "ekuinoks_maret": (0, 3, 20),
        "solstis_juni": (90, 6, 21),
        "ekuinoks_september": (180, 9, 23),
        "solstis_desember": (270, 12, 21),
    }
    out = {}
    for nama, (lon, bl, hr) in awal.items():
        jde = _cari_bujur(lon, jd(dt.datetime(tahun, bl, hr, 12, tzinfo=UTC)) + DELTA_T)
        out[nama] = dari_jd(jde - DELTA_T)
    return out


# ------------------------------------------------------------------------------------------------ Bulan
_BARU = [
    (-0.40720, "Mp", 0),
    (0.17241, "M", 1),
    (0.01608, "2Mp", 0),
    (0.01039, "2F", 0),
    (0.00739, "Mp-M", 1),
    (-0.00514, "Mp+M", 1),
    (0.00208, "2M", 2),
    (-0.00111, "Mp-2F", 0),
    (-0.00057, "Mp+2F", 0),
    (0.00056, "2Mp+M", 1),
    (-0.00042, "3Mp", 0),
    (0.00042, "M+2F", 1),
    (0.00038, "M-2F", 1),
    (-0.00024, "2Mp-M", 1),
    (-0.00017, "Om", 0),
    (-0.00007, "Mp+2M", 0),
    (0.00004, "2Mp-2F", 0),
    (0.00004, "3M", 0),
    (0.00003, "Mp+M-2F", 0),
    (0.00003, "2Mp+2F", 0),
    (-0.00003, "Mp+M+2F", 0),
    (0.00003, "Mp-M+2F", 0),
    (-0.00002, "Mp-M-2F", 0),
    (-0.00002, "3Mp+M", 0),
    (0.00002, "4Mp", 0),
]
_PURNAMA = [
    (-0.40614, "Mp", 0),
    (0.17302, "M", 1),
    (0.01614, "2Mp", 0),
    (0.01043, "2F", 0),
    (0.00734, "Mp-M", 1),
    (-0.00515, "Mp+M", 1),
    (0.00209, "2M", 2),
    (-0.00111, "Mp-2F", 0),
    (-0.00057, "Mp+2F", 0),
    (0.00056, "2Mp+M", 1),
    (-0.00042, "3Mp", 0),
    (0.00042, "M+2F", 1),
    (0.00038, "M-2F", 1),
    (-0.00024, "2Mp-M", 1),
    (-0.00017, "Om", 0),
    (-0.00007, "Mp+2M", 0),
    (0.00004, "2Mp-2F", 0),
    (0.00004, "3M", 0),
    (0.00003, "Mp+M-2F", 0),
    (0.00003, "2Mp+2F", 0),
    (-0.00003, "Mp+M+2F", 0),
    (0.00003, "Mp-M+2F", 0),
    (-0.00002, "Mp-M-2F", 0),
    (-0.00002, "3Mp+M", 0),
    (0.00002, "4Mp", 0),
]
_KUARTIR = [
    (-0.62801, "Mp", 0),
    (0.17172, "M", 1),
    (-0.01183, "Mp+M", 1),
    (0.00862, "2Mp", 0),
    (0.00804, "2F", 0),
    (0.00454, "Mp-M", 1),
    (0.00204, "2M", 2),
    (-0.00180, "Mp-2F", 0),
    (-0.00070, "Mp+2F", 0),
    (-0.00040, "3Mp", 0),
    (-0.00034, "2Mp-M", 1),
    (0.00032, "M+2F", 1),
    (0.00032, "M-2F", 1),
    (-0.00028, "Mp+2M", 2),
    (0.00027, "2Mp+M", 1),
    (-0.00017, "Om", 0),
    (-0.00005, "Mp-M-2F", 0),
    (0.00004, "2Mp+2F", 0),
    (-0.00004, "Mp+M+2F", 0),
    (0.00004, "Mp-2M", 0),
    (0.00003, "Mp+M-2F", 0),
    (0.00003, "3M", 0),
    (0.00002, "2Mp-2F", 0),
    (0.00002, "Mp-M+2F", 0),
    (-0.00002, "3Mp+M", 0),
]
_PLANET = [
    (0.000325, 299.77, 0.107408, -0.009173),
    (0.000165, 251.88, 0.016321, 0),
    (0.000164, 251.83, 26.651886, 0),
    (0.000126, 349.42, 36.412478, 0),
    (0.000110, 84.66, 18.206239, 0),
    (0.000062, 141.74, 53.303771, 0),
    (0.000060, 207.14, 2.453732, 0),
    (0.000056, 154.84, 7.306860, 0),
    (0.000047, 34.52, 27.261239, 0),
    (0.000042, 207.19, 0.121824, 0),
    (0.000040, 291.34, 1.844379, 0),
    (0.000037, 161.72, 24.198154, 0),
    (0.000035, 239.56, 25.513099, 0),
    (0.000023, 331.55, 3.592518, 0),
]


def _arg(expr: str, v: dict[str, float]) -> float:
    """evaluasi kombinasi linear argumen seperti '2Mp+M-2F' (derajat)."""
    tot, i, tanda = 0.0, 0, 1.0
    while i < len(expr):
        ch = expr[i]
        if ch in "+-":
            tanda = 1.0 if ch == "+" else -1.0
            i += 1
            continue
        n = ""
        while i < len(expr) and expr[i].isdigit():
            n += expr[i]
            i += 1
        nama = expr[i : i + 2] if expr[i : i + 2] in ("Mp", "Om") else expr[i]
        i += len(nama)
        tot += tanda * (int(n) if n else 1) * v[nama]
        tanda = 1.0
    return tot


def fase_bulan_k(k: float) -> dt.datetime:
    """k bulat = bulan baru, +0.25 kuartir awal, +0.5 purnama, +0.75 kuartir akhir (Meeus bab 49). -> UTC."""
    T = k / 1236.85
    jde = 2451550.09766 + 29.530588861 * k + 0.00015437 * T**2 - 0.000000150 * T**3 + 0.00000000073 * T**4
    E = 1 - 0.002516 * T - 0.0000074 * T**2
    v = {
        "M": 2.5534 + 29.10535670 * k - 0.0000014 * T**2 - 0.00000011 * T**3,
        "Mp": 201.5643 + 385.81693528 * k + 0.0107582 * T**2 + 0.00001238 * T**3 - 0.000000058 * T**4,
        "F": 160.7108 + 390.67050284 * k - 0.0016118 * T**2 - 0.00000227 * T**3 + 0.000000011 * T**4,
        "Om": 124.7746 - 1.56375588 * k + 0.0020672 * T**2 + 0.00000215 * T**3,
    }
    frac = round((k - math.floor(k)) * 4) / 4
    tabel = _BARU if frac == 0 else _PURNAMA if frac == 0.5 else _KUARTIR
    kor = sum(c * E**pe * math.sin(_r(_arg(a, v))) for c, a, pe in tabel)
    if frac in (0.25, 0.75):
        M, Mp, F = _r(v["M"]), _r(v["Mp"]), _r(v["F"])
        W = (
            0.00306
            - 0.00038 * E * math.cos(M)
            + 0.00026 * math.cos(Mp)
            - 0.00002 * math.cos(Mp - M)
            + 0.00002 * math.cos(Mp + M)
            + 0.00002 * math.cos(2 * F)
        )
        kor += W if frac == 0.25 else -W
    kor += sum(c * math.sin(_r(a0 + a1 * k + a2 * T * T)) for c, a0, a1, a2 in _PLANET)
    return dari_jd(jde + kor - DELTA_T)


_JARAK = [  # (D, M, Mp, F, sigma_r) Meeus tabel 47.A, 32 suku terbesar (satuan 0.001 km)
    (0, 0, 1, 0, -20905355),
    (2, 0, -1, 0, -3699111),
    (2, 0, 0, 0, -2955968),
    (0, 0, 2, 0, -569925),
    (0, 1, 0, 0, 48888),
    (0, 0, 0, 2, -3149),
    (2, 0, -2, 0, 246158),
    (2, -1, -1, 0, -152138),
    (2, 0, 1, 0, -170733),
    (2, -1, 0, 0, -204586),
    (0, 1, -1, 0, -129620),
    (1, 0, 0, 0, 108743),
    (0, 1, 1, 0, 104755),
    (2, 0, 0, -2, 10321),
    (0, 0, 1, -2, 79661),
    (4, 0, -1, 0, -34782),
    (0, 0, 3, 0, -23210),
    (4, 0, -2, 0, -21636),
    (2, 1, -1, 0, 24208),
    (2, 1, 0, 0, 30824),
    (1, 0, -1, 0, -8379),
    (1, 1, 0, 0, -16675),
    (2, -1, 1, 0, -12831),
    (2, 0, 2, 0, -10445),
    (4, 0, 0, 0, -11650),
    (2, 0, -3, 0, 14403),
    (0, 1, -2, 0, -7003),
    (2, -1, -2, 0, 10056),
    (1, 0, 1, 0, 6322),
    (2, -2, 0, 0, -9884),
    (0, 1, 2, 0, 5751),
    (0, 2, 0, 0, -4950),
]


def jarak_bulan(t: dt.datetime) -> float:
    """jarak pusat Bumi-Bulan (km) - Meeus bab 47 (suku terbesar)."""
    T = (jd(t) + DELTA_T - 2451545.0) / 36525.0
    D = 297.8501921 + 445267.1114034 * T - 0.0018819 * T**2 + T**3 / 545868 - T**4 / 113065000
    M = 357.5291092 + 35999.0502909 * T - 0.0001536 * T**2 + T**3 / 24490000
    Mp = 134.9633964 + 477198.8675055 * T + 0.0087414 * T**2 + T**3 / 69699 - T**4 / 14712000
    F = 93.2720950 + 483202.0175233 * T - 0.0036539 * T**2 - T**3 / 3526000 + T**4 / 863310000
    E = 1 - 0.002516 * T - 0.0000074 * T**2
    sr = sum(c * (E ** abs(m)) * math.cos(_r(d * D + m * M + mp * Mp + f * F)) for d, m, mp, f, c in _JARAK)
    return 385000.56 + sr / 1000.0


def fase_bulan_tahun(tahun: int) -> list[tuple[str, dt.datetime]]:
    """semua fase utama Bulan dalam satu tahun (UTC)."""
    nama = {0.0: "bulan baru", 0.25: "kuartir awal", 0.5: "purnama", 0.75: "kuartir akhir"}
    k0 = math.floor((tahun - 2000) * 12.3685) - 2
    out = []
    for i in range(0, 4 * 16):
        k = k0 + i / 4
        t = fase_bulan_k(k)
        if t.year == tahun:
            out.append((nama[round((k - math.floor(k)) * 4) / 4], t))
    return sorted(out, key=lambda x: x[1])


def supermoon(tahun: int, ambang_km: float = 361500.0) -> list[tuple[dt.datetime, float]]:
    """purnama dengan jarak Bulan <= ambang (definisi umum 'supermoon', ~90% jarak perige)."""
    return [(t, jarak_bulan(t)) for n, t in fase_bulan_tahun(tahun) if n == "purnama" and jarak_bulan(t) <= ambang_km]


# ------------------------------------------------------------------------------------------------ zenit
@dataclass(frozen=True)
class Kota:
    nama: str
    lat: float
    lon: float
    zona: str


KOTA: tuple[Kota, ...] = (
    Kota("Banda Aceh", 5.5483, 95.3238, "WIB"),
    Kota("Medan", 3.5952, 98.6722, "WIB"),
    Kota("Pontianak", -0.0263, 109.3425, "WIB"),
    Kota("Palembang", -2.9761, 104.7754, "WIB"),
    Kota("Jakarta", -6.1754, 106.8272, "WIB"),
    Kota("Bandung", -6.9175, 107.6191, "WIB"),
    Kota("Cianjur", -6.8222, 107.1394, "WIB"),
    Kota("Semarang", -6.9900, 110.4200, "WIB"),
    Kota("Yogyakarta", -7.7956, 110.3695, "WIB"),
    Kota("Surabaya", -7.2575, 112.7521, "WIB"),
    Kota("Denpasar", -8.6705, 115.2126, "WITA"),
    Kota("Banjarmasin", -3.3186, 114.5944, "WITA"),
    Kota("Makassar", -5.1477, 119.4327, "WITA"),
    Kota("Manado", 1.4748, 124.8421, "WITA"),
    Kota("Kupang", -10.1772, 123.6070, "WITA"),
    Kota("Ambon", -3.6954, 128.1814, "WIT"),
    Kota("Jayapura", -2.5337, 140.7181, "WIT"),
)


def tengah_hari(tanggal: dt.date, lon: float) -> dt.datetime:
    """waktu kulminasi Matahari (UTC) di bujur lon pada tanggal itu."""
    t = dt.datetime(tanggal.year, tanggal.month, tanggal.day, 12, tzinfo=UTC) - dt.timedelta(hours=lon / 15)
    for _ in range(2):
        eot = matahari(jd(t) + DELTA_T).eot
        t = dt.datetime(tanggal.year, tanggal.month, tanggal.day, 12, tzinfo=UTC) - dt.timedelta(
            hours=lon / 15, minutes=eot
        )
    return t


def hari_tanpa_bayangan(kota: Kota, tahun: int) -> list[dt.datetime]:
    """saat Matahari tepat di zenit (deklinasi = lintang) - 2x setahun untuk kota tropis. -> waktu LOKAL."""
    if abs(kota.lat) > 23.43:
        return []
    zona = dt.timezone(dt.timedelta(hours=ZONA[kota.zona]), kota.zona)
    selisih = []
    d = dt.date(tahun, 1, 1)
    while d.year == tahun:
        t = tengah_hari(d, kota.lon)
        selisih.append((d, t, matahari(jd(t) + DELTA_T).deklinasi - kota.lat))
        d += dt.timedelta(days=1)
    out = []
    for (d0, t0, s0), (d1, t1, s1) in zip(selisih, selisih[1:]):
        if s0 == 0 or (s0 < 0) != (s1 < 0):
            t = t0 if abs(s0) <= abs(s1) else t1
            out.append(t.astimezone(zona))
    return out


# ------------------------------------------------------------------------------------------------ meteor
HUJAN_METEOR: tuple[tuple[str, float, int], ...] = (  # (nama, bujur Matahari J2000 puncak (IMO), ZHR khas)
    ("Quadrantid", 283.15, 110),
    ("Lyrid", 32.32, 18),
    ("Eta Aquarid", 45.5, 50),
    ("Delta Aquarid Selatan", 127.0, 25),
    ("Perseid", 140.0, 100),
    ("Draconid", 195.4, 10),
    ("Orionid", 208.0, 20),
    ("Leonid", 235.27, 15),
    ("Geminid", 262.2, 150),
    ("Ursid", 270.7, 10),
)


def hujan_meteor(tahun: int) -> list[tuple[str, dt.datetime, int]]:
    out = []
    for nama, lon, zhr in HUJAN_METEOR:
        # tebakan awal: bujur 0 ~ 20 Maret, ~0.9856 derajat per hari
        tebak = dt.datetime(tahun, 3, 20, tzinfo=UTC) + dt.timedelta(days=((lon % 360) / 0.9856))
        if tebak.year != tahun:
            tebak = tebak.replace(year=tahun)
        jde = _cari_bujur(lon, jd(tebak) + DELTA_T, j2000=True)
        t = dari_jd(jde - DELTA_T)
        if t.year != tahun:  # Quadrantid dll. bisa jatuh di tahun sebelah -> geser satu tahun
            jde = _cari_bujur(lon, jde + (365.2422 if t.year < tahun else -365.2422), j2000=True)
            t = dari_jd(jde - DELTA_T)
        out.append((nama, t, zhr))
    return sorted(out, key=lambda x: x[1])
