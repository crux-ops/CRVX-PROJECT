# AGEN.md - memori jangka panjang agen produksi KlikTahu

Spesifikasi induk: `PROMPT_KLIKTAHU.txt` (baca dulu). Dokumen ini = keadaan terkini + keputusan yang sudah dikunci.

## Keputusan terkunci
- **Suara narator: `voice-00`** (audisi 2026-09-26, dipilih pemilik; pria, id-ID, narator edukasi).
  Pakai SELAMANYA untuk semua Shorts dan Long. Jangan ganti.
- Nomor episode: Shorts terakhir **Ep50** (cegukan). Long terakhir Long02 (repo lama).
- Repo ini: `crux-ops/CRVX-PROJECT`, branch kerja `arena/01a0dc8d-crvx-project`. MP4 tidak pernah masuk repo.
- Font Poppins diunduh lewat `gh api repos/google/fonts/contents/ofl/poppins/...` (raw.githubusercontent diblokir di sandbox).
- pip di sandbox butuh `--break-system-packages`.

## Status mesin (2026-09-26)
| Bagian | Status | Uji |
|---|---|---|
| sfx.py (28 bunyi sintetis) | jadi | `python3 sfx.py` |
| process_audio / build_timeline / build_audio / master_audio | jadi | ep50: isi hilang 0 ms, -14.3 LUFS |
| render.py + mesin_fx.py + diagrams.py + mesin_v11.py + mesin_util.py | jadi | `python3 mesin_fx.py`, `python3 mesin_v11.py` |
| check_layout.py, qc_mp4.py, tools/render_lokal.sh | jadi | ep50 layout BERSIH |
| mesin_v11_ep50.py (8 visual + BEATS) | jadi | montase diperiksa mata |
| long/ (mesin 16:9) | BELUM dibangun | - |
| analisis/ (v3-v6) | BELUM dibangun | - |
| workflow Actions ringan (selftest) | belum | - |

## Cara kerja cepat
```
tools/render_lokal.sh shorts <slug> prep   # audio + timeline + layout + preview (cepat)
tools/render_lokal.sh shorts <slug>        # render penuh (~0.25 s/frame efektif @2 vCPU, ~40 menit) -> dist/
```
Render jalankan sebagai proses latar. Kecepatan: ~0.5 s/frame per proses (SS 1.5, finishing setelah downscale).

## Arsitektur singkat (yang berbeda/perlu diingat)
- `render.py` harus dijalankan sebagai skrip yang mendelegasikan ke modul `render` (sudah): jika tidak, `__main__`
  dan `render` punya SS terpisah -> skala kacau.
- Finishing FX dilakukan SETELAH downscale ke 1080x1920 (lebih cepat, grain di resolusi keluaran).
- `BEATS` didaftarkan oleh modul episode lewat `daftar_beats(visual, {nama: (frac, sfx)})`; fungsi visual memakai
  `beat(visual, nama)` -> animasi, SFX, dan punch kamera (sfx dalam `PUNCH`) sinkron.
- Transisi memakai 2 frame (A/B) di jendela 0.5 s sekitar batas adegan; `trans` di content.json.
- `label(..., bg=WHITE)` untuk teks di atas diagram; semua teks final dicatat ke `CTX['boxes']` untuk audit margin.
- Kotak teks bbox sprite termasuk padding ~4 px: jauhkan >= 12 px dari margin.

## Episode
### Ep50 - Kenapa Kamu Cegukan? (`episodes/ep50_cegukan`)
- 9 adegan, 280 kata, VO 147.7 s, total 161.5 s. Aksen per adegan di content.json. header_badge "TUBUH · REFLEKS".
- Sumber: Mayo Clinic, Cleveland Clinic, NHS, UCL (Whitehead 2019), Straus 2003 BioEssays, Guinness.
- Metadata: `episodes/ep50_cegukan/METADATA.md`, teks tempel: `pustaka/Ep50_Cegukan/SIAP_TEMPEL.md`.

## Pelajaran baru
- Stabilo kata kunci: pusat di y + 0.62*size (anchor 'ma'), tinggi 0.5*size.
- Lensa glotis: gambar celah sebagai poligon lensa (dua bezier), bukan poligon lipatan + kotak (jadi balok).
- `tail_intro` 0.9 (bukan 0.8) agar lolos QC jeda sempit (ekor >= lead_in + 0.3).

## Berikutnya
1. Setelah pemilik menonton Ep50: revisi bila ada, lalu Ep51 dari antrean (piramida / aurora / pelangi).
2. Bangun `long/` dan `analisis/` bila diminta.
