#!/bin/zsh
# polish round (walk/guard/strafe/stagger/death/heal/walk_two): own out dir under feedback-v4
cd /Users/midir/veyr-review-fable-20261021
exec python3 tools/art/blender/feedback_v4/run.py --port 9887 --owner fable-veyr-knight-backpedal-20261021 --out Local/Blender/feedback-v4-20261021/polish-fable "$@"
