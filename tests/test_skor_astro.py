"""rumus prompt §8 (nilai hitung tangan), v7, astronomi offline vs data resmi (BMKG, fase bulan, meteor)."""

from __future__ import annotations

import datetime as dt

import pytest

from kliktahu import astro, momen
from kliktahu import skor as S

SIG = {"jml": 40, "kuat": 20.0, "niat": 30, "yt": 10, "sains": 5, "rel": 8, "kom": 6, "vis": 4.5, "ever": 1}


def test_rumus_prompt_v3_v4_v5_v6():
    assert S.v3_skor(SIG) == pytest.approx(40 + 20 * 0.7 + 30 * 0.9 + 5 * 3 + 10 * 0.3)  # 99.0
    assert S.v3_tumbuh(SIG) == pytest.approx(99 + 8 * 1.2 + 6 * 1.5 + 4.5 * 0.8 + 3)  # 124.2
    assert S.v4_keluarga(124.2, 6, 1.5, 4) == pytest.approx(124.2 + 15 + 2.25 + 8)
    assert S.v5_velocity(30, ["a", "b", "c"], 20, ["a"]) == pytest.approx(10 / 20 + 0.5 * 2 / 3)
    assert S.v5_velocity(30, ["a"], None, None) == 0
    assert S.v5_momen(0) == 1 and S.v5_momen(45) == pytest.approx(1 - 45 / 56.25) and S.v5_momen(46) == 0
    assert S.v5_views(SIG, 3, 0.5, 0.8) == pytest.approx((40 + 20 + 20 + 3.6 + 18 + 10 + 6) + 2 + 4.8)
    assert S.v6_papan(1, 1, 1, 1, 1, 1) == 100 and S.v6_papan(0, 0, 0, 0, 0, 0) == 0
    assert S.skor_celah(5, 900, 20000) > S.skor_celah(60, 120, 800000)
    assert S.skor_wiki(90000, 1.4) > S.skor_wiki(4000, 0.8)


def test_v7_netral_dan_keyakinan():
    v, yakin, x = S.v7_peluang({})
    assert v == pytest.approx(50) and yakin == 0 and set(x) == set(S.BOBOT_V7)
    v, yakin, _ = S.v7_peluang({n: (1.0, 1.0) for n in S.BOBOT_V7})
    assert v == pytest.approx(100) and yakin == pytest.approx(1)
    assert S.kesegaran("dibahas") == (0.0, 1.0) and S.kesegaran("segar", 0.9)[0] < 1
    assert S.momentum(None, None, None, None) is None
    assert S.momentum(1.0, 4.0, 100000, 3)[0] > S.momentum(-1.0, 0.25, 10, -3)[0]


def test_astro_hari_tanpa_bayangan_sama_dengan_bmkg():
    kota = {k.nama: k for k in astro.KOTA}
    sem = astro.hari_tanpa_bayangan(kota["Semarang"], 2026)
    jkt = astro.hari_tanpa_bayangan(kota["Jakarta"], 2026)
    # BMKG kulminasi utama II 2026: Semarang 11 Okt 11.25.02 WIB; Jakarta 9 Okt 11.40 WIB; Jakarta I: 5 Mar
    assert sem[1].date() == dt.date(2026, 10, 11) and abs(sem[1].hour * 60 + sem[1].minute - (11 * 60 + 25)) <= 1
    assert jkt[1].date() == dt.date(2026, 10, 9) and abs(jkt[1].hour * 60 + jkt[1].minute - (11 * 60 + 40)) <= 1
    assert jkt[0].date() == dt.date(2026, 3, 5)
    assert astro.hari_tanpa_bayangan(astro.Kota("Tokyo", 35.7, 139.7, "WIT"), 2026) == []


def test_astro_fase_bulan_ekuinoks_meteor():
    purnama = [t for n, t in astro.fase_bulan_tahun(2026) if n == "purnama"]
    assert [t.strftime("%m-%d") for t in purnama][-3:] == ["10-26", "11-24", "12-24"]
    assert len(purnama) == 13  # 2026 punya blue moon (31 Mei)
    t = astro.fase_bulan_k(-283)  # Meeus contoh 49.a: 1977-02-18 03:37:42 TD
    assert t.date() == dt.date(1977, 2, 18) and abs((t.hour * 60 + t.minute) - (3 * 60 + 37)) <= 2
    jarak = astro.jarak_bulan(dt.datetime(1992, 4, 12, tzinfo=astro.UTC) - dt.timedelta(seconds=69.5))
    assert jarak == pytest.approx(368409.7, abs=300)  # Meeus contoh 47.a
    eq = astro.ekuinoks_solstis(2026)
    assert eq["ekuinoks_september"].date() == dt.date(2026, 9, 23)
    assert abs((eq["ekuinoks_september"] - dt.datetime(2026, 9, 23, 0, 5, tzinfo=astro.UTC)).total_seconds()) < 1200
    puncak = {n: t for n, t, _ in astro.hujan_meteor(2026)}
    for nama, (bl, hr) in {"Orionid": (10, 21), "Leonid": (11, 17), "Geminid": (12, 14), "Lyrid": (4, 22)}.items():
        assert abs((puncak[nama].date() - dt.date(2026, bl, hr)).days) <= 1, nama
    assert [t.strftime("%m-%d") for t, _ in astro.supermoon(2026)] == ["11-24", "12-24"]


def test_momen_skor_tema():
    h = dt.date(2026, 9, 25)
    semua = momen.semua(h, 90)
    s, m = momen.skor_tema("hari tanpa bayangan", semua, h)
    assert s > 0.6 and "bayangan" in m.nama.lower()
    assert momen.skor_tema("cegukan", semua, h) == (0.0, None)
    live = momen.Momen(h, "Gempa M6.2 Sukabumi", ["gempa bumi"], "live", "BMKG", 0.8)
    assert momen.skor_momen(live, h) == pytest.approx(0.8)
    assert momen.skor_momen(live, h + dt.timedelta(days=4)) == 0


def test_v7_tanpa_pesaing_peringkat_sama_keyakinan_tidak_terkunci(k):
    """pemilik mematikan analisis pesaing -> komponen celah keluar dari rumus (bobot lain dinormalisasi)."""
    from kliktahu import skor as S

    assert k.riset.pesaing is False  # kanal.toml: keputusan pemilik 25-09-2026
    tema = {
        "a": {
            "permintaan": (0.71, 1.0),
            "minat": (0.61, 1.0),
            "momentum": (0.54, 0.2),
            "kecocokan": (0.61, 0.65),
            "waktu": (0.95, 1.0),
            "kesegaran": (1.0, 1.0),
        },
        "b": {
            "permintaan": (0.56, 1.0),
            "minat": (0.81, 1.0),
            "momentum": (1.0, 0.2),
            "kecocokan": (0.61, 0.65),
            "waktu": (0.70, 1.0),
            "kesegaran": (0.95, 1.0),
        },
        "c": {
            "permintaan": (1.0, 1.0),
            "minat": (0.54, 1.0),
            "momentum": (0.56, 0.2),
            "kecocokan": (0.56, 0.65),
            "waktu": (0.0, 1.0),
            "kesegaran": (1.0, 1.0),
        },
    }
    lama = {n: S.v7_peluang(kom) for n, kom in tema.items()}
    baru = {n: S.v7_peluang(kom, ("celah",)) for n, kom in tema.items()}
    assert sorted(tema, key=lambda n: -lama[n][0]) == sorted(tema, key=lambda n: -baru[n][0])  # peringkat sama
    for n in tema:
        assert baru[n][0] == pytest.approx((lama[n][0] - 16 * 0.5) / 0.84)  # celah netral 0.5 dikeluarkan
        assert baru[n][1] == pytest.approx(lama[n][1] / 0.84) and baru[n][1] > 0.75 > lama[n][1]
        assert baru[n][2]["celah"] == 0.5
    assert S.v7_peluang({}, tuple(S.BOBOT_V7)) == (50.0, 0.0, {n: 0.5 for n in S.BOBOT_V7})
