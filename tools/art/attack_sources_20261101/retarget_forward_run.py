"""Retarget the explicitly-forward licensed Mixamo run; never reuse the backward namesake."""
import bpy,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
H=ROOT/'tools/art/blender/fab_rig_testing/retarget.py';g={'__file__':str(H)};exec(compile(H.read_text(),str(H),'exec'),g)
SOURCE=ROOT/'Local/AttackSources20261102/MixamoGreatSword/selected/ForwardRun.fbx'
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()=='ee48df1f77c89f5251e4e769dbd9fe26ba9c56415a0f08e2047fbf94d141b57f'
OUT=ROOT/'Local/AttackSources20261103/ForwardRun';NAME='Mixamo_ForwardRun_v1';assert not (OUT/'Exports'/(NAME+'.blend')).exists()
g['OUT']=OUT;g['render']=lambda *args:None
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(ROOT/'Local/CustomuseAssets/Polish20261025/idle-joins/knight/IdleTwoHand_Blender_v2r4.glb'))
rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');bpy.context.scene.frame_set(0)
hold={b.name:b.matrix_basis.copy() for b in rig.pose.bones if any(b.name.startswith(side+'Hand'+finger) for side in ['Left','Right'] for finger in ['Index','Middle','Ring','Pinky','Thumb'])}
bpy.context.scene['session_owner']=g['OWNER'];g['run'](SOURCE,'mixamo',NAME,True,False,True,hold)
p=OUT/'Exports'/(NAME+'.json');d=json.loads(p.read_text());d.update(sourceSHA256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),sourceMotion='Explicitly forward Great Sword Run',sourceLicense='Adobe Mixamo royalty-free project incorporation; no raw-library redistribution',accepted=False);p.write_text(json.dumps(d,indent=2)+'\n')
review={'__file__':str(H)};exec(compile(H.read_text(),str(H),'exec'),review);review['OUT']=OUT;end=bpy.context.scene.frame_end;review['render'](NAME,[round(end*i/8) for i in range(9)])
print('FORWARD_RUN_RETARGETED_REVIEW_PENDING',flush=True)
