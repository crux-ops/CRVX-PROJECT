# CRVX-PROJECT - mesin produksi & riset KlikTahu

Mesin produksi video edukasi channel YouTube **KlikTahu** (fakta sains & misteri, bahasa Indonesia):
YouTube Shorts 1080x1920 60 fps dan video panjang 1920x1080 30 fps, motion graphics tanpa tokoh,
VO + SFX sintetis (tanpa musik, tanpa subtitle) - plus lapisan **data & riset real-time** (upgrade September 2026):
basis data, riset topik 12 sumber, keputusan niche/topik, generator metadata, perpustakaan, perencana, dasbor.

- Spesifikasi lengkap pemilik: `PROMPT_KLIKTAHU.txt` - Memori & status agen: `AGEN.md` - Indeks episode: `PUSTAKA.md`
- Pengaturan kanal (merek, topik diblokir, jadwal, aturan metadata, riset): `kanal.toml`

```bash
pip install -r requirements-dev.txt     # versi terbaru per 25-09-2026, dipin persis (render cukup 3 paket inti)
npm ci --prefix skema/ts                # opsional: uji tipe TypeScript + paritas rumus skor
bash tools/uji_semua.sh                 # SEMUA uji (11 selftest mesin + pytest + ruff + mypy + TypeScript), tanpa render
```

Render dilakukan di sandbox/komputer lokal (`tools/render_lokal.sh`), BUKAN di GitHub Actions. Actions hanya uji ringan.

## Navigasi (tanpa aplikasi/server - satu CLI)
| Perintah | Isi |
|---|---|
| `python3 -m kliktahu riset --mode online\|agen\|uji` | riset real-time v7 -> papan peluang, keputusan niche/topik, draf metadata, `laporan/RISET.md` |
| `python3 -m kliktahu metadata buat --episode <slug> --tulis` / `metadata cek <file>` | 3 judul, deskripsi (bab dari timeline + sumber), hashtag, tag <= 500; lint (gerbang render) |
| `python3 -m kliktahu pustaka daftar\|cari\|tambah\|status\|impor-studio\|duplikat` | perpustakaan episode (SQLite + FTS5), impor CSV YouTube Studio |
| `python3 -m kliktahu rencana` / `momen` / `astro` | kalender konten (`laporan/KALENDER.md` + `kalender.ics`), momen (kurasi + astronomi + live) |
| `python3 -m kliktahu dasbor --png` | dasbor kanal: terminal + `laporan/DASBOR.md` + `laporan/dasbor.png` |
| `python3 -m kliktahu kanal` / `db` / `skema` / `sinkron` | cek pengaturan, basis data (ekspor/impor JSONL), turunan skema, cermin Bolt Database/Supabase |

## Cara mesin memutuskan (ringkas)
- **Data sama untuk semua tema**: autocomplete Google + YouTube ("kenapa <kata inti>") + pageview Wikipedia (judul kanonik).
  Frasa dihitung hanya bila MEMBAHAS tema (kata utuh, alias, tolak homonim, kata ambigu butuh konteks); topik diblokir
  dibuang dari data, kata sensitif tidak pernah masuk judul/tag/hook.
- **Skor v7** 0-100 (permintaan, minat, momentum, kecocokan, momen, kesegaran, bukti; celah pesaing hanya bila
  `[riset] pesaing = true`) + **keyakinan** = porsi bobot yang didukung data nyata.
- **Momen yang tidak datang dua kali** didahulukan bila selisih <= 8 poin DAN masih terkejar jeda produksi; bila juara
  skor dilewati, alasannya ditulis di `laporan/RISET.md`.
- **Tema bencana** (gempa, tsunami, gunung api, badai) selalu mode hormat: tanpa kata sensasi, info resmi BMKG/PVMBG di
  deskripsi, lint menolak nada sensasi.
- **Kalender**: keputusan riset = slot Shorts pertama, lalu tenggat momen terdekat dulu (tidak pernah sesudah event).
- **Gerbang render**: `METADATA.md` harus lulus lint (tema dibaca dari `content.json` -> disclaimer kesehatan & nada bencana).

## Struktur singkat
| Bagian | File |
|---|---|
| Audio | `process_audio.py`, `build_timeline.py`, `build_audio.py`, `master_audio.py`, `sfx.py` |
| Visual Shorts | `render.py`, `diagrams.py`, `mesin_v11.py` (+ `mesin_v11_epNN.py`), `mesin_fx.py`, `mesin_util.py` |
| QC | `check_layout.py`, `qc_mp4.py`, `tools/uji_semua.sh` |
| Render | `tools/render_lokal.sh <shorts\|long> <slug> [prep]` (gerbang METADATA sebelum render) |
| Video panjang | `long/mesin_long.py`, `long/render_long.py`, `long/audio_long.py`, `long/<slug>/` |
| Data & riset (baru) | `kliktahu/` - `db.py`, `skema.py`, `skor.py`, `astro.py`, `momen.py`, `riset/`, `metadata.py`, `pustaka.py`, `perencana.py`, `dasbor.py`, `sinkron.py` |
| Skema & tipe | `skema/sqlite.sql`, `skema/postgres.sql`, `supabase/migrations/`, `skema/json/`, `skema/ts/` (TypeScript + paritas) |
| Analisis lama (rumus prompt) | `analisis/v3_sapuan.py` ... `analisis/v6_strategi.py` (memakai `kliktahu/skor.py`) |
| Uji | `tests/` (pytest), selftest `--uji` tiap modul, `.github/workflows/uji.yml` (Python 3.11 + 3.14, Node 24) |
