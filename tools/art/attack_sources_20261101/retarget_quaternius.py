"""Stage CC0 source motions on the unchanged knight for fit review in Blender."""
import bpy, json, hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
HELPER=ROOT/'tools/art/blender/fab_rig_testing/retarget.py'
OUT=ROOT/'Local/AttackSources20261102/QuaterniusRetarget'
g={'__file__':str(HELPER)};exec(compile(HELPER.read_text(),str(HELPER),'exec'),g)
g['OUT']=OUT;g['render']=lambda *args:None

def source_name(n,kind):
    mapping={'Hips':'pelvis','Spine':'spine_01','Spine1':'spine_02','Spine2':'spine_03','Neck':'neck_01','Head':'Head'}
    if n in mapping:return mapping[n]
    for side,suffix in [('Left','l'),('Right','r')]:
        if not n.startswith(side):continue
        part=n[len(side):]
        body={'Shoulder':'clavicle','Arm':'upperarm','ForeArm':'lowerarm','Hand':'hand','UpLeg':'thigh','Leg':'calf','Foot':'foot','ToeBase':'ball'}
        if part in body:return body[part]+'_'+suffix
        for finger in ['Index','Middle','Ring','Pinky','Thumb']:
            prefix='Hand'+finger
            if part.startswith(prefix):return f'{finger.lower()}_{int(part[len(prefix):] or 0)+1:02}_{suffix}'
    raise ValueError(n)
g['source_name']=source_name

hold_source=ROOT/'Local/CustomuseAssets/Polish20261025/idle-joins/knight/IdleOneHand_Blender_v2r4.glb'
bpy.ops.import_scene.gltf(filepath=str(hold_source));rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');bpy.context.scene.frame_set(0)
hold={b.name:b.matrix_basis.copy() for b in rig.pose.bones if any(b.name.startswith(side+'Hand'+finger) for side in ['Left','Right'] for finger in ['Index','Middle','Ring','Pinky','Thumb'])}
jobs=[(1,'Sprint_Loop',False),(2,'Sword_Dash',True),(2,'Sword_Heavy_Combo',True),(2,'Consume',False)]
for library,action,travel in jobs:
    file=next((ROOT/f'Local/AttackSources20261102/Quaternius{library}').rglob(f'UAL{library}_Standard_RM.glb'))
    name=f'Quaternius_{action}_v1';assert not (OUT/'Exports'/f'{name}.blend').exists()
    bpy.context.scene['session_owner']=g['OWNER']
    g['run'](file,'quaternius',name,travel,False,True,hold,action)
    p=OUT/'Exports'/f'{name}.json';d=json.loads(p.read_text());d.update(sourceAction=action,sourceSHA256=hashlib.sha256(file.read_bytes()).hexdigest(),license='CC0',accepted=False,sourceURL='https://quaternius.itch.io/universal-animation-library'+('-2' if library==2 else ''))
    p.write_text(json.dumps(d,indent=2)+'\n')
print('VEYR_QUATERNIUS_RETARGET_STAGED',flush=True)
