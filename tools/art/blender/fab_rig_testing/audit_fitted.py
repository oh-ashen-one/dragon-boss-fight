"""Verify source-body preservation and exported grip stability in Blender."""
import bpy,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=ROOT/'Local/FabRigTesting';OWNER='codex-veyr-fab-grip'
FILES=['Mixamo_Walk_v15','Mixamo_Attack_v15','Mixamo_Block_v15','Fab_Run_v15','Fab_Roll_v15']
BONES=['VeyrRoot','Hips','Spine','Spine1','Spine2','Neck','Head','LeftShoulder','RightShoulder','LeftUpLeg','LeftLeg','LeftFoot','LeftToeBase','RightUpLeg','RightLeg','RightFoot','RightToeBase']
def load(name,fps):
 assert bpy.context.scene.get('session_owner')==OWNER
 for o in list(bpy.context.scene.objects):bpy.data.objects.remove(o,do_unlink=True)
 bpy.data.orphans_purge(do_local_ids=True,do_linked_ids=False,do_recursive=True);s=bpy.context.scene;s.render.fps=int(fps);bpy.ops.import_scene.gltf(filepath=str(OUT/'Exports'/(name+'.glb')));s['session_owner']=OWNER;return next(o for o in s.objects if o.type=='ARMATURE')
results=[]
for name in FILES:
 row=json.loads((OUT/'Exports'/(name+'.json')).read_text());N=round(row['duration']*row['fps']);raw=name.rsplit('_v',1)[0]+'_v1';source=load(raw,row['fps']);samples={}
 for f in range(N+1):
  bpy.context.scene.frame_set(f);samples[f]={n:source.pose.bones[n].matrix.copy() for n in BONES}
 target=load(name,row['fps']);worst=0;grip0={};drift={'Right':0,'Left':0};held=['Right','Left'] if row['gripMode']=='two-handed' else ['Right'];previous=None;max_angle=0
 for i in range(N*2+1):
  f=i/2;bpy.context.scene.frame_set(int(f),subframe=f-int(f));p=target.pose.bones;H=p['WeaponSocket'].matrix.copy()
  if i%2==0:
   worst=max(worst,max(abs(p[n].matrix[a][b]-samples[int(f)][n][a][b]) for n in BONES for a in range(4) for b in range(4)))
   q=H.to_quaternion();q.normalize()
   if previous is not None:max_angle=max(max_angle,math.degrees(q.rotation_difference(previous).angle))
   previous=q.copy()
  for side in held:
   rel=H.inverted()@p[side+'Hand'].matrix
   if i==0:grip0[side]=rel.copy()
   drift[side]=max(drift[side],(H.to_3x3()@(rel.translation-grip0[side].translation)).length)
 assert worst<1e-4,(name,worst)
 assert max(drift.values())<.005,(name,drift)
 results.append({'name':name,'bodyBonesChecked':BONES,'maxBodyMatrixDelta':worst,'maxPalmDriftSceneUnits':{s:drift[s] for s in held},'maxSocketRotationDegreesPerBakedFrame':max_angle,'duration':row['duration'],'fps':row['fps'],'gripMode':row['gripMode']})
 print(name,'body',worst,'grip',drift,'angle',max_angle,flush=True)
(OUT/'Evidence/fitted-motion-audit.json').write_text(json.dumps(results,indent=2))
