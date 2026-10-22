#!/bin/zsh
# usage: rpc.sh <script.py>  (runs on Studio in dragon Blender via veyr_rpc owner guard)
R=/Users/midir/veyr-review-fable-20261021
cd $R && VEYR_BLENDER_OWNER=fable-veyr-dragon-20261021 VEYR_BLENDER_PORT=9888 python3 tools/art/blender/veyr_rpc.py "$1"
