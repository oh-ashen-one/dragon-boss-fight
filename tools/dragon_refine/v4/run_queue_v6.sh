#!/bin/zsh
# Fix round 4 review renders (v6 Actions). One clip at a time: prep (Blender, no render) and the EEVEE frames, BOTH through
# the shared GPU slot (`gpu_slot.sh capture`, Blender counts as a GPU client) -> MP4s -> the clip's frame PNGs are deleted.
# usage: tools/dragon_refine/v4/run_queue_v6.sh [queue file]   (default Local/dragon-review-20261029/queue_v6.txt)
# Queue lines: <blend> <action> <label> [tall|xtall]; "STOP" ends the queue. Done labels go to queue_v6_done.txt and are skipped
# on a re-run, so a later session resumes where this one stopped. Exit 75 (slot settle-timeout: GPU busy) is not a crash: the
# step is retried once after 120 s; a second 75 in a row stops the whole queue (exit 75) instead of waiting for hours.
# Two real failures stop the queue (no auto-relaunch). Writes the "Round 4 fix" column at the end (build_review_page_v6.py).
set -u
REPO=${0:A:h:h:h:h}
R=$REPO/Local/dragon-review-20261029; Q=${1:-$R/queue_v6.txt}; LOG=$R/queue_v6.log; DONE=$R/queue_v6_done.txt
B=/Applications/Blender.app/Contents/MacOS/Blender; SLOT=$HOME/.cache/gpu-slot/bin/gpu_slot.sh; T=$REPO/tools/dragon_refine
export REVIEW_ROOT=$R
mkdir -p $R/work $R/video; touch $DONE
fails=0
slot() {   # slot <label> <log> <args...>: one gated Blender run; 75 -> one retry after 120 s; prints the final rc
  local lab=$1 lg=$2; shift 2; local n=0 rc
  while true; do
    $SLOT capture --label $lab -- $B --background --factory-startup "$@" > $lg 2>&1; rc=$?
    [[ $rc != 75 ]] && break
    n=$((n+1)); echo "$(date +%T) $lab: slot settle-timeout (GPU busy) [$n]" >> $LOG
    (( n >= 2 )) && break
    sleep 120
  done
  return $rc
}
while read -r BL ACT LAB CAM; do
  [[ -z "$BL" || "$BL" == \#* ]] && continue
  [[ "$BL" == STOP ]] && break
  grep -qx "$LAB" $DONE && { echo "$(date +%T) skip $LAB (done)" >> $LOG; continue; }
  [[ -f "$BL" ]] || { echo "$(date +%T) skip $LAB (no blend: $BL; not authored or did not pass measure_v6)" >> $LOG; continue; }
  FLAG=""; [[ "${CAM:-}" == tall ]] && FLAG=--tall; [[ "${CAM:-}" == xtall ]] && FLAG=--xtall
  echo "$(date +%T) prep $LAB" >> $LOG
  slot dragon-r4-prep $R/work/prep_$LAB.log $BL --python $T/prep_render.py -- $ACT $LAB $R/work/prepared_$LAB.blend; rc=$?
  [[ $rc == 75 ]] && { echo "$(date +%T) $LAB: GPU busy twice in a row, queue stopped (resume: re-run this script)" >> $LOG; exit 75; }
  [[ $rc != 0 ]] && { echo "prep failed $LAB rc=$rc" >> $LOG; exit 4; }
  echo "$(date +%T) render $LAB $FLAG" >> $LOG
  slot dragon-r4-render $R/work/render_$LAB.log $R/work/prepared_$LAB.blend --python $T/render_clip_v3.py -- $LAB $FLAG; rc=$?
  [[ $rc == 75 ]] && { echo "$(date +%T) $LAB: GPU busy twice in a row, queue stopped (resume: re-run this script)" >> $LOG; exit 75; }
  if [[ $rc != 0 ]]; then
    fails=$((fails+1)); echo "$(date +%T) $LAB render failed rc=$rc (failure $fails)" >> $LOG
    (( fails >= 2 )) && { echo "two render failures: stopping (no auto-relaunch)" >> $LOG; exit 5; }
    continue
  fi
  for C in front left threequarter; do
    ffmpeg -y -hide_banner -loglevel error -framerate 24 -i $R/frames/$LAB/$C/f_%04d.png -c:v libx264 -crf 16 -preset slow -pix_fmt yuv420p \
      -map_metadata -1 -movflags +faststart $R/video/clip_${LAB}_${C}.mp4 || { echo "encode failed $LAB $C" >> $LOG; exit 6; }
  done
  ls $R/video/clip_${LAB}_{front,left,threequarter}.mp4 >/dev/null 2>&1 && rm -rf $R/frames/$LAB      # disk: frames go once the MP4s exist
  echo $LAB >> $DONE; echo "PIPELINE_DONE $LAB" >> $LOG
done < $Q
echo "QUEUE_V6_FINISHED" >> $LOG
python3 $T/v4/build_review_page_v6.py >> $LOG 2>&1
