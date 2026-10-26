from pathlib import Path
import bpy,importlib.util,json
root=Path(__file__).resolve().parents[4];out=root/'Local/Overhaul20261026/blink'
p=root/'tools/art/blender/fab_rig_testing/retarget.py';spec=importlib.util.spec_from_file_location('blink_review',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.OUT=out;m.OWNER='codex-veyr-overhaul-20261026'
for name in ('Sourced_BlinkLeft_v1','Sourced_BlinkRight_v1'):
 m.reset();bpy.ops.import_scene.gltf(filepath=str(out/'Exports'/(name+'.glb')));t=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');t.name='Knight_Comparison';end=round(t.animation_data.action.frame_range[1]);m.render(name,[0,end//4,end//2,3*end//4,end])
