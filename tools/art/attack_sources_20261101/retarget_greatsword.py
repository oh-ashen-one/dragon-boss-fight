"""Retarget licensed Mixamo greatsword motions; keep original motion and files."""
import bpy,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];H=ROOT/'tools/art/blender/fab_rig_testing/retarget.py';g={'__file__':str(H)};exec(compile(H.read_text(),str(H),'exec'),g)
SRC=ROOT/'Local/AttackSources20261102/MixamoGreatSword';OUT=SRC/'Retarget';g['OUT']=OUT;g['render']=lambda *args:None
hold_source=ROOT/'Local/CustomuseAssets/Polish20261025/idle-joins/knight/IdleTwoHand_Blender_v2r4.glb'
bpy.ops.import_scene.gltf(filepath=str(hold_source));rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');bpy.context.scene.frame_set(0)
hold={b.name:b.matrix_basis.copy() for b in rig.pose.bones if any(b.name.startswith(side+'Hand'+finger) for side in ['Left','Right'] for finger in ['Index','Middle','Ring','Pinky','Thumb'])}
jobs=[('PowerSlash',SRC/'selected/PowerSlash.fbx',True),('DownwardSlash',SRC/'selected/DownwardSlash.fbx',True),('JumpAttack',SRC/'extracted/great sword jump attack.fbx',True),('SlideAttack',SRC/'extracted/great sword slide attack.fbx',True),('HighSpinAttack',SRC/'extracted/great sword high spin attack.fbx',True),('GreatSwordRun',SRC/'extracted/great sword run.fbx',True),('GreatSwordIdle',SRC/'extracted/great sword idle.fbx',False),('RunStopOneHand',SRC/'selected/RunStopOneHand.fbx',True),('RunStopTwoHand',SRC/'selected/RunStopTwoHand.fbx',True)]
for key,source,travel in jobs:
 name='Mixamo_'+key+'_v1';assert not (OUT/'Exports'/f'{name}.blend').exists();bpy.context.scene['session_owner']=g['OWNER'];g['run'](source,'mixamo',name,travel,False,True,hold)
 p=OUT/'Exports'/f'{name}.json';d=json.loads(p.read_text());d.update(sourceSHA256=hashlib.sha256(source.read_bytes()).hexdigest(),sourceMotion=key,sourceLicense='Adobe Mixamo royalty-free project incorporation; no raw-library redistribution',accepted=False);p.write_text(json.dumps(d,indent=2)+'\n')
 render={'__file__':str(H)};exec(compile(H.read_text(),str(H),'exec'),render);render['OUT']=OUT;end=bpy.context.scene.frame_end;render['render'](name,[round(end*i/8) for i in range(9)])
print('VEYR_MIXAMO_GREATSWORD_RETARGETED')
