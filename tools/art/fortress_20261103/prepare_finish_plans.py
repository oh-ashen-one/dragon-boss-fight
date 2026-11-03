#!/usr/bin/env python3
"""Append the source-preserving painted wall and budgeted iron-basket import plans."""
import json,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'tools/unreal'))
from import_tripo_static import validate_plan
ITEMS=[('FortressPaintedWall','5c6df4b4-3cd8-4b29-8fea-429fbdd657b9',[150000,60000,15000],2048),('FortressBrazier','43d0356a-e8bc-482d-bfa6-4afdbc02112d',[40000,15000,3000],1024)]
def main():
 p=ROOT/'Local/ArtPass20261025/Tripo/import-plan.json';plan=json.loads(p.read_text())
 for name,job,lods,tex in ITEMS:
  f=ROOT/'Local/ArtPass20261025/Tripo/Fortress20261103'/(name+'_native-source_v001.glb')
  item=dict(name=name,version='v001',kind='architecture',source={'file':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()},lod_triangles=lods,screen_sizes=[1.,.45,.18],texture_max_size=tex,complex_collision=True,collision_lod=2,provider='Tripo browser H3.1; owned geometry adaptation' if name=='FortressPaintedWall' else 'Tripo browser H3.1',source_url='https://studio.tripo3d.ai/workspace/generate/'+job,license='Owner-generated reference; verified Max paid plan; private raw source',creator='Owner-directed generation')
  validate_plan({'schema':1,'assets':[item]});old=[x for x in plan['assets'] if x['name']==name]
  if old and old!=[item]:raise RuntimeError('Preserve conflicting finish plan: '+name)
  if not old:plan['assets'].append(item)
 p.write_text(json.dumps(plan,indent=2)+'\n');print('Fortress finish plans validated')
if __name__=='__main__':main()
