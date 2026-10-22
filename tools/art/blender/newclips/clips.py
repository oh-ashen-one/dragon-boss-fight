"""New Knight clips (2026-10-21, autonomous scope): Blender-side helpers. Execute ONLY in the task-owned
Blender MCP session (owner fable-veyr-knight-run-20261021, port 9885) via run_nc.py.

Reads approved / earlier scenes read-only; writes only under Local/Blender/newclips-20261021.
Native Blender control rig + four-limb IK + baked deform action (rebuild/approved_actions.py core).
"""
from pathlib import Path
import bpy, math, json, hashlib, shutil, importlib.util
from mathutils import Vector, Matrix, Quaternion
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
OUT = REPO / "Local/Blender/newclips-20261021"; OWNER = "fable-veyr-knight-run-20261021"; PORT = 9885
ASSETS = REPO / "tools/asset-review/.asset-cache/review"
_sp = importlib.util.spec_from_file_location("veyr_core_nc", REPO / "tools/art/blender/rebuild/approved_actions.py"); core = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(core)
core.OWNER = OWNER


def _inside(p, root):
    p, root = Path(p).resolve(), Path(root).resolve(); return p == root or root in p.parents


def writable(p):
    assert _inside(p, OUT), f"refusing to write outside {OUT}: {p}"; return Path(p)


def open_scene(path):
    bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False); s = bpy.context.scene
    prev = s.get("session_owner"); s["session_owner"] = OWNER; s["mcp_port"] = PORT; s["nc_opened_from"] = str(path)
    return {"opened": str(path), "prev": prev, "job": s.get("rebuild_job"), "fps": s.render.fps, "frames": [s.frame_start, s.frame_end], "duration": s.get("duration"), "two_hand": s.get("two_hand"), "sword": s.get("sword_file")}


def info():
    s = bpy.context.scene; out = {"markers": [(m.name, m.frame) for m in s.timeline_markers]}
    for o in s.objects:
        a = o.animation_data.action.name if o.animation_data and o.animation_data.action else None
        out[o.name] = {"t": o.type, "parent": o.parent.name if o.parent else None, "act": a, "cons": [(c.type, getattr(c, "subtarget", "")) for c in o.constraints]}
    return out


def capture(label, fps=30, res=420, ortho=1.6, center_z=.55, views=None, t0=0., t1=None, center_y=0., center_x=0., follow_bone=None):
    s = bpy.context.scene; assert s.get("session_owner") == OWNER
    cam = s.camera; folder = writable(OUT / "renders" / label); folder.mkdir(parents=True, exist_ok=True)
    for p in folder.glob("*.png"): p.unlink()
    s.render.resolution_x = s.render.resolution_y = res; s.display.shading.color_type = "OBJECT"
    for o in s.objects:
        if o.get("export_body"): o.color = (.53, .55, .6, 1)
        if o.get("review_attachment"): o.color = (.25, .16, .07, 1)
        if o.get("review_prop"): o.color = (.7, .32, .06, 1)
    bpy.ops.mesh.primitive_plane_add(size=4, location=(0, 0, 0)); g = bpy.context.object; g.name = "TMP_Ground"; g.color = (.16, .17, .15, 1)
    marks = []
    for i in range(-10, 11):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, i * .1, .0005)); m = bpy.context.object; m.scale = (.6, .003, .001); m.color = (.3, .3, .28, 1); marks.append(m)
    views = views or {"front": (0, -4, .35), "side": (4, 0, .35), "threequarter": (2.8, -4, 1.), "rear": (0, 4, .35)}
    dur = s["duration"]; t1 = dur if t1 is None else t1; n = round((t1 - t0) * fps) + 1; written = 0
    try:
        for view, xyz in views.items():
            for i in range(n):
                t = min(t1, t0 + i / fps); ff = t * s.render.fps; s.frame_set(int(ff), subframe=ff - int(ff))
                center = Vector((center_x, center_y, center_z))
                if follow_bone: rg = bpy.data.objects["Knight_Deform"]; center = rg.matrix_world @ rg.pose.bones[follow_bone].head
                d = Vector(xyz).normalized(); cam.location = center + d * 5
                cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler(); cam.data.ortho_scale = ortho
                s.render.filepath = str(folder / f"{view}-{i:04d}.png"); bpy.ops.render.render(write_still=True); written += 1
    finally:
        for o in [g, *marks]: bpy.data.objects.remove(o, do_unlink=True)
        for me in [m for m in bpy.data.meshes if m.users == 0]: bpy.data.meshes.remove(me)
    return {"folder": str(folder), "perView": n, "frames": written}


# ------------------------------------------------------------------ sampling ------------------------
CTRL = ("Hilt_Control", "LeftArm_Target", "RightArm_Target", "LeftLeg_Target", "RightLeg_Target", "LeftArm_Pole", "RightArm_Pole", "LeftLeg_Pole", "RightLeg_Pole")


def _flat(m): return [x for row in m for x in row]


def sample(name):
    """Evaluate every frame of the open scene's controls: FK basis of all bones, world matrices of CTRL, FK hands."""
    s = bpy.context.scene; fk = bpy.data.objects["Pose_Control_Rig"]; data = {"fps": s.render.fps, "frames": s.frame_end, "duration": s.get("duration"), "src": s.get("nc_opened_from"), "f": []}
    for fr in range(s.frame_end + 1):
        s.frame_set(fr); bpy.context.view_layer.update()
        row = {"fk": {b.name: _flat(b.matrix_basis) for b in fk.pose.bones}, "w": {n: _flat(bpy.data.objects[n].matrix_world) for n in CTRL if n in bpy.data.objects},
               "hand": {sd: _flat(fk.matrix_world @ fk.pose.bones[sd + "Hand"].matrix) for sd in ("Left", "Right")}}
        data["f"].append(row)
    p = writable(OUT / "cache" / (name + ".json")); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(data))
    return {"file": str(p), "frames": len(data["f"])}


def grip_relation():
    s = bpy.context.scene; s.frame_set(0); h = bpy.data.objects["Hilt_Control"].matrix_world; r = bpy.data.objects["RightArm_Target"].matrix_world
    l = bpy.data.objects["LeftArm_Target"].matrix_world
    rel = r.inverted() @ h; return {"rightToHilt": _flat(rel), "leftToHiltOffset": _flat(h.inverted() @ l)}


# ------------------------------------------------------------------ timeline composer ---------------
_CACHE = {}


def _load(name):
    if name not in _CACHE: _CACHE[name] = json.loads((OUT / "cache" / (name + ".json")).read_text())
    return _CACHE[name]


def _M(v): return Matrix([v[0:4], v[4:8], v[8:12], v[12:16]])


def _mblend(a, b, w):
    la, ra, sa = a.decompose(); lb, rb, sb = b.decompose()
    if ra.dot(rb) < 0: rb = -rb
    return Matrix.LocRotScale(la.lerp(lb, w), ra.slerp(rb, w), sa.lerp(sb, w))


def pchip(points, t):
    xs = [p[0] for p in points]; ys = [p[1] for p in points]
    if t <= xs[0]: return ys[0]
    if t >= xs[-1]: return ys[-1]
    n = len(xs); h = [xs[i + 1] - xs[i] for i in range(n - 1)]; d = [(ys[i + 1] - ys[i]) / h[i] for i in range(n - 1)]; m = [0.] * n
    m[0] = d[0] if n > 2 and d[0] * d[1] > 0 else 0.; m[-1] = d[-1] if n > 2 and d[-1] * d[-2] > 0 else 0.
    for i in range(1, n - 1):
        if d[i - 1] * d[i] <= 0: m[i] = 0.
        else: w1 = 2 * h[i] + h[i - 1]; w2 = h[i] + 2 * h[i - 1]; m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    i = max(j for j in range(n - 1) if xs[j] <= t); s = (t - xs[i]) / h[i]; s2, s3 = s * s, s * s * s
    return (2*s3 - 3*s2 + 1) * ys[i] + (s3 - 2*s2 + s) * h[i] * m[i] + (-2*s3 + 3*s2) * ys[i + 1] + (s3 - s2) * h[i] * m[i + 1]


class State:
    """Control state of one source at source time s (seconds); arm grip expressed relative to the hilt."""
    def __init__(self, src, s, grip_rel, two):
        d = _load(src); fr = max(0., min(d["frames"], s * d["fps"])); i = int(fr); j = min(i + 1, d["frames"]); w = fr - i
        A, B = d["f"][i], d["f"][j]
        self.fk = {n: _mblend(_M(A["fk"][n]), _M(B["fk"][n]), w) for n in A["fk"]}
        W = {n: _mblend(_M(A["w"][n]), _M(B["w"][n]), w) for n in A["w"]}
        if two: self.hilt = W["Hilt_Control"]
        else: self.hilt = W["RightArm_Target"] @ grip_rel          # one-hand source: keep the combo's right-hand grip
        self.left_world = W["LeftArm_Target"]; self.left_rel = self.hilt.inverted() @ W["LeftArm_Target"]; self.two = two
        self.legs = {n: W[n] for n in ("LeftLeg_Target", "RightLeg_Target")}; self.poles = {n: W[n].translation.copy() for n in ("LeftArm_Pole", "RightArm_Pole", "LeftLeg_Pole", "RightLeg_Pole")}


def blend_states(a, b, w, grip_rel):
    out = State.__new__(State)
    out.fk = {n: _mblend(a.fk[n], b.fk[n], w) for n in a.fk}
    out.hilt = _mblend(a.hilt, b.hilt, w)
    if a.two and b.two: out.left = out.hilt @ _mblend(a.left_rel, b.left_rel, w)
    else:
        la = out.hilt @ a.left_rel if a.two else a.left_world; lb = out.hilt @ b.left_rel if b.two else b.left_world
        out.left = _mblend(la, lb, w)
    out.right = out.hilt @ grip_rel.inverted()
    out.legs = {n: _mblend(a.legs[n], b.legs[n], w) for n in a.legs}; out.poles = {n: a.poles[n].lerp(b.poles[n], w) for n in a.poles}
    return out


def smooth01(x):
    x = min(1., max(0., x)); return x * x * (3 - 2 * x)


def compose(job, base_scene, segments, duration, grip_src="light_two", extra=None):
    """segments: [{src, two, knots:[(t_out, s_src)...], xin: crossfade seconds into this segment}] in output order.
    Writes dense world-space control keys (every frame) on the opened base scene's control rig."""
    open_scene(base_scene); s = bpy.context.scene
    old = s.get("rebuild_job"); coll = bpy.data.collections["AUTHORING_" + old]; coll.name = "AUTHORING_" + job
    s["rebuild_job"] = job; s["duration"] = duration; s["nc_segments"] = json.dumps(segments)
    fps = 150; s.render.fps = fps; s.render.fps_base = 1; s.frame_start = 0; s.frame_end = round(duration * fps)
    for m in list(s.timeline_markers): s.timeline_markers.remove(m)
    g = _load(grip_src); grip_rel = _M(g["f"][0]["w"]["RightArm_Target"]).inverted() @ _M(g["f"][0]["w"]["Hilt_Control"])
    fk = bpy.data.objects["Pose_Control_Rig"]; hilt = bpy.data.objects["Hilt_Control"]
    objs = {n: bpy.data.objects[n] for n in CTRL}
    for o in [fk, *objs.values()]:
        mw = o.matrix_world.copy(); o.animation_data_clear(); o.constraints.clear(); o.parent = None; o.matrix_world = mw
    for o in list(coll.objects):
        if o.name.endswith("_Follow"): bpy.data.objects.remove(o, do_unlink=True)
    starts = [seg["knots"][0][0] for seg in segments]; prev = {}
    for fr in range(s.frame_end + 1):
        t = fr / fps; states = []
        for k, seg in enumerate(segments):
            t0 = seg["knots"][0][0]; t1 = seg["knots"][-1][0]; xin = seg.get("xin", 0.)
            nxt = segments[k + 1] if k + 1 < len(segments) else None
            if t < t0 - 1e-9 or (nxt and t > nxt["knots"][0][0] + nxt.get("xin", 0.) + 1e-9): continue
            src_t = pchip(seg["knots"], t); states.append((k, State(seg["src"], src_t, grip_rel, seg["two"])))
        if len(states) == 1: st = blend_states(states[0][1], states[0][1], 0., grip_rel)
        else:
            (ka, a), (kb, b) = states[-2], states[-1]; seg = segments[kb]; w = smooth01((t - seg["knots"][0][0]) / max(1e-6, seg.get("xin", 0.)))
            st = blend_states(a, b, w, grip_rel)
        for b_ in fk.pose.bones: b_.matrix_basis = st.fk[b_.name]
        bpy.context.view_layer.update()
        for b_ in fk.pose.bones: core.key(b_, fr, prev)
        hilt.matrix_world = st.hilt; core.key(hilt, fr, prev)
        objs["LeftArm_Target"].matrix_world = st.left; core.key(objs["LeftArm_Target"], fr, prev)
        objs["RightArm_Target"].matrix_world = st.right; core.key(objs["RightArm_Target"], fr, prev)
        for n, m in st.legs.items(): objs[n].matrix_world = m; core.key(objs[n], fr, prev)
        for n, v in st.poles.items(): objs[n].location = v; objs[n].keyframe_insert("location", frame=fr)
    for o in [fk, *objs.values()]:
        for fc in core.curves(o.animation_data.action):
            for kp in fc.keyframe_points: kp.interpolation = "LINEAR"
    for i, seg in enumerate(segments): s.timeline_markers.new(f"seg{i}_{seg['src']}", frame=round(seg["knots"][0][0] * fps))
    if extra: extra(s)
    core.at(0); return {"job": job, "frames": s.frame_end, "duration": duration}


def bake_job(job, source_label, times_n=17):
    s = bpy.context.scene; assert s.get("session_owner") == OWNER and s.get("rebuild_job") == job
    core.OUT = writable(OUT / job); core.OUT.mkdir(parents=True, exist_ok=True)
    core.JOBS[job] = (source_label, s["duration"], [s["duration"] * i / (times_n - 1) for i in range(times_n)], bool(s.get("two_hand")))
    core.bake(); return {"blend": bpy.data.filepath}


# ------------------------------------------------------------------ LightCombo_Blender_v1 -----------
COMBO = dict(
    duration=2.26,
    # light_two source (approved two-hand compact light): impact = blade crosses forward at s~0.41
    L=[(0, 0), (.20, .20), (.385, .385), (.40, .41), (.47, .41), (.49, .43), (.58, .55), (.64, .575),
       (.73, .47), (.775, .42), (.79, .41), (.85, .41), (.87, .39), (.99, .24), (1.05, .22)],
    # heavy one-hand v3 source (free left arm counterbalance): coil from the windup hold, impact s~0.52
    H=[(.93, .30), (1.03, .44), (1.085, .51), (1.10, .52), (1.18, .52), (1.20, .54), (1.41, .76), (1.52, .86), (1.85, 1.20)], H_xin=.15,
    # back to the approved two-hand idle (light_two end pose), left hand re-grips
    I=[(1.70, 1.10), (2.26, 1.10)], I_xin=.35,
    belly_clear=0.05, belly_dir=(0, 1, 0),
)


def light_combo():
    C = COMBO; base = REPO / "Local/Blender/approved-rebuild-20261021/light_two_Blender_v1.blend"
    segs = [{"src": "light_two", "two": True, "knots": C["L"]},
            {"src": "heavy", "two": False, "knots": C["H"], "xin": C["H_xin"]},
            {"src": "light_two", "two": True, "knots": C["I"], "xin": C["I_xin"]}]
    def clear_belly(t):  # heavy recovery: the long pommel would enter the belly plate (measured 8 mm); carry the hands forward
        w = smooth01((t - 1.40) / .14) * smooth01((1.86 - t) / .14)
        return Vector(C["belly_dir"]).normalized() * C["belly_clear"] * w, False
    r = compose("light_combo", base, segs, C["duration"], hilt_offset=clear_belly)
    s = bpy.context.scene; s["review_name"] = "LightCombo_Blender_v1"; s["hit_stops"] = json.dumps([[.40, .47], [.79, .85], [1.10, 1.18]]); s["two_hand"] = True
    return r


# ------------------------------------------------------------------ generic per-frame inspection ----
def _groups(body, prefixes):
    gid = {g.index: g.name for g in body.vertex_groups}
    return [v.index for v in body.data.vertices if sum(gg.weight for gg in v.groups if gid.get(gg.group, "").startswith(prefixes)) > .5]


def inspect_clip(name, free_left=None, step=1):
    """Feet planted/slide, sword-body clearance, free-left-hand-to-sword clearance, per frame of the baked scene.
    free_left: list of (t0, t1) seconds where the left hand is NOT on the hilt (checked for clearance to the sword)."""
    from mathutils.bvhtree import BVHTree
    s = bpy.context.scene; rig = bpy.data.objects["Knight_Deform"]
    body = next(o for o in s.objects if o.type == "MESH" and o.get("export_body") and len(o.data.vertices) > 1000 and not o.get("review_prop"))
    sword = next(o for o in s.objects if o.type == "MESH" and o.get("review_attachment")); sword.data.calc_loop_triangles()
    sv = [v.co.copy() for v in sword.data.vertices]; st = [list(t.vertices) for t in sword.data.loop_triangles]
    feet = {sd: _groups(body, (sd + "Foot", sd + "ToeBase")) for sd in ("Left", "Right")}
    excl = set(_groups(body, ("LeftHand", "RightHand", "LeftForeArm", "RightForeArm")))
    torso = _groups(body, ("Hips", "Spine", "Neck", "Head", "LeftUpLeg", "RightUpLeg"))[::2]
    lhand = _groups(body, ("LeftHand", "LeftForeArm")); rest = [i for i in range(len(body.data.vertices)) if i not in excl][::2]
    free_left = free_left or []; rows = []
    for fr in range(0, s.frame_end + 1, step):
        t = fr / s.render.fps; s.frame_set(fr); dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); mw = ev.matrix_world
        bvh = BVHTree.FromPolygons([sword.matrix_world @ v for v in sv], st, all_triangles=True)
        r = {"f": fr, "t": round(t, 4)}
        for sd in feet:
            pts = [mw @ me.vertices[i].co for i in feet[sd]]; z0 = min(p.z for p in pts); low = [p for p in pts if p.z < z0 + .004]
            c = sum(low, Vector()) / len(low); r[sd + "Z"] = z0; r[sd + "C"] = [c.x, c.y]
        sb = min(bvh.find_nearest(mw @ me.vertices[i].co)[3] for i in rest); r["swordBody"] = sb
        r["swordTorso"] = min(bvh.find_nearest(mw @ me.vertices[i].co)[3] for i in torso)
        if any(a <= t <= b for a, b in free_left): r["freeLeftHandSword"] = min(bvh.find_nearest(mw @ me.vertices[i].co)[3] for i in lhand)
        ev.to_mesh_clear(); rows.append(r)
    g0 = min(min(r["LeftZ"], r["RightZ"]) for r in rows); slide = {}
    for sd in feet:
        worst = (0., None); n = 0
        for a, b in zip(rows, rows[1:]):
            if a[sd + "Z"] - g0 < .003 and b[sd + "Z"] - g0 < .003:
                d = math.hypot(b[sd + "C"][0] - a[sd + "C"][0], b[sd + "C"][1] - a[sd + "C"][1]); n += 1
                if d > worst[0]: worst = (d, a["f"])
        slide[sd] = {"maxPlantedStepPerFrame": worst[0], "atFrame": worst[1], "plantedPairs": n}
    res = {"frames": len(rows), "ground": g0, "slide": slide, "minSwordBody": min(r["swordBody"] for r in rows), "minSwordBodyFrame": min(rows, key=lambda r: r["swordBody"])["f"], "swordTorsoUnder2mmFrames": [r["f"] for r in rows if r["swordTorso"] < .002],
           "minFreeLeftHandSword": min([r["freeLeftHandSword"] for r in rows if "freeLeftHandSword" in r] or [None]) if free_left else None,
           "lift": {sd: max(r[sd + "Z"] for r in rows) - g0 for sd in feet}}
    p = writable(OUT / s["rebuild_job"] / (name + ".json")); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps({**res, "rows": rows}, indent=1))
    return res


def sword_near(fr, thresh=.01, n=8):
    from mathutils.bvhtree import BVHTree
    s = bpy.context.scene; s.frame_set(fr)
    body = next(o for o in s.objects if o.type == "MESH" and o.get("export_body") and len(o.data.vertices) > 1000 and not o.get("review_prop"))
    sword = next(o for o in s.objects if o.type == "MESH" and o.get("review_attachment")); sword.data.calc_loop_triangles()
    bvh = BVHTree.FromPolygons([sword.matrix_world @ v.co for v in sword.data.vertices], [list(t.vertices) for t in sword.data.loop_triangles], all_triangles=True)
    gid = {g.index: g.name for g in body.vertex_groups}; dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); mw = ev.matrix_world; hits = {}
    for v in me.vertices:
        hit = bvh.find_nearest(mw @ v.co)
        if hit[3] is not None and hit[3] < thresh:
            g = max(((gid[x.group], x.weight) for x in body.data.vertices[v.index].groups), key=lambda x: x[1])[0]; hits[g] = min(hits.get(g, 1.), hit[3])
    ev.to_mesh_clear(); return dict(sorted(hits.items(), key=lambda x: x[1])[:n])


# ------------------------------------------------------------------ compose v2: foot lock -----------
def foot_lock(mats, fps=150, speed=.0016, height=.012, ease=4):
    """Pin a foot target while it is down and nearly still (removes source/crossfade skating).
    mats: per-frame world matrices. Planted = low (within `height` of this foot's lowest) and slow (< speed per frame).
    Inside a planted span the translation is held at the span's mean; spans blend in/out over `ease` frames."""
    n = len(mats); zs = [m.translation.z for m in mats]; zmin = min(zs)
    v = [0.] + [(mats[i].translation - mats[i - 1].translation).length for i in range(1, n)]
    planted = [(zs[i] - zmin < .004) or ((zs[i] - zmin < height) and (v[i] < speed)) for i in range(n)]  # on the ground = planted, even if the source skids
    # close tiny gaps / drop tiny spans
    spans = []; i = 0
    while i < n:
        if planted[i]:
            j = i
            while j + 1 < n and planted[j + 1]: j += 1
            if j - i >= 4: spans.append((i, j))
            i = j + 1
        else: i += 1
    out = [m.copy() for m in mats]
    for a, b in spans:
        p = (mats[b] if (b == n - 1 and a > 0) else mats[a]).translation.copy()  # pin where the foot lands; a final span pins to the end pose exactly
        for k in range(max(0, a - ease), min(n, b + ease + 1)):
            if a <= k <= b: w = 1.
            elif k < a: w = smooth01(1 - (a - k) / ease)
            else: w = smooth01(1 - (k - b) / ease)
            m = out[k]; loc, rot, sc = m.decompose(); out[k] = Matrix.LocRotScale(loc.lerp(p, w), rot, sc)
    # a foot that travels between plants must clear the ground (step, not drag)
    gaps = []; prev_end = None
    for a_, b_ in spans:
        if prev_end is not None and a_ - prev_end > 2: gaps.append((prev_end, a_))
        prev_end = b_
    for a_, b_ in gaps:
        travel = (out[b_].translation.xy - out[a_].translation.xy).length; lift = max(out[k].translation.z for k in range(a_, b_ + 1)) - zmin
        if travel > .01:
            for k in range(a_, b_ + 1):
                u = (k - a_) / (b_ - a_); m = out[k]; loc, rot, sc = m.decompose(); loc.z = max(loc.z, zmin + .03 * math.sin(math.pi * u) ** .45); out[k] = Matrix.LocRotScale(loc, rot, sc)
    return out, spans


def compose(job, base_scene, segments, duration, grip_src="light_two", extra=None, lock_feet=True, hilt_offset=None):
    open_scene(base_scene); s = bpy.context.scene
    old = s.get("rebuild_job"); coll = bpy.data.collections["AUTHORING_" + old]; coll.name = "AUTHORING_" + job
    s["rebuild_job"] = job; s["duration"] = duration; s["nc_segments"] = json.dumps(segments)
    fps = 150; s.render.fps = fps; s.render.fps_base = 1; s.frame_start = 0; s.frame_end = round(duration * fps)
    for m in list(s.timeline_markers): s.timeline_markers.remove(m)
    g = _load(grip_src); grip_rel = _M(g["f"][0]["w"]["RightArm_Target"]).inverted() @ _M(g["f"][0]["w"]["Hilt_Control"])
    fk = bpy.data.objects["Pose_Control_Rig"]; hilt = bpy.data.objects["Hilt_Control"]; objs = {n: bpy.data.objects[n] for n in CTRL}
    for o in [fk, *objs.values()]:
        mw = o.matrix_world.copy(); o.animation_data_clear(); o.constraints.clear(); o.parent = None; o.matrix_world = mw
    for o in list(coll.objects):
        if o.name.endswith("_Follow"): bpy.data.objects.remove(o, do_unlink=True)
    frames = []
    for fr in range(s.frame_end + 1):
        t = fr / fps; states = []
        for k, seg in enumerate(segments):
            t0 = seg["knots"][0][0]; nxt = segments[k + 1] if k + 1 < len(segments) else None
            if t < t0 - 1e-9 or (nxt and t > nxt["knots"][0][0] + nxt.get("xin", 0.) + 1e-9): continue
            states.append((k, State(seg["src"], pchip(seg["knots"], t), grip_rel, seg["two"])))
        if len(states) == 1: st = blend_states(states[0][1], states[0][1], 0., grip_rel)
        else:
            (ka, a), (kb, b) = states[-2], states[-1]; w = smooth01((t - segments[kb]["knots"][0][0]) / max(1e-6, segments[kb].get("xin", 0.)))
            st = blend_states(a, b, w, grip_rel)
        if hilt_offset:
            off, move_left = hilt_offset(t)  # world-space translation of the hilt + right grip (+ left hand when it is on the hilt)
            if off is not None and off.length > 0:
                T_ = Matrix.Translation(off); st.hilt = T_ @ st.hilt; st.right = T_ @ st.right
                if move_left: st.left = T_ @ st.left
        frames.append(st)
    spans = {}
    if lock_feet:
        for n in ("LeftLeg_Target", "RightLeg_Target"):
            locked, spans[n] = foot_lock([f.legs[n] for f in frames])
            for f, m in zip(frames, locked): f.legs[n] = m
    prev = {}
    for fr, st in enumerate(frames):
        for b_ in fk.pose.bones: b_.matrix_basis = st.fk[b_.name]
        bpy.context.view_layer.update()
        for b_ in fk.pose.bones: core.key(b_, fr, prev)
        hilt.matrix_world = st.hilt; core.key(hilt, fr, prev)
        objs["LeftArm_Target"].matrix_world = st.left; core.key(objs["LeftArm_Target"], fr, prev)
        objs["RightArm_Target"].matrix_world = st.right; core.key(objs["RightArm_Target"], fr, prev)
        for n, m in st.legs.items(): objs[n].matrix_world = m; core.key(objs[n], fr, prev)
        for n, v in st.poles.items(): objs[n].location = v; objs[n].keyframe_insert("location", frame=fr)
    for o in [fk, *objs.values()]:
        for fc in core.curves(o.animation_data.action):
            for kp in fc.keyframe_points: kp.interpolation = "LINEAR"
    for i, seg in enumerate(segments): s.timeline_markers.new(f"seg{i}_{seg['src']}", frame=round(seg["knots"][0][0] * fps))
    s["foot_lock_spans"] = json.dumps(spans)
    if extra: extra(s)
    core.at(0); return {"job": job, "frames": s.frame_end, "duration": duration, "footSpans": spans}


def sword_penetration(fr_list=None, step=3):
    """Count body vertices INSIDE the sword mesh (BVH normal test) per frame; depth = distance to surface."""
    from mathutils.bvhtree import BVHTree
    s = bpy.context.scene; body = next(o for o in s.objects if o.type == "MESH" and o.get("export_body") and len(o.data.vertices) > 1000 and not o.get("review_prop"))
    sword = next(o for o in s.objects if o.type == "MESH" and o.get("review_attachment")); sword.data.calc_loop_triangles()
    gid = {g.index: g.name for g in body.vertex_groups}; out = []
    for fr in (fr_list or range(0, s.frame_end + 1, step)):
        s.frame_set(fr); bvh = BVHTree.FromPolygons([sword.matrix_world @ v.co for v in sword.data.vertices], [list(t.vertices) for t in sword.data.loop_triangles], all_triangles=True)
        dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); mw = ev.matrix_world; n = 0; depth = 0.; groups = {}
        for v in me.vertices:
            q = mw @ v.co; hit = bvh.find_nearest(q, .03)
            if hit[0] is not None and (q - hit[0]).dot(hit[1]) < -1e-5:
                g = max(((gid[x.group], x.weight) for x in body.data.vertices[v.index].groups), key=lambda x: x[1])[0]
                if "Hand" in g: continue
                n += 1; depth = max(depth, hit[3]); groups[g] = groups.get(g, 0) + 1
        ev.to_mesh_clear(); out.append((fr, n, round(depth, 4), groups))
    return out



def push_dir(fr):
    """Mean outward normal of the sword surface at body vertices inside it (direction to move the sword out)."""
    from mathutils.bvhtree import BVHTree
    s = bpy.context.scene; s.frame_set(fr); body = next(o for o in s.objects if o.type == "MESH" and o.get("export_body") and len(o.data.vertices) > 1000 and not o.get("review_prop"))
    sword = next(o for o in s.objects if o.type == "MESH" and o.get("review_attachment")); sword.data.calc_loop_triangles()
    bvh = BVHTree.FromPolygons([sword.matrix_world @ v.co for v in sword.data.vertices], [list(t.vertices) for t in sword.data.loop_triangles], all_triangles=True)
    dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); mw = ev.matrix_world; acc = Vector(); n = 0; c = Vector()
    for v in me.vertices:
        q = mw @ v.co; hit = bvh.find_nearest(q, .03)
        if hit[0] is not None and (q - hit[0]).dot(hit[1]) < -1e-5: acc += hit[1]; n += 1; c += q
    ev.to_mesh_clear()
    return {"n": n, "meanSwordNormal": list(acc.normalized()) if n else None, "contactCentroid": list(c / n) if n else None, "socket": list(bpy.data.objects["ReviewWeaponSocket"].matrix_world.translation)}



# ------------------------------------------------------------------ export -----------------------------
def approved_names():
    a = json.loads((REPO / "tools/art/blender/rebuild/approvals.json").read_text())["clips"]
    d = json.loads((REPO / "tools/art/blender/feedback/decisions.json").read_text())["approved"]
    return {e["file"]: e["sha256"] for e in a + d}


def export_clip(review_name, allow_overwrite=False, extra_report=None):
    """Strap-fix body (feedback v4 weights), export <OUT>/<job>/<job>_Blender_v1.glb with the review animation name,
    save the scene there, copy to <OUT>/export/<review_name>.glb. Approved names are refused."""
    s = bpy.context.scene; job = s["rebuild_job"]; assert s.get("session_owner") == OWNER
    name = review_name + ".glb"; assert name not in approved_names(), name
    sp = importlib.util.spec_from_file_location("veyr_v4_strap_nc", REPO / "tools/art/blender/feedback_v4/strap_v4.py"); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    strap = m.apply_body()
    folder = writable(OUT / job); folder.mkdir(parents=True, exist_ok=True); core.at(0); rig = bpy.data.objects["Knight_Deform"]
    for o in s.objects: o.select_set(o == rig or o.name == "ReviewWeaponSocket" or bool(o.get("export_body")))
    bpy.context.view_layer.objects.active = rig; p = folder / (job + "_Blender_v1.glb")
    with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
        bpy.ops.export_scene.gltf(filepath=str(p), export_format="GLB", use_selection=True, export_animations=True, export_animation_mode="ACTIVE_ACTIONS", export_nla_strips_merged_animation_name=review_name, export_frame_range=True, export_force_sampling=True, export_optimize_animation_size=False, export_cameras=False, export_lights=False, export_extras=True)
    tx = bpy.data.texts.get("newclips_clips.py") or bpy.data.texts.new("newclips_clips.py"); tx.clear(); tx.write(Path(__file__).read_text()); tx.use_fake_user = True
    s["review_name"] = review_name
    bpy.ops.wm.save_as_mainfile(filepath=str(folder / (job + "_Blender_v1.blend")), compress=True); assert _inside(bpy.data.filepath, OUT)
    rp = folder / (job + "-report.json"); r = json.loads(rp.read_text()) if rp.exists() else {}
    r.update(job=job, reviewName=review_name, duration=s["duration"], sha256=hashlib.sha256(p.read_bytes()).hexdigest(), ownerApproved=False, strapFix=strap, segments=json.loads(s.get("nc_segments", "[]")), hitStops=json.loads(s.get("hit_stops", "[]")), footLockSpans=json.loads(s.get("foot_lock_spans", "{}")), **(extra_report or {}))
    rp.write_text(json.dumps(r, indent=2) + "\n")
    dest = writable(OUT / "export" / name); dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not allow_overwrite: raise FileExistsError(dest)
    shutil.copyfile(p, dest)
    return {"glb": str(dest), "sha256": r["sha256"], "blend": bpy.data.filepath, "strap": strap.get("sha256Weights"), "ikError": r.get("nativeIKError")}



def contact_detail(frames):
    """Per frame: body groups inside the sword, sword-local z range of the touching sword surface (handle < 0 < blade),
    mean outward sword normal at the contacts (world)."""
    from mathutils.bvhtree import BVHTree
    s = bpy.context.scene; body = next(o for o in s.objects if o.type == "MESH" and o.get("export_body") and len(o.data.vertices) > 1000 and not o.get("review_prop"))
    sword = next(o for o in s.objects if o.type == "MESH" and o.get("review_attachment")); sword.data.calc_loop_triangles(); sock = bpy.data.objects["ReviewWeaponSocket"]
    gid = {g.index: g.name for g in body.vertex_groups}; out = {}
    for fr in frames:
        s.frame_set(fr); bvh = BVHTree.FromPolygons([sword.matrix_world @ v.co for v in sword.data.vertices], [list(t.vertices) for t in sword.data.loop_triangles], all_triangles=True)
        dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); mw = ev.matrix_world; zs = []; nrm = Vector(); groups = {}
        inv = sock.matrix_world.inverted()
        for v in me.vertices:
            q = mw @ v.co; hit = bvh.find_nearest(q, .03)
            if hit[0] is not None and (q - hit[0]).dot(hit[1]) < -1e-5:
                g = max(((gid[x.group], x.weight) for x in body.data.vertices[v.index].groups), key=lambda x: x[1])[0]
                if "Hand" in g: continue
                groups[g] = groups.get(g, 0) + 1; zs.append((inv @ hit[0]).z); nrm += hit[1]
        ev.to_mesh_clear()
        out[fr] = {"groups": groups, "swordLocalZ": [round(min(zs), 3), round(max(zs), 3)] if zs else None, "push": [round(x, 2) for x in nrm.normalized()] if zs else None}
    return out



def contact_scan(name, step=1):
    """Every frame: body vertices inside the sword (hands excluded), depth, mean push normal, mean sword-local z of the
    contacts, right-palm world point and blade direction. Written to <OUT>/<job>/<name>.json; returns a summary."""
    from mathutils.bvhtree import BVHTree
    s = bpy.context.scene; body = next(o for o in s.objects if o.type == "MESH" and o.get("export_body") and len(o.data.vertices) > 1000 and not o.get("review_prop"))
    sword = next(o for o in s.objects if o.type == "MESH" and o.get("review_attachment")); sword.data.calc_loop_triangles(); sock = bpy.data.objects["ReviewWeaponSocket"]
    gid = {g.index: g.name for g in body.vertex_groups}
    keep = [v.index for v in body.data.vertices if "Hand" not in max(((gid[x.group], x.weight) for x in v.groups), key=lambda x: x[1], default=("", 0))[0]]
    tris = [list(t.vertices) for t in sword.data.loop_triangles]; sv = [v.co.copy() for v in sword.data.vertices]; rows = {}
    for fr in range(0, s.frame_end + 1, step):
        s.frame_set(fr); M = sword.matrix_world; bvh = BVHTree.FromPolygons([M @ v for v in sv], tris, all_triangles=True)
        dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); mw = ev.matrix_world
        n = 0; depth = 0.; push = Vector(); zs = 0.; inv = sock.matrix_world.inverted()
        for i in keep:
            q = mw @ me.vertices[i].co; hit = bvh.find_nearest(q, .04)
            if hit[0] is not None and (q - hit[0]).dot(hit[1]) < -1e-5:
                n += 1; depth = max(depth, hit[3]); push += hit[1]; zs += (inv @ hit[0]).z
        ev.to_mesh_clear(); S = sock.matrix_world
        rows[fr] = {"n": n, "depth": depth, "push": list(push.normalized()) if n else None, "z": zs / n if n else None,
                    "palm": list(S @ Vector((0, 0, -.075))), "blade": list((S.to_3x3() @ Vector((0, 0, 1))).normalized())}
    p = writable(OUT / s["rebuild_job"] / (name + ".json")); p.write_text(json.dumps(rows))
    bad = [f for f, r in rows.items() if r["n"] > 3]
    return {"frames": len(rows), "framesOver3": len(bad), "maxN": max(r["n"] for r in rows.values()), "maxDepth": max(r["depth"] for r in rows.values()), "file": str(p)}



def normal_check():
    """Sign test of the sword mesh normals: points clearly OUTSIDE the sword must give (q-hit).n > 0."""
    from mathutils.bvhtree import BVHTree
    sword = next(o for o in bpy.context.scene.objects if o.type == "MESH" and o.get("review_attachment")); sword.data.calc_loop_triangles()
    vs = [v.co.copy() for v in sword.data.vertices]; bvh = BVHTree.FromPolygons(vs, [list(t.vertices) for t in sword.data.loop_triangles], all_triangles=True)
    c = sum(vs, Vector()) / len(vs); res = []
    for d in (Vector((1, 0, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0)), Vector((0, -1, 0)), Vector((0, 0, 1)), Vector((0, 0, -1))):
        q = c + d * 3.; hit = bvh.find_nearest(q); res.append(round((q - hit[0]).normalized().dot(hit[1]), 3))
    # also handle region (z<0) from the side
    for z in (-.3, -.1, .5, 1.2):
        for d in (Vector((1, 0, 0)), Vector((0, 1, 0))):
            q = Vector((0, 0, z)) + d * .5; hit = bvh.find_nearest(q); res.append(("z", z, round((q - hit[0]).normalized().dot(hit[1]), 3)))
    return {"centre": list(c), "signs": res, "nonManifoldHint": len(sword.data.polygons)}



def ik_errors(top=8):
    """Per frame: baked hand/foot bone position vs its IK target (unreachable targets show up here)."""
    s = bpy.context.scene; rig = bpy.data.objects["Knight_Deform"]; out = []
    for fr in range(s.frame_end + 1):
        s.frame_set(fr)
        for lab, bone in (("LeftArm", "LeftHand"), ("RightArm", "RightHand"), ("LeftLeg", "LeftFoot"), ("RightLeg", "RightFoot")):
            tg = bpy.data.objects[lab + "_Target"].matrix_world.translation; b = rig.matrix_world @ rig.pose.bones[bone].head
            out.append((round((tg - b).length, 5), fr, lab))
    out.sort(reverse=True); return out[:top]



def limb_stretch(top=10):
    """Per frame: change of each limb segment length in the baked rig vs rest (detached hands/feet = unreachable targets)."""
    s = bpy.context.scene; rig = bpy.data.objects["Knight_Deform"]; segs = [(sd + a, sd + b) for sd in ("Left", "Right") for a, b in (("Arm", "ForeArm"), ("ForeArm", "Hand"), ("UpLeg", "Leg"), ("Leg", "Foot"))]
    rest = {k: (rig.data.bones[k[1]].head_local - rig.data.bones[k[0]].head_local).length for k in segs}; out = []
    for fr in range(s.frame_end + 1):
        s.frame_set(fr)
        for k in segs:
            L = (rig.pose.bones[k[1]].head - rig.pose.bones[k[0]].head).length; out.append((round(abs(L - rest[k]), 5), fr, k[1]))
    out.sort(reverse=True); bad = sorted(set(f for e, f, _ in out if e > .002)); return {"top": out[:top], "framesOver2mm": bad}
