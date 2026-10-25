"""Pack task-owned candidate scenes for portable review; no source scene writes."""
from pathlib import Path
exec(compile((Path(__file__).parent/'common.py').read_text(),str(Path(__file__).parent/'common.py'),'exec'))
NAMES=['Dragon_FlyHover_Blender_polish_v1','Dragon_Takeoff_Blender_polish_v3','Dragon_Land_Blender_polish_v4','RunTwoHand_Blender_polish_v2','GripToTwoHand_Blender_polish_v2','GripToOneHand_Blender_polish_v2','Roll_Blender_polish_v2','RollAttack_Blender_polish_v2']
rows=[]
for name in NAMES:
 path=OUT/(name+'.blend');open_scene(path);s=bpy.context.scene
 assert Path(bpy.data.filepath).resolve().is_relative_to(OUT.resolve())
 s['polish_owner']='codex-veyr-polish-20261025';s['polish_export']=str(OUT/(name+'.glb'));s['polish_candidate']=True
 if name.startswith(('Roll_','RollAttack_')):s['polish_note']='Praised torso, left arm and leg motion preserved. Original right palm trajectory carries the intact boat forward; native right-arm IK changes only the right arm. Roll/attack prefix exact.'
 if name.startswith(('RunTwoHand','GripTo')):s['sword_file']='BoatGreatsword_OneHand_v4.glb'
 bpy.ops.file.pack_all();s.frame_set(0)
 with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):bpy.ops.wm.save_as_mainfile(filepath=str(path),compress=True)
 rows.append({'name':name,'images':len(bpy.data.images),'unpackedFileImages':[i.name for i in bpy.data.images if i.source=='FILE' and not i.packed_file]})
(OUT/'packed-scenes.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows))
