# AGEN.md - memori jangka panjang agen KlikTahu

> Baca file ini PERTAMA KALI setiap sesi. Perbarui setiap ada perubahan besar / episode baru.
> Spesifikasi lengkap dari pemilik: `PROMPT_KLIKTAHU.txt` (sumber kebenaran; file ini ringkasan + status).

## 0. Status singkat
- Fase: **mesin SELESAI dibangun ulang (tahap 1-8 lulus uji)**, menunggu perintah episode. Berikutnya: **Ep50** (Shorts), **Long03**.
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
- Satu commit bermakna per tahap; jangan push beruntun dalam hitungan menit.
- Tidak pernah menyimpan token/password di file atau chat.
- **Repo `crux-ops/CRVX-PROJECT` saat ini PUBLIK** (dicek 2026-09-25). Agen tidak punya hak admin untuk
  mengubahnya -> pemilik perlu mengubah ke Private lewat Settings > General > Danger Zone.

## 4. Lingkungan sandbox (dicek 2026-09-25)
- 2 vCPU, RAM 3.8 GB, disk ~20 GB. Python 3.11. `pip install --break-system-packages -r requirements.txt`.
- ffmpeg dari `imageio_ffmpeg.get_ffmpeg_exe()` (v7.0.2; ada atempo, ebur128, alimiter, libx264, aac). Tidak ada ffprobe.
- Internet terbatas: PyPI dan api.github.com BISA; Google, YouTube, Wikipedia, fonts.google, raw.githubusercontent DIBLOKIR.
  -> Font diunduh lewat `gh api repos/google/fonts/contents/ofl/poppins/<file>` (base64).
  -> Analisis tren: pakai alat web search agen, masukkan hasilnya sebagai data manual (lihat analisis/).
- Disk: frame PNG 1080x1920 berbutir ~3-5 MB/frame -> JANGAN simpan semua frame; render per potongan (chunk)
  langsung ke encoder (lihat tools/render_lokal.sh).
- Folder `build/` dan `dist/` tidak ikut snapshot Arena (hilang bila sandbox reset) -> hasil penting segera diserahkan.

## 5. Struktur repo
Lihat PROMPT_KLIKTAHU.txt §4. Konvensi tambahan:
- Artefak per episode: `build/<slug>/` (audio_proc/, timeline.json, vo_track.wav, audio_master*.wav, seg/, sheet).
- Long: `build/long/<slug>/`.
- Hasil serah: `dist/<OUT_NAME>/` (MP4 + METADATA.md + SIAP_TEMPEL.md [+ thumbnail.jpg]).
- `pratinjau/` = gambar pratinjau untuk ditunjukkan ke pemilik (diabaikan git).

## 6. Suara narator (TERKUNCI - jangan diganti)
- Dipilih pemilik 2026-09-25 lewat audisi TTS Arena (battle "00"): **voice_id `voice-00`**.
- Parameter audisi: language `id-ID`, gender `masculine`, use_case `educational`, index 0.
  Kalimat audisi: "Kenapa aurora hanya muncul di dekat kutub, padahal Matahari menyinari seluruh Bumi? ..."
- voice_id Arena berlaku per sesi. Di sesi baru: audisi ulang dengan parameter yang SAMA, lalu pilih kandidat
  yang suaranya sama dengan klip referensi `suara/referensi_narator.wav`. Catat voice_id sesi baru di sini.
- Semua VO Shorts & Long wajib memakai suara ini. Rekam ulang klip = suara yang sama, teks hampir sama.

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

## 9. Cara uji cepat (semua harus LULUS)
```
python3 sfx.py                 # katalog SFX + cek deterministik
python3 process_audio.py --uji # QC keutuhan (sintetis + uji negatif + klip TTS asli)
python3 diagrams.py            # selftest semua visual (gerak, zona teks)
python3 check_layout.py --uji  # audit zona harus menangkap pelanggaran sengaja
python3 mesin_fx.py            # finishing, 14 transisi (identitas di ujung fase), material
python3 mesin_v11.py           # BEATS konsisten, layout kinetik, events
python3 process_audio.py demo_langit && python3 build_timeline.py demo_langit \
  && python3 build_audio.py demo_langit && python3 master_audio.py demo_langit
```

## 10. Cara pakai (ringkas)
**Episode Shorts baru (hanya bila pemilik memerintah):**
1. Analisis -> pilih topik (lihat §11). 2. `episodes/epNN_slug/{content.json, config.env}` (+ `mesin_v11_epNN.py`
   untuk visual khusus; pola lihat `mesin_v11_ep00.py`). 3. VO: satu klip per adegan `audio_raw/<id>.wav` dengan
   voice-00 (maks 10 klip TTS per giliran agen). 4. `tools/render_lokal.sh shorts epNN_slug prep` -> periksa
   `build/<slug>/check_layout.jpg` + `python3 render.py <slug> --times auto --sheet` (baca gambarnya!).
5. METADATA.md 4 blok + `pustaka/EpNN_Nama/SIAP_TEMPEL.md` + PUSTAKA.md + AGEN.md SEBELUM render.
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

## 12. Tindakan untuk pemilik
- **Push tertunda (2026-09-25):** token GitHub sandbox kedaluwarsa setelah tahap 4. Commit tahap 5 dan tahap 6-7
  hanya ada di lokal/snapshot Arena. Setelah koneksi GitHub di Arena diperbaiki: cek `git log`, lalu
  `git push origin <cabang-sesi>`. Workflow `.github/workflows/uji.yml` mungkin butuh izin 'workflows' untuk di-push.
- Ubah repo `crux-ops/CRVX-PROJECT` menjadi **Private** (Settings > General > Danger Zone). Agen tidak punya hak admin.
- Bila ingin sapuan autocomplete nyata: jalankan `python3 analisis/v3_sapuan.py` di komputer dengan internet biasa,
  commit snapshot `analisis/data/hasil_mendalam_*.json`.
