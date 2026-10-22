#!/bin/zsh
# usage: sheets.sh LABEL  -> contact sheets in <renders>/<LABEL>/sheets
set -e
D=/Users/midir/veyr-review-fable-20261021/Local/Blender/feedback-v4-20261021/renders/$1; O=$D/sheets; mkdir -p $O; rm -f $O/*.png(N)
cd $D
for v in front side threequarter; do
  n=$(ls $v-full-*.png | wc -l | tr -d " "); h=$(( (n+1)/2 ))
  a=(); b=()
  i=0; for f in $(ls $v-full-*.png); do if [ $i -lt $h ]; then a+=($f); else b+=($f); fi; i=$((i+1)); done
  montage -label "%t" ${a[@]} -tile 7x -geometry 300x300+2+2 -pointsize 18 -background "#222" -fill white $O/$v-A.png
  montage -label "%t" ${b[@]} -tile 7x -geometry 300x300+2+2 -pointsize 18 -background "#222" -fill white $O/$v-B.png
done
for v in side front; do
  n=$(ls feet-$v-*.png | wc -l | tr -d " "); h=$(( (n+1)/2 ))
  a=(); b=(); i=0; for f in $(ls feet-$v-*.png); do if [ $i -lt $h ]; then a+=($f); else b+=($f); fi; i=$((i+1)); done
  montage -label "%t" ${a[@]} -tile 4x -geometry 480x160+2+2 -pointsize 16 -background "#222" -fill white $O/feet-$v-A.png
  montage -label "%t" ${b[@]} -tile 4x -geometry 480x160+2+2 -pointsize 16 -background "#222" -fill white $O/feet-$v-B.png
done
ls $O
