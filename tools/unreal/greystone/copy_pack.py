#!/usr/bin/env python3
"""Copy Paragon: Greystone (and optionally the GASP mannequin set) from the launcher VaultCache into the project.

No engine. The VaultCache is read-only to us; the copies land in .gitignored folders:
  Content/ParagonGreystone/              (pack mount path /Game/ParagonGreystone/, unchanged, so references resolve)
  Content/Characters/UEFN_Mannequin/     (--gasp: GASP's /Game/Characters/UEFN_Mannequin, same mount path)
  Content/Characters/Paragon/Heroes/TwinBlast/  (--gasp: the RTG_UEFN_to_TwinBlast template, its IK rig and preview mesh)
Refuses to overwrite a non-empty destination unless --update. Writes a SHA-256 manifest under Local/greystone/.

usage: copy_pack.py [--project /path/to/Unreal/Veyr] [--gasp] [--update]
"""
import argparse
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import greystone_common as g

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument('--project', type=Path, default=g.PROJECT)
p.add_argument('--gasp', action='store_true')
p.add_argument('--update', action='store_true')
a = p.parse_args()

project = a.project.resolve()
assert (project / 'Veyr.uproject').is_file(), 'not the Veyr project: ' + str(project)
root = project.parents[1]
ignored = subprocess.run(['git', '-C', str(root), 'check-ignore', '-q', str(project / 'Content/ParagonGreystone/x.uasset')])
assert ignored.returncode == 0, 'Content/ParagonGreystone is not .gitignored in this checkout: refuse to copy'

jobs = [(g.GREYSTONE_VAULT, project / 'Content/ParagonGreystone')]
if a.gasp:
    for rel in ('Characters/UEFN_Mannequin', 'Characters/Paragon/Heroes/TwinBlast'):  # whole hero: the RTG's preview mesh lives in Meshes/
        jobs.append((g.GASP_VAULT / rel, project / 'Content' / rel))
        check = subprocess.run(['git', '-C', str(root), 'check-ignore', '-q', str(project / 'Content' / rel / 'x.uasset')])
        if check.returncode != 0 and rel.startswith('Characters/Paragon'):
            sys.exit('Add Unreal/**/Content/Characters/Paragon/ to .gitignore before copying GASP TwinBlast rigs')
        assert check.returncode == 0, rel + ' is not .gitignored'

stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
manifest = {'created': stamp, 'project': str(project), 'copies': []}
for source, destination in jobs:
    assert source.is_dir(), 'missing VaultCache source: ' + str(source)
    if destination.exists() and any(destination.iterdir()) and not a.update:
        sys.exit('destination not empty (use --update): ' + str(destination))
    files = sorted(x for x in source.rglob('*') if x.is_file())
    entries = []
    for f in files:
        rel = f.relative_to(source)
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = g.sha256(f)
        if not (target.exists() and g.sha256(target) == digest):
            # APFS clone first (same volume as the VaultCache: no extra disk), plain copy otherwise.
            if subprocess.run(['/bin/cp', '-c', '-p', str(f), str(target)], capture_output=True).returncode != 0:
                shutil.copy2(f, target)
        entries.append({'path': str(rel), 'bytes': f.stat().st_size, 'sha256': digest})
    manifest['copies'].append({'source': str(source), 'destination': str(destination), 'files': len(entries),
                               'bytes': sum(e['bytes'] for e in entries), 'entries': entries})
    print(f'{len(entries)} files -> {destination}')

out = root / 'Local/greystone'
out.mkdir(parents=True, exist_ok=True)
path = out / f'pack-manifest-{stamp}.json'
path.write_text(json.dumps(manifest, indent=1) + '\n')
print('manifest', path)
# Expected for the Greystone pack (VaultCache listing 2026-11-18): 1735 files.
greystone = manifest['copies'][0]['files']
if greystone != 1735:
    print(f'NOTE: Greystone pack has {greystone} files, the 2026-11-18 listing had 1735')
