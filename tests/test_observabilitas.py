"""Tahap 12: jejak audit & observabilitas (run id, tahap, status sumber, kuota, kegagalan; TANPA rahasia)."""

from __future__ import annotations

import datetime as dt
import json
import pathlib

from kliktahu import kesegaran as G
from kliktahu import observabilitas as O

UTC = dt.UTC


def test_redaksi_url_dan_teks():
    assert "ABC123" not in O.redaksi_url("https://api.x.com/a?key=ABC123&q=1")  # nilai kunci disembunyikan
    assert "u:p@" not in O.redaksi_url("https://u:p@x.com/a")
    assert "SECRETVALUE" not in O.redaksi("token: SECRETVALUE lalu selesai")
    assert O.redaksi({"key": "abc", "nama": "tsunami"})["key"] == "<rahasia>"


def test_jejak_mencatat_tahap_dan_durasi(tmp_path):
    j = O.Jejak(nama="uji")
    with j.tahap("kumpulkan", kueri="tsunami"):
        j.pakai("saran_google", 3)
    j.sumber(G.status_sumber("saran", dt.datetime.now(UTC), None, None, "saran_google", dari_jaringan=True))
    j.putus(topik="tsunami", skor=71.2)
    j.tutup()
    r = j.ringkas()
    assert r["permintaan"] == 3 and r["durasi_detik"] >= 0
    assert r["status_sumber"]["saran"] == G.LIVE
    assert r["keputusan"]["topik"] == "tsunami"
    assert any(p.jenis == "mulai.kumpulkan" for p in j.peristiwa)
    assert any(p.jenis == "selesai.kumpulkan" for p in j.peristiwa)


def test_jejak_mencatat_galat_tanpa_menghentikan():
    j = O.Jejak()
    try:
        with j.tahap("momen"):
            raise ConnectionError("timeout")
    except ConnectionError:
        pass
    r = j.ringkas()
    assert r["galat"] and "timeout" in r["galat"][0]["galat"]
    assert "GAGAL" in "\n".join(j.tabel_md())


def test_kuota_dan_biaya():
    j = O.Jejak()
    j.pakai("pesaing_youtube", 2)  # 100 unit per panggilan
    j.pakai("saran_google", 5)
    assert j.ringkas()["biaya_unit"] == 200.0
    assert j.ringkas()["kuota_per_sumber"]["saran_google"] == 5


def test_audit_trail_jsonl_append(tmp_path):
    p = tmp_path / "audit.jsonl"
    j1 = O.Jejak(nama="satu")
    j1.catat("uji", url="https://x.com/a?key=RAHASIA")
    j1.tulis(p)
    j2 = O.Jejak(nama="dua")
    j2.tulis(p)
    baris = p.read_text(encoding="utf-8").strip().splitlines()
    assert len(baris) == 3  # 1 ringkasan + 1 peristiwa (run 1) + 1 ringkasan (run 2)
    assert "RAHASIA" not in p.read_text(encoding="utf-8")
    muat = [json.loads(b) for b in baris]
    assert muat[0]["run"]["nama"] == "satu" and muat[-1]["run"]["nama"] == "dua"


def test_keyakinan_data_ikut_ringkasan():
    j = O.Jejak()
    j.banyak_sumber(
        [
            G.status_sumber("saran", dt.datetime.now(UTC), None, None, "saran_google", dari_jaringan=True),
            G.status_sumber("momen", None, None, None, "momen_bmkg", catatan="host diblokir"),
        ]
    )
    r = j.ringkas()
    assert 0 < r["keyakinan_data"] < 1.0
    assert len(r["status_sumber"]) == 2


def test_jumlah_permintaan_konsisten_antara_header_dan_jejak():
    """REGRESI (2026-09-26): pencatat kumulatif `pencari.pakai` dicatat dua kali (per kandidat
    dan di akhir), sehingga laporan menulis 203 permintaan di jejak padahal yang benar 111."""
    import datetime as _dt
    import re as _re

    from kliktahu import analisis

    h = analisis.jalankan("kenapa tsunami", mode="uji", hari=_dt.date(2026, 9, 25), log=lambda s: None)
    md = pathlib.Path(h["laporan"]).read_text(encoding="utf-8")
    angka = _re.findall(r"(\d+) permintaan", md)
    assert len(set(angka)) == 1, f"jumlah permintaan tidak konsisten di laporan: {angka}"
    assert int(angka[0]) == h["permintaan"]
