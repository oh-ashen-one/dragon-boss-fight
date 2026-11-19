"""Render the dragon at chosen clip times from fixed front / side / three-quarter (+ close-up) cameras (2026-11-18).

Blender, background. Imports one clip GLB (body, rig, its action and morph animation), optionally loads a
saved .blend instead, optionally replaces the skin weights from an NPZ (joints/weights in GLB vertex
order), and renders each time from cameras placed from the armature only, so before/after renders of
the same clip share camera, light and framing exactly. Workbench, studio light, the body's own texture.

blender --background --factory-startup --python render_skin_views.py -- \
    --glb CLIP.glb [--weights fixed.npz] --times 0.95 0.73 --focus wings|paw0|paw1|body --out DIR --tag before
"""
import argparse, math, sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector

ap = argparse.ArgumentParser()
ap.add_argument('--glb')
ap.add_argument('--weights')
ap.add_argument('--times', type=float, nargs='+')
ap.add_argument('--focus', default='body')
ap.add_argument('--out', type=Path, required=True)
ap.add_argument('--tag')
ap.add_argument('--size', type=int, default=720)
ap.add_argument('--jobs', type=Path, help='JSON list of {glb, weights, times, focus, tag}: many renders in one Blender process')
A = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
A.out.mkdir(parents=True, exist_ok=True)
import json, types
JOBS = json.loads(A.jobs.read_text()) if A.jobs else [dict(glb=A.glb, weights=A.weights, times=A.times, focus=A.focus, tag=A.tag)]

def run(a):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    scene = bpy.context.scene
    scene.render.fps = 60
    bpy.ops.import_scene.gltf(filepath=a.glb)
    mesh = next(o for o in bpy.data.objects if o.type == 'MESH' and o.parent and o.parent.type == 'ARMATURE')
    arm = mesh.parent
    for o in list(bpy.data.objects):
        if o not in (mesh, arm) and o.type == 'MESH':
            bpy.data.objects.remove(o, do_unlink=True)


    def apply_weights(obj, path):
        d = np.load(path); J = d['joints'].astype(int); W = d['weights'].astype(float)
        names = [g.name for g in obj.vertex_groups]
        order = d['names'].tolist() if 'names' in d else names
        groups = {n: obj.vertex_groups[n] for n in order}
        allidx = list(range(len(obj.data.vertices)))
        for g in obj.vertex_groups:
            g.remove(allidx)
        for k in range(J.shape[1]):
            for j in np.unique(J[:, k]):
                sel = np.flatnonzero((J[:, k] == j) & (W[:, k] > 0))
                g = groups[order[j]]
                for w in np.unique(np.round(W[sel, k], 6)):
                    idx = sel[np.round(W[sel, k], 6) == w].tolist()
                    g.add(idx, float(w), 'ADD')


    if a.weights:
        apply_weights(mesh, a.weights)

    # Light, look
    scene.render.engine = 'BLENDER_WORKBENCH'
    sh = scene.display.shading
    sh.light = 'STUDIO'; sh.color_type = 'TEXTURE'; sh.show_cavity = True; sh.cavity_type = 'BOTH'
    sh.show_object_outline = False; sh.show_specular_highlight = True
    scene.display.render_aa = '8'
    scene.render.resolution_x = scene.render.resolution_y = a.size
    scene.render.film_transparent = False
    world = bpy.data.worlds.new('W') if not scene.world else scene.world
    scene.world = world
    sh.background_type = 'VIEWPORT'; sh.background_color = (0.62, 0.66, 0.72)

    cam_data = bpy.data.cameras.new('Cam'); cam = bpy.data.objects.new('Cam', cam_data)
    scene.collection.objects.link(cam); scene.camera = cam
    cam_data.lens = 50

    FOCUS = {'wings': ['VeyrWingNegZRoot', 'VeyrWingPosZRoot', 'bone_2', 'bone_6', 'bone_11'],
             'paw0': ['bone_9', 'tripo::1_Left_Limb_1'], 'paw1': ['bone_14', 'tripo::0_Left_Limb_2', 'tripo::0_Left_Limb_3']}


    def heads():
        return {p.name: arm.matrix_world @ p.head for p in arm.pose.bones}


    def look(loc, target):
        cam.location = loc
        cam.rotation_euler = (target - loc).to_track_quat('-Z', 'Y').to_euler()


    action = arm.animation_data.action if arm.animation_data else None
    for t in a.times:
        f = t * scene.render.fps
        scene.frame_set(int(math.floor(f)), subframe=f - math.floor(f))
        bpy.context.view_layer.update()
        H = heads()
        pts = [v for n, v in H.items() if not n.startswith('tripo::Head') and not n.startswith('bone_3')]
        lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)])
        centre = (lo + hi) / 2; span = max((hi - lo).length, 0.5)
        if a.focus in FOCUS:
            sel = [H[n] for n in FOCUS[a.focus]]
            centre = sum(sel, Vector()) / len(sel)
            span = 0.34 if a.focus == 'wings' else 0.16
        dist = span * 1.9
        # Blender import: glTF +X (dragon forward) stays +X, glTF +Z (dragon's +Z side) becomes -Y, up is +Z.
        views = {'front': Vector((1, 0, 0.18)), 'side': Vector((0, -1, 0.12)), 'threequarter': Vector((0.75, -0.75, 0.45))}
        if a.focus == 'paw0':
            views = {'front': Vector((1, 0, 0.25)), 'side': Vector((0, 1, 0.15)), 'threequarter': Vector((0.7, 0.7, 0.45))}
        if a.focus == 'wings':
            views['top'] = Vector((0.25, 0, 1))
        for name, d in views.items():
            look(centre + d.normalized() * dist, centre)
            scene.render.filepath = str(a.out / f'{a.tag}_{a.focus}_t{t:05.2f}_{name}.png')
            bpy.ops.render.render(write_still=True)
            print('RENDERED', scene.render.filepath)


for job in JOBS:
    run(types.SimpleNamespace(out=A.out, size=A.size, weights=None, focus='body', **job))
print('DONE')
