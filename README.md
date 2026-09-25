# CRVX-PROJECT - mesin produksi KlikTahu

Mesin produksi video edukasi channel YouTube **KlikTahu** (fakta sains & misteri, bahasa Indonesia):
YouTube Shorts 1080x1920 60 fps dan video panjang 1920x1080 30 fps, motion graphics tanpa tokoh,
VO + SFX sintetis (tanpa musik, tanpa subtitle).

- Spesifikasi lengkap: `PROMPT_KLIKTAHU.txt`
- Memori & status agen: `AGEN.md`
- Indeks episode: `PUSTAKA.md`

Ketergantungan hanya: `pillow`, `numpy`, `imageio-ffmpeg` (`pip install -r requirements.txt`).
Render dilakukan di sandbox/komputer lokal (`tools/render_lokal.sh`), BUKAN di GitHub Actions.

## Struktur singkat
| Bagian | File |
|---|---|
| Audio | `process_audio.py`, `build_timeline.py`, `build_audio.py`, `master_audio.py`, `sfx.py` |
| Visual Shorts | `render.py`, `diagrams.py`, `mesin_v11.py` (+ `mesin_v11_epNN.py`), `mesin_fx.py`, `mesin_util.py` |
| QC | `check_layout.py`, `qc_mp4.py`, `tools/uji_semua.sh` |
| Render | `tools/render_lokal.sh <shorts\|long> <slug> [prep]` |
| Video panjang | `long/mesin_long.py`, `long/render_long.py`, `long/audio_long.py`, `long/<slug>/` |
| Analisis topik | `analisis/v3_sapuan.py` ... `analisis/v6_strategi.py` |

Uji semua (tanpa render): `bash tools/uji_semua.sh`
