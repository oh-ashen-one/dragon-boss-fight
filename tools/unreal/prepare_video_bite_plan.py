#!/usr/bin/env python3
"""Prepare the cut video2rig bite as an animation-only native revision (opt-in via -VeyrVideoBite).

Adds BiteV2rWindup/Active/Recovery as adjacent trims of one exported action so the runtime plays
one continuous motion; the keyed Bite* clips stay in the definition for before/after comparison.
"""
import argparse
import hashlib
import json
from pathlib import Path

from graft_canonical_animation import graft
from import_customuse import inspect_glb, compatible

ROOT = Path(__file__).resolve().parents[2]
POLISH = ROOT / 'Local/CustomuseAssets/Polish20261025'


def prepare(exported, source, cut_report, version, base_plan, replace_source):
    base = json.loads(base_plan.read_text())
    folder = POLISH / ('videobite-' + version)
    if folder.exists() or (ROOT / 'Unreal/Veyr/Content/Characters/Customuse/DragonV3B' / version).exists():
        raise ValueError('Fresh version required')
    export = json.loads(exported.with_suffix('.json').read_text())
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    if source_sha != export['sourceSHA256'] or hashlib.sha256(exported.read_bytes()).hexdigest() != export['outputSHA256']:
        raise ValueError('Source/export changed since validation')
    canonical = Path(base['rig']['file'])
    if hashlib.sha256(canonical.read_bytes()).hexdigest() != base['rig']['sha256']:
        raise ValueError('Canonical changed')
    out = folder / 'dragon' / exported.name
    proof = graft(canonical, exported, out)
    entry = {'file': str(out), 'sha256': proof['outputSHA256']}
    compatible(inspect_glb(base['rig']), inspect_glb(entry))
    cut = json.loads(cut_report.read_text())
    windup_end, active_end = cut['trims_out_s']['windup_end'], cut['trims_out_s']['active_end']
    duration = proof['durationSeconds']
    fps = cut['output_fps']
    # Contact = lowest mouth point during the strike window, in clip seconds.
    path = cut['mouth_path_m']
    window = [i for i in range(len(path)) if windup_end <= i / fps <= active_end]
    impact = min(window, key=lambda i: path[i][2]) / fps
    common = dict(**entry, loop=False, source_duration=duration, root_motion_policy='preserve', root_motion_removed=False,
                  root_translation_samples_cm=[], root_yaw_samples_degrees=[], root_sample_rate=fps,
                  nominal_speed_cm_per_second=0., gameplay_play_rate=1., damage_windows=[],
                  approved_source_file=source.name, approved_source_sha256=source_sha, owner_approved=False)
    clips = [dict(name='BiteV2rWindup', start_seconds=0., end_seconds=windup_end, impact_seconds=-1., **common),
             dict(name='BiteV2rActive', start_seconds=windup_end, end_seconds=active_end, impact_seconds=impact, **common),
             dict(name='BiteV2rRecovery', start_seconds=active_end, end_seconds=duration, impact_seconds=-1., **common)]
    plan = {k: v for k, v in base.items() if k != 'clips'}
    plan.update(version=version, replace_runtime_source=replace_source, owner_requested_revision=True, owner_approved=False,
                purpose='Opt-in video2rig bite (-VeyrVideoBite) for owner before/after review; keyed Bite clips retained')
    plan['required_clips'] = sorted(set(base['required_clips']) | {c['name'] for c in clips})
    plan['clips'] = clips
    folder.mkdir(parents=True, exist_ok=True)
    plan_path = folder / 'import-plan-DragonV3B.json'
    plan_path.write_text(json.dumps(plan, indent=2) + '\n')
    receipt = {'plan': str(plan_path), 'sha256': hashlib.sha256(plan_path.read_bytes()).hexdigest(), 'exportProof': export,
               'graftProof': proof, 'trims': {'windup_end': windup_end, 'active_end': active_end, 'impact': impact, 'duration': duration},
               'source': {'video': 'Higgsfield Seedance 2.5 job 1e68df15-5bc6-4181-b3a9-b8b3d714384e (2026-10-28), reused, no new spend',
                          'fit': 'video2rig mac-mps reader-64, median miss 3.76 px', 'cut_report': str(cut_report)},
               'status': 'prepared; native import and rendered verification pending'}
    (folder / 'preparation.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('Video bite prepared', version, 'duration', duration, 'trims', windup_end, active_end, 'impact', impact)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('exported', type=Path)
    p.add_argument('source', type=Path)
    p.add_argument('cut_report', type=Path)
    p.add_argument('--version', default='v034videobite')
    p.add_argument('--base-plan', type=Path, default=POLISH / 'idle-wings-v032/import-plan-DragonV3B.json')
    p.add_argument('--replace-source', default='/Game/Characters/Customuse/DragonV3B/v033wings/DA_DragonV3B')
    a = p.parse_args()
    prepare(a.exported, a.source, a.cut_report, a.version, a.base_plan, a.replace_source)
