"""HeavyAttackOneHand v4r4 (Elden Ring pass, A/B vs v4r3 which stays intact). Run via run.py in the
owned session AFTER revise.py open_job('heavy', folder=<v4 out root>) has opened the r3 scene; then
revise.py rebake('heavy') with --out pointing at this pass's own folder. Never saves.

Layers on the r3 controls (additive, endpoints untouched):
  wind-up hold f7-14 - slow build instead of a frozen arm: blade tip rises (wrist, about blade x up)
                       and the torso coils further (Spine yaw, same sense as the approved coil);
                       both release before the strike so the impact path is r3's.
  impact f20-28      - head pitched up about its own lateral axis (face direction measured from the
                       rest pose) so the eyes stay on the target; fades out through recovery.
"""
from pathlib import Path
import bpy, importlib.util, math, json
from mathutils import Vector, Matrix

HERE = Path(__file__).resolve().parent
_cs = importlib.util.spec_from_file_location('veyr_v4_common', HERE / 'common.py'); cm = importlib.util.module_from_spec(_cs); _cs.loader.exec_module(cm)
P = cm.params(globals().get('VEYR_V4_PARAMS'))
_fs = importlib.util.spec_from_file_location('feedback2', cm.REPO / 'tools/art/blender/feedback/feedback_actions.py'); f = importlib.util.module_from_spec(_fs); _fs.loader.exec_module(f)
c = f.c; c.OUT = P['out']; c.OWNER = P['owner']
DUR = 1.4; KEY_STEP = 1 / 50.
Z = Vector((0, 0, 1))


def smooth01(x):
    x = min(1., max(0., x)); return x * x * (3 - 2 * x)


def rot_about(b, axis, pivot, deg):
    if abs(deg) < 1e-9: return
    m = b.matrix.copy(); b.matrix = Matrix.Translation(pivot) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-pivot) @ m; bpy.context.view_layer.update()


def w_hold(t, a=.2, b=.47, r0=.5, r1=.63):  # build through the hold, release before impact
    return smooth01((t - a) / (b - a)) * (1 - smooth01((t - r0) / (r1 - r0)))


def w_head(t, a=.57, b=.67, r0=.933, r1=1.15):
    return smooth01((t - a) / (b - a)) * (1 - smooth01((t - r0) / (r1 - r0)))


def layer(tip_deg=12., twist_deg=6., head_deg=17.):
    s = bpy.context.scene
    assert s.get('session_owner') == P['owner'] and s.get('rebuild_job') == 'heavy', 'open_job(heavy) first'
    fps = s.render.fps; fk = bpy.data.objects['Pose_Control_Rig']; pb = fk.pose.bones; W = fk.matrix_world; hilt = bpy.data.objects['Hilt_Control']
    names = ('Spine', 'Head', 'RightHand')
    n = round(DUR / KEY_STEP); times = [min(DUR, i * KEY_STEP) for i in range(n + 1)]
    base = {}
    for t in times:
        c.at(t * fps); base[t] = {nm: pb[nm].matrix_basis.copy() for nm in names}
    c.at(0); q0 = (W @ pb['Spine2'].matrix).to_quaternion(); Rh0 = (W @ pb['Head'].matrix).to_3x3(); f_local = Rh0.inverted() @ Vector((0, -1, 0))
    c.at(.35 * fps); dq = (W @ pb['Spine2'].matrix).to_quaternion() @ q0.inverted(); sign = 1. if dq.z * (1 if dq.w >= 0 else -1) >= 0 else -1.
    for fc in list(c.curves(fk.animation_data.action)):
        if any(fc.data_path.startswith(f'pose.bones["{nm}"]') for nm in names): fc.keyframe_points.clear()
    prev = {}; log = []
    for t in times:
        fr = t * fps; c.at(fr)
        for nm in names: pb[nm].matrix_basis = base[t][nm]
        bpy.context.view_layer.update()
        g = w_hold(t)
        if g: rot_about(pb['Spine'], Z, pb['Spine'].head.copy(), sign * twist_deg * g)
        if g:
            bl = (hilt.matrix_world.to_3x3() @ Z).normalized(); k = bl.cross(Z)
            if k.length > 1e-6:
                k = (W.to_3x3().inverted() @ k.normalized()).normalized(); rot_about(pb['RightHand'], k, pb['RightHand'].head.copy(), tip_deg * g)
        gh = w_head(t)
        if gh:
            fw = (W @ pb['Head'].matrix).to_3x3() @ f_local; fw.z = 0
            if fw.length > 1e-6:
                k = (W.to_3x3().inverted() @ fw.normalized().cross(Z)).normalized(); rot_about(pb['Head'], k, pb['Head'].head.copy(), head_deg * gh)
        for nm in names: c.key(pb[nm], fr, prev)
        log.append((round(t * 30, 1), round(g, 2), round(gh, 2)))
    c.smooth(fk); c.at(0)
    s['heavy_v4r4'] = json.dumps({'tipDeg': tip_deg, 'twistDeg': twist_deg, 'headDeg': head_deg, 'coilSign': sign, 'keyStep': KEY_STEP})
    return {'coilSign': sign, 'keys': n + 1, 'weights30': log[::5]}


def probe(frames30=range(0, 43)):
    """Baked deform: blade elevation (deg, socket axis vs horizontal), face pitch (deg, rest face dir carried by the head), chest yaw (deg vs f0)."""
    s = bpy.context.scene; rig = bpy.data.objects['Knight_Deform']; so = bpy.data.objects['ReviewWeaponSocket']; W = rig.matrix_world
    s.frame_set(0); Rh0 = (W @ rig.pose.bones['Head'].matrix).to_3x3(); fl = Rh0.inverted() @ Vector((0, -1, 0)); q0 = (W @ rig.pose.bones['Spine2'].matrix).to_quaternion()
    out = []
    for f30 in frames30:
        ff = f30 / 30 * s.render.fps; s.frame_set(int(ff), subframe=ff - int(ff))
        a = (so.matrix_world.to_3x3() @ Z).normalized(); fw = (W @ rig.pose.bones['Head'].matrix).to_3x3() @ fl
        dq = (W @ rig.pose.bones['Spine2'].matrix).to_quaternion() @ q0.inverted()
        out.append((f30, round(math.degrees(math.asin(max(-1, min(1, a.z)))), 1), round(math.degrees(math.asin(max(-1, min(1, fw.normalized().z)))), 1), round(math.degrees(dq.to_euler().z), 1)))
    return out


def closeups(label, frames30=(10, 20, 26), res=640, ortho=.62, view=(3., -3., 1.2), bone='LeftHand'):
    """Left-glove close-ups (baked scene), labelled f<frame> at 30 fps; writes into renders/<label>/."""
    s = bpy.context.scene; cam = s.camera; rig = bpy.data.objects['Knight_Deform']
    folder = cm.check_writable(P['out'] / 'renders' / label); folder.mkdir(parents=True, exist_ok=True)
    s.render.resolution_x = s.render.resolution_y = res; s.display.shading.color_type = 'OBJECT'
    for o in s.objects:
        if o.get('export_body'): o.color = (.53, .55, .6, 1)
        if o.get('review_attachment'): o.color = (.25, .16, .07, 1)
    s.frame_set(0); q0 = (rig.matrix_world @ rig.pose.bones['Spine2'].matrix).to_quaternion()
    paths = []
    for f30 in frames30:
        ff = f30 / 30 * s.render.fps; s.frame_set(int(ff), subframe=ff - int(ff))
        hand = rig.matrix_world @ rig.pose.bones[bone].head
        yaw = ((rig.matrix_world @ rig.pose.bones['Spine2'].matrix).to_quaternion() @ q0.inverted()).to_euler().z  # camera turns with the chest
        d = (Matrix.Rotation(yaw, 3, 'Z') @ Vector(view)).normalized()
        cam.data.type = 'ORTHO'; cam.location = hand + d * 4; cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler(); cam.data.ortho_scale = ortho
        p = folder / f'closeup_f{f30:02d}.png'; s.render.filepath = str(p); bpy.ops.render.render(write_still=True); paths.append(str(p))
    return paths


def layer5(rise_deg=13., twist_deg=12., head_deg=32., neck_frac=.38, t3=.1, t13=.433, rel0=.5, rel1=.633, head_a=.57):
    """v4r5: blade elevation steered to a STEADY rise f3-f13 (wrist about blade x up; cancels the source dip f4-f8),
    stronger coil (Spine yaw), head pitched up harder at impact, split neck/head. Endpoints untouched."""
    s = bpy.context.scene
    assert s.get('session_owner') == P['owner'] and s.get('rebuild_job') == 'heavy', 'open_job(heavy) first'
    fps = s.render.fps; fk = bpy.data.objects['Pose_Control_Rig']; pb = fk.pose.bones; W = fk.matrix_world; hilt = bpy.data.objects['Hilt_Control']
    names = ('Spine', 'Neck', 'Head', 'RightHand')
    n = round(DUR / KEY_STEP); times = [min(DUR, i * KEY_STEP) for i in range(n + 1)]
    base = {}
    for t in times:
        c.at(t * fps); base[t] = {nm: pb[nm].matrix_basis.copy() for nm in names}
    c.at(0); q0 = (W @ pb['Spine2'].matrix).to_quaternion(); Rh0 = (W @ pb['Head'].matrix).to_3x3(); f_local = Rh0.inverted() @ Vector((0, -1, 0))
    c.at(.35 * fps); dq = (W @ pb['Spine2'].matrix).to_quaternion() @ q0.inverted(); sign = 1. if dq.z * (1 if dq.w >= 0 else -1) >= 0 else -1.
    def elev():
        a = (hilt.matrix_world.to_3x3() @ Z).normalized(); return math.degrees(math.asin(max(-1, min(1, a.z)))), a
    for fc in list(c.curves(fk.animation_data.action)):
        if any(fc.data_path.startswith(f'pose.bones["{nm}"]') for nm in names): fc.keyframe_points.clear()
    prev = {}; log = []; E0 = None
    for t in times:
        fr = t * fps; c.at(fr)
        for nm in names: pb[nm].matrix_basis = base[t][nm]
        bpy.context.view_layer.update()
        g = w_hold(t)
        if g: rot_about(pb['Spine'], Z, pb['Spine'].head.copy(), sign * twist_deg * g)
        e_now, bl = elev()
        if E0 is None and t >= t3 - 1e-9: E0 = e_now
        th = 0.
        if E0 is not None and t < rel1:
            tgt = E0 + rise_deg * smooth01((t - t3) / (t13 - t3)); w = 1 - smooth01((t - rel0) / (rel1 - rel0))
            th = (tgt - e_now) * w
            k = bl.cross(Z)
            if k.length > 1e-6 and abs(th) > 1e-6:
                k = (W.to_3x3().inverted() @ k.normalized()).normalized(); rot_about(pb['RightHand'], k, pb['RightHand'].head.copy(), th)
        gh = w_head(t, a=head_a)
        if gh:
            fw = (W @ pb['Head'].matrix).to_3x3() @ f_local; fw.z = 0
            if fw.length > 1e-6:
                k = (W.to_3x3().inverted() @ fw.normalized().cross(Z)).normalized()
                rot_about(pb['Neck'], k, pb['Neck'].head.copy(), head_deg * neck_frac * gh); rot_about(pb['Head'], k, pb['Head'].head.copy(), head_deg * (1 - neck_frac) * gh)
        for nm in names: c.key(pb[nm], fr, prev)
        log.append((round(t * 30, 1), round(elev()[0], 1), round(th, 1)))
    c.smooth(fk); c.at(0)
    s['heavy_v4r5'] = json.dumps({'riseDeg': rise_deg, 'twistDeg': twist_deg, 'headDeg': head_deg, 'neckFrac': neck_frac, 'coilSign': sign})
    return {'coilSign': sign, 'E0': round(E0, 1), 'elev30': log[:25]}


def joints_px(frames30, view=(0, -4, .5), res=480, ortho=2.1, bones=('LeftArm', 'RightArm', 'Head')):
    """Projected joint positions (px, sheet scale) on the baked rig at 30 fps frames."""
    s = bpy.context.scene; rig = bpy.data.objects['Knight_Deform']; px = res / ortho
    d = Vector(view).normalized(); rgt = d.cross(Z).normalized(); upv = rgt.cross(d).normalized(); out = {}
    for f30 in frames30:
        ff = f30 / 30 * s.render.fps; s.frame_set(int(ff), subframe=ff - int(ff))
        out[f30] = {b: (round((rig.matrix_world @ rig.pose.bones[b].head).dot(rgt) * px, 1), round((rig.matrix_world @ rig.pose.bones[b].head).dot(upv) * px, 1)) for b in bones}
    return out
