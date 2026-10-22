#!/bin/zsh
# rzoom.sh LABEL A B VIEW... : labelled zoom strip of sheet frames A..B (tile 240, 10 cols)
L=$1; A=$2; B=$3; shift 3
R=/Users/midir/veyr-review-fable-20261021; D=$R/Local/Blender/newclips-20261021/renders
for v in "$@"; do T=$D/zoomtmp_$L_$v; rm -rf $T; mkdir -p $T
 for ((i=A;i<=B;i++)); do ln -s $D/$L/$v-$(printf %04d $i).png $T/$v-$(printf %04d $((i-A))).png; done
 python3 $R/tools/art/blender/newclips/labelsheet.py $T $v $D/${L}_${v}_z${A}-${B}.jpg 10 240 $(python3 -c "print($A/30)"); rm -rf $T; done
