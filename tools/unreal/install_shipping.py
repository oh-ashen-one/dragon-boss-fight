#!/usr/bin/env python3
"""Install a verified local Shipping bundle and a native, GPU-guarded launcher."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--receipt',type=Path,required=True)
p.add_argument('--verification',required=True)
a=p.parse_args();receipt=a.receipt.resolve(strict=True);data=json.loads(receipt.read_text())
assert data['packagingSucceeded'] and data['configuration']=='Shipping' and len(data['apps'])==1
verification=json.loads((ROOT/a.verification).read_text())
assert verification['passed'] and verification['runs'] and all(r['passed'] for r in verification['runs'])
assert len({r['sourceId'] for r in verification['runs']})==1
source_id=verification['runs'][0]['sourceId']
source=Path(data['apps'][0]).resolve(strict=True)
subprocess.run(['codesign','--verify','--deep','--strict',str(source)],check=True,capture_output=True)
info=plistlib.loads((source/'Contents/Info.plist').read_bytes());binary=source/'Contents/MacOS'/info['CFBundleExecutable']
digest=hashlib.sha256(binary.read_bytes()).hexdigest()
folder=Path.home()/'Applications/Veyr'/digest[:12];app=folder/source.name
assert not folder.exists(), 'Preserve an existing installed build'
folder.mkdir(parents=True)
subprocess.run(['ditto',str(source),str(app)],check=True)
subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True,capture_output=True)
assert hashlib.sha256((app/'Contents/MacOS'/info['CFBundleExecutable']).read_bytes()).hexdigest()==digest
(folder/'veyr-install-owner.json').write_text(json.dumps({'repository':str(ROOT),'packageReceipt':str(receipt),'binarySHA256':digest},indent=2)+'\n')
launcher=Path.home()/'Applications/Play Veyr.app'
assert not launcher.exists(), 'Preserve an existing launcher; inspect its ownership first'
resources=launcher/'Contents/Resources';executables=launcher/'Contents/MacOS';resources.mkdir(parents=True);executables.mkdir()
subprocess.run(['xcrun','swiftc',str(ROOT/'tools/unreal/PlayVeyr.swift'),'-o',str(executables/'PlayVeyr')],check=True,capture_output=True)
plist={'CFBundleIdentifier':'local.veyr.play','CFBundleName':'Play Veyr','CFBundleDisplayName':'Play Veyr','CFBundleExecutable':'PlayVeyr','CFBundlePackageType':'APPL','CFBundleVersion':'1','LSUIElement':True,'NSHighResolutionCapable':True}
(launcher/'Contents/Info.plist').write_bytes(plistlib.dumps(plist))
(resources/'LaunchConfig.json').write_text(json.dumps({'python':sys.executable,'script':str(ROOT/'tools/unreal/play_shipping.py'),'log':str(ROOT/'Local/owner-play-launch.log')},indent=2)+'\n')
(resources/'veyr-launcher-owner.json').write_text(json.dumps({'repository':str(ROOT),'purpose':'GPU-guarded Shipping launch'},indent=2)+'\n')
subprocess.run(['codesign','--force','--sign','-',str(launcher)],check=True,capture_output=True)
subprocess.run(['codesign','--verify','--deep','--strict',str(launcher)],check=True,capture_output=True)
pointer={'app':str(app),'packageReceipt':str(receipt.relative_to(ROOT)),'binarySHA256':digest,'sourceId':source_id,'verification':a.verification,'launcher':str(launcher),'experimentalMovementEnabled':False}
(ROOT/'Local/LatestShipping.json').write_text(json.dumps(pointer,indent=2)+'\n')
subprocess.run([str(executables/'PlayVeyr'),'--check'],check=True)
desktop=Path.home()/'Desktop/Play Veyr.app';assert not desktop.exists() and not desktop.is_symlink(), 'Preserve an existing desktop item'
desktop.symlink_to(launcher,target_is_directory=True)
(ROOT/'Local/ShippingInstallation.json').write_text(json.dumps({**pointer,'desktopLauncher':str(desktop),'signatureVerified':True,'launcherCheckPassed':True},indent=2)+'\n')
print('Shipping build installed; native guarded launcher verified')
