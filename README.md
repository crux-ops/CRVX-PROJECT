# CRVX-PROJECT - mesin produksi KlikTahu

Mesin produksi video edukasi channel YouTube **KlikTahu** (fakta sains & misteri, bahasa Indonesia):
YouTube Shorts 1080x1920 60 fps dan video panjang 1920x1080 30 fps, motion graphics tanpa tokoh,
VO + SFX sintetis (tanpa musik, tanpa subtitle).

- Spesifikasi lengkap: `PROMPT_KLIKTAHU.txt`
- Memori & status agen: `AGEN.md`
- Indeks episode: `PUSTAKA.md`

Ketergantungan hanya: `pillow`, `numpy`, `imageio-ffmpeg` (`pip install -r requirements.txt`).
Render dilakukan di sandbox/komputer lokal (`tools/render_lokal.sh`), BUKAN di GitHub Actions.
