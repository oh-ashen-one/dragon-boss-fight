#!/usr/bin/env python3
"""Validate the normalized gatehouse and append its fixed native import request."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'tools/unreal'))
from import_tripo_static import validate_plan
SOURCE=ROOT/'Local/ArtPass20261025/Tripo/Fortress20261103/FortressGatehouse_native-source_v001.glb'
PLAN=ROOT/'Local/ArtPass20261025/Tripo/import-plan.json'
def main():
    if not SOURCE.is_file():raise SystemExit('Prepare/bake and normalize the gatehouse first; no plan changed')
    item={'name':'FortressGatehouse','version':'v001','kind':'architecture','source':{'file':str(SOURCE),'sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest()},'lod_triangles':[150000,60000,15000],'screen_sizes':[1.,.45,.18],'texture_max_size':2048,'complex_collision':True,'collision_lod':2,'provider':'Tripo browser H3.1','source_url':'https://studio.tripo3d.ai/workspace/generate/4175a824-a287-4369-9f39-8e9d1f77dab4','license':'Generated under verified Max paid plan; owner-owned reference; see paid-user terms','creator':'Owner-directed generation'}
    validate_plan({'schema':1,'assets':[item]})
    plan=json.loads(PLAN.read_text()) if PLAN.exists() else {'schema':1,'assets':[]};old=[x for x in plan['assets'] if x['name']==item['name']]
    if old and old!=[item]:raise SystemExit('Different gatehouse entry exists; preserve it and use a fresh version')
    if not old:plan['assets'].append(item);PLAN.write_text(json.dumps(plan,indent=2)+'\n')
    (SOURCE.parent/'import-plan.json').write_text(json.dumps({'schema':1,'assets':[item]},indent=2)+'\n')
    print('FortressGatehouse native import plan validated')
if __name__=='__main__':main()
