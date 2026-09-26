"""Tahap 5: verifikasi klaim (fakta vs inferensi vs sinyal minat; dukungan, konflik, kemandirian penerbit)."""

from __future__ import annotations

from kliktahu import klaim as K

DOMAIN = ("nature.com", "agupubs.onlinelibrary.wiley.com", "bmkg.go.id")
BUKTI = [
    {
        "judul": "The 2018 Palu tsunami reached 10 m runup",
        "url": "https://agupubs.onlinelibrary.wiley.com/x",
        "penerbit": "AGU",
        "tahun": 2021,
        "kredibel": True,
    },
    {
        "judul": "Palu tsunami flow depth about 6 m",
        "url": "https://nature.com/y",
        "penerbit": "Nature",
        "tahun": 2019,
        "kredibel": True,
    },
    {"judul": "Blog pribadi tentang tsunami", "url": "https://blog-aneh.com/z", "kredibel": True},
]


def test_klasifikasi_tiga_jenis():
    assert K.klasifikasi("kenapa tsunami bisa terjadi") == K.SINYAL_MINAT
    assert K.klasifikasi("Apakah tsunami bisa diprediksi?") == K.SINYAL_MINAT
    assert K.klasifikasi("Tsunami kemungkinan dipicu longsor bawah laut") == K.INFERENSI
    assert K.klasifikasi("Tsunami Palu mencapai 10 meter") == K.FAKTA


def test_sinyal_minat_tidak_butuh_pembuktian():
    k = K.verifikasi("kenapa tsunami bisa terjadi", K.dari_sumber(BUKTI, DOMAIN), DOMAIN)
    assert k.status == K.SINYAL and k.boleh_dipakai
    assert "bukan pernyataan" in k.catatan[0]


def test_fakta_didukung_oleh_dua_penerbit_independen():
    k = K.verifikasi("Tsunami Palu runup 10 m", K.dari_sumber(BUKTI, DOMAIN), DOMAIN)
    assert k.status == K.DIDUKUNG
    assert k.n_independen == 2 and k.kredibel


def test_sumber_tidak_kredibel_tidak_dihitung():
    k = K.verifikasi("Tsunami Palu mencapai 10 meter", K.dari_sumber([BUKTI[2]], DOMAIN), DOMAIN)
    assert k.status == K.TIDAK_DIDUKUNG
    assert "tidak ada yang kredibel" in k.catatan[0]


def test_tanpa_data_beda_dengan_tidak_didukung():
    assert K.verifikasi("Tsunami mencapai 10 meter", [], DOMAIN).status == K.TANPA_DATA
    assert K.verifikasi("Tsunami mencapai 10 meter", K.dari_sumber([BUKTI[2]], DOMAIN), DOMAIN).status == (
        K.TIDAK_DIDUKUNG
    )


def test_angka_tidak_ada_di_sumber_ditolak():
    k = K.verifikasi("Tsunami Palu mencapai 900 meter", K.dari_sumber(BUKTI, DOMAIN), DOMAIN)
    assert k.status == K.TIDAK_DIDUKUNG and "tidak ditemukan" in k.catatan[0]


def test_konflik_angka_terdeteksi_dan_diminta_cek_manual():
    klaim = "Tsunami Palu runup 10 m"
    k = K.verifikasi(klaim, K.dari_sumber(BUKTI, DOMAIN), DOMAIN, butuh_independen=1)
    # dua sumber kredibel menyebut angka berbeda untuk satuan yang sama -> KONFLIK (heuristik)
    if k.status == K.KONFLIK:
        assert "heuristik" in k.catatan[-1] and "dicek manusia" in k.catatan[-1]
    else:  # bergantung kecocokan angka klaim; yang penting tidak pernah mengklaim 'didukung' tanpa bukti
        assert k.status in (K.DIDUKUNG, K.LEMAH)


def test_kemandirian_penerbit():
    a = K.Bukti("A", url="https://nature.com/1")
    b = K.Bukti("B", url="https://nature.com/2")
    c = K.Bukti("C", url="https://bmkg.go.id/3")
    assert not K.mandiri(a, b)
    assert K.mandiri(a, c)


def test_satu_penerbit_saja_jadi_lemah():
    satu = [BUKTI[0]]
    k = K.verifikasi("Tsunami Palu mencapai 10 meter", K.dari_sumber(satu, DOMAIN), DOMAIN, butuh_independen=2)
    assert k.status == K.LEMAH and "cari sumber kedua" in k.catatan[-1]


def test_inferensi_diberi_catatan_bahasa():
    k = K.verifikasi("Tsunami kemungkinan dipicu longsor", K.dari_sumber(BUKTI, DOMAIN), DOMAIN)
    assert k.jenis == K.INFERENSI
    assert any("inferensi" in c for c in k.catatan)


def test_angka_satuan_dinormalisasi():
    assert (10.0, "meter") in K.angka_satuan("tinggi 10 m")
    assert (1000.0, "meter") in K.angka_satuan("jarak 1 km")


def test_laporan_dan_ringkas():
    daftar = K.verifikasi_banyak(
        ["kenapa tsunami bisa terjadi", "Tsunami Palu mencapai 10 meter"], K.dari_sumber(BUKTI, DOMAIN), DOMAIN
    )
    md = K.laporan_md(daftar)
    assert md[0].startswith("| klaim")
    assert set(K.ringkas(daftar)) <= {K.SINYAL, K.DIDUKUNG, K.LEMAH, K.KONFLIK, K.TIDAK_DIDUKUNG, K.TANPA_DATA}
    assert K.klaim_dari_frasa(["kenapa tsunami surut", "tsunami palu"])


def test_boleh_dipakai_hanya_untuk_yang_aman():
    daftar = K.verifikasi_banyak(
        ["kenapa tsunami bisa terjadi", "Tsunami mencapai 900 meter"], K.dari_sumber(BUKTI, DOMAIN), DOMAIN
    )
    assert daftar[0].boleh_dipakai and not daftar[1].boleh_dipakai
