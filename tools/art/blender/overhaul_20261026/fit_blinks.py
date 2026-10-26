from pathlib import Path
import importlib.util,shutil,bpy
root=Path(__file__).resolve().parents[4];out=root/'Local/Overhaul20261026/blink'
p=root/'tools/art/blender/fab_rig_testing/fit_weapon.py';spec=importlib.util.spec_from_file_location('overhaul_fit',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.OWNER='codex-veyr-overhaul-20261026';m.OUT=out
for source,name in [('Mixamo_Strafe_2','Sourced_BlinkRight_v1'),('Mixamo_Strafe_3','Sourced_BlinkLeft_v1')]:
 for ext in ('.glb','.json'):shutil.copy2(out/'Exports'/(source+ext),out/'Exports'/('Mixamo_Walk_v1'+ext))
 m.run(('walk',),'v1','one',name)
