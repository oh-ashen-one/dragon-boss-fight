"""Render matched repeated-stride/exit studies from actual Blender actions.

Before repeats the untouched capture lead-in. After repeats the corrected loop
then continues the shared exit. Only whole-body travel is accumulated for this
presentation; no source file is overwritten and no text is burned into frames.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--pair-directory',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
pairdir=a.pair_directory.resolve(strict=True);out=a.output.resolve()
assert pairdir.is_relative_to(ROOT/'Local') and out.is_relative_to(ROOT/'Local') and not out.exists()
pair=json.loads((pairdir/'pair.json').read_text());loopmeta,exitmeta=pair['clips']
loopfile=ROOT/loopmeta['editableScene'];exitfile=ROOT/exitmeta['editableScene'];source=ROOT/exitmeta['source']
helper=ROOT/'tools/art/blender/fab_rig_testing/retarget.py';ns={'__file__':str(helper)}
exec(compile(helper.read_text(),str(helper),'exec'),ns);ns['OUT']=out
out.mkdir(parents=True)


def samples(path,first=0):
    metadata=json.loads(path.with_suffix('.json').read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest()==metadata['editableSceneSHA256']
    bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False)
    scene=bpy.context.scene;rig=bpy.data.objects['Knight_Comparison'];assert scene.render.fps==120
    rows=[]
    for frame in range(first,scene.frame_end+1):
        scene.frame_set(frame);bpy.context.view_layer.update()
        rows.append({b.name:(rig.matrix_world @ b.matrix).copy() for b in rig.pose.bones})
    origin=rows[0]['Hips'].translation.copy();origin.z=0
    for row in rows:
        for matrix in row.values():matrix.translation-=origin
    return rows


before=samples(source,16);after_loop=samples(loopfile);after_exit=samples(exitfile)
assert len(after_loop)==81 and len(before)==len(after_exit)
def depth(bone):return 0 if bone.parent is None else 1+depth(bone.parent)
for label,loop,exit in [('before',before[:81],before),('after',after_loop,after_exit)]:
    # Three full periods followed by the full exit, preserving every source
    # phase and root travel. At the join, exclude duplicate endpoint samples.
    travel=loop[-1]['Hips'].translation-loop[0]['Hips'].translation
    rows=[]
    for cycle in range(3):
        for source_row in loop[:-1]:
            row={n:m.copy() for n,m in source_row.items()}
            for matrix in row.values():matrix.translation+=travel*cycle
            rows.append(row)
    for source_row in exit:
        row={n:m.copy() for n,m in source_row.items()}
        for matrix in row.values():matrix.translation+=travel*3
        rows.append(row)
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False)
    scene=bpy.context.scene;rig=bpy.data.objects['Knight_Comparison'];rig.animation_data.action.use_fake_user=True
    action=bpy.data.actions.new('ContiguousReview_'+label);rig.animation_data.action=action
    scene.frame_start,scene.frame_end=0,len(rows)-1;previous={};error=0.
    bones=sorted(rig.pose.bones,key=depth)
    for frame,row in enumerate(rows):
        scene.frame_set(frame)
        for bone in bones:
            bone.rotation_mode='QUATERNION';bone.matrix=rig.matrix_world.inverted() @ row[bone.name];bpy.context.view_layer.update()
            q=bone.rotation_quaternion.copy()
            if bone.name in previous:q.make_compatible(previous[bone.name])
            bone.rotation_quaternion=q;previous[bone.name]=q.copy()
            for prop in ['location','rotation_quaternion','scale']:bone.keyframe_insert(prop,frame=frame)
        for bone in bones:
            actual=rig.matrix_world @ bone.matrix
            error=max(error,max(abs(actual[i][j]-row[bone.name][i][j]) for i in range(4) for j in range(4)))
    assert error<1e-5, 'Review reconstruction changed source poses'
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for key in curve.keyframe_points:key.interpolation='LINEAR'
    bpy.ops.mesh.primitive_plane_add(size=50,location=(0,0,-.0005));ground=bpy.context.object
    mat=bpy.data.materials.new('ReviewGround');mat.diffuse_color=(.18,.20,.22,1);ground.data.materials.append(mat)
    for axis in range(2):
        for i in range(-48,49):
            curve=bpy.data.curves.new('GridLine','CURVE');curve.dimensions='3D';curve.bevel_depth=.001
            line=curve.splines.new('POLY');line.points.add(1)
            line.points[0].co=(-12,i*.25,.0002,1) if axis==0 else (i*.25,-12,.0002,1)
            line.points[1].co=(12,i*.25,.0002,1) if axis==0 else (i*.25,12,.0002,1)
            obj=bpy.data.objects.new('GridLine',curve);scene.collection.objects.link(obj)
    frames=list(range(0,len(rows),4));scales=ns['render'](label,frames,ortho_scale=2.8,resolution=960)
    bpy.ops.wm.save_as_mainfile(filepath=str(out/(label+'.blend')),compress=True)
    (out/(label+'.json')).write_text(json.dumps({'variant':label,'frames':frames,'reviewFPS':30,'viewOrthoScales':scales,'groundHeightSourceUnits':0,'sourcePoseReconstructionMaxError':error,'source':str(source.relative_to(ROOT)),'pair':str(pairdir.relative_to(ROOT)),'loopRepeats':3,'accepted':False},indent=2)+'\n')
print('CONTIGUOUS_MATCHED_SOURCE_FRAMES_RENDERED',flush=True)
