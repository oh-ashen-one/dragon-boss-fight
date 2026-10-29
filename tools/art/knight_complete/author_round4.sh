#!/bin/bash
# Knight fix round 4: authoring (headless Blender, no rendering) + plan. RUN ONLY WHEN THE ORCHESTRATOR SAYS "GPU is yours":
# gpu_slot counts every Blender process (even --background) as a GPU client. Run from anywhere.
#   tools/art/knight_complete/author_round4.sh
# Each Blender stage goes through gpu_slot capture (waits up to 3600 s; exit 75 = not run -> this script stops, no retry
# loop, no bypass). Outputs are new names only (v6 / v6c / v6r in Local/FabRigTesting/Exports; export() refuses to
# overwrite). The sprint body gate (leg plane <= 52 deg, shin side/front >= 0.8, stance ankle error <= 1 cm) stops the
# chain with GATE_FAIL and Local/FabRigTesting/Exports/round4-bodies-report.json; do not pass --force without review.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"; cd "$ROOT"
K=tools/art/knight_complete; LOG=Local/knight-review-20261028/r4/logs; mkdir -p "$LOG"
SLOT="$HOME/.cache/gpu-slot/bin/gpu_slot.sh"
python3 $K/build_round4.py --dry                     # inputs present, outputs free, blink timeline, roll timing
stage() {  # stage NAME [ARGS...]
  local st=$1; shift
  "$SLOT" capture --label "knight-r4-$st" --timeout 3600 -- \
    blender --background --factory-startup --python $K/build_round4.py -- "$st" "$@" > "$LOG/author-$st.log" 2>&1 \
    || { echo "STAGE $st FAILED (exit $?), see $LOG/author-$st.log"; tail -5 "$LOG/author-$st.log"; exit 1; }
  grep -E '^(RUNBODY|FITTED|CYCLE|RETIMED|EXPORTED|SKIP|GATE|ROLL|WRIST|CONTACT|STEPS)' "$LOG/author-$st.log" | cut -c1-300 || true
}
stage bodies
stage fit
stage cycles
RETIME_ARGS=$(python3 $K/measure_round4.py retime-args); echo "RETIME $RETIME_ARGS"
# shellcheck disable=SC2086
stage retime $RETIME_ARGS
stage rollattack
python3 $K/prepare_round4_plan.py --check
python3 $K/prepare_round4_plan.py > "$LOG/prepare-plan.log" 2>&1; grep -E 'STANCE_VS_NOMINAL|ROLL_ROOT_END|PLAN_WRITTEN' "$LOG/prepare-plan.log"
echo "AUTHORED; next: tools/art/knight_complete/render_round4.sh (plan NOT activated, nothing imported)"
