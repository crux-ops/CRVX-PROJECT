# AGEN.md - memori jangka panjang agen KlikTahu

> Baca file ini PERTAMA KALI setiap sesi. Perbarui setiap ada perubahan besar / episode baru.
> Spesifikasi lengkap dari pemilik: `PROMPT_KLIKTAHU.txt` (sumber kebenaran; file ini ringkasan + status).

## 0. Status singkat
- Fase: **PRODUKSI EPISODE**. Pemilik memerintahkan "Buat video shorts!" (25-09-2026) -> **Ep50 tsunami Palu**
  (`episodes/ep50_tsunami_palu`, sudut "Kenapa tsunami Palu bisa terjadi?", tayang Sen 28 Sep 2026 11.30 WIB =
  peringatan 8 tahun). Status: **RENDER SELESAI + QC MP4 LULUS (26-09-2026) -> SIAP UNGGAH**. MP4 147.48 s
  (8849 frame @ 60 fps, 1080x1920, H.264 High BT.709, AAC 48 kHz), 121.8 MB, master -14.2 LUFS / true-peak -1.2 dBTP,
  korelasi 1.0000, VO geser 0 ms & isi hilang 0 ms di 9 adegan. File rilis = render ulang penuh 26-09 03:01 UTC dari
  kode df08bfc (MD5 ab39da6403d801c66758f32ccaeba5d4, 121773203 byte; diserahkan lewat tautan unduh sementara +
  pratinjau 720p 39.7 MB di `/home/user/VIDEO_Ep50/`). MP4 TIDAK di repo: ada di
  `dist/KlikTahu_Ep50_Tsunami_Palu/` (sandbox; hilang bila reset) -> buat ulang: `tools/render_lokal.sh shorts
  ep50_tsunami_palu` (~35-45 menit; QC wajib LULUS; MD5 bisa beda di mesin sandbox lain - lihat §7 RENDER Ep50).
  Berikutnya (HANYA atas perintah pemilik): Ep51 gunung berapi (cek MAGMA dulu; perbaiki perencana dulu - lihat §7
  RENDER Ep50), Long03 otak.
- Keputusan pemilik 25-09-2026: **repo TETAP PUBLIK** (jangan minta diubah ke privat lagi); **analisis pesaing TIDAK
  perlu** (tanpa YOUTUBE_API_KEY; komponen celah tidak dipakai).
- Jangan membuat video episode sebelum pemilik memberi perintah.

| Tahap | Isi | Status |
|---|---|---|
| 1 | struktur repo, requirements, fonts, .gitignore, AGEN.md | SELESAI |
| 2 | pipeline audio + sfx + QC keutuhan | SELESAI (uji: isi hilang 0 ms, uji negatif lulus) |
| 3 | render.py + diagrams.py + mesin_util + check_layout | SELESAI (demo 3 adegan, audit bersih) |
| 4 | mesin_v11 + mesin_fx | SELESAI (selftest + montase; 0.33 s/frame/proses) |
| 5 | qc_mp4 + tools/render_lokal.sh (demo end-to-end) | SELESAI (demo 15.2 s, QC MP4 lulus) |
| 6 | mesin Long | SELESAI (demo 2 bab 28.7 s, QC MP4 lulus) |
| 7 | mesin analisis v3-v6 + --uji | SELESAI (uji offline lulus; sapuan nyata TERBLOKIR di sandbox) |
| 8 | audisi suara narator -> kunci ID suara | SELESAI (dimajukan, voice-00) |
| U1 | fondasi data: kanal.toml, skema tunggal (SQLite/Postgres-Bolt/JSON/TS), DAL, klien Bolt, rumus v3-v7 + TS, astronomi | SELESAI (pytest, paritas TS 760 kasus) |
| U2 | riset real-time v7 + keputusan + metadata (gerbang render) + pustaka + perencana (ICS) + dasbor + CLI | SELESAI (38 tes, ruff, mypy) |
| U3 | riset NYATA (mode agen) + perbaikan dari data nyata (derau, relevansi, penyusutan tren, momen berlangsung) | SELESAI (CI 3.11 + 3.14) |
| U4 | sapuan lengkap 44 tema + relevansi homonim + judul wiki kanonik + keputusan sadar jeda produksi & transparan + mode hormat bencana + perencana EDF | SELESAI (61 tes, CI) |
| E50 | produksi Ep50 tsunami Palu: naskah, VO voice-00, visual mesin_v11_ep50, render lokal, QC MP4 | SELESAI 26-09-2026 (QC MP4 LULUS; siap unggah Sen 28/09 11.30 WIB) |
| U5 | tahap 1-12 rencana upgrade: validasi, kesegaran, pencarian multi-sumber (+3 sumber baru), penemuan topik, verifikasi klaim, niche, meta/ (judul, deskripsi, hashtag, tag), evaluasi offline, observabilitas, orkestrator `analisis.py` | SELESAI (194 tes, ruff+mypy+TS, `uji_semua` 65 s) |

## 1. Identitas channel (tetap)
- KlikTahu, bahasa Indonesia, pilar fakta sains & misteri.
- Shorts 1080x1920 60 fps (<= 178 s). Long 1920x1080 30 fps (9-11 menit).
- Motion graphics tanpa tokoh/wajah, VO pria, TANPA musik, TANPA subtitle (fitur caption ada tapi MATI).
- Warna Shorts: CREAM (246,241,232), INK (24,24,31), MUTED (128,122,114), aksen per adegan (hex di content.json).
- Font Poppins (Bold/SemiBold/Medium/Regular) di `fonts/` (OFL, lisensi `fonts/OFL.txt`).
  Poppins TIDAK punya glyph centang/bintang/superskrip -> gambar sebagai bentuk (lihat diagrams.py).

## 2. Aturan keras (ringkas - detail di PROMPT_KLIKTAHU.txt §2)
1 tanpa subtitle | 2 VO+SFX sintetis, tanpa musik | 3 audio utuh: tanpa gate/expander/peredam napas,
hanya hening awal/akhir yang boleh dibuang, QC "isi hilang" wajib | 4 1 episode = 1 render = 1 rilis,
metadata lengkap SEBELUM render | 5 METADATA.md 4 blok ASCII | 6 topik diblokir: kentut, ngiler,
keringat & bau badan | 7 1 topik 1 arah, sumber kredibel, kesehatan: "bukan pengganti dokter" |
8 tanpa tokoh | 9 satu suara narator selamanya | 10 jangan potong WAV berulang, rekam ulang |
11 jangan sentuh repo lain | 12 jangan lapor selesai sebelum uji/QC lulus.

## 3. GitHub & keamanan
- Render TIDAK di GitHub Actions. Actions hanya uji ringan (< 5 menit), `permissions: contents: read`, tanpa cron.
- MP4 tidak pernah masuk repo/Releases. Video diserahkan sebagai file di workspace (`dist/`).
  (Pengecualian keputusan pemilik 26-09-2026 untuk Ep51: MP4 diarsip TERBELAH 2 bagian < 100 MB di
  `arsip_video/ep51_gunung_petir/` + README gabung, karena host unggah Releases/LFS tak terjangkau
  dari sandbox; lihat log §8 "ARSIP Ep51".)
- Satu commit bermakna per tahap; jangan push beruntun dalam hitungan menit.
- Tidak pernah menyimpan token/password di file atau chat. `kanal.toml` hanya berisi NAMA variabel lingkungan
  (divalidasi: nilai yang tampak seperti kunci DITOLAK). Kunci tidak ikut kunci cache/log/snapshot (ada tesnya).
- CI `.github/workflows/uji.yml`: push ke main & `arena/**`, matriks Python 3.11 + 3.14 + Node 24, < 5 menit, tanpa cron.
- **Repo `crux-ops/CRVX-PROJECT` PUBLIK atas keputusan pemilik (25-09-2026: "Repo tetap publik!")** - menggantikan
  aturan "repo privat" di PROMPT_KLIKTAHU.txt §3. Konsekuensi: JANGAN PERNAH commit rahasia (token, kunci, .env,
  kredensial, data pribadi); `.gitignore` + validasi kanal.toml sudah menjaga ini, tetap periksa `git diff` sebelum commit.

## 4. Lingkungan sandbox (dicek 2026-09-25)
- 2 vCPU, RAM 3.8 GB, disk ~20 GB. Python 3.11. `pip install --break-system-packages -r requirements.txt`.
- ffmpeg dari `imageio_ffmpeg.get_ffmpeg_exe()` (v7.0.2; ada atempo, ebur128, alimiter, libx264, aac). Tidak ada ffprobe.
- Internet terbatas: HANYA PyPI, registry npm, dan api.github.com yang BISA dari sandbox (dicek ulang 2026-09-25: 48 host
  lain - Google, YouTube, Wikipedia/Wikimedia, BMKG, NASA, NOAA, OpenAlex, dll. - putus TLS/EOF). Node v22.22 + npm ada.
  Python sandbox 3.11.2 (uv tidak bisa unduh Python lain) -> Python 3.14 diuji lewat CI.
  -> Alat `fetch_page` AGEN BISA membuka suggestqueries.google.com, wikimedia.org REST, trends.google.com RSS, dan URL log
     CI (blob Azure bertanda tangan) -> riset nyata = mode agen (lihat §11).
  -> Font diunduh lewat `gh api repos/google/fonts/contents/ofl/poppins/<file>` (base64).
  -> Analisis tren: pakai alat web search agen, masukkan hasilnya sebagai data manual (lihat analisis/).
- Disk: frame PNG 1080x1920 berbutir ~3-5 MB/frame -> JANGAN simpan semua frame; render per potongan (chunk)
  langsung ke encoder (lihat tools/render_lokal.sh).
- Folder `build/` dan `dist/` tidak ikut snapshot Arena (hilang bila sandbox reset) -> hasil penting segera diserahkan.
- Sandbox DIBUAT ULANG setiap kali giliran dihentikan (6x pada 26-09-2026 dini hari): proses latar mati, HEAD kembali ke
  commit awal dcdcc5a (working tree = snapshot giliran terakhir), paket pip & node_modules hilang. Pulihkan (~15 s):
  tambah refspec arena -> `git fetch` -> `git reset --mixed origin/arena/...` -> `pip install --break-system-packages -r
  requirements-dev.txt` -> `npm ci --prefix skema/ts`. File di luar repo (mis. `/home/user/potongan_render/`) dan
  file yang diabaikan git (build/, dist/, data/kliktahu.db) TERBUKTI HILANG saat reset (26-09) -> potongan render
  tidak bisa diselamatkan; perubahan working tree yang tidak diabaikan git tetap ada. Commit + push sedini mungkin.
- Sandbox juga BARU di awal setiap giliran (bukan hanya bila dihentikan): 26-09 giliran selesai normal pun `dist/`
  hilang -> pemilik bertanya "Mana videonya?". PENYERAHAN MP4 (wajib, dalam giliran yang sama dengan render):
  `dist/` & `*.mp4` di repo tidak ikut snapshot; MP4 asli ~122 MB + perubahan repo ~10 MB melewati batas snapshot
  ~128 MB. Jadi: (1) tautan unduh SEMENTARA = server statis `python3 /tmp/unduh/server.py <folder> 8000` (start_process,
  0.0.0.0; mencatat `TERKIRIM <file>` bila unduhan utuh) + halaman `index.html` (bukan aplikasi, tidak di-commit) ->
  tunggu log TERKIRIM file asli sebelum mengakhiri giliran; (2) salinan pratinjau 720p ~40 MB di luar repo
  `/home/user/VIDEO_Ep50/` (bukan nama folder yang dikecualikan) + present_file; (3) jangan simpan MP4 di repo/Releases.

## 5. Struktur repo
Lihat PROMPT_KLIKTAHU.txt §4. Konvensi tambahan:
- Artefak per episode: `build/<slug>/` (audio_proc/, timeline.json, vo_track.wav, audio_master*.wav, seg/, sheet).
- Long: `build/long/<slug>/`.
- Hasil serah: `dist/<OUT_NAME>/` (MP4 + METADATA.md + SIAP_TEMPEL.md [+ thumbnail.jpg]).
- `pratinjau/` = gambar pratinjau untuk ditunjukkan ke pemilik (diabaikan git).
- UPGRADE U5: `kliktahu/validasi.py`, `kesegaran.py`, `cari.py`, `penemuan.py`, `klaim.py`, `niche.py`,
  `meta/` (judul, deskripsi, hashtag, tag), `evaluasi.py`, `observabilitas.py`, `analisis.py` (orkestrator);
  `data/evaluasi/kasus.jsonl` (dataset evaluasi, di-commit); `data/audit/` (jejak JSONL, DIABAIKAN git);
  `laporan/EVALUASI.md` & `laporan/_uji/` (hasil generate, DIABAIKAN git); bagian `[analisis]` di `kanal.toml`.
- UPGRADE: `kanal.toml` (pengaturan kanal), `kliktahu/` (paket data/riset/metadata/perencana/dasbor, CLI
  `python3 -m kliktahu`), `skema/` (SQL SQLite+Postgres, JSON Schema, TypeScript `skema/ts/`), `supabase/migrations/`,
  `tests/` (pytest), `data/ekspor/*.jsonl` (isi basis data, DI-COMMIT; `data/kliktahu.db` diabaikan git -> pulihkan dengan
  `python3 -m kliktahu db impor`), `laporan/` (RISET.md, KALENDER.md + kalender.ics, DASBOR.md, draf/), 
  `analisis/data/agen/*.json` (data riset nyata hasil alat agen, di-commit).

## 6. Suara narator (TERKUNCI - jangan diganti)
- Dipilih pemilik 2026-09-25 lewat audisi TTS Arena (battle "00"): **voice_id `voice-00`**.
- Parameter audisi: language `id-ID`, gender `masculine`, use_case `educational`, index 0.
  Kalimat audisi: "Kenapa aurora hanya muncul di dekat kutub, padahal Matahari menyinari seluruh Bumi? ..."
- voice_id Arena berlaku per sesi. Di sesi baru: audisi ulang dengan parameter yang SAMA, lalu pilih kandidat
  yang suaranya sama dengan klip referensi `suara/referensi_narator.wav`. Catat voice_id sesi baru di sini.
- Semua VO Shorts & Long wajib memakai suara ini. Rekam ulang klip = suara yang sama, teks hampir sama.
- Dipakai: Ep50 (9 klip, 25-09-2026) - QC isi hilang 0 ms, pace 1.90-1.93 kata/detik.

## 7. Pelajaran & jebakan
Lihat PROMPT_KLIKTAHU.txt §11. Tambahan dari rebuild:
- TTS Arena (voice-00): WAV 24 kHz mono, pace alami ~2.2 kata/detik -> atempo ~0.88 memberi ~1.9 kata/detik.
  Kalimat dengan jeda panjang (intro) bisa di bawah target -> dipercepat maks 1.08. Pipeline kerja 48 kHz.
- QC "isi hilang": referensi = klip mentah yang di-atempo UTUH, hasil = potongan referensi yang sama ->
  sejajar per sampel, bandingkan amplop PUNCAK frame 5 ms TANPA toleransi waktu, ambang isi = SIL_DB+3
  (sama dengan pemotong hening). Versi awal (RMS 10 ms, -45 dB, toleransi +-2 frame) meloloskan ekor
  lirih yang dibuang -> ketahuan lewat uji negatif. Uji negatif WAJIB tetap ada di `--uji`.
- Limiter harus sadar TRUE-PEAK (interpolasi 4x, `mesin_util.puncak_antar_sampel`): tanpa itu master
  -1.2 dBFS punya true-peak -0.3 dBTP dan bisa lewat batas setelah AAC.
- SFX tidak bisa didengar agen: periksa lewat spektrogram (`pratinjau/sfx_spektrogram.png`).
- Kamera = kotak sumber `Image.resize(box=..., LANCZOS)` (zoom+geser digabung ke downscale). Transform affine
  di kanvas SS memakan 138 ms/frame -> dibuang; rotasi hanya saat guncang hook. Transisi + HUD digambar di
  resolusi output (D.set_ss(1.0)). Unsharp = kernel 3x3 setara (2x lebih cepat). Hasil: 0.33 s/frame/proses.
- Bloom adaptif harus pakai persentil-90 + porsi piksel terang, bukan rata-rata saja: frame setengah biru
  (penutup transisi) membuat area krem terbakar putih. Ada uji khusus di `mesin_fx.py`.
- Warna penutup transisi = aksen adegan MASUK untuk KEDUA fase (kalau tidak, warna melompat di potongan).
- HUD berwarna aksen hilang di atas penutup transisi -> pil krem di belakang brand + alas bilah progres.
- Kinetik skala 1.5 -> 1 membuat kata menumpuk tetangga -> tiap kata dipotong di JENDELA slotnya sendiri.
- Frame 0 intro harus sudah berisi (kata pertama mulai di t negatif, visual generik intro dimajukan 0.45 s).
- Selftest gerak harus membandingkan juga fase AKHIR (t 3.5 vs 5.8), bukan hanya saat animasi masuk.
- ffmpeg 7: `-c copy -f null` TIDAK mencetak 'frame=' -> hitung frame via `-f framecrc` (qc_mp4.hitung_frame).
  Dengan `set -euo pipefail`, grep kosong mematikan skrip DIAM-DIAM -> render_lokal.sh punya `trap ERR`.
  Jalankan dari start_process dengan `bash -o pipefail -c "... | tee log"` agar kode keluar tidak tertutup tee.
- QC "VO mulai tepat" = lag korelasi-silang MP4 vs stem VO (bukan sampel pertama di atas ambang: SFX transisi
  berbunyi ~0.7 s sebelum narator -> dulu terbaca -680 ms palsu).
- Render per potongan (CHUNK=600) + penanda .ok = bisa dilanjutkan; terukur 0.22-0.26 s/frame efektif
  (2 vCPU, termasuk encoder) -> Shorts 150 s ~35-40 menit. Long 0.25-0.30 s/frame -> 10 menit ~80-90 menit.
- Long: semua HUD di dalam margin 40 px (x 48..1872); zona aman teks 16:9 = 5% (x 96..1824, y 90..1026).
  Audit MP4 membuang titik kecil (bintang latar) lewat opening morfologi; teks diaudit lewat kotak teks.
- Odometer: nol di depan hanya disembunyikan di kiri digit satuan (4,2 pernah tampil ",7").
- Analisis: pencocokan "sudah dibahas" harus KATA UTUH ("ai" != "baterai"); entri "Long:" = boleh jadi Shorts.
- UPGRADE (2026-09-25):
  - `random.randint/choice/sample` BERBEDA antar versi Python (3.11 vs 3.14) -> fixture uji hanya boleh memakai
    `random.random()` (kelas `Acak` di kliktahu/paritas.py). Ketahuan dari CI 3.14.
  - `ruff format` membungkus ulang baris -> patch "replace + assert" harus memakai teks TERKINI (cek dulu dengan grep).
  - `fuzz.token_set_ratio` menganggap subset = identik ("kenapa gunung meletus" = "... ada petir") -> jangan dipakai
    untuk dedup tag/sudut; pakai `fuzz.ratio` atau kata pembeda sudut.
  - Autocomplete nyata penuh DERAU: "aurora ph" (tim esports), "lubang KNALPOT hitam", sudut agama ("menurut islam").
    -> filter relevansi (frasa wajib memuat kata kunci tema/alias), daftar `derau` dan `sensitif` di kanal.toml.
  - "hari tanpa bayangan" hampir TIDAK dicari dalam bentuk pertanyaan (autocomplete kosong) walau momennya dekat.
  - Pageview bulanan artikel sepi melonjak palsu (21 -> 75) -> tren disusutkan pseudo-count 100.
  - Momen berlangsung (tanggal..selesai) wajib dicari dengan kueri IRISAN, bukan `tanggal BETWEEN` (perencana & dasbor
    sempat melewatkan erupsi yang mulai 4 Sep).
  - Hook "padahal kamu melihatnya setiap hari" salah untuk gunung meletus/lubang hitam -> hanya untuk pengalaman sehari-hari.
  - Apostrof harus DIBUANG saat normalisasi ("ka'bah" -> "kabah"); dulu jadi "ka bah" dan lolos daftar sensitif ke tag.
  - CI Python 3.14: angka libm (tanh/log10) beda digit terakhir antar platform -> cek fixture paritas pakai toleransi;
    mypy jangan dipin python_version (stub numpy 2.5 memakai sintaks 3.12+). Log CI dibaca lewat fetch_page URL blob.
  - Jangan push beruntun: kumpulkan perbaikan CI dalam satu push (2026-09-25 sempat 2 push berjarak 4 menit).
- UPGRADE U4 (2026-09-25, sapuan 27 tema tambahan):
  - TABRAKAN AWALAN autocomplete: "kenapa ai" -> 10/10 "kenapa AIR ...", "kenapa mars" -> Marselino/Marshanda. Aturan: bila
    >= 50% saran hanya berawalan kata inti, ambil ulang dengan SPASI di akhir ("kenapa ai ") dan simpan di kunci tanpa spasi.
  - HOMONIM tidak bisa diatasi autocomplete: "gua" = gua batu / "aku" (gaul), "angin duduk"/"masuk angin" (penyakit awam),
    "atlantis land", "kampung gajah", "ai hoshino" -> `TOLAK` & `KONTEKS` per tema di kliktahu/tema.py (bukan derau global:
    "masuk angin" bisa jadi topik tubuh kelak). YouTube menulis "dejavu" satu kata -> ALIAS.
  - Judul Wikipedia di registri WAJIB kanonik: "Astronaut" (alihan) 13 tayangan/bulan vs "Antariksawan" ~250. API pageview
    tidak mengikuti alihan & tidak gagal -> angka kecil diam-diam. Cek via API MediaWiki `action=query&redirects=1`
    (mode online kini otomatis).
  - Kata agama baru di autocomplete: alhamdulillah, najis, adzan, pahala -> ditambahkan ke `sensitif`.
  - Aturan 2 keputusan dulu memakai tanggal MULAI momen -> momen berlangsung tidak pernah didahulukan, dan momen hari ini
    dianggap terkejar padahal produksi butuh 2 hari. Kini: `sisa_momen()` sadar jeda produksi; bila juara skor dilewati,
    alasannya DITULIS di laporan dan juara skor diberi catatan penjadwalan.
  - Peringatan nada bencana dulu hanya untuk momen live -> keputusan tsunami (momen peringatan Palu) TANPA peringatan dan
    hook "Jawabannya lebih seru dari yang kamu kira". Kini tema `BENCANA` selalu mode hormat: hook "Ini penjelasan
    ilmiahnya.", templat sensasional dibuang, baris info resmi (BMKG/InaTEWS, PVMBG/MAGMA), lint GALAT kata sensasi.
  - Gerbang render (`metadata cek`) dulu tidak tahu tema/pilar -> disclaimer kesehatan TIDAK ditegakkan di gerbang. Kini
    tema dibaca dari content.json di folder episode.
  - Perencana dulu mengurutkan momen menurut skor -> tsunami (event 28 Sep) jatuh 29 Sep. Kini: KEPUTUSAN di slot pertama +
    EDF (tenggat terdekat dulu), momen bertanggal tidak pernah dijadwalkan sesudah event.
  - JANGAN `rm data/kliktahu.db` begitu saja: nomor run mulai lagi dari #1 dan arsip `RISET_<tgl>_<mode>_run1.md` tertimpa.
    DB baru -> `python3 -m kliktahu db impor` (ekspor yang di-commit) DULU, baru riset (run berikutnya bernomor lanjut).
  - Statistik laporan harus menghitung kueri BERDATA: mode agen dulu menulis "autocomplete ok (610/610)" padahal hanya 90
    kueri berisi data (kombinasi benih lain memang tidak diambil). Kini "610 (90 berdata)". Sumber ilmiah yang dicatat ke DB
    ikut tersimpan di `data/ekspor/sumber_ilmiah.jsonl` -> `db impor` memulihkannya (tidak perlu dicatat ulang).
- UPGRADE U5 (2026-09-26):
  - `ruff format` mengubah baris sebelum `edit`/`replace` dijalankan -> SELALU cek teks terkini (grep) sebelum
    patch "replace + assert"; skrip patch yang gagal di tengah TIDAK menulis berkas (semua perbaikan hilang).
  - Kandidat topik dari artikel/momen yang tidak terkait kueri bisa menang hanya karena momennya kuat -> kandidat
    harus dibatasi CAKUPAN kueri (yang benar-benar disebut hasil autocomplete), sisanya jadi "sinyal lain".
  - Nama kandidat non-kanonik ("gunung meletus") kehilangan aturan topik (BENCANA/hormat) -> kanonisasi ke nama
    registri SEBELUM dinilai, bukan setelah metadata dibuat.
  - Dua tema cocok pada satu frasa ("gunung meletus TIDUR"): pilih kata kunci TERPANJANG, bukan semua yang cocok.
  - `bool` adalah subclass `int` di Python -> validator angka wajib menolak `True/False` secara eksplisit.
  - `max()` atas generator kosong melempar -> periksa `any(...)` dulu sebelum mencari nilai maksimum bersyarat.
  - mypy menolak `S.bukti(n)[0] if ada else None` -> simpan hasil fungsi yang bisa None ke variabel dulu.
  - Status FIXTURE (data uji) punya pengali keyakinan 0.3: metrik kesegaran evaluasi OFFLINE harus memakai
    `anggap_fixture_segar=True`, bila tidak semua kasus selalu gagal tanpa alasan yang benar.
  - `analisis.jalankan()` mengembalikan KAMUS (bukan objek) -> `evaluasi` menerima kamus maupun objek
    (`_nama_kandidat`, `_status_objek`, `nilai_kelengkapan`) supaya rantai bisa dinilai tanpa impor balik.

- RENDER Ep50 (2026-09-26):
  - WAJIB lihat frame RESOLUSI PENUH tiap adegan (`python3 render.py <slug> --times a,b,c --sheet /tmp/x.jpg`) sebelum
    render panjang. check_layout (margin/HUD/kolom tombol) TIDAK mendeteksi: teks menabrak garis bingkai kotak, dan
    kontras warna teks. Temuan Ep50 (semua diperbaiki sebelum rilis): `D.odometer()` memakai y = BASELINE (bukan
    tengah) -> angka "7,5" naik 21 px & menempel bingkai; glyph "~" Poppins Bold bertinta -0.43..-0.23 em dari
    baseline (sejajarkan pusat tinta dgn pusat angka); label emas gelap(aksen, 0.35) di atas tanah hanya 1.7:1;
    keterangan D.MUTED di atas pasir 3.1:1 (pakai `MUTED_TUA` / D.INK, >= 4.5:1); label 331 px keluar bingkai panel.
  - D.MUTED (128,122,114) hanya 3.5-4.25:1 di latar terang (putih/panel/langit). Episode berikutnya: pertimbangkan
    MUTED global lebih gelap (>= 4.5:1) - ubah SEBELUM render, bukan di tengah (semua potongan berubah).
  - Perbaikan di tengah render: render_lokal memanggil render.py BARU per potongan -> perbaikan adegan untuk potongan
    yang BELUM dirender otomatis terpakai; potongan yang SUDAH jadi: hapus `seg_XXXX.mp4` + `.ok`, jalankan ulang.
    Tentukan potongan terdampak dari WAKTU MUNCUL elemen (beat x durasi adegan timeline), lalu buktikan dengan
    piksel MP4 final di batas potongan (tidak boleh ada lompatan warna).
  - Demuxer concat ffmpeg: potongan hilang = galat tetapi kode keluar 0 -> video terpotong (20 s). Kini render_lokal
    memeriksa semua potongan + `.ok` sebelum gabung, potongan kosong dirender ulang; qc_mp4 tidak crash lagi bila
    frame contoh di luar video (cek baru "frame contoh terbaca").
  - JANGAN jalankan `tools/uji_semua.sh` saat render berjalan: cek kecepatan mesin_fx ("cepat (< 400 ms @1080x1920)")
    GAGAL karena CPU penuh (26-09: 7585 ms) - bukan regresi; semua cek fungsional tetap OK. Ulangi setelah render
    selesai (CPU idle) dan baru laporkan LULUS.
  - MD5 MP4 hanya pembanding di mesin yang SAMA: render ulang penuh di mesin sandbox lain (Xeon AVX-512, 0.24-0.31
    s/frame) memberi MD5 e0810145 (render pertama 22ec6ce1; dugaan kuat: jalur SIMD numpy beda per CPU - render
    pertama juga gabungan potongan dari beberapa tahap perbaikan, tanpa elemen yang diubah). Di satu mesin piksel
    deterministik (uji 26-09: 30 frame f1, PYTHONHASHSEED 1 vs 987 -> md5 sama). Yang wajib: QC MP4 LULUS + lihat
    frame perbaikan.
  - PERENCANA (ditemukan 26-09, BELUM diperbaiki; jangan commit KALENDER/DASBOR hasil `rencana` ulang dulu):
    (1) slot `terkunci` tidak tampil di KALENDER.md (tulis_md hanya menulis usulan) & pola jam 11.30/18.30 bergeser;
    (2) `rencana` pada 26-09 memindah gunung berapi (#1, peluang 67.9) dari 29/09 ke 09/10: momen erupsi (mulai 4 Sep)
    keluar jendela momen -> dipasangkan ke Hari Pengurangan Risiko Bencana 13 Okt. Sebelum Ep51: cek MAGMA/PVMBG
    terbaru, perbaiki perencana (tampilkan slot terkunci/episode render, momen berlangsung), baru buat ulang kalender.
    Kalender 25-09 (Ep50 tsunami 28/09 11.30) tetap berlaku.

## 8. Log perubahan
- 2026-09-25: Tahap 1 - struktur repo, requirements, fonts Poppins (via GitHub API), .gitignore, AGEN.md, PUSTAKA.md.
- 2026-09-25: Audisi suara (dimajukan dari tahap 8) -> voice-00 terkunci; klip referensi suara/referensi_narator.wav.
- 2026-09-25: Tahap 2 - process_audio (QC keutuhan + uji negatif), build_timeline, build_audio, master_audio
  (-14 LUFS, true-peak -1.2, ducking SFX), sfx.py (29 bunyi sintetis). Episode uji: episodes/demo_langit.
- 2026-09-25: Tahap 3 - diagrams.py (primitif SDF anti-alias, teks ter-cache + KOTAK_TEKS, ikon bentuk, 10 visual
  generik), render.py (lapisan frame, CLI --range/--outdir/--pipe/--times/--sheet, multiproses), check_layout.py
  (audit margin/zona + --uji negatif), mesin_util (preview_times, ink_report, sheet).
- 2026-09-25: Tahap 4 - mesin_fx (finishing adaptif, kamera nois/beat, kaca cair, bayang, bokeh, mesh, odometer,
  14 transisi fase), mesin_v11 (kinetik + stabilo, stiker, penanda FAKTA, events/BEATS, layout intro/fact/outro),
  mesin_v11_ep00 (pola modul episode: visual hamburan00 + tabel beat bernama).
- 2026-09-25: Tahap 5 - qc_mp4.py (stream, durasi, korelasi, VO per adegan, puncak, montase, margin),
  tools/render_lokal.sh (prep -> audit -> render per potongan ke libx264 BT.709 -> gabung -> mux -> QC -> dist/).
  Demo KlikTahu_Demo_Langit.mp4 (15.23 s, 12.6 MB) LULUS QC.
- 2026-09-25: Tahap 6 - long/mesin_long.py (align DP kata, Ctx, komponen, kartu bab, HUD), render_long.py,
  audio_long.py, long/demo_bintang (visual.py + BEATS terkunci kata + thumbnail.py). Demo 28.7 s LULUS QC.
- 2026-09-25: Tahap 7 - analisis/ umum + v3 sapuan, v4 peta, v5 real-time (velocity, momen, pabrik metadata),
  v6 strategi 0-100 (+ kalender 7 episode, sudut, hook, loop performa). Semua --uji lulus. momen.json dari
  BMKG (hari tanpa bayangan) + kalender astronomi. tools/uji_semua.sh (11 selftest, 13 s) + .github/workflows/uji.yml.

- 2026-09-25: UPGRADE U1 (commit 3622692) - kanal.toml, kliktahu/{kanal,teks,tema,skema,db,sinkron,skor,paritas,astro,momen},
  skema turunan (SQLite/Postgres+RLS/JSON Schema/TypeScript), TS 7.0.2 + paritas rumus 760 kasus.
- 2026-09-25: UPGRADE U2 (commit 8336e84) - riset real-time v7 (12 sumber, klien HTTP/2 retry+rate limit+cache, mode
  online/uji/agen), keputusan, metadata + lint + gerbang render_lokal.sh, pustaka, perencana+ICS, dasbor, CLI, 38 tes.
- 2026-09-25: UPGRADE U3 - riset NYATA mode agen (162 saran Google, 115 YouTube, 15 pageview Wikipedia, Google Trends,
  berita PVMBG) -> keputusan gunung berapi; perbaikan dari data nyata (lihat §7); dependensi dipin versi 25-09-2026.
- 2026-09-25: VERIFIKASI - pasang bersih venv baru (requirements-dev.txt + npm ci) -> tools/uji_semua.sh LULUS; render
  regresi demo_langit penuh (render_lokal.sh) dengan dependensi baru -> QC MP4 LULUS identik (15.23 s, 12.6 MB, korelasi
  1.0000, isi hilang 0 ms, 0.24-0.28 s/frame); gerbang METADATA diuji 3 kasus (tidak ada/gagal lint = exit 4, lulus = render).
- 2026-09-25: UPGRADE U4 - sapuan data nyata 27 tema tambahan (44 tema: 46 kueri Google, 44 YouTube, 42 pageview
  Wikipedia + berita tsunami/BMKG) -> run #2 agen; relevansi TOLAK/KONTEKS/ALIAS, judul wiki kanonik (+ ikuti alihan
  otomatis di mode online), kata sensitif agama, domain kredibel (esdm/bnpb/aps/agu/wiley/springer/pnas), keputusan sadar
  jeda produksi + transparan, mode hormat tema bencana (hook/judul/deskripsi/lint), sudut sadar momen & tolak sudut generik,
  nama diri/singkatan di hook & judul, gerbang render membaca content.json, perencana KEPUTUSAN-dulu + EDF, dasbor
  menampilkan jadwal keputusan; momen kurasi + peringatan tsunami Palu 28 Sep; 61 tes.
- 2026-09-26: RENDER Ep50 tsunami Palu (lokal, 2 vCPU, 0.17-0.23 s/frame, SS 1.5): 8849 frame @ 60 fps. Sebelum rilis:
  label "M 7,5" (baseline + dipusatkan), "~10 m" (pusat tinta), kontras 4 label (MENCAIR 1.7 -> 7.9:1, keterangan
  3.1/3.7 -> 5.6-6.6:1), label f3 di dalam panel -> check_layout BERSIH -> QC MP4 LULUS (147.48 s, 121.7 MB, -14.2 LUFS,
  TP -1.2 dBTP, korelasi 1.0000, isi hilang 0 ms, MD5 22ec6ce1; render ulang identik byte). Ketahanan: render_lokal
  cek potongan sebelum gabung, qc_mp4 tahan frame di luar video. PUSTAKA/DB: Ep50 status render, tayang 2026-09-28.
- 2026-09-26 (lanjutan): reset sandbox #6 menghapus MP4 -> render ulang PENUH dari d20af21 (mesin lain, 43 menit) ->
  QC MP4 LULUS dengan angka sama (147.48 s, korelasi 1.0000, puncak -1.13 dBFS, VO 0 ms / isi hilang 0 ms), 121.8 MB,
  MD5 e0810145 (beda dari 22ec6ce1, dugaan kuat karena mesin berbeda; lihat §7). Frame perbaikan (M 7,5 /
  MENCAIR / ~10 m / atau lebih) dicek di MP4 final. uji_semua LULUS (52 s, CPU idle). Catatan: jangan jalankan
  uji_semua saat render.
- 2026-09-26 (UPGRADE U5): 12 tahap rencana upgrade 2026-09 (RENCANA_UPGRADE_2026_09.md) diimplementasikan:
  validasi input & provenance (kredibilitas tidak pernah bawaan True); status & kesegaran sumber (live/cache/
  kedaluwarsa/offline/fixture + TTL per jenis); lapisan pencarian multi-sumber `cari.py` (21 adaptor, kuota,
  rantai cadangan, dedup, isolasi kegagalan) + 3 sumber baru terverifikasi (Crossref, Open-Meteo, Wikipedia
  teratas); penemuan topik dengan kanonisasi nama registri & laporan batas registri; verifikasi klaim
  (fakta/inferensi/sinyal minat, konflik angka, kemandirian penerbit); skor niche 0-100 + keyakinan + rentang
  (bukan peluang sukses) dengan komponen biaya produksi; paket `meta/` untuk judul (sudut + bukti + uji bahasa),
  deskripsi (setia bukti, provenance, tanggal riset), hashtag (relevan, aturan platform), tag (variasi nyata,
  batas 500); evaluasi offline 6 kasus LULUS + uji live opt-in yang tidak pernah jalan di CI; jejak audit
  `observabilitas.py` (run id, tahap, status, kuota, galat, TANPA rahasia); orkestrator `analisis.py` + CLI
  `cari`/`analisis`/`evaluasi`; pengaturan dipindah ke `[analisis]` di kanal.toml; 106 tes baru (total 194);
  ruff kini menyertakan `tools/` (2 pelanggaran lama diperbaiki).
- 2026-09-26 (lanjutan 2): pemilik "Mana videonya?" - sandbox baru di awal giliran menghapus `dist/` -> render ulang
  ke-3 (mesin lain lagi, 43 menit) -> QC MP4 LULUS angka sama, MD5 ab39da64 (121773203 byte); frame perbaikan dicek.
  Diserahkan lewat tautan unduh sementara (server statis port 8000) + pratinjau 720p di `/home/user/VIDEO_Ep50/`.
- 2026-09-26 (Ep51): pemilik "buat 1 video shorts" -> Ep51 gunung berapi, sudut "kenapa gunung meletus ada petir"
  (juara skor run #2, 67.9). Cek MAGMA/PVMBG NYATA: 69 gunung dipantau (42 Normal/22 Waspada/5 Siaga/0 Awas per
  7 Sep); Anak Krakatau erupsi menerus 4 Sep 23.07 WIB-6 Sep 00.04 WIB (~25 jam), kolom 13-17 km (BRIN/BBC), Level III
  Siaga radius 3 km. Fakta petir vulkanik terverifikasi: fractoemission, triboelektrik (Cimarelli 2014 Geology),
  muatan es, LIVS (Genareau 2015 Geology), rekor Hunga Tonga 590.000 & Anak Krakatau 2018 340.000 (GLD360/Reuters).
  Naskah 9 adegan 261 kata -> VO voice-00 (QC isi hilang 0 ms) -> timeline 153.4 s. `mesin_v11_ep51.py` 8 visual,
  BEATS dikunci kata VO lewat alat BARU `tools/waktu_kata.py`. check_layout BERSIH; METADATA lint LULUS (bab dari
  timeline, 7 sumber). Kontras: `diagrams.luminans/kontras/teks_terbaca` + stiker/chip_pop auto warna teks.
- 2026-09-26 (perencana, PRASYARAT Ep51): dua bug §7 diperbaiki + uji regresi. (a) `momen.skor_momen`: momen live/agen
  yang baru lewat <= 3 hari tetap skor penuh (dulu meluruh -> topik tergeser momen statis jauh/13 Okt). (b) kalender
  kini menampilkan slot 'terkunci'/'selesai' (kolom status) lewat `perencana.baris_kunci`. DB: Ep50='selesai',
  Ep51='terkunci' (tak direncanakan ulang) + ekspor ulang. pytest penuh 198 LULUS; ruff+mypy bersih.
- 2026-09-26 (RENDER Ep51): `tools/render_lokal.sh shorts ep51_gunung_petir` lokal 2 vCPU, 0.22-0.26 s/frame, SS 1.5,
  9204 frame @ 60 fps dalam 2367 s (16 potongan x 600, semua OK sebelum digabung). QC MP4 LULUS: 153.400 s video /
  153.408 s audio, BT.709, AAC 48 kHz, korelasi 0.99999 (delay 0.0 ms), puncak -1.16 dBFS, VO 9 adegan geser +0.0 ms
  & isi hilang 0 ms, frame contoh terbaca, margin 40 px bersih. Master audio -14.10 LUFS / TP -1.20 dBTP / 73 SFX /
  VO turun 0.00 dB / korelasi VO~mix 1.000. Hasil 125.9 MB (125857742 byte), MD5 c53f3bf172b0dcd9ce249d1ae5961d62.
  Diserahkan: tautan unduh sementara (server statis port 8000, folder `dist/`) + pratinjau 720p
  `/home/user/VIDEO_Ep51/KlikTahu_Ep51_Gunung_Petir_720p.mp4`. PUSTAKA/DB: Ep51 status render -> rencana 'selesai',
  jadwal tayang Sen 29 Sep 2026 18.30 WIB. MP4 TIDAK masuk repo (gitignore `*.mp4`).
- 2026-09-26 (ARSIP Ep51): pemilik "Taruh saja di github!" -> aturan lama digeser untuk Ep51. Dicoba dulu
  `gh release create` + aset (gagal: uploads.github.com EOF/terblokir) dan LFS batch API (href S3
  github-cloud/lfs.github.com tak terjangkau). Blob > 100 MB pasti ditolak push -> MP4 dibelah
  `split -b 70M` jadi 2 bagian (73400320 + 52457422 byte) di `arsip_video/ep51_gunung_petir/` + README.md
  cara gabung; concat diverifikasi identik (SHA-256 6cc2b9b2..., MD5 c53f3bf1...). Push 424dc96 diterima
  (hanya peringatan GH001/50 MB, bukan penolakan). Halaman rilis Ep51 dibuat tanpa aset (dokumentasi +
  tautan arsip): releases/tag/Ep51.

### 11c. Analisis mendalam (UPGRADE U5 - `kliktahu/analisis.py`)

- `python3 -m kliktahu cari "<kueri>" [--jenis saran,ilmiah] [--sumber <id>] [--json]` - satu kueri ke semua sumber
  (mode `uji`/`agen` bila internet sandbox terblokir; `online` di komputer biasa).
- `python3 -m kliktahu analisis "<kueri>" [--mode online|agen|uji] [--tema <tema registri>]` - rantai penuh:
  kumpulkan -> sahikan -> temukan -> buktikan -> nilai -> putuskan -> metadata -> jejak. Hasil:
  `laporan/ANALISIS.md` (+ `laporan/_uji/` pada mode uji) dan jejak `data/audit/analisis_<tanggal>.jsonl`.
- `python3 -m kliktahu evaluasi` - nilai rantai atas `data/evaluasi/kasus.jsonl` (relevansi, dukungan klaim,
  kesegaran, kelengkapan, biaya) -> `laporan/EVALUASI.md`. Live hanya dengan `--live --izin-live` + env
  `KLIKTAHU_LIVE=1`, TIDAK pernah di CI/cron.
- Jebakan yang sudah diatasi: kandidat dari artikel/momen yang tidak disebut kueri dikeluarkan dari keputusan
  ("kenapa bintang berkedip" tidak dijawab "gempa bumi"); "gunung meletus" disatukan ke "gunung berapi" supaya
  aturan topik bencana berlaku; kata kunci terpanjang menang saat dua tema cocok satu frasa ("gunung meletus
  TIDUR" bukan topik mimpi & tidur); judul berita tidak dijadikan nama topik (bising).

## 9. Cara uji cepat (semua harus LULUS)
```
python3 sfx.py                 # katalog SFX + cek deterministik
python3 process_audio.py --uji # QC keutuhan (sintetis + uji negatif + klip TTS asli)
python3 diagrams.py            # selftest semua visual (gerak, zona teks)
python3 check_layout.py --uji  # audit zona harus menangkap pelanggaran sengaja
python3 mesin_fx.py            # finishing, 14 transisi (identitas di ujung fase), material
python3 mesin_v11.py           # BEATS konsisten, layout kinetik, events
bash tools/uji_semua.sh        # SEMUA: 11 selftest + kanal + skema + pytest + ruff + mypy + TypeScript (~35 s)
npm ci --prefix skema/ts       # sekali, agar uji TypeScript ikut jalan
python3 process_audio.py demo_langit && python3 build_timeline.py demo_langit \
  && python3 build_audio.py demo_langit && python3 master_audio.py demo_langit
```

## 10. Cara pakai (ringkas)
**Episode Shorts baru (hanya bila pemilik memerintah):**
1. Analisis -> pilih topik (lihat §11). 2. `episodes/epNN_slug/{content.json, config.env}` (+ `mesin_v11_epNN.py`
   untuk visual khusus; pola lihat `mesin_v11_ep00.py`). 3. VO: satu klip per adegan `audio_raw/<id>.wav` dengan
   voice-00 (maks 10 klip TTS per giliran agen). 4. `tools/render_lokal.sh shorts epNN_slug prep` -> periksa
   `build/<slug>/check_layout.jpg` + `python3 render.py <slug> --times auto --sheet` (baca gambarnya!).
5. METADATA.md 4 blok + `pustaka/EpNN_Nama/SIAP_TEMPEL.md` + PUSTAKA.md + AGEN.md SEBELUM render:
   `python3 -m kliktahu pustaka tambah --format shorts --tema "<tema>" --slug epNN_slug` lalu (setelah prep = timeline ada)
   `python3 -m kliktahu metadata buat --episode epNN_slug --format shorts --kode EpNN --tulis` (judul dari frasa riset,
   bab dari timeline, sumber dari content.json field "sumber" / basis data). render_lokal.sh MENOLAK render (exit 4)
   bila METADATA.md tidak ada / tidak lulus lint (kecuali slug demo_*).
6. Render penuh sebagai proses latar: `bash -o pipefail -c "tools/render_lokal.sh shorts <slug> 2>&1 | tee build/log"`
   -> QC MP4 lulus -> serahkan `dist/<OUT_NAME>/`.
**Video panjang:** `long/<slug>/{content.json (scenes type "bab": id, judul, accent, vo), config.env, visual.py,
thumbnail.py, audio_raw/babN.wav}` -> `tools/render_lokal.sh long <slug> [prep]`.
**Pratinjau cepat:** `python3 render.py <slug> --times 1.0,4.5 --sheet pratinjau/x.jpg`;
Long: `python3 long/render_long.py --slug <slug> --sheet auto`.

## 11. Mesin analisis (analisis/)
- `python3 analisis/v6_strategi.py --mode online|manual` (memanggil v5 -> v4 -> v3). Laporan: `analisis/STRATEGI_V6.md`,
  `REALTIME_V5.md`, `PETA_V4.md`; snapshot `analisis/data/hasil_mendalam_<YYYYMMDD>.json` (di-commit, untuk VELOCITY).
- Sandbox Arena: Google/YouTube/Wikipedia DIBLOKIR -> mode online gagal (pesan [OFFLINE]). Gunakan `--mode manual`
  dengan data dari web search agen:
  - `analisis/data/manual_saran.json`   {"google": {"kenapa pelangi": ["...", ...]}, "youtube": {...}}
  - `analisis/data/manual_wiki.json`    {"<tema>": {"views60": 12345, "tren": 1.2}}
  - `analisis/data/manual_pesaing.json` {"<tema>": {"jumlah": 20, "umur_median_hari": 300, "median_views": 150000,
                                          "judul": ["judul pesaing", ...]}}
  - `analisis/performa.csv`             episode,pilar,views,retensi   (dari YouTube Studio)
  Komponen tanpa data = NETRAL 0.5 dan ditandai "(n)" di laporan.
- Momen dekat (dicek 2026-09-25): **hari tanpa bayangan 9-13 Okt 2026** (Semarang 11 Okt 11.25 WIB, BMKG),
  Orionid 21-22 Okt, supermoon 24 Nov, Geminid 13-14 Des.

### 11b. Mesin riset real-time v7 (kliktahu/riset) - UPGRADE 2026-09
- `python3 -m kliktahu riset --mode online` (komputer dengan internet biasa): 12 sumber - Google & YouTube Autocomplete,
  Wikipedia pageview, Google News RSS, GDELT, Google Trends harian, YouTube Data API (bila `YOUTUBE_API_KEY`), BMKG, USGS,
  NOAA SWPC, JPL CAD, NASA EONET, OpenAlex/Europe PMC, Brave/SearXNG (opsional). Sopan: rate limit, retry, cache 12 jam.
- Sandbox Arena: `--mode agen --agen analisis/data/agen/<file>.json` (format di kliktahu/riset/agen.py). Agen mengisi file
  dengan fetch_page: `https://suggestqueries.google.com/complete/search?client=firefox&hl=id&gl=id&q=kenapa%20<inti>`
  (+`&ds=yt`), `https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/id.wikipedia/all-access/user/<Judul>/monthly/<awal>/<akhir>`,
  `https://trends.google.com/trending/rss?geo=ID`, web_search untuk momen live. Kunci kueri HARUS persis "<benih> <kata>".
- `--mode uji` = internet palsu deterministik (jalur HTTP penuh). Laporan: `laporan/RISET.md` (+arsip), basis data +
  ekspor JSONL. Lalu: `python3 -m kliktahu rencana` (KALENDER.md + kalender.ics), `python3 -m kliktahu dasbor --png`.
- Skor: rumus prompt v3-v6 (kliktahu/skor.py, satu implementasi, dipakai juga analisis/v3-v6) + v7 PELUANG 0-100 =
  26 permintaan + 12 minat + 14 momentum + 16 celah + 12 kecocokan + 10 momen + 5 kesegaran + 5 bukti; KEYAKINAN = porsi
  bobot berdata nyata. Sejak 25-09-2026 `[riset] pesaing = false` (keputusan pemilik): komponen celah KELUAR dari rumus,
  bobot lain dinormalisasi (/0.84) -> peringkat sama, keyakinan tidak lagi terkunci 64% (run berikutnya ~76%).
  Parameter `tanpa` ada di Python & TypeScript (paritas 784 kasus). Nyalakan lagi: `pesaing = true` + YOUTUBE_API_KEY.
- Hasil 25-09-2026 run #1 (17 tema): 1 gunung berapi 73.1 | 2 pesawat 65.2 | 3 pelangi 63.1 (arsip run1).
- Hasil 25-09-2026 run #2 (SEMUA 44 tema segar/long; normalisasi permintaan ikut berubah): 1 gunung berapi 67.9 |
  2 tsunami 65.7 | 3 otak 62.5 | 4 kuku 59.4 | 5 segitiga bermuda 57.7 | 6 pesawat 57.3 | 7 burung 56.7 | 8 darah 55.6.
  KEPUTUSAN tsunami (aturan 2: momen Palu 28 Sep, selisih 2.2 <= 8 poin), sumber: Sassa & Takagawa 2019 (Landslides),
  Ho dkk. 2021 (AGU), NOAA, BMKG InaTEWS. Kalender: Ep50 tsunami Sen 28/09 11.30 | Ep51 gunung berapi | Ep52 kuku |
  Ep53 galaksi (Pekan Antariksa 4-10 Okt) | Ep54 segitiga bermuda | Long03 otak (Sab 3 Okt).
- Metodologi agen (WAJIB sama untuk semua tema agar adil): "kenapa <kata inti>" di Google DAN YouTube + pageview bulanan
  judul kanonik; aturan tabrakan awalan (lihat §7); sumber ilmiah tema terpilih dicatat ke DB SETELAH run
  (`db.simpan_sumber`, kredibel dihitung dari domain) agar komponen bukti tetap netral bagi semua tema.

### 11d. Analisis dengan data NYATA (26-09-2026) - jawaban untuk "jalankan analisis di GitHub"

**Riset online TIDAK boleh dijalankan di GitHub Actions.** Aturan §3 di atas dan PROMPT §3: Actions hanya uji
ringan (< 5 menit, `contents: read`, tanpa cron, tanpa scraping). Menjalankan riset Google/YouTube/Wikipedia
dari Actions persis pola yang membuat akun lama pemilik di-flag. Yang BOLEH dan SUDAH jalan di GitHub:
`.github/workflows/uji.yml` menjalankan `tools/uji_semua.sh` (offline, fixture) setiap push ke `arena/**`.

Jalur untuk data nyata adalah **mode agen** (§11b), dan sudah dipakai penuh pada 26-09-2026:

1. Agen mengambil data sendiri dengan `fetch_page` / `web_search` (bukan data karangan).
2. Data ditulis ke `analisis/data/agen/riset_20260926.json` (ter-commit, bisa diaudit siapa pun).
3. `python3 -m kliktahu analisis "kenapa gunung meletus" --mode agen --agen analisis/data/agen/riset_20260926.json
   --tema "gunung berapi"` -> mesin memprosesnya dengan RUMUS YANG SAMA persis seperti mode online.

Sumber yang TERBUKTI bisa diakses agen (dicek 26-09-2026): `suggestqueries.google.com/complete/search`
(+`&ds=yt`), `wikimedia.org/api/rest_v1/metrics/pageviews/...`, `api.crossref.org`,
`data.bmkg.go.id/DataMKG/TEWS/autogempa.xml`, `trends.google.com/trending/rss?geo=ID`, `web_search`.
Yang GAGAL: `export.arxiv.org/api/query` (HTTP 500) - jangan dipakai.
**Jebakan:** `sort=published&order=desc` di Crossref mengembalikan jurnal predator ber-tahun 2109/2121.
Pakai urutan relevansi (bawaan), lalu saring tahun.

**Hasil run data nyata 26-09-2026 (5 tema, 15 kueri autocomplete, 5 judul Wikipedia, 12 DOI):**

| kueri | topik | skor | momentum | catatan |
|---|---|---|---|---|
| kenapa gunung meletus | gunung berapi (bumi) | **87.3** (yakin 92%) | 1.00 | pageview 813 (Agu) -> 2202 (Sep, hari ke-26) |
| kenapa kuku | kuku (tubuh) | 72.4 | 0.64 | stabil |
| kenapa otak | otak (tubuh) | 72.3 | 0.54 | stabil |
| kenapa pelangi | pelangi (bumi) | 67.9 | 0.35 | menurun |
| kenapa aurora | aurora (antariksa) | 65.0 | 0.42 | autocomplete tercemar (aurora = pemain esports) |

Konteks lonjakan gunung berapi (nyata, bukan angka kosong): Semeru erupsi 26 Sep 08:21 WIB (kolom ±700 m),
rangkaian erupsi 22.00-24.00 WIB malam sebelumnya, G. Ibu & Ili Lewotolok berulang, Anak Krakatau Level III
(Siaga) sejak 2 Juli 2026. Peringatan bencana otomatis aktif: arahkan ke PVMBG/MAGMA Indonesia.

**5 bug yang BARU terlihat saat data asli dipakai** (semua diperbaiki + uji regresi; ini sebabnya fixture
tidak cukup - fixture tidak pernah melonjak, tidak pernah berisi jam, tidak pernah punya berita nyata):

1. `PencariAgen` mengabaikan bagian `wiki` & `berita` -> laporan mengatakan "momentum 0.50 (tanpa data)"
   padahal datanya ada. Sekarang dibaca, dan `ringkas()` melaporkan sumber yang terpakai (dulu selalu "0/0").
2. Lonjakan Wikipedia tidak pernah masuk rumus momentum (argumen di-hardcode `None`) - berlaku juga untuk
   mode online. Sekarang `lonjakan_z` dipakai: pada run ini momentum gunung berapi 0.50 -> 1.00, skor 79.3 -> 87.3.
3. Tema momen live diisi dari **nama kandidat** (bukan dari sumber momen) -> lingkaran yang menguatkan diri:
   momen Semeru diklaim kandidat "gunung erebus di antartika semburkan" hanya karena sama-sama ada kata
   "gunung", dan kandidat itu MEMENANGKAN keputusan. Sekarang tema diambil dari `mentah` sumber atau isi
   judulnya sendiri, dan klaim momen butuh >= 2 kata isi.
4. Gerbang cakupan kueri lolos dengan satu kata umum ("hari") -> kandidat momen kalender ikut memutuskan
   jawaban atas kueri yang tidak menyebutnya. Sekarang butuh kecocokan frasa utuh (atau >= 2 kata isi).
5. Pencatat `pencari.pakai` (kumulatif) dicatat dua kali -> laporan menulis "203 permintaan" padahal 111;
   dan `nama_pendek` memotong jam: "Gunung Semeru erupsi 08:21 WIB" jadi "Gunung Semeru erupsi 08",
   memicu peringatan palsu "angka 08 tidak ditemukan di teks bukti".

## 12. Tindakan untuk pemilik
- (Selesai 2026-09-25) push tertunda tahap 5-7 sudah dipulihkan & di-push ulang (sandbox sempat reset ke commit awal).
- (Selesai 2026-09-25 15.20 UTC) push tertunda 13.00 UTC dipulihkan: sandbox reset lagi ke commit awal -> tambah
  refspec arena, `git fetch`, `git reset --mixed origin/arena/...`, commit dibuat ulang dari working tree (mypy tanpa
  pin, apostrof ka'bah, catatan AGEN), paket dipasang ulang (`pip install -r requirements-dev.txt`, `npm ci`), uji LULUS.
- (Diputuskan 25-09-2026) repo tetap PUBLIK; analisis pesaing / YOUTUBE_API_KEY TIDAK diperlukan.
- Ep50 (SIAP): unggah `KlikTahu_Ep50_Tsunami_Palu.mp4` (unduh lewat tautan unduh sementara saat agen menyerahkan;
  file hilang dari sandbox setelah giliran selesai -> bila terlewat: minta render ulang, atau jalankan sendiri
  `tools/render_lokal.sh shorts ep50_tsunami_palu` di komputer dengan Python 3.11+ & `pip install -r requirements.txt`)
  Sen 28 Sep 2026 11.30 WIB; judul/deskripsi/tag/bab/komentar sematan dari `pustaka/Ep50_Tsunami/SIAP_TEMPEL.md`
  (+ `METADATA.md`). Setelah tayang: `python3 -m kliktahu pustaka status Ep50 rilis --youtube-id <id>`.
- Ep51 (SIAP): unggah `KlikTahu_Ep51_Gunung_Petir.mp4` (tautan unduh sementara port 8000 saat agen menyerahkan;
  bila sandbox sudah reset: minta render ulang atau jalankan `tools/render_lokal.sh shorts ep51_gunung_petir`)
  Sen 29 Sep 2026 18.30 WIB; judul/deskripsi/tag/bab/komentar sematan dari `pustaka/Ep51_Gunung_Berapi/SIAP_TEMPEL.md`
  (+ `METADATA.md`). Judul terpilih: "Kenapa Gunung Meletus Ada Petir? Ini Jawaban Sainsnya".
  Setelah tayang: `python3 -m kliktahu pustaka status Ep51 rilis --youtube-id <id>`.
- (Opsional) loop performa: ekspor CSV YouTube Studio (Analytics > Advanced mode > Export) lalu
  `python3 -m kliktahu pustaka impor-studio <file.csv>` -> bobot pilar menyesuaikan otomatis.
- (Opsional, DISARANKAN) jalankan analisis NYATA di komputer dengan internet biasa (sandbox memblokir hampir semua
  host riset): `python3 -m kliktahu analisis "kenapa <topik>" --mode online` lalu `python3 -m kliktahu evaluasi
  --live --izin-live` (butuh env `KLIKTAHU_LIVE=1`) - ini satu-satunya cara membuktikan rantai terhadap data pasar.
- (Opsional) cermin awan Bolt Database/Supabase: jalankan `skema/postgres.sql`, set env URL+KEY, `python3 -m kliktahu sinkron dorong`.
- Bila ingin sapuan autocomplete nyata: jalankan `python3 analisis/v3_sapuan.py` di komputer dengan internet biasa,
  commit snapshot `analisis/data/hasil_mendalam_*.json`.
