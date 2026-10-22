"""Elden-Ring-style remaster (A/B *_Blender_v2) of the six approved Blender idles/attacks. Execute ONLY in the owned
Blender (owner fable-veyr-knight-walk-20261021, port 9886) via run.py. Opens the approved scenes read-only and writes
only under <out>/er_v2/ and <export_dir>/<Review>_Blender_v2.glb. Approved files are never written.
Additive Blender layers on the approved FK/control curves; endpoints and timing preserved (audit_er.py checks it).
"""
from pathlib import Path
import bpy, importlib.util, math, json, hashlib, shutil
from mathutils import Vector, Matrix, Quaternion
HERE = Path(__file__).resolve().parent
_cs = importlib.util.spec_from_file_location("veyr_v4_common", HERE / "common.py"); cm = importlib.util.module_from_spec(_cs); _cs.loader.exec_module(cm)
P = cm.params(globals().get("VEYR_V4_PARAMS"))
_as = importlib.util.spec_from_file_location("veyr_core_er", cm.REPO / "tools/art/blender/rebuild/approved_actions.py"); c = importlib.util.module_from_spec(_as); _as.loader.exec_module(c)
REPO = cm.REPO; APPROVED = REPO / "Local/Blender/approved-rebuild-20261021"; OUT = P["out"] / "er_v2"; c.OUT = OUT; c.OWNER = P["owner"]
NAMES = {"idle_one": "IdleOneHand_Blender_v2", "idle_two": "IdleTwoHand_Blender_v2", "overhead": "LightAttack_BlackKnightReference_Blender_v2",
         "sweep": "StrongAttackTwoHand_Sweep_Blender_v2", "thrust": "StrongAttackTwoHand_Thrust_Blender_v2", "light_two": "LightAttackTwoHand_Compact_Blender_v2"}
STEP = 3
G = {}


def _walk_tools():
    sp = importlib.util.spec_from_file_location("veyr_walk_tools", HERE / "walk_v4.py"); m = importlib.util.module_from_spec(sp); m.VEYR_V4_PARAMS = globals().get("VEYR_V4_PARAMS"); sp.loader.exec_module(m)
    return m


def smooth01(x): x = min(1., max(0., x)); return x * x * (3 - 2 * x)
def env(t, D, r=.45): return smooth01(t / r) * smooth01((D - t) / r)


def wr(fk, name, axis, deg):
    if abs(deg) < 1e-9: return
    b = fk.pose.bones[name]; m = b.matrix.copy(); b.matrix = Matrix.Translation(m.translation) @ Matrix.Rotation(math.radians(deg), 4, axis) @ m.to_3x3().to_4x4(); bpy.context.view_layer.update()


def open_job(job):
    cm.open_tagged(APPROVED / (job + "_Blender_v1.blend"), P["owner"]); s = bpy.context.scene; assert s["rebuild_job"] == job
    OUT.mkdir(parents=True, exist_ok=True); cm.check_writable(OUT)
    return s


def animated_controls(job):
    return [o for o in bpy.data.collections["AUTHORING_" + job].objects if o.type == "EMPTY" and o.animation_data and o.animation_data.action]


def sample(job, warp=None):
    """Sample approved control state (FK bases, world-keyed empties) at warped times; returns per-frame records."""
    s = bpy.context.scene; fk = bpy.data.objects["Pose_Control_Rig"]; E = s.frame_end; emp = animated_controls(job); rec = []
    for fr in range(0, E + 1, STEP) if E % STEP == 0 else list(range(0, E, STEP)) + [E]:
        src = warp(fr) if warp else fr; c.at(src)
        rec.append((fr, {b.name: b.matrix_basis.copy() for b in fk.pose.bones}, {o.name: o.matrix_basis.copy() for o in emp}, fk.pose.bones["Spine2"].head.copy()))
    return rec


def rekey(job, rec, layer=None):
    """Clear and re-key FK + world-keyed empties from samples, applying an additive layer(t, fk, empties)."""
    s = bpy.context.scene; fk = bpy.data.objects["Pose_Control_Rig"]; fps = s.render.fps; emp = {o.name: o for o in animated_controls(job)}
    fk.animation_data_clear()
    for o in emp.values(): o.animation_data_clear()
    prev = {}
    for fr, bases, embs, chest0 in rec:
        for b in fk.pose.bones: b.matrix_basis = bases[b.name]
        for n, m in embs.items(): emp[n].matrix_basis = m
        bpy.context.view_layer.update()
        if layer: layer(fr / fps, fk, emp, chest0)
        for b in fk.pose.bones: c.key(b, fr, prev)
        for o in emp.values(): c.key(o, fr, prev)
    for o in [fk, *emp.values()]: c.smooth(o)
    fk.animation_data.action.name = job + "_ER_V2_FK"


def bake_export(job, name=None):
    name = name or NAMES[job]
    s = bpy.context.scene; assert s.get("session_owner") == P["owner"]
    m = _walk_tools(); fix = m._strap(); strays = fix_strays()
    tx = bpy.data.texts.get("er_v4.py") or bpy.data.texts.new("er_v4.py"); tx.clear(); tx.write(Path(__file__).read_text()); tx.use_fake_user = True
    c.bake()
    glb = OUT / (job + "_Blender_v1.glb"); rp = OUT / (job + "-report.json"); r = json.loads(rp.read_text())
    r.update(strayIslandFix=strays, reviewName=name, remaster="Elden Ring A/B v2 from approved " + job + "_Blender_v1", layers=json.loads(s.get("er_layers", "[]")), strapFixWeightsSHA256=s.get("strap_fix_v4"), ownerApproved=False)
    rp.write_text(json.dumps(r, indent=2) + "\n")
    dest = P["export_dir"] / (name + ".glb"); assert dest.name not in cm.approved_names(); P["export_dir"].mkdir(parents=True, exist_ok=True); shutil.copyfile(glb, dest)
    return {"blend": bpy.data.filepath, "glb": str(dest), "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(), "nativeIKError": r["nativeIKError"], "endpoint": r["endpointMatrixDelta"]}


def clip_check(job, path=None, step=4):
    """Sword mesh vs body (hands/fingers excluded) and blade vs helmet clearance over the clip (evaluated meshes)."""
    from mathutils.bvhtree import BVHTree
    cm.open_tagged(Path(path) if path else OUT / (job + "_Blender_v1.blend"), P["owner"]); s = bpy.context.scene
    m = _walk_tools(); body = m._body(); gid = {g.index: g.name for g in body.vertex_groups}
    def dom(v):
        best = max(v.groups, key=lambda g: g.weight, default=None); return gid.get(best.group, "") if best else ""
    nonhand = [v.index for v in body.data.vertices if "Hand" not in dom(v) and "ForeArm" not in dom(v)]
    head = [v.index for v in body.data.vertices if dom(v) in ("Head", "Neck")]
    sw = [o for o in s.objects if o.get("review_attachment") and o.type == "MESH"]; worst = (9, 0); worstH = (9, 0)
    for fr in range(0, s.frame_end + 1, step):
        s.frame_set(fr); dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); mw = ev.matrix_world
        verts = []; tris = []
        for o in sw:
            e = o.evaluated_get(dg); mm = e.to_mesh(); mm.calc_loop_triangles(); b0 = len(verts); verts += [o.matrix_world @ v.co for v in mm.vertices]; tris += [[b0 + i for i in t.vertices] for t in mm.loop_triangles]; e.to_mesh_clear()
        bvh = BVHTree.FromPolygons(verts, tris, all_triangles=True)
        dd = [(bvh.find_nearest(mw @ me.vertices[i].co), i) for i in nonhand[::3]]; (hit, vi) = min(dd, key=lambda x: x[0][3]); d = hit[3]
        dh = min(bvh.find_nearest(mw @ me.vertices[i].co)[3] for i in head[::2])
        if d < worst[0]:
            sl = sw[0].matrix_world.inverted() @ hit[0] if sw else Vector()
            worst = (round(d, 4), fr, dom(body.data.vertices[vi]), round(sl.z, 3), sum(1 for (h_, i_) in dd if h_[3] < .003))
        if dh < worstH[0]: worstH = (round(dh, 4), fr)
        ev.to_mesh_clear()
    return {"swordToBodyMin": worst, "swordToHeadMin": worstH}


def render(label, job, path=None, **kw):
    return _walk_tools().render(label, path=Path(path) if path else OUT / (job + "_Blender_v1.blend"), **kw)


# ----------------------------------------------------------------------------------------- idle_one --------
IDLE1 = dict(breath_cycles=2, chest=(2.0, 2.4), clav=4.5, head_breath=1.2, sway_x=.010, sway_yaw=1.6, roll=1.4, head_yaw=3.0, head_lag=.25, arm_lag=.18, arm_swing=.006)


def idle_one():
    s = open_job("idle_one"); fps = s.render.fps; D = s["duration"]; T = IDLE1; rec = sample("idle_one")
    hist = {}
    def layer(t, fk, emp, chest0):
        e = env(t, D)  # additive layers fade to zero at the approved endpoints (exact start/end pose, seamless loop)
        b = e * math.sin(2 * math.pi * T["breath_cycles"] * t / D); bl = e * math.sin(2 * math.pi * T["breath_cycles"] * (t - .15) / D)
        w = e * math.sin(2 * math.pi * t / D); wl = e * math.sin(2 * math.pi * (t - T["head_lag"]) / D)
        # weight shift over the planted feet (one slow cycle), small pelvis roll/yaw; spine re-centres the chest
        hips = fk.pose.bones["Hips"]; hips.location += fk.data.bones["Hips"].matrix_local.to_3x3().inverted() @ Vector((T["sway_x"] * w, 0, -.002 * e * (1 - math.cos(2 * math.pi * t / D)) * .5)); bpy.context.view_layer.update()
        wr(fk, "Hips", "Y", T["roll"] * w); wr(fk, "Hips", "Z", T["sway_yaw"] * w); wr(fk, "Spine", "Y", -.8 * T["roll"] * w)
        # breathing: chest lifts and opens, clavicles rise, head counters slightly (lagged)
        wr(fk, "Spine1", "X", -T["chest"][0] * b); wr(fk, "Spine2", "X", -T["chest"][1] * b)
        wr(fk, "LeftShoulder", "Y", -T["clav"] * bl); wr(fk, "RightShoulder", "Y", T["clav"] * bl)
        wr(fk, "Neck", "X", .5 * T["head_breath"] * b); wr(fk, "Head", "X", .5 * T["head_breath"] * bl)
        wr(fk, "Head", "Z", T["head_yaw"] * wl - .5 * T["sway_yaw"] * w)
        # free left arm: hangs from the shoulder, follows the chest with lag and a small pendulum
        tg = emp.get("LeftArm_Target")
        if tg:
            ch = fk.pose.bones["Spine2"].head.copy(); hist[round(t, 4)] = ch - chest0
            lagd = hist.get(round(max(0., t - T["arm_lag"]), 4), ch - chest0)
            tg.matrix_basis = Matrix.Translation((Vector((lagd.x, lagd.y, lagd.z)) * .9 + Vector((0, T["arm_swing"] * math.sin(2 * math.pi * (t - .3) / D), 0))) * e) @ tg.matrix_basis
    rekey("idle_one", rec, layer)
    s["er_layers"] = json.dumps(["idle_one: " + json.dumps(IDLE1)])
    return bake_export("idle_one")


# ----------------------------------------------------------------------------------------- idle_two --------
IDLE2 = dict(breath_cycles=2, chest=(1.2, 1.6), clav=3.0, head_breath=.8, sway_x=.009, sway_yaw=1.5, roll=1.2, head_yaw=2.5, head_lag=.25, hilt_lag=.12, hilt_follow=.85, tip_float=1.2, pommel_clear=.03)


def idle_two():
    s = open_job("idle_two"); D = s["duration"]; T = IDLE2; rec = sample("idle_two"); hist = {}
    def layer(t, fk, emp, chest0):
        e = env(t, D)
        b = e * math.sin(2 * math.pi * T["breath_cycles"] * t / D); bl = e * math.sin(2 * math.pi * T["breath_cycles"] * (t - .15) / D)
        w = e * math.sin(2 * math.pi * t / D); wl = e * math.sin(2 * math.pi * (t - T["head_lag"]) / D)
        hips = fk.pose.bones["Hips"]; hips.location += fk.data.bones["Hips"].matrix_local.to_3x3().inverted() @ Vector((T["sway_x"] * w, 0, -.002 * e * (1 - math.cos(2 * math.pi * t / D)) * .5)); bpy.context.view_layer.update()
        wr(fk, "Hips", "Y", T["roll"] * w); wr(fk, "Hips", "Z", T["sway_yaw"] * w); wr(fk, "Spine", "Y", -.8 * T["roll"] * w)
        wr(fk, "Spine1", "X", -T["chest"][0] * b); wr(fk, "Spine2", "X", -T["chest"][1] * b)
        wr(fk, "LeftShoulder", "Y", -T["clav"] * bl); wr(fk, "RightShoulder", "Y", T["clav"] * bl)
        wr(fk, "Neck", "X", .5 * T["head_breath"] * b); wr(fk, "Head", "X", .5 * T["head_breath"] * bl)
        wr(fk, "Head", "Z", T["head_yaw"] * wl - .5 * T["sway_yaw"] * w)
        # two-hand hilt rides the chest with lag (grip offsets on the hilt are untouched), tip floats after the breath
        ch = fk.pose.bones["Spine2"].head.copy(); hist[round(t, 4)] = ch - chest0
        lagd = hist.get(round(max(0., t - T["hilt_lag"]), 4), ch - chest0) * e
        h = emp.get("Hilt_Control")
        if h:
            p_ = h.matrix_basis.translation.copy(); tip = T["tip_float"] * e * math.sin(2 * math.pi * T["breath_cycles"] * (t - .3) / D)
            h.matrix_basis = Matrix.Translation(lagd * T["hilt_follow"] + Vector((0, -T["pommel_clear"] * e, 0))) @ Matrix.Translation(p_) @ Matrix.Rotation(math.radians(tip), 4, "X") @ Matrix.Translation(-p_) @ h.matrix_basis
        for sd in ("Left", "Right"):
            pl = emp.get(sd + "Arm_Pole")
            if pl and not pl.parent: pl.matrix_basis = Matrix.Translation(ch - chest0) @ pl.matrix_basis
    rekey("idle_two", rec, layer)
    s["er_layers"] = json.dumps(["idle_two: " + json.dumps(IDLE2)])
    return bake_export("idle_two")


def contact_probe(job, fr, path=None):
    from mathutils.bvhtree import BVHTree
    cm.open_tagged(Path(path) if path else OUT / (job + "_Blender_v1.blend"), P["owner"]); s = bpy.context.scene; s.frame_set(fr)
    m = _walk_tools(); body = m._body(); gid = {g.index: g.name for g in body.vertex_groups}; dg = bpy.context.evaluated_depsgraph_get()
    sw = [o for o in s.objects if o.get("review_attachment") and o.type == "MESH"][0]; e = sw.evaluated_get(dg); mm = e.to_mesh(); mm.calc_loop_triangles()
    bvh = BVHTree.FromPolygons([sw.matrix_world @ v.co for v in mm.vertices], [list(t.vertices) for t in mm.loop_triangles], all_triangles=True)
    ev = body.evaluated_get(dg); me = ev.to_mesh(); out = []
    for v in me.vertices:
        p = ev.matrix_world @ v.co; hit = bvh.find_nearest(p)
        if hit[3] < .004:
            g = max(body.data.vertices[v.index].groups, key=lambda x: x.weight); out.append((round(hit[3], 4), gid[g.group], [round(x, 3) for x in p], [round(x, 3) for x in (sw.matrix_world.inverted() @ hit[0])], [round(x, 3) for x in hit[1]]))
    ev.to_mesh_clear(); e.to_mesh_clear(); return sorted(out)[:12]


def pommel_series(job, path=None, step=30):
    cm.open_tagged(Path(path) if path else OUT / (job + "_Blender_v1.blend"), P["owner"]); s = bpy.context.scene; rig = bpy.data.objects["Knight_Deform"]; so = bpy.data.objects["ReviewWeaponSocket"]
    out = []
    for fr in range(0, s.frame_end + 1, step):
        s.frame_set(fr); pm = so.matrix_world @ Vector((0, 0, -.45)); hp = rig.matrix_world @ rig.pose.bones["RightUpLeg"].head; hb = rig.matrix_world @ rig.pose.bones["Hips"].head
        out.append((round(fr / s.render.fps, 2), [round(x, 3) for x in pm], round(pm.y - hp.y, 3), round(pm.y - hb.y, 3)))
    return out


# ------------------------------------------------------------- idle layer v2 rules (critic 2026-10-21) -------
# No endpoint fades: every channel is a whole number of cycles in the clip and zero at t=0/D (approved endpoints
# kept exactly). "Lag" is a delayed-peak harmonic (sin x - c sin 2x): still zero at the ends, peak later, and its
# speed at the seam differs from the lead channel, so channels are never all at rest across the wrap.
def wave(t, D, cycles, lag=0.):
    x = 2 * math.pi * cycles * t / D; return math.sin(x) - lag * math.sin(2 * x)


IDLE_R2 = dict(breath_cycles=2, chest=(2.0, 2.4), clav=9.0, sway_x=.005, sway_yaw=1.2, roll=1.0, head_counter=.3, head_yaw=2.2,
               head_lag=.45, chest_lag=.4, breath_lag=.2, wrist_scale=.25, wrist_lag=.3, arm_scale=.9, arm_lag=.35, tip_float=1.0, right_clav=.3)


def _idle_pose(fk, T, t, D, lagged=False):
    """Pose the additive idle layer on top of the base FK already set. lagged=True evaluates every channel with the
    wrist-lag harmonic (used to derive the delayed sword/arm follow)."""
    L = T["wrist_lag"] if lagged else 0.
    b = wave(t, D, T["breath_cycles"], L); bl = wave(t, D, T["breath_cycles"], max(L, T["breath_lag"]))
    w = wave(t, D, 1, L); wh = wave(t, D, 1, max(L, T["head_lag"])); wc = wave(t, D, 1, max(L, T["chest_lag"]))
    h0x = fk.pose.bones["Head"].head.x; hips0x = fk.pose.bones["Hips"].head.x
    hips = fk.pose.bones["Hips"]; hips.location += fk.data.bones["Hips"].matrix_local.to_3x3().inverted() @ Vector((T["sway_x"] * w, 0, 0)); bpy.context.view_layer.update()
    wr(fk, "Hips", "Y", T["roll"] * w); wr(fk, "Hips", "Z", T["sway_yaw"] * w); wr(fk, "Spine", "Y", -.8 * T["roll"] * w)
    # chest follows the pelvis sway with a lag: spine roll re-places the chest on the lagged waveform
    sp = fk.pose.bones["Spine"]; c2 = fk.pose.bones["Spine2"]; ls = (c2.head - sp.head).length or .13
    wr(fk, "Spine", "Y", math.degrees(math.atan2(T["sway_x"] * (wc - w), ls)))
    wr(fk, "Spine1", "X", -T["chest"][0] * b); wr(fk, "Spine2", "X", -T["chest"][1] * bl)
    # shrug: clavicles lift the shoulder joints; upper arms counter-rotate so the arms translate up instead of swinging
    wr(fk, "LeftShoulder", "Y", -T["clav"] * bl); wr(fk, "RightShoulder", "Y", T["right_clav"] * T["clav"] * bl)
    wr(fk, "LeftArm", "Y", T["clav"] * bl); wr(fk, "RightArm", "Y", -T["right_clav"] * T["clav"] * bl)
    # head steadier than chest: counter ~50% of the sway in world x (neck roll), lagged yaw drift
    head = fk.pose.bones["Head"].head.copy(); nk = fk.pose.bones["Neck"]; nl = (head - nk.head).length or .05
    want = h0x + (1 - T["head_counter"]) * T["sway_x"] * wh  # head x: half the sway, most lagged
    wr(fk, "Neck", "Y", math.degrees(math.atan2(want - fk.pose.bones["Head"].head.x, nl)))
    wr(fk, "Head", "Z", T["head_yaw"] * wh - .5 * T["sway_yaw"] * w); wr(fk, "Head", "X", .6 * bl)


def use_out(sub):
    global OUT
    OUT = P["out"] / sub; c.OUT = OUT; OUT.mkdir(parents=True, exist_ok=True); return str(OUT)


def idle_r2(job, T=None, name=None, sub="er_v2"):
    use_out(sub); T = dict(T or IDLE_R2); s = open_job(job); D = s["duration"]; fps = s.render.fps; rec = sample(job)
    fk = bpy.data.objects["Pose_Control_Rig"]; emp = {o.name: o for o in animated_controls(job)}; two = bool(s.get("two_hand"))
    fk.animation_data_clear()
    for o in emp.values(): o.animation_data_clear()
    prev = {}; stats = {"wristTravel": 0., "wristDeg": 0.}
    def setbase(bases, embs):
        for b in fk.pose.bones: b.matrix_basis = bases[b.name]
        for n, m in embs.items(): emp[n].matrix_basis = m
        bpy.context.view_layer.update()
    for fr, bases, embs, chest0 in rec:
        t = fr / fps
        setbase(bases, embs); Hb = fk.pose.bones["RightHand"].matrix.copy(); C0 = fk.pose.bones["Spine2"].matrix.copy(); LA0 = fk.pose.bones["LeftArm"].head.copy(); RA0 = fk.pose.bones["RightArm"].head.copy()
        _idle_pose(fk, T, t, D, lagged=True); Hl = fk.pose.bones["RightHand"].matrix.copy(); Cl = fk.pose.bones["Spine2"].matrix.copy()
        setbase(bases, embs); _idle_pose(fk, T, t, D)
        if not two:
            # sword wrist: 0.25x of the (lagged) chest-driven hand change, so the blade no longer pumps with breath
            k = T["wrist_scale"]; dq = Hb.to_quaternion().rotation_difference(Hl.to_quaternion())
            q = Quaternion((1, 0, 0, 0)).slerp(dq, k) @ Hb.to_quaternion(); dd_ = Hl.translation - Hb.translation; p_ = Hb.translation + Vector((dd_.x * k, dd_.y * k, dd_.z))  # full vertical (shoulder lift reach), 0.25x horizontal
            fk.pose.bones["RightHand"].matrix = Matrix.LocRotScale(p_, q, Hb.to_scale()); bpy.context.view_layer.update()
            stats["wristTravel"] = max(stats["wristTravel"], (p_ - Hb.translation).length); stats["wristDeg"] = max(stats["wristDeg"], math.degrees(Quaternion((1, 0, 0, 0)).slerp(dq, k).angle))
            tg = emp.get("LeftArm_Target")
            if tg:
                lift = fk.pose.bones["LeftArm"].head - LA0  # free hand rides the shrug fully, the chest sway with lag
                tg.matrix_basis = Matrix.Translation((Cl.translation - C0.translation) * T["arm_scale"] + Vector((0, 0, lift.z - (Cl.translation - C0.translation).z * T["arm_scale"]))) @ tg.matrix_basis
        else:
            h = emp.get("Hilt_Control")
            if h:
                d_ = (Cl.translation - C0.translation) * T["wrist_scale"]; p_ = h.matrix_basis.translation.copy(); tip = T["tip_float"] * wave(t, D, T["breath_cycles"], T["wrist_lag"])
                h.matrix_basis = Matrix.Translation(d_) @ Matrix.Translation(p_) @ Matrix.Rotation(math.radians(tip), 4, "X") @ Matrix.Translation(-p_) @ h.matrix_basis
                stats["wristTravel"] = max(stats["wristTravel"], d_.length); stats["wristDeg"] = max(stats["wristDeg"], abs(tip))
            for sd in ("Left", "Right"):
                pl = emp.get(sd + "Arm_Pole")
                if pl and not pl.parent: pl.matrix_basis = Matrix.Translation(fk.pose.bones["Spine2"].matrix.translation - C0.translation) @ pl.matrix_basis
        for b in fk.pose.bones: c.key(b, fr, prev)
        for o in emp.values(): c.key(o, fr, prev)
    for o in [fk, *emp.values()]: c.smooth(o)
    fk.animation_data.action.name = job + "_ER_V2R2_FK"
    s["er_layers"] = json.dumps([job + " r2 rules: " + json.dumps(T), stats])
    r = bake_export(job, name); r["stats"] = stats; return r


def idle_metrics(job, path=None, px_per_unit=410.):
    """Critic metrics: per-track seam speed ratio, lags (hips->chest->head x), shoulder lift vs chest, pelvis sway,
    sword centroid travel in side view (px at ~390 px figure)."""
    cm.open_tagged(Path(path) if path else OUT / (job + "_Blender_v1.blend"), P["owner"]); s = bpy.context.scene; rig = bpy.data.objects["Knight_Deform"]; so = bpy.data.objects["ReviewWeaponSocket"]
    W = lambda n: rig.matrix_world @ rig.pose.bones[n].head; E = s.frame_end; fps = s.render.fps; tr = {k: [] for k in ("hips", "chest", "head", "lsh", "rsh", "sword")}; ang = []
    for fr in range(0, E + 1):
        s.frame_set(fr); tr["hips"].append(W("Hips")); tr["chest"].append(W("Spine2")); tr["head"].append(W("Head")); tr["lsh"].append(W("LeftArm")); tr["rsh"].append(W("RightArm"))
        tr["sword"].append(so.matrix_world @ Vector((0, 0, .9))); ang.append(so.matrix_world.to_3x3().normalized() @ Vector((0, 0, 1)))
    out = {}
    for k, v in tr.items():
        sp = [(v[(i + 1) % E] - v[i]).length * fps for i in range(E)]; med = sorted(sp)[E // 2] or 1e-9
        seam = [sp[i % E] for i in range(-6, 6)]; out[k + "SeamSpeedRatio"] = round(sum(seam) / len(seam) / med, 2)
    def lag(a, b):  # frames b lags a (x channel), cyclic xcorr
        xa = [p.x for p in tr[a]][:E]; xb = [p.x for p in tr[b]][:E]; ma = sum(xa) / E; mb = sum(xb) / E
        best = max(range(-E // 4, E // 4), key=lambda L: sum((xa[i] - ma) * (xb[(i + L) % E] - mb) for i in range(E))); return best
    out["chestLagFramesVsHips"] = lag("hips", "chest"); out["headLagFramesVsHips"] = lag("hips", "head")
    px = lambda vals: round((max(vals) - min(vals)) * px_per_unit, 1)
    out["pelvisSwayPx"] = px([p.x for p in tr["hips"]]); out["chestSwayPx"] = px([p.x for p in tr["chest"]]); out["headSwayPx"] = px([p.x for p in tr["head"]])
    out["shoulderLiftRelChestPx"] = px([(l.z + r.z) / 2 - c_.z for l, r, c_ in zip(tr["lsh"], tr["rsh"], tr["chest"])])
    out["swordCentroidSideTravelPx"] = round(max((Vector((0, p.y, p.z)) - Vector((0, q.y, q.z))).length for p in tr["sword"] for q in tr["sword"][::5]) * px_per_unit, 1)
    out["swordPitchRangeDeg"] = round(max(math.degrees(a.angle(b)) for a in ang for b in ang[::5]), 2)
    out["fps"] = fps
    return out


def sword_profile(job, path=None, step=3):
    cm.open_tagged(Path(path) if path else APPROVED / (job + "_Blender_v1.blend"), P["owner"]); s = bpy.context.scene; so = bpy.data.objects["ReviewWeaponSocket"]; rig = bpy.data.objects["Knight_Deform"]
    fps = s.render.fps; pts = []
    for fr in range(0, s.frame_end + 1, step):
        s.frame_set(fr); pts.append((fr, so.matrix_world @ Vector((0, 0, 2.0)), so.matrix_world.translation.copy(), (rig.matrix_world @ rig.pose.bones["Hips"].head).copy()))
    out = []
    for a, b in zip(pts, pts[1:]):
        out.append((round(a[0] / fps, 3), round((b[1] - a[1]).length * fps / step, 2), [round(x, 2) for x in a[1]], [round(x, 3) for x in a[3]]))
    return {"fps": fps, "end": s.frame_end, "dur": s["duration"], "profile": out}


# ------------------------------------------------------------------------------------------ attacks --------
def bump(t, a, p, b):
    """Smooth 0->1->0 bump: rises a..p, falls p..b (zero outside)."""
    if t <= a or t >= b: return 0.
    return smooth01((t - a) / (p - a)) if t < p else smooth01((b - t) / (b - p))


def bump_hold(t, a, p, b, hold=0.):
    """Like bump, but holds the apex for `hold` s (heavy hang before the reversal); total window unchanged."""
    if hold <= 0: return bump(t, a, p, b)
    p1 = p - hold / 2; p2 = p + hold / 2
    if t <= a or t >= b: return 0.
    if t < p1: return smooth01((t - a) / (p1 - a))
    if t <= p2: return 1.
    return smooth01((b - t) / (b - p2))


def settle(t, t0, tau=.12):
    """Impact follow-through: 0 before t0, dips to 1 at t0+tau, decays smoothly (critically damped)."""
    if t <= t0: return 0.
    x = (t - t0) / tau; return x * math.exp(1 - x)


def hitstop_warp2(ti, h, T2, ease=.12, ease_back=.12):
    """Hit-stop with an eased restart: playback speed 1 -> 0 (hold h) -> ramps up to a catch-up rate r over `ease`
    -> eases back to 1 by T2. r is solved so the warped time meets real time at T2 (contact frame and clip end kept)."""
    def speed(t, r):
        if t < ti: return 1.
        if t < ti + h: return 0.
        if t < ti + h + ease: return r * smooth01((t - ti - h) / ease)
        if t < T2 - ease_back: return r
        if t < T2: return r + (1 - r) * smooth01((t - (T2 - ease_back)) / ease_back)
        return 1.
    def integ(r, upto, n=400):
        a_ = ti; dt = (upto - a_) / n; acc = 0.
        for i in range(n): acc += speed(a_ + (i + .5) * dt, r) * dt
        return acc
    lo, hi = 1., 6.
    for _ in range(50):
        r = .5 * (lo + hi)
        if integ(r, T2) < T2 - ti: lo = r
        else: hi = r
    r = .5 * (lo + hi)
    def w(t):
        if t < ti: return t
        if t >= T2: return t
        return ti + integ(r, t, 200)
    w.rate = r
    return w


def hitstop_warp3(ti, h, ease, c0, c1, ramp=.06, post=1.):
    """Hit-stop, eased restart at normal speed through the fast part, and the lost time caught up later inside a slow
    stretch [c0, c1] (eased in/out) so no post-hold frame step exceeds the approved clip's own fastest step."""
    def speed(t, r):
        if t < ti: return 1.
        if t < ti + h: return 0.
        if t < ti + h + ease: return post * smooth01((t - ti - h) / ease)
        if t < c0: return post
        if t < c0 + ramp: return post + (r - post) * smooth01((t - c0) / ramp)
        if t < c1 - ramp: return r
        if t < c1: return r + (1 - r) * smooth01((t - (c1 - ramp)) / ramp)
        return 1.
    def integ(r, upto, n=500):
        dt = (upto - ti) / n; return sum(speed(ti + (i + .5) * dt, r) * dt for i in range(n))
    lo, hi = 1., 8.
    for _ in range(50):
        r = .5 * (lo + hi)
        if integ(r, c1) < c1 - ti: lo = r
        else: hi = r
    r = .5 * (lo + hi)
    def w(t):
        if t < ti or t >= c1: return t
        return ti + integ(r, t, 250)
    w.rate = r
    return w


def hitstop_warp(ti, h, T2):
    def w(t):
        if t < ti: return t
        if t < ti + h: return ti
        if t < T2: return ti + (t - ti - h) * (T2 - ti) / (T2 - ti - h)
        return t
    return w


OVERHEAD = dict(ti=.955, h=.1, T2=1.6, ant=(.42, .72, .80), ant_drop=.03, ant_arch=12., ant_head=4., strike_lag_head=7.,
                ft_drop=.024, ft_pitch=6., ft_head=6., ft_tau=.13, arm_lag=.08, arm_ft=.04, rec_settle=(2.2, 2.45, 2.68), rec_drop=.006,
                heave=(1.05, 1.35, 2.1), heave_deg=2.6, heave_hz=1.6, ant_follow=1., ant_cock=18., ant_back=.025, rebound=6., jolt=.008)


def attack_v2(job, C, name=None, sub="er_v2", keep_wrist=True):
    use_out(sub); s = open_job(job); fps = s.render.fps; D = s["duration"]; two = bool(s.get("two_hand")); D_src = D
    if C.get("extend"):  # lengthen the clip (whole 150 Hz frames); the warp maps [0, D_new] onto the approved [0, D]
        s.frame_end = s.frame_end + round(C["extend"] * fps); D = s.frame_end / fps; s["duration"] = D
    for o in s.objects:
        if o.type == "MESH" and o.name.startswith("Icosphere") and len(o.data.vertices) < 100: o["export_body"] = False; o.hide_render = True; o.hide_set(True)
    if C.get("zones"): W = hitstop_warp4(C["ti"], C["h"], C.get("ease", .08), D, C["zones"], post=C.get("post_speed", 1.), post_dur=C.get("post_dur", 0.), D_src=D_src, ti_src=C.get("ti_src"), hang=C.get("hang"))
    elif C.get("catchup"): W = hitstop_warp3(C["ti"], C["h"], C.get("ease", .12), *C["catchup"], post=C.get("post_speed", 1.))
    elif C.get("eased", False): W = hitstop_warp2(C["ti"], C["h"], C["T2"], C.get("ease", .12), C.get("ease_back", .12))
    else: W = hitstop_warp(C["ti"], C["h"], C["T2"])
    global STEP
    _st = STEP; STEP = C.get("step", STEP)
    try: rec = sample(job, warp=lambda fr: W(fr / fps) * fps)
    finally: STEP = _st
    fk = bpy.data.objects["Pose_Control_Rig"]; emp = {o.name: o for o in animated_controls(job)}
    fk.animation_data_clear()
    for o in emp.values(): o.animation_data_clear()
    prev = {}; hist = {}; ti_end = C["ti"] + C["h"]
    for fr, bases, embs, chest0 in rec:
        t = fr / fps
        for b in fk.pose.bones: b.matrix_basis = bases[b.name]
        for n, m in embs.items(): emp[n].matrix_basis = m
        bpy.context.view_layer.update(); Hb = fk.pose.bones["RightHand"].matrix.copy(); C0 = fk.pose.bones["Spine2"].head.copy(); Cold = fk.pose.bones["Spine2"].matrix.copy()
        a = bump_hold(t, *C["ant"], C.get("ant_hold", 0.)); ft = settle(t, ti_end, C["ft_tau"]) * smooth01((C["T2"] + .4 - t) / .4); rs = bump(t, *C["rec_settle"])
        strike = bump(t, C["ant"][2] - .04, (C["ant"][2] + C["ti"]) / 2, C["ti"] + .02)
        jolt = C.get("jolt", 0) * settle(t, C["ti"] + C["h"], C.get("jolt_tau", .05))
        if C.get("sink"):  # impact sink: body drops within the contact frame and STAYS low (no rebound), fading out through the stand-up
            sd, sf0, sfd = C["sink"]; jolt -= sd * smooth01((t - C["ti"] + C.get("sink_lead", 0.)) / .04) * (1 - smooth01((t - sf0) / sfd))
        hips = fk.pose.bones["Hips"]; hips.location += fk.data.bones["Hips"].matrix_local.to_3x3().inverted() @ Vector((0, C.get("ant_back", 0) * a, -C["ant_drop"] * a - C["ft_drop"] * ft - C["rec_drop"] * rs + jolt)); bpy.context.view_layer.update()
        wr(fk, "Spine1", "X", -C["ant_arch"] * a * .5 + C["ft_pitch"] * ft * .5); wr(fk, "Spine2", "X", -C["ant_arch"] * a * .5 + C["ft_pitch"] * ft * .5)
        # head: holds back during the strike (lag), whips through after impact, settles
        wr(fk, "Head", "X", -C["ant_head"] * a - C["strike_lag_head"] * strike + C["ft_head"] * settle(t, ti_end + .04, C["ft_tau"]) * smooth01((C["T2"] + .4 - t) / .4))
        wr(fk, "LeftShoulder", "Y", -2.5 * ft); wr(fk, "RightShoulder", "Y", 2.5 * ft)
        if C.get("head_lag"):  # head trails the swing sideways into contact, whips through during the freeze, settles (neck offset: blade untouched)
            lag, whip, ax = C["head_lag"]; x = t - C["ti"]; dxh = 0.
            if -.14 < x <= 0: dxh = lag * smooth01((x + .14) / .14)
            elif 0 < x <= .1: dxh = lag + (whip - lag) * smooth01(x / .1)
            elif .1 < x < .45: dxh = whip * (1 - smooth01((x - .1) / .35))
            if dxh:
                nk = fk.pose.bones["Neck"]; nk.location += nk.bone.matrix_local.to_3x3().inverted() @ (fk.matrix_world.to_3x3().inverted() @ (Vector(ax) * dxh)); bpy.context.view_layer.update()
        if C.get("push"):  # impact push during the freeze: torso + helmet lean forward (pitch only: the grip ignores pitch)
            pb = bump(t, C["ti"] - .02, C["ti"] + C["h"], C["ti"] + C["h"] + (C["push"][2] if len(C["push"]) > 2 else .22)); wr(fk, "Spine1", "X", C["push"][0] * pb * .5); wr(fk, "Spine2", "X", C["push"][0] * pb * .5); wr(fk, "Head", "X", C["push"][1] * pb)
        endw = smooth01((C["T2"] + .4 - t) / .4)
        tf = 0.
        if C.get("ft_twist"):
            tau_ = C.get("ft_twist_tau", .14); x_ = (t - C.get("ft_twist_start", C["ti"] + C["h"])) / tau_
            tf = (x_ * math.exp(1 - x_) - C.get("ft_overshoot", 0.) * max(0., x_ - 1.5) * math.exp(1.5 - x_) * (x_ > 1.5)) if x_ > 0 else 0.
            if C.get("ft_twist_shape") == "exp": tf = (1 - math.exp(-x_)) if x_ > 0 else 0.  # decaying settle: biggest step first, no pop
        tw = -C.get("ant_twist", 0) * a + C.get("ft_twist", 0) * tf * endw
        if tw:  # coil before / over-rotation after the strike; split pelvis vs lumbar (chest+grip rigid above); head keeps the target
            hf = C.get("twist_hips", 0.)
            if hf: wr(fk, "Hips", "Z", hf * tw)
            wr(fk, "Spine", "Z", (1 - hf) * tw); wr(fk, "Head", "Z", -.7 * tw)
        if C.get("lead_shift"):  # weight onto the lead foot through the strike, back by recovery
            ls_ = (bump_hold(t, C["ant"][2], C["ti"] + C["h"] / 2, C["T2"] + .3, C["h"]) if C.get("zones") else bump(t, C["ant"][2], C["ti"] + C["h"], C["T2"] + .3)); hips = fk.pose.bones["Hips"]
            hips.location += fk.data.bones["Hips"].matrix_local.to_3x3().inverted() @ (Vector(C["lead_shift"]) * ls_); bpy.context.view_layer.update()
        if C.get("exhale"):  # ONE slow exhale-and-recover over the hold: single raised-cosine (one direction flip), neck sink + chest slump + clavicle drop
            b0, b1, dz, sp_deg, cl_deg = C["exhale"][:5]; hz_ = C["exhale"][5] if len(C["exhale"]) > 5 else 0.
            fade = C.get("exhale_fade", 0.)
            if b0 < t < b1 + fade:
                g = (smooth01((t - b0) / (b1 - b0)) if t < b1 else 1 - smooth01((t - b1) / fade)) if fade else .5 * (1 - math.cos(2 * math.pi * (t - b0) / (b1 - b0)))
                nk = fk.pose.bones["Neck"]; nk.location += nk.bone.matrix_local.to_3x3().inverted() @ (fk.matrix_world.to_3x3().inverted() @ Vector((0, 0, dz * g))); bpy.context.view_layer.update()
                wr(fk, "Spine2", "X", sp_deg * g); wr(fk, "LeftShoulder", "Z", cl_deg * g); wr(fk, "RightShoulder", "Z", -cl_deg * g)
                if hz_: hb_ = fk.pose.bones["Hips"]; hb_.location += fk.data.bones["Hips"].matrix_local.to_3x3().inverted() @ Vector((0, 0, hz_ * g)); bpy.context.view_layer.update()
        if C.get("breath"):  # two heavy breaths in the hold: (1-cos) inhale rises the head (neck lift + chest arch) and shrugs the clavicles
            b0, b1, nb, dz, sp_deg, cl_deg = C["breath"]
            if b0 < t < b1:
                g = .5 * (1 - math.cos(2 * math.pi * nb * (t - b0) / (b1 - b0)))
                nk = fk.pose.bones["Neck"]; nk.location += nk.bone.matrix_local.to_3x3().inverted() @ (fk.matrix_world.to_3x3().inverted() @ Vector((0, 0, dz * g))); bpy.context.view_layer.update()
                wr(fk, "Spine2", "X", sp_deg * g); wr(fk, "LeftShoulder", "Z", cl_deg * g); wr(fk, "RightShoulder", "Z", -cl_deg * g); wr(fk, "LeftShoulder", "Y", cl_deg * g); wr(fk, "RightShoulder", "Y", -cl_deg * g)
        if C.get("heave"):  # post-impact exertion: two heavy breaths in the hold, chest/shoulders heave
            hv = bump(t, *C["heave"]) * math.sin(2 * math.pi * C["heave_hz"] * (t - C["heave"][0]))
            wr(fk, "Spine2", "X", -C["heave_deg"] * hv); wr(fk, "LeftShoulder", "Y", -2 * C["heave_deg"] * hv); wr(fk, "RightShoulder", "Y", 2 * C["heave_deg"] * hv)
        if keep_wrist and not two:  # sword path = approved (hit-stop warped) except the wind-up, where it cocks back with the body
            Hl = fk.pose.bones["RightHand"].matrix.copy(); kf = C.get("ant_follow", 0) * a
            q = Hb.to_quaternion().slerp(Hl.to_quaternion(), kf); Hn = Matrix.LocRotScale(Hb.translation.lerp(Hl.translation, kf), q, Hb.to_scale())
            if C.get("ant_cock"):  # extra wind-up: the arm/sword cocks further back around the shoulder, then releases
                sh_ = fk.pose.bones["RightArm"].head.copy(); Hn = Matrix.Translation(sh_) @ Matrix.Rotation(math.radians(-C["ant_cock"] * a), 4, "X") @ Matrix.Translation(-sh_) @ Hn
            if C.get("rebound"):  # impact: the blade kicks back up off the ground and settles
                rb = settle(t, C["ti"] + C["h"], .07) * smooth01((C["T2"] - t) / .3); p0 = Hn.translation.copy()
                Hn = Matrix.Translation(p0) @ Matrix.Rotation(math.radians(-C["rebound"] * rb), 4, "X") @ Matrix.Translation(-p0) @ Hn
            if C.get("kick"):  # impact kick: the hand (and so the whole blade) lifts vertically and drops back - tip rises, no skid
                Hn = Matrix.Translation((0, 0, C["kick"] * settle(t, C["ti"] + C["h"], C.get("kick_tau", .07)))) @ Hn
            fk.pose.bones["RightHand"].matrix = Hn; bpy.context.view_layer.update()
        if two:  # two-hand: the grip rides the chest (coil, drop, follow-through) rigidly; approved grip offsets untouched
            Dfull = fk.pose.bones["Spine2"].matrix @ Cold.inverted(); qd = Dfull.to_quaternion(); qz = Quaternion((qd.w, 0, 0, qd.z)); qz.normalize()
            C1 = fk.pose.bones["Spine2"].head.copy()  # grip follows chest translation + yaw only (pitch layers must not swing the blade)
            Dm = Matrix.Translation(C1) @ qz.to_matrix().to_4x4() @ Matrix.Translation(-C0) if C.get("yaw_only_grip", True) else Dfull
            hl = emp.get("Hilt_Control")
            if hl: hl.matrix_basis = Dm @ hl.matrix_basis
            for sd in ("Left", "Right"):
                pl = emp.get(sd + "Arm_Pole")
                if pl and not pl.parent: pl.matrix_basis = Matrix.Translation(Dm.translation + (Dm.to_3x3() @ Vector()) ) @ pl.matrix_basis if False else Dm @ pl.matrix_basis
        ch = fk.pose.bones["Spine2"].head.copy(); hist[fr] = ch - C0
        tg = emp.get("LeftArm_Target")
        if tg and not two:
            lf = max(0, fr - round(C["arm_lag"] * fps)); lag_ = hist.get(lf, hist.get(min(hist, key=lambda k_: abs(k_ - lf))))
            tg.matrix_basis = Matrix.Translation(lag_ + Vector((0, -C["arm_ft"] * settle(t, ti_end + .03, .15), -C["arm_ft"] * .5 * settle(t, ti_end + .03, .15)))) @ tg.matrix_basis
        for b in fk.pose.bones: c.key(b, fr, prev)
        for o in emp.values(): c.key(o, fr, prev)
    for o in [fk, *emp.values()]: c.smooth(o)
    fk.animation_data.action.name = job + "_ER_V2_FK"
    s["er_layers"] = json.dumps([job + ": " + json.dumps(C)])
    return bake_export(job, name)


def small_meshes(path):
    cm.open_tagged(Path(path), P["owner"]); s = bpy.context.scene; s.frame_set(0); out = []
    for o in s.objects:
        if o.type == "MESH" and len(o.data.vertices) < 2000:
            bb = [o.matrix_world @ Vector(c_) for c_ in o.bound_box]
            out.append({"name": o.name, "verts": len(o.data.vertices), "parent": o.parent.name if o.parent else None, "ptype": o.parent_type, "pbone": o.parent_bone,
                        "export_body": bool(o.get("export_body")), "mods": [(m.type, getattr(m, "object", None) and m.object.name) for m in o.modifiers],
                        "groups": [g.name for g in o.vertex_groups][:6], "bbmin": [round(min(v[i] for v in bb), 3) for i in range(3)], "bbmax": [round(max(v[i] for v in bb), 3) for i in range(3)],
                        "hide_render": o.hide_render, "materials": [m.name for m in o.data.materials if m]})
    return out


# ------------------------------------------------------------------------------- idle round 3 (critic) -------
# True time delays: each follower copies its leader's recorded delta from an earlier frame (cyclic), and the
# delayed-minus-undelayed difference fades over 0.2 s at the ends only, so the approved endpoints stay exact while
# every channel keeps moving through the seam (all lead channels are sines, fastest at t=0).
IDLE_R3 = dict(breath_cycles=2, chest=(1.0, 1.2), clav=7.0, right_clav=.35, sway_x=.005, sway_yaw=1.0, roll=.8,
               chest_delay=.07, head_delay=.14, shrug_delay=.07, hand_delay=.17, wrist_delay=.25, wrist_scale=.25,
               head_follow=.5, head_base_counter=.5, head_yaw=1.8, arm_scale=.9, tip_float=.8, end_fade=.2)


def idle_r3(job, T=None, name=None, sub="er_v2r3"):
    use_out(sub); T = dict(T or IDLE_R3); s = open_job(job); D = s["duration"]; fps = s.render.fps; rec = sample(job)
    for o in s.objects:  # stray 2-unit Icosphere flagged export_body in the approved scenes: not body geometry
        if o.type == "MESH" and o.name.startswith("Icosphere") and len(o.data.vertices) < 100: o["export_body"] = False; o.hide_render = True; o.hide_set(True)
    fk = bpy.data.objects["Pose_Control_Rig"]; emp = {o.name: o for o in animated_controls(job)}; two = bool(s.get("two_hand"))
    w1 = 2 * math.pi / D; w2 = 2 * math.pi * T["breath_cycles"] / D
    def ef(t): return smooth01(t / T["end_fade"]) * smooth01((D - t) / T["end_fade"])
    def dsin(w, t, tau): return math.sin(w * t) + (math.sin(w * (t - tau)) - math.sin(w * t)) * ef(t)
    def setbase(bases, embs):
        for b in fk.pose.bones: b.matrix_basis = bases[b.name]
        for n, m in embs.items(): emp[n].matrix_basis = m
        bpy.context.view_layer.update()
    hb = []; cb = []; lsb = []; ltb = []
    for fr, bases, embs, chest0 in rec:
        setbase(bases, embs); hb.append(fk.pose.bones["Head"].head.copy()); cb.append(fk.pose.bones["Spine2"].head.copy()); lsb.append(fk.pose.bones["LeftArm"].head.copy())
        ltb.append(emp["LeftArm_Target"].matrix_world.translation.copy() if "LeftArm_Target" in emp else Vector())
    m_off = sum(((h - c_).x for h, c_ in zip(hb, cb))) / len(hb); m_hz = sum((a.z - b.z for a, b in zip(ltb, lsb))) / len(ltb)
    P1 = []
    for k, (fr, bases, embs, chest0) in enumerate(rec):
        t = fr / fps; setbase(bases, embs)
        H0 = fk.pose.bones["RightHand"].matrix.copy(); C0 = fk.pose.bones["Spine2"].head.copy(); LS0 = fk.pose.bones["LeftArm"].head.copy()
        sw = math.sin(w1 * t); cw = dsin(w1, t, T["chest_delay"]); b = math.sin(w2 * t); sh = dsin(w2, t, T["shrug_delay"])
        hips = fk.pose.bones["Hips"]; hips.location += fk.data.bones["Hips"].matrix_local.to_3x3().inverted() @ Vector((T["sway_x"] * sw, 0, 0)); bpy.context.view_layer.update()
        wr(fk, "Hips", "Y", T["roll"] * sw); wr(fk, "Hips", "Z", T["sway_yaw"] * sw)
        sp = fk.pose.bones["Spine"]; ls = (fk.pose.bones["Spine2"].head - sp.head).length or .13
        wr(fk, "Spine", "Y", -.8 * T["roll"] * sw + math.degrees(math.atan2(T["sway_x"] * (cw - sw), ls)))
        wr(fk, "Spine1", "X", -T["chest"][0] * b); wr(fk, "Spine2", "X", -T["chest"][1] * b)
        wr(fk, "LeftShoulder", "Y", -T["clav"] * sh); wr(fk, "RightShoulder", "Y", T["right_clav"] * T["clav"] * sh)
        wr(fk, "LeftArm", "Y", T["clav"] * sh); wr(fk, "RightArm", "Y", -T["right_clav"] * T["clav"] * sh)
        P1.append(dict(t=t, C=fk.pose.bones["Spine2"].head - C0, LS=fk.pose.bones["LeftArm"].head - LS0, Hl=fk.pose.bones["RightHand"].matrix.copy(), H0=H0,
                       basebody={b_.name: b_.matrix_basis.copy() for b_ in fk.pose.bones}))
    N = len(rec); step_t = (rec[1][0] - rec[0][0]) / fps
    def back(k, tau):
        return (k - round(tau / step_t)) % (N - 1)
    fk.animation_data_clear()
    for o in emp.values(): o.animation_data_clear()
    prev = {}; stats = {"wristTravel": 0.}
    for k, (fr, bases, embs, chest0) in enumerate(rec):
        t = fr / fps; e = ef(t); R1 = P1[k]; setbase(bases, embs)
        for b_ in fk.pose.bones: b_.matrix_basis = R1["basebody"][b_.name]
        bpy.context.view_layer.update()
        cxd = P1[back(k, T["head_delay"])]["C"].x; cxd = R1["C"].x + (cxd - R1["C"].x) * e
        dev = (hb[k] - cb[k]).x - m_off
        kd = back(k, T["head_delay"])
        if T.get("head_delay_base"):  # head follows the whole chest x (base + layer) with the delay
            tgt = cb[kd].x + m_off + T["head_follow"] * P1[kd]["C"].x
            wx = hb[k].x + (tgt - hb[k].x) * e + (1 - e) * T["head_follow"] * R1["C"].x
        else:
            wx = hb[k].x + T["head_follow"] * cxd - T["head_base_counter"] * dev * e
        wy = hb[k].y
        nk = fk.pose.bones["Neck"]; hd = fk.pose.bones["Head"]; nl = (hd.head - nk.head).length or .05
        dx = wx - hd.head.x; dy = wy - hd.head.y
        wr(fk, "Neck", "Y", math.degrees(math.atan2(dx, nl))); wr(fk, "Neck", "X", -math.degrees(math.atan2(dy, nl)))
        wr(fk, "Head", "X", math.degrees(math.atan2(dy, nl)))
        wr(fk, "Head", "Z", T["head_yaw"] * dsin(w1, t, T["head_delay"]))
        if not two:
            kk = back(k, T["wrist_delay"]); Hl = P1[kk]["Hl"]; H0d = P1[kk]["H0"]; H0 = R1["H0"]
            dq = H0d.to_quaternion().rotation_difference(Hl.to_quaternion()); dp = Hl.translation - H0d.translation
            dq0 = H0.to_quaternion().rotation_difference(R1["Hl"].to_quaternion()); dp0 = R1["Hl"].translation - H0.translation
            dq = dq0.slerp(dq, e); dp = dp0.lerp(dp, e); ksc = T["wrist_scale"]
            q = Quaternion((1, 0, 0, 0)).slerp(dq, ksc) @ H0.to_quaternion(); pp = H0.translation + Vector((dp.x * ksc, dp.y * ksc, dp.z))
            fk.pose.bones["RightHand"].matrix = Matrix.LocRotScale(pp, q, H0.to_scale()); bpy.context.view_layer.update(); stats["wristTravel"] = max(stats["wristTravel"], (pp - H0.translation).length)
            tg = emp.get("LeftArm_Target")
            if tg:
                kh = back(k, T["hand_delay"]); d_ = P1[kh]["LS"]; dd = R1["LS"].lerp(d_, e)
                cxh = R1["C"].lerp(P1[kh]["C"], e)
                # free hand: base hang below the base shoulder (its own vertical wobble removed), then the shoulder's lift delayed
                zfix = (lsb[k].z + m_hz - ltb[k].z) * e
                tg.matrix_basis = Matrix.Translation(Vector((cxh.x * T["arm_scale"], cxh.y * T["arm_scale"], dd.z + zfix))) @ tg.matrix_basis
        else:
            h = emp.get("Hilt_Control")
            if h:
                d_ = R1["C"].lerp(P1[back(k, T["wrist_delay"])]["C"], e) * T["wrist_scale"]; p_ = h.matrix_basis.translation.copy()
                tip = T["tip_float"] * dsin(w2, t, T["wrist_delay"] + .1)
                d_ += Vector((T.get("grip_float", 0) * .7 * math.sin(w1 * t), 0, T.get("grip_float", 0) * math.sin(w2 * t + .9) - T.get("grip_float", 0) * math.sin(.9) * (1 - e)))
                h.matrix_basis = Matrix.Translation(d_) @ Matrix.Translation(p_) @ Matrix.Rotation(math.radians(tip), 4, "X") @ Matrix.Translation(-p_) @ h.matrix_basis
                stats["wristTravel"] = max(stats["wristTravel"], d_.length)
            for sd in ("Left", "Right"):
                pl = emp.get(sd + "Arm_Pole")
                if pl and not pl.parent: pl.matrix_basis = Matrix.Translation(R1["C"]) @ pl.matrix_basis
        for b_ in fk.pose.bones: c.key(b_, fr, prev)
        for o in emp.values(): c.key(o, fr, prev)
    for o in [fk, *emp.values()]: c.smooth(o)
    fk.animation_data.action.name = job + "_ER_V2R3_FK"
    s["er_layers"] = json.dumps([job + " r3 rules: " + json.dumps(T), stats])
    r = bake_export(job, name); r["stats"] = stats; return r


def idle_metrics2(job, path=None, px=410., fps_r=30.):
    """Tracked-point metrics sampled at the render rate: seam speed ratio per track, cross-correlation lags
    (head vs chest x, free hand vs left shoulder z) in render frames, head fore-aft vs back plate, vertical heave."""
    cm.open_tagged(Path(path) if path else OUT / (job + "_Blender_v1.blend"), P["owner"]); s = bpy.context.scene; rig = bpy.data.objects["Knight_Deform"]; so = bpy.data.objects["ReviewWeaponSocket"]
    W = lambda n: rig.matrix_world @ rig.pose.bones[n].head; D = s["duration"]; n = round(D * fps_r); tr = {}
    names = {"hips": "Hips", "chest": "Spine2", "head": "Head", "lsh": "LeftArm", "rsh": "RightArm", "lhand": "LeftHand", "lknee": "LeftLeg", "rknee": "RightLeg"}
    for i in range(n + 1):
        ff = i / fps_r * s.render.fps; s.frame_set(int(ff), subframe=ff - int(ff))
        for k, b in names.items(): tr.setdefault(k, []).append(W(b))
        tr.setdefault("grip", []).append(so.matrix_world.translation.copy()); tr.setdefault("swordmid", []).append(so.matrix_world @ Vector((0, 0, .9)))
        tr.setdefault("back", []).append(rig.matrix_world @ rig.pose.bones["Spine1"].matrix @ Vector((0, .0, .08)))
    out = {}
    for k, v in tr.items():
        sp = [(v[(i + 1) % n] - v[i]).length * fps_r for i in range(n)]; med = sorted(sp)[n // 2] or 1e-9
        seam = [sp[i % n] for i in range(-2, 2)]; out[k] = round(sum(seam) / len(seam) / med, 2)
    def xc(a, b, ax):
        xa = [getattr(p, ax) for p in tr[a]][:n]; xb = [getattr(p, ax) for p in tr[b]][:n]; ma = sum(xa) / n; mb = sum(xb) / n
        return -max(range(-10, 11), key=lambda L: sum((xa[i] - ma) * (xb[(i - L) % n] - mb) for i in range(n)))  # + = b lags a
    rng = lambda v, ax: round((max(getattr(p, ax) for p in v) - min(getattr(p, ax) for p in v)) * px, 1)
    return {"seamSpeedRatio": out, "headLagVsChestX_frames": xc("chest", "head", "x"), "handLagVsShoulderZ_frames": xc("lsh", "lhand", "z"),
            "headForeAftPx": rng(tr["head"], "y"), "backForeAftPx": rng(tr["back"], "y"), "headSidePx": rng(tr["head"], "x"), "chestSidePx": rng(tr["chest"], "x"),
            "verticalHeavePx": rng(tr["head"], "z"), "shoulderLiftRelChestPx": round((max((l.z + r.z) / 2 - c_.z for l, r, c_ in zip(tr["lsh"], tr["rsh"], tr["chest"])) - min((l.z + r.z) / 2 - c_.z for l, r, c_ in zip(tr["lsh"], tr["rsh"], tr["chest"]))) * px, 1),
            "swordMidTravelPx": round(max((Vector((0, p.y, p.z)) - Vector((0, q.y, q.z))).length for p in tr["swordmid"] for q in tr["swordmid"]) * px, 1)}


def find_shard(path, x=.264, z=.87, r=.03, fr=0):
    import bmesh
    cm.open_tagged(Path(path), P["owner"]); s = bpy.context.scene; s.frame_set(fr); dg = bpy.context.evaluated_depsgraph_get(); out = []
    for o in s.objects:
        if o.type != "MESH" or o.hide_render: continue
        ev = o.evaluated_get(dg); me = ev.to_mesh(); mw = ev.matrix_world
        hits = [v.index for v in me.vertices if abs((mw @ v.co).x - x) < r and abs((mw @ v.co).z - z) < r]
        if hits:
            bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table(); seen = {hits[0]}; st = [hits[0]]
            while st:
                vv = bm.verts[st.pop()]
                for e_ in vv.link_edges:
                    w_ = e_.other_vert(vv).index
                    if w_ not in seen: seen.add(w_); st.append(w_)
            gid = {g.index: g.name for g in o.vertex_groups}; wsum = {}
            for i in seen:
                for g in o.data.vertices[i].groups: wsum[gid.get(g.group, "?")] = wsum.get(gid.get(g.group, "?"), 0) + g.weight
            pts = [mw @ me.vertices[i].co for i in seen]
            out.append({"obj": o.name, "hits": len(hits), "islandVerts": len(seen), "centroid": [round(sum(p[j] for p in pts) / len(pts), 3) for j in range(3)], "weights": sorted(((round(v, 1), k) for k, v in wsum.items()), reverse=True)[:6], "firstVert": hits[0]})
            bm.free()
        ev.to_mesh_clear()
    return out


def stray_islands(path, max_verts=40, min_dist=.04):
    """Small mesh islands whose rest position is far from the bone segment they are weighted to."""
    import bmesh
    cm.open_tagged(Path(path), P["owner"]); s = bpy.context.scene; m = _walk_tools(); body = m._body(); rig = bpy.data.objects["Knight_Deform"]
    bm = bmesh.new(); bm.from_mesh(body.data); bm.verts.ensure_lookup_table(); isl = [-1] * len(bm.verts); n = 0; mem = {}
    for v in bm.verts:
        if isl[v.index] >= 0: continue
        st = [v]; isl[v.index] = n; mem[n] = [v.index]
        while st:
            x_ = st.pop()
            for e_ in x_.link_edges:
                y_ = e_.other_vert(x_)
                if isl[y_.index] < 0: isl[y_.index] = n; mem[n].append(y_.index); st.append(y_)
        n += 1
    gid = {g.index: g.name for g in body.vertex_groups}; out = []
    for k, ids in mem.items():
        if len(ids) > max_verts: continue
        ws = {}
        for i in ids:
            for g in body.data.vertices[i].groups: ws[gid[g.group]] = ws.get(gid[g.group], 0) + g.weight
        dom = max(ws, key=ws.get); b = rig.data.bones[dom]; a_ = rig.matrix_world @ b.head_local; z_ = rig.matrix_world @ b.tail_local
        cen = sum((body.matrix_world @ body.data.vertices[i].co for i in ids), Vector()) / len(ids)
        u = (z_ - a_); tt = max(0, min(1, (cen - a_).dot(u) / u.length_squared)); d = (cen - (a_ + u * tt)).length
        if d > min_dist: out.append({"island": k, "verts": len(ids), "dominant": dom, "restCentroid": [round(c_, 3) for c_ in cen], "distToBone": round(d, 3), "ids": ids[:8]})
    bm.free(); return {"islands": n, "stray": sorted(out, key=lambda r: -r["distToBone"])[:15]}


def fix_strays(min_dist=.2):
    """Tabard-hem shards (tiny islands at shin height) are weighted to the right forearm in the approved body, so they
    fly with the arm (the white shard beside the helmet). Re-weight every small island that sits > min_dist from its
    dominant arm/hand bone at rest to Hips, like the rest of the tabard. Approved files are not touched."""
    import bmesh
    m = _walk_tools(); body = m._body(); rig = bpy.data.objects["Knight_Deform"]; gid = {g.index: g.name for g in body.vertex_groups}
    bm = bmesh.new(); bm.from_mesh(body.data); bm.verts.ensure_lookup_table(); seen = [False] * len(bm.verts); fixed = []
    hips = body.vertex_groups.get("Hips")
    for v in bm.verts:
        if seen[v.index]: continue
        st = [v]; seen[v.index] = True; ids = [v.index]
        while st:
            x_ = st.pop()
            for e_ in x_.link_edges:
                y_ = e_.other_vert(x_)
                if not seen[y_.index]: seen[y_.index] = True; ids.append(y_.index); st.append(y_)
        if len(ids) > 60: continue
        ws = {}
        for i in ids:
            for g in body.data.vertices[i].groups: ws[gid[g.group]] = ws.get(gid[g.group], 0) + g.weight
        if not ws: continue
        dom = max(ws, key=ws.get)
        if not any(k_ in dom for k_ in ("Arm", "Hand", "Shoulder")): continue
        b = rig.data.bones[dom]; a_ = b.head_local; z_ = b.tail_local; u = z_ - a_
        cen = sum((body.data.vertices[i].co for i in ids), Vector()) / len(ids)
        tt = max(0, min(1, (cen - a_).dot(u) / u.length_squared)); d = (cen - (a_ + u * tt)).length
        if d > min_dist:
            for i in ids:
                for g in list(body.data.vertices[i].groups): body.vertex_groups[g.group].remove([i])
                hips.add([i], 1.0, "REPLACE")
            fixed.append((len(ids), dom, round(d, 3)))
    bm.free(); bpy.context.scene["stray_fix"] = json.dumps(fixed)
    return {"islands": len(fixed), "verts": sum(f_[0] for f_ in fixed)}


# ------------------------------------------------------------------------------- idle round 4 (critic) -------
# No end blend: every layer is a smooth whole-cycle curve. Delayed channels use
#   S(t) = x(t - tau) - x(-tau) * h(t),  h(t) = (1 + cos(2 pi t / D)) / 2
# i.e. the delayed copy minus a full-cycle raised-cosine offset, so it is zero at t = 0/D (approved endpoints kept)
# while position, velocity and acceleration stay continuous across the wrap. Control curves get Cycles modifiers so
# Bezier handles are computed cyclically (no flat end tangents).
IDLE_R4 = dict(breath_cycles=2, chest=(1.0, 1.2), clav=5.0, right_clav=.35, sway_x=.005, sway_y=.0015, sway_yaw=1.0, roll=.8,
               chest_delay=.07, head_delay=.16, shrug_delay=.05, hand_delay=.21, wrist_delay=.25, wrist_scale=.25,
               head_follow=.65, head_yaw=1.8, arm_scale=.9, tip_float=.8, grip_float=0., head_z_delay=.12, seam_smooth=.3)


def _cyclic(objs):
    for o in objs:
        if not (o.animation_data and o.animation_data.action): continue
        for fc in c.curves(o.animation_data.action):
            if not any(m_.type == "CYCLES" for m_ in fc.modifiers): fc.modifiers.new("CYCLES")
            fc.update()


def idle_r4(job, T=None, name=None, sub="er_v2r4"):
    use_out(sub); T = dict(T or IDLE_R4); s = open_job(job); D = s["duration"]; fps = s.render.fps; rec = sample(job)
    if T.get("seam_smooth", .3): seam_smooth(rec, fps, T.get("seam_smooth", .3))
    for o in s.objects:
        if o.type == "MESH" and o.name.startswith("Icosphere") and len(o.data.vertices) < 100: o["export_body"] = False; o.hide_render = True; o.hide_set(True)
    fk = bpy.data.objects["Pose_Control_Rig"]; emp = {o.name: o for o in animated_controls(job)}; two = bool(s.get("two_hand"))
    assert not fk.data.bones["Neck"].use_connect, "Neck must accept a location offset"
    w1 = 2 * math.pi / D; w2 = 2 * math.pi * T["breath_cycles"] / D
    h = lambda t: .5 * (1 + math.cos(2 * math.pi * t / D))
    S = lambda w, t, tau: math.sin(w * (t - tau)) + math.sin(w * tau) * h(t)  # delayed sine, zero at 0/D, smooth cyclic
    N = len(rec); step_t = (rec[1][0] - rec[0][0]) / fps
    def back(k, tau): return (k - round(tau / step_t)) % (N - 1)
    def dly(arr, k, tau):  # cyclic delayed copy of a recorded vector/float series minus the raised-cosine offset
        t = rec[k][0] / fps; v0 = arr[back(0, tau)] - arr[0]
        return arr[back(k, tau)] - v0 * h(t)
    def setbase(bases, embs):
        for b in fk.pose.bones: b.matrix_basis = bases[b.name]
        for n, m in embs.items(): emp[n].matrix_basis = m
        bpy.context.view_layer.update()
    hb = []; cb = []; lsb = []; ltb = []
    for fr, bases, embs, chest0 in rec:
        setbase(bases, embs); hb.append(fk.pose.bones["Head"].head.copy()); cb.append(fk.pose.bones["Spine2"].head.copy()); lsb.append(fk.pose.bones["LeftArm"].head.copy())
        ltb.append(emp["LeftArm_Target"].matrix_world.translation.copy() if "LeftArm_Target" in emp else Vector())
    m_off = sum((hb[i] - cb[i] for i in range(N - 1)), Vector()) / (N - 1); m_hz = sum((ltb[i].z - lsb[i].z for i in range(N - 1))) / (N - 1)
    # pass 1: body layers on the base; record chest/shoulder/hand deltas
    P1 = []
    for k, (fr, bases, embs, chest0) in enumerate(rec):
        t = fr / fps; setbase(bases, embs)
        H0 = fk.pose.bones["RightHand"].matrix.copy(); C0 = fk.pose.bones["Spine2"].head.copy(); LS0 = fk.pose.bones["LeftArm"].head.copy()
        sw = math.sin(w1 * t); cw = S(w1, t, T["chest_delay"]); b = math.sin(w2 * t); sh = S(w2, t, T["shrug_delay"]); fy = math.sin(w2 * t + 0.)
        hips = fk.pose.bones["Hips"]; hips.location += fk.data.bones["Hips"].matrix_local.to_3x3().inverted() @ Vector((T["sway_x"] * sw, T["sway_y"] * fy, 0)); bpy.context.view_layer.update()
        wr(fk, "Hips", "Y", T["roll"] * sw); wr(fk, "Hips", "Z", T["sway_yaw"] * sw)
        sp = fk.pose.bones["Spine"]; ls = (fk.pose.bones["Spine2"].head - sp.head).length or .13
        wr(fk, "Spine", "Y", -.8 * T["roll"] * sw + math.degrees(math.atan2(T["sway_x"] * (cw - sw), ls)))
        wr(fk, "Spine1", "X", -T["chest"][0] * b); wr(fk, "Spine2", "X", -T["chest"][1] * b)
        wr(fk, "LeftShoulder", "Y", -T["clav"] * sh); wr(fk, "RightShoulder", "Y", T["right_clav"] * T["clav"] * sh)
        wr(fk, "LeftArm", "Y", T["clav"] * sh); wr(fk, "RightArm", "Y", -T["right_clav"] * T["clav"] * sh)
        P1.append(dict(C=fk.pose.bones["Spine2"].head - C0, Cabs=fk.pose.bones["Spine2"].head.copy(), LS=fk.pose.bones["LeftArm"].head - LS0, Hl=fk.pose.bones["RightHand"].matrix.copy(), H0=H0,
                       basebody={b_.name: b_.matrix_basis.copy() for b_ in fk.pose.bones}))
    Cabs = [p["Cabs"] for p in P1]; Cd = [p["C"] for p in P1]; LSd = [p["LS"] for p in P1]
    hand_dp = [p["Hl"].translation - p["H0"].translation for p in P1]
    hand_rv = []
    for p in P1:
        q = p["H0"].to_quaternion().rotation_difference(p["Hl"].to_quaternion()); hand_rv.append(q.axis * q.angle if q.angle > 1e-9 else Vector())
    fk.animation_data_clear()
    for o in emp.values(): o.animation_data_clear()
    prev = {}; stats = {"wristTravel": 0.}
    for k, (fr, bases, embs, chest0) in enumerate(rec):
        t = fr / fps; R1 = P1[k]; setbase(bases, embs)
        for b_ in fk.pose.bones: b_.matrix_basis = R1["basebody"][b_.name]
        bpy.context.view_layer.update()
        # head: trails the whole chest (base + layer) by head_delay in x/y; z via neck offset, delayed chest heave
        tgt = dly(Cabs, k, T["head_delay"]) + m_off; tgt0_err = (Cabs[back(0, T["head_delay"])] + m_off) - hb[0]
        want = tgt - (tgt0_err - (dly(Cabs, 0, T["head_delay"]) + m_off - hb[0])) * 0  # dly already zeroes the offset at t=0
        want = Vector((hb[k].x + (want.x - hb[k].x), hb[k].y + (want.y - hb[k].y), 0))
        want.x = hb[k].x + (dly(Cabs, k, T["head_delay"]).x + m_off.x - hb[k].x) * 1.0
        want.y = hb[k].y + (dly(Cabs, k, T["head_delay"]).y + m_off.y - hb[k].y) * 1.0
        corr = (Cabs[0] + m_off - hb[0])  # constant mismatch of the mean-offset model at t=0 -> remove with h(t)
        want.x -= corr.x * h(t); want.y -= corr.y * h(t)
        nk = fk.pose.bones["Neck"]; hd = fk.pose.bones["Head"]; nl = (hd.head - nk.head).length or .05
        dx = want.x - hd.head.x; dy = want.y - hd.head.y
        wr(fk, "Neck", "Y", math.degrees(math.atan2(dx, nl))); wr(fk, "Neck", "X", -math.degrees(math.atan2(dy, nl))); wr(fk, "Head", "X", math.degrees(math.atan2(dy, nl)))
        dz = (dly(Cabs, k, T["head_z_delay"]).z - Cabs[k].z)  # vertical: head rides the chest heave late
        nb = fk.pose.bones["Neck"]; nb.location += nb.bone.matrix_local.to_3x3().inverted() @ (fk.matrix_world.to_3x3().inverted() @ Vector((0, 0, dz)))
        bpy.context.view_layer.update()
        wr(fk, "Head", "Z", T["head_yaw"] * S(w1, t, T["head_delay"]))
        if not two:
            ksc = T["wrist_scale"]; rv = dly(hand_rv, k, T["wrist_delay"]); dp = dly(hand_dp, k, T["wrist_delay"]); H0 = R1["H0"]
            q = (Quaternion(rv.normalized(), rv.length * ksc) if rv.length > 1e-9 else Quaternion()) @ H0.to_quaternion()
            pp = H0.translation + Vector((dp.x * ksc, dp.y * ksc, dp.z))
            fk.pose.bones["RightHand"].matrix = Matrix.LocRotScale(pp, q, H0.to_scale()); bpy.context.view_layer.update(); stats["wristTravel"] = max(stats["wristTravel"], (pp - H0.translation).length)
            tg = emp.get("LeftArm_Target")
            if tg:
                dd = dly(LSd, k, T["hand_delay"]); cxh = dly(Cd, k, T["hand_delay"])
                zfix = (lsb[k].z + m_hz - ltb[k].z) - (lsb[0].z + m_hz - ltb[0].z) * h(t)
                tg.matrix_basis = Matrix.Translation(Vector((cxh.x * T["arm_scale"], cxh.y * T["arm_scale"], dd.z + zfix))) @ tg.matrix_basis
        else:
            hl = emp.get("Hilt_Control")
            if hl:
                d_ = dly(Cd, k, T["wrist_delay"]) * T["wrist_scale"]; p_ = hl.matrix_basis.translation.copy()
                tip = T["tip_float"] * S(w2, t, T["wrist_delay"] + .1)
                gf = T["grip_float"]; d_ += Vector((gf * .7 * math.sin(w1 * t), 0, gf * math.sin(w2 * t)))
                hl.matrix_basis = Matrix.Translation(d_) @ Matrix.Translation(p_) @ Matrix.Rotation(math.radians(tip), 4, "X") @ Matrix.Translation(-p_) @ hl.matrix_basis
                stats["wristTravel"] = max(stats["wristTravel"], d_.length)
            for sd in ("Left", "Right"):
                pl = emp.get(sd + "Arm_Pole")
                if pl and not pl.parent: pl.matrix_basis = Matrix.Translation(R1["C"]) @ pl.matrix_basis
        for b_ in fk.pose.bones: c.key(b_, fr, prev)
        for o in emp.values(): c.key(o, fr, prev)
    for o in [fk, *emp.values()]: c.smooth(o)
    _cyclic([fk, *emp.values()])
    fk.animation_data.action.name = job + "_ER_V2R4_FK"
    s["er_layers"] = json.dumps([job + " r4 rules: " + json.dumps(T), stats])
    r = bake_export(job, name); r["stats"] = stats; return r


def seam_accel(job, path=None, fps_r=30., px=410.):
    """Render-rate tracked seam check: per-track acceleration at the wrap vs loop median, and velocity direction
    reversal across f(n-3)..f3 (cosine of consecutive velocity vectors)."""
    cm.open_tagged(Path(path) if path else OUT / (job + "_Blender_v1.blend"), P["owner"]); s = bpy.context.scene; rig = bpy.data.objects["Knight_Deform"]; so = bpy.data.objects["ReviewWeaponSocket"]
    D = s["duration"]; n = round(D * fps_r); tr = {}
    for i in range(n):
        ff = i / fps_r * s.render.fps; s.frame_set(int(ff), subframe=ff - int(ff))
        tr.setdefault("sword", []).append(so.matrix_world @ Vector((0, 0, .9))); tr.setdefault("pommel", []).append(so.matrix_world @ Vector((0, 0, -.45)))
        tr.setdefault("rhand", []).append(rig.matrix_world @ rig.pose.bones["RightHand"].head); tr.setdefault("lhand", []).append(rig.matrix_world @ rig.pose.bones["LeftHand"].head)
        tr.setdefault("head", []).append(rig.matrix_world @ rig.pose.bones["Head"].head); tr.setdefault("chest", []).append(rig.matrix_world @ rig.pose.bones["Spine2"].head)
        tr.setdefault("hips", []).append(rig.matrix_world @ rig.pose.bones["Hips"].head); tr.setdefault("lknee", []).append(rig.matrix_world @ rig.pose.bones["LeftLeg"].head)
    out = {}
    for k, v in tr.items():
        vel = [v[(i + 1) % n] - v[i] for i in range(n)]; acc = [(vel[i] - vel[i - 1]).length for i in range(n)]; med = sorted(acc)[n // 2] or 1e-9
        seam = max(acc[i % n] for i in range(-3, 4)); cosmin = min((vel[i % n].normalized().dot(vel[(i + 1) % n].normalized()) if vel[i % n].length > 1e-7 and vel[(i + 1) % n].length > 1e-7 else 1.) for i in range(-3, 3))
        spd = [x.length for x in vel]; smed = sorted(spd)[n // 2] or 1e-9
        out[k] = {"seamAccelOverMedian": round(seam / med, 2), "minVelCosAcrossSeam": round(cosmin, 2), "seamSpeedOverMedian": round(sum(spd[i % n] for i in range(-2, 2)) / 4 / smed, 2)}
    def xc(a, b, ax):
        xa = [getattr(p, ax) for p in tr[a]]; xb = [getattr(p, ax) for p in tr[b]]; ma = sum(xa) / n; mb = sum(xb) / n
        return -max(range(-10, 11), key=lambda L: sum((xa[i] - ma) * (xb[(i - L) % n] - mb) for i in range(n)))
    rng = lambda v, ax: round((max(getattr(p, ax) for p in v) - min(getattr(p, ax) for p in v)) * px, 1)
    out["lags"] = {"headVsChest_x": xc("chest", "head", "x"), "headVsChest_y": xc("chest", "head", "y"), "headVsChest_z": xc("chest", "head", "z"), "lhandVsChest_z": xc("chest", "lhand", "z")}
    out["ranges"] = {"chestZ": rng(tr["chest"], "z"), "headZ": rng(tr["head"], "z"), "headY": rng(tr["head"], "y")}
    return out



def seam_smooth(rec, fps, w=.3):
    """The approved idles end on flat (auto-clamped) tangents, a velocity kink at the wrap. Rebuild every sampled
    base channel inside +-w of the seam with two cubic Hermite pieces that keep the exact value at t=0/D and use a
    shared centred slope there, C1-joined to the original curve at +-w. Endpoint poses are unchanged."""
    N = len(rec); E = N - 1; step = (rec[1][0] - rec[0][0]) / fps; m = max(2, round(w / step))
    def chan(get):
        vals = [get(r) for r in rec]
        return vals
    def herm(p0, p1, m0, m1, u, hh):
        h00 = 2 * u ** 3 - 3 * u ** 2 + 1; h10 = u ** 3 - 2 * u ** 2 + u; h01 = -2 * u ** 3 + 3 * u ** 2; h11 = u ** 3 - u ** 2
        return p0 * h00 + m0 * hh * h10 + p1 * h01 + m1 * hh * h11
    def fix(series):  # series: list of floats over k=0..E (series[E]==series[0])
        x = list(series); cyc = lambda k: x[k % E]
        sl0 = (cyc(1) - cyc(-1)) / (2 * step) * 0 + (cyc(m) - cyc(-m)) / (2 * m * step)  # centred slope across the wrap
        smR = (cyc(m + 1) - cyc(m - 1)) / (2 * step); smL = (cyc(-m + 1) - cyc(-m - 1)) / (2 * step); hh = m * step
        for j in range(1, m):
            u = j / m
            x[j] = herm(cyc(0), cyc(m), sl0, smR, u, hh)
            x[E - j] = herm(cyc(-m), cyc(0), smL, sl0, 1 - u, hh)
        return x
    def smooth_mats(get, setm):
        mats = [get(r) for r in rec]
        locs = [M.to_translation() for M in mats]; qs = [M.to_quaternion() for M in mats]; scl = [M.to_scale() for M in mats]
        for i in range(1, N):
            if qs[i].dot(qs[i - 1]) < 0: qs[i] = -qs[i]
        L = [fix([v[a] for v in locs]) for a in range(3)]; Q = [fix([q[a] for q in qs]) for a in range(4)]
        for k in range(N):
            q = Quaternion((Q[0][k], Q[1][k], Q[2][k], Q[3][k])); q.normalize()
            setm(k, Matrix.LocRotScale(Vector((L[0][k], L[1][k], L[2][k])), q, scl[k]))
    names = list(rec[0][1].keys())
    for n in names: smooth_mats(lambda r, n=n: r[1][n], lambda k, M, n=n: rec[k][1].__setitem__(n, M))
    for n in list(rec[0][2].keys()): smooth_mats(lambda r, n=n: r[2][n], lambda k, M, n=n: rec[k][2].__setitem__(n, M))
    return m


SWEEP = dict(ti=.55, h=.08, T2=.88, ant=(.16, .36, .42), ant_drop=.02, ant_arch=3., ant_head=0., strike_lag_head=3.,
             ft_drop=.012, ft_pitch=3., ft_head=3., ft_tau=.12, arm_lag=.08, arm_ft=0., rec_settle=(1.2, 1.33, 1.44), rec_drop=.006,
             ant_twist=10., ft_twist=8., ft_twist_tau=.14, lead_shift=(.012, -.01, 0.), ant_hold=.06, jolt=.008)


THRUST = dict(ti=.80, h=.08, T2=1.4, ant=(.28, .51, .60), ant_hold=.06, ant_drop=.022, ant_arch=4., ant_head=0., strike_lag_head=3.,
              ft_drop=.015, ft_pitch=4., ft_head=3., ft_tau=.13, arm_lag=.08, arm_ft=0., rec_settle=(1.95, 2.1, 2.27), rec_drop=.006,
              ant_twist=9., ft_twist=5., ft_twist_tau=.14, lead_shift=(.006, -.022, 0.), jolt=.008,
              heave=(.95, 1.15, 1.48), heave_deg=2.2, heave_hz=2.0, ant_back=.015)


SWEEP2 = dict(ti=.48, h=.08, T2=.9, eased=True, ease=.12, ease_back=.12, catchup=(.90, 1.32, .08), post_speed=.8, ant=(.16, .36, .42), ant_hold=.06, ant_drop=.035, ant_arch=4., ant_head=0.,
              strike_lag_head=4., ft_drop=.025, ft_pitch=5., ft_head=6., ft_tau=.12, arm_lag=.08, arm_ft=0., rec_settle=(1.15, 1.3, 1.44), rec_drop=.02,
              ant_twist=10., ft_twist=14., ft_twist_tau=.22, ft_overshoot=.35, twist_hips=.5, lead_shift=(.03, -.02, 0.), jolt=0., ft_twist_start=.74)
THRUST2 = dict(ti=.80, h=.08, T2=1.4, eased=True, ease=.12, ease_back=.15, catchup=(.95, 1.45, .08), post_speed=.85, ant=(.28, .51, .60), ant_hold=.06, ant_drop=.035, ant_arch=5., ant_head=0.,
               strike_lag_head=4., ft_drop=.025, ft_pitch=5., ft_head=6., ft_tau=.13, arm_lag=.08, arm_ft=0., rec_settle=(1.95, 2.1, 2.27), rec_drop=.02,
               ant_twist=9., ft_twist=12., ft_twist_tau=.2, ft_overshoot=.3, twist_hips=.5, lead_shift=(.015, -.035, 0.), jolt=.02, ft_twist_start=.92,
               heave=(.95, 1.15, 1.48), heave_deg=3.0, heave_hz=2.0, ant_back=.03)


def view_steps(path, fps_r=20., res=720, ortho=2.6, view=(2.8, -4, 1.), t0=0., t1=None, head_window=None):
    """Projected (camera-plane) per-frame steps in px for blade centroid, chest and hips at the sheet rate; optional
    blade-to-head clearance inside a time window (evaluated meshes)."""
    from mathutils.bvhtree import BVHTree
    cm.open_tagged(Path(path), P["owner"]); s = bpy.context.scene; rig = bpy.data.objects["Knight_Deform"]; so = bpy.data.objects["ReviewWeaponSocket"]
    d = Vector(view).normalized(); up = Vector((0, 0, 1)); rgt = d.cross(up).normalized(); upv = rgt.cross(d).normalized(); px = res / ortho
    t1 = t1 if t1 is not None else s["duration"]; n = round((t1 - t0) * fps_r); P_ = {"blade": [], "chest": [], "hips": []}
    for i in range(n + 1):
        ff = (t0 + i / fps_r) * s.render.fps; s.frame_set(int(ff), subframe=ff - int(ff))
        for k, p in (("blade", so.matrix_world @ Vector((0, 0, .9))), ("chest", rig.matrix_world @ rig.pose.bones["Spine2"].head), ("hips", rig.matrix_world @ rig.pose.bones["Hips"].head)):
            P_[k].append(Vector((p.dot(rgt), p.dot(upv))) * px)
    out = {}
    for k, v in P_.items():
        out[k + "Pts"] = [(round(q.x, 1), round(q.y, 1)) for q in v]; st = [(v[i + 1] - v[i]).length for i in range(n)]; out[k + "MaxStep"] = round(max(st), 1); out[k + "Steps"] = [round(x, 1) for x in st]
    if head_window:
        m = _walk_tools(); body = m._body(); gid = {g.index: g.name for g in body.vertex_groups}
        head = [v.index for v in body.data.vertices if max(v.groups, key=lambda g: g.weight, default=None) and gid[max(v.groups, key=lambda g: g.weight).group] in ("Head", "Neck")]
        sw = [o for o in s.objects if o.get("review_attachment") and o.type == "MESH"]; best = (9, 0)
        for fr in range(round(head_window[0] * s.render.fps), round(head_window[1] * s.render.fps) + 1, 2):
            s.frame_set(fr); dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh()
            verts = []; tris = []
            for o in sw:
                e = o.evaluated_get(dg); mm = e.to_mesh(); mm.calc_loop_triangles(); b0 = len(verts); verts += [o.matrix_world @ v.co for v in mm.vertices]; tris += [[b0 + i for i in t.vertices] for t in mm.loop_triangles]; e.to_mesh_clear()
            bvh = BVHTree.FromPolygons(verts, tris, all_triangles=True); dmin = min(bvh.find_nearest(ev.matrix_world @ me.vertices[i].co)[3] for i in head[::2])
            if dmin < best[0]: best = (round(dmin, 4), round(fr / s.render.fps, 3))
            ev.to_mesh_clear()
        out["bladeHeadMinInWindow"] = best
    return out



def hitstop_warp4(ti, h, ease, D, zones, post=1., post_dur=0., ease_back=.06, dt=1/1500., D_src=None, ti_src=None, hang=None):
    """Hit-stop + catch-up defined in SOURCE time: ds/dt = base(t) * (1 + k*Z(s)); Z = smooth windows over source stretches
    where the approved motion is slow, so the lost time is recovered there (never in fast stretches). k solved so s(D)=D."""
    def hf(t):  # optional pre-contact hang: output window [ha, hb] at speed hs with smooth ramps
        if not hang: return 1.
        ha, hb, hs, rp = hang
        if t <= ha - rp or t >= hb + rp: return 1.
        if t < ha: return 1 - (1 - hs) * smooth01((t - ha + rp) / rp)
        if t > hb: return hs + (1 - hs) * smooth01((t - hb) / rp)
        return hs
    m_ = 3000; area = sum(hf((i + .5) * ti / m_) for i in range(m_)) * ti / m_
    pre = (ti_src / area) if ti_src else 1.  # pre-contact gain: source contact lands exactly on the (frame-aligned) freeze
    def base(t):
        if t < ti: return pre * hf(t)
        if t < ti + h: return 0.
        x = t - ti - h
        if x < ease: return post * smooth01(x / ease)
        x -= ease
        if x < post_dur: return post
        x -= post_dur
        if x < ease_back: return post + (1 - post) * smooth01(x / ease_back)
        return 1.
    def Z(s):
        z = 0.
        for a, b, wgt in zones:
            r_ = min(.03, (b - a) / 3)
            if a < s < b: z += wgt * smooth01((s - a) / r_) * smooth01((b - s) / r_)
        return z
    D_src = D_src if D_src is not None else D
    n = int(round(D / dt))
    def run(k):
        s = 0.; out = [0.]
        for i in range(n):
            t = (i + .5) * dt; s += base(t) * (1 + k * Z(s)) * dt; out.append(s)
        return out
    lo, hi = -.95, 20.
    for _ in range(60):
        k = .5 * (lo + hi)
        if run(k)[-1] < D_src: lo = k
        else: hi = k
    tab = run(.5 * (lo + hi)); err = tab[-1] - D_src
    tab = [v - err * (i / n) for i, v in enumerate(tab)]; tab[-1] = D_src
    def w(t):
        if t <= 0: return t
        if t >= D: return D_src + (t - D)
        x = t / dt; i = int(x); f = x - i
        return tab[i] * (1 - f) + tab[min(i + 1, n)] * f
    w.k = .5 * (lo + hi)
    return w

COMPACT = dict(ti=.35, h=.067, T2=.70, eased=True, ease=.1, catchup=(.62, .95, .06), post_speed=.8, ant=(.06, .2, .27), ant_hold=.04,
               ant_drop=.03, ant_arch=4., ant_head=0., strike_lag_head=4., ft_drop=.02, ft_pitch=4., ft_head=5., ft_tau=.1, arm_lag=.08, arm_ft=0.,
               rec_settle=(.88, .99, 1.08), rec_drop=.015, ant_twist=8., ft_twist=10., ft_twist_tau=.16, ft_overshoot=.3, twist_hips=.5,
               ft_twist_start=.52, lead_shift=(.025, -.015, 0.), jolt=0.)

COMPACT2 = dict(COMPACT, zones=[(.50, .63, 1.), (.86, 1.085, 1.)], ease=.06, post_speed=.9, post_dur=.06)
COMPACT3 = dict(COMPACT2, post_speed=.82, post_dur=.08)
SWEEP3 = dict(SWEEP2, zones=[(.68, .95, 1.), (1.22, 1.455, .7)], ease=.1, post_speed=.75, post_dur=.06, ft_overshoot=.8)
SWEEP3B = dict(SWEEP3, ti=.53)


def tip_local(s=None):
    """Blade tip in socket-local coords: the weapon vertex farthest from the socket origin (rest)."""
    s = s or bpy.context.scene; so = bpy.data.objects["ReviewWeaponSocket"]; inv = so.matrix_world.inverted(); best = (0, Vector())
    for o in s.objects:
        if o.get("review_attachment") and o.type == "MESH":
            for v in o.data.vertices:
                q = inv @ (o.matrix_world @ v.co)
                if q.length > best[0]: best = (q.length, q.copy())
    return best[1]


def tip_steps(path, fps_r=20., res=720, ortho=2.1, views=(("front", (0, -4, .5)), ("side", (4, 0, .5)), ("tq", (2.8, -4, 1.))), t0=0., t1=None, hi=120.):
    """Projected blade-TIP steps per view at the sheet rate, plus front-view centreline crossings (tip x vs chest x)
    sampled at `hi` Hz with tip speed there, to place hit-stops at contact."""
    cm.open_tagged(Path(path), P["owner"]); s = bpy.context.scene; rig = bpy.data.objects["Knight_Deform"]; so = bpy.data.objects["ReviewWeaponSocket"]
    s.frame_set(0); tl = tip_local(s); t1 = t1 if t1 is not None else s["duration"]; px = res / ortho; out = {}
    def proj(view, p):
        d = Vector(view).normalized(); rgt = d.cross(Vector((0, 0, 1))).normalized(); upv = rgt.cross(d).normalized(); return Vector((p.dot(rgt), p.dot(upv))) * px
    def at(t):
        ff = t * s.render.fps; s.frame_set(int(ff), subframe=ff - int(ff)); return so.matrix_world @ tl, rig.matrix_world @ rig.pose.bones["Spine2"].head
    n = round((t1 - t0) * fps_r); pts = [at(t0 + i / fps_r) for i in range(n + 1)]
    for nm, v in views:
        q = [proj(v, a) for a, _ in pts]; out[nm] = [round((q[i + 1] - q[i]).length, 1) for i in range(n)]
        out[nm + "Pts"] = [(round(p.x), round(p.y)) for p in q]
    m = round((t1 - t0) * hi); fr = [at(t0 + i / hi) for i in range(m + 1)]; fv = (0, -4, .5)
    dx = [proj(fv, a).x - proj(fv, c).x for a, c in fr]; sp = [(proj(fv, fr[min(i + 1, m)][0]) - proj(fv, fr[max(i - 1, 0)][0])).length * hi / 2 / fps_r for i in range(m + 1)]
    out["cross"] = [(round(t0 + i / hi, 3), round(sp[i], 1)) for i in range(m) if dx[i] * dx[i + 1] < 0]
    k = max(range(m + 1), key=lambda i: sp[i]); out["fastest"] = (round(t0 + k / hi, 3), round(sp[k], 1))
    return out
SWEEP3C = dict(SWEEP3, ti=.55)
SWEEP4 = dict(SWEEP3, ti=.55, post_speed=.6, post_dur=.12, zones=[(.72, .95, 1.)], extend=.1)
SWEEP5 = dict(SWEEP4, post_speed=.45, extend=.15, step=1)
SWEEP6 = dict(SWEEP5, ft_twist_start=.86, T2=1.05)
SWEEP7 = dict(SWEEP6, post_dur=.16)
SWEEP8 = dict(SWEEP7, ft_twist=10., ft_twist_tau=.18)


def _front_body(fk, px, view=(0, -4, .5)):
    d = Vector(view).normalized(); rgt = d.cross(Vector((0, 0, 1))).normalized(); upv = rgt.cross(d).normalized(); W = fk.matrix_world
    pr = lambda p: Vector(((W @ p).dot(rgt), (W @ p).dot(upv))) * px
    b = fk.pose.bones; return pr(b["Head"].tail).y, (pr(b["LeftArm"].head) - pr(b["RightArm"].head)).x


def breath_probe(job="thrust", t=1.2, ortho=2.6, res=720):
    """Front-view px deltas of head-top and shoulder width for candidate breath controls (FK rig, one frame)."""
    open_job(job); s = bpy.context.scene; fk = bpy.data.objects["Pose_Control_Rig"]; px = res / ortho; out = {}
    tests = {"base": lambda: None,
             "clavX6": lambda: (wr(fk, "LeftShoulder", "X", 6), wr(fk, "RightShoulder", "X", 6)),
             "clavY6": lambda: (wr(fk, "LeftShoulder", "Y", -6), wr(fk, "RightShoulder", "Y", 6)),
             "clavZ6": lambda: (wr(fk, "LeftShoulder", "Z", 6), wr(fk, "RightShoulder", "Z", -6)),
             "sp2X3": lambda: wr(fk, "Spine2", "X", 3), "sp2Z3": lambda: wr(fk, "Spine2", "Z", 3),
             "neck1cm": lambda: setattr(fk.pose.bones["Neck"], "location", fk.pose.bones["Neck"].location + fk.pose.bones["Neck"].bone.matrix_local.to_3x3().inverted() @ (fk.matrix_world.to_3x3().inverted() @ Vector((0, 0, .01))))}
    for k, f in tests.items():
        c.at(t * s.render.fps); bpy.context.view_layer.update(); f(); bpy.context.view_layer.update(); out[k] = [round(x, 2) for x in _front_body(fk, px)]
    b = out["base"]; return {k: [round(v[0] - b[0], 2), round(v[1] - b[1], 2)] for k, v in out.items()}


def mesh_clear(path, groups, t0, t1, step=3):
    """Min distance (m) from evaluated body verts whose dominant group is in `groups` to the weapon mesh, over [t0, t1]."""
    from mathutils.bvhtree import BVHTree
    cm.open_tagged(Path(path), P["owner"]); s = bpy.context.scene
    m = _walk_tools(); body = m._body(); gid = {g.index: g.name for g in body.vertex_groups}
    idx = [v.index for v in body.data.vertices if v.groups and gid[max(v.groups, key=lambda g: g.weight).group] in groups]
    sw = [o for o in s.objects if o.get("review_attachment") and o.type == "MESH"]; best = (9, 0)
    for fr in range(round(t0 * s.render.fps), round(t1 * s.render.fps) + 1, step):
        s.frame_set(fr); dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); verts = []; tris = []
        for o in sw:
            e = o.evaluated_get(dg); mm = e.to_mesh(); mm.calc_loop_triangles(); b0 = len(verts); verts += [o.matrix_world @ v.co for v in mm.vertices]; tris += [[b0 + i for i in t.vertices] for t in mm.loop_triangles]; e.to_mesh_clear()
        bvh = BVHTree.FromPolygons(verts, tris, all_triangles=True); dmin = min(bvh.find_nearest(ev.matrix_world @ me.vertices[i].co)[3] for i in idx)
        if dmin < best[0]: best = (round(dmin, 4), round(fr / s.render.fps, 3))
        ev.to_mesh_clear()
    return best


def body_track(path, fps_r=15., ortho=2.6, res=720, t0=0., t1=None, view=(0, -4, .5)):
    """Front-view head-top y and shoulder width (px) per sheet frame, on the baked deform rig."""
    cm.open_tagged(Path(path), P["owner"]); s = bpy.context.scene; rig = bpy.data.objects["Knight_Deform"]; px = res / ortho
    t1 = t1 if t1 is not None else s["duration"]; n = round((t1 - t0) * fps_r); ht = []; sw = []
    for i in range(n + 1):
        ff = (t0 + i / fps_r) * s.render.fps; s.frame_set(int(ff), subframe=ff - int(ff)); a, b = _front_body(rig, px, view); ht.append(round(a, 1)); sw.append(round(b, 1))
    return {"headTop": ht, "shoulderW": sw}


THRUST3 = dict(THRUST2, catchup=None, zones=[(.95, 1.5, 1.)], ease=.02, post_speed=.4, post_dur=.2, jolt_tau=.1, ft_twist_start=.88, ft_twist_tau=.15,
               ant=(.26, .47, .66), ant_hold=.05, heave=None, breath=(1.0, 1.6, 2, .012, -3., 8.), step=1)
THRUST4 = dict(THRUST3, h=.067, ft_twist=6., ft_twist_shape="exp", ft_twist_tau=.13, jolt=.012, jolt_tau=.13, ant=(.26, .46, .70), breath=(1.0, 1.75, 2, .02, -4., 8.), push=(3., 4.))
THRUST5 = dict(THRUST4, breath=(.95, 1.55, 2, .022, -4., 8.))


def head_chest(path, fps_r=20., ortho=2.1, res=720, t0=0., t1=None):
    """Front-view head-minus-chest x offset (px) per sheet frame on the baked deform rig."""
    cm.open_tagged(Path(path), P["owner"]); s = bpy.context.scene; rig = bpy.data.objects["Knight_Deform"]; px = res / ortho
    d = Vector((0, -4, .5)).normalized(); rgt = d.cross(Vector((0, 0, 1))).normalized(); t1 = t1 if t1 is not None else s["duration"]; out = []
    for i in range(round((t1 - t0) * fps_r) + 1):
        ff = (t0 + i / fps_r) * s.render.fps; s.frame_set(int(ff), subframe=ff - int(ff)); W = rig.matrix_world; b = rig.pose.bones
        out.append(round(((W @ b["Head"].head) - (W @ b["Spine2"].head)).dot(rgt) * px, 1))
    return out


COMPACT4 = dict(COMPACT3, ti=.40, h=.067, zones=[(.50, .62, 1.)], extend=.1, ease=.03, post_speed=.55, post_dur=.08, step=1, push=(3., 4.),
                head_lag=(-.025, .015, (1., 0., 0.)), ft_twist_start=.62, T2=.75, rec_settle=(.98, 1.09, 1.18))
COMPACT5 = dict(COMPACT4, ti_src=.408)
COMPACT6 = dict(COMPACT5, T2=.65, rec_settle=(.80, .92, 1.04))


def tip_extent(path, views=(("front", (0, -4, .5)), ("side", (4, 0, .5)), ("tq", (2.8, -4, 1.))), cy=-.25, cz=.85, ortho=2.1, res=720, fps_r=30.):
    """Per view: blade-tip and head-top projected extents (px from frame centre; frame half = res/2) over the clip."""
    cm.open_tagged(Path(path), P["owner"]); s = bpy.context.scene; so = bpy.data.objects["ReviewWeaponSocket"]; rig = bpy.data.objects["Knight_Deform"]
    s.frame_set(0); tl = tip_local(s); px = res / ortho; c0 = Vector((0, cy, cz)); out = {}
    pts = []
    for i in range(round(s["duration"] * fps_r) + 1):
        ff = i / fps_r * s.render.fps; s.frame_set(int(ff), subframe=ff - int(ff)); pts.append((so.matrix_world @ tl, rig.matrix_world @ rig.pose.bones["Head"].tail, rig.matrix_world @ rig.pose.bones["LeftFoot"].head))
    for nm, v in views:
        d = Vector(v).normalized(); rgt = d.cross(Vector((0, 0, 1))).normalized(); upv = rgt.cross(d).normalized()
        q = [Vector(((p - c0).dot(rgt), (p - c0).dot(upv))) * px for p, _, _ in pts]
        out[nm] = {"x": [round(min(a.x for a in q)), round(max(a.x for a in q))], "y": [round(min(a.y for a in q)), round(max(a.y for a in q))],
                   "worst_t": round(max(range(len(q)), key=lambda i: max(abs(q[i].x), abs(q[i].y))) / fps_r, 3)}
    return out


THRUST6 = dict(THRUST5, breath=None, exhale=(.95, 1.55, -.006, 2., -3.), push=(1.5, 2., .4), jolt=.006, jolt_tau=.2)
THRUST7 = dict(THRUST6, ft_drop=.006, ft_tau=.25, ft_pitch=2., ft_head=3.)
THRUST8 = dict(THRUST7, exhale=(.95, 1.5, -.007, 2., -3.), exhale_fade=.4)
THRUST9 = dict(THRUST8, post_speed=1., post_dur=0., ease=1e-4)
THRUST10 = dict(THRUST8, post_speed=.8, post_dur=.08, ease=1e-4)
COMPACT7 = dict(COMPACT6, ti=.45, ti_src=.43, h=.05, post_speed=1., post_dur=0., ease=1e-4, extend=.0667, ft_twist=4., ft_overshoot=0., lead_shift=(.01, -.015, 0.), head_lag=(-.035, .02, (1., 0., 0.)))
COMPACT8 = dict(COMPACT7, extend=.1, ft_drop=.008, ft_twist=2., lead_shift=(0., -.015, 0.))


def blade_prof(path, fps_r=20., t0=0., t1=None):
    """Per sheet frame: blade-axis rotation step (deg), tip world z (m) and tip world xy (m)."""
    cm.open_tagged(Path(path), P["owner"]); s = bpy.context.scene; so = bpy.data.objects["ReviewWeaponSocket"]
    s.frame_set(0); tl = tip_local(s); t1 = t1 if t1 is not None else s["duration"]; out = {"t": [], "rot": [], "tipz": [], "tipxy": []}; prev = None
    for i in range(round((t1 - t0) * fps_r) + 1):
        t = t0 + i / fps_r; ff = t * s.render.fps; s.frame_set(int(ff), subframe=ff - int(ff)); m = so.matrix_world; tip = m @ tl; ax = (tip - m.translation).normalized()
        out["t"].append(round(t, 3)); out["tipz"].append(round(tip.z, 3)); out["tipxy"].append((round(tip.x, 3), round(tip.y, 3)))
        out["rot"].append(round(math.degrees(ax.angle(prev)), 1) if prev is not None else 0.); prev = ax
    return out
OVERHEAD2 = dict(OVERHEAD, ti=1.10, ti_src=.94, h=.067, hang=(.70, .957, .35, .04), ant=(.42, .83, 1.0), ant_hold=.2, zones=[(1.2, 2.05, 1.)], ease=1e-4, post_speed=1., post_dur=0.,
                 step=1, rebound=0., kick=.03, kick_tau=.07, jolt=.02, jolt_tau=.08, heave=None, exhale=(1.35, 1.95, -.011, 2.5, -3.), exhale_fade=.4, rec_drop=.014)
OVERHEAD3 = dict(OVERHEAD2, T2=1.15, exhale=(1.55, 2.05, -.012, 2.5, -3.), exhale_fade=.35, rec_drop=.018)
OVERHEAD4 = dict(OVERHEAD3, exhale=(1.55, 2.05, -.018, 3., -4.))
OVERHEAD5 = dict(OVERHEAD3, exhale=(1.5, 2.05, -.012, 3., -4., -.015))
OVERHEAD6 = dict(OVERHEAD5, exhale=(1.5, 2.05, -.015, 3.5, -4., -.02))
OVERHEAD7 = dict(OVERHEAD6, ft_drop=0., ft_pitch=0., ft_head=0., jolt=0., sink=(.025, 1.85, .7), exhale=(1.3, 1.85, -.012, 3.5, -6., -.02), exhale_fade=.7, rec_drop=0., kick=.04, kick_tau=.12, zones=[(1.2, 1.75, 1.)])
OVERHEAD8 = dict(OVERHEAD7, sink=(.03, 1.85, .8), exhale=(1.3, 1.85, -.015, 3.5, -6., -.03), exhale_fade=.8, kick_tau=.09)
OVERHEAD9 = dict(OVERHEAD8, sink=(.03, 1.85, .9), exhale_fade=.9, sink_lead=.03)


def end_diff(path, ref):
    """Max joint world-position difference at first/last frame between two scenes (baked deform rig)."""
    out = {}
    for tag, pth in (("new", path), ("ref", ref)):
        cm.open_tagged(Path(pth), P["owner"]); s = bpy.context.scene; rig = bpy.data.objects["Knight_Deform"]; out[tag] = {}
        for fr in (s.frame_start, s.frame_end):
            s.frame_set(fr); out[tag][fr == s.frame_start] = {b.name: (rig.matrix_world @ b.head).copy() for b in rig.pose.bones}
    res = {}
    for start in (True, False):
        a = out["new"][start]; b = out["ref"][start]; worst = max(a, key=lambda n: (a[n] - b[n]).length); res["start" if start else "end"] = (worst, round((a[worst] - b[worst]).length, 6))
    return res
OVERHEAD10 = dict(OVERHEAD9, sink=(.03, 1.8, .85), exhale=(1.3, 1.8, -.015, 3.5, -6., -.03), exhale_fade=.85)
THRUST11 = dict(THRUST8, rec_drop=0.)
