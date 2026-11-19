#!/usr/bin/env python3
"""Bring the git-ignored (private) Unreal content of one checkout into another with APFS clones.

Packaging needs content that is not in git: git-ignored paths under Unreal/Veyr/Content (Characters, ParagonGreystone,
ArtPass, some audio folders, ...) and under Unreal/Veyr/Config (for example the ignored DefaultEditor.ini). A fresh
worktree has none of it. This tool lists those paths from `git status --porcelain --ignored` in the SOURCE tree and
copies each into the same place in the TARGET tree with `cp -cRp` (copy-on-write clone: no extra disk, mtimes kept).

  clone_private_content.py --from /Users/midir/veyr-knight-20261028 --to ~/my-worktree [--untracked] [--dry-run]

Rules: read-only on the source (git runs with GIT_OPTIONAL_LOCKS=0, so even the index is untouched); only paths under
Unreal/Veyr/Content and Unreal/Veyr/Config; __pycache__, *.pyc and .DS_Store are ignored; a file already present with the
same size and mtime is skipped; a tracked file in the target is never overwritten; a differing untracked file already in
the target is kept and reported (--update replaces it). --untracked also brings untracked (not ignored) Content folders.

By default it also seeds <target>/Unreal/Veyr/DerivedDataCache from the source's with clones (`cp -cRn`, existing files are
never overwritten), so the first editor run in a fresh worktree does not rebuild every static mesh while holding the engine
lock. Skip it with --no-ddc.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

SCOPES = ('Unreal/Veyr/Content', 'Unreal/Veyr/Config')
JUNK_NAMES = {'__pycache__', '.DS_Store'}
GIT_ENV = {**os.environ, 'GIT_OPTIONAL_LOCKS': '0'}


def git(tree, *args):
    result = subprocess.run(['git', '-C', str(tree), *args], capture_output=True, env=GIT_ENV)
    if result.returncode:
        sys.exit(f'git {" ".join(args)} failed in {tree}: {result.stderr.decode(errors="replace").strip()}')
    return result.stdout


def is_junk(path):
    return any(part in JUNK_NAMES for part in path.parts) or path.suffix == '.pyc'


def list_entries(source, untracked):
    """(status, relative path) for ignored (and optionally untracked) entries inside the two scopes."""
    out = git(source, 'status', '--porcelain=v1', '-z', '--ignored=traditional', '--', *SCOPES)
    entries = []
    for item in out.split(b'\0'):
        if len(item) < 4:
            continue
        status, rel = item[:2].decode(), item[3:].decode()
        if status == '!!' or (untracked and status == '??'):
            rel = rel.rstrip('/')
            if any(rel == s or rel.startswith(s + '/') for s in SCOPES) and not is_junk(Path(rel)):
                entries.append((status, rel))
    return entries


def tracked_files(target):
    out = git(target, 'ls-files', '-z', '--', *SCOPES)
    return {p.decode() for p in out.split(b'\0') if p}


def same_file(a, b):
    sa, sb = a.stat(), b.stat()
    return sa.st_size == sb.st_size and int(sa.st_mtime) == int(sb.st_mtime)


def clone(source, destination, dry_run):
    if dry_run:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['/bin/cp', '-cRp', str(source), str(destination)], check=True)


def prune_junk(folder):
    for directory, directories, files in os.walk(folder):
        for name in list(directories):
            if name in JUNK_NAMES:
                shutil.rmtree(Path(directory) / name, ignore_errors=True)
                directories.remove(name)
        for name in files:
            if name in JUNK_NAMES or name.endswith('.pyc'):
                (Path(directory) / name).unlink(missing_ok=True)


def tree_stats(folder):
    files = size = 0
    for directory, _, names in os.walk(folder):
        for name in names:
            try:
                size += (Path(directory) / name).lstat().st_size
                files += 1
            except OSError:
                pass
    return files, size


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--from', dest='source', type=Path, required=True, help='checkout that holds the private content (read-only)')
    parser.add_argument('--to', dest='target', type=Path, required=True, help='worktree to fill')
    parser.add_argument('--untracked', action='store_true', help='also bring untracked (not ignored) Content folders')
    parser.add_argument('--update', action='store_true', help='replace a differing untracked file already in the target (never a tracked file)')
    parser.add_argument('--no-ddc', action='store_true', help='do not seed Unreal/Veyr/DerivedDataCache from the source tree')
    parser.add_argument('--dry-run', action='store_true', help='print what would be done, copy nothing')
    args = parser.parse_args()
    source, target = args.source.expanduser().resolve(), args.target.expanduser().resolve()
    if source == target:
        sys.exit('source and target are the same tree')
    for tree in (source, target):
        if not (tree / 'Unreal/Veyr/Veyr.uproject').is_file():
            sys.exit(f'{tree} is not a Veyr checkout (Unreal/Veyr/Veyr.uproject missing)')
    tracked = tracked_files(target)
    counts = {'cloned': 0, 'identical': 0, 'tracked': 0, 'differs': 0, 'updated': 0}
    cloned_bytes = 0
    conflicts, tracked_skips = [], []

    def tracked_under(rel):
        prefix = rel + '/'
        return any(t.startswith(prefix) for t in tracked)

    def handle(rel):
        nonlocal cloned_bytes
        s, d = source / rel, target / rel
        if is_junk(Path(rel)):
            return
        if s.is_dir() and not s.is_symlink():
            if not d.exists() and not tracked_under(rel):
                clone(s, d, args.dry_run)
                if not args.dry_run:
                    prune_junk(d)
                files, size = tree_stats(s if args.dry_run else d)
                counts['cloned'] += files
                cloned_bytes += size
                print(f'  clone dir  {rel}  ({files} files, {size / 1e6:.1f} MB)', flush=True)
                return
            for child in sorted(s.iterdir()):
                handle(f'{rel}/{child.name}')
            return
        if rel in tracked:
            counts['tracked'] += 1
            tracked_skips.append(rel)
            return
        if d.exists() or d.is_symlink():
            if d.is_file() and s.is_file() and same_file(s, d):
                counts['identical'] += 1
            elif args.update:
                if not args.dry_run:
                    d.unlink()
                clone(s, d, args.dry_run)
                counts['updated'] += 1
                cloned_bytes += s.stat().st_size
            else:
                counts['differs'] += 1
                conflicts.append(rel)
            return
        clone(s, d, args.dry_run)
        counts['cloned'] += 1
        cloned_bytes += s.lstat().st_size
        print(f'  clone file {rel}', flush=True)

    entries = list_entries(source, args.untracked)
    print(f'{source} -> {target}: {len(entries)} private entries' + (' (dry run)' if args.dry_run else ''), flush=True)
    for status, rel in entries:
        print(f'{"ignored  " if status == "!!" else "untracked"} {rel}', flush=True)
        handle(rel)
    print(f"summary: cloned {counts['cloned']} files ({cloned_bytes / 1e9:.2f} GB logical, clones take no extra disk), "
          f"skipped {counts['identical']} identical, {counts['tracked']} tracked-in-target, kept {counts['differs']} differing"
          + (f", updated {counts['updated']}" if args.update else ''))
    for rel in tracked_skips[:20]:
        print('  not overwritten (tracked in target):', rel)
    for rel in conflicts[:20]:
        print('  differs, kept (use --update to replace):', rel)
    if not args.no_ddc:
        seed_ddc(source, target, args.dry_run)
    return 0


def seed_ddc(source, target, dry_run):
    src, dst = source / 'Unreal/Veyr/DerivedDataCache', target / 'Unreal/Veyr/DerivedDataCache'
    if not src.is_dir():
        print('DerivedDataCache: none in the source tree, nothing to seed')
        return
    before_files, before_size = tree_stats(dst) if dst.is_dir() else (0, 0)
    if not dry_run:
        dst.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(['/bin/cp', '-cRn', str(src) + '/.', str(dst) + '/'], capture_output=True, text=True)
        if result.stderr.strip():
            print('DerivedDataCache: cp reported:', result.stderr.strip()[:300])
    files, size = tree_stats(dst) if dst.is_dir() else (0, 0)
    src_files, src_size = tree_stats(src)
    print(f'DerivedDataCache: {"would seed" if dry_run else "seeded"} {dst} (source {src_files} files, {src_size / 1e9:.2f} GB; '
          f'target now {files} files, {size / 1e9:.2f} GB, was {before_files}; existing files kept, clones take no extra disk)', flush=True)


if __name__ == '__main__':
    sys.exit(main())
