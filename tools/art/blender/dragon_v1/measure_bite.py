import bpy, json, math
import numpy as np
src = open('/Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_v1/audit_loco.py').read().split('frames = list(range(F0, F1+1))')[0]
g = {}; exec(src, g)
s = bpy.context.scene; D = bpy.data.objects['DRAGON_DEFORM']
head = np.where(g['wsum'](['bone_5']) > 0.8)[0]
rest = g['rest']; tipi = head[np.argmax(rest[head, 0])]          # snout tip vertex (max X at rest)
xs, pitch, yaw = [], [], []
for f in range(0, 55):
    s.frame_set(f); V = g['eval_verts']()
    xs.append(V[tipi, 0])
    M = (D.matrix_world @ D.pose.bones['bone_5'].matrix).to_3x3()
    v0 = (D.data.bones['bone_5'].matrix_local.to_3x3().inverted() @ __import__('mathutils').Vector((1, 0, 0)))   # rest snout axis (world +X) in bone space
    d = M @ v0; d.normalize()
    pitch.append(math.degrees(math.asin(max(-1, min(1, d.z))))); yaw.append(math.degrees(math.atan2(d.y, d.x)))
xs = np.array(xs); PX = 1280/1.3
print('RES', json.dumps({'snout_drawback_px': round(float((xs[0]-xs[:14].min())*PX), 1), 'snout_strike_past_idle_px': round(float((xs[14:24].max()-xs[0])*PX), 1),
      'snout_pitch_at_strike_deg': round(pitch[18], 1), 'shake_yaw_range_deg': round(max(yaw[20:32]) - min(yaw[20:32]), 1)}))
