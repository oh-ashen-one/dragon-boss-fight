#!/usr/bin/env bash
# Rebuild Data/dragon/*.json from every usable Veyr Action. Headless, Blender one process at a time (this script's own).
# Usage: tools/movedata/run_veyr.sh [extra build_moves.py args]
# Env: BLENDER (binary), SAMPLES (sample dir), BLENDER_CAP (max Blender processes on the machine including this one's, default 1;
#      the shared cap is four, so a machine that already runs a render may set 2).
# Moves are listed below as: blend|action|move|loop(0/1). A missing blend is skipped with a note (so a partial Local/ still builds).
set -euo pipefail
cd "$(dirname "$0")/../.."
BLENDER="${BLENDER:-blender}"
SAMPLES="${SAMPLES:-Local/movedata/samples}"
CAP="${BLENDER_CAP:-1}"
D=Local/video2rig/dragon
MOVES=(
  "$D/Dragon_Idle_v2r_v2.blend|idle_v2|idle|1"
  "$D/Dragon_Roar_sd_v2r_v2.blend|roar_sd_v2|roar|0"
  "$D/Dragon_Collapse_sd_v2r_v2.blend|collapse_v2|collapse|0"
  "$D/Dragon_Death_sd_v2r_v2.blend|death_v2|death|0"
  "$D/Dragon_Bite_sd_v2r_v2.blend|bite_v2|bite|0"
  "$D/Dragon_ClawSwipe_sd_v2r_v2.blend|claw_swipe_v2|claw_swipe|0"
  "$D/Dragon_Stagger_sd_v2r_v2.blend|stagger_v2|stagger|0"
  "$D/Dragon_Land2_sd_v2r_v2.blend|land2_v2|land|0"
  "$D/Dragon_Takeoff2_sd_v2r_v2.blend|takeoff2_v2|takeoff|0"
  "$D/Dragon_Rise_sd_v2r_v2.blend|rise_v2|rise|0"
  "$D/Dragon_IdleLook_sd_v2r_v2.blend|idle_look_v2|idle_look|1"
  "$D/Dragon_IdleLayered_sd_v2r_v2.blend|idle_layered_v2|idle_layered|1"
)
run() {  # blend action move
  if [ "$(pgrep -x Blender | wc -l)" -ge "$CAP" ]; then
    echo "$(pgrep -x Blender | wc -l) Blender process(es) running, cap $CAP; refusing to start another (set BLENDER_CAP to allow)" >&2; exit 2
  fi
  "$BLENDER" --background --factory-startup "$1" --python tools/movedata/sample_action.py -- \
      --action "$2" --move "$3" --out "$SAMPLES" 2>&1 | grep -E 'MOVEDATA_SAMPLE|Error|Traceback' || true
  test -f "$SAMPLES/$3.sample.npz"
}
files=(); loops=()
for m in "${MOVES[@]}"; do
  IFS='|' read -r blend action move loop <<<"$m"
  if [ ! -f "$blend" ]; then echo "skip $move: $blend not found" >&2; continue; fi
  run "$blend" "$action" "$move"
  files+=("$SAMPLES/$move.sample.npz")
  if [ "$loop" = "1" ]; then loops+=(--loop "$move"); fi
done
python3 tools/movedata/build_moves.py "${files[@]}" "${loops[@]}" --out Data/dragon "$@"
