#!/bin/zsh
# Fix round 4: one refine (+ CPU dump) run through the shared GPU slot. Blender counts as a GPU client, so even this
# no-render run goes through `gpu_slot.sh capture --label dragon-r4-author`; exit 75 (slot busy) waits 120 s and retries ONCE,
# a second 75 stops (exit 75) so the caller can write down what remains.
# usage: run_v6.sh <move> <input v5 blend> <out blend> [key=value ...]   -> report <out>.json, dump <work>/d_<move>_v6.npz
set -u
REPO=${0:A:h:h:h:h}
B=/Applications/Blender.app/Contents/MacOS/Blender; SLOT=$HOME/.cache/gpu-slot/bin/gpu_slot.sh; T=$REPO/tools/dragon_refine/v4
WK=$REPO/Local/video2rig/dragon/refine/v6/work; mkdir -p $WK
MV=$1; IN=$2; OUT=$3; shift 3
rm -f $OUT
for try in 1 2; do
  $SLOT capture --label dragon-r4-author -- $B --background --factory-startup $IN --python $T/refine_v6.py -- $MV $OUT ${OUT:r}.json "$@" dump=$WK/d_${MV}_v6.npz > $WK/log_$MV.txt 2>&1
  rc=$?
  [[ $rc != 75 ]] && break
  echo "slot busy (75) [$try]" >> $WK/log_$MV.txt
  [[ $try == 1 ]] && sleep 120
done
grep -E "SAVED|DUMPED|Error|Traceback|line [0-9]+|slot busy" $WK/log_$MV.txt | cut -c1-400
exit $rc
