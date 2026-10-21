"""Knight deform-mesh skin-weight fix for feedback v4 (LEG 0, 2026-10-21).

Problem: thin armour pieces under the left armpit (a side strap, inner-elbow and cuff
shards, side breastplate plates) are skinned partly to the left arm chain and partly
to Spine*/Hips (some even to LeftUpLeg). When the left arm leaves the body the mixed
linear-blend weights stretch them into a dark armpit-to-hip line.

Fix (per connected mesh island, so every armour shard moves as one piece):
  candidate = island mixes arm-chain weight and foreign (torso/leg) weight, each > 3 %,
              stretches > 1.2 cm in a raised-arm test pose, and lies below the shoulder (z < .765);
  class     = arm if its summed arm-chain weight >= its summed foreign weight, else torso;
  arm   -> drop all weights except <Side>Shoulder/Arm/ForeArm/Hand*; renormalise;
  torso -> drop <Side>Arm/ForeArm/Hand* weights; renormalise.
Vertices left without weight take the island's average of the kept groups.

Functions (run in the owned Blender via run.py):
  build_body(side='Left', frames=(200,))  heal scene must be open (raised-arm test pose);
       computes the fix on its body, writes a NEW body file
       <out>/body/Knight_Body_StrapFix_v4.blend (+ weights JSON); never saves the scene.
  apply_body()  copies the saved v4 weights onto the open scene's body (vertex count and
       rest positions must match); tags scene['strap_fix_v4']=<weights sha256>.
The approved body inside the approved/v3 scenes is never modified on disk.
"""
from pathlib import Path
import bpy, bmesh, json, hashlib, importlib.util
from collections import defaultdict
HERE = Path(__file__).resolve().parent
_cs = importlib.util.spec_from_file_location('veyr_v4_common', HERE / 'common.py'); cm = importlib.util.module_from_spec(_cs); _cs.loader.exec_module(cm)
P = cm.params(globals().get('VEYR_V4_PARAMS'))
BODY_DIR = P['out'] / 'body'
BODY_BLEND = BODY_DIR / 'Knight_Body_StrapFix_v4.blend'
BODY_JSON = BODY_DIR / 'Knight_Body_StrapFix_v4.weights.json'


def _body():
    s = bpy.context.scene
    return next(o for o in s.objects if o.type == 'MESH' and o.get('export_body') and not o.get('review_prop'))


def _islands(mesh):
    bm = bmesh.new(); bm.from_mesh(mesh); bm.verts.ensure_lookup_table()
    isl = [-1] * len(bm.verts); n = 0
    for v in bm.verts:
        if isl[v.index] >= 0: continue
        st = [v]; isl[v.index] = n
        while st:
            x = st.pop()
            for e in x.link_edges:
                y = e.other_vert(x)
                if isl[y.index] < 0: isl[y.index] = n; st.append(y)
        n += 1
    bm.free(); mem = defaultdict(list)
    for i, k in enumerate(isl): mem[k].append(i)
    return isl, mem


def _stretch(body, isl, frames):
    s = bpy.context.scene; rest = [v.co.copy() for v in body.data.vertices]; st = defaultdict(float)
    for fr in frames:
        s.frame_set(fr); dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh()
        co = [v.co.copy() for v in me.vertices]; ev.to_mesh_clear()
        for e in body.data.edges:
            a, b = e.vertices; d = (co[a] - co[b]).length - (rest[a] - rest[b]).length
            if d > st[isl[a]]: st[isl[a]] = d
    return st


def _weights(body):
    gid = {g.index: g.name for g in body.vertex_groups}
    return [{gid[g.group]: g.weight for g in v.groups if g.weight > 0} for v in body.data.vertices]


def compute(side='Left', frames=(200,)):
    body = _body(); V = body.data.vertices; W = _weights(body)
    arm = (side + 'Arm', side + 'ForeArm', side + 'Hand'); shoulder = side + 'Shoulder'
    def cls(n): return 'arm' if n.startswith(arm) else 'sh' if n == shoulder else 'for'
    isl, mem = _islands(body.data); st = _stretch(body, isl, frames)
    new = {}; report = []
    for k, vs in mem.items():
        w = defaultdict(float)
        for i in vs:
            for n, x in W[i].items(): w[cls(n)] += x
        tot = sum(w.values()) or 1.
        cz = sum(V[i].co.z for i in vs) / len(vs)
        if not (w['arm'] / tot > .03 and w['for'] / tot > .03 and st[k] > .012 and cz < .765): continue
        label = 'arm' if w['arm'] >= w['for'] else 'torso'
        drop = (lambda n: cls(n) == 'for') if label == 'arm' else (lambda n: cls(n) == 'arm')
        avg = defaultdict(float)
        for i in vs:
            for n, x in W[i].items():
                if not drop(n): avg[n] += x
        at = sum(avg.values())
        for i in vs:
            keep = {n: x for n, x in W[i].items() if not drop(n)}
            if sum(keep.values()) < 1e-4: keep = {n: x / at for n, x in avg.items()}
            t = sum(keep.values()); new[i] = {n: x / t for n, x in keep.items()}
        report.append({'island': k, 'verts': len(vs), 'class': label, 'stretchBefore': round(st[k], 4), 'armFrac': round(w['arm'] / tot, 3), 'foreignFrac': round(w['for'] / tot, 3)})
    return new, report


def _apply(body, new):
    VG = body.vertex_groups
    for i, ws in new.items():
        i = int(i)
        for g in list(body.data.vertices[i].groups):
            n = body.vertex_groups[g.group].name
            if n not in ws: VG[n].remove([i])
        for n, x in ws.items(): VG[n].add([i], x, 'REPLACE')
    body.data.update()


def _digest(new):
    return hashlib.sha256(json.dumps({str(k): {n: round(x, 6) for n, x in sorted(v.items())} for k, v in sorted(new.items(), key=lambda kv: int(kv[0]))}, sort_keys=True).encode()).hexdigest()


def _rest_hash(body):
    return hashlib.sha256(b''.join(v.co.to_tuple(6).__repr__().encode() for v in body.data.vertices)).hexdigest()


def _paths(rest_hash, default=False):
    if default: return BODY_BLEND, BODY_JSON
    stem = 'Knight_Body_StrapFix_v4_' + rest_hash[:10]
    return BODY_DIR / (stem + '.blend'), BODY_DIR / (stem + '.weights.json')


def build_body(side='Left', frames=(200,), default=True):
    s = bpy.context.scene
    assert s.get('session_owner') == P['owner']
    body = _body(); rest_hash = _rest_hash(body)
    before = _stretch(body, _islands(body.data)[0], frames)
    new, report = compute(side, frames); _apply(body, new)
    after = _stretch(body, _islands(body.data)[0], frames)
    digest = _digest(new)
    cm.check_writable(BODY_DIR); BODY_DIR.mkdir(parents=True, exist_ok=True)
    blend_p, json_p = _paths(rest_hash, default)
    if blend_p.exists() and not P['allow_overwrite']: raise FileExistsError(blend_p)
    json_p.write_text(json.dumps({'side': side, 'testFrames': list(frames), 'testScene': bpy.data.filepath, 'vertexCount': len(body.data.vertices),
                                     'restPositionsSHA256': rest_hash, 'weightsSHA256': digest, 'islands': report,
                                     'weights': {str(k): v for k, v in sorted(new.items())}}, indent=1))
    rig = bpy.data.objects['Knight_Deform']; body['strap_fix_v4'] = digest
    bpy.data.libraries.write(str(blend_p), {body, body.data, rig, rig.data}, fake_user=True, compress=True)
    s['strap_fix_v4'] = digest
    def top(d): return sorted(((round(v, 3)) for v in d.values()), reverse=True)[:6]
    return {'body': str(blend_p), 'weights': str(json_p), 'restSHA256': rest_hash, 'sha256Weights': digest, 'changedVertices': len(new), 'islands': len(report),
            'islandStretchTopBefore': top(before), 'islandStretchTopAfter': top(after),
            'islandsOver5cmBefore': sum(1 for v in before.values() if v > .05), 'islandsOver5cmAfter': sum(1 for v in after.values() if v > .05)}


def apply_body(auto_frames=None):
    """Copy the saved v4 strap-fix weights matching this body (by rest-position hash) onto the
    open scene. Bodies imported from different approved GLBs differ; if none matches and
    auto_frames is given, build that body's fix first (same rule) and save it as a new file."""
    s = bpy.context.scene
    assert s.get('session_owner') == P['owner']
    body = _body()
    if body.get('strap_fix_v4') and s.get('strap_fix_v4') == body.get('strap_fix_v4'):
        return {'already': True, 'sha256Weights': body['strap_fix_v4']}
    rh = _rest_hash(body); data = None
    for jp in sorted(BODY_DIR.glob('*.weights.json')):
        d = json.loads(jp.read_text())
        if d['restPositionsSHA256'] == rh: data = d; break
    if data is None:
        if auto_frames is None: raise LookupError('no v4 strap-fix body for this mesh; pass auto_frames')
        r = build_body('Left', tuple(auto_frames), default=False); r['built'] = True; return r
    assert len(body.data.vertices) == data['vertexCount']
    _apply(body, data['weights']); body['strap_fix_v4'] = data['weightsSHA256']; s['strap_fix_v4'] = data['weightsSHA256']
    return {'applied': len(data['weights']), 'sha256Weights': data['weightsSHA256'], 'file': str(jp)}
