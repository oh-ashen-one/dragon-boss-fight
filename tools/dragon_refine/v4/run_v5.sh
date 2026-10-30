#!/bin/zsh
# Fix round 3: one refine (+ CPU dump) run through the shared GPU slot. Blender counts as a GPU client, so even this
# no-render run goes through `gpu_slot.sh capture`; exit 75 (slot busy) waits 120 s and retries, at most 3 times.
# usage: run_v5.sh <move> <input v4 blend> <out blend> [key=value ...]   -> report <out>.json, dump <work>/d_<move>_v5.npz
set -u
REPO=${0:A:h:h:h:h}
B=/Applications/Blender.app/Contents/MacOS/Blender; SLOT=$HOME/.cache/gpu-slot/bin/gpu_slot.sh; T=$REPO/tools/dragon_refine/v4
WK=$REPO/Local/video2rig/dragon/refine/v5/work; mkdir -p $WK
MV=$1; IN=$2; OUT=$3; shift 3
rm -f $OUT
for try in 1 2 3 4; do
  $SLOT capture --label dragon-r3-refine-$MV -- $B --background --factory-startup $IN --python $T/refine_v5.py -- $MV $OUT ${OUT:r}.json "$@" dump=$WK/d_${MV}_v5.npz > $WK/log_$MV.txt 2>&1
  rc=$?
  [[ $rc != 75 ]] && break
  echo "slot busy (75), retry in 120 s" >> $WK/log_$MV.txt; sleep 120
done
grep -E "SAVED|DUMPED|FLARE|Error|Traceback|line [0-9]+" $WK/log_$MV.txt | cut -c1-400
exit $rc
