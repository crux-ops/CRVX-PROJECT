"""Tahap 7-10: judul, deskripsi, hashtag, tag (satu implementasi di kliktahu/meta/, dipakai metadata.py)."""

from __future__ import annotations

import pytest

from kliktahu import kanal as K
from kliktahu import metadata as M
from kliktahu.meta import deskripsi as D
from kliktahu.meta import hashtag as H
from kliktahu.meta import judul as J
from kliktahu.meta import tag as T


@pytest.fixture()
def k() -> K.Kanal:
    return K.muat()


# -------------------------------------------------------------------------------------------------- tahap 7
def test_judul_beragam_sudut_bukan_pengulangan(k):
    frasa = ["kenapa tsunami bisa terjadi", "kenapa tsunami surut", "kenapa tsunami cepat", "kenapa tsunami malam"]
    judul, skor, _w = J.buat(frasa, "tsunami", "shorts", k, kata_kunci="kenapa tsunami bisa terjadi")
    assert len(judul) == 3 and all(j.isascii() for j in judul)
    assert len({J._inti_judul(j) for j in judul}) == 3  # tiga sudut berbeda
    for a, b in J.duplikat(judul):
        pytest.fail(f"judul ganda: {a} / {b}")


def test_judul_ditolak_bila_diblokir_sensitif_atau_terlalu_panjang(k):
    buruk = J.skor_judul(
        "Kenapa Kentut Bisa Terjadi Setiap Hari? Ini Jawabannya", "kenapa kentut", "kentut", "shorts", [], k
    )
    assert buruk.skor == -100.0
    panjang = J.skor_judul("X" * 120, "x", "x", "shorts", [], k)
    assert panjang.skor == -100.0
    sensitif = J.skor_judul("Kenapa Tsunami Menurut Islam? Penjelasan", "kenapa tsunami", "tsunami", "shorts", [], k)
    assert sensitif.skor == -100.0


def test_judul_angka_tanpa_bukti_diperingatkan(k):
    bukti = [{"judul": "Tsunami runup 7 meter", "penerbit": "AGU"}]
    j = "Kenapa Tsunami Bisa Mencapai 900 Meter? Ini Jawabannya"
    n = J.skor_judul(j, "kenapa tsunami", "tsunami", "shorts", [], k, bukti=bukti)
    assert any("900" in p and "bukti" in p for p in n.peringatan)
    n2 = J.skor_judul(
        "Kenapa Tsunami Bisa Mencapai 7 Meter? Ini Jawabannya",
        "kenapa tsunami",
        "tsunami",
        "shorts",
        [],
        k,
        bukti=bukti,
    )
    assert not any("bukti" in p for p in n2.peringatan)


def test_judul_campuran_bahasa_asing_diperingatkan(k):
    n = J.skor_judul("Why The Tsunami Happened And What Is The Truth", "kenapa tsunami", "tsunami", "shorts", [], k)
    assert any("bahasa asing" in p for p in n.peringatan)


def test_judul_tetap_episode_dinilai_tanpa_diganti(k):
    tetap = ["Kenapa Tsunami Bisa Terjadi?", "Tanda Tsunami yang Wajib Kamu Tahu", "Sains di Balik Tsunami Palu"]
    judul, skor, _ = J.buat(["kenapa tsunami"], "tsunami", "shorts", k, kata_kunci="kenapa tsunami", judul_tetap=tetap)
    assert judul == tetap[:3] and len(skor) == 3


def test_mode_hormat_topik_bencana_membuang_templat_sensasi(k):
    frasa = ["kenapa tsunami bisa terjadi"]
    judul, _s, _w = J.buat(frasa, "tsunami", "shorts", k, kata_kunci="kenapa tsunami", hormat=True)
    assert all("Bikin Kaget" not in j for j in judul)


# -------------------------------------------------------------------------------------------------- tahap 8
def test_deskripsi_setia_pada_bukti():
    class C:
        teks = "Tsunami Palu mencapai 10 meter"
        status = "didukung"
        jenis = "fakta"

    class Buruk:
        teks = "Tsunami disebabkan oleh paus raksasa"
        status = "tidak_didukung"
        jenis = "fakta"

    class Tanya:
        teks = "kenapa tsunami bisa terjadi"
        status = "sinyal"
        jenis = "sinyal_minat"

    ringkas = D.ringkasan_dari_klaim([C(), Buruk(), Tanya()], "tsunami")
    assert "10 meter" in ringkas and "paus" not in ringkas and "kenapa" not in ringkas


def test_deskripsi_lengkap_dengan_provenance_dan_tanggal(k):
    sumber = [{"judul": "Palu tsunami", "penerbit": "AGU", "tahun": 2021, "url": "https://doi.org/10.1000/x"}]
    d = D.buat_deskripsi(
        "kenapa tsunami bisa terjadi",
        "tsunami",
        "tsunami",
        "shorts",
        k,
        bab=[(0.0, "Pertanyaan"), (31.0, "Penyebab")],
        sumber=sumber,
        hashtag=["#KlikTahu"],
        tanggal_riset="2026-09-26",
        status_sumber="saran: LIVE",
    )
    assert d.splitlines()[0].startswith("Kenapa tsunami")
    assert "0:00 Pertanyaan" in d and "0:31 Penyebab" in d
    assert "AGU" in d and "2021" in d
    assert "Tanggal riset: 2026-09-26" in d and "Status sumber" in d
    assert "BMKG" in d  # info resmi topik bencana


def test_deskripsi_kesehatan_wajib_disclaimer(k):
    d = D.buat_deskripsi("kenapa cegukan", "cegukan", "cegukan", "shorts", k, pilar="tubuh")
    assert k.aturan.disclaimer_kesehatan in d
    g = D.lint_deskripsi(d.replace(k.aturan.disclaimer_kesehatan, ""), "shorts", k, False, "tubuh", "kenapa cegukan")
    assert any("kesehatan" in x for x in g)


def test_bab_dari_timeline_menggabung_yang_terlalu_pendek(k):
    konten = {
        "scenes": [
            {"id": "intro", "type": "intro"},
            {"id": "f1", "type": "fact", "badge": "satu"},
            {"id": "f2", "type": "fact", "badge": "dua"},
            {"id": "outro", "type": "outro"},
        ]
    }
    timeline = {
        "scenes": [
            {"id": "intro", "start": 0.0},
            {"id": "f1", "start": 12.0},
            {"id": "f2", "start": 14.0},
            {"id": "outro", "start": 60.0},
        ],
        "total": 100.0,
    }
    bab = D.bab_dari_timeline(konten, timeline)
    assert bab[0][0] == 0.0  # bab pertama selalu 0:00
    assert [b[1] for b in bab] == ["Pertanyaan", "Dua", "Kesimpulan"]  # 'Satu' (2 detik) digabung
    awal = [b[0] for b in bab]
    assert all(b - a >= D.BAB_MIN_DETIK for a, b in zip(awal, [*awal[1:], 100.0]))


# -------------------------------------------------------------------------------------------------- tahap 9
def test_hashtag_relevan_dan_aturan_platform(k):
    tagar, w = H.buat_hashtag("tsunami", "tsunami", "shorts", k)
    assert tagar[0] == "#KlikTahu" and "#Shorts" in tagar and len(tagar) <= k.metadata.maks_hashtag
    assert not w or all("trend-stuffing" not in x for x in w)


def test_hashtag_tak_relevan_diperingatkan():
    w: list[str] = []
    g = H.lint(["#KlikTahu", "#FaktaSains", "#Kpop", "#Shorts"], "shorts", K.muat(), w, konteks=["tsunami"])
    assert not g  # sah menurut aturan platform, tetapi tidak relevan
    assert any("tidak relevan" in x for x in w)


def test_hashtag_lebih_dari_15_ditolak():
    g = H.lint([f"#Tag{i}" for i in range(16)], "shorts", K.muat(), [])
    assert any("mengabaikan SEMUA" in x for x in g)


def test_hashtag_hanya_angka_ditolak():
    g = H.lint(["#12345"], "shorts", K.muat(), [])
    assert any("hanya angka" in x for x in g)


# -------------------------------------------------------------------------------------------------- tahap 10
def test_tag_dari_variasi_pencarian_dan_batas_500(k):
    frasa = [
        f"kenapa tsunami {a} {b} di {c}"
        for a in ("surut", "cepat", "malam", "tinggi")
        for b in ("pantai", "sungai")
        for c in ("selatan", "utara", "barat")
    ]
    tag, w = T.buat_tag("kenapa tsunami bisa terjadi", "tsunami", "tsunami", frasa, k)
    assert tag[0].startswith("kenapa tsunami")  # kata kunci utama di depan
    assert T.panjang(tag) <= k.metadata.maks_tag_karakter
    assert any("tertinggal" in x for x in w)  # jujur: ada calon yang tidak muat


def test_tag_dedup_tidak_memakai_token_set(k):
    tag, _ = T.buat_tag(
        "kenapa gunung meletus",
        "gunung meletus",
        "gunung berapi",
        ["kenapa gunung meletus ada petir", "kenapa gunung meletus keluar petir"],
        k,
    )
    assert len(tag) == len({t for t in tag})
    assert not any("koma" in t for t in tag)


def test_tag_tidak_ada_kata_inti_diperingatkan(k):
    tag, w = T.buat_tag("zzz", "tsunami", "tsunami", [], k)
    assert any("kata inti" in x for x in w) or any("tsunami" in t for t in tag)


def test_tag_penjelasan_jujur(k):
    teks = "\n".join(T.jelaskan(["tsunami", "fakta tsunami"], k))
    assert "TIDAK menjanjikan" in teks


# -------------------------------------------------------------------------------------------------- rakit
def test_metadata_buat_memakai_modul_meta(k):
    p = M.buat(
        "tsunami",
        ["kenapa tsunami bisa terjadi", "kenapa tsunami surut"],
        "shorts",
        k,
        sudut=["kenapa tsunami surut sebelum datang"],
        bukti=[{"judul": "Palu tsunami 10 m", "penerbit": "AGU"}],
        tanggal_riset="2026-09-26",
        status_sumber="saran: LIVE",
    )
    assert len(p.judul) == 3 and p.hashtag and p.tag_karakter <= 500
    assert "Tanggal riset: 2026-09-26" in p.deskripsi
    assert p.lulus or not p.galat  # draf: galat hanya dari aturan keras


def test_metadata_draf_ascii_dan_tiga_judul(k, tmp_path):
    p = M.buat("pelangi", ["kenapa pelangi melengkung"], "shorts", k)
    assert len(p.judul) == 3 and p.deskripsi.isascii() and p.hashtag
    md = M.tulis_md(p, tmp_path / "METADATA.md", "uji")
    d = M.urai_md(md.read_text())
    assert d["judul"] == p.judul and d["tag"] == p.tag and d["hashtag"] == p.hashtag
    g, _w = M.cek_md(md, "shorts", "bumi", k, tema="pelangi")
    assert any("timestamp" in x for x in g)  # draf tanpa timeline -> gerbang render menolak (aturan keras)


def test_nama_pendek_tidak_memotong_jam():
    """REGRESI (2026-09-26): titik dua di JAM ("08:21 WIB") dulu dianggap pemisah penjelasan,
    sehingga nama momen jadi "Gunung Semeru erupsi 08" dan memicu peringatan angka palsu."""
    from kliktahu import momen as M

    n = "Gunung Semeru erupsi 08:21 WIB, kolom letusan ±700 m di atas puncak (PVMBG)"
    assert M.nama_pendek(n) == "Gunung Semeru erupsi 08:21 WIB"
    # pemisah yang benar tetap bekerja
    assert M.nama_pendek("Hari tanpa bayangan: Makassar 11.50 WITA") == "Hari tanpa bayangan"
    assert M.nama_pendek("Peringatan 8 tahun tsunami Palu (gempa M7,5)") == "Peringatan 8 tahun tsunami Palu"


def test_angka_dalam_jam_tidak_dicap_tanpa_bukti():
    """REGRESI: judul yang mengutip jam ("08:21") jangan dilaporkan "angka 08 tanpa bukti"."""
    from kliktahu.meta.judul import angka_tanpa_bukti

    bukti = [{"judul": "Gunung Semeru erupsi 08:21 WIB, kolom letusan 700 m", "penerbit": "PVMBG"}]
    assert angka_tanpa_bukti("Gunung Semeru Erupsi 08:21: Kenapa Gunung Meletus?", bukti) == []
    assert angka_tanpa_bukti("Gunung Meletus 999 Meter?", bukti) == ["999"]
