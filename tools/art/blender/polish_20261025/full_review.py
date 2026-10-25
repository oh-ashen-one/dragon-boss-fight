"""Render actual Blender animation at the intended speed, three viewpoints."""
from pathlib import Path
import importlib.util,json,math,bpy
HERE=Path(__file__).resolve().parent
def module(name):
 p=HERE/(name+'.py');sp=importlib.util.spec_from_file_location('polish_'+name,p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m

def run(kind):
 m=module(kind)
 names=['Dragon_FlyHover_Blender_polish_v1','Dragon_Takeoff_Blender_polish_v2','Dragon_Land_Blender_polish_v3'] if kind=='dragon' else ['RunTwoHand_Blender_polish_v2','GripToTwoHand_Blender_polish_v2','GripToOneHand_Blender_polish_v2','Roll_Blender_polish_v2','RollAttack_Blender_polish_v2']
 reports=[]
 for name in names:
  m.open_scene(m.OUT/(name+'.blend'));s=bpy.context.scene;duration=(s.frame_end-s.frame_start)/s.render.fps;N=math.ceil(duration*30);frames=[s.frame_start+(s.frame_end-s.frame_start)*i/N for i in range(N)];folder='fullspeed/'+name
  if kind=='dragon':m.render_dragon(folder,frames,('side','front','three_quarter'))
  else:m.render_knight(folder,frames,('side','front','threequarter'))
  row={'name':name,'duration':duration,'framesPerView':N,'playbackFPS':N/duration,'sourceFrames':frames,'views':['side','front','three_quarter' if kind=='dragon' else 'threequarter'],'folder':str(m.OUT/folder)};(m.OUT/folder/'timing.json').write_text(json.dumps(row,indent=2));reports.append(row)
 print(json.dumps(reports))
