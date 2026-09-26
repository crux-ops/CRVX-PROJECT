# Rencana upgrade KlikTahu — September 2026

Tanggal audit: 26 September 2026 UTC. Target: branch `arena/01a0d793-crvx-project`.

## Lingkup dan prinsip

Upgrade proyek yang ada, bukan aplikasi baru dan bukan produksi video. Pertahankan CLI, model data, serta perilaku render. `PROMPT_KLIKTAHU.txt` tidak diubah. Tambahkan modul hanya untuk kebutuhan terukur; jangan menganggap paket terbaru otomatis lebih baik.

Dokumen ini membedakan implementasi paket pertama dari pekerjaan lanjutan. Daftar rencana bukan klaim bahwa semua fitur telah selesai atau bahwa semua pin sudah terbaru.

## Paket pertama

| Berkas | Perubahan |
|---|---|
| `kliktahu/riset/http.py` | Sanitasi URL efektif sesuai semantik HTTPX; buang parameter rahasia, userinfo, fragment; dukung Retry-After tanggal HTTP. |
| `tests/test_http_keamanan.py` | Tes karakterisasi cache/JSON/404/retry dan regresi keamanan, encoding, parameter berulang, tanggal HTTP. |
| `tools/cek_versi.py` | Audit pin runtime dan dev dari pyproject terhadap rilis PyPI stabil, tidak ditarik, tersedia pada batas tanggal, dan cocok Requires-Python. |
| `tests/test_cek_versi.py` | Uji offline marker Python, rilis masa depan, prerelease, yanked, metadata rusak, kegagalan sumber, dan pin yang tidak ada. |
| `RENCANA_UPGRADE_2026_09.md` | Urutan upgrade, dampak, kriteria penerimaan, dan batas verifikasi. |

### Dampak perilaku dan migrasi

URL tersanitasi kini memakai encoding query yang benar. Perubahan kunci cache dapat menyebabkan cache miss pertama; tidak mengubah skema SQLite. Sanitasi baru tidak menghapus rahasia yang mungkin sudah tersimpan di cache lama. Bila pernah memasukkan rahasia dalam URL, hentikan proses, hapus cache lokal `data/cache_http.sqlite` beserta sidecar SQLite setelah semua koneksi ditutup, dan rotasi kredensial yang terpapar. Cache dapat dibangun ulang; jangan menghapus basis data pustaka.

Retry-After lebih dari 30 detik kini menghasilkan `GagalHTTP`, bukan dipotong menjadi 30 detik lalu mencoba terlalu dini. Consumer menggunakan jalur kegagalan HTTP yang ada. Tes harus memastikan kegagalan satu sumber tidak menghentikan seluruh riset. Tidak ada jaminan cooldown global antarpermintaan pada paket pertama.

Sanitasi URL bukan pencegahan SSRF menyeluruh. Isolasi cache antarkredensial, redaksi exception berantai, pembatasan ukuran respons, serta pemeriksaan redirect dan alamat jaringan tetap pekerjaan lanjutan.

### Verifikasi dependensi

Gunakan lingkungan pengembangan yang dipasang melalui `requirements-dev.txt`; tool memakai `httpx` dan `packaging` (dependensi pytest). Tidak ada instalasi atau perubahan pin otomatis.

```bash
python3 tools/cek_versi.py --python-version 3.11 --as-of 2026-09-26
python3 tools/cek_versi.py --python-version 3.14 --as-of 2026-09-26
```

Exit 0 berarti pin aktif terverifikasi terbaru sesuai metadata yang diperiksa; 1 berarti pembaruan tersedia; 2 berarti konfigurasi/verifikasi gagal. Metadata Requires-Python yang hilang tidak dianggap bukti kompatibilitas. Target OS/arsitektur mengikuti lingkungan saat tool berjalan. Batas tanggal mengecualikan upload masa depan, tetapi bukan rekonstruksi historis status yanked. Status yanked mengikuti respons PyPI saat diambil.

Ini bukan resolver dependensi, audit kerentanan, atau bukti ketersediaan wheel/ABI. Pembaruan pin selanjutnya membutuhkan verifikasi lingkungan bersih, keselarasan requirements dengan pyproject, audit kerentanan, dan CI. Klaim versi terbaru dalam dokumentasi lama belum dibuktikan oleh keberadaan tool ini.

## Rancangan lanjutan: riset sampai metadata

| Tahap | Modul/perbaikan | Kriteria penerimaan |
|---|---|---|
| 1 | Validasi input agen dan provenance | Struktur, tipe, nilai hingga, batas angka, tanggal berzona waktu, URL, penerbit, dan waktu pengambilan divalidasi. Tidak memberi kredibilitas True secara bawaan. |
| 2 | Kesegaran dan status sumber | Pisahkan live, cache segar, kedaluwarsa, offline, dan fixture. TTL per jenis sumber; tampilkan waktu pengambilan, bukan hanya waktu laporan. |
| 3 | Pencarian multisumber | Adapter sumber resmi dengan timeout, kuota, backoff, fallback, deduplikasi, dan status kegagalan. Hormati robots, lisensi, autentikasi, dan batas akses. |
| 4 | Discovery topik | Perluas kandidat dari pertanyaan dan sinyal live, lalu cocokkan niche kanal; jangan membatasi penemuan tanpa menjelaskan batas registri tema. |
| 5 | Verifikasi klaim | Peta klaim ke bukti yang dibaca; bedakan fakta, inferensi, dan sinyal minat. Periksa konflik sumber dan independensi penerbit. |
| 6 | Pemilihan niche/topik | Skor yang dapat dijelaskan untuk permintaan, momentum, celah, kecocokan kanal, kesegaran, biaya produksi, dan kekuatan bukti. Ketidakpastian bukan probabilitas sukses. |
| 7 | Judul | Variasi judul berdasarkan sudut dan bukti; tidak menjanjikan angka atau fakta yang tidak didukung. Uji duplikasi dan kecocokan bahasa Indonesia. |
| 8 | Deskripsi | Ringkasan yang setia pada bukti, daftar sumber, tanggal riset, dan disclaimer relevan; jangan membuat bab sebelum timeline tersedia. |
| 9 | Hashtag | Relevan terhadap topik, tidak menumpuk tren yang tidak berkaitan; validasi aturan platform terkini dari sumber resmi. |
| 10 | Tag | Kata inti dan variasi pencarian nyata; deduplikasi, relevansi, dan batas platform diverifikasi. Jangan menjanjikan ranking. |
| 11 | Evaluasi | Dataset evaluasi offline dan pengujian opt-in live yang tidak berjalan pada CI rutin; ukur relevansi, dukungan klaim, kesegaran, kelengkapan, dan biaya. |
| 12 | Observabilitas | Run ID, snapshot sumber, alasan keputusan, kegagalan, waktu, biaya/kuota, dan audit trail tanpa menyimpan rahasia. |

Urutan: karakterisasi perilaku lama → seam/adaptor → pengujian kontrak → perubahan fokus → integrasi. Migrasi skema atau perubahan CLI memerlukan rencana migrasi dan persetujuan terpisah. Hindari penambahan server, dashboard baru, video, atau publikasi otomatis.

## Gerbang kualitas

```bash
python3 -m pytest -q tests/test_http_keamanan.py tests/test_cek_versi.py
ruff check kliktahu tests tools/cek_versi.py
ruff format --check kliktahu tests tools/cek_versi.py
python3 -m mypy
bash tools/uji_semua.sh
```

CI yang ada menjalankan suite utama pada Python 3.11 dan 3.14. Skrip CI saat audit belum memasukkan `tools/cek_versi.py` ke target Ruff eksplisit; perintah tambahan di atas tetap diperlukan. Jangan menyamakan sukses unit test dengan sukses riset live. Jangan menyatakan upgrade menyeluruh selesai sebelum setiap tahap memiliki bukti tes.

## Referensi

Dokumentasi PyPI JSON API ditelusuri pada 26 September 2026: https://docs.pypi.org/api/json/ . Gunakan metadata rilis nyata untuk versi, bukan tanggal yang ditulis dalam README. Tidak ada nomor versi baru yang diasumsikan dalam paket ini.
