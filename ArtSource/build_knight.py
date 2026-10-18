"""Original TEMP knight blockout, anatomical rig and baked combat animation.

SOURCE ONLY until an authorized shared-slot Blender run is scheduled.
blender --background --factory-startup --threads 2 --python ArtSource/build_knight.py

No asset service, network access, purchases or extracted game content. Main mesh
must be replaced by approved Tripo art before any visual-completion claim.
"""
import bpy
import math
import json
from pathlib import Path
from mathutils import Vector, Matrix, Quaternion

OUT = Path(__file__).resolve().parent
FPS = 60
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.render.fps = FPS
scene.unit_settings.system = 'METRIC'
scene['asset_status'] = 'TEMPORARY ORIGINAL KNIGHT BLOCKOUT — APPROVED TRIPO REPLACEMENT REQUIRED'
parts = []
defs = {}


def v(value):
    return Vector(value)


def lerp(a, b, t):
    return v(a).lerp(v(b), t)


def smooth(t):
    t = max(0, min(1, t))
    return t*t*(3-2*t)


def two_bone(start, end, first, second, pole):
    """Analytical limb solve: a real knee/elbow bend with constant segment lengths."""
    start, end, pole = v(start), v(end), v(pole)
    axis = end-start
    distance = max(.0001, axis.length)
    axis /= distance
    distance = min(distance, first+second-.0001)
    end = start+axis*distance
    projection = (first*first-second*second+distance*distance)/(2*distance)
    bend = pole-start
    bend -= axis*bend.dot(axis)
    if bend.length < .001:
        bend = axis.cross(Vector((1, 0, 0)))
    bend.normalize()
    height = math.sqrt(max(0, first*first-projection*projection))
    return start+axis*projection+bend*height, end


def path(keys, t):
    for index in range(len(keys)-1):
        a, b = keys[index], keys[index+1]
        if t <= b[0]:
            return lerp(a[1], b[1], smooth((t-a[0])/max(.0001, b[0]-a[0])))
    return v(keys[-1][1])


def skeleton(t=0, mode='Idle'):
    """Author in world meters; pose matrices then convert into each bone's basis.

    Left/right feet solve independently. Standing actions keep their ground
    anchors fixed, while locomotion translates each stance foot at 5.8m/s.
    """
    j = {}
    hip_z = 1.01
    pelvis = v((0, 0, hip_z))
    lean = yaw = roll = 0
    feet = {'L': v((.18, -.04, .12)), 'R': v((-.18, .10, .12))}
    hands = {'L': v((.38, -.14, 1.21)), 'R': v((-.39, -.18, 1.23))}
    sword_direction = v((-.12, -.18, 1)).normalized()
    head_tilt = 0
    bottle_in_hand = 0
    world_roll = 0
    tumble_center = v((0, 0, .84))

    if mode == 'Idle':
        pelvis.z += math.sin(t*math.tau/2.4)*.012
        lean = 3
        hands['L'].z += math.sin(t*math.tau/2.4)*.007
    elif mode == 'Locomotion':
        cycle = 26/FPS
        pelvis.z = .84+.025*math.cos(t*math.tau/cycle*2)
        lean = 11
        for side, phase_offset in [('L', 0), ('R', .5)]:
            phase = (t/cycle+phase_offset) % 1
            u = (phase % .5)*2
            stance = phase < .5
            travel = 5.8*cycle/2
            feet[side].y = (-.5+u)*travel if stance else (.5-smooth(u))*travel
            feet[side].z = .12 if stance else .12+.25*math.sin(u*math.pi)
            feet[side].x *= .86
        yaw = math.sin(t*math.tau/cycle)*5
        hands['L'] += v((0, math.sin(t*math.tau/cycle)*.15, -.05))
        hands['R'] += v((0, -math.sin(t*math.tau/cycle)*.09, -.06))
        sword_direction = v((-.16, -.25, .95)).normalized()
    elif mode in {'Slash_A', 'Slash_B'}:
        alternate = mode == 'Slash_B'
        anticipation = (.24, .02, 1.52) if alternate else (-.48, .10, 1.56)
        contact = (-.05, -.59, 1.27) if alternate else (.08, -.60, 1.30)
        finish = (-.49, -.18, 1.02) if alternate else (.32, -.23, 1.03)
        hands['R'] = path([(0, hands['R']), (.17, anticipation), (.23, contact), (.39, finish), (.65, hands['R'])], t)
        directions = [(0, sword_direction), (.17, (.40, .08, .92) if alternate else (-.34, .10, .94)),
                      (.23, (-.64, -.76, .06) if alternate else (.64, -.76, .06)),
                      (.39, (-.92, -.12, -.34) if alternate else (.92, -.12, -.34)), (.65, sword_direction)]
        sword_direction = path(directions, t).normalized()
        sign = -1 if alternate else 1
        yaw = path([(0, (0,0,0)), (.17, (0,0,sign*18)), (.23, (0,0,-sign*12)), (.39, (0,0,-sign*23)), (.65, (0,0,0))], t).z
        lean = 4+8*math.sin(min(1, t/.65)*math.pi)
        pelvis.z -= .045*math.sin(min(1, t/.65)*math.pi)
        hands['L'] = path([(0, hands['L']), (.17, (.27,-.28,1.43)), (.39, (.42,.05,1.25)), (.65, hands['L'])], t)
    elif mode == 'Dodge':
        # A crouched shoulder roll. Gameplay owns travel; no horizontal root motion.
        tuck = math.sin(min(1, t/.58)*math.pi)
        pelvis.z = 1.01-.33*tuck
        lean = 19*tuck
        feet['L'] = lerp(feet['L'], (.22,.24,.55), tuck)
        feet['R'] = lerp(feet['R'], (-.22,.13,.54), tuck)
        hands['L'] = lerp(hands['L'], (.26,-.34,1.00), tuck)
        hands['R'] = lerp(hands['R'], (-.30,-.30,.96), tuck)
        sword_direction = lerp(sword_direction, (-.78,-.10,-.62), tuck).normalized()
        world_roll = -360*smooth(t/.58)
        head_tilt = 24*tuck
    elif mode == 'Heal':
        bottle_in_hand = smooth(t/.18)*(1-smooth((t-1.04)/.21))
        hands['L'] = path([(0,hands['L']),(.18,(.25,.04,1.02)),(.55,(.10,-.25,1.75)),(.85,(.10,-.25,1.75)),(1.04,(.21,-.13,1.35)),(1.25,hands['L'])],t)
        hands['R'] = lerp(hands['R'], (-.46,-.08,1.04), math.sin(min(1,t/1.25)*math.pi))
        sword_direction = lerp(sword_direction, (-.40,-.30,-.87), math.sin(min(1,t/1.25)*math.pi)).normalized()
        head_tilt = -12*smooth((t-.38)/.18)*(1-smooth((t-.88)/.2))
        lean = -3*math.sin(min(1,t/1.25)*math.pi)
    elif mode == 'Hit':
        recoil = path([(0,(0,0,0)),(.09,(0,0,1)),(.24,(0,0,.55)),(.65,(0,0,0))],t).z
        lean = -18*recoil
        roll = -7*recoil
        pelvis.z -= .09*recoil
        hands['L'] += v((.04,-.06,.12))*recoil
        hands['R'] += v((-.03,.08,-.06))*recoil
    elif mode == 'Death':
        kneel = smooth(t/.65)
        fall = smooth((t-.55)/1.05)
        pelvis.z = 1.01-.51*kneel
        lean = 23*kneel
        roll = 9*kneel
        feet['L'] = lerp(feet['L'], (.21,.25,.10), kneel)
        feet['R'] = lerp(feet['R'], (-.28,.15,.13), kneel)
        hands['L'] = lerp(hands['L'], (.41,-.15,.53), kneel)
        hands['R'] = lerp(hands['R'], (-.43,-.15,.48), kneel)
        sword_direction = lerp(sword_direction, (-.76,-.50,.06), kneel).normalized()
        world_roll = -83*fall
        tumble_center = v((0, 0, .47))
        head_tilt = 18*kneel

    # Torso articulation is concentrated in hips/spine/chest, not a rigid whole-body tilt.
    torso_rotation = (Quaternion((0,0,1), math.radians(yaw)) @
                      Quaternion((0,1,0), math.radians(roll)) @
                      Quaternion((1,0,0), math.radians(lean)))
    torso = lambda offset: pelvis + torso_rotation @ v(offset)
    j['pelvis'] = pelvis
    j['spine'] = torso((0,0,.16))
    j['chest'] = torso((0,0,.39))
    j['neck'] = torso((0,0,.56))
    j['head'] = torso((0,0,.67))
    j['crown'] = j['head'] + torso_rotation @ Quaternion((1,0,0),math.radians(head_tilt)) @ v((0,0,.22))
    j['face'] = j['head'] + torso_rotation @ v((0,-.24,.09))
    for side, sign in [('L',1),('R',-1)]:
        j['hip_'+side] = pelvis+v((sign*.16,0,0))
        j['ankle_'+side] = feet[side]
        j['knee_'+side],j['ankle_'+side] = two_bone(j['hip_'+side],j['ankle_'+side],.47,.47,pelvis+v((sign*.20,-1,-.4)))
        j['toe_'+side] = j['ankle_'+side]+v((0,-.23,-.065))
        j['toe_tip_'+side] = j['toe_'+side]+v((0,-.10,0))
        j['shoulder_'+side] = torso((sign*.29,0,.43))
        j['wrist_'+side] = hands[side]
        pole = j['shoulder_'+side]+v((sign*.65,.12,-.3))
        j['elbow_'+side],j['wrist_'+side] = two_bone(j['shoulder_'+side],j['wrist_'+side],.29,.28,pole)
        j['finger_'+side] = j['wrist_'+side]+v((0,-.10,0))
        j['tasset_'+side] = pelvis+v((sign*.19,-.09,-.08))
        j['tasset_tip_'+side] = j['tasset_'+side]+v((sign*.025,-.025,-.32))
    j['sword_grip'] = j['wrist_R']
    j['sword_tip'] = j['sword_grip']+sword_direction*1.30
    j['flask'] = lerp(pelvis+v((.25,.08,-.07)),j['wrist_L'],bottle_in_hand)
    j['flask_top'] = j['flask']+v((0,0,.13))

    if abs(world_roll) > .001:
        rotation = Quaternion((1,0,0), math.radians(world_roll))
        for name in j: j[name] = tumble_center+rotation@(j[name]-tumble_center)
        # Floor clearance for body endpoints; weapon can trail along the ground.
        body_points = [point.z for name,point in j.items() if not name.startswith(('sword','flask'))]
        lift = max(0, .13-min(body_points))
        for name in j: j[name].z += lift
    return j


rest = skeleton()


def bone(name, a, b, parent):
    defs[name] = (a, b, parent)


bone('root', (0,0,0), (0,0,.2), None)
bone('pelvis', rest['pelvis'], rest['spine'], 'root')
bone('spine', rest['spine'], rest['chest'], 'pelvis')
bone('chest', rest['chest'], rest['neck'], 'spine')
bone('neck', rest['neck'], rest['head'], 'chest')
bone('head', rest['head'], rest['crown'], 'neck')
bone('face_forward', rest['head'], rest['face'], 'head')
for side in ['L','R']:
    bone('clavicle_'+side,rest['chest'],rest['shoulder_'+side],'chest')
    bone('upperarm_'+side,rest['shoulder_'+side],rest['elbow_'+side],'clavicle_'+side)
    bone('forearm_'+side,rest['elbow_'+side],rest['wrist_'+side],'upperarm_'+side)
    bone('hand_'+side,rest['wrist_'+side],rest['finger_'+side],'forearm_'+side)
    bone('thigh_'+side,rest['hip_'+side],rest['knee_'+side],'pelvis')
    bone('shin_'+side,rest['knee_'+side],rest['ankle_'+side],'thigh_'+side)
    bone('foot_'+side,rest['ankle_'+side],rest['toe_'+side],'shin_'+side)
    bone('toe_'+side,rest['toe_'+side],rest['toe_tip_'+side],'foot_'+side)
    bone('tasset_'+side,rest['tasset_'+side],rest['tasset_tip_'+side],'pelvis')
bone('sword',rest['sword_grip'],rest['sword_tip'],'hand_R')
bone('flask',rest['flask'],rest['flask_top'],'pelvis')


def material(name,color,metal=.0,rough=.55,glow=0):
    mat=bpy.data.materials.new('TEMP knight | '+name)
    mat.diffuse_color=(*color,1);mat.use_nodes=True
    node=mat.node_tree.nodes.get('Principled BSDF')
    node.inputs['Base Color'].default_value=(*color,1)
    node.inputs['Metallic'].default_value=metal
    node.inputs['Roughness'].default_value=rough
    node.inputs['Emission Color'].default_value=(*color,1)
    node.inputs['Emission Strength'].default_value=glow
    return mat


steel=material('etched blue steel',(.22,.28,.31),.8,.34)
edge=material('worn silver edges',(.55,.60,.61),.85,.3)
cloth=material('charcoal cloth',(.045,.052,.055),0,.94)
leather=material('oxblood leather',(.12,.045,.027),0,.77)
brass=material('old brass',(.42,.28,.09),.7,.44)
glass=material('ember flask',(.64,.18,.03),.1,.25,.7)


def assign(ob,bn,mat,name):
    ob.name='TEMP_Knight_'+name
    ob.data.materials.append(mat)
    group=ob.vertex_groups.new(name=bn)
    group.add(list(range(len(ob.data.vertices))),1,'REPLACE')
    for face in ob.data.polygons:face.use_smooth=True
    parts.append(ob)
    return ob


def ellipsoid(center,scale,bn,mat,name):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=10,location=center)
    ob=bpy.context.object;ob.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    return assign(ob,bn,mat,name)


def capsule(a,b,r1,r2,bn,mat,name):
    a,b=v(a),v(b);direction=b-a
    bpy.ops.mesh.primitive_cone_add(vertices=12,radius1=r1,radius2=r2,depth=direction.length,location=(a+b)/2)
    ob=bpy.context.object;ob.rotation_euler=direction.to_track_quat('Z','Y').to_euler()
    bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
    return assign(ob,bn,mat,name)


def box(center,scale,bn,mat,name):
    bpy.ops.mesh.primitive_cube_add(size=1,location=center)
    ob=bpy.context.object;ob.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    bevel=ob.modifiers.new('Plate edge chamfer','BEVEL');bevel.width=.014;bevel.segments=2
    bpy.context.view_layer.objects.active=ob;bpy.ops.object.modifier_apply(modifier=bevel.name)
    return assign(ob,bn,mat,name)


ellipsoid(rest['chest']+v((0,0,-.04)),(.27,.16,.23),'chest',steel,'breastplate')
ellipsoid(rest['spine'],(.22,.13,.16),'spine',cloth,'articulated_waist')
ellipsoid(rest['pelvis'],(.24,.15,.13),'pelvis',steel,'cuirass_hip')
capsule(rest['neck'],rest['head'],.10,.10,'neck',cloth,'gorget')
ellipsoid(rest['head']+v((0,0,.09)),(.16,.17,.19),'head',steel,'closed_helm')
box(rest['head']+v((0,-.16,.11)),(.25,.028,.027),'head',cloth,'visor_slit')
box(rest['head']+v((0,-.17,.035)),(.038,.025,.11),'head',edge,'nasal_ridge')
for side,sign in [('L',1),('R',-1)]:
    ellipsoid(rest['shoulder_'+side],(.17,.17,.12),'upperarm_'+side,steel,'pauldron_'+side)
    capsule(rest['shoulder_'+side],rest['elbow_'+side],.092,.078,'upperarm_'+side,cloth,'sleeve_'+side)
    ellipsoid(rest['elbow_'+side],(.084,.083,.08),'forearm_'+side,edge,'elbow_cop_'+side)
    capsule(rest['elbow_'+side],rest['wrist_'+side],.087,.062,'forearm_'+side,steel,'vambrace_'+side)
    ellipsoid(rest['wrist_'+side],(.068,.085,.065),'hand_'+side,leather,'gauntlet_'+side)
    capsule(rest['hip_'+side],rest['knee_'+side],.125,.09,'thigh_'+side,steel,'thigh_plate_'+side)
    ellipsoid(rest['knee_'+side]+v((0,-.025,0)),(.10,.11,.085),'shin_'+side,edge,'knee_cop_'+side)
    capsule(rest['knee_'+side],rest['ankle_'+side],.10,.07,'shin_'+side,steel,'greave_'+side)
    ellipsoid((rest['ankle_'+side]+rest['toe_'+side])/2,(.095,.18,.075),'foot_'+side,leather,'boot_'+side)
    ellipsoid(rest['toe_'+side],(.095,.10,.06),'toe_'+side,steel,'sabatons_'+side)
    box((rest['tasset_'+side]+rest['tasset_tip_'+side])/2,(.18,.06,.30),'tasset_'+side,cloth,'split_tabard_'+side)
    box(rest['pelvis']+v((sign*.19,-.13,-.03)),(.13,.05,.10),'pelvis',brass,'belt_plate_'+side)

grip=rest['sword_grip'];direction=(rest['sword_tip']-grip).normalized()
capsule(grip-direction*.06,grip+direction*.15,.035,.035,'sword',leather,'sword_grip')
cross=direction.cross(v((0,1,0))).normalized()
capsule(grip+direction*.18-cross*.16,grip+direction*.18+cross*.16,.025,.025,'sword',brass,'crossguard')
# Diamond-section original straight blade, visibly tapered instead of a thin cube.
normal=direction.cross(cross).normalized()
verts=[]
for length,width in [(.19,.054),(1.08,.037),(1.30,0)]:
    center=grip+direction*length
    for offset in [cross*width,normal*.015,-cross*width,-normal*.015]:verts.append(center+offset)
faces=[]
for ring in range(2):
    for i in range(4):faces.append((ring*4+i,ring*4+(i+1)%4,(ring+1)*4+(i+1)%4,(ring+1)*4+i))
mesh=bpy.data.meshes.new('TEMP_diamond_blade');mesh.from_pydata(verts,[],faces)
ob=bpy.data.objects.new('TEMP_blade',mesh);bpy.context.collection.objects.link(ob);assign(ob,'sword',edge,'diamond_blade')
ellipsoid(rest['flask'],(.055,.055,.075),'flask',glass,'ember_flask')
capsule(rest['flask']+v((0,0,.05)),rest['flask_top'],.025,.025,'flask',brass,'flask_neck')

arm=bpy.data.armatures.new('TEMP_Knight_AnatomicalSkeleton')
rig=bpy.data.objects.new('Knight_Rig',arm);bpy.context.collection.objects.link(rig)
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.object.mode_set(mode='EDIT')
for name,(a,b,parent) in defs.items():
    eb=arm.edit_bones.new(name);eb.head=a;eb.tail=b
    if parent:eb.parent=arm.edit_bones[parent]
bpy.ops.object.mode_set(mode='OBJECT')
rig.show_in_front=True
bpy.ops.object.select_all(action='DESELECT')
for ob in parts:ob.select_set(True)
bpy.context.view_layer.objects.active=parts[0];bpy.ops.object.join()
body=bpy.context.object;body.name='TEMP_Knight_Blockout_REPLACE_WITH_TRIPO';body.parent=rig
modifier=body.modifiers.new('Knight deform','ARMATURE');modifier.object=rig
for pb in rig.pose.bones:pb.rotation_mode='QUATERNION'

links={'pelvis':('pelvis','spine'),'spine':('spine','chest'),'chest':('chest','neck'),
       'neck':('neck','head'),'head':('head','crown'),'face_forward':('head','face'),
       'sword':('sword_grip','sword_tip'),'flask':('flask','flask_top')}
for side in ['L','R']:
    for bn,a,b in [('clavicle','chest','shoulder_'+side),('upperarm','shoulder_'+side,'elbow_'+side),
                   ('forearm','elbow_'+side,'wrist_'+side),('hand','wrist_'+side,'finger_'+side),
                   ('thigh','hip_'+side,'knee_'+side),('shin','knee_'+side,'ankle_'+side),
                   ('foot','ankle_'+side,'toe_'+side),('toe','toe_'+side,'toe_tip_'+side),
                   ('tasset','tasset_'+side,'tasset_tip_'+side)]:links[bn+'_'+side]=(a,b)


previous_quaternions = {}


def pose(time,mode,frame):
    joints=skeleton(time,mode)
    for name,pb in ((name,rig.pose.bones[name]) for name in defs):
        if name=='root':
            pb.matrix=pb.bone.matrix_local.copy()
        else:
            a,b=links[name];head,tail=joints[a],joints[b]
            rest_direction=pb.bone.tail_local-pb.bone.head_local
            desired=tail-head
            delta=rest_direction.rotation_difference(desired)
            pb.matrix=Matrix.Translation(head) @ delta.to_matrix().to_4x4() @ pb.bone.matrix_local.to_3x3().to_4x4()
        # Parent-first solve with immediate dependency updates keeps planted ankles
        # coherent when hips/spine change and avoids local/world axis confusion.
        bpy.context.view_layer.update()
        # Equivalent quaternion signs must stay continuous across the 360° dodge.
        rotation = pb.rotation_quaternion.copy()
        if name in previous_quaternions and rotation.dot(previous_quaternions[name]) < 0:
            rotation.negate()
        pb.rotation_quaternion = rotation
        previous_quaternions[name] = rotation.copy()
        pb.keyframe_insert('location',frame=frame,group=name)
        pb.keyframe_insert('rotation_quaternion',frame=frame,group=name)
        pb.keyframe_insert('scale',frame=frame,group=name)


actions=[]
specs=[('Idle',2.4,[]),('Locomotion',26/FPS,[]),('Slash_A',.65,[.17,.23,.39]),
       ('Slash_B',.65,[.17,.23,.39]),('Dodge',.58,[.08,.44]),('Heal',1.25,[.85]),
       ('Hit',.65,[.09]),('Death',2.0,[.65,1.6])]
rig.animation_data_create()
for name,duration,events in specs:
    previous_quaternions.clear()
    action=bpy.data.actions.new(name);rig.animation_data.action=action;action.use_fake_user=True
    # FBX's one-frame bake stops at the last integer sample. Fractional endpoints
    # such as Dodge .58s (34.8 ticks) otherwise lose their last pose and Unity sees
    # only .566667s. Hold the true final pose at the next whole export-frame tick.
    export_ticks=math.ceil(duration*FPS-1e-7)
    times={0,duration,export_ticks/FPS,*events}
    times.update(i/FPS for i in range(export_ticks+1))
    for t in sorted(times):pose(min(t,duration),name,1+t*FPS)
    rig.animation_data.action=None
    track=rig.animation_data.nla_tracks.new();track.name=name;track.mute=True
    track.strips.new(name,1,action)
    actions.append({'name':name,'seconds':duration,'export_seconds':export_ticks/FPS,'events_seconds':events})

rig.animation_data.action=None
for pb in rig.pose.bones:pb.matrix_basis=Matrix.Identity(4)
scene.frame_start=1;scene.frame_end=145;scene.frame_set(1)
rig['status']='TEMPORARY geometry, rig and motion study; requires approved Tripo replacement'
rig['space']='meters; Blender Z up, -Y forward; root offsets authored via world matrices'
rig['code_license']='MIT';rig['original_mesh_animation_license']='CC0-1.0'
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);body.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Knight_TEMP_Rig.blend'))
bpy.ops.export_scene.fbx(filepath=str(OUT/'Knight_TEMP_Rig.fbx'),use_selection=True,object_types={'ARMATURE','MESH'},
    add_leaf_bones=False,axis_forward='-Z',axis_up='Y',bake_anim=True,bake_anim_use_all_actions=True,
    bake_anim_use_nla_strips=False,bake_anim_simplify_factor=0)

# Remove private authoring pathname metadata without changing FBX binary offsets.
fbx_path=OUT/'Knight_TEMP_Rig.fbx';fbx=fbx_path.read_bytes()
private=str(OUT/'Knight_TEMP_Rig.blend').encode();public=b'ArtSource/Knight_TEMP_Rig.blend'
padding=len(private)-len(public)
if padding>=2:
    prefix=(b'.//' if padding%2 else b'')+b'./'*((padding-(3 if padding%2 else 0))//2)
    replacement=prefix+public;assert len(replacement)==len(private)
    fbx_path.write_bytes(fbx.replace(private,replacement))
manifest={'status':'TEMPORARY original blockout; approved Tripo mesh pending','bones':len(defs),'fps':FPS,
          'vertices':len(body.data.vertices),'triangles':sum(len(p.vertices)-2 for p in body.data.polygons),
          'actions':actions,'forward':'Blender -Y; Unity runtime should derive from face_forward bone',
          'locomotion_speed_meters_per_second':5.8,'sword_contact_seconds':.23,
          'root_translation':'Pose matrices authored in Blender world space; gameplay owns horizontal travel',
          'license_code':'MIT','license_original_mesh_animation':'CC0-1.0',
          'validation':'Export only; requires native rendered review, planted-foot and contact verification'}
(OUT/'knight-rig-manifest.json').write_text(json.dumps(manifest,indent=2))
print('KNIGHT_TEMP_EXPORT_SUCCESS '+json.dumps({'bones':len(defs),'clips':len(actions),'vertices':len(body.data.vertices)}))
