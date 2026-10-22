"""HeavyAttackOneHand v4 free-arm rebuild (owner 2026-10-21: "his left hand is in his body
lol its not real at all"). Execute ONLY inside the owned Blender MCP session via run.py,
after revise.py open_job('heavy'); then revise.py rebake('heavy'). Never saves.

Cause in v3: the free-hand target offsets were authored in WORLD axes while the approved
strike twists the chest ~90 degrees, so the "outside/behind the shoulder" offset swung in
front of and into the torso. v4 authors the free hand, its elbow pole and the clavicle in
the CHEST frame (Spine2 rotation relative to idle), so the arm hangs off the moving
shoulder girdle. The approved right-hand sword path, body/leg controls and 1.4 s timing are
untouched; only LeftShoulder FK, LeftArm_Target and LeftArm_Pole are rewritten.

Beats: wind-up - arm reaches out/forward on the open side, clavicle protracts and lifts,
counterbalancing the backswung blade; strike - elbow drives back, clavicle retracts, hand
pulls behind the left hip opposite the sweeping sword (opening the chest); recovery - hand
settles toward a low front guard and returns exactly to idle at 1.4 s.
"""
from pathlib import Path
import bpy, importlib.util, math, json
from mathutils import Vector, Matrix, Quaternion
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
_cs = importlib.util.spec_from_file_location('veyr_v4_common', HERE / 'common.py'); cm = importlib.util.module_from_spec(_cs); _cs.loader.exec_module(cm)
P = cm.params(globals().get('VEYR_V4_PARAMS'))
_fs = importlib.util.spec_from_file_location('feedback2', cm.REPO / 'tools/art/blender/feedback/feedback_actions.py'); f = importlib.util.module_from_spec(_fs); _fs.loader.exec_module(f)
c = f.c; c.OUT = P['out']; c.OWNER = P['owner']
DUR = 1.4
KEY_STEP = 0.02

# Offsets in the idle chest frame (x = left/out, y = back, z = up), metres of rig units.
TUNE = dict(
    # r2 (critic): wind-up reaches toward the target just above the belt with the elbow open
    # ~145 deg (hand_world, shoulder-relative WORLD offsets, converted into the chest frame);
    # impact leads with the elbow (pole keys earlier than the hand) and the shoulder pulls back;
    # recovery swings forward past the hang (overshoot) before settling.
    hand=[(0, None), (.12, (.10, -.09, -.21)), (.20, 'W1'), (.45, 'W2'), (.56, (.20, .02, -.12)),
          (.66, (.17, .07, -.14)), (.76, (.13, .125, -.16)), (.9, (.13, .115, -.165)),
          (.98, (.135, -.035, -.2)), (1.06, 'W4'), (1.18, 'W5'), (1.4, None)],
    hand_world={'W1': (.07, -.15, -.20), 'W2': (.06, -.155, -.195),
                # recovery pendulum in WORLD, relative to the idle hang: swings through, overshoots forward, settles
                'W3': ('rest', (.02, .09, .02)), 'W4': ('rest', (.065, -.035, .035)), 'W5': ('rest', (.022, .008, .012))}, reach_frac=.953,
    pole=[(0, None), (.20, (.28, .02, -.24)), (.45, (.28, .02, -.24)), (.54, (.24, .30, -.08)),
          (.66, (.22, .33, -.05)), (.9, (.22, .30, -.07)), (1.08, (.25, .20, -.15)), (1.25, None), (1.4, None)],
    # clavicle: (protract(-)/retract(+) about chest up, elevate(-)/depress(+) about chest forward) degrees
    clav=[(0, (0, 0)), (.12, (-5, -3)), (.25, (-12, -6)), (.42, (-12, -6)), (.56, (4, -2)),
          (.68, (18, 4)), (.82, (16, 3)), (.95, (6, 1)), (1.1, (-3, 0)), (1.25, (-2, 0)), (1.4, (0, 0))],
    # left fingers: 0 = source pose, 1 = idle fist; half-closed into the impact
    fist=[(0, 0), (.5, 0), (.66, .6), (.9, .6), (1.1, .25), (1.4, 0)],
)


def pchip(points, t):
    xs = [p[0] for p in points]; ys = [p[1] for p in points]
    if t <= xs[0]: return ys[0]
    if t >= xs[-1]: return ys[-1]
    n = len(xs); h = [xs[i + 1] - xs[i] for i in range(n - 1)]; d = [(ys[i + 1] - ys[i]) / h[i] for i in range(n - 1)]
    m = [0.] * n
    for i in range(1, n - 1):
        if d[i - 1] * d[i] <= 0: m[i] = 0.
        else:
            w1 = 2 * h[i] + h[i - 1]; w2 = h[i] + 2 * h[i - 1]; m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    i = max(j for j in range(n - 1) if xs[j] <= t); s = (t - xs[i]) / h[i]; s2, s3 = s * s, s * s * s
    return (2 * s3 - 3 * s2 + 1) * ys[i] + (s3 - 2 * s2 + s) * h[i] * m[i] + (-2 * s3 + 3 * s2) * ys[i + 1] + (s3 - s2) * h[i] * m[i + 1]


def smooth01(x):
    x = min(1., max(0., x)); return x * x * (3 - 2 * x)


def vec_curve(points, rest, t):
    def ev(v):
        if v is None: return rest
        if isinstance(v, tuple) and v and v[0] == 'rest': return rest + Vector(v[1])
        return Vector(v)
    pts = [(tt, ev(v)) for tt, v in points]
    return Vector([pchip([(tt, v[k]) for tt, v in pts], t) for k in range(3)])


def chest_rot(fk, q0):
    return (fk.matrix_world @ fk.pose.bones['Spine2'].matrix).to_quaternion() @ q0.inverted()


def author():
    s = bpy.context.scene
    assert s.get('session_owner') == P['owner'] and s.get('rebuild_job') == 'heavy', 'open_job(heavy) first'
    f.configure('heavy'); fps = s.render.fps; fk = bpy.data.objects['Pose_Control_Rig']
    target = bpy.data.objects['LeftArm_Target']; pole = bpy.data.objects['LeftArm_Pole']
    n = round(DUR / KEY_STEP); times = [min(DUR, i * KEY_STEP) for i in range(n + 1)]
    sh = fk.pose.bones['LeftShoulder']
    snap = {}
    for t in times:
        c.at(t * fps); snap[t] = sh.matrix_basis.copy()
    act = fk.animation_data.action
    for fc in list(c.curves(act)):
        if fc.data_path.startswith('pose.bones["LeftShoulder"]'):
            fc.keyframe_points.clear()
    c.at(0)
    q0 = (fk.matrix_world @ fk.pose.bones['Spine2'].matrix).to_quaternion()
    shoulder0 = fk.matrix_world @ fk.pose.bones['LeftArm'].head
    hand0 = target.matrix_world.copy()
    rest_hand = hand0.translation - shoulder0
    rest_pole = f.rest_arm_pole(fk, 'Left') - shoulder0
    f.reset_animation(target); f.reset_animation(pole)
    prev = {}; T = dict(TUNE); reach = 0.
    Larm = (fk.pose.bones['LeftForeArm'].head - fk.pose.bones['LeftArm'].head).length + (fk.pose.bones['LeftHand'].head - fk.pose.bones['LeftForeArm'].head).length
    # world reach keys -> chest-frame offsets at their key time
    hw = {}
    for tt, v in T['hand']:
        if isinstance(v, str):
            c.at(tt * fps); sh.matrix_basis = snap[min(times, key=lambda x: abs(x - tt))]; bpy.context.view_layer.update()
            Rk = chest_rot(fk, q0); hv = T['hand_world'][v]
            w = rest_hand + Vector(hv[1]) if hv[0] == 'rest' else Vector(hv).normalized() * T['reach_frac'] * Larm
            hw[v] = tuple(Rk.inverted() @ w)
    T['hand'] = [(tt, hw[v] if isinstance(v, str) else v) for tt, v in T['hand']]
    fingers = [b for b in fk.pose.bones if b.name.startswith(('LeftHandThumb', 'LeftHandIndex', 'LeftHandMiddle', 'LeftHandRing', 'LeftHandPinky'))]
    fsnap = {}
    for t in times:
        c.at(t * fps); fsnap[t] = {b.name: b.matrix_basis.copy() for b in fingers}
    fist0 = fsnap[0]
    for fc in list(c.curves(act)):
        if any(fc.data_path.startswith(f'pose.bones["{b.name}"]') for b in fingers): fc.keyframe_points.clear()
    for t in times:
        fr = t * fps; c.at(fr); w = pchip(T['fist'], t)
        for b in fingers:
            a_ = fsnap[t][b.name]; z_ = fist0[b.name]
            b.matrix_basis = Matrix.LocRotScale(a_.to_translation().lerp(z_.to_translation(), w), a_.to_quaternion().slerp(z_.to_quaternion(), w), a_.to_scale())
            c.key(b, fr, prev)
    for t in times:
        fr = t * fps; c.at(fr)
        sh.matrix_basis = snap[t]; bpy.context.view_layer.update()
        R = chest_rot(fk, q0)
        pro, ele = [pchip([(tt, v[k]) for tt, v in T['clav']], t) for k in (0, 1)]
        for ang, ax in ((pro, Vector((0, 0, 1))), (ele, Vector((0, 1, 0)))):
            if abs(ang) > 1e-9:
                m = sh.matrix.copy(); axis = (R @ ax).normalized()
                sh.matrix = Matrix.Translation(m.translation) @ Matrix.Rotation(math.radians(ang), 4, axis) @ m.to_3x3().to_4x4()
                bpy.context.view_layer.update()
        c.key(sh, fr, prev)
        shoulder = fk.matrix_world @ fk.pose.bones['LeftArm'].head
        off = vec_curve(T['hand'], rest_hand, t); po = vec_curve(T['pole'], rest_pole, t)
        m = R.to_matrix().to_4x4() @ hand0.to_3x3().to_4x4(); m.translation = shoulder + R @ off
        target.matrix_basis = m; c.key(target, fr, prev)
        pole.location = shoulder + R @ po; pole.keyframe_insert('location', frame=fr)
        reach = max(reach, (R @ off).length / Larm)
    for o in (fk, target, pole): c.smooth(o)
    tx = bpy.data.texts.get('feedback_v4_heavy.py') or bpy.data.texts.new('feedback_v4_heavy.py'); tx.clear(); tx.write(Path(__file__).read_text()); tx.use_fake_user = True
    s['heavy_v4'] = json.dumps({'keyStep': KEY_STEP, 'frame': 'chest (Spine2) relative to idle', 'controls': ['LeftShoulder FK', 'LeftArm_Target', 'LeftArm_Pole']})
    c.at(0)
    return {'keys': n + 1, 'maxFreeArmReach': reach, 'armLength': Larm, 'reachKeysChest': {k: [round(x, 3) for x in v] for k, v in hw.items()}}


def _dominant(body):
    gid = {g.index: g.name for g in body.vertex_groups}
    out = []
    for v in body.data.vertices:
        best = max(v.groups, key=lambda gg: gg.weight, default=None)
        out.append(gid.get(best.group, '') if best else '')
    return out


LEFT_ARM = ('LeftHand', 'LeftForeArm', 'LeftArm', 'LeftShoulder')
TORSO_LEGS = ('Hips', 'Spine', 'LeftUpLeg', 'LeftLeg', 'LeftFoot', 'LeftToe', 'RightUpLeg', 'RightLeg', 'RightFoot', 'RightToe')


def intersections(step=2):
    """Evaluated BAKED mesh, classified by each vertex's dominant bone. Unsigned distances
    (armour shells are open, so inside tests are unreliable) plus count within 5 mm:
      glove: left hand/forearm verts vs every triangle not on the left arm chain;
      rightarm: right hand/forearm verts vs torso+legs triangles;
      blade: sword verts farther than .14 from the right palm vs torso+legs triangles.
    Supplements, never replaces, visual review."""
    s = bpy.context.scene; rig = bpy.data.objects['Knight_Deform']
    body = next(o for o in s.objects if o.type == 'MESH' and o.get('export_body') and not o.get('review_prop'))
    sword = [o for o in s.objects if o.type == 'MESH' and o.get('review_attachment')]
    dom = _dominant(body)
    glove = [i for i, d in enumerate(dom) if d.startswith(('LeftHand', 'LeftForeArm'))]
    rarm = [i for i, d in enumerate(dom) if d.startswith(('RightHand', 'RightForeArm'))]
    body.data.calc_loop_triangles(); tris = [tuple(t.vertices) for t in body.data.loop_triangles]
    t_noleft = [t for t in tris if not any(dom[i].startswith(LEFT_ARM) for i in t)]
    t_core = [t for t in tris if all(dom[i].startswith(TORSO_LEGS) for i in t)]
    res = {'glove_to_body': (1e3, 0), 'blade_to_torso_legs': (1e3, 0), 'right_forearm_to_torso_legs': (1e3, 0)}
    series = []; stretch_max = 0; rest = [v.co.copy() for v in body.data.vertices]
    def rest_len(a, b): return (rest[a] - rest[b]).length
    for fr in range(0, s.frame_end + 1, step):
        s.frame_set(fr); dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); mw = ev.matrix_world
        co = [mw @ v.co for v in me.vertices]
        def ok(t):  # drop skin-stretch artifact triangles (edge > 2.5x rest), reported separately
            return all((co[t[a]] - co[t[b]]).length <= 2.5 * rest_len(t[a], t[b]) + .004 for a, b in ((0, 1), (1, 2), (2, 0)))
        bad = sum(1 for t in tris if not ok(t)); stretch_max = max(stretch_max, bad)
        b1 = BVHTree.FromPolygons(co, [t for t in t_noleft if ok(t)], all_triangles=True); b2 = BVHTree.FromPolygons(co, [t for t in t_core if ok(t)], all_triangles=True)
        def dist(tree, p):
            hit = tree.find_nearest(p); return 1e3 if hit[0] is None else hit[3]
        gd = [dist(b1, co[i]) for i in glove[::2]]; rd = [dist(b2, co[i]) for i in rarm[::2]]
        palm = rig.matrix_world @ rig.pose.bones['RightHand'].head; bd = []
        for o in sword:
            oe = o.evaluated_get(dg); sm = oe.to_mesh(); smw = oe.matrix_world
            for v in list(sm.vertices)[::2]:
                p = smw @ v.co
                if (p - palm).length > .14: bd.append(dist(b2, p))
            oe.to_mesh_clear()
        ev.to_mesh_clear(); t = fr / s.render.fps
        vals = {'glove_to_body': gd, 'blade_to_torso_legs': bd or [1e3], 'right_forearm_to_torso_legs': rd}
        series.append([round(t, 3)] + [x for k in res for x in (round(min(vals[k]), 4), sum(1 for d in vals[k] if d < .005))])
        for k in res:
            if min(vals[k]) < res[k][0]: res[k] = (min(vals[k]), t)
    return {'min': res, 'maxStretchedArtifactTriangles': stretch_max, 'counts': {'glove': len(glove), 'rightForearm': len(rarm)}, 'columns': ['t'] + [x for k in res for x in (k, k + '_n<5mm')], 'series': series[::2]}


TORSO = ('Hips', 'Spine')


def _torso_depth(co, tree, axis_pt, p):
    """Radial depth of p under the OUTERMOST torso shell (ray from outside toward the spine axis)."""
    d = p - axis_pt; d.z = 0
    if d.length < 1e-6: return .3
    d.normalize(); origin = Vector((axis_pt.x, axis_pt.y, p.z)) + d * .6
    hit = tree.ray_cast(origin, -d, .6)
    if hit[0] is None: return -1.
    r_surface = .6 - hit[3]; r_p = (p - Vector((axis_pt.x, axis_pt.y, p.z))).length
    return r_surface - r_p  # > 0: inside the outer torso shell


def torso_depths(step=3, near=.26):
    """Per frame: deepest sword (grip/guard/pommel within `near` of the right wrist) and right
    forearm/hand vertex under the outer torso shell, plus push direction for the sword."""
    s = bpy.context.scene; rig = bpy.data.objects['Knight_Deform']
    body = next(o for o in s.objects if o.type == 'MESH' and o.get('export_body') and not o.get('review_prop'))
    sword = [o for o in s.objects if o.type == 'MESH' and o.get('review_attachment')]
    dom = _dominant(body); body.data.calc_loop_triangles()
    tt = [tuple(t.vertices) for t in body.data.loop_triangles if all(dom[i].startswith(TORSO) for i in t.vertices)]
    rarm = [i for i, d in enumerate(dom) if d.startswith(('RightHand', 'RightForeArm'))]
    out = []
    for fr in range(0, s.frame_end + 1, step):
        s.frame_set(fr); dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); mw = ev.matrix_world
        co = [mw @ v.co for v in me.vertices]; tree = BVHTree.FromPolygons(co, tt, all_triangles=True)
        ax = rig.matrix_world @ rig.pose.bones['Spine1'].head; wrist = rig.matrix_world @ rig.pose.bones['RightHand'].head
        sw = (-1., None)
        for o in sword:
            oe = o.evaluated_get(dg); sm = oe.to_mesh(); smw = oe.matrix_world
            for v in list(sm.vertices)[::3]:
                p = smw @ v.co
                if (p - wrist).length < near:
                    dd = _torso_depth(co, tree, ax, p)
                    if dd > sw[0]: sw = (dd, p)
            oe.to_mesh_clear()
        ra = max(_torso_depth(co, tree, ax, co[i]) for i in rarm[::4])
        ev.to_mesh_clear()
        out.append((round(fr / s.render.fps, 3), round(sw[0], 4), round(ra, 4), [round(x, 3) for x in (sw[1] - wrist)] if sw[1] is not None else None))
    return out


DIRS = [Vector(v).normalized() for v in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1), (1, 1, 1))]
HANDLE_Z = .55
TWIST_FIX = False  # forearm-roll preservation tried 2026-10-21: raised the export joint step 20.7 -> 30.5 deg, left off  # sword-local Z below which the mesh is handle/grip/pommel (pommel knob -.45..-.37)


def grip_clearance(step=5, near_hand=.075):
    """Round 2 check (critic: pommel exits the back f6-14 / right chest f20-26, grip buried f34).
    Per frame: clearance of the sword handle+pommel vertices from the body mesh, excluding the
    right hand/forearm that hold it and handle vertices within `near_hand` of the right palm.
    clearance = -depth under the outer torso shell when inside it, else nearest surface distance.
    Returned per 30 fps frame: (frame30, pommel clearance, grip clearance, worst body part)."""
    s = bpy.context.scene; rig = bpy.data.objects['Knight_Deform']
    body = next(o for o in s.objects if o.type == 'MESH' and o.get('export_body') and not o.get('review_prop'))
    sword = next(o for o in s.objects if o.type == 'MESH' and o.get('review_attachment'))
    dom = _dominant(body); body.data.calc_loop_triangles()
    keep = [tuple(t.vertices) for t in body.data.loop_triangles if not any(dom[i].startswith(('RightHand', 'RightForeArm')) for i in t.vertices)]
    tor = [tuple(t.vertices) for t in body.data.loop_triangles if all(dom[i].startswith(TORSO) for i in t.vertices)]
    tri_dom = [dom[t[0]] for t in keep]
    handle = [v.index for v in sword.data.vertices if v.co.z < HANDLE_Z]
    pommel = set(v.index for v in sword.data.vertices if v.co.z < -.36)
    out = []
    for fr in range(0, s.frame_end + 1, step):
        s.frame_set(fr); dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); mw = ev.matrix_world
        co = [mw @ v.co for v in me.vertices]; ev.to_mesh_clear()
        tree = BVHTree.FromPolygons(co, keep, all_triangles=True); ttree = BVHTree.FromPolygons(co, tor, all_triangles=True)
        ax = rig.matrix_world @ rig.pose.bones['Spine1'].head
        palm = rig.matrix_world @ (rig.pose.bones['RightHand'].matrix @ Vector((0, .05, 0)))
        smw = sword.matrix_world; best = {'p': (1e3, ''), 'g': (1e3, '')}
        for i in handle[::2]:
            p = smw @ sword.data.vertices[i].co
            if (p - palm).length < near_hand: continue
            hit = tree.find_nearest(p); d = hit[3] if hit[0] is not None else 1e3; part = tri_dom[hit[2]] if hit[0] is not None else ''
            if hit[0] is not None and d < .12:
                votes = 0
                for dv in DIRS:
                    n = 0; o = p.copy()
                    for _ in range(12):
                        h = tree.ray_cast(o, dv, 2.)
                        if h[0] is None: break
                        n += 1; o = h[0] + dv * 1e-4
                    votes += n % 2
                if votes >= 4 and (p - hit[0]).dot(hit[1]) < 0: d = -d; part = part + '-INSIDE'
            k = 'p' if i in pommel else 'g'
            if d < best[k][0]: best[k] = (d, part)
        out.append((round(fr / s.render.fps * 30, 1), round(best['p'][0], 4), best['p'][1], round(best['g'][0], 4), best['g'][1]))
    return out


# ---- round 2: sword path (critic 2026-10-21: pommel exits the back f6-14, right chest f20-26,
# grip buried in the breastplate f34). The approved blade arc/timing is kept; the right hand is
# translated just far enough outward (and the elbow pole with it) for the whole handle + pommel
# to clear the torso/legs/left arm by `margin`, solved on the FK control rig, smoothed in time.

def _clear_curves(obj, bone_names):
    for fc in list(c.curves(obj.animation_data.action)):
        if any(fc.data_path.startswith(f'pose.bones["{n}"]') for n in bone_names): fc.keyframe_points.clear()


def _two_bone(fk, side, w_new, hand_rot, local0=None):
    pb = fk.pose.bones; S = pb[side + 'Arm'].head.copy(); E = pb[side + 'ForeArm'].head.copy(); W = pb[side + 'Hand'].head.copy()
    a = (E - S).length; b = (W - E).length; d = (w_new - S).length
    d = min(max(d, abs(a - b) + 1e-4), a + b - 1e-4); axis = (w_new - S).normalized()
    pdir = (E - S) - axis * (E - S).dot(axis)
    pdir = pdir.normalized() if pdir.length > 1e-6 else Vector((0, 1, 0))
    ca = (a * a + d * d - b * b) / (2 * a * d); sa = math.sqrt(max(0., 1 - ca * ca))
    e_new = S + axis * a * ca + pdir * a * sa; w_new = S + axis * d
    for name, p0, p1, q0 in ((side + 'Arm', S, e_new, E), (side + 'ForeArm', e_new, w_new, None)):
        bone = pb[name]; head = bone.head.copy(); tail_dir = ((q0 if q0 is not None else pb[side + 'Hand'].head) - head).normalized()
        rot = tail_dir.rotation_difference((p1 - p0).normalized()); m = bone.matrix.copy()
        bone.matrix = Matrix.Translation(p0) @ rot.to_matrix().to_4x4() @ Matrix.Translation(-head) @ m
        bpy.context.view_layer.update()
    if local0 is not None:  # keep the forearm roll consistent with the original wrist twist (no spin)
        fa = pb[side + 'ForeArm']; F = fa.matrix.to_quaternion(); Ft = hand_rot @ local0.inverted()
        d = Ft @ F.inverted()
        if d.w < 0: d.negate()
        ax_ = (pb[side + 'Hand'].head - fa.head).normalized()
        proj = Vector((d.x, d.y, d.z)).dot(ax_) * ax_; tw = Quaternion((d.w, proj.x, proj.y, proj.z))
        if tw.magnitude > 1e-9:
            tw.normalize(); m = fa.matrix.copy(); hd = fa.head.copy()
            fa.matrix = Matrix.Translation(hd) @ tw.to_matrix().to_4x4() @ Matrix.Translation(-hd) @ m; bpy.context.view_layer.update()
    h = pb[side + 'Hand']; h.matrix = Matrix.Translation(w_new) @ hand_rot.to_matrix().to_4x4(); bpy.context.view_layer.update()
    return e_new - E, (w_new - W)


def _clearance(tree, tdom, pts, margin):
    worst = (1e3, None, None)
    for p in pts:
        hit = tree.find_nearest(p)
        if hit[0] is None: continue
        d = hit[3]
        if d < margin + .06:
            votes = 0
            for dv in DIRS:
                k = 0; o = p.copy()
                for _ in range(12):
                    h = tree.ray_cast(o, dv, 2.)
                    if h[0] is None: break
                    k += 1; o = h[0] + dv * 1e-4
                votes += k % 2
            if votes >= 4 and (p - hit[0]).dot(hit[1]) < 0: d = -d
        if d < worst[0]: worst = (d, p, hit)
    return worst


def fix_sword(margin=.03, sigma=3, iters=10, ramp=.14, safety=1.3, pivots=(2.35, 1.4, .3), max_reach=.955,
              exclude=('RightHand', 'RightForeArm', 'RightArm', 'LeftHand', 'LeftForeArm', 'LeftArm'), stride=3, push_normal=False):
    """Per key: swing the sword about a pivot on its own axis (blade tip, blade middle or just above
    the hand) so the handle + pommel clear the body by `margin`; pick the pivot that moves the blade
    tip least (approved arc) while the arm stays within `max_reach` of full extension (no locked elbow). The hand's
    position/rotation deltas are smoothed in time, ramped to zero at the idle endpoints, solved
    onto the FK arm (two-bone) and the elbow pole follows."""
    s = bpy.context.scene
    assert s.get('session_owner') == P['owner'] and s.get('rebuild_job') == 'heavy', 'open_job(heavy) first'
    fps = s.render.fps; fk = bpy.data.objects['Pose_Control_Rig']; rig = bpy.data.objects['Knight_Deform']
    pole = bpy.data.objects['RightArm_Pole']
    body = next(o for o in s.objects if o.type == 'MESH' and o.get('export_body') and not o.get('review_prop'))
    sword = next(o for o in s.objects if o.type == 'MESH' and o.get('review_attachment'))
    dom = _dominant(body); body.data.calc_loop_triangles()
    tris = [tuple(t.vertices) for t in body.data.loop_triangles if not any(dom[i].startswith(tuple(exclude)) for i in t.vertices)]
    tdom = [dom[t[0]] for t in tris]
    handle = [v.co.copy() for v in sword.data.vertices if v.co.z < HANDLE_Z][::stride]
    n = round(DUR / KEY_STEP); times = [min(DUR, i * KEY_STEP) for i in range(n + 1)]
    names = ('RightArm', 'RightForeArm', 'RightHand')
    c.at(0); Ks = (fk.matrix_world @ fk.pose.bones['RightHand'].matrix).inverted() @ sword.matrix_world
    pb = fk.pose.bones
    L = (pb['RightForeArm'].head - pb['RightArm'].head).length + (pb['RightHand'].head - pb['RightForeArm'].head).length
    orig = {}; dpos = {}; drot = {}; worst0 = {}; worst1 = {}; piv = {}
    for t in times:
        c.at(t * fps)
        hand_m = fk.matrix_world @ pb['RightHand'].matrix; S = fk.matrix_world @ pb['RightArm'].head
        orig[t] = ({nm: pb[nm].matrix_basis.copy() for nm in names}, pole.location.copy(), pb['RightHand'].matrix.copy())
        dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); co = [ev.matrix_world @ v.co for v in me.vertices]; ev.to_mesh_clear()
        tree = BVHTree.FromPolygons(co, tris, all_triangles=True); ax = rig.matrix_world @ rig.pose.bones['Spine1'].head
        Sm = hand_m @ Ks; palm = hand_m @ Vector((0, .05, 0))
        base = [Sm @ p for p in handle]; base = [p for p in base if (p - palm).length > .075]
        a = (Sm.to_3x3() @ Vector((0, 0, 1))).normalized(); Pp = Sm @ Vector((0, 0, -.45))
        u = Pp - ax; u.z = 0; u.normalize()
        w0, wp, wh = _clearance(tree, tdom, base, margin); worst0[t] = w0
        if push_normal and wh is not None and not tdom[wh[2]].startswith(TORSO):  # own arm / thighs: push away from that surface
            nv = (wp - wh[0]) if w0 > 0 else Vector(wh[1]); nv = nv - a * nv.dot(a)
            if nv.length > 1e-6: u = nv.normalized()
        r = a.cross(u)
        best = None
        if w0 < margin and r.length > 1e-6:
            r.normalize()
            for pz in pivots:
                Pv = Sm @ Vector((0, 0, pz)); Lp = (Pv - Pp).length; D = 0.; R = Matrix.Identity(4); ok = True
                for it in range(iters):
                    R = Matrix.Translation(Pv) @ Matrix.Rotation(-D / Lp, 4, r) @ Matrix.Translation(-Pv)
                    if ((R @ hand_m).translation - S).length > max_reach * L:  # back off to the reach limit
                        lo, hi = 0., D
                        for _ in range(12):
                            mid = .5 * (lo + hi); Rm = Matrix.Translation(Pv) @ Matrix.Rotation(-mid / Lp, 4, r) @ Matrix.Translation(-Pv)
                            if ((Rm @ hand_m).translation - S).length > max_reach * L: hi = mid
                            else: lo = mid
                        D = lo; R = Matrix.Translation(Pv) @ Matrix.Rotation(-D / Lp, 4, r) @ Matrix.Translation(-Pv); ok = False; break
                    wst = _clearance(tree, tdom, [R @ p for p in base], margin)[0]
                    if wst >= margin: break
                    D += (margin - wst) * 1.1
                wst = _clearance(tree, tdom, [R @ p for p in base], margin)[0]
                shift = ((R @ hand_m).translation - hand_m.translation).length
                tip = Sm @ Vector((0, 0, 2.35)); tipd = ((R @ tip) - tip).length  # keep the approved blade arc
                score = (0 if wst >= margin - 1e-3 else 1, -wst if wst < margin - 1e-3 else tipd + .3 * shift)
                if best is None or score < best[0]: best = (score, R, wst, pz)
        if best is None: R = Matrix.Identity(4); worst1[t] = w0; piv[t] = None
        else: R = best[1]; worst1[t] = best[2]; piv[t] = best[3]
        new = R @ hand_m
        dpos[t] = new.translation - hand_m.translation
        q = new.to_quaternion() @ hand_m.to_quaternion().inverted(); drot[t] = q.axis * q.angle if q.angle > 1e-9 else Vector()
    def smooth(d):
        out = {}
        for i, t in enumerate(times):
            acc = Vector(); ws = 0.
            for j, u_ in enumerate(times):
                w = math.exp(-((i - j) / sigma) ** 2 / 2); acc += d[u_] * w; ws += w
            v = acc / ws
            out[t] = v * safety * (smooth01(t / ramp) * smooth01((DUR - t) / ramp))
        return out
    sp = smooth(dpos); sr = smooth(drot)
    _clear_curves(fk, names); pole.animation_data_clear()
    prev = {}; shift = {}
    for t in times:
        fr = t * fps; c.at(fr); bases, pl, hm = orig[t]
        for nm in names: pb[nm].matrix_basis = bases[nm]
        bpy.context.view_layer.update()
        rq = Quaternion(sr[t].normalized(), sr[t].length) if sr[t].length > 1e-9 else Quaternion()
        want = hm.translation + fk.matrix_world.inverted().to_3x3() @ sp[t]; Sh = pb['RightArm'].head
        if (want - Sh).length > max_reach * L: want = Sh + (want - Sh).normalized() * max(max_reach * L, (hm.translation - Sh).length)
        loc0 = pb['RightForeArm'].matrix.to_quaternion().inverted() @ hm.to_quaternion()
        de, dw = _two_bone(fk, 'Right', want, rq @ hm.to_quaternion(), loc0 if TWIST_FIX else None)
        shift[t] = sp[t].length
        for nm in names: c.key(pb[nm], fr, prev)
        pole.location = pl + de; pole.keyframe_insert('location', frame=fr)
    c.smooth(fk); c.smooth(pole)
    s['heavy_v4_r2_sword'] = json.dumps({'margin': margin, 'pivots': list(pivots), 'maxReach': max_reach, 'sigma': sigma, 'ramp': ramp, 'safety': safety, 'maxHandShift': max(shift.values())})
    c.at(0)
    return {'maxHandShift': round(max(shift.values()), 4), 'maxDeg': round(math.degrees(max(v.length for v in sr.values())), 1),
            'worstBefore': [(round(t * 30, 1), round(worst0[t], 3)) for t in times[::3]], 'solvedWorst': [(round(t * 30, 1), round(worst1[t], 3), piv[t]) for t in times[::3]],
            'shift': [(round(t * 30, 1), round(shift[t], 3)) for t in times[::3]]}


def open_elbow(min_deg=115., sigma=3, until=.45, fade=.15):
    """Round 3: the approved wind-up folds the sword arm to ~54 deg at the shoulder, which put
    the handle into the upper arm and (after r2's clearance push) produced a 146->67->145 deg
    elbow pop. Keep the sword-arm elbow at least `min_deg` open: where the wrist is closer to
    the shoulder than that allows, slide it straight out from the shoulder (hand orientation
    kept, sword translates with it), smoothed in time; the elbow pole follows."""
    s = bpy.context.scene
    assert s.get('session_owner') == P['owner'] and s.get('rebuild_job') == 'heavy', 'open_job(heavy) first'
    fps = s.render.fps; fk = bpy.data.objects['Pose_Control_Rig']; pole = bpy.data.objects['RightArm_Pole']; pb = fk.pose.bones
    names = ('RightArm', 'RightForeArm', 'RightHand')
    n = round(DUR / KEY_STEP); times = [min(DUR, i * KEY_STEP) for i in range(n + 1)]
    c.at(0); a = (pb['RightForeArm'].head - pb['RightArm'].head).length; b = (pb['RightHand'].head - pb['RightForeArm'].head).length
    dmin = math.sqrt(a * a + b * b - 2 * a * b * math.cos(math.radians(min_deg)))
    orig = {}; raw = {}; before = {}
    for t in times:
        c.at(t * fps); S = pb['RightArm'].head.copy(); W = pb['RightHand'].head.copy(); E = pb['RightForeArm'].head.copy()
        orig[t] = ({nm: pb[nm].matrix_basis.copy() for nm in names}, pole.location.copy(), pb['RightHand'].matrix.copy())
        before[t] = math.degrees((S - E).angle(W - E)); d = (W - S).length
        k = 1. if t <= until else max(0., 1 - (t - until) / fade); k = k * k * (3 - 2 * k)
        raw[t] = (W - S).normalized() * (dmin - d) * k if d < dmin else Vector()
    sm = {}
    for i, t in enumerate(times):
        acc = Vector(); ws = 0.
        for j, u in enumerate(times):
            w = math.exp(-((i - j) / sigma) ** 2 / 2); acc += raw[u] * w; ws += w
        v = acc / ws
        sm[t] = v if v.length >= raw[t].length else (v.normalized() * raw[t].length if v.length > 1e-9 else raw[t])
        if t in (times[0], times[-1]): sm[t] = Vector()  # exact approved idle endpoints
    _clear_curves(fk, names); pole.animation_data_clear(); prev = {}; after = {}
    for t in times:
        fr = t * fps; c.at(fr); bases, pl, hm = orig[t]
        for nm in names: pb[nm].matrix_basis = bases[nm]
        bpy.context.view_layer.update()
        de, dw = _two_bone(fk, 'Right', hm.translation + sm[t], hm.to_quaternion())
        S, E, W = pb['RightArm'].head, pb['RightForeArm'].head, pb['RightHand'].head; after[t] = math.degrees((S - E).angle(W - E))
        for nm in names: c.key(pb[nm], fr, prev)
        pole.location = pl + de; pole.keyframe_insert('location', frame=fr)
    c.smooth(fk); c.smooth(pole); c.at(0)
    s['heavy_v4_r3_elbow'] = json.dumps({'minDeg': min_deg, 'sigma': sigma})
    return {'minBefore': round(min(before.values()), 1), 'minAfter': round(min(after.values()), 1), 'maxShift': round(max(v.length for v in sm.values()), 4),
            'elbow': [(round(t * 30, 1), round(before[t]), round(after[t])) for t in times[::3]]}


def ease_arm(t0=0., t1=.24, passes=3, names=('RightArm', 'RightForeArm', 'RightHand')):
    """Round 3: spread the fastest sword-arm rotations of the lift over more frames - a 1-2-1
    quaternion filter on the FK keys inside [t0, t1] (endpoints and keys outside untouched)."""
    s = bpy.context.scene; fps = s.render.fps; fk = bpy.data.objects['Pose_Control_Rig']; pb = fk.pose.bones
    n = round(DUR / KEY_STEP); times = [min(DUR, i * KEY_STEP) for i in range(n + 1)]
    q = {}
    for t in times:
        c.at(t * fps); q[t] = {nm: pb[nm].matrix_basis.copy() for nm in names}
    for _ in range(passes):
        nq = {t: dict(q[t]) for t in times}
        for i in range(1, len(times) - 1):
            t = times[i]
            if not (t0 < t < t1): continue
            for nm in names:
                a, m, b = q[times[i - 1]][nm], q[t][nm], q[times[i + 1]][nm]
                qa, qm, qb = a.to_quaternion(), m.to_quaternion(), b.to_quaternion()
                qa.make_compatible(qm); qb.make_compatible(qm)
                avg = qa.slerp(qb, .5); r = qm.slerp(avg, .5)
                nq[t][nm] = Matrix.LocRotScale(m.to_translation().lerp(a.to_translation().lerp(b.to_translation(), .5), .5), r, m.to_scale())
        q = nq
    _clear_curves(fk, names); prev = {}
    for t in times:
        c.at(t * fps)
        for nm in names: pb[nm].matrix_basis = q[t][nm]
        bpy.context.view_layer.update()
        for nm in names: c.key(pb[nm], t * fps, prev)
    c.smooth(fk); c.at(0)
    return {'eased': [t0, t1], 'passes': passes}
