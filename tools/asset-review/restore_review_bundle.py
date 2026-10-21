#!/usr/bin/env python3
"""Restore a private review archive, verifying hashes and preserving existing work."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import zipfile

def restore(archive, destination):
    destination=destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        manifest=json.loads(bundle.read('manifest.json'))
        entries=manifest['files']
        # Validate the complete archive and all existing destinations before writes.
        for entry in entries:
            relative=PurePosixPath(entry['path'])
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('Unsafe archive path')
            target=(destination/relative).resolve()
            if not target.is_relative_to(destination):
                raise ValueError('Destination escapes checkout')
            digest=hashlib.sha256()
            with bundle.open(entry['path']) as source:
                for chunk in iter(lambda:source.read(1024*1024),b''):digest.update(chunk)
            if digest.hexdigest()!=entry['sha256']:
                raise ValueError(f"Archive hash mismatch: {relative}")
            if target.exists():
                with target.open('rb') as current:
                    existing_hash=hashlib.file_digest(current,'sha256').hexdigest()
                if existing_hash!=entry['sha256']:
                    raise FileExistsError(f'Preserving different existing file: {target}')
        for entry in entries:
            target=destination/entry['path']
            if target.exists():continue
            target.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=target.parent,delete=False) as stage:
                temporary=Path(stage.name)
                with bundle.open(entry['path']) as source:shutil.copyfileobj(source,stage)
            try:
                os.link(temporary,target)  # Atomic create; preserve a concurrent writer.
            finally:
                temporary.unlink(missing_ok=True)
    print(f"Verified and restored {len(entries)} files into {destination}")

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive',type=Path)
    p.add_argument('--destination',type=Path,default=Path(__file__).resolve().parents[2])
    a=p.parse_args();restore(a.archive,a.destination)
