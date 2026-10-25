"""Run in the owned Blender MCP after prepare_sources.py; never opens Unreal."""
from pathlib import Path
p=Path(__file__).with_name('retarget.py');g={'__file__':str(p)};exec(compile(p.read_text(),str(p),'exec'),g)
r=g['OUT']/'Source';jobs=[(r/'Mixamo/sword and shield walk.fbx','mixamo','Mixamo_Walk_v1',False),(r/'Mixamo/sword and shield slash.fbx','mixamo','Mixamo_Attack_v1',False),(r/'Mixamo/sword and shield block.fbx','mixamo','Mixamo_Block_v1',False),(next((r/'Fab').rglob('A_RunFwd_Loop.fbx')),'fab','Fab_Run_v1',False),(next((r/'Fab').rglob('A_Roll_IdleFwd.fbx')),'fab','Fab_Roll_v1',True)]
assert not any((g['OUT']/'Exports'/(name+'.glb')).exists() for _,_,name,_ in jobs),'Preserve existing candidates; choose new version names before reauthoring'
for path,kind,name,travel in jobs:g['run'](path,kind,name,travel)
