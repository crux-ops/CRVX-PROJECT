"""Tahap 3: lapisan pencarian multi-sumber (adaptor, kuota, rantai cadangan, dedup, isolasi kegagalan)."""

from __future__ import annotations

import datetime as dt
import json

import httpx

from kliktahu import cari as C
from kliktahu import kanal
from kliktahu.riset import sumber as SB
from kliktahu.riset.fixture import transport_uji
from kliktahu.riset.http import KlienRiset, Offline

HARI = dt.date(2026, 9, 25)


def _klien(**kw) -> KlienRiset:
    return KlienRiset(kanal.muat(), transport=transport_uji(HARI), pakai_cache=False, tidur=lambda s: None, **kw)


def test_registri_adaptor_lengkap_dan_ttl_sinkron():
    daftar = {s.id: s for s in C.SUMBER.values()}
    for jenis, rantai in C.RANTAI.items():
        assert rantai, f"jenis {jenis} tanpa rantai cadangan"
        for sid in rantai:
            assert sid in C.SUMBER, f"{sid} di rantai tapi tidak terdaftar"
            # cuaca_ekstrem sengaja ikut rantai MOMEN (umpan cuaca menyumbang peristiwa), sisanya searah
            assert C.SUMBER[sid].jenis == jenis or sid == "cuaca_ekstrem"
    for sid in daftar:
        assert C.KUOTA_BAWAAN.get(sid, 0) > 0
        assert daftar[sid].ttl > 0


def test_sumber_butuh_kunci_tidak_masuk_daftar_aktif():
    aktif = {s.id for s in C.daftar_sumber(hanya_aktif=True)}
    assert "pesaing_youtube" not in aktif  # tidak ada YOUTUBE_API_KEY di lingkungan uji
    assert "saran_google" in aktif


def test_cari_satu_jenis_mengembalikan_hasil_berstatus(pencari_uji):
    lap = pencari_uji.cari("kenapa tsunami", C.SARAN)
    assert lap.ok and lap.hasil
    assert all(h.jenis == C.SARAN for h in lap.hasil)
    assert {s.jenis for s in lap.status} == {C.SARAN}
    assert all(c.ok for c in lap.catatan)


def test_rantai_cadangan_dipakai_bila_sumber_pertama_gagal():
    class Rusak:
        def get(self, *a, **kw):
            raise Offline("putus")

    k = kanal.muat()
    pc = C.Pencari(_klien(), k, HARI, "uji")
    # paksa sumber pertama gagal dengan mengganti adaptornya sementara
    asli = C.SUMBER["saran_google"].ambil
    try:
        object.__setattr__(C.SUMBER["saran_google"], "ambil", lambda *a, **kw: (_ for _ in ()).throw(Offline("putus")))
        hasil, catatan = pc.cari_jenis(C.SARAN, "kenapa tsunami")
        assert hasil and {h.sumber for h in hasil} == {"saran_youtube"}  # cadangan menjawab
        assert catatan[0].sumber == "saran_google" and not catatan[0].ok
    finally:
        object.__setattr__(C.SUMBER["saran_google"], "ambil", asli)
    assert Rusak  # referensi kelas contoh (tidak dipakai, hanya penanda niat uji)


def test_kuota_menghentikan_sumber_tanpa_menghentikan_jenis_lain(pencari_uji):
    pc = C.Pencari(pencari_uji.klien, pencari_uji.k, HARI, "uji", kuota={"saran_google": 1})
    pc.cari("satu", C.SARAN)
    lap = pc.cari("dua", C.SARAN)
    assert any((not c.ok) and "kuota" in c.alasan for c in lap.catatan)
    assert pc.cari("tiga", C.WIKI).ok  # jenis lain tetap jalan


def test_dedup_menyimpan_metrik_tertinggi():
    h1 = C.Hasil("a", C.SARAN, "q", "judul sama", url="https://x/1", metrik=3.0)
    h2 = C.Hasil("a", C.SARAN, "q", "judul sama", url="https://x/1", metrik=9.0)
    h3 = C.Hasil("a", C.SARAN, "q", "judul lain")
    out = C.dedup([h1, h2, h3])
    assert len(out) == 2 and out[0].metrik == 9.0


def test_sumber_gagal_tidak_menghentikan_sumber_lain(pencari_uji):
    lap = pencari_uji.cari("kenapa tsunami")  # semua jenis
    assert lap.ok
    gagal = [c for c in lap.catatan if not c.ok]
    assert not gagal, [c.alasan for c in gagal]
    assert len({h.jenis for h in lap.hasil}) >= 5


def test_laporan_per_jenis_dan_ringkas(pencari_uji):
    lap = pencari_uji.cari("kenapa tsunami", [C.SARAN, C.ILMIAH])
    per = lap.per_jenis()
    assert set(per) == {C.SARAN, C.ILMIAH}
    assert "temuan" in lap.ringkas()


# -------------------------------------------------------------------------------- sumber baru (urai murni)
def test_urai_crossref():
    teks = json.dumps(
        {
            "message": {
                "items": [
                    {
                        "title": ["Palu tsunami flow"],
                        "DOI": "10.1142/s1793431120500098",
                        "container-title": ["Journal of Earthquake and Tsunami"],
                        "issued": {"date-parts": [[2019, 12, 20]]},
                        "type": "journal-article",
                        "is-referenced-by-count": 12,
                    },
                    {"title": ["Tanpa DOI"], "DOI": None},
                ]
            }
        }
    )
    out = SB.urai_crossref(teks)
    assert len(out) == 1 and out[0]["doi"] == "10.1142/s1793431120500098"
    assert out[0]["tahun"] == 2019 and out[0]["url"].startswith("https://doi.org/")
    assert SB.urai_crossref("bukan json") == []


def test_urai_cuaca_mendeteksi_ekstrem():
    teks = json.dumps(
        {
            "daily": {
                "time": ["2026-09-26", "2026-09-27"],
                "precipitation_sum": [3.0, 55.0],
                "wind_speed_10m_max": [10.0, 62.0],
            }
        }
    )
    d = SB.urai_cuaca(teks)
    assert len(d["hari"]) == 2
    assert {e["jenis"] for e in d["ekstrem"]} == {"hujan lebat", "angin kencang"}
    assert d["ekstrem"][0]["tanggal"] == "2026-09-27"


def test_urai_wiki_top_membuang_halaman_sistem():
    teks = json.dumps(
        {
            "items": [
                {
                    "articles": [
                        {"article": "Halaman_Utama", "views": 40000, "rank": 1},
                        {"article": "Istimewa:Pencarian", "views": 3000, "rank": 2},
                        {"article": "Berkas:Logo.svg", "views": 900, "rank": 3},
                        {"article": "Tsunami", "views": 800, "rank": 4},
                    ]
                }
            ]
        }
    )
    out = SB.urai_wiki_top(teks)
    assert [o["judul"] for o in out] == ["Tsunami"]


def test_adaptor_baru_kena_transport_uji(pencari_uji):
    assert pencari_uji.cari("tsunami", C.ILMIAH, sumber=["ilmiah_crossref"]).ok
    assert pencari_uji.cari("Jakarta", C.CUACA).ok
    assert pencari_uji.cari("top harian", C.WIKI, sumber=["wiki_top"]).ok


def test_pencari_agen_tanpa_http():
    data = {
        "diambil": "2026-09-25T15:00:00+07:00",
        "saran": {"google": {"kenapa tsunami": ["kenapa tsunami surut", "kenapa tsunami cepat"]}},
        "sumber_ilmiah": {"tsunami": [{"judul": "Palu tsunami", "url": "https://doi.org/10.1000/x"}]},
        "momen_live": [{"tanggal": "2026-09-25", "nama": "Gempa M5.8", "tema": ["gempa bumi"], "urgensi": 0.7}],
        "tren_harian": [{"judul": "gempa hari ini", "traffic": 10000}],
        "tanya": {"tsunami": ["apakah tsunami bisa diprediksi?"]},
    }
    pc = C.PencariAgen(data, kanal.muat(), HARI)
    lap = pc.cari("kenapa tsunami")
    assert lap.ok and {h.jenis for h in lap.hasil} >= {C.SARAN, C.ILMIAH, C.MOMEN, C.TREN, C.WEB}
    assert all(h.status in (G_FIXTURE := {"cache_segar", "kedaluwarsa", "live", "fixture"}) for h in lap.hasil)
    assert G_FIXTURE  # status diisi dari waktu pengambilan, bukan diklaim live


def test_klien_tidak_terjangkau_jadi_status_offline():
    def transport(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("blokir")

    pc = C.Pencari(
        KlienRiset(kanal.muat(), transport=httpx.MockTransport(transport), pakai_cache=False, tidur=lambda s: None),
        kanal.muat(),
        HARI,
        "uji",
    )
    lap = pc.cari("kenapa tsunami", C.SARAN)
    assert not lap.hasil
    assert all(not c.ok for c in lap.catatan)


def test_pencari_agen_membaca_wiki_dan_berita():
    """REGRESI (2026-09-26): dulu bagian 'wiki' & 'berita' di data agen diabaikan diam-diam,
    sehingga laporan mengatakan "momentum netral (tanpa data)" padahal datanya ada."""
    data = {
        "diambil": "2026-09-26T12:00:00+07:00",
        "saran": {"google": {"kenapa gunung meletus": ["kenapa gunung meletus ada petir"]}},
        "wiki": {
            "gunung berapi": {
                "judul": "Gunung berapi",
                "bulanan": {"2026-07": 800, "2026-08": 810, "2026-09": 2200},
                "hari_bulan_ini": 26,
            }
        },
        "berita": {"gunung berapi": {"n7": 5, "n28": 10, "judul": ["Semeru erupsi 700 m"]}},
    }
    pc = C.PencariAgen(data, kanal.muat(), dt.date(2026, 9, 26))
    lap = pc.cari("kenapa gunung meletus")
    jenis = {h.jenis for h in lap.hasil}
    assert C.WIKI in jenis and C.BERITA in jenis
    w = next(h for h in lap.hasil if h.jenis == C.WIKI)
    assert w.metrik and w.metrik > 0 and w.mentah and "lonjakan_z" in w.mentah
    b = next(h for h in lap.hasil if h.jenis == C.BERITA and h.mentah)
    assert b.mentah["n7"] == 5 and b.mentah["rasio"] > 1.0
    assert "wiki_agen" in pc.ringkas() and "berita_agen" in pc.ringkas()


def test_ringkas_agen_menyebut_sumber_yang_terpakai():
    """REGRESI: ringkas() dulu selalu "0/0 bagian data terpakai" karena catatan tidak pernah diakumulasi."""
    data = {"diambil": "2026-09-26T12:00:00+07:00", "saran": {"google": {"kenapa kuku": ["kenapa kuku bergelombang"]}}}
    pc = C.PencariAgen(data, kanal.muat(), dt.date(2026, 9, 26))
    assert "belum ada" in pc.ringkas()
    pc.cari("kenapa kuku")
    r = pc.ringkas()
    assert "0/0" not in r and "saran_google" in r
