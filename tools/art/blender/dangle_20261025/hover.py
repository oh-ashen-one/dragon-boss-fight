"""Execute inside the session-owned Blender MCP. Existing wing loop, new four-limb hang."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
__file__=str(ROOT/'tools/art/blender/polish_20261025/dragon.py')
exec(compile(Path(__file__).read_text(),__file__,'exec'))
OWNER='codex-veyr-dangle-20261025';OUT=ROOT/'Local/Blender/dangle-20261025'
BASE=ROOT/'Local/Blender/polish-20261025/Dragon_FlyHover_Blender_polish_v1.blend'

def author():
 open_scene(IDLE);c=bpy.data.objects['DRAGON_CTRL'];idle={n:c.pose.bones[n].matrix.copy() for n in ('IK_FL','IK_FR','IK_HL','IK_HR')}
 open_scene(BASE);s=bpy.context.scene;c=bpy.data.objects['DRAGON_CTRL'];p=c.pose.bones
 hips={};targets={}
 for f in range(61):
  s.frame_set(f);hips[f]={};targets[f]={};sway=math.sin(2*math.pi*f/60)
  for side,prefix,sign in [('L','1',1),('R','0',-1)]:
   hip=p[f'C_tripo::{prefix}_Right_Limb_0'].head.copy();hips[f][side]=hip
   for kind in ('H','F'):
    n='IK_'+kind+side
    # Rotation is derived from the planted paw, preserving the paw's roll.
    # Positive Y pitch points forward-facing claws toward gravity (Z-down).
    pitch=65 if kind=='H' else 55
    rot=Quaternion(Vector((0,1,0)),math.radians(pitch+3*sway))@idle[n].to_quaternion()
    if kind=='H':pos=hip+Vector((-.01+.004*sway,sign*.038,-.14))
    else:
     # Front-left source skeleton has one arm segment; right has two. Use a
     # shared chest reference for symmetric wrist height without stretching.
     sh=p['C_tripo::1_Left_Limb_0'].head.copy()
     pos=Vector((sh.x+.060+.004*sway,sign*(abs(sh.y)+.018),sh.z-.113))
    targets[f][n]=Matrix.Translation(pos)@rot.to_matrix().to_4x4()
 act=bpy.data.actions.new('Dragon_Hover_Dangle_v2_EditableFourLimbIK');c.animation_data.action=act
 for f in range(61):
  s.frame_set(f)
  for n,m in targets[f].items():key_matrix(p[n],m,f)
 for fc in curves(act):
  for k in fc.keyframe_points:k.interpolation='LINEAR'
 # Retain the calibrated hind bend planes. Set all IK chains non-stretching.
 for b in p:
  for con in b.constraints:
   if con.type=='IK':con.use_stretch=False;con.iterations=128
 for f in range(61):
  s.frame_set(f)
  for side,sign in [('L',1),('R',-1)]:
   o=bpy.data.objects['POLISH_HindPole_'+side];o.location=c.matrix_world@(hips[f][side]+Vector((.13,sign*.12,-.035)));o.keyframe_insert('location',frame=f)
 s.frame_set(0)
 # Right elbow receives an explicit outward bend plane, away from the ribs.
 con=p['C_tripo::0_Left_Limb_1'].constraints['LegIK'];o=bpy.data.objects.new('DANGLE_FrontRightPole',None);s.collection.objects.link(o);con.pole_target=o;con.pole_subtarget='';o.location=Vector((.12,-.24,.30));best=None
 for deg in range(-180,181,5):
  con.pole_angle=math.radians(deg);bpy.context.view_layer.update();el=p['C_tripo::0_Left_Limb_1'].head;score=(el-Vector((.18,-.16,.34))).length
  if best is None or score<best[0]:best=(score,con.pole_angle)
 con.pole_angle=best[1]
 print(render_dragon('candidate-v3',(0,15,30,45),('side','front','three_quarter')))
 s.frame_set(0);bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'working-v3.blend'),compress=True)
 print('DANGLE_READY',math.degrees(best[1]))

author()
