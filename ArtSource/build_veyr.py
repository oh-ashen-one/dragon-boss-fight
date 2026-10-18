"""Veyr temporary anatomical blockout and reusable action rig.
Original authored geometry; NOT the final Tripo asset.
Run: blender --background --threads 2 --python ArtSource/build_veyr.py
"""
import bpy, math, json, os
from mathutils import Vector
from pathlib import Path

OUT = Path(__file__).resolve().parent
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.render.fps = 30
scene.unit_settings.system = 'METRIC'
scene['asset_status'] = 'TEMPORARY ORIGINAL BLOCKOUT — REPLACE MAIN MESH WITH APPROVED TRIPO ASSET'
parts = []
bone_defs = {}

def material(name, color, rough=.62, metal=.05, emission=0):
    m = bpy.data.materials.new(name); m.diffuse_color = (*color, 1)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Metallic'].default_value = metal
    bsdf.inputs['Emission Color'].default_value = (*color, 1)
    bsdf.inputs['Emission Strength'].default_value = emission
    return m

hide = material('TEMP | charcoal volcanic scales', (.075,.095,.105), .7, .12)
armor = material('TEMP | oxidized obsidian plates', (.15,.20,.22), .4, .3)
horn = material('TEMP | pale basalt horn', (.43,.40,.30), .56, .1)
wing = material('TEMP | burnt bronze wing membrane', (.24,.12,.075), .85)
ember = material('TEMP | cinder fissures', (1,.19,.025), .35, .1, 2)
eye = material('TEMP | amber eyes', (1,.63,.08), .25, 0, 5)

def bone(name, head, tail, parent=None):
    bone_defs[name] = (head,tail,parent)

bone('root',(0,0,0),(0,0,1))
bone('body',(0,1.5,4),(0,-1.5,4.2),'root')
bone('chest',(0,-1.5,4.2),(0,-3,4.6),'body')
bone('neck_01',(0,-3,4.6),(0,-4.9,5.2),'chest')
bone('neck_02',(0,-4.9,5.2),(0,-6.4,5.1),'neck_01')
bone('head',(0,-6.4,5.1),(0,-8.2,4.7),'neck_02')
bone('jaw',(0,-6.8,4.75),(0,-8.5,4.45),'head')
for i in range(5):
    bone('tail_%02d'%i,(0,2+i*1.65,4-i*.48),(0,3.65+i*1.65,3.52-i*.48),'body' if i==0 else 'tail_%02d'%(i-1))
for side,sign in [('L',1),('R',-1)]:
    for limb,y in [('fore',-2.4),('hind',1.7)]:
        n=f'{limb}_{side}'
        bone(n+'_upper',(sign*1.35,y,4),(sign*2.1,y+.38,2.45),'chest' if limb=='fore' else 'body')
        bone(n+'_lower',(sign*2.1,y+.38,2.45),(sign*2.4,y-.3,.62),n+'_upper')
        bone(n+'_foot',(sign*2.4,y-.3,.62),(sign*2.4,y-1.25,.3),n+'_lower')
    bone('wing_'+side+'_upper',(sign*1.15,-1.9,4.8),(sign*4,-.3,6.6),'chest')
    bone('wing_'+side+'_tip',(sign*4,-.3,6.6),(sign*5.5,3.4,4.1),'wing_'+side+'_upper')

def assign(ob, name, mat):
    ob.name = 'TEMP_'+name
    ob.data.materials.append(mat)
    for p in ob.data.polygons: p.use_smooth=True
    group = ob.vertex_groups.new(name=name)
    group.add(list(range(len(ob.data.vertices))),1,'REPLACE')
    parts.append(ob)
    return ob

def ellipsoid(loc, scale, b, mat=hide, segments=16, rings=10):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments,ring_count=rings,location=loc)
    ob=bpy.context.object; ob.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    return assign(ob,b,mat)

def tapered(a,b,r1,r2,bn,mat=hide,vertices=12):
    a,b=Vector(a),Vector(b); d=b-a
    bpy.ops.mesh.primitive_cone_add(vertices=vertices,radius1=r1,radius2=r2,depth=d.length,location=(a+b)/2)
    ob=bpy.context.object; ob.rotation_euler=d.to_track_quat('Z','Y').to_euler()
    bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
    return assign(ob,bn,mat)

ellipsoid((0,.3,4.1),(1.85,3.1,1.35),'body')
ellipsoid((0,-2.1,4.35),(1.65,1.4,1.55),'chest')
for bn in ['neck_01','neck_02']:
    a,b,_=bone_defs[bn]; tapered(a,b,.85 if bn=='neck_01' else .65,.62 if bn=='neck_01' else .48,bn)
    ellipsoid(a,(.8,.8,.8),bn)
ellipsoid((0,-7.25,5),(1,.98,.65),'head',armor)
ellipsoid((0,-8.05,4.75),(.72,.95,.36),'head')
ellipsoid((0,-7.85,4.4),(.66,1.02,.18),'jaw',armor)
for s in [-1,1]:
    ellipsoid((s*.84,-7.55,5.22),(.14,.25,.12),'head',eye)
    tapered((s*.68,-6.9,5.4),(s*1.1,-5.7,6.65),.35,0,'head',horn)
    tapered((s*.85,-7.1,5.12),(s*1.55,-6.5,5.7),.25,0,'head',horn)
    for j in range(4):
        tapered((s*.56,-7.3-j*.34,4.6),(s*.52,-7.3-j*.34,4.27),.085,0,'head',horn,8)
for i in range(5):
    a,b,_=bone_defs['tail_%02d'%i]
    tapered(a,b,.9-i*.16,.76-i*.16,'tail_%02d'%i)
    tapered((0,a[1],a[2]+.55),(0,a[1]+.5,a[2]+1.15-i*.13),.33-i*.045,0,'tail_%02d'%i,armor)
for side,s in [('L',1),('R',-1)]:
    for limb,y in [('fore',-2.4),('hind',1.7)]:
        n=f'{limb}_{side}'
        for section,r1,r2 in [('upper',.75,.55),('lower',.48,.3),('foot',.35,.26)]:
            a,b,_=bone_defs[n+'_'+section]
            tapered(a,b,r1,r2,n+'_'+section)
            ellipsoid(a,(r1,r1,r1),n+'_'+section,armor if section=='lower' else hide)
        for toe in range(3):
            x=s*2.4+(toe-1)*.3
            tapered((x,y-.9,.3),(x,y-1.8,.14),.19,0,n+'_foot',horn)
        ellipsoid((s*2.22,y+.2,2.54),(.48,.48,.38),n+'_lower',ember)
    for section in ['upper','tip']:
        a,b,_=bone_defs['wing_'+side+'_'+section]
        tapered(a,b,.26,.12,'wing_'+side+'_'+section,armor)
    # Separate rigid membrane panels keep the folded silhouette clear in blockout.
    verts=[(s*1.3,-1.6,4.65),(s*4,-.3,6.6),(s*5.5,3.4,4.1),(s*3.7,2.8,4.6),(s*2.8,3.8,3.8),(s*1.35,1.6,4.2)]
    mesh=bpy.data.meshes.new('TEMP_membrane');mesh.from_pydata(verts,[],[(0,1,3),(1,2,3),(0,3,5),(3,4,5)])
    ob=bpy.data.objects.new('TEMP_wing_membrane',mesh);bpy.context.collection.objects.link(ob)
    assign(ob,'wing_'+side+'_upper',wing)
    # Low-profile dorsal armor and forward swept rib structures.
    for j in range(3):
        tapered((s*(1.3+j*.2),-.6+j*.9,4.8),(s*(2.15+j*.2),-.1+j*1.0,5.4),.25,0,'body',armor)
for y in [-2,-1,0,1,2]:
    ellipsoid((0,y,5.25),(.75,.52,.2),'body' if y>=-1 else 'chest',armor)
    tapered((0,y,5.3),(0,y+.45,6),.35,0,'body' if y>=-1 else 'chest',horn)
    ellipsoid((0,y-.08,5.43),(.12,.35,.06),'body' if y>=-1 else 'chest',ember)

# Build reusable deform skeleton. Rest data doubles as the skinning guide.
armdata=bpy.data.armatures.new('Veyr_AnatomicalRig')
rig=bpy.data.objects.new('Veyr_Rig',armdata);bpy.context.collection.objects.link(rig)
bpy.context.view_layer.objects.active=rig;rig.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
for name,(head,tail,parent) in bone_defs.items():
    eb=armdata.edit_bones.new(name);eb.head=head;eb.tail=tail
    if parent: eb.parent=armdata.edit_bones[parent]
bpy.ops.object.mode_set(mode='OBJECT')
rig.show_in_front=True
bpy.ops.object.select_all(action='DESELECT')
for p in parts:p.select_set(True)
bpy.context.view_layer.objects.active=parts[0]
bpy.ops.object.join();mesh=bpy.context.object;mesh.name='TEMP_Veyr_Blockout_REPLACE_WITH_TRIPO'
mesh.parent=rig
mod=mesh.modifiers.new('Veyr deformation','ARMATURE');mod.object=rig
mesh['status']='Temporary original geometry. Not final generated asset.'
for p in rig.pose.bones:p.rotation_mode='XYZ'

def pose(frame, rotations=None, root=(0,0,0)):
    rotations=rotations or {}
    for p in rig.pose.bones:
        p.rotation_euler=tuple(math.radians(v) for v in rotations.get(p.name,(0,0,0)))
        p.location=root if p.name=='root' else (0,0,0)
        p.keyframe_insert('rotation_euler',frame=frame,group=p.name)
        p.keyframe_insert('location',frame=frame,group=p.name)

actions=[]
def action(name, keys):
    rig.animation_data_create();a=bpy.data.actions.new(name);rig.animation_data.action=a
    for fr,rot,loc in keys:pose(fr,rot,loc)
    a.use_fake_user=True
    actions.append({'name':name,'frames':keys[-1][0],'seconds':round((keys[-1][0]-1)/30,3)})
    rig.animation_data.action=None
    track=rig.animation_data.nla_tracks.new();track.name=name
    strip=track.strips.new(name,1,a);strip.name=name;track.mute=True
    return a

neutral={}
action('Idle',[(1,{},(0,0,0)),(46,{'chest':(2,0,0),'neck_01':(-3,0,1),'wing_L_upper':(0,2,2),'wing_R_upper':(0,-2,-2)},(0,0,.07)),(91,{},(0,0,0))])
walkA={};walkB={}
for n in ['fore_L','hind_R','fore_R','hind_L']:
    sign=1 if n in ['fore_L','hind_R'] else -1
    walkA[n+'_upper']=(sign*19,0,0);walkB[n+'_upper']=(-sign*19,0,0)
    walkA[n+'_lower']=(-max(0,sign)*22,0,0);walkB[n+'_lower']=(-max(0,-sign)*22,0,0)
action('Walk',[(1,walkA,(0,0,0)),(16,walkB,(0,0,.08)),(31,walkA,(0,0,0))])
stomp={'chest':(-12,0,-5),'fore_L_upper':(-62,0,0),'fore_L_lower':(40,0,0),'neck_01':(10,0,0)}
action('Stomp',[(1,{},(0,0,0)),(25,stomp,(0,0,.22)),(35,stomp,(0,0,.24)),(43,{'chest':(8,0,5),'fore_L_upper':(12,0,0)},(0,0,-.3)),(55,{'head':(8,0,0)},(0,0,-.1)),(80,{},(0,0,0))])
action('Bite',[(1,{},(0,0,0)),(24,{'neck_01':(-20,0,0),'neck_02':(-15,0,0),'jaw':(28,0,0)},(0,.3,.08)),(33,{'neck_01':(18,0,0),'neck_02':(12,0,0),'head':(15,0,0),'jaw':(4,0,0)},(0,-.35,-.15)),(43,{'neck_01':(20,0,0),'jaw':(0,0,0)},(0,-.2,-.15)),(72,{},(0,0,0))])
action('Breath',[(1,{},(0,0,0)),(30,{'neck_01':(-10,0,20),'head':(8,0,5),'jaw':(26,0,0)},(0,0,.1)),(43,{'neck_01':(13,0,25),'head':(15,0,10),'jaw':(20,0,0)},(0,0,-.1)),(105,{'neck_01':(13,0,-25),'head':(15,0,-10),'jaw':(20,0,0)},(0,0,-.1)),(130,{},(0,0,0))])
tailWind={'body':(0,0,-13),'chest':(0,0,8)}
tailHit={'body':(0,0,18),'chest':(0,0,-10)}
for i in range(5):tailWind['tail_%02d'%i]=(0,0,-18);tailHit['tail_%02d'%i]=(0,0,25-i*2)
action('Tail_Sweep',[(1,{},(0,0,0)),(31,tailWind,(0,0,.05)),(39,tailWind,(0,0,.05)),(53,tailHit,(0,0,0)),(70,tailHit,(0,0,0)),(100,{},(0,0,0))])
for n in ['fore_L','fore_R','hind_L','hind_R']:
    sign=1 if n.endswith('L') else -1
    buck={n+'_upper':(-42,0,sign*12),n+'_lower':(65,0,0),'body':(0,0,-sign*6),'neck_01':(-10,0,0)}
    action('Buckle_'+n,[(1,{},(0,0,0)),(8,buck,(0,0,-.25)),(24,buck,(0,0,-.22)),(46,{},(0,0,0))])
down={'body':(5,0,8),'chest':(8,0,-3),'neck_01':(23,0,0),'neck_02':(8,0,0),'head':(-18,0,0),'jaw':(12,0,0)}
for n in ['fore_L','fore_R','hind_L','hind_R']:
    down[n+'_upper']=(-50,0,10 if n.endswith('L') else -10)
    down[n+'_lower']=(82,0,0)
action('Collapse',[(1,{},(0,0,0)),(18,{'neck_01':(-12,0,0)},(0,0,.1)),(38,down,(0,0,-1.65)),(54,down,(0,0,-1.5)),(76,down,(0,0,-1.55))])
action('Stagger_Loop',[(1,down,(0,0,-1.55)),(31,{**down,'jaw':(17,0,0)},(0,0,-1.51)),(61,down,(0,0,-1.55))])
action('Recover',[(1,down,(0,0,-1.55)),(25,{**down,'neck_01':(-8,0,0)},(0,0,-1.3)),(53,{'chest':(-8,0,0),'head':(-10,0,0)},(0,0,-.3)),(76,{},(0,0,0))])
dead={**down,'body':(0,0,25),'neck_01':(18,0,-13),'head':(5,0,8),'jaw':(23,0,0),'wing_L_upper':(0,0,15),'wing_R_upper':(0,0,-25)}
action('Death',[(1,{},(0,0,0)),(24,{'neck_01':(-24,0,0),'jaw':(28,0,0)},(0,0,.15)),(65,dead,(0,0,-1.85)),(81,dead,(0,0,-1.72)),(120,dead,(0,0,-1.8))])

# Neutral rest state when imported; all actions stay in named NLA tracks.
rig.animation_data.action=None
for p in rig.pose.bones:p.rotation_euler=(0,0,0);p.location=(0,0,0)
scene.frame_start=1;scene.frame_end=130;scene.frame_set(1)
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);mesh.select_set(True)
bpy.context.view_layer.objects.active=rig
rig['forward_axis']='Blender -Y; FBX export -Z forward / Y up'
rig['license']='Original procedural blockout and animations: CC0-1.0. Code: MIT.'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Veyr_TEMP_Rig.blend'))
bpy.ops.export_scene.fbx(filepath=str(OUT/'Veyr_TEMP_Rig.fbx'),use_selection=True,object_types={'ARMATURE','MESH'},add_leaf_bones=False,axis_forward='-Z',axis_up='Y',bake_anim=True,bake_anim_use_all_actions=True,bake_anim_use_nla_strips=False,bake_anim_simplify_factor=.2)
# FBX writes an authoring-source pathname into metadata. Strip local workspace
# identity without changing binary record lengths/offsets. Redundant relative
# path components are valid paths and avoid embedded NUL or bogus offsets.
fbx_path=OUT/'Veyr_TEMP_Rig.fbx'
fbx=fbx_path.read_bytes()
private_path=str(OUT/'Veyr_TEMP_Rig.blend').encode()
public_path=b'ArtSource/Veyr_TEMP_Rig.blend'
padding=len(private_path)-len(public_path)
if padding >= 2:
    prefix=(b'.//' if padding%2 else b'') + b'./'*((padding-(3 if padding%2 else 0))//2)
    replacement=prefix+public_path
    assert len(replacement)==len(private_path)
    fbx_path.write_bytes(fbx.replace(private_path,replacement))
manifest={'status':'TEMPORARY BLOCKOUT; final Tripo mesh pending','mesh_vertices':len(mesh.data.vertices),'mesh_triangles':sum(len(p.vertices)-2 for p in mesh.data.polygons),'bones':len(bone_defs),'fps':30,'actions':actions,'bone_rest':bone_defs,'space':'meters; Blender Z up and -Y forward','license_mesh_animation':'CC0-1.0','license_script':'MIT'}
(OUT/'veyr-rig-manifest.json').write_text(json.dumps(manifest,indent=2))
print('VEYR_EXPORT_SUCCESS '+json.dumps({k:manifest[k] for k in ['mesh_vertices','mesh_triangles','bones']}))
