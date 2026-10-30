"""Render the 'rise from lying' Seedance start picture: the collapse clip's end pose, same cameras as the ground picture.

Wrapper, no change to the renderer: sets the collapse Action's last frame on the armature (scene frame_set), prints
the lowest vertex height of the evaluated mesh (contact check), then runs Local/video2rig/dragon-air/render_start_air.py
unchanged (runpy) with the remaining arguments.

    blender --background --factory-startup Dragon_Collapse_sd_v2r_v4.blend --python render_start_lying.py -- \
        [--frame N] --out DIR --cameras-from CAMERAS.json --floor-z 0 [renderer args...]

--frame defaults to the collapse Action's last frame. All other arguments go to render_start_air.py.
"""
import os
import runpy
import sys

import bpy

RENDERER = '/Users/midir/dragon-boss-fight/Local/video2rig/dragon-air/render_start_air.py'

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
frame = None
if '--frame' in argv:
    i = argv.index('--frame')
    frame = int(argv[i + 1])
    del argv[i:i + 2]

scene = bpy.context.scene
arm = next(o for o in scene.objects if o.type == 'ARMATURE')
act = arm.animation_data.action if arm.animation_data else None
if act is None:
    sys.exit('render_start_lying: the armature has no active Action')
if frame is None:
    frame = int(round(act.frame_range[1]))
scene.frame_set(frame)
bpy.context.view_layer.update()
print(f'LYING action={act.name} range={tuple(act.frame_range)} frame={scene.frame_current}', flush=True)

deps = bpy.context.evaluated_depsgraph_get()
rows = []
for o in scene.objects:
    if o.type != 'MESH' or not o.visible_get():
        continue
    ev = o.evaluated_get(deps)
    for v in ev.data.vertices:
        w = ev.matrix_world @ v.co
        rows.append((w.z, w.x, w.y))
rows.sort()
lo = rows[0]
print(f'LYING lowest_vertex_z={lo[0]:.5f} at x={lo[1]:.4f} y={lo[2]:.4f}; nverts={len(rows)}', flush=True)
below = sum(1 for r in rows if r[0] < -1e-4)
near = sum(1 for r in rows if r[0] < 0.01)
print(f'LYING verts_below_floor(<-0.0001)={below} verts_within_1cm={near} highest_z={rows[-1][0]:.4f}', flush=True)
xs = [r[1] for r in rows]; ys = [r[2] for r in rows]
print(f'LYING bbox x[{min(xs):.3f},{max(xs):.3f}] y[{min(ys):.3f},{max(ys):.3f}] z[{rows[0][0]:.3f},{rows[-1][0]:.3f}]', flush=True)
# chin/head: lowest verts in the forward (+X facing) 15% of the body length
x0, x1 = min(xs), max(xs)
front = [r for r in rows if r[1] > x1 - 0.15 * (x1 - x0)]
print(f'LYING front15% (head/chin) lowest_z={min(r[0] for r in front):.5f} n={len(front)}', flush=True)

sys.argv = [sys.argv[0], '--'] + argv
runpy.run_path(RENDERER, run_name='__main__')
