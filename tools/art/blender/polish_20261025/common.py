import bpy,json,math,hashlib
from pathlib import Path
from mathutils import Vector,Matrix,Quaternion
ROOT=Path(__file__).resolve().parents[4];OUT=ROOT/'Local/Blender/polish-20261025';SRC=Path('/Users/midir/veyr-review-fable-20261021/Local/Blender');OWNER='codex-veyr-polish-20261025'
def open_scene(path):
 assert bpy.context.scene.get('session_owner')==OWNER
 bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False)
 bpy.context.scene['session_owner']=OWNER;bpy.context.scene['mcp_port']=9891
 bpy.context.scene.frame_set(0)
def curves(act):
 if not act:return []
 return [f for l in act.layers for st in l.strips for cb in st.channelbags for f in cb.fcurves]
def key_matrix(pb,m,frame):
 pb.matrix=m;bpy.context.view_layer.update()
 for k in ('location','rotation_quaternion','scale'):pb.keyframe_insert(k,frame=frame)
def render_dragon(out,frames=(0,),views=('side','front','three_quarter')):
 g={'__file__':str(ROOT/'tools/art/blender/dragon_flight_r2/drender_r2.py')}
 exec(compile((ROOT/'tools/art/blender/dragon_flight_r2/drender_r2.py').read_text(),g['__file__'],'exec'),g)
 g['TARGET']=Vector((0,0,.30))
 for v,(off,scale) in g['VIEWS'].items():g['VIEWS'][v]=(off,max(scale,1.4) if scale>0 else scale)
 g['setup'](show=('DRAGON_MESH','DRAGON_DEFORM'))
 # Keep control rig evaluating even though not rendered.
 bpy.data.objects['DRAGON_CTRL'].hide_set(False)
 return g['render'](frames,OUT/out,res=(640,480),views=views)
def dragon_probe():
 open_scene(SRC/'dragon-v1-20261021/flight_r2/Dragon_FlyHover_Blender_v1r2.blend')
 print(json.dumps({'hover':{n:list(bpy.data.objects['DRAGON_CTRL'].pose.bones[n].head) for n in ['C_tripo::1_Right_Limb_0','C_tripo::1_Right_Limb_1','IK_HL','IKT_HL']}}))
 print(render_dragon('dragon-baseline'))
 open_scene(SRC/'dragon-v1-20261021/Dragon_Idle_Blender_v1r3.blend')
 c=bpy.data.objects['DRAGON_CTRL'];print(json.dumps({'idle':{b.name:{'head':list(b.head),'tail':list(b.tail),'matrix':[list(r) for r in b.matrix]} for b in c.pose.bones if 'Right_Limb'in b.name or b.name.startswith(('IK_H','IKT_H'))}}))
