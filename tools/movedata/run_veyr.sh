#!/usr/bin/env bash
# Rebuild Data/dragon/*.json from the two usable Veyr Actions. Headless, one Blender at a time.
# Usage: tools/movedata/run_veyr.sh [extra build_moves.py args]
set -euo pipefail
cd "$(dirname "$0")/../.."
BLENDER="${BLENDER:-blender}"
SAMPLES="${SAMPLES:-Local/movedata/samples}"
run() {  # blend action move
  if pgrep -x Blender >/dev/null; then
    echo "another Blender process is running; refusing to start a second one" >&2; exit 2
  fi
  "$BLENDER" --background --factory-startup "$1" --python tools/movedata/sample_action.py -- \
      --action "$2" --move "$3" --out "$SAMPLES" 2>&1 | grep -E 'MOVEDATA_SAMPLE|Error|Traceback' || true
  test -f "$SAMPLES/$3.sample.npz"
}
run Local/video2rig/dragon/Dragon_Idle_v2r_v2.blend idle_v2 idle
run Local/video2rig/dragon/Dragon_Roar_sd_v2r_v2.blend roar_sd_v2 roar
python3 tools/movedata/build_moves.py "$SAMPLES/idle.sample.npz" "$SAMPLES/roar.sample.npz" \
    --loop idle --out Data/dragon "$@"
