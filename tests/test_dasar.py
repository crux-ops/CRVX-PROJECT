"""kanal.toml, teks, skema (turunan tidak melenceng), basis data (DAL, blokir, FTS, ekspor/impor)."""

from __future__ import annotations

import sqlite3

import pytest

from kliktahu import kanal, skema, teks
from kliktahu.db import DB, DataDiblokir


def test_kanal_sah_dan_aturan_keras(k):
    assert k.nama == "KlikTahu" and k.shorts_terakhir == 49 and k.long_terakhir == 2
    for w in ("kentut", "ngiler", "keringat", "bau badan"):
        assert w in k.aturan.blokir
    assert k.aturan.subtitle is False and k.aturan.musik is False
    assert k.metadata.maks_tag_karakter <= 500


@pytest.mark.parametrize(
    "ubah, pesan",
    [
        (lambda d: d["aturan"].__setitem__("blokir", ["ngiler", "keringat", "bau badan"]), "kentut"),
        (lambda d: d["aturan"].__setitem__("musik", True), "musik"),
        (lambda d: d["riset"].__setitem__("env_youtube_key", "AIzaSyBOCOR-kunci-asli"), "NAMA variabel"),
        (lambda d: d["metadata"].__setitem__("maks_tag_karakter", 600), "batas keras"),
        (lambda d: d["jadwal"].__setitem__("slot_wib", ["25:00"]), "HH:MM"),
        (lambda d: d["pilar"].pop("misteri"), "keenam pilar"),
        (lambda d: d["riset"].__setitem__("pesaing", "tidak"), "pesaing harus true/false"),
    ],
)
def test_kanal_menolak_konfigurasi_salah(ubah, pesan):
    import tomllib

    d = tomllib.loads((kanal.ROOT / "kanal.toml").read_text(encoding="utf-8"))
    ubah(d)
    with pytest.raises(kanal.KanalError, match=pesan):
        kanal.dari_dict(d)


def test_teks_blokir_sensitif_ascii():
    b = ("kentut", "iler", "keringat", "bau badan")
    assert teks.diblokir("Kenapa BERKERINGAT saat tidur?", b)  # potongan kata (>= 6 huruf)
    assert teks.diblokir("apakah iler itu", b) and not teks.diblokir("diler motor bekas", b)  # kata pendek = utuh
    assert teks.sensitif("kenapa pelangi jadi lambang lgbt", ["lgbt"])
    assert (
        teks.ascii_saja("Kenapa langit biru? \u2014 \u201cfakta\u201d \U0001f680 caf\u00e9")
        == 'Kenapa langit biru? - "fakta" cafe'
    )
    assert teks.hashtag("hari tanpa bayangan") == "#HariTanpaBayangan"
    assert teks.panjang_tag_youtube(["pelangi", "kenapa pelangi"]) == 7 + 16 + 1
    assert teks.kata_utuh_semua("ai", "kecerdasan ai") and not teks.kata_utuh_semua("ai", "baterai")


def test_skema_turunan_sinkron_dan_ddl_berjalan():
    assert skema.cek() == [], "jalankan: python3 -m kliktahu skema tulis"
    con = sqlite3.connect(":memory:")
    con.executescript(skema.ddl_sqlite())
    nama = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {t.nama for t in skema.TABEL} <= nama
    pg = skema.ddl_postgres()
    assert pg.count("ENABLE ROW LEVEL SECURITY") == len(skema.TABEL) and "jsonb" in pg and "timestamptz" in pg
    ts = skema.typescript()
    assert "export interface Database" in ts and "Relationships: []" in ts and 'export type Pilar = "tubuh"' in ts


def test_db_crud_fk_check_dan_kode_episode(db):
    db.seed_tema()
    assert db.topik("pelangi")["pilar"] == "bumi"
    assert db.kode_berikut("shorts") == "Ep50" and db.kode_berikut("long") == "Long03"
    assert db.tambah_episode("shorts", "pelangi", judul="Kenapa Pelangi Melengkung?") == "Ep50"
    assert db.kode_berikut("shorts") == "Ep51"
    with pytest.raises(sqlite3.IntegrityError):
        db.sisip("topik", {"slug": "x", "nama": "x", "pilar": "bukan_pilar"})  # CHECK pilihan
    with pytest.raises(sqlite3.IntegrityError):
        db.sisip("episode", {"kode": "Ep99", "format": "shorts", "topik_id": 99999})  # foreign key
    db.ubah_episode("Ep50", status="rilis")
    assert db.topik("pelangi")["status"] == "dibahas"  # rilis -> topik dibahas
    hasil = db.cari("pelangi melengkung")
    assert hasil and hasil[0]["kunci"] in ("Ep50", "pelangi")


def test_db_blokir_ditolak_dan_dibuang(db):
    with pytest.raises(DataDiblokir):
        db.upsert_topik("kentut", "kentut", "tubuh")
    rid = db.mulai_run("uji")
    assert db.simpan_snapshot(rid, "google_saran", "kenapa kentut bau", {"items": ["a"]}) is None
    sid = db.simpan_snapshot(
        rid,
        "google_saran",
        "kenapa pelangi",
        {"items": ["kenapa pelangi melengkung", "kenapa pelangi keringat dingin"]},
    )
    assert db.ambil("snapshot_pencarian", id=sid)["data"]["items"] == ["kenapa pelangi melengkung"]
    db.con.execute("INSERT INTO topik (slug, nama, pilar) VALUES ('ngiler', 'ngiler malam', 'tubuh')")
    assert db.bersihkan_blokir()["topik"] == 1


def test_db_ekspor_impor_bolak_balik(db, tmp_path):
    db.seed_tema()
    db.tambah_episode("long", "aurora", judul="Aurora dari nol")
    n = db.ekspor(tmp_path / "ek")
    d2 = DB(tmp_path / "baru.db")
    m = d2.impor(tmp_path / "ek")
    assert m == n and d2.episode("Long03")["judul"] == "Aurora dari nol"
    assert DB(tmp_path / "baru.db").versi == skema.VERSI_SKEMA  # migrasi idempoten saat dibuka ulang


def test_skema_cek_toleran_libm_tapi_ketat_masukan():
    import json

    d = json.loads((skema.ROOT / skema.FIXTURE_PARITAS).read_text(encoding="utf-8"))
    e = json.loads(json.dumps(d))
    e["kasus"][0]["out"] = e["kasus"][0]["out"] * (1 + 1e-15)  # beda digit terakhir (libm lintas platform)
    f = json.loads(json.dumps(d))
    f["kasus"][0]["in"][0]["jml"] += 1  # masukan berubah = melenceng sungguhan
    assert skema._sama_toleran(e, d) and not skema._sama_toleran(f, d)


def test_apostrof_tidak_meloloskan_kata_sensitif(k):
    assert teks.norm("Ka'bah") == "kabah" and teks.norm("Jum\u2019at") == "jumat"
    assert teks.sensitif("kenapa pesawat tidak boleh melewati ka'bah", k.aturan.sensitif)
