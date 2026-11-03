"""Measure the actual Blender-to-export socket basis before refitting the approved cup."""
import bpy,json,sys
from pathlib import Path
from mathutils import Matrix,Vector
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'tools/unreal'))
from normalize_customuse_glb import GLB
source=ROOT/'Local/AttackSources20261102/QuaterniusRetarget/Exports/Quaternius_Consume_v1'
bpy.ops.wm.open_mainfile(filepath=str(source.with_suffix('.blend')),load_ui=False);rig=bpy.data.objects['Knight_Comparison'];scene=bpy.context.scene;g=GLB(source.with_suffix('.glb'));names={n.get('name'):i for i,n in enumerate(g.json['nodes'])};B=Matrix.Rotation(1.5707963267948966,4,'X');rows=[]
for t in [0.,.4,.8,1.2]:
 f=t*scene.render.fps/scene.render.fps_base;scene.frame_set(int(f),subframe=f-int(f));bpy.context.view_layer.update();world=g.world_matrices(0,t);bone=rig.matrix_world@rig.pose.bones['CupSocket'].matrix;native=Matrix(world[names['CupSocket']].tolist());A=bone.inverted()@B@native
 rows.append({'seconds':t,'staticMeshLocalToBoneLocal':[[float(v) for v in row] for row in A],'rimBoneLocal':list(A@Vector((.060,-.023,-.091)))})
report={'source':str(source.relative_to(ROOT)),'samples':rows,'oldFitterRimLocal':[.060,-.023,-.091],'scope':'Basis derived from matching exported joint matrices and Blender poses; no visual quality acceptance'}
(ROOT/'docs/master-goal-20261103/heal-socket-basis.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
