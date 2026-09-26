"""Tahap 6: pemilihan niche/topik - skor bisa dijelaskan, keyakinan & rentang jujur, bukan probabilitas sukses."""

from __future__ import annotations

import datetime as dt

from kliktahu import niche as N


def test_bobot_wajib_jumlah_satu():
    assert abs(sum(N.BOBOT_NICHE.values()) - 1.0) < 1e-12
    assert set(N.BOBOT_NICHE) == set(N.URUTAN)


def test_komponen_tanpa_data_netral_dan_menurunkan_keyakinan():
    penuh = N.skor_niche("a", "bumi", N.komponen_dasar(permintaan=0.8, momentum=0.8, waktu=0.0, kecocokan=0.7))
    kosong = N.skor_niche("a", "bumi", N.komponen_dasar(permintaan=0.8, momentum=0.8, waktu=0.0))
    assert penuh.keyakinan > kosong.keyakinan
    assert kosong.x["kecocokan"] == 0.5


def test_rentang_melebar_bila_keyakinan_rendah():
    yakin = N.skor_niche("a", "bumi", N.komponen_dasar(**{k: 0.7 for k in N.BOBOT_NICHE}))
    ragu = N.skor_niche("a", "bumi", N.komponen_dasar(permintaan=0.7))
    assert yakin.keyakinan == 1.0 and ragu.keyakinan < 0.5
    assert (ragu.rentang[1] - ragu.rentang[0]) > (yakin.rentang[1] - yakin.rentang[0])
    assert 0 <= ragu.rentang[0] <= 100 and 0 <= ragu.rentang[1] <= 100


def test_biaya_produksi_masuk_akal_dan_dipakai_terbalik():
    assert N.biaya_produksi(1.0, "shorts") < N.biaya_produksi(0.1, "shorts")  # sulit divisualkan = mahal
    assert N.biaya_produksi(1.0, "shorts") < N.biaya_produksi(1.0, "long")  # 10 bab = mahal
    assert N.biaya_produksi(1.0, "shorts") < N.biaya_produksi(1.0, "shorts", ada_sumber=False)
    assert N.biaya_produksi(1.0, "shorts") < N.biaya_produksi(1.0, "shorts", di_registri=False)
    assert 0.0 <= N.biaya_produksi(0.0, "long", ada_sumber=False, di_registri=False, butuh_riset_lanjut=True) <= 1.0


def test_komponen_dipakai_semua_dan_celah_bisa_dikeluarkan():
    komponen = N.komponen_dasar(**{k: 0.6 for k in N.BOBOT_NICHE})
    h = N.skor_niche("tsunami", "bumi", komponen)
    h2 = N.skor_niche("tsunami", "bumi", komponen, tanpa=("celah",))
    assert h.skor == h2.skor  # komponen netral -> peringkat tidak berubah
    assert h2.tanpa == ("celah",)
    assert "tidak dipakai" in "\n".join(N.jelaskan(h2))


def test_penjelasan_menyebut_bukan_probabilitas():
    h = N.skor_niche("tsunami", "bumi", N.komponen_dasar(permintaan=0.9, waktu=0.8))
    teks = "\n".join(N.jelaskan(h))
    assert "BUKAN peluang" in teks and "permintaan" in teks


def test_pilih_momen_bisa_mendahului_juara_skor_dengan_alasan():
    kuat = N.skor_niche("bintang", "antariksa", N.komponen_dasar(**{k: 0.8 for k in N.BOBOT_NICHE}))
    momen = N.skor_niche("tsunami", "bumi", N.komponen_dasar(**{k: 0.75 for k in N.BOBOT_NICHE}))
    hari = dt.date(2026, 9, 26)
    pilih, alasan = N.pilih([kuat, momen], hari, {"tsunami": dt.date(2026, 9, 28)}, batas_selisih=8.0)
    assert pilih is not None and pilih.nama == "tsunami"
    assert any("Didahulukan" in a for a in alasan)


def test_pilih_tidak_mendahului_bila_selisih_terlalu_besar():
    kuat = N.skor_niche("bintang", "antariksa", N.komponen_dasar(**{k: 1.0 for k in N.BOBOT_NICHE}))
    lemah = N.skor_niche("tsunami", "bumi", N.komponen_dasar(**{k: 0.1 for k in N.BOBOT_NICHE}))
    pilih, _ = N.pilih([kuat, lemah], dt.date(2026, 9, 26), {"tsunami": dt.date(2026, 9, 28)}, batas_selisih=8.0)
    assert pilih is not None and pilih.nama == "bintang"


def test_peta_pilar_dan_urutan():
    daftar = [
        N.skor_niche("tsunami", "bumi", N.komponen_dasar(**{k: 0.8 for k in N.BOBOT_NICHE})),
        N.skor_niche("gempa bumi", "bumi", N.komponen_dasar(**{k: 0.6 for k in N.BOBOT_NICHE})),
        N.skor_niche("bintang", "antariksa", N.komponen_dasar(**{k: 0.9 for k in N.BOBOT_NICHE})),
    ]
    peta = N.peta_pilar(daftar)
    assert peta[0]["pilar"] == "antariksa" and peta[1]["pilar"] == "bumi"
    assert [h.nama for h in N.urutkan(daftar)][0] == "bintang"
    assert N.tabel_md(daftar)[0].startswith("| # |")


def test_biaya_dari_tema_registri():
    assert N.biaya_dari_tema("tsunami") < N.biaya_dari_tema("topik_tidak_ada")
    assert 0.0 <= N.biaya_dari_tema("otak") <= 1.0
