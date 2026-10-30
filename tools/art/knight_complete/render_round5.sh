#!/bin/bash
# Knight fix round 5: review renders (through the shared GPU slot), all-intra page and metrics. Run after
# author_round5.sh + prepare_round5_plan.py. gpu_slot exit 75 = slot busy (not a crash): wait 120 s, at most 3 retries.
#   tools/art/knight_complete/render_round5.sh
# 1. job list (review_jobs_r5.py): r5 AND r4 RollAttack + blinks rendered with the same round-5 framing (whole blade in
#    frame, 1.5x the round-4 pixel density), in place, root travel, blink top views
# 2. Blender workbench renders, headless, one Blender, via gpu_slot capture
# 3. MP4s all-intra + lazy page in serve-round5; the PNG frames are deleted after encoding (disk)
# 4. metrics: data/round5-metrics.json (critic-spec roll gates, blink foot gates, byte-identical checks)
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"; cd "$ROOT"
K=tools/art/knight_complete; R=Local/knight-review-20261028/r5; mkdir -p "$R/logs"
python3 $K/review_jobs_r5.py "$R" || exit 1
for attempt in 0 1 2 3; do
  "$HOME/.cache/gpu-slot/bin/gpu_slot.sh" capture --label knight-r5-render --timeout 3600 -- \
    blender --background --factory-startup --python $K/render_review.py -- "$R/jobs.json" "$R" > "$R/logs/render.log" 2>&1
  rc=$?
  if [ $rc -eq 75 ] && [ $attempt -lt 3 ]; then echo "slot busy (75), retry in 120 s"; sleep 120; continue; fi
  break
done
[ $rc -ne 0 ] && { echo "RENDER FAILED (exit $rc), see $R/logs/render.log"; tail -8 "$R/logs/render.log"; exit 1; }
grep -c '^RENDERED' "$R/logs/render.log"; grep 'gpu_slot\[' "$R/logs/render.log" | tail -1
python3 $K/build_review_page.py "$R" --serve ../serve-round5 --intra || exit 1
python3 $K/measure_round5.py docs/knight-complete-20261028/data/round5-metrics.json > "$R/logs/metrics.log" 2>&1 || { tail -20 "$R/logs/metrics.log"; exit 1; }
tail -8 "$R/logs/metrics.log" | cut -c1-600
rm -rf "$R/frames"
du -sh Local/knight-review-20261028/serve-round5
echo "serve: python3 Local/knight-review-20261028/serve-round5/rangeserver.py Local/knight-review-20261028/serve-round5 <port>"
