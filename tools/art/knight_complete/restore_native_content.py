#!/usr/bin/env python3
"""Layer private native-content releases into a staging tree with provenance, then
move untracked files into the worktree. Downloaded archives are data only."""
import hashlib, json, os, subprocess, sys, zipfile
from pathlib import Path
R = Path(sys.argv[1]).resolve()          # restore folder
WT = Path(sys.argv[2]).resolve()         # worktree root
DL = R / "dl"; ST = R / "staging"
ORDER = [
 ("native-integration-20261025", ["Veyr-NativeContent-20261025-part1.zip","Veyr-NativeContent-20261025-part2.zip","Veyr-NativeContent-20261025-part3.zip","Veyr-NativeContent-20261025-prop-material-fix.zip"]),
 ("combat-arena-polish-native-20261025", ["Veyr-Polish-Native-20261025-part1.zip","Veyr-Polish-Native-20261025-part2.zip","Veyr-Polish-Native-20261025-part3.zip","Veyr-Polish-Native-20261025-material-skeleton-save.zip"]),
 ("sourced-animation-game-v027", ["Veyr-Native-Sourced-v027.zip"]),
 ("overhaul-game-v029-20261026", ["Veyr-Native-Overhaul-v029.zip"]),
]
def sha(b): return hashlib.sha256(b).hexdigest()
prov = {}; mani_checked = 0; mani_failed = []
for rel, zips in ORDER:
  for zn in zips:
    with zipfile.ZipFile(DL/rel/zn) as z:
      expected = {}
      for mname in ("manifest.json","native-delta-manifest.json","OVERHAUL-NATIVE-MANIFEST.json"):
        if mname in z.namelist():
          m = json.loads(z.read(mname))
          rows = m if isinstance(m, list) else m.get("files", [])
          for r in rows:
            if isinstance(r, dict) and "sha256" in r:
              expected[r.get("file") or r.get("path")] = r["sha256"]
      for n in z.namelist():
        if n.endswith("/") or not n.startswith("Unreal/Veyr/Content/"): continue
        p = (ST / n).resolve()
        if not p.is_relative_to(ST.resolve()): raise ValueError("unsafe path " + n)
        data = z.read(n); h = sha(data)
        if n in expected:
          mani_checked += 1
          if expected[n] != h: mani_failed.append(n)
        p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
        prov.setdefault(n, []).append({"release": rel, "archive": zn, "sha256": h, "bytes": len(data)})
tracked = set(subprocess.run(["git","ls-files","Unreal/Veyr/Content"],cwd=WT,capture_output=True,text=True,check=True).stdout.split("\n"))
moved = skipped_tracked = 0; rows = []
for n, hist in sorted(prov.items()):
  final = hist[-1]
  row = {"file": n, "release": final["release"], "archive": final["archive"], "sha256": final["sha256"], "bytes": final["bytes"], "overrides": [h["release"] for h in hist[:-1]]}
  if n in tracked:
    row["action"] = "skipped-git-tracked"; skipped_tracked += 1
  else:
    dst = WT / n
    if dst.exists(): raise FileExistsError(str(dst))
    dst.parent.mkdir(parents=True, exist_ok=True); os.rename(ST / n, dst); row["action"] = "restored"; moved += 1
  rows.append(row)
out = {"releasesInOrder": [r for r, _ in ORDER], "manifestHashesChecked": mani_checked, "manifestHashFailures": mani_failed, "restored": moved, "skippedGitTracked": skipped_tracked, "files": rows}
(R / "restore-provenance.json").write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps({k: v for k, v in out.items() if k != "files"}))
