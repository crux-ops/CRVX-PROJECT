"""Tahap 1 (validasi input & provenance) dan tahap 2 (kesegaran & status sumber)."""

from __future__ import annotations

import datetime as dt

import pytest

from kliktahu import kesegaran as G
from kliktahu import validasi as V

UTC = dt.UTC


# -------------------------------------------------------------------------------------------------- tahap 1
def test_waktu_wajib_berzona():
    hv = V.HasilValidasi()
    assert V.waktu_berzona("2026-09-26T10:00:00+07:00", "w", hv) is not None
    assert V.waktu_berzona("2026-09-26T10:00:00Z", "w", hv) is not None
    assert V.waktu_berzona("2026-09-26", "w", hv) is None  # tanpa zona -> ditolak
    assert hv.galat and "zona" in hv.galat[-1].pesan


def test_url_ditolak_bila_rahasia_atau_userinfo():
    hv = V.HasilValidasi()
    assert V.url_sah("https://nasa.gov/a?b=1", "u", hv)
    assert V.url_sah("https://u:p@x.com/a", "u", hv) is None
    assert V.url_sah("https://api.x.com/a?key=RAHASIA", "u", hv) is None
    assert V.url_sah("ftp://x.com/a", "u", hv) is None
    assert len(hv.galat) == 3


def test_kredibilitas_tidak_pernah_bawaan_true():
    """sumber luar mengaku kredibel tetapi domainnya tidak dikenal -> kredibel dihitung ulang jadi False."""
    items = [
        {"judul": "Tulisan blog", "url": "https://blog-aneh.com/tsunami", "kredibel": True},
        {"judul": "Jurnal", "url": "https://doi.org/10.1000/1", "doi": "10.1000/1", "penerbit": "Nature"},
        {"judul": "Tanpa URL/DOI", "kredibel": True},
        "bukan objek",
    ]
    bersih, hv = V.bersihkan_sumber(items, ("nature.com",))
    assert [b["judul"] for b in bersih] == ["Tulisan blog", "Jurnal"]
    assert bersih[0]["kredibel"] is False
    assert bersih[1]["kredibel"] is True  # DOI sah + penerbit -> bisa dicek
    assert any("tidak lolos" in g.pesan for g in hv.peringatan)


def test_rentang_angka_dan_panjang_teks():
    hv = V.HasilValidasi()
    assert V.angka(5, "a", hv, 0, 10) == 5.0
    assert V.angka(50, "a", hv, 0, 10) is None
    assert V.angka(True, "a", hv, 0, 10) is None  # bool bukan angka
    assert V.angka(float("nan"), "a", hv, 0, 10) is None
    assert V.teks("x" * 500, "t", hv, maks=100) is None


def test_validasi_data_agen_menolak_struktur_asing_dan_tema_tidak_dikenal():
    hv = V.validasi_data_agen({"saran": {"google": {"q": ["a"]}}, "bagian_aneh": 1}, {"tsunami"})
    assert any("tidak dikenal" in g.pesan for g in hv.galat)
    hv2 = V.validasi_data_agen({"wiki": {"topik_aneh": {"views60": 10}}}, {"tsunami"})
    assert any("tidak ada di registri" in g.pesan for g in hv2.galat)


def test_validasi_data_agen_terima_berkas_nyata():
    data = {
        "diambil": "2026-09-25T15:00:00+07:00",
        "alat": "fetch_page",
        "saran": {"google": {"kenapa tsunami": ["kenapa tsunami bisa terjadi"]}},
        "wiki": {"tsunami": {"bulanan": {"2026-07": 100, "2026-08": 120}, "hari_bulan_ini": 25}},
        "momen_live": [{"tanggal": "2026-09-25", "nama": "Gempa M5.8", "tema": ["gempa bumi"], "urgensi": 0.6}],
        "sumber_ilmiah": {
            "tsunami": [{"judul": "Palu tsunami", "url": "https://doi.org/10.1000/x", "doi": "10.1000/x"}]
        },
    }
    hv = V.validasi_data_agen(data, {"tsunami"}, ("nature.com",))
    assert hv.ok, hv.galat


def test_validasi_data_agen_menolak_bulan_ngawur():
    hv = V.validasi_data_agen({"wiki": {"tsunami": {"bulanan": {"2026-13": 5}}}}, {"tsunami"})
    assert any("YYYY-MM" in g.pesan for g in hv.galat)


# -------------------------------------------------------------------------------------------------- tahap 2
def test_status_sumber_lima_keadaan():
    now = dt.datetime(2026, 9, 26, 4, tzinfo=UTC)
    assert G.status_sumber("saran", now - dt.timedelta(hours=1), now).status == G.CACHE_SEGAR
    assert G.status_sumber("momen", now - dt.timedelta(hours=1), now).status == G.KEDALUWARSA  # TTL 0.5 jam
    assert G.status_sumber("ilmiah", now - dt.timedelta(days=3), now).status == G.CACHE_SEGAR  # TTL 168 jam
    assert G.status_sumber("berita", None, now).status == G.TANPA_DATA
    assert G.status_sumber("berita", None, now, catatan="host diblokir").status == G.OFFLINE
    assert G.status_sumber("saran", now, now, dari_jaringan=True).status == G.LIVE
    assert G.status_sumber("saran", now, now, fixture=True).status == G.FIXTURE


def test_keyakinan_data_turun_bila_kedaluwarsa():
    now = dt.datetime(2026, 9, 26, 4, tzinfo=UTC)
    st = [
        G.status_sumber("saran", now - dt.timedelta(hours=1), now),
        G.status_sumber("momen", now - dt.timedelta(days=2), now),
    ]
    assert 0.0 < G.keyakinan_data(st) < 1.0
    assert G.keyakinan_data([]) == 0.0


def test_ttl_bisa_diganti_dan_gabung_ambil_tersegar():
    now = dt.datetime(2026, 9, 26, 4, tzinfo=UTC)
    s = G.status_sumber("saran", now - dt.timedelta(hours=5), now, ttl_jam=1.0)
    assert s.status == G.KEDALUWARSA and s.ttl_jam == 1.0
    gab = G.gabung([s, G.status_sumber("saran", now, now, dari_jaringan=True)])
    assert gab["saran"].status == G.LIVE


def test_tanpa_zona_dicatat_bukan_ditolak():
    now = dt.datetime(2026, 9, 26, 4, tzinfo=UTC)
    s = G.status_sumber("saran", dt.datetime(2026, 9, 26, 2), now)
    assert s.status == G.CACHE_SEGAR and "tanpa zona" in s.catatan


def test_ringkas_dan_tabel():
    now = dt.datetime(2026, 9, 26, 4, tzinfo=UTC)
    st = G.status_sumber("saran", now - dt.timedelta(hours=1), now, sumber="saran_google")
    assert "saran" in G.ringkas([st]) and len(G.tabel_md([st])) == 3


@pytest.mark.parametrize("jenis", ["saran", "momen", "ilmiah", "tren"])
def test_ttl_setiap_jenis_ada_dan_masuk_akal(jenis):
    assert 0 < G.ttl(jenis) <= 720
