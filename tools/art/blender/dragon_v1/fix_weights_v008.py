"""Rig v008: move legacy tripo::Head_1 weights (front-right shoulder skin parented under the
hind-right hip chain) onto the mirrored left-side distribution; drop sub-0.4% legacy weights.
Geometry, bones, rest pose untouched. Source GLB untouched."""
import bpy, json
import numpy as np
from pathlib import Path
from mathutils import kdtree, Vector
W = Path('/Users/midir/veyr-review-fable-20261021/Local/Blender/dragon-v1-20261021')
me = bpy.data.objects['tripo_node_c2f64f2b-a633-4e6f-accb-09e66']; m=me.data
exec(open('/Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_v1/load_base.py').read())
me = bpy.data.objects['tripo_node_c2f64f2b-a633-4e6f-accb-09e66']; m=me.data
assert me.get('rig_version') is None, 'already fixed'
gi = {g.index:g.name for g in me.vertex_groups}; gn={v:k for k,v in gi.items()}
MIR = {'bone_6':'bone_11','bone_7':'tripo::0_Left_Limb_0','tripo::1_Left_Limb_0':'tripo::0_Left_Limb_1','bone_9':'bone_14','tripo::1_Left_Limb_1':'tripo::0_Left_Limb_2',
       'tripo::Spine_2':'tripo::Spine_3'}
for k in ('Root','Elbow','Membrane','Wrist','Tip'): MIR['VeyrWingNegZ'+k]='VeyrWingPosZ'+k
for k in range(5): MIR[f'tripo::1_Right_Limb_{k}']=f'tripo::0_Right_Limb_{k}'
LEGACY = {'tripo::Head_0','tripo::Head_1','tripo::Head_2','tripo::Head_3','bone_36','bone_37','tripo::Root'}
co = np.array([v.co for v in m.vertices])
left = np.where(co[:,1] > 0.0)[0]
kd = kdtree.KDTree(len(left))
for i in left: kd.insert(Vector(co[i]), int(i))
kd.balance()
def weights(i): return {gi[g.group]: g.weight for g in m.vertices[i].groups if g.weight>0}
new = {}; changed_head1=0; changed_micro=0; maxdelta=0
for v in m.vertices:
    w = weights(v.index)
    if not (set(w) & LEGACY): continue
    h1 = w.pop('tripo::Head_1', 0.)
    micro = sum(w.pop(b,0.) for b in list(w) if b in LEGACY)
    out = dict(w)
    if h1 > 1e-4:
        c=Vector(co[v.index]); c.y=-c.y
        acc={}; tot=0
        for (_, j, d) in kd.find_n(c, 4):
            wt = 1.0/max(d,1e-4); tot+=wt
            for b,x in weights(j).items():
                if b in LEGACY: continue
                b2 = MIR.get(b, b)
                acc[b2]=acc.get(b2,0)+x*wt
        s=sum(acc.values())
        for b,x in acc.items(): out[b]=out.get(b,0)+h1*x/s
        changed_head1+=1
    else: changed_micro+=1
    items=sorted(out.items(), key=lambda x:-x[1])[:4]; s=sum(x for _,x in items)
    new[v.index]={b:x/s for b,x in items}
for i,w in new.items():
    for gidx in [g.group for g in m.vertices[i].groups]:
        me.vertex_groups[gidx].remove([i])
    for b,x in w.items():
        me.vertex_groups[b].add([i], x, 'REPLACE')
me['rig_version']='v008-weightfix'
# verify
sums=[]; legacy_left=0; over4=0
for v in m.vertices:
    ws=[g.weight for g in v.groups if g.weight>0]; sums.append(sum(ws)); over4+=len(ws)>4
    legacy_left+=any(gi[g.group] in LEGACY and g.weight>0 for g in v.groups)
rep={'head1_reassigned':changed_head1,'micro_cleaned':changed_micro,'sum_min':min(sums),'sum_max':max(sums),'legacy_weighted_verts':legacy_left,'over4':over4}
(W/'reports/rig_v008_weightfix.json').write_text(json.dumps(rep,indent=1))
s=bpy.context.scene
bpy.ops.wm.save_as_mainfile(filepath=str(W/'Dragon_Rig_v008_weightfix.blend'), compress=True)
s['session_owner']='fable-veyr-dragon-20261021'
print(json.dumps(rep))
