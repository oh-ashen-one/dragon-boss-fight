#!/usr/bin/env bash
# Rebuild Data/dragon/*.json from every usable Veyr Action. Headless, Blender one process at a time (this script's own).
# Usage: tools/movedata/run_veyr.sh [extra build_moves.py args]
# Env: BLENDER (binary), SAMPLES (sample dir), BLENDER_CAP (max Blender processes on the machine including this one's, default 1;
#      the shared cap is four, so a machine that already runs a render may set 2), GPU_SLOT (default ~/.cache/gpu-slot/bin/gpu_slot.sh;
#      every Blender run goes through `gpu_slot.sh capture --label dragon-r3-movedata`, since Blender counts as a GPU client; set
#      GPU_SLOT= to run Blender directly). Exit 75 from the slot (busy) waits 120 s and retries once; a second 75 stops with 75.
# A sample whose recorded action and blend md5 match the listed blend is reused without starting Blender.
# Moves are listed below as: blend|action|move|loop(0/1). A missing blend is skipped with a note (so a partial Local/ still builds).
set -euo pipefail
cd "$(dirname "$0")/../.."
BLENDER="${BLENDER:-blender}"
SAMPLES="${SAMPLES:-Local/movedata/samples}"
CAP="${BLENDER_CAP:-1}"
SLOT="${GPU_SLOT-$HOME/.cache/gpu-slot/bin/gpu_slot.sh}"
D=Local/video2rig/dragon
# Fix round 2 (2026-10-29): nine moves read the v4 Actions (tools/dragon_refine/v4); claw swipe, stagger, death, idle kept.
# Fix round 3 (2026-10-30): roar, collapse, bite, rise and air_land read the v5 Actions (tools/dragon_refine/v4/refine_v5.py);
# land2, air_hover, air_takeoff and air_fire_down stay on v4 (see Local/dragon-review-20261029/measure_v5.json).
MOVES=(
  "$D/Dragon_Idle_v2r_v2.blend|idle_v2|idle|1"
  "$D/Dragon_Roar_sd_v2r_v5.blend|roar_v5|roar|0"
  "$D/Dragon_Collapse_sd_v2r_v5.blend|collapse_v5|collapse|0"
  "$D/Dragon_Death_sd_v2r_v3.blend|death_v3|death|0"
  "$D/Dragon_Bite_sd_v2r_v5.blend|bite_v5|bite|0"
  "$D/Dragon_ClawSwipe_sd_v2r_v3.blend|claw_swipe_v3|claw_swipe|0"
  "$D/Dragon_Stagger_sd_v2r_v3.blend|stagger_v3|stagger|0"
  "$D/Dragon_Land2_sd_v2r_v4.blend|land2_v4|land|0"
  "$D/Dragon_Takeoff2_sd_v2r_v2.blend|takeoff2_v2|takeoff|0"
  "$D/Dragon_Rise_sd_v2r_v5.blend|rise_v5|rise|0"
  "$D/Dragon_IdleLook_sd_v2r_v2.blend|idle_look_v2|idle_look|1"
  "$D/Dragon_IdleLayered_sd_v2r_v2.blend|idle_layered_v2|idle_layered|1"
  "$D/Dragon_AirHover_sd_v2r_v4.blend|air_hover_v4|air_hover|1"
  "$D/Dragon_AirLand_sd_v2r_v5.blend|air_land_v5|air_land|0"
  "$D/Dragon_AirTakeoff_sd_v2r_v4.blend|takeoff3_v4|air_takeoff|0"
  "$D/Dragon_AirFireDown_sd_v2r_v4.blend|air_fire_down_v4|air_fire_down|0"
)
fresh() {  # blend action move -> 0 when the existing sample came from this blend (md5) and action
  # paths go through the environment, not argv: gpu_slot counts a python command line naming video2rig as an ML GPU client
  FR_BLEND="$1" FR_ACTION="$2" FR_SAMPLE="$SAMPLES/$3.sample.npz" python3 - <<'PY'
import sys, os, hashlib, numpy as np
blend, action, p = os.environ["FR_BLEND"], os.environ["FR_ACTION"], os.environ["FR_SAMPLE"]
if not os.path.exists(p): sys.exit(1)
z = np.load(p, allow_pickle=True)
h = hashlib.md5(open(blend, "rb").read()).hexdigest()
sys.exit(0 if str(z["action"]) == action and str(z["blend_md5"]) == h else 1)
PY
}
blender_run() {  # blend action move
  if [ -n "$SLOT" ]; then
    "$SLOT" capture --label dragon-r3-movedata -- "$BLENDER" --background --factory-startup "$1" --python tools/movedata/sample_action.py -- \
        --action "$2" --move "$3" --out "$SAMPLES"
  else
    "$BLENDER" --background --factory-startup "$1" --python tools/movedata/sample_action.py -- --action "$2" --move "$3" --out "$SAMPLES"
  fi
}
run() {  # blend action move
  if fresh "$1" "$2" "$3"; then echo "reuse $3: sample matches $2 in $1"; return 0; fi
  if [ "$(pgrep -x Blender | wc -l)" -ge "$CAP" ]; then
    echo "$(pgrep -x Blender | wc -l) Blender process(es) running, cap $CAP; refusing to start another (set BLENDER_CAP to allow)" >&2; exit 2
  fi
  local rc busy=0 log
  log="$(mktemp)"
  while :; do
    rc=0; blender_run "$1" "$2" "$3" >"$log" 2>&1 || rc=$?
    grep -E 'MOVEDATA_SAMPLE|Error|Traceback' "$log" || true
    if [ "$rc" = 75 ]; then
      busy=$((busy + 1))
      if [ "$busy" -ge 2 ]; then rm -f "$log"; echo "gpu_slot busy (75) twice for $3; stopping (rerun later: fresh samples are reused)" >&2; exit 75; fi
      echo "gpu_slot busy (75) for $3; retry in 120 s" >&2; sleep 120; continue
    fi
    break
  done
  rm -f "$log"
  fresh "$1" "$2" "$3" || { echo "sample for $3 not written from $2 (exit $rc)" >&2; exit 1; }
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
python3 tools/movedata/annotate_air.py Data/dragon/moves.json
