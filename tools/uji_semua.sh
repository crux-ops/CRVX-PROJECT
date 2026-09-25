#!/usr/bin/env bash
# tools/uji_semua.sh - jalankan SEMUA uji ringan (tanpa render penuh). Dipakai lokal & GitHub Actions.
# Gagal satu = gagal semua (exit != 0). Target < 2 menit.
set -euo pipefail
cd "$(dirname "$0")/.."
T0=$(date +%s)
jalan() { echo "== $*"; "$@" | tail -2; }
# --- mesin produksi (tahap 1-7)
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
# --- lapisan data & riset real-time (kliktahu/)
jalan python3 -m kliktahu kanal cek
jalan python3 -m kliktahu skema cek
jalan python3 -m pytest -q tests
if python3 -c "import ruff" 2>/dev/null || command -v ruff >/dev/null; then
  jalan ruff check kliktahu tests
  jalan ruff format --check kliktahu tests
fi
if python3 -c "import mypy" 2>/dev/null; then
  jalan python3 -m mypy
fi
# --- TypeScript: tipe skema + paritas rumus skor (butuh Node >= 22.18)
if command -v node >/dev/null && [[ -d skema/ts/node_modules ]]; then
  (cd skema/ts && jalan npm run --silent build && jalan npm test --silent)
elif command -v node >/dev/null; then
  echo "== (lewati TypeScript: jalankan 'npm ci --prefix skema/ts' sekali untuk memasang typescript)"
fi
echo "SEMUA UJI LULUS ($(( $(date +%s) - T0 )) s)"
