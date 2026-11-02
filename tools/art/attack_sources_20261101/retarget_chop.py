"""Evaluate a different licensed two-hand source after two rejected Kevin revisions."""
import bpy,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
helper=Path(__file__).with_name('retarget_quaternius.py');g0={'__file__':str(helper)};exec(compile(helper.read_text().split('hold_source=')[0],str(helper),'exec'),g0);g=g0['g']
hold_source=ROOT/'Local/CustomuseAssets/Polish20261025/idle-joins/knight/IdleTwoHand_Blender_v2r4.glb'
bpy.ops.import_scene.gltf(filepath=str(hold_source));rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');bpy.context.scene.frame_set(0)
hold={b.name:b.matrix_basis.copy() for b in rig.pose.bones if any(b.name.startswith(side+'Hand'+finger) for side in ['Left','Right'] for finger in ['Index','Middle','Ring','Pinky','Thumb'])}
source=next((ROOT/'Local/AttackSources20261102/Quaternius2').rglob('UAL2_Standard_RM.glb'));name='Quaternius_HeavyChop_v1';out=g0['OUT'];assert not (out/'Exports'/f'{name}.blend').exists();bpy.context.scene['session_owner']=g['OWNER']
g['run'](source,'quaternius',name,False,False,True,hold,'TreeChopping_Loop')
p=out/'Exports'/f'{name}.json';d=json.loads(p.read_text());d.update(sourceAction='TreeChopping_Loop',sourceSHA256=hashlib.sha256(source.read_bytes()).hexdigest(),license='CC0',accepted=False);p.write_text(json.dumps(d,indent=2)+'\n')
h=ROOT/'tools/art/blender/fab_rig_testing/retarget.py';render={'__file__':str(h)};exec(compile(h.read_text(),str(h),'exec'),render);render['OUT']=out;end=bpy.context.scene.frame_end;render['render'](name,[round(end*i/8) for i in range(9)])
print('VEYR_ALTERNATE_HEAVY_STAGED')
