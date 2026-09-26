#!/usr/bin/env bash
# tools/render_lokal.sh <shorts|long> <slug> [prep]
# Render penuh di sandbox (pengganti GitHub Actions). Mode "prep" berhenti sebelum render frame.
set -euo pipefail
MODE=${1:?shorts|long}; SLUG=${2:?slug}; STEP=${3:-full}
cd "$(dirname "$0")/.."
if [ "$MODE" != "shorts" ]; then echo "mesin long belum dibangun di repo ini"; exit 2; fi
set -a; eval "$(python3 -c "
import audio_util,shlex
for k,v in audio_util.load_env('episodes/$SLUG/config.env').items(): print(k+'='+shlex.quote(v))")"; set +a
FF=$(python3 -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())")
BUILD=episodes/$SLUG/build; mkdir -p "$BUILD" dist
echo "== 1. audio"
python3 process_audio.py "$SLUG"
python3 build_timeline.py "$SLUG"
python3 build_audio.py "$SLUG"
python3 master_audio.py "$SLUG"
echo "== 2. tata letak"
python3 check_layout.py "$SLUG" --sheet "$BUILD/layout_check.jpg"
python3 render.py --slug "$SLUG" --times auto --sheet "$BUILD/preview.jpg"
[ "$STEP" = "prep" ] && { echo "prep selesai: $BUILD/preview.jpg"; exit 0; }
echo "== 3. render frame"
JOBS=${JOBS:-$(nproc)}
python3 render.py --slug "$SLUG" --fps "${FPS:-60}" --ss "${SS:-1.5}" --sharpen "${SHARPEN:-52}" --jobs "$JOBS" --outdir "$BUILD/frames"
echo "== 4. encode + mux"
OUT="dist/${OUT_NAME:-$SLUG}.mp4"
"$FF" -y -v warning -stats -framerate "${FPS:-60}" -i "$BUILD/frames/f_%05d.png" -i "$BUILD/audio_master.wav" \
  -c:v libx264 -preset "${PRESET:-slow}" -tune "${TUNE:-animation}" -pix_fmt yuv420p -profile:v high -level 4.2 \
  -b:v "${VBITRATE:-6400k}" -maxrate "${MAXRATE:-11000k}" -bufsize "${BUFSIZE:-16000k}" -g 120 \
  -c:a aac -b:a "${ABITRATE:-256k}" -ar 48000 -movflags +faststart -shortest "$OUT"
echo "== 5. QC"
python3 qc_mp4.py "$OUT" --slug "$SLUG"
cp episodes/$SLUG/METADATA.md "dist/${OUT_NAME:-$SLUG}_METADATA.md" 2>/dev/null || true
P=$(ls -d pustaka/*/ 2>/dev/null | grep -i "$(echo $SLUG | cut -d_ -f1)" | head -1)
[ -n "$P" ] && cp "$P/SIAP_TEMPEL.md" "dist/${OUT_NAME:-$SLUG}_SIAP_TEMPEL.md" || true
ls -la dist/
