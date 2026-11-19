"""Render matched before/after turntable clips of a dragon clip in Blender (2026-11-19).

Background Blender, one process, run through gpu_slot. Each job imports one clip GLB, optionally replaces
the skin weights from an NPZ (GLB vertex order), plays the clip slowed by --slow while the camera orbits
the focus point, and writes PNG frames. The camera depends only on the armature (bone heads), so the
before and after jobs of the same clip get identical cameras, light and timing.

blender -b --factory-startup --python render_skin_turntable.py -- --jobs jobs.json --out DIR
jobs.json: [{"glb": ..., "weights": null|npz, "tag": "before_takeoff", "focus": "wings"|"body"|"paw0"|"paw1",
             "t0": 0, "t1": 1.5, "frames": 90, "orbit": 360, "elev": 0.25, "dist": 1.0, "az0": 0}]
"""
import argparse, json, math, sys, types
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector

ap = argparse.ArgumentParser()
ap.add_argument('--jobs', type=Path, required=True); ap.add_argument('--out', type=Path, required=True)
ap.add_argument('--size', type=int, default=640)
A = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
FOCUS = {'wings': ['VeyrWingNegZRoot', 'VeyrWingPosZRoot', 'bone_2', 'bone_6', 'bone_11'],
         'paw0': ['bone_9', 'tripo::1_Left_Limb_1'], 'paw1': ['bone_14', 'tripo::0_Left_Limb_2', 'tripo::0_Left_Limb_3']}
SPAN = {'wings': 0.75, 'paw0': 0.32, 'paw1': 0.32}


def apply_weights(obj, path):
    d = np.load(path); J = d['joints'].astype(int); W = d['weights'].astype(float); names = [str(x) for x in d['names']]
    assert [g.name for g in obj.vertex_groups] == names
    idx = list(range(len(obj.data.vertices)))
    for g in obj.vertex_groups:
        g.remove(idx)
    for k in range(J.shape[1]):
        for j in np.unique(J[:, k]):
            sel = np.flatnonzero((J[:, k] == j) & (W[:, k] > 0))
            vals = np.round(W[sel, k], 6)
            for w in np.unique(vals):
                obj.vertex_groups[names[j]].add(sel[vals == w].tolist(), float(w), 'REPLACE')


def run(job):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    scene = bpy.context.scene; scene.render.fps = 60
    bpy.ops.import_scene.gltf(filepath=job.glb)
    mesh = next(o for o in bpy.data.objects if o.type == 'MESH' and o.parent and o.parent.type == 'ARMATURE')
    arm = mesh.parent
    for o in list(bpy.data.objects):
        if o.type == 'MESH' and o is not mesh:
            bpy.data.objects.remove(o, do_unlink=True)
    if job.weights:
        apply_weights(mesh, job.weights)
    scene.render.engine = 'BLENDER_WORKBENCH'
    sh = scene.display.shading
    sh.light = 'STUDIO'; sh.color_type = 'TEXTURE'; sh.show_cavity = True; sh.cavity_type = 'BOTH'
    sh.background_type = 'VIEWPORT'; sh.background_color = (0.62, 0.66, 0.72)
    scene.display.render_aa = '8'
    scene.render.resolution_x = scene.render.resolution_y = A.size
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam')); scene.collection.objects.link(cam); scene.camera = cam
    cam.data.lens = 50
    out = A.out / job.tag; out.mkdir(parents=True, exist_ok=True)
    fixed = None
    if not job.track and job.focus in FOCUS:  # one camera target for the whole clip: the mean focus point
        acc = Vector()
        for i in range(job.frames):
            t = job.t0 + (job.t1 - job.t0) * i / max(job.frames - 1, 1); f = t * scene.render.fps
            scene.frame_set(int(math.floor(f)), subframe=f - math.floor(f))
            acc += sum((arm.matrix_world @ arm.pose.bones[n].head for n in FOCUS[job.focus]), Vector()) / len(FOCUS[job.focus])
        fixed = acc / job.frames
    for i in range(job.frames):
        u = i / max(job.frames - 1, 1)
        t = job.t0 + (job.t1 - job.t0) * u
        f = t * scene.render.fps
        scene.frame_set(int(math.floor(f)), subframe=f - math.floor(f))
        H = {p.name: arm.matrix_world @ p.head for p in arm.pose.bones}
        if job.focus in FOCUS:
            c = fixed if fixed is not None else sum((H[n] for n in FOCUS[job.focus]), Vector()) / len(FOCUS[job.focus]); span = SPAN[job.focus]
        else:
            pts = [v for n, v in H.items() if not n.startswith('tripo::Head')]
            c = sum(pts, Vector()) / len(pts); span = 1.2
        az = math.radians(job.az0 + job.orbit * u)
        d = Vector((math.cos(az), math.sin(az), job.elev)).normalized() * span * 1.9 * job.dist
        cam.location = c + d
        cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = str(out / f'{i:04d}.png')
        bpy.ops.render.render(write_still=True)
    print('RENDERED', job.tag, job.frames, flush=True)


for j in json.loads(A.jobs.read_text()):
    base = dict(track=True, weights=None, focus='body', t0=0.0, t1=1.0, frames=60, orbit=360, elev=0.25, dist=1.0, az0=0)
    base.update(j)
    run(types.SimpleNamespace(**base))
print('DONE')
