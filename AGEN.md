# AGEN.md - memori jangka panjang agen KlikTahu

> Baca file ini PERTAMA KALI setiap sesi. Perbarui setiap ada perubahan besar / episode baru.
> Spesifikasi lengkap dari pemilik: `PROMPT_KLIKTAHU.txt` (sumber kebenaran; file ini ringkasan + status).

## 0. Status singkat
- Fase: **membangun ulang mesin dari nol** (belum ada episode baru). Episode berikutnya: **Ep50** (Shorts), **Long03**.
- Jangan membuat video episode sebelum pemilik memberi perintah.

| Tahap | Isi | Status |
|---|---|---|
| 1 | struktur repo, requirements, fonts, .gitignore, AGEN.md | SELESAI |
| 2 | pipeline audio + sfx + QC keutuhan | SELESAI (uji: isi hilang 0 ms, uji negatif lulus) |
| 3 | render.py + diagrams.py + mesin_util + check_layout | SELESAI (demo 3 adegan, audit bersih) |
| 4 | mesin_v11 + mesin_fx | belum |
| 5 | qc_mp4 + tools/render_lokal.sh (demo end-to-end) | belum |
| 6 | mesin Long | belum |
| 7 | mesin analisis v3-v6 + --uji | belum |
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

## 8. Log perubahan
- 2026-09-25: Tahap 1 - struktur repo, requirements, fonts Poppins (via GitHub API), .gitignore, AGEN.md, PUSTAKA.md.
- 2026-09-25: Audisi suara (dimajukan dari tahap 8) -> voice-00 terkunci; klip referensi suara/referensi_narator.wav.
- 2026-09-25: Tahap 2 - process_audio (QC keutuhan + uji negatif), build_timeline, build_audio, master_audio
  (-14 LUFS, true-peak -1.2, ducking SFX), sfx.py (29 bunyi sintetis). Episode uji: episodes/demo_langit.
- 2026-09-25: Tahap 3 - diagrams.py (primitif SDF anti-alias, teks ter-cache + KOTAK_TEKS, ikon bentuk, 10 visual
  generik), render.py (lapisan frame, CLI --range/--outdir/--pipe/--times/--sheet, multiproses), check_layout.py
  (audit margin/zona + --uji negatif), mesin_util (preview_times, ink_report, sheet).

## 9. Cara uji cepat (semua harus LULUS)
```
python3 sfx.py                 # katalog SFX + cek deterministik
python3 process_audio.py --uji # QC keutuhan (sintetis + uji negatif + klip TTS asli)
python3 diagrams.py            # selftest semua visual (gerak, zona teks)
python3 check_layout.py --uji  # audit zona harus menangkap pelanggaran sengaja
python3 process_audio.py demo_langit && python3 build_timeline.py demo_langit \
  && python3 build_audio.py demo_langit && python3 master_audio.py demo_langit
```
