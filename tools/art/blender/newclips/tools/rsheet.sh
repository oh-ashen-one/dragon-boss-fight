#!/bin/zsh
# rsheet.sh LABEL [cols] [tile] : capture 4 views at 480 (ortho 2.2) and labelled preview sheets; copies nothing
L=$1; C=${2:-17}; T=${3:-150}
R=/Users/midir/veyr-review-fable-20261021
$R/Local/blender-session-fable-run/ncj.sh rollattack.py "C.capture(\"$L\", res=480, ortho=2.2, center_z=.55)" | tail -c 200; echo
for v in front side threequarter rear; do python3 $R/tools/art/blender/newclips/labelsheet.py $R/Local/Blender/newclips-20261021/renders/$L $v $R/Local/Blender/newclips-20261021/renders/${L}_${v}_preview.jpg $C $T; done
