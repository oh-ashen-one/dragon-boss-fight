"""Inspect the actual approved cup following the candidate socket, from two close views."""
import bpy,math,json,argparse,sys
from pathlib import Path
from mathutils import Matrix,Vector
parser=argparse.ArgumentParser();parser.add_argument('--version',default='v5geometry');args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []);assert args.version.isalnum()
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'Local/AttackSources20261103/HealGeometry';SOURCE=BASE/('Quaternius_Heal_'+args.version+'.blend');OUT=BASE/('review-'+args.version);OUT.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(SOURCE),load_ui=False);s=bpy.context.scene;r=bpy.data.objects['Knight_Comparison'];old_cup=bpy.data.objects.get('PREVIEW_ApprovedDrinkingCup');bpy.data.objects.remove(old_cup,do_unlink=True) if old_cup else None;before=set(s.objects);bpy.ops.import_scene.gltf(filepath=str(ROOT/'Local/CustomuseAssets/Polish20261025/props/DrinkingCup.glb'));cup=next(o for o in set(s.objects)-before if o.type=='MESH');cup.name='PREVIEW_ApprovedDrinkingCup';import_basis=cup.matrix_world.copy();attach=bpy.data.objects.new('PREVIEW_CupSocketAttach',None);s.collection.objects.link(attach);con=attach.constraints.new('COPY_TRANSFORMS');con.target=r;con.subtarget='CupSocket';cup.parent=attach;cup.matrix_parent_inverse=Matrix.Identity(4);cup.matrix_basis=Matrix.Rotation(-math.pi/2,4,'X')@import_basis
cam=bpy.data.objects.new('HealReviewCamera',bpy.data.cameras.new('HealReviewCamera'));s.collection.objects.link(cam);s.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=.52
s.render.engine='BLENDER_WORKBENCH';sh=s.display.shading;sh.light='STUDIO';sh.color_type='TEXTURE';sh.show_shadows=True;sh.show_cavity=True;sh.background_type='WORLD'
if not s.world:s.world=bpy.data.worlds.new('ReviewWorld')
s.world.color=(.065,.07,.08);s.view_settings.view_transform='Standard';s.view_settings.exposure=.8;s.render.resolution_x=960;s.render.resolution_y=720;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG'
for view,offset in [('front-left',(.8,-1.1,.10)),('side',(.9,-.25,.06))]:
 for f in [72,120,168,216]:
  s.frame_set(f);bpy.context.view_layer.update();head=(r.matrix_world@r.pose.bones['Head'].matrix).translation;focus=head+Vector((0,-.04,-.04));cam.location=focus+Vector(offset);cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();s.render.filepath=str(OUT/(view+f'-{f:03d}.png'));bpy.ops.render.render(write_still=True)
s.frame_set(144);bpy.ops.wm.save_as_mainfile(filepath=str(BASE/('Quaternius_Heal_'+args.version+'_preview.blend')),compress=True);print('HEAL_GEOMETRY_PREVIEWS_RENDERED',flush=True)
