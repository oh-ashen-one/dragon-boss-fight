"""Headless EEVEE frame render of one prepared clip from three fixed cameras.

Usage: blender -b --factory-startup work/prepared_<label>.blend --python scripts/render_clip.py -- <label> [--test]

Camera, light, ground and world are built from constants in this file only, so every label gets
bit-identical set-up. Frames: t = i/24 s, i = 0..floor(duration*24) inclusive, written as PNGs to
frames/<label>/<camera>/f_%04d.png (encoded to MP4 by scripts/encode.sh).
"""
import bpy, sys, math
from pathlib import Path
from mathutils import Vector

ROOT = Path(__import__("os").environ.get("REVIEW_ROOT", Path(__file__).resolve().parents[2] / "Local/dragon-review-20261029"))
args = sys.argv[sys.argv.index("--") + 1:]
label = args[0]
TEST = "--test" in args
TALL = "--tall" in args or "--xtall" in args
XTALL = "--xtall" in args
sc = bpy.context.scene

# ---------------- fixed set-up (identical for every clip) ----------------
TARGET = Vector((0.0, 0.0, 0.24))
CAMS = {   # name: position  (dragon at origin, faces +X, left side = +Y)
    "front":        Vector((2.30, 0.00, 0.50)),
    "left":         Vector((0.00, 2.30, 0.40)),
    "threequarter": Vector((1.65, 1.65, 0.80)),
}
if TALL:   # airborne moves: 1.35x farther and aimed higher, so a 0.75 m hop stays in shot (frame height 1.26 m at the target)
    TARGET = Vector((0.0, 0.0, 0.40))
    CAMS = {"front": Vector((3.10, 0.00, 0.55)), "left": Vector((0.00, 3.10, 0.45)), "threequarter": Vector((2.20, 2.20, 0.95))}
    if XTALL:   # a rise to 1.2 m: frame height 1.7 m around z 0.62
        TARGET = Vector((0.0, 0.0, 0.62))
        CAMS = {"front": Vector((4.20, 0.00, 0.70)), "left": Vector((0.00, 4.20, 0.65)), "threequarter": Vector((3.00, 3.00, 1.15))}
LENS_MM = 50.0
RES = (960, 540)
FPS = 24
WORLD_GREY = 0.30      # linear
GROUND_A, GROUND_B = 0.18, 0.22   # faint two-tone checker (0.25-unit squares) for foot-slide reference
SUN_ROT = (math.radians(50), math.radians(10), math.radians(35))
SUN_ENERGY = 3.0

# ---------------- clip timing ----------------
act = bpy.data.objects["DragonArmature"].animation_data.action
f0, f1 = int(round(act.frame_range[0])), int(round(act.frame_range[1]))
fps_native = sc.render.fps / sc.render.fps_base
duration = (f1 - f0) / fps_native
n = int(math.floor(duration * FPS + 1e-6)) + 1

# ---------------- scene ----------------
engines = [i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
eevee = next(e for e in engines if e.startswith("BLENDER_EEVEE"))
sc.render.engine = eevee
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = RES[0], RES[1], 100
sc.render.film_transparent = False
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGB"
sc.view_settings.view_transform = "Standard"
sc.view_settings.look = "None"
sc.view_settings.exposure = 0.0
sc.view_settings.gamma = 1.0
sc.display_settings.display_device = "sRGB"
if hasattr(sc.render, "use_motion_blur"):
    sc.render.use_motion_blur = False
try:
    sc.eevee.taa_render_samples = 32
except Exception:
    pass
for attr in ("use_bloom", "use_gtao", "use_ssr", "use_raytracing"):
    if hasattr(sc.eevee, attr):
        try: setattr(sc.eevee, attr, False)
        except Exception: pass

# world: plain grey
w = bpy.data.worlds.new("GreyWorld"); w.use_nodes = True
bg = next(nd for nd in w.node_tree.nodes if nd.type == "BACKGROUND")
bg.inputs["Color"].default_value = (WORLD_GREY, WORLD_GREY, WORLD_GREY, 1.0); bg.inputs["Strength"].default_value = 1.0
sc.world = w

# ground (flat, faint checker)
bpy.ops.mesh.primitive_plane_add(size=24.0, location=(0, 0, 0)); g = bpy.context.active_object; g.name = "Ground"
gm = bpy.data.materials.new("GroundMat"); gm.use_nodes = True
nt = gm.node_tree; nt.nodes.clear()
out = nt.nodes.new("ShaderNodeOutputMaterial"); bsdf = nt.nodes.new("ShaderNodeBsdfDiffuse")
chk = nt.nodes.new("ShaderNodeTexChecker"); tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping")
mp.inputs["Scale"].default_value = (96.0, 96.0, 96.0)   # plane spans 24 units, 96 checks across = 0.25-unit squares
chk.inputs["Scale"].default_value = 1.0
chk.inputs["Color1"].default_value = (GROUND_A, GROUND_A, GROUND_A, 1); chk.inputs["Color2"].default_value = (GROUND_B, GROUND_B, GROUND_B, 1)
nt.links.new(tc.outputs["UV"], mp.inputs["Vector"]); nt.links.new(mp.outputs["Vector"], chk.inputs["Vector"])
nt.links.new(chk.outputs["Color"], bsdf.inputs["Color"]); nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
g.data.materials.append(gm)

# one sun
bpy.ops.object.light_add(type="SUN", location=(0, 0, 5)); sun = bpy.context.active_object; sun.name = "Sun"
sun.rotation_euler = SUN_ROT; sun.data.energy = SUN_ENERGY; sun.data.angle = math.radians(8)

# cameras
cams = {}
for name, pos in CAMS.items():
    cd = bpy.data.cameras.new("cam_" + name); cd.lens = LENS_MM; cd.sensor_width = 36.0; cd.clip_start = 0.05; cd.clip_end = 100
    co = bpy.data.objects.new("cam_" + name, cd); sc.collection.objects.link(co)
    co.location = pos
    co.rotation_euler = (TARGET - pos).to_track_quat("-Z", "Y").to_euler()
    cams[name] = co

sc.render.fps = FPS; sc.render.fps_base = 1.0   # output rate (animation already sampled by time above)
idxs = range(n) if not TEST else [0, n // 2]
for name, co in cams.items():
    sc.camera = co
    d = ROOT / "frames" / label / name; d.mkdir(parents=True, exist_ok=True)
    for i in idxs:
        # sample by clip time, independent of the scene fps override above
        fr = f0 + (i / FPS) * fps_native
        fi = int(math.floor(fr + 1e-6)); sub = max(0.0, fr - fi)
        sc.frame_set(fi, subframe=sub if sub > 1e-6 else 0.0)
        sc.render.filepath = str(d / f"f_{i:04d}.png")
        bpy.ops.render.render(write_still=True)
    print("CAM_DONE", label, name, len(list(idxs)), flush=True)
print("RENDER_DONE", label, n, flush=True)
