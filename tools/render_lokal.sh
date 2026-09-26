#!/usr/bin/env bash
# tools/render_lokal.sh - render PENUH di sandbox/komputer agen (pengganti GitHub Actions).
#
#   tools/render_lokal.sh <shorts|long> <slug> [prep]
#
# Urutan: prep audio (process_audio -> build_timeline -> build_audio -> master_audio;
#         Long: + align + audio_long + thumbnail) -> audit tata letak
#         -> render per POTONGAN (CHUNK frame) langsung ke libx264 (tanpa PNG di disk; potongan yang sudah
#            jadi dilewati = bisa dilanjutkan bila terputus) -> gabung tanpa encode ulang
#         -> mux AAC 48 kHz +faststart -> qc_mp4 -> salin MP4 + METADATA + SIAP_TEMPEL ke dist/<OUT_NAME>/
# Mode 'prep' berhenti sebelum render (cek cepat).
# Jalankan sebagai proses latar untuk render penuh (Shorts ~25-40 menit di 2 vCPU).
set -euo pipefail
trap 'echo "[GAGAL] render_lokal.sh baris $LINENO: $BASH_COMMAND" >&2' ERR

JENIS="${1:?pakai: render_lokal.sh <shorts|long> <slug> [prep]}"
SLUG="${2:?slug wajib}"
MODE="${3:-full}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
FF="$(python3 -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')"

if [[ "$JENIS" == "shorts" ]]; then
  EPDIR="episodes/$SLUG"; LONGFLAG=""; W=1080; H=1920
else
  EPDIR="long/$SLUG"; LONGFLAG="--long"; W=1920; H=1080
fi
[[ -f "$EPDIR/config.env" ]] || { echo "config tidak ada: $EPDIR/config.env"; exit 1; }
set -a; source "$EPDIR/config.env"; set +a
EPISODE_SLUG="${EPISODE_SLUG:-$SLUG}"
if [[ "$JENIS" == "shorts" ]]; then BDIR="build/$EPISODE_SLUG"; else BDIR="build/long/$EPISODE_SLUG"; fi
OUT_NAME="${OUT_NAME:-KlikTahu_$SLUG}"
JOBS="$(nproc)"
CHUNK="${CHUNK:-600}"
log() { echo "[$(date +%H:%M:%S)] $*"; }

log "== $JENIS $SLUG ($MODE) | FPS ${FPS} SS ${SS} | jobs $JOBS"
log "1/6 prep audio"
python3 process_audio.py "$SLUG" $LONGFLAG
python3 build_timeline.py "$SLUG" $LONGFLAG
if [[ "$JENIS" == "long" ]]; then
  python3 long/render_long.py --slug "$SLUG" --align
fi
python3 build_audio.py "$SLUG" $LONGFLAG
if [[ "$JENIS" == "shorts" ]]; then
  python3 master_audio.py "$SLUG"
else
  python3 long/audio_long.py --slug "$SLUG"
  [[ -f "long/$SLUG/thumbnail.py" ]] && python3 "long/$SLUG/thumbnail.py"
fi

log "2/6 audit tata letak"
if [[ "$JENIS" == "shorts" ]]; then
  python3 check_layout.py "$SLUG"
else
  python3 long/render_long.py --slug "$SLUG" --check
fi

if [[ "$MODE" == "prep" ]]; then
  log "PREP SELESAI (belum render). Periksa montase: $BDIR/"
  exit 0
fi

# GERBANG METADATA (aturan keras §2.4: metadata lengkap SEBELUM render). Episode demo_* dikecualikan (uji mesin).
if [[ "$SLUG" != demo_* ]]; then
  log "cek METADATA.md (4 blok, ASCII, bab dari timeline, sumber, tag <= 500)"
  [[ -f "$EPDIR/METADATA.md" ]] || { log "GAGAL: $EPDIR/METADATA.md belum ada - buat dulu: python3 -m kliktahu metadata buat --episode $SLUG --format $JENIS --tulis"; exit 4; }
  python3 -m kliktahu metadata cek "$EPDIR/METADATA.md" --format "$JENIS" || { log "GAGAL: METADATA.md belum lulus lint - perbaiki sebelum render"; exit 4; }
fi

TOTAL="$(python3 -c "import json;print(json.load(open('$BDIR/timeline.json'))['frames'])")"
SEGDIR="$BDIR/seg"
mkdir -p "$SEGDIR"
log "3/6 render + encode per potongan: $TOTAL frame, potongan $CHUNK"
ENC=(-c:v libx264 -preset "${PRESET:-slow}" -tune "${TUNE:-animation}" -profile:v high -level 4.2
     -vf "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p"
     -colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv
     -b:v "${VBITRATE}" -maxrate "${MAXRATE}" -bufsize "${BUFSIZE}" -g $((FPS * 2)) -keyint_min "$FPS")
T0=$(date +%s)
i=0
for ((LO = 0; LO < TOTAL; LO += CHUNK)); do
  HI=$((LO + CHUNK < TOTAL ? LO + CHUNK : TOTAL))
  SEG="$SEGDIR/seg_$(printf %04d $i).mp4"
  if [[ -s "$SEG" && -f "$SEG.ok" && "$(cat "$SEG.ok")" == "$LO:$HI" ]]; then  # potongan kosong = render ulang
    log "   potongan $i [$LO:$HI] sudah ada - lewati"
  else
    rm -f "$SEG" "$SEG.ok"
    if [[ "$JENIS" == "shorts" ]]; then
      python3 render.py "$SLUG" --pipe --range "$LO:$HI" --jobs "$JOBS" \
        | "$FF" -v error -y -f rawvideo -pix_fmt rgb24 -s "${W}x${H}" -r "$FPS" -i - "${ENC[@]}" -an "$SEG"
    else
      python3 long/render_long.py --slug "$SLUG" --pipe --range "$LO:$HI" --jobs "$JOBS" \
        | "$FF" -v error -y -f rawvideo -pix_fmt rgb24 -s "${W}x${H}" -r "$FPS" -i - "${ENC[@]}" -an "$SEG"
    fi
    N=$(python3 qc_mp4.py --frame "$SEG")
    if [[ "$N" != "$((HI - LO))" ]]; then
      log "GAGAL: potongan $i berisi $N frame, harusnya $((HI - LO))"; exit 1
    fi
    echo "$LO:$HI" > "$SEG.ok"
    EL=$(( $(date +%s) - T0 ))
    log "   potongan $i [$LO:$HI] OK ($N frame) - ${EL}s berlalu"
  fi
  i=$((i + 1))
done
NSEG=$i
# potongan bisa hilang/kosong (dihapus dari luar saat render berjalan, disk penuh). Demuxer concat ffmpeg hanya
# mencetak galat lalu keluar dengan kode 0 -> video TERPOTONG. Periksa semua potongan + penanda .ok dulu.
for ((k = 0; k < NSEG; k++)); do
  SEGK="$SEGDIR/seg_$(printf %04d $k).mp4"
  if [[ ! -s "$SEGK" || ! -f "$SEGK.ok" ]]; then
    log "GAGAL: potongan $k hilang/kosong ($SEGK) - jalankan ulang (potongan lain dilanjutkan)"; exit 1
  fi
done

log "4/6 gabung + mux audio"
LIST="$SEGDIR/daftar.txt"
: > "$LIST"
for ((k = 0; k < NSEG; k++)); do echo "file 'seg_$(printf %04d $k).mp4'" >> "$LIST"; done
"$FF" -v error -y -f concat -safe 0 -i "$LIST" -c copy "$BDIR/video_saja.mp4"
OUT="$BDIR/$OUT_NAME.mp4"
"$FF" -v error -y -i "$BDIR/video_saja.mp4" -i "$BDIR/audio_master.wav" -map 0:v:0 -map 1:a:0 -c:v copy \
  -c:a aac -b:a "${ABITRATE:-256k}" -ar 48000 -ac 2 -movflags +faststart "$OUT"
log "   $OUT ($(du -h "$OUT" | cut -f1))"

log "5/6 QC MP4"
python3 qc_mp4.py "$OUT" --slug "$SLUG" $LONGFLAG

log "6/6 serahkan ke dist/$OUT_NAME/"
DIST="dist/$OUT_NAME"
mkdir -p "$DIST"
cp "$OUT" "$DIST/"
[[ -f "$EPDIR/METADATA.md" ]] && cp "$EPDIR/METADATA.md" "$DIST/"
PUS=$(ls -d pustaka/*/ 2>/dev/null | grep -i "$(echo "$OUT_NAME" | sed 's/KlikTahu_//')" | head -1 || true)
[[ -n "$PUS" && -f "$PUS/SIAP_TEMPEL.md" ]] && cp "$PUS/SIAP_TEMPEL.md" "$DIST/"
[[ -f "$BDIR/thumbnail.jpg" ]] && cp "$BDIR/thumbnail.jpg" "$DIST/"
cp "$BDIR/qc_mp4.json" "$DIST/" 2>/dev/null || true
log "SELESAI: $DIST ($(( $(date +%s) - T0 ))s render+encode)"
ls -la "$DIST"
