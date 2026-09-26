"""Orkestrator analisis.py + CLI (`cari`, `analisis`, `evaluasi`) - rantai tahap 1-12."""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pytest

from kliktahu import analisis
from kliktahu import evaluasi as E

HARI = dt.date(2026, 9, 25)


@pytest.fixture()
def hasil():
    return analisis.jalankan("kenapa gunung meletus", mode="uji", hari=HARI, log=lambda s: None)


def test_rantai_lengkap_menghasilkan_topik_dan_metadata(hasil):
    assert hasil["topik"] == "gunung berapi"
    assert hasil["pilar"] == "bumi"
    assert hasil["skor"] and 0 <= hasil["skor"]["skor"] <= 100
    md = hasil["metadata"]
    assert len(md["judul"]) == 3 and md["hashtag"] and md["tag_karakter"] <= 500
    assert md["deskripsi"].isascii() and "Sumber:" in md["deskripsi"]


def test_metadata_topik_bencana_tanpa_sensasi(hasil):
    teks = " ".join(hasil["metadata"]["judul"] + [hasil["metadata"]["deskripsi"]]).lower()
    assert "bikin kaget" not in teks and "ngeri" not in teks
    assert any("BMKG" in p or "PVMBG" in p for p in hasil["peringatan"])


def test_status_sumber_dan_jejak_ada(hasil):
    assert hasil["status"] and {s["jenis"] for s in hasil["status"]} >= {"saran", "ilmiah", "momen"}
    assert hasil["permintaan"] > 0 and hasil["detik"] > 0
    assert hasil["laporan"] and "ANALISIS.md" in hasil["laporan"]


def test_cakupan_kueri_membatasi_keputusan(hasil):
    """kandidat dari artikel/momen yang tidak disebut kueri tidak boleh menang."""
    assert hasil["topik"] in hasil["cakupan"]
    assert hasil["sampingan"] and all(s["nama"] != hasil["topik"] for s in hasil["sampingan"])


def test_laporan_markdown_berisi_bagian_wajib(hasil):
    teks = Path(hasil["laporan"]).read_text(encoding="utf-8")
    for bagian in (
        "# ANALISIS MENDALAM",
        "## Keputusan",
        "## Kandidat topik",
        "## Kesegaran sumber",
        "## Metadata draf",
        "## Jejak run",
    ):
        assert bagian in teks


def test_kandidat_diluar_registri_tetap_dilaporkan():
    h = analisis.jalankan("kenapa jamur tumbuh di kamar mandi", mode="uji", hari=HARI, log=lambda s: None)
    assert h["kandidat"]
    assert any(not k["di_registri"] for k in h["kandidat"]) or h["topik"]


def test_analisis_tema_tertentu():
    h = analisis.jalankan("kenapa tsunami surut", mode="uji", hari=HARI, tema="tsunami", log=lambda s: None)
    assert h["topik"] == "tsunami"


def test_evaluasi_offline_semua_kasus_lulus():
    metrik, ringkasan = E.jalankan_offline(hari=HARI, log=lambda s: None)
    assert ringkasan["n"] >= 3 and ringkasan["lulus"] == ringkasan["n"]
    assert ringkasan["rata"]["relevansi"] >= E.AMBANG["relevansi"]
    assert metrik[0].biaya["permintaan"] > 0


def test_evaluasi_live_ditolak_tanpa_izin(monkeypatch):
    monkeypatch.setenv("KLIKTAHU_LIVE", "1")
    with pytest.raises(ValueError, match="izin"):
        E.jalankan_live(izin=False)
    monkeypatch.delenv("KLIKTAHU_LIVE")
    with pytest.raises(ValueError, match="KLIKTAHU_LIVE"):
        E.jalankan_live(izin=True)


def test_penilaian_kelengkapan_menangkap_metadata_rusak():
    skor, catatan = E.nilai_kelengkapan({"judul": ["satu"], "deskripsi": "", "hashtag": [], "tag": []})
    assert skor == 0.0 and catatan
    baik = {"judul": ["a", "b", "c"], "deskripsi": "isi", "hashtag": ["#KlikTahu"], "tag": ["x"], "lint_lulus": True}
    assert E.nilai_kelengkapan(baik)[0] == 1.0


# -------------------------------------------------------------------------------------------------- CLI
def _cli(*args: str) -> str:
    r = subprocess.run([sys.executable, "-m", "kliktahu", *args], capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


def test_cli_cari_json():
    out = _cli("cari", "kenapa tsunami", "--maks", "5", "--json")
    d = json.loads(out)
    assert d["kueri"] == "kenapa tsunami" and d["hasil"] and d["status"]


def test_cli_analisis():
    out = _cli("analisis", "kenapa tsunami bisa terjadi", "--abaikan-pustaka")
    assert "KEPUTUSAN:" in out and "Hashtag:" in out and "Tag (" in out


def test_cli_evaluasi(tmp_path):
    out = _cli("evaluasi", "--keluar", str(tmp_path / "EVAL.md"))
    assert "LULUS" in out and (tmp_path / "EVAL.md").exists()


def test_momen_tidak_diklaim_kandidat_yang_hanya_berbagi_satu_kata():
    """REGRESI (2026-09-26): nama kandidat disuntikkan ke momen.tema -> tiap kandidat "punya momen".
    Akibatnya momen Semeru diklaim kandidat 'gunung erebus di antartika semburkan' hanya karena
    sama-sama mengandung kata 'gunung', dan kandidat itu memenangkan keputusan."""
    import datetime as _dt

    from kliktahu import momen as M

    m_semeru = M.Momen(_dt.date(2026, 9, 26), "Gunung Semeru erupsi 08:21 WIB", ["gunung berapi"], "live", "PVMBG", 0.8)
    skor, ev = analisis._skor_momen_kandidat(
        "gunung erebus di antartika semburkan", [m_semeru], _dt.date(2026, 9, 26), 45
    )
    assert ev is None and skor == 0.0
    skor2, ev2 = analisis._skor_momen_kandidat("gunung berapi", [m_semeru], _dt.date(2026, 9, 26), 45)
    assert ev2 is not None and ev2.nama == m_semeru.nama


def test_tema_momen_live_bukan_dari_nama_kandidat():
    """REGRESI: tema momen live diambil dari sumbernya (mentah) atau isi judulnya, BUKAN nama kandidat."""
    data = {
        "diambil": "2026-09-26T12:00:00+07:00",
        "saran": {"google": {"kenapa gunung meletus": ["kenapa gunung meletus ada petir"]}},
        "momen_live": [
            {
                "tanggal": "2026-09-26",
                "nama": "Gunung Semeru erupsi 08:21 WIB",
                "tema": ["gunung berapi"],
                "urgensi": 0.8,
            }
        ],
    }
    h = analisis.jalankan(
        "kenapa gunung meletus",
        mode="agen",
        hari=dt.date(2026, 9, 26),
        agen=data,
        log=lambda s: None,
    )
    assert h["topik"], h.get("peringatan")
    # momen Semeru tidak boleh menempel ke kandidat berita yang tidak terkait
    for kand in h.get("kandidat") or []:
        assert "erebus" not in str(kand).lower()
