"""Meshy preset motion -> Knight deform rig retarget (A/B candidates). Execute ONLY in the owned Blender
(owner fable-veyr-knight-walk-20261021, port 9886) via run.py. Saves only under <out>/meshy/.
The approved WalkTwoHand v5r2 files are locked and never opened for writing here.
"""
from pathlib import Path
import bpy, importlib.util, math, json, hashlib, shutil
from mathutils import Vector, Matrix, Quaternion
HERE = Path(__file__).resolve().parent
_cs = importlib.util.spec_from_file_location("veyr_v4_common", HERE / "common.py"); cm = importlib.util.module_from_spec(_cs); _cs.loader.exec_module(cm)
P = cm.params(globals().get("VEYR_V4_PARAMS"))
_fs = importlib.util.spec_from_file_location("feedback2", cm.REPO / "tools/art/blender/feedback/feedback_actions.py"); f = importlib.util.module_from_spec(_fs); _fs.loader.exec_module(f)
c = f.c; c.OWNER = P["owner"]; OUT = P["out"] / "meshy"; c.OUT = OUT
REPO = cm.REPO; MESHY = REPO / "Local/meshy-ab-20261021"
SRC = {"run": REPO / "Local/Blender/remainder-20261021/run_Blender_v1.blend", "backpedal": REPO / "Local/Blender/remainder-20261021/backpedal_Blender_v1.blend"}
CLIP = {"run": "run_sprint.glb", "backpedal": "walk_backward_sword.glb"}


def import_meshy(job, clip=None):
    s = bpy.context.scene; before = set(bpy.data.objects)
    with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]): bpy.ops.import_scene.gltf(filepath=str(Path(clip) if clip and "/" in str(clip) else MESHY / (clip or CLIP[job])))
    new = set(bpy.data.objects) - before; arm = next(o for o in new if o.type == "ARMATURE")
    for o in new:
        if o.type == "MESH": bpy.data.objects.remove(o, do_unlink=True)
    arm.name = "MESHY_Source"; return arm


def inspect(job="run"):
    cm.open_tagged(SRC[job], P["owner"]); s = bpy.context.scene
    arm = import_meshy(job); act = arm.animation_data.action
    keys = sorted({round(k.co.x, 3) for fc in c.curves(act) for k in fc.keyframe_points})
    out = {"scene": [s.frame_start, s.frame_end, s.render.fps, s.get("duration")], "armObj": [list(arm.location), list(arm.rotation_euler), list(arm.scale), arm.rotation_mode],
           "parent": arm.parent.name if arm.parent else None, "action": act.name, "keys": [keys[0], keys[-1], len(keys)], "interp": list({k.interpolation for fc in c.curves(act) for k in fc.keyframe_points}),
           "bones": {}}
    for b in arm.data.bones:
        out["bones"][b.name] = {"parent": b.parent.name if b.parent else None, "headW": [round(x, 4) for x in arm.matrix_world @ b.head_local], "len": round(b.length * arm.matrix_world.to_scale().x, 4)}
    rig = bpy.data.objects["Knight_Deform"]
    out["knight"] = {b.name: [round(x, 4) for x in rig.matrix_world @ b.head_local] for b in rig.data.bones if "Hand" not in b.name or b.name.endswith("Hand")}
    out["sceneObjs"] = [(o.name, o.type, o.parent.name if o.parent else None, [cn.type for cn in o.constraints]) for o in s.objects]
    return out


MAP = {"Hips": "Hips", "Spine": "Spine02", "Spine1": "Spine01", "Spine2": "Spine", "Neck": "neck", "Head": "Head"}
for _s in ("Left", "Right"):
    for _n in ("Shoulder", "Arm", "ForeArm", "Hand", "UpLeg", "Leg", "Foot", "ToeBase"): MAP[_s + _n] = _s + _n
G = {}


def _q(m): return m.to_3x3().normalized().to_quaternion()


def _depth(b):
    d = 0
    while b.parent: b = b.parent; d += 1
    return d


def source_keys(arm):
    act = arm.animation_data.action
    return sorted({round(k.co.x, 4) for fc in c.curves(act) for k in fc.keyframe_points})


def period_check(job="run"):
    """Is the last source key a repeat of the first (closed) or one step short of it?"""
    cm.open_tagged(SRC[job], P["owner"]); arm = import_meshy(job); s = bpy.context.scene; ks = source_keys(arm)
    def snap(fr):
        s.frame_set(int(fr)); return {b.name: (arm.matrix_world @ b.matrix).translation.copy() for b in arm.pose.bones}
    a, b2, z = snap(ks[0]), snap(ks[1]), snap(ks[-1]); y = snap(ks[-2])
    d_first_last = max((a[n] - z[n]).length for n in a); step = max((a[n] - b2[n]).length for n in a); step_end = max((y[n] - z[n]).length for n in a)
    return {"keys": [ks[0], ks[-1], len(ks)], "firstVsLast": d_first_last, "firstStep": step, "lastStep": step_end}


def retarget_pose(rig, arm, base, s_leg, hipsK0, hipsM0, keep=()):
    T_ = G.get("tune", {})
    """Pose Knight FK bones from the evaluated Meshy armature: world-space rest-relative rotations; scaled hips."""
    order = sorted(rig.pose.bones, key=lambda b: _depth(b.bone))
    for pb in order: pb.matrix_basis = base[pb.name]
    bpy.context.view_layer.update()
    mw = arm.matrix_world
    for pb in order:
        src = MAP.get(pb.name)
        if not src or pb.name in keep: continue
        mb = arm.pose.bones[src]; qM = _q(mw @ mb.matrix); qMr = _q(mw @ mb.bone.matrix_local); qKr = _q(rig.data.bones[pb.name].matrix_local)
        q = qM @ qMr.inverted() @ qKr
        damp = T_.get("damp", {}).get(pb.name)
        if damp: q = qKr.slerp(q if q.dot(qKr) >= 0 else -q, damp)
        loc = pb.matrix.translation.copy()
        if pb.name == "Hips":
            loc = hipsK0 + ((mw @ mb.matrix).translation - hipsM0) * s_leg
        pb.matrix = Matrix.LocRotScale(loc, q, pb.matrix.to_scale()); bpy.context.view_layer.update()
        if pb.name in ("Neck", "Head") and T_.get("neck_back"):
            m_ = pb.matrix.copy(); pb.matrix = Matrix.Translation(m_.translation) @ Matrix.Rotation(math.radians(-T_["neck_back"]), 4, "X") @ m_.to_3x3().to_4x4(); bpy.context.view_layer.update()


def _walk_tools():
    sp = importlib.util.spec_from_file_location("veyr_walk_tools", HERE / "walk_v4.py"); m = importlib.util.module_from_spec(sp); m.VEYR_V4_PARAMS = globals().get("VEYR_V4_PARAMS"); sp.loader.exec_module(m)
    return m


def retarget(job="run", period=None, src_fps=30., wrap_frac=None, clip=None, hips_dz=0., keep=()):
    if clip: CLIP[job] = clip
    """Open the remainder scene for job (read only), import the Meshy clip, retarget onto Pose_Control_Rig FK keys."""
    cm.open_tagged(SRC[job], P["owner"]); s = bpy.context.scene; assert s["rebuild_job"] == job
    arm = import_meshy(job, clip); arm.hide_set(True); arm.hide_render = True; arm["reference_only"] = True
    rig = bpy.data.objects["Pose_Control_Rig"]; c.at(0)
    base = {b.name: b.matrix_basis.copy() for b in rig.pose.bones}; G["base"] = base
    G["idle_hilt"] = bpy.data.objects["Hilt_Control"].matrix_world.copy(); G["idle_chest"] = rig.pose.bones["Spine2"].matrix.copy()
    ks = source_keys(arm); n = len(ks); period = period or n / src_fps
    mw = arm.matrix_world
    upK = sum((rig.data.bones[sd + "UpLeg"].head_local).z for sd in ("Left", "Right")) / 2
    upM = sum((mw @ arm.data.bones[sd + "UpLeg"].head_local).z for sd in ("Left", "Right")) / 2
    s_leg = upK / upM; hipsK0 = rig.data.bones["Hips"].head_local.copy() + Vector((0, 0, hips_dz)); hipsM0 = mw @ arm.data.bones["Hips"].head_local
    rig.animation_data_clear(); prev = {}; fps = 150; s.render.fps = fps; s.render.fps_base = 1
    step_f = fps / src_fps
    if wrap_frac is not None:  # source wraps last->first with a shorter step: keep uniform keys, shorten the seam interval
        end = round((n - 1) * step_f + wrap_frac * step_f); period = end / fps
    else:
        end = round(period * fps)
    s.frame_start = 0; s.frame_end = end
    for i, kf in enumerate(ks):
        s.frame_set(int(kf)); retarget_pose(rig, arm, base, s_leg, hipsK0, hipsM0, keep)
        fr = i * step_f if wrap_frac is not None else i * end / n
        for b in rig.pose.bones: c.key(b, fr, prev)
    # close the loop: final key equals the first source key
    s.frame_set(int(ks[0])); retarget_pose(rig, arm, base, s_leg, hipsK0, hipsM0, keep)
    for b in rig.pose.bones: c.key(b, end, prev)
    c.smooth(rig)
    for fc in c.curves(rig.animation_data.action):
        if not any(m.type == "CYCLES" for m in fc.modifiers): fc.modifiers.new("CYCLES")
        fc.update()
    G.update(arm=arm, ks=ks, end=end, n=n, s_leg=s_leg, uniform=(wrap_frac is None))
    rig.animation_data.action.name = job + "_MESHY_RETARGET_FK"
    s["duration"] = period; s["retarget_source"] = CLIP[job]; s["retarget"] = json.dumps({"method": "world-space rest-relative bone rotations (Meshy->Knight by name/role), hips translation scaled by hip-joint height", "s_leg": s_leg, "sourceKeys": n, "period": period})
    s.timeline_markers.clear()
    c.JOBS[job] = ("Meshy " + CLIP[job], period, [i * period / n for i in range(n + 1)], False)
    c.at(0)
    return {"s_leg": s_leg, "keys": n, "period": period, "end": end}


def bake_export(job, name, deliver=True):
    s = bpy.context.scene; assert s.get("session_owner") == P["owner"]
    OUT.mkdir(parents=True, exist_ok=True); cm.check_writable(OUT)
    m = _walk_tools(); fix = m._strap()
    c.bake()
    glb = OUT / (job + "_Blender_v1.glb"); rp = OUT / (job + "-report.json"); r = json.loads(rp.read_text())
    r.update(reviewName=name, retarget=json.loads(s["retarget"]), source=str(s.get("retarget_source")), strapFixWeightsSHA256=s.get("strap_fix_v4"), strapFix=fix, ownerApproved=False, rootMotion="in place", refinements=json.loads(s.get("refinements", "[]")))
    rp.write_text(json.dumps(r, indent=2) + "\n")
    if not deliver: return {"blend": bpy.data.filepath, "glb": str(glb), "sha256": hashlib.sha256(glb.read_bytes()).hexdigest()}
    dest = P["export_dir"] / (name + ".glb"); assert dest.name not in cm.approved_names(); shutil.copyfile(glb, dest)
    return {"blend": bpy.data.filepath, "glb": str(dest), "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(), "nativeIKError": r["nativeIKError"]}


def render(label, job, **kw):
    m = _walk_tools(); return m.render(label, path=OUT / (job + "_Blender_v1.blend"), **kw)


def foot_series(job="run", step=3, path=None):
    """Baked deform rig: per-frame sole min z and contact-centre y for both feet (to find stance windows/speed)."""
    cm.open_tagged(Path(path) if path else OUT / (job + "_Blender_v1.blend"), P["owner"]); s = bpy.context.scene
    m = _walk_tools(); body = m._body(); ids = m.foot_ids(body); rows = []
    for fr in range(0, s.frame_end + 1, step):
        s.frame_set(fr); dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); mw = ev.matrix_world; r = [fr]
        for sd in ("Left", "Right"):
            pts = [mw @ me.vertices[i].co for i in ids[sd]]; z0 = min(p.z for p in pts); low = [p for p in pts if p.z < z0 + .004]
            r += [round(z0, 4), round(sum(p.y for p in low) / len(low), 4), round(sum(p.x for p in low) / len(low), 4)]
        ev.to_mesh_clear(); rows.append(r)
    return rows


def _sole_locals():
    """Foot/toe sole vertices in their bone rest frames (dominant-group), for fast sole-height evaluation."""
    m = _walk_tools(); body = m._body(); rig = bpy.data.objects["Knight_Deform"]
    gid = {g.index: g.name for g in body.vertex_groups}; out = {}
    for sd in ("Left", "Right"):
        F = (rig.matrix_world @ rig.data.bones[sd + "Foot"].matrix_local).inverted(); Tm = (rig.matrix_world @ rig.data.bones[sd + "ToeBase"].matrix_local).inverted()
        fl, tl = [], []
        for v in body.data.vertices:
            w = {gid.get(g.group, ""): g.weight for g in v.groups}; wf = w.get(sd + "Foot", 0); wt = w.get(sd + "ToeBase", 0)
            if wf + wt < .5: continue
            p = body.matrix_world @ v.co
            (fl if wf >= wt else tl).append((F if wf >= wt else Tm) @ p)
        out[sd] = (fl, tl)
    return out


def _sole_min(sd, footM, toeM, loc):
    fl, tl = loc[sd]; pts = [footM @ p for p in fl] + [toeM @ p for p in tl]
    z0 = min(p.z for p in pts); low = [p for p in pts if p.z < z0 + .004]
    return z0, sum(low, Vector()) / len(low)


def foot_pass(job="run", stance_h=.014, ramp=10, speed=None, sign=1, src_feet=False, stride=1., lateral=0., thigh_cap=None, knee_out=0., fix_x=None, vel_only=False, knee_cap=None):
    G["stride"] = stride
    """Replace FK-following leg targets with keyed world targets: per-foot ground offset, exact ground contact and
    constant-speed (in-place) planted slide inside stance windows; Meshy swing kept. Knees still native IK."""
    s = bpy.context.scene; fk = bpy.data.objects["Pose_Control_Rig"]; loc = _sole_locals(); E = s.frame_end; fps = s.render.fps
    F = {sd: [] for sd in ("Left", "Right")}; TR = {}; HK = {}; capped = {"Left": 0., "Right": 0.}
    for fr in range(E + 1):
        sp = _src_feet(fr) if src_feet else None
        c.at(fr)
        for sd in F:
            fm = fk.pose.bones[sd + "Foot"].matrix.copy(); tm = fk.pose.bones[sd + "ToeBase"].matrix.copy()
            if sp: dlt = sp[sd] - fm.translation; fm = Matrix.Translation(dlt) @ fm; tm = Matrix.Translation(dlt) @ tm
            F[sd].append((fm, tm)); HK.setdefault(sd, []).append((fk.pose.bones[sd + "UpLeg"].head.copy(), fk.pose.bones[sd + "Leg"].head.copy(), (fk.pose.bones["Hips"].head - fk.pose.bones["Spine2"].head).normalized()))
    info = {}
    for sd in F:
        mins = []; cen = []
        for fm, tm in F[sd]: z0, cc = _sole_min(sd, fm, tm, loc); mins.append(z0); cen.append(fm.translation.copy())
        k = -min(mins); zs = [z + k for z in mins]
        vy = [(cen[(i + 1) % E].y - cen[(i - 1) % E].y) * fps / 2 for i in range(E + 1)]
        low = sorted(vy[i] for i in range(E + 1) if (zs[i] < stance_h or vel_only) and vy[i] * sign > 0); vp = low[len(low) // 2] if low else 0.
        st = [(zs[i] < stance_h or vel_only) and (vp == 0 or (vy[i] / vp > .3 and vy[i] / vp < 2.5)) for i in range(E + 1)]
        for _ in range(2):  # close 1-2 frame gaps
            st = [st[i] or (st[(i - 1) % E] and st[(i + 1) % E]) for i in range(E + 1)]
        w = []
        for i in range(E + 1):
            dmin = min([abs(i - j) for j in range(E + 1) if st[j]] + [min(abs(i - j - E), abs(i - j + E)) for j in range(E + 1) if st[j]])
            w.append(1. if st[i] else max(0., 1 - dmin / ramp) ** 2 * (3 - 2 * max(0., 1 - dmin / ramp)) if dmin < ramp else 0.)
        idx = [i for i in range(E + 1) if st[i]]
        info[sd] = {"groundOffset": k, "stanceFrames": [idx[0], idx[-1], len(idx)] if idx else None, "cen": cen, "zs": zs, "w": w, "st": st}
    def segments(st):
        seg = [0] * (E + 1); sid = 0
        for i in range(E + 1):
            if st[i] and (i == 0 or not st[i - 1]): sid += 1
            seg[i] = sid if st[i] else 0
        if st[0] and st[E]:
            last = seg[E]; seg = [1 if x == last else x for x in seg]
        return seg
    if speed is None:
        num = den = 0.
        for sd in F:
            I = info[sd]; seg = segments(I["st"])
            for sgi in set(x for x in seg if x):
                fr_ = [i for i in range(E + 1) if seg[i] == sgi]
                if 0 in fr_ and E in fr_: fr_ = [j for j in fr_ if j != E]; fr_ = sorted(fr_, key=lambda j: j if j > E / 2 else j + E)
                tt = [(j if (j > E / 2 or not (0 in fr_ and max(fr_) > E / 2)) else j + E) / fps for j in fr_] if False else None
                base_ = fr_[0]; tt = [((j - base_) % E) / fps for j in fr_]; yy = [I["cen"][j].y for j in fr_]
                if len(tt) > 2:
                    mt = sum(tt) / len(tt); my = sum(yy) / len(yy)
                    num += sum((a - mt) * (b - my) for a, b in zip(tt, yy)); den += sum((a - mt) ** 2 for a in tt)
        speed = num / den
    ystride0 = sum(fk.data.bones[sd_ + "Foot"].head_local.y for sd_ in ("Left", "Right")) / 2
    prev = {}
    for sd in F:
        I = info[sd]; tg = bpy.data.objects[sd + "Leg_Target"]; tg.constraints.clear(); tg.animation_data_clear(); tg.parent = None
        st = I["st"]; runs = []; i = 0
        # stance segments (cyclic) -> anchor (mid contact point) per segment
        seg = [0] * (E + 1); sid = 0
        for i in range(E + 1):
            if st[i] and (i == 0 or not st[i - 1]): sid += 1
            seg[i] = sid if st[i] else 0
        if st[0] and st[E]:
            last = seg[E]; seg = [1 if x == last else x for x in seg]
        anchors = {}
        for sgi in set(x for x in seg if x):
            fr_ = [i for i in range(E + 1) if seg[i] == sgi]
            if 0 in fr_ and E in fr_: fr_ = sorted(fr_, key=lambda j: j if j > E / 2 else j + E)
            mid = fr_[len(fr_) // 2]; anchors[sgi] = (mid, I["cen"][mid].copy())
        # nearest segment for blending outside stance
        def near(i):
            best = None
            for sgi, (mid, a) in anchors.items():
                d = min(abs(i - mid), abs(i - mid - E), abs(i - mid + E))
                if best is None or d < best[0]: best = (d, sgi)
            return best[1]
        mats = []
        for i in range(E + 1):
            fm, tm = F[sd][i]; sgi = seg[i] or near(i); mid, a = anchors[sgi]
            dt = (i - mid); dt = min([dt, dt - E, dt + E], key=abs) / fps
            want = Vector((a.x, a.y + speed * dt, 0.))
            cc = I["cen"][i]; wt = I["w"][i]
            d = Vector(((want.x - cc.x) * wt, (want.y - cc.y) * wt, I["groundOffset"] + (-I["zs"][i]) * wt))
            if not st[i]: d.z = I["groundOffset"] + max(0., -I["zs"][i]) * 0 - I["zs"][i] * wt
            if fix_x is not None: d.x = (1 if sd == "Left" else -1) * fix_x - fm.translation.x
            mats.append(Matrix.Translation(d) @ fm)
        # cyclic 5-tap smoothing of target translation (linear planted slide is preserved; removes ramp kinks)
        for i in range(E + 1):
            acc = Vector((0, 0, 0)); ws = 0.
            for k_, wk in ((-2, 1.), (-1, 2.), (0, 3.), (1, 2.), (2, 1.)):
                j = (i + k_) % E; acc += mats[j].translation * wk; ws += wk
            m_ = mats[i].copy(); m_.translation = acc / ws if not st[i] else mats[i].translation
            m_ = Matrix.Translation(Vector(((1 if sd == "Left" else -1) * lateral, 0, 0))) @ m_
            if not src_feet and stride != 1.: t_ = m_.translation.copy(); m_.translation = Vector((t_.x, ystride0 + (t_.y - ystride0) * stride, t_.z))
            if thigh_cap:
                H, Kf, down = HK[sd][i]; L1 = (fk.data.bones[sd + "Leg"].head_local - fk.data.bones[sd + "UpLeg"].head_local).length; L2 = (fk.data.bones[sd + "Foot"].head_local - fk.data.bones[sd + "Leg"].head_local).length
                for _ in range(3):
                    A = m_.translation; dvec = A - H; dl = min(dvec.length, L1 + L2 - 1e-6); u = dvec.normalized()
                    w = (Kf - H) - u * (Kf - H).dot(u); w = w.normalized() if w.length > 1e-6 else Vector((0, -1, 0))
                    ca = max(-1, min(1, (L1 * L1 + dl * dl - L2 * L2) / (2 * L1 * dl))); Kp = H + L1 * (u * ca + w * math.sqrt(1 - ca * ca))
                    ang = math.degrees(down.angle(Kp - H))
                    if ang <= thigh_cap: break
                    ax = down.cross(Kp - H).normalized(); ex = ang - thigh_cap; capped[sd] = max(capped[sd], ex)
                    R_ = Matrix.Translation(H) @ Matrix.Rotation(math.radians(-ex), 4, ax) @ Matrix.Translation(-H); m_ = Matrix.Translation(R_ @ m_.translation - m_.translation) @ m_
            if knee_cap and not st[i]:
                H, Kf, down = HK[sd][i]; L1 = (fk.data.bones[sd + "Leg"].head_local - fk.data.bones[sd + "UpLeg"].head_local).length; L2 = (fk.data.bones[sd + "Foot"].head_local - fk.data.bones[sd + "Leg"].head_local).length
                dmin = math.sqrt(L1 * L1 + L2 * L2 - 2 * L1 * L2 * math.cos(math.radians(180 - knee_cap)))
                dv = m_.translation - H
                if dv.length < dmin: m_ = Matrix.Translation(dv.normalized() * (dmin - dv.length)) @ m_; capped[sd + "Knee"] = max(capped.get(sd + "Knee", 0), dmin - dv.length)
            tg.matrix_basis = m_; c.key(tg, i, prev)
        if knee_cap or thigh_cap:  # second cyclic smoothing pass over the capped swing path (stance untouched)
            KM = []
            for i in range(E + 1): c.at(i); KM.append(tg.matrix_world.copy())
            tg.animation_data_clear(); prv2 = {}
            for i in range(E + 1):
                m2 = KM[i].copy()
                if not st[i]:
                    acc = Vector(); ws = 0.
                    for k_, wk in ((-3, 1.), (-2, 2.), (-1, 3.), (0, 4.), (1, 3.), (2, 2.), (3, 1.)): acc += KM[(i + k_) % E].translation * wk; ws += wk
                    m2.translation = acc / ws
                tg.matrix_basis = m2; c.key(tg, i, prv2)
        for fc in c.curves(tg.animation_data.action):
            for kp in fc.keyframe_points: kp.interpolation = "LINEAR"
        if knee_out:
            pl = bpy.data.objects[sd + "Leg_Pole"]; pl.parent = None; pl.constraints.clear(); pl.animation_data_clear(); out_ = Vector(((1 if sd == "Left" else -1) * knee_out, 0, 0))
            for i in range(E + 1):
                H, Kf, down = HK[sd][i]; A = F[sd][i][0].translation; mid = (H + A) * .5; dirk = (Kf - mid); dirk = dirk.normalized() if dirk.length > 1e-6 else Vector((0, -1, 0))
                pl.location = Kf + dirk * .3 + out_; pl.keyframe_insert("location", frame=i)
    s["refinements"] = json.dumps(json.loads(s.get("refinements", "[]")) + ["foot_pass: ground offsets %s, constant planted speed %.4f u/s" % ({sd: round(info[sd]["groundOffset"], 4) for sd in F}, speed)])
    return {"speed": speed, "thighCapExcessDeg": capped, **{sd: {"groundOffset": info[sd]["groundOffset"], "stance": info[sd]["stanceFrames"]} for sd in F}}


def sword_axes():
    s = bpy.context.scene; c.at(0); sock = bpy.data.objects["ReviewWeaponSocket"]; hilt = bpy.data.objects["Hilt_Control"]
    sw = [o for o in s.objects if o.get("review_attachment") and o.type == "MESH"]
    inv = sock.matrix_world.inverted(); pts = [inv @ (o.matrix_world @ v.co) for o in sw for v in o.data.vertices]
    ext = [(min(p[i] for p in pts), max(p[i] for p in pts)) for i in range(3)]
    return {"socketLocalExtents": ext, "hiltWorld": [list(r) for r in hilt.matrix_world], "sockEqHilt": max(abs(sock.matrix_world[i][j] - hilt.matrix_world[i][j]) for i in range(4) for j in range(4)),
            "hiltParent": hilt.parent.name if hilt.parent else None, "hiltBasis": [list(r) for r in hilt.matrix_basis], "scale": list(hilt.matrix_world.to_scale())}


BAT = dict(hand_off=(-.05, -.07, -.025), up_back=5., up_out=6., follow=.12, lag=.04, pole_off=(-.16, .04, -.20))


def sword_pass(job="run"):
    """Bat carry: right hand at the right shoulder, blade (socket +Z) held straight up, alive with the chest.
    The hilt becomes a keyed world control; the right-arm IK target rides the hilt with the approved grip offset."""
    s = bpy.context.scene; fk = bpy.data.objects["Pose_Control_Rig"]; E = s.frame_end; fps = s.render.fps
    hilt = bpy.data.objects["Hilt_Control"]; tg = bpy.data.objects["RightArm_Target"]; pole = bpy.data.objects["RightArm_Pole"]
    c.at(0); off = hilt.matrix_basis.copy(); base = hilt.matrix_world.copy(); scl = base.to_scale()
    rest_chest = _q(fk.data.bones["Spine2"].matrix_local)
    ch = []
    for fr in range(E + 1):
        c.at(fr); ch.append((_q(fk.pose.bones["Spine2"].matrix) @ rest_chest.inverted(), fk.pose.bones["RightArm"].head.copy()))
    mean = Quaternion((1, 0, 0, 0)); acc = Vector((0, 0, 0, 0))
    for q, _ in ch: acc += Vector(q if q.w >= 0 else -q)
    mean = Quaternion(acc.normalized())
    # detach controls
    hilt.parent = None; hilt.constraints.clear(); hilt.animation_data_clear()
    tg.constraints.clear(); tg.animation_data_clear(); tg.parent = hilt; tg.matrix_parent_inverse = Matrix.Identity(4); tg.matrix_basis = off.inverted()
    pole.parent = None; pole.constraints.clear(); pole.animation_data_clear()
    B = BAT; prev = {}; lagf = round(B["lag"] * fps)
    up0 = (Matrix.Rotation(math.radians(B["up_back"]), 3, "X").inverted() @ Matrix.Rotation(math.radians(B["up_out"]), 3, "Y").inverted()) @ Vector((0, 0, 1))
    zb = (base.to_3x3().normalized() @ Vector((0, 0, 1))).normalized(); r0 = base.to_3x3().normalized().to_quaternion()
    for fr in range(E + 1):
        q, sh = ch[fr]; ql, _ = ch[(fr - lagf) % E]
        pos = sh + q @ Vector(B["hand_off"])
        wob = mean.inverted() @ ql; wob = Quaternion((1, 0, 0, 0)).slerp(wob if wob.w >= 0 else -wob, B["follow"])
        u = (wob @ up0).normalized()
        R = zb.rotation_difference(u) @ r0
        hilt.matrix_basis = Matrix.LocRotScale(pos + Vector((0, 0, 0)), R, scl); c.key(hilt, fr, prev)
        # hand = hilt @ off^-1 must sit near the shoulder: shift the hilt so the HAND lands on pos
        hand = hilt.matrix_basis @ off.inverted(); hilt.matrix_basis = Matrix.Translation(pos - hand.translation) @ hilt.matrix_basis; c.key(hilt, fr, prev)
        pole.location = sh + q @ Vector(B["pole_off"]); pole.keyframe_insert("location", frame=fr)
    for o in (hilt, pole):
        for fc in c.curves(o.animation_data.action):
            for kp in fc.keyframe_points: kp.interpolation = "LINEAR"
    s["refinements"] = json.dumps(json.loads(s.get("refinements", "[]")) + ["sword_pass: bat carry at right shoulder, blade straight up (back %.0f, out %.0f deg), chest follow %.2f lag %.2fs; right-arm IK target rides hilt with approved grip offset" % (B["up_back"], B["up_out"], B["follow"], B["lag"])])
    return {"frames": E + 1}


def pops(job="run", top=8, path=None):
    """Largest per-frame local rotation steps and seam velocity jumps on the baked deform rig."""
    cm.open_tagged(Path(path) if path else OUT / (job + "_Blender_v1.blend"), P["owner"]); s = bpy.context.scene; rig = bpy.data.objects["Knight_Deform"]; E = s.frame_end
    Q = []; Pp = []
    for fr in range(E + 1):
        s.frame_set(fr); Q.append({b.name: b.matrix_basis.to_quaternion() for b in rig.pose.bones}); Pp.append({b.name: (rig.matrix_world @ b.head).copy() for b in rig.pose.bones})
    steps = []
    for fr in range(E):
        for n in Q[fr]: steps.append((math.degrees(Q[fr][n].rotation_difference(Q[fr + 1][n]).angle), fr, n))
    steps.sort(reverse=True)
    seam = sorted((((Pp[1][n] - Pp[0][n]) - (Pp[E][n] - Pp[E - 1][n])).length * s.render.fps, n) for n in Pp[0])[-5:]
    return {"steps": [(round(a, 2), f_, n) for a, f_, n in steps[:top]], "seam": [(round(v, 3), n) for v, n in seam]}


def sword_pass_idle(job="backpedal", lag=.05):
    """Carry the sword exactly as in the approved one-hand idle, relative to the chest (small lag);
    right-arm IK target rides the hilt with the approved grip offset."""
    s = bpy.context.scene; fk = bpy.data.objects["Pose_Control_Rig"]; E = s.frame_end; fps = s.render.fps
    hilt = bpy.data.objects["Hilt_Control"]; tg = bpy.data.objects["RightArm_Target"]; pole = bpy.data.objects["RightArm_Pole"]
    c.at(0); off = hilt.matrix_basis.copy(); rel = G["idle_chest"].inverted() @ G["idle_hilt"]
    prel = G["idle_chest"].inverted() @ pole.matrix_world.translation
    ch = []
    for fr in range(E + 1):
        c.at(fr); ch.append(fk.pose.bones["Spine2"].matrix.copy())
    hilt.parent = None; hilt.constraints.clear(); hilt.animation_data_clear()
    tg.constraints.clear(); tg.animation_data_clear(); tg.parent = hilt; tg.matrix_parent_inverse = Matrix.Identity(4); tg.matrix_basis = off.inverted()
    pole.parent = None; pole.constraints.clear(); pole.animation_data_clear(); prev = {}; L = round(lag * fps)
    for fr in range(E + 1):
        cn, cl = ch[fr], ch[(fr - L) % E]
        m = cl @ rel; m.translation = (cn @ rel).translation.lerp(m.translation, .5)
        hilt.matrix_basis = m; c.key(hilt, fr, prev)
        pole.location = cn @ prel; pole.keyframe_insert("location", frame=fr)
    for o in (hilt, pole):
        for fc in c.curves(o.animation_data.action):
            for kp in fc.keyframe_points: kp.interpolation = "LINEAR"
    s["refinements"] = json.dumps(json.loads(s.get("refinements", "[]")) + ["sword_pass_idle: approved one-hand idle sword carry relative to chest, lag %.2fs; right-arm IK on hilt" % lag])
    return {"frames": E + 1}


def leg_diag(job="backpedal", side="Right", frames=None):
    cm.open_tagged(OUT / (job + "_Blender_v1.blend"), P["owner"]); s = bpy.context.scene; fk = bpy.data.objects["Pose_Control_Rig"]; tg = bpy.data.objects[side + "Leg_Target"]
    L = (fk.data.bones[side + "Leg"].head_local - fk.data.bones[side + "UpLeg"].head_local).length + (fk.data.bones[side + "Foot"].head_local - fk.data.bones[side + "Leg"].head_local).length
    out = []
    for fr in (frames or range(0, s.frame_end + 1, 3)):
        c.at(fr); hip = fk.pose.bones[side + "UpLeg"].head; t = tg.matrix_world.translation
        out.append((fr, round((t - hip).length / L, 3), [round(x, 3) for x in t], [round(x, 3) for x in fk.pose.bones[side + "Foot"].head]))
    return out


def reach_all(job):
    cm.open_tagged(OUT / (job + "_Blender_v1.blend"), P["owner"]); s = bpy.context.scene; fk = bpy.data.objects["Pose_Control_Rig"]; out = {}
    for lab, (a, b, e) in {"LeftLeg": ("LeftUpLeg", "LeftLeg", "LeftFoot"), "RightLeg": ("RightUpLeg", "RightLeg", "RightFoot"), "LeftArm": ("LeftArm", "LeftForeArm", "LeftHand"), "RightArm": ("RightArm", "RightForeArm", "RightHand")}.items():
        L = (fk.data.bones[b].head_local - fk.data.bones[a].head_local).length + (fk.data.bones[e].head_local - fk.data.bones[b].head_local).length
        tg = bpy.data.objects[lab + "_Target"]; mx = (0, 0)
        for fr in range(0, s.frame_end + 1):
            c.at(fr); r = (tg.matrix_world.translation - fk.pose.bones[a].head).length / L
            if r > mx[0]: mx = (round(r, 4), fr)
        out[lab] = mx
    return out


def _src_feet(fr):
    """Meshy ankle positions at Knight frame fr (cyclic, linear between source keys), mapped onto Knight rest ankles."""
    s = bpy.context.scene; arm = G["arm"]; ks = G["ks"]; n = G["n"]; E = G["end"]; mw = arm.matrix_world
    u = fr / E * n; i = int(u) % n; f_ = u - int(u); j = (i + 1) % n
    out = {}
    for k, w in ((i, 1 - f_), (j, f_)):
        s.frame_set(int(ks[k]))
        for sd in ("Left", "Right"):
            out[sd] = out.get(sd, Vector()) + (mw @ arm.pose.bones[sd + "Foot"].head) * w
    rig = bpy.data.objects["Pose_Control_Rig"]
    res = {}
    for sd in out:
        d = (out[sd] - mw @ arm.data.bones[sd + "Foot"].head_local) * G["s_leg"]; d.x *= G.get("stride", 1.); d.y *= G.get("stride", 1.)
        res[sd] = rig.data.bones[sd + "Foot"].head_local + d
    return res


def use_out(sub):
    """Redirect scene/GLB output (keeps earlier rounds intact)."""
    global OUT
    OUT = P["out"] / sub; c.OUT = OUT; OUT.mkdir(parents=True, exist_ok=True); return str(OUT)


def run_metrics(path=None, job="run"):
    """Per-frame checks for the sprint critique: thigh flexion, free-fist vs chin, spine lean, head pitch,
    blade tilt from vertical, ankle lateral gap, blade-to-helmet clearance."""
    from mathutils.bvhtree import BVHTree
    cm.open_tagged(Path(path) if path else OUT / (job + "_Blender_v1.blend"), P["owner"]); s = bpy.context.scene; rig = bpy.data.objects["Knight_Deform"]; sock = bpy.data.objects["ReviewWeaponSocket"]
    m = _walk_tools(); body = m._body(); gid = {g.index: g.name for g in body.vertex_groups}
    head_ids = [v.index for v in body.data.vertices if sum(g.weight for g in v.groups if gid.get(g.group, "") in ("Head", "Neck")) > .5]
    sw = [o for o in s.objects if o.get("review_attachment") and o.type == "MESH"]
    rows = []
    W = lambda n: rig.matrix_world @ rig.pose.bones[n].head
    for fr in range(0, s.frame_end + 1, 2):
        s.frame_set(fr); dg = bpy.context.evaluated_depsgraph_get()
        down = (W("Hips") - W("Spine2")).normalized(); r = {"f": fr}
        for sd in ("Left", "Right"):
            r[sd + "Thigh"] = round(math.degrees(down.angle(W(sd + "Leg") - W(sd + "UpLeg"))), 1)
        r["fistMinusChin"] = round(W("LeftHand").z - (W("Head").z - .02), 3)
        r["lean"] = round(math.degrees((W("Neck") - W("Hips")).angle(Vector((0, 0, 1)))), 1)
        hm = rig.matrix_world @ rig.pose.bones["Head"].matrix; r["visorPitch"] = round(math.degrees(math.asin(max(-1, min(1, (hm.to_3x3() @ Vector((0, 0, 1))).normalized().z)))), 1)
        r["bladeTilt"] = round(math.degrees((sock.matrix_world.to_3x3() @ Vector((0, 0, 1))).angle(Vector((0, 0, 1)))), 1)
        r["ankleGap"] = round(W("LeftFoot").x - W("RightFoot").x, 3)
        ev = body.evaluated_get(dg); me = ev.to_mesh(); hp = [ev.matrix_world @ me.vertices[i].co for i in head_ids]; ev.to_mesh_clear()
        verts = []; tris = []
        for o in sw:
            e = o.evaluated_get(dg); mm = e.to_mesh(); mm.calc_loop_triangles(); b0 = len(verts); verts += [o.matrix_world @ v.co for v in mm.vertices]; tris += [[b0 + i for i in t.vertices] for t in mm.loop_triangles]; e.to_mesh_clear()
        bvh = BVHTree.FromPolygons(verts, tris, all_triangles=True); r["bladeHelmet"] = round(min(bvh.find_nearest(p)[3] for p in hp[::4]), 4)
        rows.append(r)
    keys = [k for k in rows[0] if k != "f"]
    return {"summary": {k: [min(r[k] for r in rows), max(r[k] for r in rows)] for k in keys}, "rows": rows[::3]}


R2 = dict(damp={"LeftArm": .8, "LeftForeArm": .9}, neck_back=10., lateral=.012, thigh_cap=80., knee_out=.14)


def run_r2(deliver=True):
    """Sprint round 2 (critic): feet apart at the pass, thigh lift capped, free-arm swing cut, neck back, blade near vertical."""
    use_out("meshy_r2"); G["tune"] = R2
    a = retarget("run", period=0.6, clip="run_sprint.glb")
    b = foot_pass("run", stance_h=.02, lateral=R2["lateral"], thigh_cap=R2["thigh_cap"], knee_out=R2["knee_out"])
    sword_pass("run")
    bpy.context.scene["refinements"] = json.dumps(json.loads(bpy.context.scene.get("refinements", "[]")) + ["r2: " + json.dumps(R2)])
    e = bake_export("run", "RunOneHand_Blender_meshy_r2", deliver=deliver)
    return {"retarget": a, "feet": b, "export": e}


TRIPO = REPO / "Local/tripo-ab-20261021"


def inspect_tripo(name="tripo_run_inplace.glb", job="run"):
    cm.open_tagged(SRC[job], P["owner"]); s = bpy.context.scene
    arm = import_meshy(job, str(TRIPO / name)); act = arm.animation_data.action
    ks = source_keys(arm); mw = arm.matrix_world
    out = {"armObj": [list(arm.location), list(arm.rotation_quaternion) if arm.rotation_mode == "QUATERNION" else list(arm.rotation_euler), list(arm.scale)], "parent": arm.parent.name if arm.parent else None,
           "action": act.name, "keys": [ks[0], ks[-1], len(ks)], "nbones": len(arm.data.bones), "acts": [a.name for a in bpy.data.actions][:10]}
    out["bones"] = {b.name: [round(x, 4) for x in mw @ b.head_local] for b in arm.data.bones if "Hand" not in b.name or b.name.endswith("Hand")}
    s.frame_set(int(ks[0])); out["hipsAnim0"] = [round(x, 4) for x in mw @ arm.pose.bones[[b.name for b in arm.data.bones if b.name.endswith("Hips")][0]].head]
    return out


def tripo_hips(name="tripo_run_inplace.glb", job="run"):
    cm.open_tagged(SRC[job], P["owner"]); s = bpy.context.scene; arm = import_meshy(job, str(TRIPO / name)); ks = source_keys(arm); mw = arm.matrix_world
    hb = [b for b in arm.pose.bones if b.name.endswith("Hips")][0]; out = []
    for k in ks:
        s.frame_set(int(k), subframe=k - int(k)); out.append([round(k, 2)] + [round(x, 4) for x in mw @ hb.head])
    lf = [b for b in arm.pose.bones if b.name.endswith("LeftFoot")][0]
    s.frame_set(int(ks[0])); a = mw @ lf.head; s.frame_set(int(ks[-1])); z = mw @ lf.head
    return {"hips": out, "leftFootFirstLast": [list(a), list(z)]}


TRIPO_MAP = {k: "mixamorig:" + k for k in ("Hips", "Spine", "Spine1", "Spine2", "Neck", "Head")}
for _s in ("Left", "Right"):
    for _n in ("Shoulder", "Arm", "ForeArm", "Hand", "UpLeg", "Leg", "Foot", "ToeBase"): TRIPO_MAP[_s + _n] = "mixamorig:" + _s + _n


def retarget_pose_aligned(rig, arm, base, smap, R, s_leg, hipsK0, hips_src, keep=()):
    """Like retarget_pose but with a source->Knight world alignment R and an explicit source hips offset (root removed)."""
    T_ = G.get("tune", {}); Rq = R.to_quaternion()
    order = sorted(rig.pose.bones, key=lambda b: _depth(b.bone))
    for pb in order: pb.matrix_basis = base[pb.name]
    bpy.context.view_layer.update(); mw = arm.matrix_world
    for pb in order:
        src = smap.get(pb.name)
        if not src or pb.name in keep: continue
        mb = arm.pose.bones[src]; qM = _q(mw @ mb.matrix); qMr = _q(mw @ mb.bone.matrix_local); qKr = _q(rig.data.bones[pb.name].matrix_local)
        q = Rq @ qM @ qMr.inverted() @ Rq.inverted() @ qKr
        if T_.get("lean_fix") and pb.name in ("Spine", "Spine1", "Spine2", "Neck", "Head", "LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand", "RightShoulder", "RightArm", "RightForeArm", "RightHand"): q = Quaternion((1, 0, 0), math.radians(-T_["lean_fix"])) @ q
        damp = T_.get("damp", {}).get(pb.name)
        if damp: q = qKr.slerp(q if q.dot(qKr) >= 0 else -q, damp)
        loc = pb.matrix.translation.copy()
        if pb.name == "Hips": loc = hipsK0 + (R @ hips_src) * s_leg
        pb.matrix = Matrix.LocRotScale(loc, q, pb.matrix.to_scale()); bpy.context.view_layer.update()
        if pb.name in ("Neck", "Head") and T_.get("neck_back"):
            m_ = pb.matrix.copy(); pb.matrix = Matrix.Translation(m_.translation) @ Matrix.Rotation(math.radians(-T_["neck_back"]), 4, "X") @ m_.to_3x3().to_4x4(); bpy.context.view_layer.update()


def retarget_tripo(job, name, k0=0, n=15, align_deg=90., keep=(), hips_dz=0.):
    """Tripo (Mixamo skeleton) clip -> Knight FK keys: one cycle of n source keys from k0, root travel removed."""
    if job == "walk_two":
        cm.open_tagged(REPO / "Local/Blender/approved-rebuild-20261021/idle_two_Blender_v1.blend", P["owner"]); s = bpy.context.scene
        assert s["rebuild_job"] == "idle_two"; bpy.data.collections["AUTHORING_idle_two"].name = "AUTHORING_walk_two"; s["rebuild_job"] = "walk_two"
        c.at(0)
        for sd in ("Left", "Right"):
            tg_ = bpy.data.objects[sd + "Arm_Target"]; mb_ = tg_.matrix_basis.copy(); tg_.animation_data_clear(); tg_.matrix_basis = mb_
        G["armpole0"] = {sd: bpy.data.objects[sd + "Arm_Pole"].matrix_world.translation.copy() for sd in ("Left", "Right")}
    else:
        cm.open_tagged(SRC[job], P["owner"]); s = bpy.context.scene; assert s["rebuild_job"] == job
    arm = import_meshy(job, str(TRIPO / name)); arm.hide_set(True); arm.hide_render = True; arm["reference_only"] = True
    rig = bpy.data.objects["Pose_Control_Rig"]; c.at(0)
    base = {b.name: b.matrix_basis.copy() for b in rig.pose.bones}; G["base"] = base
    G["idle_hilt"] = bpy.data.objects["Hilt_Control"].matrix_world.copy(); G["idle_chest"] = rig.pose.bones["Spine2"].matrix.copy()
    ks = source_keys(arm); mw = arm.matrix_world; R = Matrix.Rotation(math.radians(align_deg), 3, "Z")
    upK = sum(rig.data.bones[sd + "UpLeg"].head_local.z for sd in ("Left", "Right")) / 2
    upM = sum((mw @ arm.data.bones["mixamorig:" + sd + "UpLeg"].head_local).z for sd in ("Left", "Right")) / 2
    s_leg = upK / upM; hipsK0 = rig.data.bones["Hips"].head_local.copy() + Vector((0, 0, hips_dz)); hr = mw @ arm.data.bones["mixamorig:Hips"].head_local
    hb = arm.pose.bones["mixamorig:Hips"]; H = []
    for i in range(n + 1):
        s.frame_set(int(ks[k0 + i]), subframe=ks[k0 + i] - int(ks[k0 + i])); H.append((mw @ hb.head).copy())
    drift = H[n] - H[0]; res = [H[i] - (H[0] + drift * (i / n)) for i in range(n)]
    mh = sum(res, Vector()) / n
    fps = 150; s.render.fps = fps; s.render.fps_base = 1; step_src = ks[1] - ks[0]; end = round(n * step_src); s.frame_start = 0; s.frame_end = end
    rig.animation_data_clear(); prev = {}
    for i in range(n + 1):
        j = i % n; kf = ks[k0 + j]; s.frame_set(int(kf), subframe=kf - int(kf))
        hs = res[j] - mh; hs = Vector((hs.x, hs.y, H[j].z - hr.z))
        retarget_pose_aligned(rig, arm, base, TRIPO_MAP, R, s_leg, hipsK0, hs, keep)
        for b in rig.pose.bones: c.key(b, i * end / n, prev)
    c.smooth(rig)
    for fc in c.curves(rig.animation_data.action):
        if not any(m.type == "CYCLES" for m in fc.modifiers): fc.modifiers.new("CYCLES")
        fc.update()
    period = end / fps; rig.animation_data.action.name = job + "_TRIPO_RETARGET_FK"; CLIP[job] = name
    s["duration"] = period; s["retarget_source"] = name
    s["retarget"] = json.dumps({"method": "Tripo Mixamo skeleton -> Knight by name; world-space rest-relative rotations with +%g deg Z alignment; root travel removed (%.3f u/cycle); hips scaled by hip-joint height" % (align_deg, drift.length), "s_leg": s_leg, "sourceKeys": [k0, n], "period": period})
    c.JOBS[job] = ("Tripo " + name, period, [i * period / n for i in range(n + 1)], False)
    G.update(end=end, n=n, s_leg=s_leg)
    c.at(0)
    return {"s_leg": s_leg, "n": n, "period": period, "end": end, "driftPerCycle": list(drift), "closureCheck": "key %d vs %d" % (k0, k0 + n)}


RT = dict(damp={"LeftArm": .8, "LeftForeArm": .9}, neck_back=0., lateral=.03, thigh_cap=80., knee_out=.14, lean_fix=14., hips_dz=-.025)


def run_tripo(deliver=True, k0=0, n=15):
    use_out("tripo"); G["tune"] = RT; BAT["follow"] = .05
    a = retarget_tripo("run", "tripo_run_inplace.glb", k0=k0, n=n, hips_dz=RT["hips_dz"])
    b = foot_pass("run", stance_h=.02, lateral=RT["lateral"], thigh_cap=RT["thigh_cap"], knee_out=RT["knee_out"])
    sword_pass("run")
    bpy.context.scene["refinements"] = json.dumps(json.loads(bpy.context.scene.get("refinements", "[]")) + ["tripo: " + json.dumps(RT)])
    e = bake_export("run", "RunOneHand_Blender_tripo", deliver=deliver)
    return {"retarget": a, "feet": b, "export": e}


def tripo_cycle_search(name="tripo_run_inplace.glb", job="run", ns=(14, 15, 16)):
    cm.open_tagged(SRC[job], P["owner"]); s = bpy.context.scene; arm = import_meshy(job, str(TRIPO / name)); ks = source_keys(arm); mw = arm.matrix_world
    names = list(TRIPO_MAP.values()); P_ = []
    for k in ks:
        s.frame_set(int(k), subframe=k - int(k)); h = mw @ arm.pose.bones["mixamorig:Hips"].head
        P_.append({n: (mw @ arm.pose.bones[n].head) - h for n in names})
    res = []
    for n in ns:
        for k0 in range(0, len(ks) - n):
            d = max((P_[k0][b] - P_[k0 + n][b]).length for b in names)
            v = max(((P_[k0 + 1][b] - P_[k0][b]) - (P_[k0 + n][b] - P_[k0 + n - 1][b])).length for b in names) if k0 + n < len(ks) else 9
            res.append((round(d, 4), round(v, 4), k0, n))
    res.sort(); return res[:8]


def sword_pass_two(lag=.06, rot_follow=.45, off=(-.03, 0., .006), roll=-9.):
    """Two-hand ready guard carried like the approved idle (and v5r2): hilt follows the chest with lag, blade
    tipped to his right (same offset/roll as WalkTwoHand v5r2); arm poles chest-relative. Arm targets ride the hilt."""
    s = bpy.context.scene; fk = bpy.data.objects["Pose_Control_Rig"]; E = s.frame_end; fps = s.render.fps
    hilt = bpy.data.objects["Hilt_Control"]; h0 = G["idle_hilt"]; c0 = G["idle_chest"]; inv0 = c0.inverted()
    ch = []
    for fr in range(E + 1):
        c.at(fr); ch.append(fk.pose.bones["Spine2"].matrix.copy())
    hilt.animation_data_clear(); prev = {}; L = round(lag * fps)
    for fr in range(E + 1):
        rigid = ch[(fr - L) % E] @ inv0 @ h0; dp = rigid.translation - h0.translation
        pos = h0.translation + Vector((dp.x * .65, dp.y * .8, dp.z * .85)) + Vector(off)
        q = h0.to_quaternion().slerp(rigid.to_quaternion(), rot_follow)
        hilt.matrix_basis = Matrix.Translation(pos) @ Matrix.Rotation(math.radians(roll), 4, "Y") @ q.to_matrix().to_4x4() @ Matrix.Diagonal(h0.to_scale().to_4d()); c.key(hilt, fr, prev)
        for sd in ("Left", "Right"):
            pl = bpy.data.objects[sd + "Arm_Pole"]
            if fr == 0: pl.parent = None; pl.constraints.clear(); pl.animation_data_clear()
            pl.location = ch[fr] @ inv0 @ (G["armpole0"][sd] + Vector((0, -.2, .08))); pl.keyframe_insert("location", frame=fr)
    s["refinements"] = json.dumps(json.loads(s.get("refinements", "[]")) + ["sword_pass_two: idle two-hand guard on chest, lag %.2f, rot follow %.2f, v5r2 offset/roll" % (lag, rot_follow)])
    return {"frames": E + 1}


WT = dict(damp={}, neck_back=0., lateral=0., thigh_cap=None, knee_out=.08, lean_fix=0., hips_dz=0.)


def guardwalk_tripo(deliver=True, k0=42, n=32, hips_dz=0., stride=1.):
    use_out("tripo"); G["tune"] = WT
    a = retarget_tripo("walk_two", "tripo_guardwalk_t2m.glb", k0=k0, n=n, hips_dz=hips_dz, keep=("LeftShoulder", "RightShoulder"))
    b = foot_pass("walk_two", stance_h=.04, knee_out=WT["knee_out"], src_feet=False, fix_x=.064, vel_only=True, stride=stride)
    sword_pass_two()
    e = bake_export("walk_two", "WalkTwoHand_Blender_tripo", deliver=deliver)
    return {"retarget": a, "feet": b, "export": e}


def dragon_small(src=None, out=None, max_px=1024, quality=80):
    """Static bind-pose dragon mesh for Tripo auto-rig: no armature, textures <= max_px JPEG. Never saves a .blend."""
    src = Path(src or REPO / "Local/Blender/dragon-v1-20261021/source/DragonRig.glb"); out = Path(out or REPO / "Local/tripo-ab-20261021/dragon_small.glb")
    cm.open_tagged(REPO / "Local/Blender/approved-rebuild-20261021/idle_two_Blender_v1.blend", P["owner"]); s = bpy.context.scene
    for o in list(s.objects): bpy.data.objects.remove(o, do_unlink=True)
    with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]): bpy.ops.import_scene.gltf(filepath=str(src))
    arms = [o for o in s.objects if o.type == "ARMATURE"]; meshes = [o for o in s.objects if o.type == "MESH"]
    info = {"src": str(src), "srcBytes": src.stat().st_size, "objects": [(o.name, o.type, len(o.data.vertices) if o.type == "MESH" else None) for o in s.objects]}
    for a in arms:
        if a.animation_data: a.animation_data_clear()
        for pb in a.pose.bones: pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    keep = [o for o in meshes if len(o.data.vertices) > 1000]
    for o in keep:
        mw = o.matrix_world.copy()
        for m in list(o.modifiers):
            if m.type == "ARMATURE": o.modifiers.remove(m)
        o.parent = None; o.matrix_world = mw; o.vertex_groups.clear()
    for o in list(s.objects):
        if o not in keep: bpy.data.objects.remove(o, do_unlink=True)
    imgs = []
    for im in bpy.data.images:
        if im.size[0] > max_px or im.size[1] > max_px:
            f_ = max_px / max(im.size); im.scale(max(1, int(im.size[0] * f_)), max(1, int(im.size[1] * f_)))
        imgs.append((im.name, list(im.size)))
    tris = 0
    for o in keep:
        me = o.data; me.calc_loop_triangles(); tris += len(me.loop_triangles)
    bb = [o.matrix_world @ Vector(c_) for o in keep for c_ in o.bound_box]
    for o in s.objects: o.select_set(o in keep)
    with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
        bpy.ops.export_scene.gltf(filepath=str(out), export_format="GLB", use_selection=True, export_animations=False, export_skins=False, export_image_format="JPEG", export_jpeg_quality=quality, export_cameras=False, export_lights=False)
    info.update(out=str(out), bytes=out.stat().st_size, triangles=tris, images=imgs, meshes=[o.name for o in keep], bbox=[[round(min(v[i] for v in bb), 3) for i in range(3)], [round(max(v[i] for v in bb), 3) for i in range(3)]], sha256=hashlib.sha256(out.read_bytes()).hexdigest())
    return info


def dragon_views(glb=None, label="dragon_small"):
    glb = Path(glb or REPO / "Local/tripo-ab-20261021/dragon_small.glb")
    cm.open_tagged(REPO / "Local/Blender/approved-rebuild-20261021/idle_two_Blender_v1.blend", P["owner"]); s = bpy.context.scene; cam = s.camera
    for o in list(s.objects):
        if o != cam: bpy.data.objects.remove(o, do_unlink=True)
    with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]): bpy.ops.import_scene.gltf(filepath=str(glb))
    folder = cm.check_writable(P["out"] / "renders" / label); folder.mkdir(parents=True, exist_ok=True)
    s.render.resolution_x = s.render.resolution_y = 720; s.display.shading.color_type = "TEXTURE"
    out = []
    for view, d in {"front": (0, -1, .15), "side": (1, 0, .15), "threequarter": (.75, -1, .45), "top": (0, -.01, 1), "front_x": (-1, 0, .15)}.items():
        d = Vector(d).normalized(); cam.location = Vector((0, 0, .22)) + d * 5; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler(); cam.data.ortho_scale = 1.2
        s.render.filepath = str(folder / (view + ".png")); bpy.ops.render.render(write_still=True); out.append(s.render.filepath)
    return out


def free_arm_pass(min_lat=.075, side="Left"):
    """Keep the free wrist at least min_lat outside the sternum line (chest frame) every frame; keyed world target."""
    s = bpy.context.scene; fk = bpy.data.objects["Pose_Control_Rig"]; E = s.frame_end; tg = bpy.data.objects[side + "Arm_Target"]
    M = []; pushed = 0.
    rest_c = _q(fk.data.bones["Spine2"].matrix_local)
    for fr in range(E + 1):
        c.at(fr); h = fk.pose.bones[side + "Hand"].matrix.copy(); ch = fk.pose.bones["Spine2"]
        ax = (_q(ch.matrix) @ rest_c.inverted()) @ Vector((1 if side == "Left" else -1, 0, 0))
        lat = (h.translation - ch.head).dot(ax)
        if lat < min_lat:
            x = (min_lat - lat); pushed = max(pushed, x); h = Matrix.Translation(ax * x) @ h
        M.append(h)
    tg.constraints.clear(); tg.animation_data_clear(); tg.parent = None; prev = {}
    for fr in range(E + 1):
        acc = Vector(); ws = 0.
        for k_, wk in ((-2, 1.), (-1, 2.), (0, 3.), (1, 2.), (2, 1.)): acc += M[(fr + k_) % E].translation * wk; ws += wk
        m_ = M[fr].copy(); m_.translation = acc / ws; tg.matrix_basis = m_; c.key(tg, fr, prev)
    s["refinements"] = json.dumps(json.loads(s.get("refinements", "[]")) + ["free_arm_pass: free wrist >= %.3f outside sternum line, max push %.3f" % (min_lat, pushed)])
    return {"maxPush": pushed}


def run_tripo_r2(deliver=True):
    use_out("tripo_r2"); G["tune"] = RT; BAT.update(hand_off=(-.03, -.14, -.03), up_back=-2., up_out=6., follow=.05)
    a = retarget_tripo("run", "tripo_run_inplace.glb", k0=10, n=15, hips_dz=RT["hips_dz"])
    b = foot_pass("run", stance_h=.02, lateral=RT["lateral"], thigh_cap=72., knee_out=RT["knee_out"], knee_cap=110.)
    sword_pass("run"); fa = free_arm_pass(min_lat=.13)
    bpy.context.scene["refinements"] = json.dumps(json.loads(bpy.context.scene.get("refinements", "[]")) + ["tripo_r2: thigh cap 72, knee cap 110, bat hand forward -0.14"])
    e = bake_export("run", "RunOneHand_Blender_tripo_r2", deliver=deliver)
    return {"feet": b, "freeArm": fa, "export": e}


def run_meshy_r3(deliver=True):
    use_out("meshy_r3"); R3 = dict(R2); R3.update(neck_back=20.); G["tune"] = R3; BAT.update(hand_off=(-.05, -.11, -.025), up_back=-4., up_out=6., follow=.06)
    a = retarget("run", period=0.6, clip="run_sprint.glb")
    b = foot_pass("run", stance_h=.02, lateral=R3["lateral"], thigh_cap=R3["thigh_cap"], knee_out=R3["knee_out"])
    sword_pass("run")
    bpy.context.scene["refinements"] = json.dumps(json.loads(bpy.context.scene.get("refinements", "[]")) + ["r3: head tipped up 20, blade forward of helmet"])
    e = bake_export("run", "RunOneHand_Blender_meshy_r3", deliver=deliver)
    return {"feet": b, "export": e}
