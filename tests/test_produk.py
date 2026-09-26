"""metadata (buat + lint + MD), pustaka, perencana (+ICS), dasbor, sinkron Bolt/Supabase, CLI."""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from kliktahu import dasbor, perencana, pustaka, sinkron
from kliktahu import metadata as M
from kliktahu.db import DB

HARI = dt.date(2026, 9, 25)
FRASA = [
    "kenapa pelangi melengkung",
    "kenapa pelangi muncul setelah hujan",
    "kenapa pelangi jadi lambang lgbt",
    "kenapa pelangi ada 7 warna",
    "apakah pelangi bisa muncul malam",
    "kenapa pelangi warna warni",
]
KONTEN = {
    "scenes": [
        {"id": "intro", "type": "intro"},
        {"id": "f1", "type": "fact", "badge": "CAHAYA DIBIASKAN"},
        {"id": "f2", "type": "fact", "badge": "SUDUT 42 DERAJAT"},
        {"id": "outro", "type": "outro", "src": "Sumber: NOAA; Met Office"},
    ]
}
TL = {
    "scenes": [
        {"id": "intro", "start": 0},
        {"id": "f1", "start": 7.4},
        {"id": "f2", "start": 31.2},
        {"id": "outro", "start": 140.9},
    ]
}


def test_metadata_final_lulus_dan_patuh(k, tmp_path):
    p = M.buat(
        "pelangi",
        FRASA,
        "shorts",
        k,
        konten=KONTEN,
        timeline=TL,
        final=True,
        sumber=[{"penerbit": "NOAA", "judul": "Rainbows", "url": "https://www.noaa.gov/rainbow", "tahun": 2023}],
    )
    assert p.lulus, p.galat
    assert len(p.judul) == 3 and len({M._inti_judul(j) for j in p.judul}) == 3  # 3 sudut berbeda
    assert p.deskripsi.splitlines()[0] == "Kenapa pelangi melengkung?"  # baris 1 = kata kunci utama
    assert (
        "0:00 Pertanyaan" in p.deskripsi and "0:31 Sudut 42 Derajat" in p.deskripsi and "2:21 Kesimpulan" in p.deskripsi
    )  # 140.9 s dibulatkan
    assert not any("lgbt" in x.lower() for x in p.judul + p.tag + [p.deskripsi])
    assert p.tag_karakter <= 500 and p.deskripsi.isascii() and "#Shorts" in p.hashtag
    md = M.tulis_md(p, tmp_path / "METADATA.md", "Ep50 pelangi")
    g, _ = M.cek_md(md, "shorts", "bumi", k)
    assert g == []
    d = M.urai_md(md.read_text())
    assert d["judul"] == p.judul and d["tag"] == p.tag


def test_metadata_kesehatan_wajib_disclaimer(k):
    p = M.buat("cegukan", ["kenapa cegukan tidak berhenti", "kenapa cegukan terjadi"], "shorts", k)
    assert k.aturan.disclaimer_kesehatan in p.deskripsi
    g = M.lint_deskripsi(
        p.deskripsi.replace(k.aturan.disclaimer_kesehatan, ""), "shorts", k, False, "tubuh", p.judul[0]
    )
    assert any("kesehatan" in x for x in g)


@pytest.mark.parametrize(
    "rusak, pesan",
    [
        (lambda s: s.replace("## 3. Hashtag", "## Hashtag"), "4 blok"),
        (lambda s: s.replace("#FaktaSains", ""), "hashtag wajib"),
        (lambda s: s.replace("0:00 Pertanyaan", "0:05 Pertanyaan"), "0:00"),
        (lambda s: s.replace("## 1. Judul (3 pilihan)\n1. ", "## 1. Judul (3 pilihan)\n1. <b>"), "< atau >"),
        (
            lambda s: s.replace(
                "pelangi,", "pelangi, " + ", ".join(f"tag{i:03d} panjang sekali" for i in range(30)) + ",", 1
            ),
            "500",
        ),
        (lambda s: s.replace("Kenapa pelangi melengkung?", "Kenapa pelangi melengkung? \u2192"), "ASCII"),
    ],
)
def test_lint_menangkap_pelanggaran(k, tmp_path, rusak, pesan):
    p = M.buat(
        "pelangi",
        FRASA,
        "shorts",
        k,
        konten=KONTEN,
        timeline=TL,
        final=True,
        sumber=[{"penerbit": "NOAA", "judul": "Rainbows", "url": "https://www.noaa.gov/rainbow"}],
    )
    f = tmp_path / "M.md"
    s = M.tulis_md(p, f, "uji").read_text()
    f.write_text(rusak(s), encoding="utf-8")
    g, _ = M.cek_md(f, "shorts", "bumi", k)
    assert any(pesan in x for x in g), g


def test_pustaka_status_studio_duplikat(db, tmp_path):
    h = pustaka.sinkron_status(db)
    assert db.topik("kucing")["status"] == "dibahas" and db.topik("lubang hitam")["status"] == "long"
    assert db.topik("ai")["status"] == "segar" and h["arsip_baru"] >= 10  # ai != baterai
    assert db.topik("megalodon")["pilar"] == "hewan"
    db.tambah_episode("shorts", "pelangi", judul="Kenapa Pelangi Melengkung? Ini Jawaban Sainsnya", youtube_id="abc123")
    csv = tmp_path / "studio.csv"
    csv.write_text(
        "Content,Video title,Video publish time,Duration,Views,Watch time (hours),Subscribers,Impressions,"
        "Impressions click-through rate (%),Average view duration,Average percentage viewed (%)\n"
        "Total,,,,1500,10,5,20000,5.1,0:00:40,70\n"
        'abc123,Kenapa Pelangi Melengkung? Ini Jawaban Sainsnya,"Oct 3, 2026",150,1500,10,5,20000,5.1,'
        "0:00:40,70.5\n",
        encoding="utf-8",
    )
    assert pustaka.impor_studio(db, csv, HARI) == 1
    p = db.ambil("performa", kode="Ep50")
    assert (
        p["tayangan"] == 1500 and p["rata_durasi_detik"] == 40 and p["persen_ditonton"] == 70.5 and p["pilar"] == "bumi"
    )
    assert db.performa_pilar()["bumi"]["n"] == 1
    top = pustaka.duplikat(db, "bintang berkedip di langit")
    assert top[0][0] == "bintang berkedip" and top[0][1] >= 0.9


def test_perencana_dan_ics(riset_uji, tmp_path):
    h, d, _ = riset_uji
    rows = perencana.susun(d, HARI, 2)
    assert rows and len({r["judul_kerja"] for r in rows}) == len(rows)  # topik unik
    assert all(dt.date.fromisoformat(r["tanggal"]) > HARI for r in rows)
    assert [r["episode_kode"] for r in rows if r["format"] == "shorts"][0] == "Ep50"
    assert all(r["jam"] in d.kanal.jadwal.slot_wib for r in rows)
    ics = perencana.tulis_ics(rows, tmp_path / "k.ics", HARI).read_bytes()
    assert ics.startswith(b"BEGIN:VCALENDAR\r\n") and ics.endswith(b"END:VCALENDAR\r\n")
    assert all(len(b) <= 75 for b in ics.split(b"\r\n")) and ics.count(b"BEGIN:VEVENT") == len(rows)
    d.con.execute("UPDATE rencana SET status = 'terkunci' WHERE id = (SELECT MIN(id) FROM rencana)")
    kunci = d.daftar("rencana", "status = 'terkunci'")[0]
    perencana.susun(d, HARI, 2)
    assert d.ambil("rencana", id=kunci["id"])["status"] == "terkunci"  # milik pemilik tidak ditimpa


def test_dasbor_md_png(riset_uji, tmp_path):
    h, d, _ = riset_uji
    data = dasbor.kumpulkan(d, HARI)
    md = dasbor.markdown(data)
    assert "Peluang teratas" in md and data["berikut"]["shorts"] == "Ep50"
    png = dasbor.png(data, tmp_path / "d.png", d.kanal)
    from PIL import Image

    assert Image.open(png).size == (1600, 1000)


def test_sinkron_bolt_postgrest_bolak_balik(db):
    awan: dict[str, dict[int, dict]] = {}

    def h(req: httpx.Request) -> httpx.Response:
        assert req.headers["apikey"] == "kunci-uji" and req.headers["authorization"] == "Bearer kunci-uji"
        tabel = urlparse(str(req.url)).path.split("/")[-1]
        q = {a: b[0] for a, b in parse_qs(urlparse(str(req.url)).query).items()}
        t = awan.setdefault(tabel, {})
        if req.method == "POST":
            assert "merge-duplicates" in req.headers["prefer"] and q["on_conflict"] == "id"
            for r in json.loads(req.content):
                t[r["id"]] = {**t.get(r["id"], {}), **r}
            return httpx.Response(201)
        rows = [t[i] for i in sorted(t)]
        mulai, n = int(q.get("offset", 0)), int(q.get("limit", 1000))
        return httpx.Response(200, json=rows[mulai : mulai + n])

    db.seed_tema()
    db.tambah_episode("shorts", "pelangi", judul="Uji")
    kl = sinkron.KlienBolt("https://proyek.supabase.co", "kunci-uji", transport=httpx.MockTransport(h), batch=25)
    n = sinkron.dorong(db, kl)
    assert n["topik"] == len(db.daftar("topik")) and len(awan["topik"]) == n["topik"]
    d2 = DB(":memory:")
    m = sinkron.tarik(d2, kl)
    assert m["episode"] == 1 and d2.episode("Ep50")["judul"] == "Uji"
    with pytest.raises(sinkron.SinkronError):
        sinkron.KlienBolt("http://tidak-aman.example", "k")


def test_cli_asap():
    def jalan(*a: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "kliktahu", *a], capture_output=True, text=True, cwd=str(pustaka.ROOT), timeout=120
        )

    assert "SAH" in jalan("kanal").stdout
    assert jalan("skema", "cek").returncode == 0
    r = jalan("astro", "--tahun", "2026", "--kota", "Semarang")
    assert "10-10" not in r.stdout and "11-10 11:25" in r.stdout
    assert jalan("sinkron").returncode == 1  # belum dikonfigurasi -> pesan jelas, bukan crash


def test_metadata_bencana_hormat_dan_gerbang_baca_content_json(k, tmp_path):
    fr = ["kenapa tsunami bisa terjadi", "kenapa tsunami surut dulu", "kenapa tsunami palu bisa terjadi"]
    p = M.buat("tsunami", fr, "shorts", k)
    assert p.lulus, p.galat
    assert "seru" not in p.deskripsi.lower() and "Info resmi & peringatan dini: BMKG" in p.deskripsi
    assert not any("Bikin Kaget" in j or "Dugaanmu" in j for j in p.judul)
    p.judul[0] = "Kenapa Tsunami Terjadi? Jawabannya Bikin Kaget"
    g, _ = M.lint(p, k, final=False)
    assert any("sensasi" in x for x in g)
    # gerbang render: tema dibaca dari content.json di folder episode -> nada bencana & disclaimer kesehatan ditegakkan
    ep = tmp_path / "Ep50"
    ep.mkdir()
    md = M.tulis_md(M.buat("pelangi", FRASA, "shorts", k), ep / "METADATA.md", "uji")
    md.write_text(md.read_text().replace("Kenapa pelangi melengkung?\n", "Kenapa pelangi melengkung?\nSeru!\n"))
    (ep / "content.json").write_text(json.dumps({"topik": "tsunami"}), encoding="utf-8")
    assert any("sensasi" in x for x in M.cek_md(md, "shorts", k=k)[0])
    (ep / "content.json").write_text(json.dumps({"topik": "cegukan"}), encoding="utf-8")
    assert any("kesehatan" in x for x in M.cek_md(md, "shorts", k=k)[0])  # pilar tubuh diturunkan dari tema


def test_perencana_keputusan_dulu_lalu_tenggat_terdekat(db, tmp_path, monkeypatch):
    from kliktahu import momen

    def baris(nama, peluang, n):
        return {"nama": nama, "v7_peluang": peluang, "peringkat": n, "status_topik": "segar", "sinyal": {}}

    rank = [baris("gunung berapi", 67.9, 1), baris("tsunami", 65.7, 2), baris("otak", 62.5, 3), baris("kuku", 59.4, 4)]
    daftar = [
        momen.Momen(
            dt.date(2026, 9, 4), "Erupsi beruntun", ["gunung berapi"], "agen", "uji", 0.7, dt.date(2026, 9, 25)
        ),
        momen.Momen(dt.date(2026, 9, 28), "Peringatan 8 tahun tsunami Palu", ["tsunami"], "statis", "uji"),
    ]
    run = {"id": 7, "mode": "agen"}
    monkeypatch.setattr(perencana, "_peringkat", lambda d: (rank, run))
    monkeypatch.setattr(perencana.momen, "semua", lambda *a, **kw: daftar)
    monkeypatch.setattr(perencana, "LAPORAN", tmp_path)
    # tanpa keputusan: EDF -> tsunami (event 28 Sep) di slot pertama Senin 28 Sep, gunung berapi (verifikasi lewat) sesudahnya
    s = [r for r in perencana.susun(db, HARI, 2, simpan=False) if r["format"] == "shorts"]
    assert [(r["tanggal"], r["judul_kerja"]) for r in s[:2]] == [
        ("2026-09-28", "tsunami"),
        ("2026-09-29", "gunung berapi"),
    ]
    # dengan keputusan 'kuku': slot pertama = keputusan; tsunami TIDAK dijadwalkan sebagai momen sesudah event
    (tmp_path / "riset_terakhir.json").write_text(
        json.dumps({"run_id": 7, "keputusan": {"tema": "kuku", "format": "shorts", "peluang": 59.4}}), encoding="utf-8"
    )
    rows = perencana.susun(db, HARI, 2, simpan=False)
    assert rows[0]["judul_kerja"] == "kuku" and rows[0]["alasan"].startswith("KEPUTUSAN riset")
    ts = next(r for r in rows if r["judul_kerja"] == "tsunami")
    assert "momen" not in ts["alasan"] and ts["tanggal"] > "2026-09-28"  # diisi peringkat biasa, bukan "momen" telat


def test_perencana_momen_berlangsung_tanpa_selesai_dan_slot_terkunci(db, tmp_path, monkeypatch):
    from kliktahu import momen

    def baris(nama, peluang, n):
        return {"nama": nama, "v7_peluang": peluang, "peringkat": n, "status_topik": "segar", "sinyal": {}}

    rank = [baris("gunung berapi", 67.9, 1), baris("otak", 62.5, 2)]
    # erupsi mulai 4 Sep, TANPA tanggal selesai; hari ini 26 Sep -> masih berlangsung (<= BERLANGSUNG_HARI)
    erupsi = momen.Momen(
        dt.date(2026, 9, 4), "Erupsi Anak Krakatau", ["gunung berapi"], "agen", "uji", 0.7, dt.date(2026, 9, 25)
    )
    jauh = momen.Momen(dt.date(2026, 10, 13), "Hari Risiko Bencana", ["gunung berapi"], "statis", "uji")
    monkeypatch.setattr(perencana, "_peringkat", lambda d: (rank, {"id": 7, "mode": "agen"}))
    monkeypatch.setattr(perencana.momen, "semua", lambda *a, **kw: [erupsi, jauh])
    monkeypatch.setattr(perencana, "LAPORAN", tmp_path)
    h26 = dt.date(2026, 9, 26)
    # momen berlangsung tanpa selesai tetap bernilai penuh & mengalahkan momen statis jauh
    s, m = momen.skor_tema("gunung berapi", [erupsi, jauh], h26, 45)
    assert m is erupsi and s >= 0.7
    rows = perencana.susun(db, h26, 2)
    g = next(r for r in rows if r["judul_kerja"] == "gunung berapi")
    assert "Erupsi Anak Krakatau" in g["alasan"] and g["tanggal"] < "2026-10-13"
    # slot terkunci milik pemilik tampil di KALENDER.md (dulu hanya 'usulan')
    db.con.execute("UPDATE rencana SET status = 'terkunci' WHERE id = (SELECT MIN(id) FROM rencana)")
    semua = perencana.baris_kunci(db) + perencana.susun(db, h26, 2)
    md = perencana.tulis_md(semua, tmp_path / "K.md", h26).read_text()
    assert "| status |" in md and "terkunci" in md


def test_metadata_episode_bab_judul_tetap_tag_hormat(k, tmp_path):
    konten = {
        "judul": [
            "Kenapa Tsunami Palu Bisa Terjadi? Ini Jawaban Sainsnya",
            "Peringatan 8 Tahun Tsunami Palu: Kenapa Bisa Terjadi?",
            "Gempa Mendatar Kok Bisa Tsunami? Ini Penjelasan Ilmiahnya",
        ],
        "kata_kunci": "kenapa tsunami palu bisa terjadi",
        "scenes": [
            {"id": "intro", "type": "intro", "bab": "Gempa mendatar, kok ada tsunami?"},
            {"id": "f1", "type": "fact", "badge": "28 SEPTEMBER 2018", "bab": "Sesar Palu-Koro"},
            {"id": "f2", "type": "fact", "badge": "LIKUEFAKSI"},
            {"id": "outro", "type": "outro", "bab": "Penutup"},
        ],
    }
    tl = {
        "total": 60.0,
        "scenes": [
            {"id": "intro", "start": 0},
            {"id": "f1", "start": 14.4},
            {"id": "f2", "start": 32.0},
            {"id": "outro", "start": 50.1},
        ],
    }
    bab = M.bab_dari_timeline(konten, tl)
    assert bab == [(0.0, "Gempa mendatar, kok ada tsunami?"), (14.4, "Sesar Palu-Koro"), (32.0, "Likuefaksi")]
    fr = [
        "kenapa tsunami palu bisa terjadi",
        "kenapa tsunami aceh banyak korban",
        "kenapa tsunami pakai t",
        "kenapa tsunami surut dulu",
    ]
    p = M.buat(
        "tsunami",
        fr,
        "shorts",
        k,
        konten=konten,
        timeline=tl,
        final=True,
        sumber=[{"penerbit": "BMKG", "judul": "InaTEWS", "url": "https://inatews.bmkg.go.id"}],
    )
    assert p.lulus, p.galat
    assert p.judul == konten["judul"] and p.deskripsi.startswith(
        "Kenapa tsunami Palu bisa terjadi?"
    )  # nama diri kapital
    assert not any("korban" in x or x.endswith(" t") for x in p.tag)  # hormat + tanpa token satu huruf
    st = M.tulis_siap_tempel(p, tmp_path / "SIAP_TEMPEL.md", "Ep50", k, jam="2026-09-28 11:30 WIB (kalender)")
    isi = st.read_text(encoding="ascii")
    assert "jalur evakuasi" in isi and "kaget" not in isi and "2026-09-28 11:30" in isi
