# KlikTahu - mesin produksi (CRVX-PROJECT)

Mesin produksi video channel YouTube **KlikTahu** (fakta sains & misteri, bahasa Indonesia).
Spesifikasi lengkap: `PROMPT_KLIKTAHU.txt`. Memori agen: `AGEN.md`. Indeks episode: `PUSTAKA.md`.

Jalur cepat Shorts:
```
pip install -r requirements.txt
tools/render_lokal.sh shorts ep50_cegukan prep   # audio + timeline + cek tata letak
tools/render_lokal.sh shorts ep50_cegukan        # render penuh -> dist/*.mp4
```
Video (MP4) tidak disimpan di repo.
