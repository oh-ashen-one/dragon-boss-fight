#!/bin/zsh
# usage: review_pass.sh PASSNAME   (render 181 frames x 3 views, sheets, mp4, tarball)
P=$1; T=/Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_v1; R=/Users/midir/veyr-review-fable-20261021/Local/Blender/dragon-v1-20261021/renders
for v in ${=VIEWS:-front side three_quarter}; do { echo "VIEW='$v'; PASS='$P'"; [ -n "$SHOW" ] && echo "SHOW=$SHOW"; echo "LAST=${NFR:-180}"; [ -n "$RES" ] && echo "RES=$RES; FRONT_SCALE=${FRONT_SCALE:-1.1}; SIDE_SCALE=${SIDE_SCALE:-1.2}; TQ_SCALE=${TQ_SCALE:-1.0}; TARGET_Z=${TARGET_Z:-0.22}"; cat $T/render_pass.py; } > $T/_rp_$v.py; $T/rpc.sh $T/_rp_$v.py | grep -q '"success"' || echo "render failed $v"; done
cd $R/$P || exit 1
mkdir -p sheets
for v in ${=VIEWS:-front side three_quarter}; do
  ffmpeg -loglevel error -y -framerate 30 -i ${v}_%04d.png -frames:v ${NFR:-180} -c:v libx264 -pix_fmt yuv420p -crf 18 sheets/${P}_${v}.mp4
  for k in $(seq 0 $(( (${NFR:-180}) / 30 ))); do s=$((k*30)); ls ${v}_*.png | sed -n "$((s+1)),$((s+30))p" > /tmp/drs_$v_$k; montage @/tmp/drs_$v_$k -tile 6x5 -geometry 320x180+1+1 sheets/${v}_f$(printf %03d $s).png 2>/dev/null; done
done
mkdir -p /tmp/drj_$P && rm -rf /tmp/drj_$P/*; for f in *.png; do magick $f -quality 82 /tmp/drj_$P/${f%.png}.jpg; done; for f in sheets/*.png; do magick $f -quality 85 /tmp/drj_$P/sheet_$(basename ${f%.png}).jpg; done; cp sheets/*.mp4 /tmp/drj_$P/; tar -C /tmp/drj_$P -cf ../${P}_jpg.tar .
echo done
