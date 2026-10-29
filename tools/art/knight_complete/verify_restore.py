import hashlib, json, os, subprocess, sys
from pathlib import Path
R=Path(sys.argv[1]).resolve(); WT=Path(sys.argv[2]).resolve(); LIVE=Path(sys.argv[3]).resolve()
prov=json.load(open(R/"restore-provenance.json")); final={r["file"]:r for r in prov["files"]}
# release-level manifests
checked=0; bad=[]
for mf in ["dl/native-integration-20261025/manifest.json","dl/native-integration-20261025/prop-material-fix-manifest.json","dl/combat-arena-polish-native-20261025/part1-manifest.json","dl/combat-arena-polish-native-20261025/part2-manifest.json","dl/combat-arena-polish-native-20261025/part3-manifest.json","dl/combat-arena-polish-native-20261025/material-skeleton-save-manifest.json"]:
  m=json.load(open(R/mf)); rows=m if isinstance(m,list) else m.get("files",[])
  rel=mf.split("/")[1]
  for r in rows:
    f=r.get("file") or r.get("path"); h=r.get("sha256")
    if not f or not h: continue
    hist=[x for x in prov["files"] if x["file"]==f]
    # the archive version from this release must match; final may be overridden later
    checked+=1
    if f not in final: bad.append(("missing",f)); continue
print("release-manifest rows checked",checked,"missing",len(bad))
# dataless check in worktree
cc=WT/"Unreal/Veyr/Content"
flags=subprocess.run("find Unreal/Veyr/Content -type f -print0 | xargs -0 stat -f \"%Sf\" | grep -c dataless",shell=True,cwd=WT,capture_output=True,text=True).stdout.strip()
print("worktree dataless files:",flags)
# compare with live Codex tree for Customuse + other ignored content
live=LIVE/"Unreal/Veyr/Content"; missing=[]; diff=[]; same=0; dl_skipped=0; sizediff=[]
tracked=set(subprocess.run(["git","ls-files","Unreal/Veyr/Content"],cwd=WT,capture_output=True,text=True).stdout.split("\n"))
for root,_,files in os.walk(live):
  for fn in files:
    p=Path(root)/fn; relp="Unreal/Veyr/Content/"+str(p.relative_to(live))
    if "__pycache__" in relp or fn==".DS_Store": continue
    mine=WT/relp
    st=os.stat(p, follow_symlinks=False)
    dataless=bool(st.st_flags & 0x40000000)
    if not mine.exists():
      missing.append({"file":relp,"bytes":st.st_size,"liveDataless":dataless,"tracked":relp in tracked}); continue
    if dataless:
      dl_skipped+=1
      if mine.stat().st_size!=st.st_size: sizediff.append(relp)
      continue
    if hashlib.sha256(p.read_bytes()).hexdigest()!=hashlib.sha256(mine.read_bytes()).hexdigest(): diff.append(relp)
    else: same+=1
out={"identicalToLive":same,"liveDatalessSizeCompared":dl_skipped,"liveDatalessSizeMismatch":sizediff,"differentFromLive":diff,"missingVersusLive":missing}
(R/"compare-live.json").write_text(json.dumps(out,indent=1)+"\n")
print(json.dumps({k:(v if not isinstance(v,list) else len(v)) for k,v in out.items()}))
