#!/usr/bin/env bash
# tools/uji_semua.sh - jalankan SEMUA selftest ringan (tanpa render penuh). Dipakai lokal & GitHub Actions.
# Target < 1 menit. Gagal satu = gagal semua (exit != 0).
set -euo pipefail
cd "$(dirname "$0")/.."
T0=$(date +%s)
jalan() { echo "== $*"; "$@" | tail -2; }
jalan python3 sfx.py
jalan python3 process_audio.py --uji
jalan python3 diagrams.py
jalan python3 check_layout.py --uji
jalan python3 mesin_fx.py
jalan python3 mesin_v11.py
jalan python3 long/mesin_long.py --uji
for m in v3_sapuan v4_peta v5_realtime v6_strategi; do
  jalan python3 "analisis/$m.py" --uji
done
echo "SEMUA SELFTEST LULUS ($(( $(date +%s) - T0 )) s)"
