"""Blender contact correction on an existing death action; no source overwrite.

Preserves the fall and all channels except the neck's late rotation. Uses the
game's canonical skin to settle the snout to a small floor clearance.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--canonical',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
a=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
if a.output.exists() or a.output.with_suffix('.contact.json').exists():raise RuntimeError('Refusing overwrite')
source_sha=hashlib.sha256(a.source.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(a.source),load_ui=False)
reference=next(o for o in bpy.data.objects if o.type=='ARMATURE')
source_action=reference.animation_data.action
start,end=[int(round(x)) for x in source_action.frame_range]
scene=bpy.context.scene
fps,fps_base=scene.render.fps,scene.render.fps_base
old=set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=str(a.canonical))
added=set(bpy.data.objects)-old
rig=next(o for o in added if o.type=='ARMATURE');rig.name='DeathCanonicalRig'
mesh=next(o for o in added if o.type=='MESH' and any(m.type=='ARMATURE' and m.object==rig for m in o.modifiers))
for obj in old:
    if obj.type in ('MESH','ARMATURE'):
        obj.hide_render=True
        if obj.type=='MESH':obj.hide_set(True)
if mesh.data.shape_keys:
    mesh.data.shape_keys.animation_data_clear()
    for key in mesh.data.shape_keys.key_blocks:key.value=0
rig.animation_data_clear()
for bone in rig.pose.bones:
    bone.rotation_mode='QUATERNION';bone.matrix_basis.identity()
rig.animation_data_create();rig.animation_data.action=source_action.copy()
action=rig.animation_data.action;action.name='death_v4_head_contact'
rig.animation_data.action_slot=action.slots[0]
scene.render.fps,scene.render.fps_base=fps,fps_base
scene.frame_start,scene.frame_end=start,end
head_groups={g.index for g in mesh.vertex_groups if g.name in ('bone_5','VeyrJaw')}
head_indices=[v.index for v in mesh.data.vertices if v.groups and max(v.groups,key=lambda g:g.weight).group in head_groups]
if len(head_indices)<100:raise RuntimeError('Canonical head weighting mask unavailable: '+str([g.name for g in mesh.vertex_groups]))
neck=rig.pose.bones['bone_4'];head=rig.pose.bones['bone_5']

def surface():
    bpy.context.view_layer.update()
    obj=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());data=obj.to_mesh()
    try:
        xyz=np.empty(len(data.vertices)*3,dtype=np.float64);data.vertices.foreach_get('co',xyz);xyz=xyz.reshape(-1,3)
        world=np.array(obj.matrix_world,dtype=float)
        points=xyz@world[:3,:3].T+world[:3,3]
        return float(points[:,2].min()),float(points[head_indices,2].min())
    finally:obj.to_mesh_clear()

base=[]
for f in range(start,end+1):
    scene.frame_set(f);bpy.context.view_layer.update()
    direction=rig.matrix_world.to_3x3()@(head.matrix.translation-neck.matrix.translation)
    direction.z=0
    if direction.length<1e-6:raise RuntimeError('Head direction is degenerate')
    axis=Vector((0,0,1)).cross(direction).normalized()
    low,head_low=surface()
    base.append((neck.matrix.copy(),axis,low,head_low,neck.location.copy(),neck.scale.copy()))

def apply(frame_index,degrees):
    m,axis,_,_,_,_=base[frame_index]
    world=rig.matrix_world@m;pivot=world.translation
    delta=Matrix.Translation(pivot)@Matrix.Rotation(math.radians(degrees),4,axis)@Matrix.Translation(-pivot)
    neck.matrix=rig.matrix_world.inverted()@delta@world
    bpy.context.view_layer.update()

scene.frame_set(end)
target=.0015
apply(end-start,25.)
if surface()[1]>target:raise RuntimeError('Head contact requires more than the allowed 25-degree correction')
lo,hi=0.,25.
for _ in range(22):
    mid=(lo+hi)*.5;apply(end-start,mid)
    if surface()[1]>target:lo=mid
    else:hi=mid
degrees=(lo+hi)*.5
previous=None;max_translation_change=0.;max_scale_change=0.
for f in range(start,end+1):
    scene.frame_set(f)
    weight=max(0.,min(1.,(f-55.)/55.));weight=weight*weight*(3.-2.*weight)
    apply(f-start,degrees*weight)
    max_translation_change=max(max_translation_change,(neck.location-base[f-start][4]).length)
    max_scale_change=max(max_scale_change,(neck.scale-base[f-start][5]).length)
    q=neck.rotation_quaternion.copy()
    if previous is not None and q.dot(previous)<0:q.negate()
    neck.rotation_quaternion=q;previous=q
    neck.keyframe_insert(data_path='rotation_quaternion',frame=f,group='Death head contact')
for layer in action.layers:
    for strip in layer.strips:
        for bag in strip.channelbags:
            for curve in bag.fcurves:
                if curve.data_path=='pose.bones["bone_4"].rotation_quaternion':
                    for key in curve.keyframe_points:key.interpolation='LINEAR'
                    curve.update()
if max_translation_change>1e-5 or max_scale_change>1e-5:raise RuntimeError('Correction changed neck location or scale')
rows=[];new_penetration=0.
for f in range(start,end+1):
    scene.frame_set(f);low,head_low=surface();b=base[f-start]
    new_penetration=max(new_penetration,min(0.,b[2])-min(0.,low))
    rows.append({'frame':f,'headMinimumMeters':head_low,'surfaceMinimumMeters':low})
if abs(rows[-1]['headMinimumMeters']-target)>.00015:raise RuntimeError('Baked contact differs from solved pose')
if new_penetration>.001:raise RuntimeError('Correction adds more than 1 mm of floor penetration')
if hashlib.sha256(a.source.read_bytes()).hexdigest()!=source_sha:raise RuntimeError('Source changed')
scene.frame_set(end)
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig
a.output.parent.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(a.output))
report={'sourceSHA256':source_sha,'canonicalSHA256':hashlib.sha256(a.canonical.read_bytes()).hexdigest(),
        'changedChannel':'bone_4.rotation_quaternion after frame 55 only',
        'settledByFrame':110,'correctionDegrees':degrees,
        'headMinimumBeforeMeters':base[-1][3],'headMinimumAfterMeters':rows[-1]['headMinimumMeters'],
        'maximumNewPenetrationMeters':new_penetration,'maximumNeckTranslationChange':max_translation_change,
        'maximumNeckScaleChange':max_scale_change,'samples':rows,
        'scope':'Blender contact correction; native deformation and visual review still required'}
a.output.with_suffix('.contact.json').write_text(json.dumps(report,indent=2)+'\n')
print('DEATH_HEAD_CONTACT',degrees,base[-1][3],rows[-1]['headMinimumMeters'])
