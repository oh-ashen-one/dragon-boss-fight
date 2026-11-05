#!/bin/zsh
# Fix round 4 authoring + measure, resumable. One Blender refine at a time through `gpu_slot capture --label dragon-r4-author`
# (run_v6.sh: exit 75 waits 120 s and retries once; a second 75 stops this script with exit 75 -- re-run it later).
# Each move is authored to refine/v6/work/t_<move>.blend (+ CPU dump), then measure_v6.py (CPU only) scores v4/v5/v6 into
# Local/dragon-review-20261029/measure_v6.json. A move whose v6 passes every round-4 target is promoted to
# Local/video2rig/dragon/Dragon_<Move>_sd_v2r_v6.blend; a failing move stays on v5 and is commented out of queue_v6.txt.
# usage: tools/dragon_refine/v4/run_author_v6.sh [move ...]   (default: air_land roar collapse bite; done moves are skipped
#        unless FORCE=1). Options per move: env OPTS_<move>="key=value ...".
set -u
REPO=${0:A:h:h:h:h}; T=$REPO/tools/dragon_refine/v4; D=$REPO/Local/video2rig/dragon; W=$D/refine/v6/work; R=$REPO/Local/dragon-review-20261029
SEG=${SEG:-/private/tmp/claude-501/-Users-midir/1e99ac11-5966-4ca4-8ec7-273fc683df51/scratchpad/r3fix/crit/cache}
mkdir -p $W
typeset -A IN NAME; NAME=(air_land AirLand roar Roar collapse Collapse bite Bite)
MOVES=(${@:-air_land roar collapse bite})
for MV in $MOVES; do
  NM=${NAME[$MV]}
  if [[ -f $W/t_$MV.blend && -f $W/d_${MV}_v6.npz && ${FORCE:-0} != 1 ]]; then echo "skip $MV (authored)"; continue; fi
  OPTS_VAR=OPTS_$MV; eval "EXTRA=(\${=${OPTS_VAR}:-})"
  $T/run_v6.sh $MV $D/Dragon_${NM}_sd_v2r_v5.blend $W/t_$MV.blend $EXTRA; rc=$?
  [[ $rc == 75 ]] && { echo "GPU busy twice: stopped before/at $MV; resume: $0 $MOVES"; exit 75; }
  [[ $rc != 0 ]] && { echo "refine $MV failed rc=$rc (log $W/log_$MV.txt)"; exit 4; }
done
python3 $T/measure_v6.py $R/measure_v6.json v4=$D/refine/v4/work v5=$D/refine/v5/work v6=$W seg=$SEG only=${(j:,:)MOVES} || exit 6
python3 - $R/measure_v6.json $W $D $R/queue_v6.txt ${MOVES} <<'PY'
import json, sys, shutil, os, re
res, W, D, Q, moves = json.load(open(sys.argv[1])), sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5:]
NAME = {"air_land": "AirLand", "roar": "Roar", "collapse": "Collapse", "bite": "Bite"}
q = open(Q).read(); dec = res.setdefault("decisions", {})
for mv in moves:
    p = res.get(mv, {}).get("v6", {}).get("pass", {}); ok = bool(p) and all(v is not False for v in p.values())
    dst = os.path.join(D, f"Dragon_{NAME[mv]}_sd_v2r_v6.blend")
    if ok: shutil.copy2(os.path.join(W, f"t_{mv}.blend"), dst); q = re.sub(r"^#\s*(\S+%s)" % re.escape(f"Dragon_{NAME[mv]}_sd_v2r_v6.blend"), r"\1", q, flags=re.M)
    else: q = re.sub(r"^(\S+%s)" % re.escape(f"Dragon_{NAME[mv]}_sd_v2r_v6.blend"), r"# \1", q, flags=re.M)
    dec[mv] = {"ships": "v6" if ok else "v5", "pass": p}; print("DECISION", mv, "v6" if ok else "v5 (kept)", json.dumps(p))
open(Q, "w").write(q); json.dump(res, open(sys.argv[1], "w"), indent=1)
PY
