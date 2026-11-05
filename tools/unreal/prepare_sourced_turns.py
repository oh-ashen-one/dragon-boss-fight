#!/usr/bin/env python3
"""Factor authored Blender turns into native actor paths and canonical clips.

This is representation conversion: world motion is reconstructed and checked,
not newly authored. Never imports/activates assets or claims visible quality.
"""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/art/integration'))
from normalize_sourced import normalize_file
from normalize_approved import GLB as SourceGLB, UE
from normalize_customuse_glb import GLB
from graft_canonical_animation import graft
from import_customuse import compatible, inspect_glb

BASE = ROOT/'Local/CustomuseAssets/Polish20261025/knight-v044blender/import-plan-KnightB.json'
OUT = ROOT/'Local/CustomuseAssets/Polish20261025/knight-v045turns'
SOURCES = ROOT/'Local/AttackSources20261104/SourcedTurns/Exports'


def reconstruct(source, derived, normal, scale):
    original, converted = SourceGLB(source), SourceGLB(derived)
    translations = np.asarray(normal['rootTranslationSamplesCm'])
    yaws = np.asarray(normal['rootYawSamplesDegrees'])
    assert len(yaws) == len(translations) and np.isfinite(yaws).all()
    assert np.max(np.abs(np.diff(yaws))) < 15, 'Root yaw contains a wrap/jump'
    duration = normal['duration']
    worst_position, worst_angle, worst_matrix = 0., 0., 0.
    # Keys AND half-keys catch interpolation errors which exact sampled
    # inverse-matrix cancellation at the original keys would conceal.
    times = np.linspace(0,duration,2*(len(yaws)-1)+1)
    for t in times:
        f = min(float(t)*normal['rootSampleRate'],len(yaws)-1)
        i = int(f); j = min(i+1,len(yaws)-1); alpha = f-i
        translation = translations[i]*(1-alpha)+translations[j]*alpha
        yaw = yaws[i]*(1-alpha)+yaws[j]*alpha
        actor = np.eye(4)
        actor[:3,:3] = Rotation.from_rotvec([0,-np.radians(yaw),0]).as_matrix()
        actor[:3,3] = UE.T@translation/100
        old, _ = original.sample(float(t)); new, _ = converted.sample(float(t))
        for name in original.skin_names():
            a = old[original.names[name]]; b = actor@new[converted.names[name]]
            worst_matrix = max(worst_matrix,float(np.max(np.abs(a-b))))
            worst_position = max(worst_position,float(np.linalg.norm(a[:3,3]-b[:3,3])*scale))
            ra = a[:3,:3]/np.linalg.norm(a[:3,:3],axis=0)
            rb = b[:3,:3]/np.linalg.norm(b[:3,:3],axis=0)
            angle = np.degrees(np.arccos(np.clip((np.trace(ra.T@rb)-1)*.5,-1,1)))
            worst_angle = max(worst_angle,float(angle))
    return {'samples':len(times),'boneComparisons':len(times)*len(original.skin_names()),
            'maximumWorldPositionErrorCm':worst_position,'maximumWorldRotationErrorDegrees':worst_angle,
            'maximumMatrixError':worst_matrix,'limits':{'positionCm':.1,'rotationDegrees':.1},
            'passed':worst_position<=.1 and worst_angle<=.1}


def main():
    assert not OUT.exists(), 'Preserve previous preparations'
    base = json.loads(BASE.read_text())
    canonical = Path(base['rig']['file'])
    assert hashlib.sha256(canonical.read_bytes()).hexdigest() == base['rig']['sha256']
    diagnostics = json.loads((ROOT/'docs/master-goal-20261103/sourced-turn-diagnostics.json').read_text())
    source_records = {r['name']:r for r in diagnostics['candidates']}
    scale = diagnostics['scaleCmPerSourceUnit']
    plan = {k:v for k,v in base.items() if k!='clips'}
    plan.update(version='v045turns',replace_runtime_source='/Game/Characters/Customuse/KnightB/v044blender/DA_KnightB',
                purpose='Sourced Blender turn candidates; grounded/native/contact/quality checks pending',
                owner_approved=False,clips=[])
    rows = []
    for key, name in [('TurnRight180TwoHand','Mixamo_Turn180_A_v1'),
                      ('TurnRight180QuickTwoHand','Mixamo_Turn180_B_v1'),
                      ('TurnRight90TwoHand','Mixamo_Turn_A_v1'),
                      ('TurnLeft90TwoHand','Mixamo_Turn_B_v1')]:
        source = SOURCES/(name+'.glb'); record = source_records[name]
        assert hashlib.sha256(source.read_bytes()).hexdigest()==record['sourceSHA256']
        scene = ROOT/record['editableBlenderScene']
        assert hashlib.sha256(scene.read_bytes()).hexdigest()==record['editableSceneSHA256']
        meta = json.loads(source.with_suffix('.json').read_text())
        assert meta['authoringApplication']=='Blender'
        duration = SourceGLB(source).duration()
        intermediate = OUT/'intermediate'/source.name
        normal = normalize_file(source,SourceGLB(canonical),intermediate,120,duration,root_turn=True)
        target = OUT/'knight'/source.name
        proof = graft(canonical,intermediate,target)
        fidelity = reconstruct(source,target,normal,scale)
        rows.append({'clip':key,'normalization':normal,'graft':proof,'worldMotionReconstruction':fidelity})
        (OUT/('preparation-'+key+'.json')).write_text(json.dumps(rows[-1],indent=2)+'\n')
        assert fidelity['passed'], 'World-motion reconstruction failed; preserve diagnostic outputs, do not import'
        compatible(inspect_glb(base['rig']),inspect_glb({'file':str(target),'sha256':proof['outputSHA256']}))
        plan['clips'].append(dict(name=key,file=str(target),sha256=proof['outputSHA256'],
             mesh_variant=base['canonical_mesh_variant'],start_seconds=0.,end_seconds=duration,loop=False,
             gameplay_play_rate=1.,nominal_speed_cm_per_second=0.,damage_windows=[],impact_seconds=-1.,
             weapon_file=base['clips'][0]['weapon_file'],root_motion_policy='preserve',root_motion_removed=True,
             root_motion_vertical=False,root_sample_rate=normal['rootSampleRate'],
             root_translation_samples_cm=normal['rootTranslationSamplesCm'],
             root_yaw_samples_degrees=normal['rootYawSamplesDegrees'],source_duration=duration,
             approved_source_file=source.name,approved_source_sha256=record['sourceSHA256']))
        print(key,'world-motion conversion',fidelity['passed'],flush=True)
    plan['required_clips']=sorted(set(base['required_clips'])|{c['name'] for c in plan['clips']})
    (OUT/'import-plan-KnightB.json').write_text(json.dumps(plan,indent=2)+'\n')
    report={'nativeImported':False,'accepted':False,'sourceAuthoring':'Blender; conversion preserves authored world motion',
            'scope':'Two-hand source conversion only. One-hand variants and opposite180degree source remain required.',
            'clips':[{'clip':r['clip'],'rootYawEndDegrees':r['normalization']['rootYawSamplesDegrees'][-1],
                      'worldMotionReconstruction':r['worldMotionReconstruction']} for r in rows]}
    (ROOT/'docs/master-goal-20261103/sourced-turn-root-preparation.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
