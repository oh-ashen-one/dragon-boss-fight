import bpy, json
src = open('/Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_v1/audit_loco.py').read().split('frames = list(range(F0, F1+1))')[0]
g = {}; exec(src, g)
s = bpy.context.scene; out = []
for f in range(0, LAST+1, 2):
    s.frame_set(f); o = g['overlaps'](g['eval_verts']())
    if o['wingR/legs'] or o['wingL/legs']: out.append((f, o['wingR/legs'], o['wingL/legs']))
print('RES', json.dumps(out))
