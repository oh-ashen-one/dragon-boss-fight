#!/usr/bin/env python3
"""Prepare several cut video2rig moves as one animation-only native DragonV3B revision.

Manifest JSON: {"version": ..., "base_plan": ..., "replace_source": ..., "moves": [
  {"stem": "Claw1", "phases": true|false, "loop": false, "export": GLB, "source": BLEND, "cut_report": JSON,
   "impact_source_frame": 72, "source_fps": 24}]}
Phased moves become <Stem>Windup/Active/RecoveryV2r adjacent trims of one action; others become <Stem>V2r.
"""
import hashlib
import json
import sys
from pathlib import Path

from graft_canonical_animation import graft
from import_customuse import inspect_glb, compatible

ROOT = Path(__file__).resolve().parents[2]
POLISH = ROOT / 'Local/CustomuseAssets/Polish20261025'


def out_seconds(spec, src_frame, fps):
    """Output time of a source frame under the cut's per-phase rates (blend smoothing ignored, ms-level)."""
    t = 0.0
    for f0, f1, rate in spec['rates']:
        if src_frame <= f0:
            break
        t += (min(src_frame, f1) - f0) / (fps * rate)
    return t


def main(manifest_path):
    m = json.loads(Path(manifest_path).read_text())
    base = json.loads(Path(m['base_plan']).read_text())
    version = m['version']
    folder = POLISH / ('videomoves-' + version)
    if folder.exists() or (ROOT / 'Unreal/Veyr/Content/Characters/Customuse/DragonV3B' / version).exists():
        raise ValueError('Fresh version required')
    canonical = Path(base['rig']['file'])
    if hashlib.sha256(canonical.read_bytes()).hexdigest() != base['rig']['sha256']:
        raise ValueError('Canonical changed')
    clips, proofs = [], []
    for mv in m['moves']:
        exported, source = Path(mv['export']), Path(mv['source'])
        export = json.loads(exported.with_suffix('.json').read_text())
        source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
        if source_sha != export['sourceSHA256'] or hashlib.sha256(exported.read_bytes()).hexdigest() != export['outputSHA256']:
            raise ValueError('Source/export changed since validation: ' + mv['stem'])
        out = folder / 'dragon' / exported.name
        proof = graft(canonical, exported, out)
        entry = {'file': str(out), 'sha256': proof['outputSHA256']}
        compatible(inspect_glb(base['rig']), inspect_glb(entry))
        cut = json.loads(Path(mv['cut_report']).read_text())
        spec = json.loads(Path(mv['cut_spec']).read_text())
        duration = proof['durationSeconds']
        common = dict(**entry, source_duration=duration, root_motion_policy='preserve', root_motion_removed=False,
                      root_translation_samples_cm=[], root_yaw_samples_degrees=[], root_sample_rate=cut['output_fps'],
                      nominal_speed_cm_per_second=0., gameplay_play_rate=1., damage_windows=[],
                      approved_source_file=source.name, approved_source_sha256=source_sha, owner_approved=False)
        if mv.get('phases'):
            w, a = cut['trims_out_s']['windup_end'], cut['trims_out_s']['active_end']
            impact = min(max(out_seconds(spec, mv['impact_source_frame'], mv['source_fps']), w), a)
            clips += [dict(name=mv['stem'] + 'WindupV2r', loop=False, start_seconds=0., end_seconds=w, impact_seconds=-1., **common),
                      dict(name=mv['stem'] + 'ActiveV2r', loop=False, start_seconds=w, end_seconds=a, impact_seconds=impact, **common),
                      dict(name=mv['stem'] + 'RecoveryV2r', loop=False, start_seconds=a, end_seconds=duration, impact_seconds=-1., **common)]
        else:
            clips.append(dict(name=mv['stem'] + 'V2r', loop=bool(mv.get('loop')), start_seconds=0., end_seconds=duration,
                              impact_seconds=-1., **common))
        proofs.append({'stem': mv['stem'], 'export': export, 'graft': proof})
    plan = {k: v for k, v in base.items() if k != 'clips'}
    plan.update(version=version, replace_runtime_source=m['replace_source'], owner_requested_revision=True, owner_approved=False,
                purpose='Overnight video2rig moves (default when present; -VeyrLegacyDragon restores keyed clips)')
    plan['required_clips'] = sorted(set(base['required_clips']) | {c['name'] for c in clips})
    plan['clips'] = clips
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / 'import-plan-DragonV3B.json'
    path.write_text(json.dumps(plan, indent=2) + '\n')
    (folder / 'preparation.json').write_text(json.dumps({'plan': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                                         'clips': [c['name'] for c in clips], 'proofs': proofs}, indent=2) + '\n')
    print('Prepared', version, len(clips), 'clips:', ', '.join(c['name'] for c in clips))


if __name__ == '__main__':
    main(sys.argv[1])
