#!/bin/bash
# Knight fix round 3: review renders (through the shared GPU slot), page and metrics. Run from anywhere.
#   tools/art/knight_complete/render_round3.sh
# 1. job list (in-place r3 + idle refs + protected StrafeLeft(2H), root-travel strafes/sprints/backpedals/blinks)
# 2. Blender workbench renders, headless, wrapped in gpu_slot capture (waits up to 3600 s for a slot; never bypassed)
# 3. MP4s + lazy-loading page in Local/knight-review-20261028/serve-round3 (round-2 MP4s reused as BEFORE)
# 4. metrics incl. the critic's pixel seam method and first/last-vs-idle pixels, byte-identical check
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"; cd "$ROOT"
R=Local/knight-review-20261028/r3
python3 tools/art/knight_complete/review_jobs_r3.py "$R"
"$HOME/.cache/gpu-slot/bin/gpu_slot.sh" capture --label knight-r3-render --timeout 3600 -- \
  blender --background --factory-startup --python tools/art/knight_complete/render_review.py -- "$R/jobs.json" "$R" \
  > "$R/logs/render.log" 2>&1
grep -c '^RENDERED' "$R/logs/render.log" || true
python3 tools/art/knight_complete/build_review_page.py "$R" --serve ../serve-round3
python3 tools/art/knight_complete/measure_round3.py docs/knight-complete-20261028/data/round3-metrics.json
echo "serve: python3 Local/knight-review-20261028/serve-round3/rangeserver.py Local/knight-review-20261028/serve-round3 <port>"
