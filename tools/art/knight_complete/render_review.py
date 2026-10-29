"""Headless Blender review renders for the knight completion pass (2026-10-28).

blender --background --factory-startup --python render_review.py -- JOBS.json OUTDIR
Each job: {"label", "segments": [{"glb", "start", "end", "rate"}], "blend": seconds, "cycles": n}
Segments play back to back at in-game rate (rate = clip seconds per real second); a segment
switch blends from the frozen previous pose to the next clip over `blend` seconds, linear in
bone-local space (the in-game UVeyrSingleNodeInstance transition). Renders front, side and
three-quarter views at 30 fps (real time) with the boat sword on WeaponSocket and a floor grid.

Round 3 options (all optional; jobs without them render exactly as before):
  segment "even": true      loops: n = round(span*30) frames at evenly spaced phases t_i = start + i*(end-start)/n, so
                            the wrap step equals every other step; actions: n+1 frames ending exactly on `end`
  segment "root":           {"velocityGameCmS": [left, forward]} constant in-game capsule speed (game cm = rig m x 240),
                            or {"samplesCm": [[x, y, z], ...], "rate": Hz} the plan's root track (UE mesh-local cm,
                            x = knight's left, y = boss forward; mesh cm = rig cm). Offsets accumulate across segments.
  segment "hide": [t0, t1]  clip-second window in which the knight and sword are not drawn (blink hidden window)
  job "camera":             "hips" (default, follows the hips), "root" (follows the root offset, so the floor grid
                            scrolls under planted feet) or "fixed" (centred on the whole root path)
  job "display": glb        draw this file's mesh (e.g. the mesh variant the engine uses) with the sampled poses
  job "ortho": metres       orthographic width (default 2.1, widened to fit a fixed camera's root path)

Round 4 option (optional; jobs without it render exactly as before):
  job "views": [names]      subset/order of "front", "side", "threequarter", "top" (default the first three). "top" looks
                            straight down with the boss at the top of the image and the knight's right on the right, so
                            pelvis / leg-plane yaw is readable directly (frames saved as top_NNNN.png)"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

args = sys.argv[sys.argv.index("--") + 1:]
JOBS = json.loads(Path(args[0]).read_text())
OUT = Path(args[1])
ROOT = Path(__file__).resolve().parents[3]
SWORD = ROOT / "Local/polish-review-20261025/BoatGreatsword_OneHand_v4.glb"
FPS = 30
VIEWS = {"front": (0, -3, .4), "side": (3, 0, .4), "threequarter": (2, -3, .5)}
RES = 360
DRY = "--dry" in args  # sample, pose and place everything but do not render (no GPU work); for checking jobs


def clear():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=False, do_recursive=True)


def import_glb(path):
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    new = set(bpy.context.scene.objects) - before
    arm = next(o for o in new if o.type == "ARMATURE")
    return arm, new


def sample_poses(arm, times):
    """matrix_basis per pose bone at each clip time (seconds)."""
    s = bpy.context.scene
    rows = []
    for t in times:
        f = t * FPS
        s.frame_set(int(math.floor(f)), subframe=f - math.floor(f))
        rows.append({b.name: b.matrix_basis.copy() for b in arm.pose.bones})
    return rows


def mix(a, b, w):
    la, qa, sa = a.decompose()
    lb, qb, sb = b.decompose()
    if qa.dot(qb) < 0:
        qb = -qb
    return Matrix.LocRotScale(la.lerp(lb, w), qa.slerp(qb, w), sa.lerp(sb, w))


def setup_scene(floor_size=6):
    s = bpy.context.scene
    s.render.fps = FPS
    s.render.fps_base = 1
    s.render.engine = "BLENDER_WORKBENCH"
    sh = s.display.shading
    sh.light = "STUDIO"
    sh.color_type = "TEXTURE"
    sh.show_shadows = True
    sh.show_cavity = True
    sh.background_type = "WORLD"
    if not s.world:
        s.world = bpy.data.worlds.new("ReviewWorld")
    s.world.color = (.065, .07, .08)
    s.view_settings.view_transform = "Standard"
    s.view_settings.exposure = .8
    s.render.resolution_x = s.render.resolution_y = RES
    s.render.resolution_percentage = 100
    s.render.image_settings.file_format = "PNG"
    bpy.ops.mesh.primitive_plane_add(size=floor_size, location=(0, 0, 0))
    floor = bpy.context.active_object
    floor.name = "ReviewFloorGrid"
    k = 14.4 * floor_size / 6
    for loop in floor.data.uv_layers.active.data:
        loop.uv = (loop.uv[0] * k, loop.uv[1] * k)  # 4 tiles per 1/2.4 m: 10.4 cm rig = 25 game cm tiles
    image = bpy.data.images.new("ReviewGrid", 64, 64)
    px = []
    for y in range(64):
        for x in range(64):
            v = .23 if ((x // 16) + (y // 16)) % 2 else .17
            px += [v, v, v * 1.05, 1.0]
    image.pixels.foreach_set(px)
    mat = bpy.data.materials.new("ReviewFloor")
    mat.use_nodes = True
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = image
    tex.interpolation = "Closest"
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    floor.data.materials.append(mat)
    cam = bpy.data.objects.new("ReviewCamera", bpy.data.cameras.new("ReviewCamera"))
    s.collection.objects.link(cam)
    s.camera = cam
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 2.1
    return cam


def attach_sword(arm):
    s = bpy.context.scene
    before = set(s.objects)
    bpy.ops.import_scene.gltf(filepath=str(SWORD))
    imported = set(s.objects) - before
    attach = bpy.data.objects.new("Review_BoatSword", None)
    s.collection.objects.link(attach)
    for o in imported:
        if o.parent not in imported:
            m = o.matrix_world.copy()
            o.parent = attach
            o.matrix_parent_inverse = Matrix.Identity(4)
            o.matrix_basis = Matrix.Rotation(-math.pi / 2, 4, "X") @ m
    con = attach.constraints.new("COPY_TRANSFORMS")
    con.target = arm
    con.subtarget = "WeaponSocket"
    return [attach] + list(imported)


def root_offset(seg, t, real):
    """Root offset (Blender world, rig m) of a segment at clip time t / real seconds since the segment start."""
    r = seg.get("root")
    if not r:
        return Vector()
    if "velocityGameCmS" in r:
        vx, vy = r["velocityGameCmS"]
        return Vector((vx, -vy, 0)) * (real / 240.0)   # glTF +X = knight's left = Blender +X; boss forward = Blender -Y
    rs, rate = r["samplesCm"], r["rate"]
    u = max(0.0, min(len(rs) - 1, t * rate)); i = int(u); j = min(i + 1, len(rs) - 1); w = u - i
    x = rs[i][0] * (1 - w) + rs[j][0] * w; y = rs[i][1] * (1 - w) + rs[j][1] * w
    return Vector((x, -y, 0)) / 100.0


def render_job(job):
    clear()
    travel = any(seg.get("root") for seg in job["segments"])
    cam = setup_scene(24 if travel else 6)
    # Pre-sample every segment pose at the output frame times.
    timeline = []  # (segment index, clip seconds) per output frame
    for k, seg in enumerate(job["segments"]):
        span = (seg["end"] - seg["start"]) / seg["rate"]
        n = max(1, int(round(span * FPS)))
        if seg.get("even"):
            cnt = n if seg.get("loop") else n + 1
            timeline += [(k, seg["start"] + i * (seg["end"] - seg["start"]) / n) for i in range(cnt)]
        else:
            timeline += [(k, seg["start"] + i / FPS * seg["rate"]) for i in range(n)]
    hold = int(round(job.get("hold", 0.0) * FPS))
    timeline += [timeline[-1]] * hold
    # root offsets (accumulated across segments) and hidden frames
    offsets, hidden, base, seg_start, last_k = [], [], Vector(), {}, None
    for i, (k, t) in enumerate(timeline):
        seg = job["segments"][k]
        if k != last_k:
            if last_k is not None:
                base = offsets[-1].copy()
            seg_start[k] = (i, base.copy()); last_k = k
        i0, b0 = seg_start[k]
        offsets.append(b0 + root_offset(seg, t - seg["start"], (i - i0) / FPS))
        h = seg.get("hide")
        hidden.append(bool(h) and h[0] <= t < h[1])
    poses = [None] * len(timeline)
    display = None
    for k, seg in enumerate(job["segments"]):
        arm, objs = import_glb(ROOT / seg["glb"])
        dur = arm.animation_data.action.frame_range[1] / FPS if arm.animation_data and arm.animation_data.action else 0
        idx = [i for i, (sk, _) in enumerate(timeline) if sk == k]
        times = []
        for i in idx:
            t = timeline[i][1]
            if seg.get("loop") and dur > 0:
                t = t % dur
            times.append(min(t, dur))
        for i, p in zip(idx, sample_poses(arm, times)):
            poses[i] = p
        if k == len(job["segments"]) - 1 and not job.get("display"):
            display, display_objs = arm, objs  # keep the last import (its mesh variant) as the display rig
            arm.animation_data_clear()
        else:
            for o in objs:
                bpy.data.objects.remove(o, do_unlink=True)
    if job.get("display"):
        display, display_objs = import_glb(ROOT / job["display"])
        display.animation_data_clear()
    # Transition blend from frozen previous pose.
    blend_frames = max(1, int(round(job.get("blend", 0.1) * FPS)))
    frozen = None
    start_of = {}
    for i, (k, _) in enumerate(timeline):
        start_of.setdefault(k, i)
    final = []
    for i, (k, _) in enumerate(timeline):
        p = poses[i]
        if k > 0:
            s0 = start_of[k]
            frozen = poses[s0 - 1]
            w = min(1.0, (i - s0 + 1) / blend_frames)
            if w < 1.0:
                p = {n: mix(frozen[n], p[n], w) for n in p if n in frozen}
        final.append(p)
    sword_objs = attach_sword(display)
    drawn = [o for o in list(display_objs) + sword_objs if o.type in ("MESH", "EMPTY") and o is not display]
    hips = display.pose.bones["Hips"]
    mode = job.get("camera", "hips")
    ortho = job.get("ortho", 2.1)
    if mode == "fixed":
        xs = [o.x for o in offsets]; ys = [o.y for o in offsets]
        centre = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, 0))
        ortho = max(ortho, max(max(xs) - min(xs), max(ys) - min(ys)) + 1.2)
    cam.data.ortho_scale = ortho
    # Round 1: one fixed facing for every clip (the approved 1H idle's mesh forward), so front/side are
    # true mesh-space views and lateral motion reads as lateral regardless of the clip's foot direction.
    fwd = CANON_FWD.copy()
    right = Vector((fwd.y, -fwd.x, 0))  # knight's right when facing fwd with Z up
    views = {"front": fwd * 3 + Vector((0, 0, .4)), "side": right * 3 + Vector((0, 0, .4)),
             "threequarter": (fwd * 3 + right * 2) + Vector((0, 0, .5)), "top": Vector((0, 0, 3.0))}
    views = {v: views[v] for v in job.get("views", ["front", "side", "threequarter"])}
    # top: camera X (image right) = knight's right, camera Y (image up) = boss forward, looking down -Z
    top_rot = Matrix((right, fwd, Vector((0, 0, 1)))).transposed().to_euler()
    folder = OUT / "frames" / job["label"]
    folder.mkdir(parents=True, exist_ok=True)
    s = bpy.context.scene
    for i, p in enumerate(final):
        for b in display.pose.bones:
            if b.name in p:
                b.matrix_basis = p[b.name]
        display.location = offsets[i]
        for o in drawn:
            o.hide_render = hidden[i]
        bpy.context.view_layer.update()
        if mode == "fixed":
            focus = centre + Vector((0, 0, .5))
        elif mode == "root":
            focus = Vector((offsets[i].x, offsets[i].y, .5))
        else:
            h = display.matrix_world @ hips.head
            focus = Vector((h.x, h.y, .5))
        for view, off in views.items():
            cam.location = focus + Vector(off)
            if view == "top":
                cam.rotation_euler = top_rot
            else:
                cam.rotation_euler = (focus - cam.location).to_track_quat("-Z", "Y").to_euler()
            s.render.filepath = str(folder / f"{view}_{i:04d}.png")
            if DRY:
                continue
            bpy.ops.render.render(write_still=True)
    print("DRY" if DRY else "RENDERED", job["label"], len(final), "hidden", sum(hidden), "root_end_rig_m", tuple(round(x, 3) for x in offsets[-1]), "camera", mode, "ortho", round(ortho, 2), flush=True)


def canonical_forward():
    clear()
    arm, _ = import_glb(ROOT / "Local/CustomuseAssets/Polish20261025/knight/IdleOneHand_Blender_v2r4.glb")
    bpy.context.scene.frame_set(0)
    mw = arm.matrix_world; pb = arm.pose.bones
    toes = (mw @ pb["LeftToeBase"].head + mw @ pb["RightToeBase"].head) / 2
    heels = (mw @ pb["LeftFoot"].head + mw @ pb["RightFoot"].head) / 2
    f = toes - heels; f.z = 0
    return f.normalized()


CANON_FWD = canonical_forward()
print("CANONICAL_FORWARD", tuple(round(x, 3) for x in CANON_FWD), flush=True)
for job in JOBS:
    if (OUT / "frames" / job["label"] / (job.get("views", ["threequarter"])[-1] + "_0000.png")).exists() and not job.get("force") and not DRY:
        print("SKIP", job["label"])
        continue
    render_job(job)
