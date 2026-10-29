import json, os, shutil, sys, hashlib
from pathlib import Path
LIVE=Path(sys.argv[1]); WT=Path(sys.argv[2]); R=Path(sys.argv[3])
items=["CustomuseAssets/Polish20261025/active-plans.json","CustomuseAssets/Polish20261025/overhaul-v029","CustomuseAssets/Polish20261025/overhaul-v028","CustomuseAssets/Polish20261025/idle-joins/knight","CustomuseAssets/Polish20261025/idle-joins/props","CustomuseAssets/Polish20261025/idle-joins/import-plan-KnightB.json","CustomuseAssets/Polish20261025/knight","CustomuseAssets/Polish20261025/props","CustomuseAssets/Polish20261025/sourced-v027b","CustomuseAssets/Sourced20261025b","polish-review-20261025","FabRigTesting/Source/Sword and Shield Pack.zip"]
for n in ["Mixamo_Walk_v17","Mixamo_WalkTwoHand_v17","Fab_RunOneHand_v18","Fab_Run_v17","Mixamo_Attack_v17","Fab_Roll_v17","Sourced_RollAttack_v2"]:
  for ext in (".json",".glb"): items.append("FabRigTesting/Exports/"+n+ext)
rows=[]
def one(src,dst):
  st=os.stat(src)
  dl=bool(st.st_flags & 0x40000000)
  rel=str(dst.relative_to(WT))
  if dl: rows.append({"file":rel,"source":"live-codex-checkout","status":"dataless-skipped","bytes":st.st_size}); return
  dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
  rows.append({"file":rel,"source":"live-codex-checkout","status":"copied","sha256":hashlib.sha256(dst.read_bytes()).hexdigest()})
for it in items:
  s=LIVE/"Local"/it; d=WT/"Local"/it
  if s.is_dir():
    for root,_,files in os.walk(s):
      for f in files:
        if f==".DS_Store": continue
        one(Path(root)/f, d/Path(root).relative_to(s)/f)
  elif s.exists(): one(s,d)
  else: rows.append({"file":"Local/"+it,"status":"absent-in-live"})
(R/"local-assets-provenance.json").write_text(json.dumps(rows,indent=1)+"\n")
import collections; print(collections.Counter(r["status"] for r in rows)); print([r["file"] for r in rows if r["status"]!="copied"])
