from pathlib import Path
import importlib.util,json
p=Path(__file__).parent/'knight.py';sp=importlib.util.spec_from_file_location('polish_knight_contacts',p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
for name,frames in [('GripToTwoHand_Blender_polish_v2',[30,45]),('GripToOneHand_Blender_polish_v2',[30,45]),('RunTwoHand_Blender_polish_v2',[24,70]),('Roll_Blender_polish_v2',[47,70])]:
 m.open_scene(m.OUT/(name+'.blend'));folder='contacts/'+name;m.render_knight(folder,frames,('front','side','threequarter'),close=True)
 (m.OUT/folder/'frames.json').write_text(json.dumps(frames))
 if name.startswith('Roll_'):m.render_knight('contacts/roll-floor',frames,('side',),close=False)
print('Requested full-resolution hand/hilt and floor reviews complete')
