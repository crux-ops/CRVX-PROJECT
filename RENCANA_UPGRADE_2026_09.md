# Rencana upgrade KlikTahu — September 2026

Tanggal audit awal: 26 September 2026 UTC. Target: branch `arena/01a0d793-crvx-project`, kerja lanjut di
`arena/01a0dbcd-crvx-project`.

## Lingkup dan prinsip

Upgrade proyek yang ada, bukan aplikasi baru dan bukan produksi video. Pertahankan CLI, model data, serta perilaku
render. `PROMPT_KLIKTAHU.txt` tidak diubah. Tambahkan modul hanya untuk kebutuhan terukur; jangan menganggap paket
terbaru otomatis lebih baik.

Dokumen ini membedakan implementasi yang sudah berjalan dari pekerjaan lanjutan. Daftar rencana bukan klaim bahwa
semua fitur selesai atau semua pin paling baru.

## Paket pertama (sudah berjalan)

| Berkas | Perubahan |
|---|---|
| `kliktahu/riset/http.py` | Sanitasi URL efektif sesuai semantik HTTPX; buang parameter rahasia, userinfo, fragment; dukung Retry-After tanggal HTTP. |
| `tests/test_http_keamanan.py` | Tes karakterisasi cache/JSON/404/retry dan regresi keamanan, encoding, parameter berulang, tanggal HTTP. |
| `tools/cek_versi.py` | Audit pin runtime dan dev dari pyproject terhadap rilis PyPI stabil, tidak ditarik, tersedia pada batas tanggal, dan cocok Requires-Python. |
| `tests/test_cek_versi.py` | Uji offline marker Python, rilis masa depan, prerelease, yanked, metadata rusak, kegagalan sumber, dan pin yang tidak ada. |

### Dampak perilaku dan migrasi

URL tersanitasi kini memakai encoding query yang benar. Perubahan kunci cache dapat menyebabkan cache miss pertama;
tidak mengubah skema SQLite. Sanitasi baru tidak menghapus rahasia yang mungkin sudah tersimpan di cache lama. Bila
pernah memasukkan rahasia dalam URL, hentikan proses, hapus cache lokal `data/cache_http.sqlite` beserta sidecar
SQLite setelah semua koneksi ditutup, dan rotasi kredensial yang terpapar. Cache dapat dibangun ulang; jangan
menghapus basis data pustaka.

Retry-After lebih dari 30 detik kini menghasilkan `GagalHTTP`, bukan dipotong menjadi 30 detik lalu mencoba terlalu
dini. Consumer menggunakan jalur kegagalan HTTP yang ada. Tes memastikan kegagalan satu sumber tidak menghentikan
seluruh riset. Tidak ada jaminan cooldown global antarpermintaan.

Sanitasi URL bukan pencegahan SSRF menyeluruh. Isolasi cache antarkredensial, redaksi exception berantai,
pembatasan ukuran respons, serta pemeriksaan redirect dan alamat jaringan tetap pekerjaan lanjutan.

### Verifikasi dependensi

```bash
python3 tools/cek_versi.py --python-version 3.11 --as-of 2026-09-26
python3 tools/cek_versi.py --python-version 3.14 --as-of 2026-09-26
```

Exit 0 berarti pin aktif terverifikasi terbaru sesuai metadata yang diperiksa; 1 berarti pembaruan tersedia; 2
berarti konfigurasi/verifikasi gagal. Metadata Requires-Python yang hilang tidak dianggap bukti kompatibilitas.
Target OS/arsitektur mengikuti lingkungan saat tool berjalan. Batas tanggal mengecualikan upload masa depan, tetapi
bukan rekonstruksi historis status yanked. Status yanked mengikuti respons PyPI saat diambil.

Ini bukan resolver dependensi, audit kerentanan, atau bukti ketersediaan wheel/ABI. Pembaruan pin selanjutnya
membutuhkan verifikasi lingkungan bersih, keselarasan requirements dengan pyproject, audit kerentanan, dan CI.
Klaim versi terbaru dalam dokumentasi lama belum dibuktikan oleh keberadaan tool ini.

## Paket kedua: riset sampai metadata (tahap 1-12)

Semua tahap di bawah SUDAH berjalan dan memiliki bukti uji. Tiap tahap menyebut modulnya dan kriteria penerimaan
yang dijadikan uji.

| Tahap | Modul | Kriteria penerimaan | Status |
|---|---|---|---|
| 1 | `kliktahu/validasi.py` | Struktur, tipe, nilai hingga, batas angka, tanggal berzona waktu, URL, penerbit, dan waktu pengambilan divalidasi. Tidak memberi kredibilitas True secara bawaan. | SELESAI (`tests/test_validasi.py`) |
| 2 | `kliktahu/kesegaran.py` | Pisahkan live, cache segar, kedaluwarsa, offline, dan fixture. TTL per jenis sumber; laporan menampilkan waktu pengambilan, bukan hanya waktu laporan. | SELESAI (`tests/test_validasi.py`) |
| 3 | `kliktahu/cari.py` (+3 sumber baru di `riset/sumber.py`) | Adapter sumber dengan timeout, kuota, backoff, fallback, deduplikasi, dan status kegagalan. Hormati robots, lisensi, autentikasi, dan batas akses. | SELESAI (`tests/test_cari.py`) |
| 4 | `kliktahu/penemuan.py` | Perluas kandidat dari pertanyaan dan sinyal live, lalu cocokkan niche kanal; batas registri tema dijelaskan di laporan. | SELESAI (`tests/test_penemuan.py`) |
| 5 | `kliktahu/klaim.py` | Peta klaim ke bukti yang dibaca; bedakan fakta, inferensi, dan sinyal minat. Periksa konflik sumber dan independensi penerbit. | SELESAI (`tests/test_klaim.py`) |
| 6 | `kliktahu/niche.py` | Skor yang dapat dijelaskan untuk permintaan, momentum, celah, kecocokan kanal, kesegaran, biaya produksi, dan kekuatan bukti. Ketidakpastian bukan probabilitas sukses. | SELESAI (`tests/test_niche.py`) |
| 7 | `kliktahu/meta/judul.py` | Variasi judul berdasarkan sudut dan bukti; tidak menjanjikan angka/fakta yang tidak didukung. Uji duplikasi dan kecocokan bahasa Indonesia. | SELESAI (`tests/test_meta.py`) |
| 8 | `kliktahu/meta/deskripsi.py` | Ringkasan setia bukti, daftar sumber ber-provenance, tanggal riset, disclaimer relevan; bab hanya dibuat bila timeline tersedia. | SELESAI (`tests/test_meta.py`) |
| 9 | `kliktahu/meta/hashtag.py` | Relevan terhadap topik, tanpa tren yang tidak berkaitan; aturan platform (maks 15 atau SEMUA diabaikan, tidak boleh hanya angka) divalidasi. | SELESAI (`tests/test_meta.py`) |
| 10 | `kliktahu/meta/tag.py` | Kata inti dan variasi pencarian nyata; deduplikasi, relevansi, dan batas 500 karakter cara YouTube diverifikasi. Tidak menjanjikan ranking. | SELESAI (`tests/test_meta.py`) |
| 11 | `kliktahu/evaluasi.py` + `data/evaluasi/kasus.jsonl` | Dataset evaluasi offline dan pengujian live opt-in yang tidak berjalan pada CI; ukur relevansi, dukungan klaim, kesegaran, kelengkapan, dan biaya. | SELESAI (`tests/test_analisis.py`) |
| 12 | `kliktahu/observabilitas.py` | Run ID, snapshot sumber, alasan keputusan, kegagalan, waktu, biaya/kuota, dan audit trail tanpa menyimpan rahasia. | SELESAI (`tests/test_observabilitas.py`) |
| — | `kliktahu/analisis.py` (orkestrator) | Menjalankan tahap 1-12 dalam satu perintah: cari -> temukan -> buktikan -> nilai -> putuskan -> metadata -> jejak. | SELESAI (`tests/test_analisis.py`) |

### Yang baru bisa dipakai

```bash
python3 -m kliktahu cari "kenapa gunung meletus" [--jenis saran,ilmiah] [--sumber saran_google] [--json]
python3 -m kliktahu analisis "kenapa tsunami bisa terjadi" [--mode online|agen|uji] [--tema tsunami] [--json]
python3 -m kliktahu evaluasi [--kasus data/evaluasi/kasus.jsonl] [--live --izin-live]   # live TIDAK untuk CI
```

`cari` = satu kueri ke semua sumber (kuota per sumber, rantai cadangan, deduplikasi, status kesegaran per sumber).
`analisis` = rantai penuh: kandidat topik (termasuk yang di luar registri, dengan keterangan batasnya), verifikasi
klaim, skor niche + keyakinan + rentang, keputusan topik, lalu judul/deskripsi/hashtag/tag, laporan
`laporan/ANALISIS.md`, dan jejak audit `data/audit/` (abaikan-git, tanpa rahasia).

### Sumber data yang ditambahkan (diuji dengan fixture, format diverifikasi langsung 26-09-2026)

| Sumber | Endpoint | Dipakai untuk |
|---|---|---|
| Crossref | `https://api.crossref.org/works` | pengecekan silang DOI/bukti ilmiah (melengkapi OpenAlex & Europe PMC) |
| Open-Meteo | `https://api.open-meteo.com/v1/forecast` | ramalan cuaca -> momen hujan lebat/angin kencang (tanpa kunci) |
| Wikipedia teratas | `https://wikimedia.org/api/rest_v1/metrics/pageviews/top/id.wikipedia/all-access/YYYY/MM/DD` | discovery: artikel paling banyak dibaca hari itu (halaman sistem dibuang) |

### Keputusan desain yang perlu diketahui

* **Cakupan kueri.** Kandidat yang tidak disebut hasil autocomplete untuk kueri itu (misal artikel Wikipedia
  teratas atau momen gempa hari ini) TIDAK dipakai menjawab kueri, tetapi tetap dilaporkan sebagai "sinyal lain"
  di laporan. Tanpa ini, pertanyaan "kenapa bintang berkedip" bisa dijawab "gempa bumi" hanya karena ada gempa.
* **Kanonisasi kandidat.** "gunung meletus" dan "gunung berapi" disatukan ke nama registri supaya aturan topik
  bencana (nada hormat, info resmi PVMBG/BMKG) ikut berlaku, bukan cuma namanya.
* **Komponen tanpa data = netral 0.5 dengan keyakinan 0** - bukan 0, bukan asumsi. Rentang tampil melebar bila
  keyakinan rendah; angka skor dinyatakan sebagai posisi relatif, BUKAN peluang tayangan.
* **Deteksi konflik klaim bersifat heuristik** (membandingkan angka + satuan yang sama antar sumber kredibel).
  Hasilnya berstatus "harus dicek manusia", bukan vonis salah/benar.
* **Mode offline (`uji`, `agen`) distempel FIXTURE**, sehingga laporan tidak pernah mengklaim data uji sebagai data
  pasar nyata.

### Batas yang belum dikerjakan (jujur, bukan klaim)

* Evaluasi **live** belum pernah dijalankan: butuh `--izin-live` + `KLIKTAHU_LIVE=1`, dan jaringan sandbox
  memblokir hampir semua host riset. Uji live harus dilakukan pemilik di komputer dengan internet biasa.
* Tidak ada metrik tayangan/retensi/CTR: evaluasi hanya mengukur rantai (relevansi, dukungan klaim, kesegaran,
  kelengkapan, biaya). Loop performa tetap lewat `pustaka impor-studio` (YouTube Studio).
* Verifikasi klaim memakai judul/penerbit/DOI dari pencarian jurnal; isi artikel tidak diunduh. Jadi "didukung"
  berarti "ada sumber kredibel & relevan yang menyebut hal itu", bukan "kalimat ini sudah dibaca mesin".
* Pencarian web (Brave/SearXNG) tetap opsional: butuh kunci/URL sendiri, dan tidak diaktifkan bila tidak diisi.
* Cooldown global antarpermintaan dan isolasi cache antarkredensial (catatan di paket pertama) belum dikerjakan.

## Paket ketiga: audit dari data nyata (26-09-2026)

Riset online **tidak** dijalankan di GitHub Actions (aturan pemilik: Actions hanya uji ringan, tanpa
scraping/cron - pola itu yang membuat akun lama di-flag). Data nyata diambil agen sendiri dengan
`fetch_page`/`web_search`, disimpan ke `analisis/data/agen/riset_20260926.json`, lalu diproses
`kliktahu analisis --mode agen` dengan rumus yang identik ke mode online.

Yang dihasilkan: 5 tema dianalisis dengan autocomplete Google/YouTube, pageview Wikipedia 3 bulan, DOI
Crossref, momen BMKG/PVMBG, dan tren Google Trends ID - semuanya nyata dan tersimpan di repo.

Yang ditemukan karena datanya **nyata** (bukan fixture), lalu diperbaiki beserta uji regresinya:

| # | Gejala | Akar masalah | Perbaikan |
|---|---|---|---|
| 1 | "momentum 0.50 (tanpa data)" padahal data ada | `PencariAgen` tidak membaca bagian `wiki`/`berita` | ditambahkan; `ringkas()` melapor per sumber |
| 2 | lonjakan pageview tak pernah dihitung | argumen `wiki_lonjakan` di-hardcode `None` | `lonjakan_z` kini masuk rumus (momentum 0.50 -> 1.00) |
| 3 | momen Semeru diklaim kandidat "gunung erebus..." | tema momen live diisi dari **nama kandidat** | tema dari `mentah` sumber / isi judul; klaim butuh >= 2 kata isi |
| 4 | kandidat momen kalender ikut memutuskan kueri orang | gerbang cakupan lolos dengan 1 kata umum | butuh frasa utuh atau >= 2 kata isi |
| 5 | laporan "203 permintaan" vs 111; peringatan "angka 08" palsu | pencatat kumulatif dicatat 2x; `nama_pendek` memotong jam `08:21` | dicatat sekali di akhir; titik dua dalam jam tidak lagi jadi pemisah |

## Gerbang kualitas

```bash
bash tools/uji_semua.sh      # SEMUA: mesin produksi + pytest + cari/analisis/evaluasi + ruff + mypy + cek_versi + TypeScript
python3 -m pytest -q tests
ruff check kliktahu tests tools
ruff format --check kliktahu tests tools
python3 -m mypy
python3 tools/cek_versi.py --python-version 3.11 --as-of 2026-09-26
```

Catatan: target Ruff kini `kliktahu tests tools` (sebelumnya `tools/cek_versi.py` tidak ikut target eksplisit;
dua pelanggaran lama di `tests/test_cek_versi.py` dan `tools/cek_versi.py` sudah diperbaiki). CI menjalankan suite
utama pada Python 3.11 dan 3.14. Jangan menyamakan sukses unit test dengan sukses riset live.

## Referensi

Dokumentasi PyPI JSON API: <https://docs.pypi.org/api/json/> . Aturan hashtag YouTube (diperiksa 26 September
2026): YouTube Help "Hashtag". Endpoint Crossref, Open-Meteo, dan Wikimedia pageviews diuji langsung pada
26 September 2026 (format respons dipakai untuk menulis parser). Gunakan metadata rilis nyata untuk versi, bukan
tanggal yang tertulis di README.
