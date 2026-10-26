from pathlib import Path
import importlib.util,bpy
root=Path(__file__).resolve().parents[4]
p=root/'tools/art/blender/fab_rig_testing/retarget.py'
spec=importlib.util.spec_from_file_location('overhaul_retarget',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.OWNER='codex-veyr-overhaul-20261026';m.OUT=root/'Local/Overhaul20261026/blink'
for i,file in enumerate(sorted((root/'Local/FabRigTesting/Source/Mixamo').glob('sword and shield strafe*.fbx'))):
 m.run(file,'mixamo','Mixamo_Strafe_'+str(i+1),travel=True)
