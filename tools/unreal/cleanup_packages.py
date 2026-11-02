#!/usr/bin/env python3
"""Prune completed, receipt-owned package copies; dry-run unless --apply.

Explicitly retain the verified build, any justified fallback and current candidate.
Never discovers deletion targets by age/name alone, and never touches source caches.
"""
import argparse
import datetime
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--keep-app', type=Path, action='append', required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    keep = [p.resolve(strict=True) for p in args.keep_app]
    assert all(p.suffix == '.app' for p in keep)
    processes = subprocess.check_output(['ps', '-axo', 'command='], text=True)
    # File descriptors protect dependencies not visible in process arguments.
    opened = subprocess.run(['lsof', '-n', '-P', '-F', 'n'], capture_output=True, text=True)
    assert opened.returncode in (0, 1), 'Cannot inspect open files'
    references = processes + '\n' + opened.stdout
    links = [x.resolve() for app in keep for x in app.rglob('*') if x.is_symlink()]
    candidates = {}
    for receipt in sorted((ROOT/'Local').glob('package-*/receipt.json')):
        data = json.loads(receipt.read_text())
        if not data.get('packagingSucceeded'): continue
        apps = [Path(p) for p in data.get('apps', [])]
        if not apps: continue
        for app in apps:
            if app.exists() and app.resolve() not in keep:
                parent = app.parent
                if parent.parent == Path('/private/tmp') and parent.name.startswith('veyr-verified-bundle-'):
                    candidates[parent] = (receipt, 'superseded app; videos and receipts preserved')
        for original in data.get('originalArchives', []):
            p = Path(original)
            try: relative = p.relative_to(ROOT/'Builds')
            except ValueError: continue
            archive = ROOT/'Builds'/relative.parts[0]
            if archive.exists() and archive.name.startswith('Unreal-Mac-'):
                candidates[archive] = (receipt, 'redundant completed archive')
        stage = Path(data.get('stagingDirectory', '/invalid'))
        marker = stage/'veyr-stage-owner.json'
        if stage.parent == Path('/private/tmp') and marker.is_file():
            owner = json.loads(marker.read_text())
            if owner.get('project') == str(ROOT/'Unreal/Veyr') and owner.get('receiptDirectory') == str(receipt.parent):
                candidates[stage] = (receipt, 'redundant completed owned stage')
    removed, skipped = {}, {}
    before = shutil.disk_usage(ROOT).free
    for target, (receipt, reason) in candidates.items():
        if target.is_symlink() or not target.is_dir():
            skipped[str(target)] = 'not an ordinary directory'; continue
        if str(target) in references or any(p == target or target in p.parents for p in keep + links):
            skipped[str(target)] = 'live process, retained app or retained symlink dependency'; continue
        item = {'receipt': str(receipt.relative_to(ROOT)), 'reason': reason}
        if args.apply: shutil.rmtree(target)
        removed[str(target)] = item
    report = {'applied': args.apply, 'removed' if args.apply else 'planned': removed,
              'retained': list(map(str, keep)), 'skipped': skipped,
              'freeBytesBefore': before, 'freeBytesAfter': shutil.disk_usage(ROOT).free,
              'utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'applied': args.apply, 'directories': len(removed), 'skipped': len(skipped),
                      'freeGiBGained': (report['freeBytesAfter']-before)/2**30}))

if __name__ == '__main__': main()
