#!/bin/zsh
cd /Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_flight_r2
for V in "21 36 30" "21 40 30"; do
  set -- ${=V}
  echo "== HU=$1 HT=$2 QF=$3"
  python3 dr.py open_ro.py 'NAME="Dragon_Takeoff_Blender_v1"' >/dev/null
  python3 dr.py author_takeoff_r3.py "MODE='takeoff'; SWEEP=0.0; HU=$1; HT=$2; QF=$3" | tail -c 60
  python3 dr.py bone_steps.py 'BONES=("tripo::1_Right_Limb_1", "tripo::0_Right_Limb_1"); F0=0; F1=45' | python3 -c "
import sys,json;t=sys.stdin.read();d=json.loads(t[t.index('{'):]);print({k:(max(v[:44]),v.index(max(v[:44]))) for k,v in d.items() if k.startswith('tripo')})"
done
date +%H:%M
