"""Tahap 4: penemuan topik (kandidat di luar registri tetap muncul, dengan keterangan batasnya)."""

from __future__ import annotations

from kliktahu import penemuan as P
from kliktahu.cari import BERITA, CUACA, MOMEN, SARAN, TREN, WIKI, Hasil


def test_inti_dari_pertanyaan_membuang_benih_dan_kata_fungsi():
    assert P.inti_dari_pertanyaan("kenapa air laut bisa asin sekali") == "air laut asin"
    assert P.inti_dari_pertanyaan("apakah gunung berapi bisa meletus") is not None
    assert P.inti_dari_pertanyaan("kenapa") is None


def test_tema_disebut_memilih_kata_kunci_terpanjang():
    """'gunung meletus TIDUR' = gunung berapi yang tidur, bukan topik mimpi & tidur."""
    assert P.tema_disebut("kenapa gunung meletus tidur") == ["gunung berapi"]
    assert "tsunami" in P.tema_disebut("kenapa tsunami surut")
    assert P.tema_disebut("kenapa gua jelek") == []  # homonim: 'gua' = aku (gaul)


def test_nilai_kecocokan_registri_dan_bukan():
    pilar, skor, terdekat, di_reg, cat = P.nilai_kecocokan("gunung berapi")
    assert (pilar, skor, di_reg) == ("bumi", 1.0, True)
    pilar2, skor2, terdekat2, di_reg2, cat2 = P.nilai_kecocokan("sabun mandi cair")
    assert di_reg2 is False and pilar2 == "" and skor2 < 0.2 and "luar niche" in cat2
    assert terdekat2 is None  # kemiripan kebetulan tidak dipaksa cocok


def test_kandidat_di_luar_registri_ditandai_dan_dijelaskan():
    daftar = P.dari_hasil(
        [
            Hasil("saran_google", SARAN, "q", "kenapa jamur tumbuh di kamar mandi"),
            Hasil("saran_google", SARAN, "q", "kenapa tsunami surut"),
        ]
    )
    nama = {k.nama for k in daftar}
    assert "tsunami" in nama  # kanonik registri
    assert any(not k.di_registri for k in daftar)  # 'jamur tumbuh kamar' -> di luar registri
    teks = P.batas_registri(daftar)
    assert "registri" in teks and "62" in teks


def test_gabung_dan_kanonisasi_menyatukan_nama_lain():
    a = P.Kandidat("gunung meletus", "", 0.9, bukti=["kenapa gunung meletus"])
    b = P.Kandidat("gunung berapi", "bumi", 1.0, di_registri=True, bukti=["kenapa gunung berapi"])
    out = P.kanonisasi(P.gabung([a, b]))
    assert [k.nama for k in out] == ["gunung berapi"]
    assert out[0].di_registri and len(out[0].bukti) == 2


def test_kanonisasi_tidak_menggabung_topik_yang_beda():
    a = P.Kandidat("tsunami", "bumi", 1.0, di_registri=True)
    b = P.Kandidat("gempa bumi", "bumi", 1.0, di_registri=True)
    assert {k.nama for k in P.kanonisasi([a, b])} == {"tsunami", "gempa bumi"}


def test_kandidat_dari_momen_dan_berita():
    hasil = [
        Hasil("momen_bmkg", MOMEN, "", "Gempa M5.8 Sukabumi", terbit="2026-09-25"),
        Hasil("cuaca_ekstrem", CUACA, "Jakarta", "Jakarta: hujan lebat 60.0 mm (2026-09-27)", terbit="2026-09-27"),
        Hasil("berita_gnews", BERITA, "q", "Tsunami Palu delapan tahun lalu"),
    ]
    nama = {k.nama for k in P.dari_hasil(hasil)}
    assert {"gempa bumi", "tsunami", "hujan & awan"} & nama


def test_artikel_wikipedia_masuk_kandidat_tanpa_angka():
    hasil = [
        Hasil("wiki_top", WIKI, "top", "Tsunami", metrik=9000),
        Hasil("tren_google", TREN, "q", "12345 aneh", metrik=5),
    ]
    nama = {k.nama for k in P.dari_hasil(hasil)}
    assert "tsunami" in nama and "12345 aneh" not in nama


def test_ringkas_laporan_menandai_bintang():
    daftar = P.dari_hasil([Hasil("saran_google", SARAN, "q", "kenapa jamur tumbuh cepat")])
    baris = P.ringkas(daftar)
    assert any(b.rstrip().endswith("*") or " * " in b for b in baris)
    assert any(b.startswith("- * =") for b in baris)


def test_perluas_dari_registri():
    assert "kenapa tsunami surut" in P.perluas_dari_registri("tsunami")
    assert P.perluas_dari_registri("topik_tidak_ada") == []
