#!/usr/bin/env python3
"""Dependency closure of Paragon effect assets in the Epic vault cache (read-only).

Every Unreal package stores the names of the packages it imports in its name table as plain
strings (/Game/...). Following those strings from the chosen particle systems gives the set of
.uasset/.uexp/.ubulk files that must be copied into Unreal/Veyr/Content with the same /Game/...
paths so the references resolve. Nothing is copied unless --copy-to is given.

    python3 tools/unreal/paragon_fx_closure.py --json Data/dragon/ground_fx.json
    python3 tools/unreal/paragon_fx_closure.py --json Data/dragon/ground_fx.json --copy-to Unreal/Veyr/Content
"""
import argparse, json, re, shutil, sys
from pathlib import Path

VAULT = Path('/Users/Shared/UnrealEngine/Launcher/VaultCache')
PATTERN = re.compile(rb'/Game/[A-Za-z0-9_./-]+')


def locate(package):
    # /Game/ParagonRampage/FX/... -> VaultCache/ParagonRampage/data/Content/ParagonRampage/FX/...
    rel = package[len('/Game/'):]
    pack = rel.split('/', 1)[0]
    path = VAULT / pack / 'data' / 'Content' / (rel + '.uasset')
    if path.exists():
        return path
    path = path.with_suffix('.umap')
    return path if path.exists() else None


def soft_paths(node):
    if isinstance(node, dict):
        for value in node.values():
            yield from soft_paths(value)
    elif isinstance(node, list):
        for value in node:
            yield from soft_paths(value)
    elif isinstance(node, str) and node.startswith('/Game/Paragon'):
        yield node.split('.', 1)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', required=True)
    ap.add_argument('--copy-to')
    args = ap.parse_args()
    roots = sorted(set(soft_paths(json.loads(Path(args.json).read_text()))))
    seen, missing, queue = {}, [], list(roots)
    while queue:
        package = queue.pop()
        if package in seen:
            continue
        path = locate(package)
        seen[package] = path
        if path is None:
            missing.append(package)
            continue
        for match in set(PATTERN.findall(path.read_bytes())):
            name = match.decode('ascii', 'ignore').split('.', 1)[0].rstrip('/')
            if name.startswith('/Game/') and name not in seen:
                queue.append(name)
    files = []
    for package, path in sorted(seen.items()):
        if path is None:
            continue
        for sibling in (path.with_suffix(s) for s in ('.uasset', '.umap', '.uexp', '.ubulk', '.uptnl')):
            if sibling.exists():
                files.append((package, sibling))
    total = sum(f.stat().st_size for _, f in files)
    folders = sorted({p.rsplit('/', 1)[0] for p in seen if seen[p]})
    print(json.dumps({'roots': roots, 'packages': len([p for p in seen if seen[p]]), 'files': len(files),
                      'megabytes': round(total / 1e6, 1), 'missing': missing, 'folders': folders}, indent=1))
    if args.copy_to:
        dest_root = Path(args.copy_to)
        for package, src in files:
            dest = dest_root / (package[len('/Game/'):] + src.suffix)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        print(f'copied {len(files)} files into {dest_root}', file=sys.stderr)
    return 1 if missing else 0


if __name__ == '__main__':
    sys.exit(main())
