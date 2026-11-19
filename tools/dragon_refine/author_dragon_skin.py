"""Build the editable dragon skin .blend with corrected weights, and read weights back out of a .blend (2026-11-18).

Blender, background, data only (no render):

  build:  blender -b --factory-startup --python author_dragon_skin.py -- build \
              --rig Dragon_Takeoff_DangleJoin_v2.glb --weights fixed.npz --actions A.glb B.glb ... --output OUT.blend
          Imports the canonical body + rig (GLB vertex order is kept by the importer), replaces every vertex
          group from the NPZ (joints/weights/names, GLB order), copies the listed clips' bone actions onto the
          same armature (kept with fake users, Take-off active) and saves OUT.blend. The script text is stored
          in the .blend. Nothing about bones, geometry, UVs or morphs changes.
  read:   blender -b OUT.blend --python author_dragon_skin.py -- read --output weights.npz
          Writes the mesh's vertex groups (top four per vertex, normalised, GLB joint order) to NPZ, so the
          shipped GLBs are patched from what the .blend holds.
"""
import argparse, sys
from pathlib import Path
import bpy
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument('mode', choices=('build', 'read'))
ap.add_argument('--rig'); ap.add_argument('--weights'); ap.add_argument('--actions', nargs='*', default=[])
ap.add_argument('--output', required=True)
a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])


def body():
    return next(o for o in bpy.data.objects if o.type == 'MESH' and o.parent and o.parent.type == 'ARMATURE')


def import_glb(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    return [o for o in bpy.data.objects if o not in before]


if a.mode == 'build':
    if Path(a.output).exists():
        raise RuntimeError('Refusing to overwrite ' + a.output)
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    scene = bpy.context.scene
    scene.render.fps = 60
    new = import_glb(a.rig)
    mesh = body(); arm = mesh.parent
    for o in new:
        if o.type == 'MESH' and o is not mesh:
            bpy.data.objects.remove(o, do_unlink=True)
    mesh.name = 'DragonBody'; arm.name = 'DragonRig'
    d = np.load(a.weights)
    J = d['joints'].astype(int); W = d['weights'].astype(float); names = [str(x) for x in d['names']]
    assert len(J) == len(mesh.data.vertices), (len(J), len(mesh.data.vertices))
    assert [g.name for g in mesh.vertex_groups] == names, 'vertex group order differs from the GLB joints'
    idx = list(range(len(mesh.data.vertices)))
    for g in mesh.vertex_groups:
        g.remove(idx)
    for k in range(J.shape[1]):
        for j in np.unique(J[:, k]):
            sel = np.flatnonzero((J[:, k] == j) & (W[:, k] > 0))
            if not len(sel):
                continue
            vals = np.round(W[sel, k], 6)
            for w in np.unique(vals):
                mesh.vertex_groups[names[j]].add(sel[vals == w].tolist(), float(w), 'REPLACE')
    main = arm.animation_data.action
    main.use_fake_user = True
    for path in a.actions:
        objs = import_glb(path)
        for o in objs:
            if o.type == 'ARMATURE' and o.animation_data and o.animation_data.action:
                act = o.animation_data.action; act.use_fake_user = True; act.name = Path(path).stem
            if o.type == 'MESH' and o.data.shape_keys and o.data.shape_keys.animation_data and o.data.shape_keys.animation_data.action:
                sk = o.data.shape_keys.animation_data.action; sk.use_fake_user = True; sk.name = Path(path).stem + '_morphs'
        for o in objs:
            bpy.data.objects.remove(o, do_unlink=True)
    arm.animation_data.action = main
    for block in (bpy.data.meshes, bpy.data.armatures):
        for x in list(block):
            if x.users == 0:
                block.remove(x)
    text = bpy.data.texts.new('author_dragon_skin.py'); text.write(Path(__file__).read_text())
    mesh['skin_fix'] = 'Wing-root rings and left front paw reweighted 2026-11-18; skeleton, geometry, UVs, morphs unchanged.'
    bpy.ops.wm.save_as_mainfile(filepath=a.output, compress=True)
    print('SAVED', a.output, 'actions', sorted(x.name for x in bpy.data.actions))
else:
    mesh = body()
    names = [g.name for g in mesh.vertex_groups]
    n = len(mesh.data.vertices)
    J = np.zeros((n, 4), np.uint16); W = np.zeros((n, 4), np.float32)
    for v in mesh.data.vertices:
        gs = sorted(((g.weight, g.group) for g in v.groups if g.weight > 0), reverse=True)[:4]
        s = sum(w for w, _ in gs) or 1.0
        for k, (w, gi) in enumerate(gs):
            J[v.index, k] = gi; W[v.index, k] = w / s
    np.savez(a.output, joints=J, weights=W, names=np.array(names))
    print('READ', a.output, n)
