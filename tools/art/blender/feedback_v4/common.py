"""Shared feedback-v4 parameters and safety checks (usable inside and outside Blender).

Precedence for every parameter: explicit overrides (run.py passes them as
VEYR_V4_PARAMS) > environment variable > v4 default. Relative paths resolve
against the repository root. Nothing here hard-codes a session owner.
"""
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
JOBS = ('heal', 'heavy', 'backpedal', 'guard_two', 'strafe_left', 'strafe_right')
REVIEW_BASE = {'heal': 'Heal', 'heavy': 'HeavyAttackOneHand', 'backpedal': 'Backpedal',
               'guard_two': 'GuardReadyTwoHand', 'strafe_left': 'StrafeLeft', 'strafe_right': 'StrafeRight'}
DEFAULTS = {
    'owner': 'fable-veyr-knight-v4-20261021',
    'scene_in': 'Local/Blender/feedback-v3-20261021',
    'out': 'Local/Blender/feedback-v4-20261021',
    'export_dir': 'Local/Blender/feedback-v4-20261021/export',
    'revision': '4',
    'approved_dir': 'tools/asset-review/.asset-cache/review',
    'allow_overwrite': False,
    'allow_reviewer_export': False,
}
ENV = {
    'owner': 'VEYR_V4_OWNER',
    'scene_in': 'VEYR_V4_SCENE_IN',
    'out': 'VEYR_V4_OUT',
    'export_dir': 'VEYR_V4_EXPORT_DIR',
    'revision': 'VEYR_V4_REVISION',
    'approved_dir': 'VEYR_V4_APPROVED_DIR',
    'allow_overwrite': 'VEYR_V4_ALLOW_OVERWRITE',
    'allow_reviewer_export': 'VEYR_V4_ALLOW_REVIEWER_EXPORT',
}
PATH_KEYS = ('scene_in', 'out', 'export_dir', 'approved_dir')
# Earlier candidates and approved material: v4 may read these, never write them.
PROTECTED = [REPO / p for p in (
    'Local/Blender/feedback-v3-20261021', 'Local/Blender/feedback-20261021',
    'Local/Blender/approved-rebuild-20261021', 'Local/Blender/remainder-20261021',
    'tools/asset-review/.asset-cache')]
REVIEWER_CACHE = REPO / 'tools/asset-review/.asset-cache/review'


def _truthy(value):
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def _inside(path, root):
    path, root = Path(path).resolve(), Path(root).resolve()
    return path == root or root in path.parents


def params(overrides=None):
    p = dict(DEFAULTS)
    if os.environ.get('VEYR_BLENDER_OWNER'):
        p['owner'] = os.environ['VEYR_BLENDER_OWNER']
    for key, var in ENV.items():
        if os.environ.get(var):
            p[key] = os.environ[var]
    p.update({k: v for k, v in (overrides or {}).items() if v is not None})
    unknown = set(p) - set(DEFAULTS)
    if unknown:
        raise ValueError(f'Unknown v4 parameters: {sorted(unknown)}')
    for key in PATH_KEYS:
        value = Path(p[key]).expanduser()
        p[key] = (value if value.is_absolute() else REPO / value).resolve()
    p['allow_overwrite'] = _truthy(p['allow_overwrite'])
    p['allow_reviewer_export'] = _truthy(p['allow_reviewer_export'])
    p['revision'] = str(p['revision'])
    check_writable(p['out'])
    if _inside(p['export_dir'], REVIEWER_CACHE) and p['allow_reviewer_export']:
        pass  # Explicit, separately authorised delivery to the reviewer only.
    else:
        check_writable(p['export_dir'])
    if _inside(p['out'], p['scene_in']) or _inside(p['scene_in'], p['out']):
        raise ValueError('v4 output must be separate from the input scene directory')
    return p


def check_writable(path):
    for root in PROTECTED:
        if _inside(path, root):
            raise PermissionError(f'Refusing to write into protected directory {root}')
    return Path(path)


def review_name(job, revision):
    return f'{REVIEW_BASE[job]}_Blender_v{revision}'


def approved_names():
    a = json.loads((REPO / 'tools/art/blender/rebuild/approvals.json').read_text())['clips']
    d = json.loads((REPO / 'tools/art/blender/feedback/decisions.json').read_text())['approved']
    return {e['file']: e['sha256'] for e in a + d}


def approved_jobs():
    """Jobs whose delivered clip (any revision) is owner-approved and therefore locked."""
    names = approved_names()
    return {job for job, base in REVIEW_BASE.items() if any(f.startswith(base + '_Blender_v') for f in names)}


def open_tagged(path, owner, port=None):
    """Open a .blend and immediately re-tag it for this session (veyr_rpc's guard)."""
    import bpy
    bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False)
    s = bpy.context.scene
    previous = s.get('session_owner')
    s['session_owner'] = owner
    s['mcp_port'] = int(port or os.environ.get('VEYR_BLENDER_PORT', '0') or 0)
    s['v4_opened_from'] = str(path)
    if previous is not None:
        s['v4_previous_session_owner'] = previous
    return previous
