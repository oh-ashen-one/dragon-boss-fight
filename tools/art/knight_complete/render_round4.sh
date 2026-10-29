#!/bin/bash
# Knight fix round 4: review renders (through the shared GPU slot), all-intra page and metrics. Run after author_round4.sh,
# only when the orchestrator says "GPU is yours". Run from anywhere.
#   tools/art/knight_complete/render_round4.sh
# 1. job list: changed clips in place (front|side|3/4), top views of sprints/blinks (r4 and the r3 sprint BEFORE),
#    root travel for the r4 sprints/blinks and the r4 AND r3 RollAttack with its root track; unchanged rows reuse r3 frames
# 2. Blender workbench renders, headless, wrapped in gpu_slot capture (waits up to 3600 s; never bypassed)
# 3. MP4s, every one all-intra (r3 frames re-encoded from their lossless PNGs, not re-rendered) + lazy page in serve-round4
# 4. metrics: bone pelvis-vs-boss, lossless + intra seams, blink tail, roll world, byte-identical + kept-r3 hash checks
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"; cd "$ROOT"
K=tools/art/knight_complete; R=Local/knight-review-20261028/r4; mkdir -p "$R/logs"
python3 $K/review_jobs_r4.py "$R"
"$HOME/.cache/gpu-slot/bin/gpu_slot.sh" capture --label knight-r4-render --timeout 3600 -- \
  blender --background --factory-startup --python $K/render_review.py -- "$R/jobs.json" "$R" \
  > "$R/logs/render.log" 2>&1
grep -c '^RENDERED' "$R/logs/render.log" || true
python3 $K/build_review_page.py "$R" --serve ../serve-round4 --intra --frames-also Local/knight-review-20261028/r3/frames
python3 $K/measure_round4.py docs/knight-complete-20261028/data/round4-metrics.json
echo "serve: python3 Local/knight-review-20261028/serve-round4/rangeserver.py Local/knight-review-20261028/serve-round4 <port>"
