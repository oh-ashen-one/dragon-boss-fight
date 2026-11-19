#!/usr/bin/env python3
"""Guarded removal of the fresh stage folder package.py creates under /private/tmp."""
import json
from pathlib import Path
import shutil

TMP_ROOT = Path('/private/tmp')


def remove_owned_stage(stage_base, project_dir, *, tmp_root=TMP_ROOT):
    """Remove stage_base only if it is an owned veyr-stage folder directly under tmp_root.

    Returns True when the folder was removed, False when any guard refused (nothing is touched then).
    """
    supplied = Path(stage_base)
    try:
        if supplied.is_symlink() or not supplied.is_dir():
            return False
        resolved = supplied.resolve()
        if supplied.parent != tmp_root or resolved.parent != tmp_root.resolve() or not resolved.name.startswith('veyr-stage-'):
            return False
        marker = resolved / 'veyr-stage-owner.json'
        if marker.is_symlink() or not marker.is_file():
            return False
        owner = json.loads(marker.read_text())
        if not isinstance(owner, dict) or owner.get('project') != str(Path(project_dir).resolve()):
            return False
        shutil.rmtree(resolved)
    except (OSError, ValueError):
        return False
    return not resolved.exists()
