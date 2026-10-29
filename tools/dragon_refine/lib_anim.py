"""Shared helpers for the dragon idle refinement (run inside Blender)."""
import bpy, math
import numpy as np
from mathutils import Quaternion, Vector, Matrix

FEET = {  # foot bone: chain (root..foot), as given in the brief
    "bone_9": ["bone_6", "bone_7", "tripo::1_Left_Limb_0", "bone_9"],
    "bone_14": ["bone_11", "tripo::0_Left_Limb_0", "tripo::0_Left_Limb_1", "bone_14"],
    "tripo::1_Right_Limb_4": [f"tripo::1_Right_Limb_{i}" for i in range(5)],
    "tripo::0_Right_Limb_4": [f"tripo::0_Right_Limb_{i}" for i in range(5)],
}
FOOT_LABEL = {"bone_9": "front+Y", "bone_14": "front-Y", "tripo::1_Right_Limb_4": "hind+Y", "tripo::0_Right_Limb_4": "hind-Y"}
TAIL = ["tripo::Tail_0", "tripo::Tail_1", "tripo::Tail_2"]

def fcurves(act):
    return [fc for l in act.layers for st in l.strips for cb in st.channelbags for fc in cb.fcurves]

def channelbag(act):
    return act.layers[0].strips[0].channelbags[0]

def bone_of(path):
    return path.split('"')[1] if path.startswith("pose.bones[") else None

def read_channels(act, frames):
    """{bone: {'q': [F,4] or None, 'l': [F,3] or None}} sampled at integer frames."""
    out = {}
    for fc in fcurves(act):
        b = bone_of(fc.data_path)
        kind = "q" if fc.data_path.endswith("rotation_quaternion") else ("l" if fc.data_path.endswith(".location") else None)
        if b is None or kind is None:
            continue
        d = out.setdefault(b, {})
        n = 4 if kind == "q" else 3
        if kind not in d:
            d[kind] = np.zeros((len(frames), n))
        d[kind][:, fc.array_index] = [fc.evaluate(f) for f in frames]
    for b, d in out.items():
        if "q" in d:  # hemisphere continuity
            q = d["q"]
            q /= np.linalg.norm(q, axis=1, keepdims=True)
            for i in range(1, len(q)):
                if np.dot(q[i], q[i - 1]) < 0: q[i] = -q[i]
    return out

def write_channels(act, ch, nframes):
    """Replace every key of every bone channel with per-frame keys 0..nframes-1 from ch."""
    for fc in fcurves(act):
        b = bone_of(fc.data_path)
        kind = "q" if fc.data_path.endswith("rotation_quaternion") else ("l" if fc.data_path.endswith(".location") else None)
        if b not in ch or kind not in ch[b]:
            continue
        vals = ch[b][kind][:nframes, fc.array_index]
        interp = fc.keyframe_points[0].interpolation if len(fc.keyframe_points) else "LINEAR"
        fc.keyframe_points.clear()
        fc.keyframe_points.add(nframes)
        co = np.empty(2 * nframes); co[0::2] = np.arange(nframes); co[1::2] = vals
        fc.keyframe_points.foreach_set("co", co)
        for kp in fc.keyframe_points: kp.interpolation = interp
        fc.update()

def qang(a, b):
    d = abs(float(np.dot(a, b)))
    return 2.0 * math.acos(min(1.0, d))

def rot_speed(ch, nf, cyclic=False):
    """per-frame summed local rotation step (rad) over all bones; len nf-1 (or nf if cyclic, last = seam)."""
    m = nf if cyclic else nf - 1
    s = np.zeros(m); per = {}
    for b, d in ch.items():
        if "q" not in d: continue
        q = d["q"]
        st = np.array([qang(q[i], q[(i + 1) % nf]) for i in range(m)])
        per[b] = st; s += st
    return s, per

def slerp(a, b, t):
    return np.array(Quaternion(a).slerp(Quaternion(b), t))

def smoothstep(x):
    return x * x * (3 - 2 * x)

def frame_eval(sc, f):
    sc.frame_set(int(f))
    return bpy.context.evaluated_depsgraph_get()

def world_points(A, frames, sc, bones_head=(), bones_tail=(), mats=()):
    """world-space heads/tails and full matrices for given bones over frames, from the evaluated pose."""
    H = {b: [] for b in bones_head}; T = {b: [] for b in bones_tail}; Ms = {b: [] for b in mats}
    for f in frames:
        dg = frame_eval(sc, f); Ae = A.evaluated_get(dg); mw = Ae.matrix_world
        for b in bones_head: H[b].append(np.array(mw @ Ae.pose.bones[b].head))
        for b in bones_tail: T[b].append(np.array(mw @ Ae.pose.bones[b].tail))
        for b in mats: Ms[b].append(mw @ Ae.pose.bones[b].matrix)
    return {k: np.array(v) for k, v in H.items()}, {k: np.array(v) for k, v in T.items()}, Ms

def mesh_coords(M, sc, frames, idx):
    out = []
    for f in frames:
        dg = frame_eval(sc, f); Me = M.evaluated_get(dg); me = Me.to_mesh()
        co = np.empty(len(me.vertices) * 3, dtype=np.float32); me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)[idx]
        mw = np.array(Me.matrix_world)
        co = co @ mw[:3, :3].T + mw[:3, 3]
        out.append(co); Me.to_mesh_clear()
    return np.array(out)

def foot_vertex_sets(M, A, frame0_world, sc):
    """Vertices in the lowest 3 cm of the mesh nearest each foot bone (xy), at the current frame."""
    dg = frame_eval(sc, 0); Me = M.evaluated_get(dg); me = Me.to_mesh()
    co = np.empty(len(me.vertices) * 3, dtype=np.float32); me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3); Me.to_mesh_clear()
    zmin = co[:, 2].min()
    low = np.where(co[:, 2] < zmin + 0.03)[0]
    sets = {}
    for foot, p in frame0_world.items():
        d = np.linalg.norm(co[low, :2] - p[:2], axis=1)
        sets[foot] = low[d < 0.06]
    return sets, float(zmin), float(co[:, 2].max())
