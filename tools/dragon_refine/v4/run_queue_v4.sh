#!/bin/zsh
# Fix round 2 review renders. One clip at a time: prep (Blender, no render) -> EEVEE frames through the shared GPU slot -> MP4s.
# usage: tools/dragon_refine/v4/run_queue_v4.sh [queue file]   (default Local/dragon-review-20261029/queue_v4.txt)
# Queue lines: <blend> <action> <label> [tall|xtall]; a line "STOP" ends the queue. Done labels are appended to queue_v4_done.txt
# and skipped on a re-run. The render runs only inside `gpu_slot.sh capture` (never unwrapped); exit 75 (slot settle-timeout,
# GPU busy) is not a crash: the clip is retried after 10 min, up to 6 times. Two real render failures stop the queue (no auto-relaunch).
set -u
REPO=${0:A:h:h:h:h}
R=$REPO/Local/dragon-review-20261029; Q=${1:-$R/queue_v4.txt}; LOG=$R/queue_v4.log; DONE=$R/queue_v4_done.txt
B=/Applications/Blender.app/Contents/MacOS/Blender; SLOT=$HOME/.cache/gpu-slot/bin/gpu_slot.sh; T=$REPO/tools/dragon_refine
export GPU_SLOT_CAPTURE_WAIT_TIMEOUT=3600 REVIEW_ROOT=$R
mkdir -p $R/work $R/video; touch $DONE
fails=0
blender_count() { pgrep -x Blender | wc -l | tr -d ' '; }
while read -r BL ACT LAB CAM; do
  [[ -z "$BL" || "$BL" == \#* ]] && continue
  [[ "$BL" == STOP ]] && break
  grep -qx "$LAB" $DONE && { echo "$(date +%T) skip $LAB (done)" >> $LOG; continue; }
  FLAG=""; [[ "${CAM:-}" == tall ]] && FLAG=--tall; [[ "${CAM:-}" == xtall ]] && FLAG=--xtall
  while (( $(blender_count) >= ${BLENDER_CAP:-2} )); do sleep 30; done
  echo "$(date +%T) prep $LAB" >> $LOG
  $B --background --factory-startup $BL --python $T/prep_render.py -- $ACT $LAB $R/work/prepared_$LAB.blend > $R/work/prep_$LAB.log 2>&1 || { echo "prep failed $LAB" >> $LOG; exit 4; }
  tries=0
  while true; do
    while (( $(blender_count) >= ${BLENDER_CAP:-2} )); do sleep 30; done
    echo "$(date +%T) render $LAB $FLAG (try $((tries+1)))" >> $LOG
    $SLOT capture --label dragon-r2-render -- $B --background --factory-startup $R/work/prepared_$LAB.blend --python $T/render_clip_v3.py -- $LAB $FLAG > $R/work/render_$LAB.log 2>&1
    rc=$?
    [[ $rc == 0 ]] && break
    if [[ $rc == 75 ]]; then tries=$((tries+1)); (( tries >= 6 )) && { echo "$(date +%T) $LAB: slot busy 6 times, stopping" >> $LOG; exit 75; }
      echo "$(date +%T) $LAB: slot settle-timeout (GPU busy), retry in 600 s" >> $LOG; sleep 600; continue; fi
    fails=$((fails+1)); echo "$(date +%T) $LAB render failed rc=$rc (failure $fails)" >> $LOG
    (( fails >= 2 )) && { echo "two render failures: stopping (no auto-relaunch)" >> $LOG; exit 5; }
    continue 2
  done
  for C in front left threequarter; do
    ffmpeg -y -hide_banner -loglevel error -framerate 24 -i $R/frames/$LAB/$C/f_%04d.png -c:v libx264 -crf 16 -preset slow -pix_fmt yuv420p \
      -map_metadata -1 -movflags +faststart $R/video/clip_${LAB}_${C}.mp4 || { echo "encode failed $LAB $C" >> $LOG; exit 6; }
  done
  echo $LAB >> $DONE; echo "PIPELINE_DONE $LAB" >> $LOG
done < $Q
echo "QUEUE_V4_FINISHED" >> $LOG
python3 $T/v4/build_review_page_v4.py >> $LOG 2>&1
