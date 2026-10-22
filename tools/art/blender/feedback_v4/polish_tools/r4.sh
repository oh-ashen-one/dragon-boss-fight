#!/bin/zsh
# round-4 polish: separate out dir + revision 4r4 (export name Backpedal_Blender_v4r4.glb)
cd /Users/midir/veyr-review-fable-20261021
exec python3 tools/art/blender/feedback_v4/run.py --port 9887 --owner fable-veyr-knight-backpedal-20261021 --out Local/Blender/feedback-v4-20261021/backpedal-round4 --revision 4r4 "$@"
