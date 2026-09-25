"""klien HTTP (retry, Retry-After, offline, cache, rahasia), pengurai sumber, mesin riset (uji & agen)."""

from __future__ import annotations

import datetime as dt
import json

import httpx
import pytest

from kliktahu.db import DB
from kliktahu.riset import http as H
from kliktahu.riset import mesin
from kliktahu.riset import sumber as SB

HARI = dt.date(2026, 9, 25)


def _klien(k, handler, **kw):
    tidur: list[float] = []
    kl = H.KlienRiset(
        k,
        transport=httpx.MockTransport(handler),
        cache=kw.pop("cache", None),
        pakai_cache=False,
        tidur=tidur.append,
        **kw,
    )
    return kl, tidur


def test_http_coba_ulang_503_lalu_hormati_retry_after(k):
    n = {"x": 0}

    def h(req):
        n["x"] += 1
        if n["x"] == 1:
            return httpx.Response(503)
        if n["x"] == 2:
            return httpx.Response(429, headers={"retry-after": "7"})
        return httpx.Response(200, json=["q", ["kenapa pelangi melengkung"]])

    kl, tidur = _klien(k, h)
    assert SB.saran(kl, "kenapa pelangi") == ["kenapa pelangi melengkung"]
    assert n["x"] == 3 and 7.0 in tidur and kl.stat["coba_ulang"] == 2


def test_http_host_diblokir_jadi_offline_cepat(k):
    def h(req):
        raise httpx.ConnectError("TLS/SSL connection has been closed (EOF)")

    kl, _ = _klien(k, h)
    with pytest.raises(H.Offline):
        SB.saran(kl, "kenapa a")
    with pytest.raises(H.Offline):  # tanpa mencoba lagi
        SB.saran(kl, "kenapa b")
    assert "suggestqueries.google.com" in kl.host_mati and kl.stat["gagal_cepat"] == 1


def test_http_cache_dan_kunci_api_tidak_ikut_kunci(k, tmp_path):
    n = {"x": 0}

    def h(req):
        n["x"] += 1
        return httpx.Response(200, json={"ok": True})

    kl, _ = _klien(k, h, cache=H.Cache(tmp_path / "c.sqlite"))
    r1 = kl.get("https://www.googleapis.com/youtube/v3/search", {"q": "a", "key": "RAHASIA-1"})
    r2 = kl.get("https://www.googleapis.com/youtube/v3/search", {"q": "a", "key": "RAHASIA-2"})
    assert n["x"] == 1 and r2.dari_cache and "RAHASIA" not in r1.url
    isi = (tmp_path / "c.sqlite").read_bytes()
    assert b"RAHASIA" not in isi


def test_http_rate_limit_per_host(k):
    jam = {"t": 0.0}
    kl = H.KlienRiset(
        k,
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=[])),
        pakai_cache=False,
        tidur=lambda s: jam.__setitem__("t", jam["t"] + s),
        jam=lambda: jam["t"],
    )
    for _ in range(4):
        kl.get("https://contoh.id/a")
    assert jam["t"] == pytest.approx(3 * k.riset.jeda_min_detik)


def test_pengurai_format_asli():
    assert SB.urai_saran('["kenapa",["kenapa langit biru","kenapa laut asin"],[],{}]') == [
        "kenapa langit biru",
        "kenapa laut asin",
    ]
    assert SB.urai_saran('window.google.ac.h(["q",[["a b",0,[512]]]])') == ["a b"]
    assert SB.urai_saran("<html>diblokir</html>") == []
    w = SB.hitung_wiki([100] * 53 + [400] * 7)
    assert w["views60"] == 100 * 53 + 400 * 7 and w["lonjakan_z"] > 2
    assert SB.wiki_dari_bulanan({"2026-07": 1069, "2026-08": 1112, "2026-09": 629}, 24)["tren"] == pytest.approx(
        (629 * 30 / 24 + 100) / (1112 + 100), rel=1e-3
    )
    sepi = SB.wiki_dari_bulanan({"2026-08": 21, "2026-09": 60}, 24)  # 21 -> 75/30 hari: bukan lonjakan nyata
    ramai = SB.wiki_dari_bulanan({"2026-08": 813, "2026-09": 2176}, 24)  # Gunung berapi Sep 2026
    assert sepi["tren"] < 1.5 < 3.0 < ramai["tren"] and ramai["lonjakan_z"] == 6.0
    rss = (
        "<rss><channel><item><title>A</title><link>u</link><pubDate>Thu, 24 Sep 2026 10:00:00 GMT</pubDate>"
        '<source url="x">Kompas</source></item><item><title>B</title><pubDate>Mon, 07 Sep 2026 10:00:00 GMT'
        "</pubDate></item></channel></rss>"
    )
    b = SB.hitung_berita(SB.urai_rss(rss), dt.datetime(2026, 9, 25, 9, tzinfo=dt.UTC))
    assert b["n7"] == 1 and b["n28"] == 2
    tr = SB.urai_tren(
        '<rss xmlns:ht="https://trends.google.com/trending/rss"><channel><item><title>gempa</title>'
        "<ht:approx_traffic>20,000+</ht:approx_traffic></item></channel></rss>"
    )
    assert tr[0]["traffic"] == 20000 and SB.angka_traffic("2K+") == 2000
    assert SB.durasi_iso("PT1M5S") == 65 and SB.durasi_iso("P1DT1H") == 90000
    swpc_lama = json.dumps(
        [["time_tag", "kp", "observed", "noaa_scale"], ["2026-09-26 00:00:00", "7.33", "predicted", "G3"]]
    )
    swpc_baru = json.dumps([{"time_tag": "2026-09-26T00:00:00", "kp": 8.0, "observed": "predicted"}])
    assert SB.urai_swpc(swpc_lama, HARI)[0].urgensi == 0.9 and SB.urai_swpc(swpc_baru, HARI)[0].urgensi == 1.0
    assert SB.kredibel("https://science.nasa.gov/x", ("nasa.gov",)) and not SB.kredibel(
        "https://nasa.gov.evil.com", ("nasa.gov",)
    )


def test_mesin_uji_menyeluruh(riset_uji):
    h, d, tmp = riset_uji
    assert h.statistik["tema_dianalisis"] == 62 and not h.statistik["host_offline"]
    assert all(v.startswith("ok") for v in h.statistik["sumber"].values()), h.statistik["sumber"]
    assert h.keputusan and h.keputusan.status in ("segar", "long")
    tema = [r["tema"] for r in h.baris]
    assert "kucing" not in tema and "petir" not in tema  # sudah dibahas -> tidak diperingkat
    assert all(0 <= r["v7_peluang"] <= 100 and 0 <= r["keyakinan"] <= 1 for r in h.baris)
    semua = json.dumps([s["data"] for s in d.daftar("snapshot_pencarian")])
    assert "kentut" not in semua and "keringat" not in semua  # BLOKIR dibuang dari data
    for p in h.metadata.values():
        assert not any("lgbt" in x for x in p.judul + p.tag)  # sensitif tidak masuk metadata
        assert p.lulus, p.galat
    assert (tmp / "lap" / "RISET.md").read_text().count("KEPUTUSAN") == 1
    assert len(d.daftar("skor", "run_id = ?", (h.run_id,))) == len(h.baris)


def test_mesin_velocity_run_kedua(tmp_path):
    d = DB(tmp_path / "v.db")
    mesin.jalankan(
        "uji", HARI - dt.timedelta(days=1), db=d, folder_laporan=tmp_path / "l", ekspor=False, log=lambda s: None
    )
    d.con.execute("UPDATE run_riset SET mode = 'online'")  # anggap run nyata kemarin
    h2 = mesin.jalankan("uji", HARI, db=d, folder_laporan=tmp_path / "l", ekspor=False, log=lambda s: None)
    assert h2.statistik["velocity_dari_run"] == 1
    assert all(r["velocity"] is not None for r in h2.baris)


def test_mesin_agen(tmp_path):
    data = {
        "diambil": "2026-09-25T15:00:00+07:00",
        "alat": "uji",
        "saran": {
            "google": {
                "kenapa pelangi": [
                    "kenapa pelangi melengkung",
                    "kenapa pelangi muncul setelah hujan",
                    "kenapa pelangi jadi lambang lgbt",
                    "kenapa pelangi warna warni",
                ],
                "kenapa cegukan": ["kenapa cegukan tidak berhenti", "kenapa cegukan terjadi"],
            },
            "youtube": {"kenapa pelangi": ["kenapa pelangi melengkung"]},
        },
        "wiki": {
            "pelangi": {
                "judul": "Pelangi",
                "bulanan": {"2026-07": 1069, "2026-08": 1112, "2026-09": 629},
                "hari_bulan_ini": 24,
            }
        },
        "sumber_ilmiah": {
            "pelangi": [
                {"judul": "How rainbows form", "url": "https://www.noaa.gov/x", "penerbit": "NOAA", "tahun": 2023}
            ]
        },
    }
    f = tmp_path / "agen.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    d = DB(tmp_path / "a.db")
    h = mesin.jalankan("agen", HARI, db=d, agen=f, folder_laporan=tmp_path / "l", ekspor=False, log=lambda s: None)
    assert {r["tema"] for r in h.baris} == {"pelangi", "cegukan"} and len(h.statistik["tema_tanpa_data"]) == 60
    top = {r["tema"]: r for r in h.baris}["pelangi"]
    assert top["wiki"]["views60"] > 0 and top["frasa_sensitif"] == ["kenapa pelangi jadi lambang lgbt"]
    assert d.sumber_topik(d.topik("pelangi")["id"])[0]["kredibel"]
