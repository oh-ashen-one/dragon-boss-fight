"""Review renders for the dragon in the session-owned Blender (Workbench, ortho, 3 views)."""
import bpy, math
from pathlib import Path
from mathutils import Vector
W = Path("/Users/midir/veyr-review-fable-20261021/Local/Blender/dragon-v1-20261021") / "flight_r2"
VIEWS = {  # camera location relative to target, ortho scale
    'front': (Vector((1.6, 0.0, 0.18)), globals().get('FRONT_SCALE', 0.95)),
    'side':  (Vector((0.0, 1.6, 0.22)), globals().get('SIDE_SCALE', 1.2)),
    'three_quarter': (Vector((1.2, 1.0, 0.5)), globals().get('TQ_SCALE', 1.0)),
    'low_three_quarter': (Vector((1.30, 1.00, -0.12)), 0.0),   # perspective 45 mm, eye ~0.08 (≈1.7 m game)
}
TARGET = Vector((0.0, 0.0, globals().get('TARGET_Z', 0.22)))

def setup(show=()):
    s = bpy.context.scene
    for o in s.objects:
        if o.type in ('MESH','ARMATURE') and not o.name.startswith('REVIEW_'):
            vis = o.name in show
            o.hide_render = not vis
            o.hide_set(not vis)
    if 'REVIEW_Ground' not in bpy.data.objects:
        me = bpy.data.meshes.new('REVIEW_Ground'); 
        me.from_pydata([(-3,-3,0),(3,-3,0),(3,3,0),(-3,3,0)],[],[(0,1,2,3)])
        g = bpy.data.objects.new('REVIEW_Ground', me); s.collection.objects.link(g)
        mat = bpy.data.materials.new('REVIEW_GroundMat'); mat.diffuse_color = (.28,.27,.25,1); me.materials.append(mat)
    for name in VIEWS:
        cn = 'REVIEW_Cam_'+name
        if cn not in bpy.data.objects:
            cam = bpy.data.objects.new(cn, bpy.data.cameras.new(cn)); s.collection.objects.link(cam)
        cam = bpy.data.objects[cn]; off, scale = VIEWS[name]
        cam.location = TARGET+off
        cam.rotation_euler = (TARGET-cam.location).to_track_quat('-Z','Y').to_euler()
        if scale > 0: cam.data.type = 'ORTHO'; cam.data.ortho_scale = scale
        else: cam.data.type = 'PERSP'; cam.data.lens = 45
        cam.data.clip_start = 0.01; cam.data.clip_end = 20
    s.render.engine = 'BLENDER_WORKBENCH'
    sh = s.display.shading
    sh.light = 'STUDIO'; sh.color_type = 'TEXTURE'; sh.show_shadows = True; sh.show_cavity = True
    sh.cavity_type = 'BOTH'; sh.background_type = 'WORLD'
    if s.world is None: s.world = bpy.data.worlds.new('World')
    s.world.color = (.06,.06,.065)
    s.display.shadow_shift = .1
    s.render.film_transparent = False
    s.view_settings.view_transform = 'Standard'; s.view_settings.exposure = 1.4; s.view_settings.look = 'None'
    s.render.image_settings.file_format = 'PNG'

def render(frames, outdir, res=(560,420), views=tuple(VIEWS), prefix=''):
    s = bpy.context.scene
    s.render.resolution_x, s.render.resolution_y = res; s.render.resolution_percentage = 100
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    written = []
    for v in views:
        s.camera = bpy.data.objects['REVIEW_Cam_'+v]
        for f in frames:
            s.frame_set(int(f))
            p = outdir/f'{prefix}{v}_{int(f):04d}.png'
            s.render.filepath = str(p)
            bpy.ops.render.render(write_still=True)
            written.append(str(p))
    return written
