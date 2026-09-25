"""kliktahu/skor.py - RUMUS SKOR dari prompt pemilik (PROMPT_KLIKTAHU.txt §8) + v7. Fungsi MURNI (tanpa I/O).

Satu implementasi dipakai analisis/v3-v6 dan mesin riset real-time (kliktahu/riset). Port TypeScript identik
ada di skema/ts/src/skor.ts dan diuji PARITAS terhadap fixture yang dihasilkan modul ini
(skema/ts/fixture/skor_paritas.json) - kedua bahasa harus memberi angka yang sama persis.

  v3  skor        = jml + kuat*0.7 + niat*0.9 + sains*3 + yt*0.3
      skor_tumbuh = skor + rel*1.2 + kom*1.5 + vis*0.8 + ever*3
  v4  skor_keluarga = skor_tumbuh + jaring*2.5 + kedalaman*1.5 + peluang*2
  v5  velocity   = (jml - jml_lalu)/max(5, jml_lalu) + 0.5 * porsi_frasa_baru
      momen      = 1 - sisa_hari/(jendela*1.25)   (0 <= sisa_hari <= jendela, jendela 45 hari)
      skor_views = (jml + kuat + yt*2 + vis*0.8 + niat*0.6 + sains*2 + jaring*2) + velocity*4 + momen*6
  v6  papan 0-100 = 34 permintaan + 18 wikipedia + 18 celah + 10 visual + 10 pilar + 10 momen
  v7  PELUANG 0-100 = 100 * sum(bobot_i * x_i) atas 8 komponen real-time (lihat BOBOT_V7), plus
      KEYAKINAN 0..1 = porsi bobot yang benar-benar didukung data (komponen tanpa data = netral 0.5, keyakinan 0).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from typing import TypedDict

Nilai = tuple[float, float]  # (x 0..1, keyakinan 0..1)


class Sinyal(TypedDict):
    jml: float
    kuat: float
    niat: float
    yt: float
    sains: float
    rel: float
    kom: float
    vis: float
    ever: float


def _j(x: float) -> float:
    """jepit ke 0..1"""
    return 0.0 if x < 0 else 1.0 if x > 1 else x


# ------------------------------------------------------------------------------------------------ v3
def v3_skor(s: Mapping[str, float]) -> float:
    return s["jml"] + s["kuat"] * 0.7 + s["niat"] * 0.9 + s["sains"] * 3 + s["yt"] * 0.3


def v3_tumbuh(s: Mapping[str, float], skor: float | None = None) -> float:
    skor = v3_skor(s) if skor is None else skor
    return skor + s["rel"] * 1.2 + s["kom"] * 1.5 + s["vis"] * 0.8 + s["ever"] * 3


def kuat(posisi: Iterable[int]) -> float:
    """kekuatan saran: posisi 0 (teratas) bernilai 1.0, posisi 9 bernilai 0.1."""
    return sum((10 - p) / 10 for p in posisi)


# ------------------------------------------------------------------------------------------------ v4
def v4_keluarga(tumbuh: float, jaring: float, kedalaman: float, peluang: float) -> float:
    return tumbuh + jaring * 2.5 + kedalaman * 1.5 + peluang * 2


# ------------------------------------------------------------------------------------------------ v5
def v5_velocity(jml: float, frasa: Sequence[str], jml_lalu: float | None, frasa_lalu: Sequence[str] | None) -> float:
    if jml_lalu is None or frasa_lalu is None:
        return 0.0
    baru = len(set(frasa) - set(frasa_lalu)) / max(1, len(frasa))
    return (jml - jml_lalu) / max(5.0, jml_lalu) + 0.5 * baru


def v5_momen(sisa_hari: float | None, jendela: float = 45) -> float:
    if sisa_hari is None or sisa_hari < 0 or sisa_hari > jendela:
        return 0.0
    return 1.0 - sisa_hari / (jendela * 1.25)


def v5_views(s: Mapping[str, float], jaring: float, velocity: float, momen: float) -> float:
    return (
        (s["jml"] + s["kuat"] + s["yt"] * 2 + s["vis"] * 0.8 + s["niat"] * 0.6 + s["sains"] * 2 + jaring * 2)
        + velocity * 4
        + momen * 6
    )


# ------------------------------------------------------------------------------------------------ v6
def norm01(vals: Sequence[float]) -> list[float]:
    if not vals:
        return []
    lo, hi = min(vals), max(vals)
    return [0.5 if hi - lo < 1e-9 else (v - lo) / (hi - lo) for v in vals]


def skor_wiki(views60: float, tren: float = 1.0) -> float:
    """pageview Wikipedia 60 hari + tren (30 hari terakhir / 30 hari sebelumnya) -> 0..1 (100 rb/60 hari ~ 1)."""
    v = min(1.0, math.log10(max(1.0, views60)) / 5.0)
    tr = _j((tren - 0.7) / 0.9)
    return 0.65 * v + 0.35 * tr


def skor_celah(jumlah: float, umur_median_hari: float = 730, median_views: float = 0) -> float:
    """celah = 1 - kejenuhan pesaing (banyak video, baru, views tinggi = jenuh)."""
    jml = min(1.0, jumlah / 40.0)
    baru = 1.0 - min(1.0, umur_median_hari / 730.0)
    views = min(1.0, median_views / 500000.0)
    return 1.0 - (0.45 * jml + 0.2 * baru + 0.35 * views)


def bobot_pilar(rata: Mapping[str, float], pilar: Sequence[str]) -> dict[str, float]:
    """rata = pilar -> rata-rata (views x retensi). Pilar tanpa data = 0.4; terbaik = 1.0; lainnya 0.25..1."""
    if not rata:
        return {p: 0.5 for p in pilar}
    mx = max(rata.values()) or 1.0
    return {p: (0.25 + 0.75 * rata[p] / mx) if p in rata else 0.4 for p in pilar}


def v6_papan(permintaan: float, wiki: float, celah: float, visual: float, pilar_w: float, momen: float) -> float:
    return 34 * permintaan + 18 * wiki + 18 * celah + 10 * visual + 10 * pilar_w + 10 * momen


# ------------------------------------------------------------------------------------------------ v7
BOBOT_V7: dict[str, float] = {
    "permintaan": 0.26,  # v5 skor_views dinormalisasi (autocomplete Google + YouTube asli)
    "minat": 0.12,  # Wikipedia: tingkat + tren pageview
    "momentum": 0.14,  # NAIK sekarang: velocity snapshot + berita + Google Trends + lonjakan Wikipedia
    "celah": 0.16,  # kejenuhan pesaing YouTube + rasio outlier (views/subscriber)
    "kecocokan": 0.12,  # bisa divisualkan + bobot pilar (performa) + evergreen
    "waktu": 0.10,  # momen (kalender statis + astronomi + umpan live)
    "kesegaran": 0.05,  # belum dibahas & tidak mirip topik lama
    "bukti": 0.05,  # tersedia sumber kredibel (jurnal/lembaga) untuk fakta
}
assert abs(sum(BOBOT_V7.values()) - 1.0) < 1e-12


def momentum(
    velocity: float | None = None,
    berita_rasio: float | None = None,
    tren_traffic: float | None = None,
    wiki_lonjakan: float | None = None,
) -> Nilai | None:
    """gabungan sinyal 'sedang naik'. Tiap bagian 0..1; bobot bagian yang ada dinormalisasi ulang.
    velocity -> 0.5+0.5*tanh(v); berita_rasio (7 hari vs rata-rata mingguan sebelumnya) -> 0.5+0.25*log2(r);
    tren_traffic (Google Trends harian, perkiraan pencarian) -> log10(t)/5; wiki_lonjakan (skor-z 7 hari) -> 0.5+z/6."""
    bagian: list[tuple[float, float]] = []
    if velocity is not None:
        bagian.append((0.35, 0.5 + 0.5 * math.tanh(velocity)))
    if berita_rasio is not None:
        bagian.append((0.25, _j(0.5 + 0.25 * math.log2(max(berita_rasio, 1e-3)))))
    if tren_traffic is not None:
        bagian.append((0.20, _j(math.log10(max(tren_traffic, 1.0)) / 5.0)))
    if wiki_lonjakan is not None:
        bagian.append((0.20, _j(0.5 + wiki_lonjakan / 6.0)))
    if not bagian:
        return None
    w = sum(b[0] for b in bagian)
    return (sum(b[0] * b[1] for b in bagian) / w, w)


def celah_v7(celah: float | None = None, rasio_outlier: float | None = None) -> Nilai | None:
    """celah pesaing + outlier: median(views/subscriber) tinggi = permintaan melebihi pasokan (celah lebih besar)."""
    if celah is None and rasio_outlier is None:
        return None
    s_out = _j(0.5 + 0.25 * math.log10(max(rasio_outlier, 1e-3))) if rasio_outlier is not None else None
    if celah is not None and s_out is not None:
        return (0.7 * celah + 0.3 * s_out, 1.0)
    if celah is not None:
        return (celah, 0.85)
    return (s_out if s_out is not None else 0.5, 0.4)


def kecocokan(visual: float, pilar_w: float, ever: float, ada_performa: bool) -> Nilai:
    return (0.45 * visual + 0.35 * pilar_w + 0.20 * ever, 1.0 if ada_performa else 0.65)


def kesegaran(status: str, mirip_maks: float = 0.0) -> Nilai:
    """'segar' = 1 (dikurangi bila mirip topik lama > 0.6), 'long' = 0.6 (boleh Shorts sudut baru), 'dibahas' = 0."""
    if status == "dibahas":
        return (0.0, 1.0)
    if status == "long":
        return (0.6, 1.0)
    return (max(0.4, 1.0 - max(0.0, mirip_maks - 0.6) * 1.5), 1.0)


def bukti(n_kredibel: int | None) -> Nilai | None:
    return None if n_kredibel is None else (min(1.0, n_kredibel / 4.0), 1.0)


def v7_peluang(
    komponen: Mapping[str, Nilai | None], tanpa: Iterable[str] = ()
) -> tuple[float, float, dict[str, float]]:
    """-> (peluang 0..100, keyakinan 0..1, x per komponen). Komponen tanpa data = netral 0.5, keyakinan 0.
    `tanpa` = komponen yang TIDAK DIPAKAI kanal (mis. 'celah' bila analisis pesaing dimatikan pemilik): bobotnya
    dikeluarkan dan bobot lain dinormalisasi ulang, sehingga keyakinan tidak terkunci oleh sumber yang sengaja
    tidak dipakai. Peringkat tidak berubah (komponen itu netral untuk semua tema); x-nya tetap dilaporkan 0.5."""
    buang = set(tanpa)
    x: dict[str, float] = {}
    total = yakin = wsum = 0.0
    for nama, w in BOBOT_V7.items():
        v = komponen.get(nama)
        xi, ci = (0.5, 0.0) if v is None else (_j(float(v[0])), _j(float(v[1])))
        x[nama] = 0.5 if nama in buang else xi
        if nama in buang:
            continue
        total += w * xi
        yakin += w * ci
        wsum += w
    if not buang:
        return 100.0 * total, yakin, x
    if wsum <= 0:
        return 50.0, 0.0, x
    return 100.0 * total / wsum, yakin / wsum, x


def format_saran(jaring: float, kedalaman: float, ever: float, v7: float) -> str:
    """Long bila pohon pertanyaannya lebar & dalam (cukup untuk ~10 bab) dan evergreen; selain itu Shorts."""
    return "long" if (jaring >= 5 and kedalaman >= 1.6 and ever >= 1 and v7 >= 55) else "shorts"
