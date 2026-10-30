#!/bin/zsh
# Rise from lying, end to end, resumable. Blender is a GPU client: every Blender run goes through `gpu_slot.sh capture --label dragon-riselying`
# (exit 75 = slot busy / GPU held by a foreign client: wait 120 s, retry, at most 4 tries, then stop with 75; re-run later, finished steps are skipped).
#   0  CPU   prep_wings_rl.py     source-mask silhouette solve of the wings (frames 100-134, twist cap) -> refine_rl/wings_rl.npz     (skipped if present, FORCE=1 redoes)
#   1  Blender refine_rise_lying.py   model.blend + fit -> refine_rl/t_rise_lying.blend (+ report.json, channels, mesh dump)               (skipped if present)
#   2  CPU   measure_rise_lying.py    -> refine_rl/measure.json; a failing check stops here (exit 3) unless FORCE_RENDER=1
#   3  copy the blend to Local/video2rig/dragon/Dragon_RiseLying_sd_v2r_v1.blend, queue line into Local/dragon-review-20261029/queue_rl.txt
#   4  Blender run_queue_rl.sh        prep + EEVEE render of label RL1 (3 cameras) -> video/clip_RL1_*.mp4 -> build_review_page_rl.py ("Rise from lying" card)
# usage: tools/dragon_refine/v4/run_rise_lying.sh [key=value ...]      extra keys go to refine_rise_lying.py (hold_s=1.25 idle_blend=8 wing_blend=16 twist_cap=25 ...)
# Python lines run from the project dir with relative paths (no video2rig / ML word on a python command line: gpu_slot counts those as ML clients).
set -u
REPO=${0:A:h:h:h:h}; T=$REPO/tools/dragon_refine/v4; P=$REPO/Local/video2rig/dragon-lying; D=$REPO/Local/video2rig/dragon; W=$P/refine_rl
R=$REPO/Local/dragon-review-20261029; B=/Applications/Blender.app/Contents/MacOS/Blender; SLOT=$HOME/.cache/gpu-slot/bin/gpu_slot.sh
FINAL=$D/Dragon_RiseLying_sd_v2r_v1.blend; TMP=$W/t_rise_lying.blend
mkdir -p $W; cd $P || exit 1
[[ -f $P/model.blend && -f $P/work/rise_lying/fit.npz && -f $P/out/rise_lying.npz ]] || { echo "missing model.blend / fit.npz / out/rise_lying.npz in $P"; exit 2; }

# ---- 0 CPU wings
if [[ ! -f $W/wings_rl.npz || ${FORCE:-0} == 1 ]]; then
  python3 $T/prep_wings_rl.py work/rise_lying/fit.npz refine_rl/wings_rl.npz > $W/prep_wings.log 2>&1 || { echo "prep_wings failed (log $W/prep_wings.log)"; exit 2; }
fi
grep -E "IoU|WROTE" $W/prep_wings.log | cut -c1-300

# ---- 1 Blender refine (gated, one at a time)
if [[ ! -f $TMP || ${FORCE:-0} == 1 ]]; then
  rm -f $TMP $TMP.channels.npz $W/report.json $W/d_rise_lying_v1.npz
  for try in 1 2 3 4; do
    $SLOT capture --label dragon-riselying -- $B --background --factory-startup $P/model.blend --python $T/refine_rise_lying.py -- \
      $P/work/rise_lying/fit.npz $TMP $W/report.json wing_src=$W/wings_rl.npz dump=$W/d_rise_lying_v1.npz "$@" > $W/log_refine.txt 2>&1
    rc=$?
    [[ $rc != 75 ]] && break
    echo "slot busy (75), retry in 120 s ($try/4)" >> $W/log_refine.txt; echo "slot busy (75), retry in 120 s ($try/4)"; sleep 120
  done
  grep -E "SAVED|CHECK|DUMPED|Error|Traceback|line [0-9]+" $W/log_refine.txt | cut -c1-400
  [[ $rc == 75 ]] && { echo "GPU busy 4 times: stopped before the refine (re-run this script)"; exit 75; }
  [[ $rc != 0 || ! -f $TMP ]] && { echo "refine failed rc=$rc (log $W/log_refine.txt)"; exit 4; }
fi

# ---- 2 CPU measure (raw-fit dump made on the CPU, no Blender)
[[ -f $W/d_raw_fit.npz ]] || python3 $T/lib_rise_lying.py dump work/rise_lying/fit.npz refine_rl/d_raw_fit.npz || exit 5
python3 $T/measure_rise_lying.py refine_rl/measure.json rl=refine_rl/d_rise_lying_v1.npz ch=refine_rl/t_rise_lying.blend.channels.npz idle=../dragon/refine/v4/work/d_idle_v2.npz \
  ref=../dragon/refine/v5/work/d_rise_v5.npz raw=refine_rl/d_raw_fit.npz views=refine_rl/wings_rl_views.npz masks=work/rise_lying/masks.npz \
  start=$(python3 -c "import json;print(json.load(open('refine_rl/report.json'))['trim']['start'])") || exit 6
FAILS=$(python3 -c "import json;p=json.load(open('refine_rl/measure.json'))['rise_lying']['pass'];print(','.join(k for k,v in p.items() if v is False))")
if [[ -n "$FAILS" && ${FORCE_RENDER:-0} != 1 ]]; then echo "measure FAILED: $FAILS  (refine_rl/measure.json; FORCE_RENDER=1 renders anyway)"; exit 3; fi

# ---- 3 promote + queue line
cp $TMP $FINAL && echo "PROMOTED $FINAL"
mkdir -p $R
grep -q "rise_lying_v1 RL1" $R/queue_rl.txt 2>/dev/null || cat > $R/queue_rl.txt <<EOF
# Rise from lying (label RL1). Run: $T/run_queue_rl.sh   (prep + render through gpu_slot capture, label dragon-riselying; re-running skips labels in queue_rl_done.txt;
# then build_review_page_rl.py writes the "Rise from lying" card, served prefix after_rise_lying)
$FINAL rise_lying_v1 RL1
STOP
EOF

# ---- 4 render + page
$T/run_queue_rl.sh; rc=$?
tail -5 $R/queue_rl.log
exit $rc
