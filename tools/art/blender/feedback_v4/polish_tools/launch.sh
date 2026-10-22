#!/bin/zsh
cd /Users/midir/veyr-review-fable-20261021
export VEYR_BLENDER_WORK=/Users/midir/veyr-review-fable-20261021/Local/blender-session-fable-backpedal
export VEYR_BLENDER_OWNER=fable-veyr-knight-backpedal-20261021
export VEYR_BLENDER_PORT=9887
export VEYR_BLENDER_ADDON=/Users/midir/blender-mcp-work/addons/blender_mcp.py
export VEYR_REVIEW_ASSETS=/Users/midir/veyr-review-fable-20261021/tools/asset-review/.asset-cache/review
export GPU_SLOT_CAPTURE_MAX_HOLD=14400
# Blender-only exception (operating-rules, owner decision 2026-10-21): ceiling 4 Blender when no game engine runs/queues.
export GPU_SLOT_CAPTURE_SLOTS=4
exec /Users/midir/.cache/gpu-slot/bin/gpu_slot.sh capture --label fable-veyr-knight-backpedal-20261021 --timeout 600 --json /Users/midir/veyr-review-fable-20261021/Local/blender-session-fable-backpedal/gpu-slot.json -- /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --python /Users/midir/veyr-review-fable-20261021/tools/art/blender/start_veyr_session.py
