#!/bin/bash
# Knight fix round 5: authoring (headless Blender, no rendering). Each Blender stage goes through gpu_slot capture;
# exit 75 = slot busy (not a crash): wait 120 s and retry, at most 3 retries. One Blender at a time.
#   tools/art/knight_complete/author_round5.sh [rollattack|blinkfeet ...] [-- --tag TAG]
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"; cd "$ROOT"
K=tools/art/knight_complete; LOG=Local/knight-review-20261028/r5/logs; mkdir -p "$LOG"
SLOT="$HOME/.cache/gpu-slot/bin/gpu_slot.sh"
STAGES=(); EXTRA=()
while [ $# -gt 0 ]; do if [ "$1" = "--" ]; then shift; EXTRA=("$@"); break; fi; STAGES+=("$1"); shift; done
[ ${#STAGES[@]} -eq 0 ] && STAGES=(rollattack blinkfeet)
python3 $K/build_round5.py --dry > "$LOG/dry.log" 2>&1 || { cat "$LOG/dry.log"; echo "DRY FAILED"; exit 1; }
for st in "${STAGES[@]}"; do
  for attempt in 0 1 2 3; do
    "$SLOT" capture --label "knight-r5-$st" --timeout 3600 -- \
      blender --background --factory-startup --python $K/build_round5.py -- "$st" ${EXTRA[@]+"${EXTRA[@]}"} > "$LOG/author-$st.log" 2>&1
    rc=$?
    if [ $rc -eq 75 ] && [ $attempt -lt 3 ]; then echo "slot busy (75) for $st, retry in 120 s"; sleep 120; continue; fi
    break
  done
  if [ $rc -ne 0 ]; then echo "STAGE $st FAILED (exit $rc), see $LOG/author-$st.log"; tail -8 "$LOG/author-$st.log"; exit 1; fi
  grep -E '^(EXPORTED|SKIP|ROLL|WRIST|BLINKFEET)|gpu_slot\[' "$LOG/author-$st.log" | cut -c1-400 || true
done
echo "AUTHORED ${STAGES[*]}"
