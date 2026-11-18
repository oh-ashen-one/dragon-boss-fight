#!/usr/bin/env python3
"""Install a newer verified Shipping build beside the existing one and repoint Play Veyr.app at it.

install_shipping.py does the first install and creates the launcher. This tool is for every later
build: it copies the signed app to ~/Applications/Veyr/<digest>/, checks the signature and the
binary digest, requires every run of the given regression suite record to have passed on that same
packaged app, then rewrites Local/LatestShipping.json. The existing launcher is not rebuilt (it reads
the pointer), and the previous installed build is left in place until --remove-previous is given.
"""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--receipt', type=Path, required=True, help='Local/package-*/receipt.json of the build')
p.add_argument('--suite', type=Path, action='append', required=True,
               help='Local/playtest-suite-*.json regression record(s) run on that build (repeatable)')
p.add_argument('--verification', required=True, help='repo-relative results document for the pointer')
p.add_argument('--remove-previous', action='store_true',
               help='delete the previously installed build folder if this repository installed it')
a = p.parse_args()

receipt = a.receipt.resolve(strict=True)
data = json.loads(receipt.read_text())
assert data['packagingSucceeded'] and data['configuration'] == 'Shipping' and len(data['apps']) == 1
source = Path(data['apps'][0]).resolve(strict=True)
assert (ROOT / a.verification).is_file(), 'verification document missing'
source_ids = set()
runs = 0
for suite in a.suite:
    for run in json.loads(suite.resolve(strict=True).read_text()):
        assert run.get('passed') is True, f"suite run did not pass: {run.get('spec')}"
        evidence = json.loads(Path(run['evidence']).read_text())
        source_ids.add(evidence['sourceId'])
        runs += 1
assert runs and len(source_ids) == 1, f'suite runs must share one source id, found {len(source_ids)}'
source_id = source_ids.pop()

subprocess.run(['codesign', '--verify', '--deep', '--strict', str(source)], check=True, capture_output=True)
info = plistlib.loads((source / 'Contents/Info.plist').read_bytes())
binary = source / 'Contents/MacOS' / info['CFBundleExecutable']
digest = hashlib.sha256(binary.read_bytes()).hexdigest()
folder = Path.home() / 'Applications/Veyr' / digest[:12]
app = folder / source.name
launcher = Path.home() / 'Applications/Play Veyr.app'
owner = json.loads((launcher / 'Contents/Resources/veyr-launcher-owner.json').read_text())
assert owner['repository'] == str(ROOT), 'the launcher belongs to another checkout'
pointer_path = ROOT / 'Local/LatestShipping.json'
previous = json.loads(pointer_path.read_text())
if not folder.exists():
    folder.mkdir(parents=True)
    subprocess.run(['ditto', str(source), str(app)], check=True)
    (folder / 'veyr-install-owner.json').write_text(json.dumps(
        {'repository': str(ROOT), 'packageReceipt': str(receipt), 'binarySHA256': digest}, indent=2) + '\n')
subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True, capture_output=True)
assert hashlib.sha256((app / 'Contents/MacOS' / info['CFBundleExecutable']).read_bytes()).hexdigest() == digest

pointer = {'app': str(app), 'packageReceipt': str(receipt.relative_to(ROOT)), 'binarySHA256': digest,
           'sourceId': source_id, 'verification': a.verification, 'launcher': str(launcher),
           'experimentalMovementEnabled': False, 'previousApp': previous.get('app')}
pointer_path.write_text(json.dumps(pointer, indent=2) + '\n')
subprocess.run([str(launcher / 'Contents/MacOS/PlayVeyr'), '--check'], check=True)
(ROOT / 'Local/ShippingInstallation.json').write_text(json.dumps(
    {**pointer, 'signatureVerified': True, 'launcherCheckPassed': True}, indent=2) + '\n')

if a.remove_previous and previous.get('app') and previous['app'] != str(app):
    old = Path(previous['app']).parent
    mark = old / 'veyr-install-owner.json'
    if old.parent == Path.home() / 'Applications/Veyr' and mark.is_file() and json.loads(mark.read_text())['repository'] == str(ROOT):
        shutil.rmtree(old)
        print('removed previous install', old)
print('installed', app, 'source', source_id[:12], 'runs', runs)
