"""Retarget the licensed free two-handed sources; no replacement or whole-motion authoring."""
import bpy
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
HELPER=ROOT/'tools/art/blender/fab_rig_testing/retarget.py'
SOURCE=ROOT/'Local/AttackSources20261101/KevinIglesias/extracted'
OUT=ROOT/'Local/AttackSources20261101/KevinIglesias/Retarget'
g={'__file__':str(HELPER)}
exec(compile(HELPER.read_text(),str(HELPER),'exec'),g)
g['OUT']=OUT;g['render']=lambda *args:None
main=dict(g['MAIN']);main.pop('Spine1');main['Spine']='Spine2'
g['MAIN']=main

def source_name(name,kind):
    common={'Hips':'B-hips','Spine':'B-spine','Spine2':'B-chest','Neck':'B-neck','Head':'B-head'}
    if name in common:return common[name]
    for side,suffix in [('Left','.L'),('Right','.R')]:
        if not name.startswith(side):continue
        part=name[len(side):]
        body={'Shoulder':'shoulder','Arm':'upperArm','ForeArm':'forearm','Hand':'hand',
              'UpLeg':'thigh','Leg':'shin','Foot':'foot','ToeBase':'toe'}
        if part in body:return 'B-'+body[part]+suffix
        for finger,base in [('Index','indexFinger'),('Middle','middleFinger'),('Ring','ringFinger'),('Pinky','pinky'),('Thumb','thumb')]:
            prefix='Hand'+finger
            if part.startswith(prefix):
                number=int(part[len(prefix):] or '0')+1
                return f'B-{base}{number:02}{suffix}'
    raise ValueError('Unmapped target bone: '+name)

g['source_name']=source_name
hold_source=ROOT/'Local/CustomuseAssets/Polish20261025/idle-joins/knight/IdleTwoHand_Blender_v2r4.glb'
bpy.ops.import_scene.gltf(filepath=str(hold_source));hold_rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');bpy.context.scene.frame_set(0)
finger_hold={b.name:b.matrix_basis.copy() for b in hold_rig.pose.bones if any(b.name.startswith(side+'Hand'+finger) for side in ['Left','Right'] for finger in ['Index','Middle','Ring','Pinky','Thumb'])}
assert len(finger_hold)==30
jobs=[('Kevin_Heavy_M_v6','Animations/Male/Combat/2H/HumanM@Attack2H01.fbx'),
      ('Kevin_Heavy_F_v6','Animations/Female/Combat/2H/HumanF@Attack2H01.fbx'),
      ('Kevin_2H_Idle_M_v6','Animations/Male/Combat/2H/HumanM@CombatIdle2H01.fbx')]
for name,rel in jobs:
    path=SOURCE/rel;sha=hashlib.sha256(path.read_bytes()).hexdigest()
    assert not (OUT/'Exports'/(name+'.glb')).exists()
    bpy.context.scene['session_owner']=g['OWNER']
    g['run'](path,'kevin_iglesias',name,False,False,True,finger_hold)
    report_path=OUT/'Exports'/(name+'.json');report=json.loads(report_path.read_text())
    expected=set(main)|{'Head','LeftToeBase','RightToeBase'}
    assert set(report['mappedBones'])==expected
    assert set(report['fullPalmFrameBones'])=={'LeftHand','RightHand'}
    assert len(report['preservedFingerBones'])==30
    assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
    report.update(sourceSHA256=sha,sourceUnchanged=True,sourceMotion='licensed free original',
                  corrections='Full anatomical palm-frame and segment FK calibration; proportional hip transfer; approved existing two-hand finger hold preserved to avoid gauntlet deformation',
                  fingerHoldSourceSHA256=hashlib.sha256(hold_source.read_bytes()).hexdigest(),
                  spineBridge='Target Spine1 follows its parent; source B-spine maps Spine, B-chest maps Spine2',
                  accepted=False)
    report_path.write_text(json.dumps(report,indent=2)+'\n')
print('VEYR_KEVIN_RETARGET_COMPLETE',flush=True)
