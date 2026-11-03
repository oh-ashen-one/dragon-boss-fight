#!/usr/bin/env python3
"""Append the measured wall/tower import requests after private source preparation."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'tools/unreal'))
from import_tripo_static import validate_plan
JOBS={'FortressMuralWall':'dae875fb-0070-4d01-81ee-d507fad80753','FortressWatchtower':'caa99309-020d-44fe-8271-c1d036d62c0b'}
def main():
    plan_path=ROOT/'Local/ArtPass20261025/Tripo/import-plan.json';plan=json.loads(plan_path.read_text())
    for name,job in JOBS.items():
        source=ROOT/'Local/ArtPass20261025/Tripo/Fortress20261103'/(name+'_native-source_v001.glb')
        item=dict(name=name,version='v001',kind='architecture',source={'file':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest()},lod_triangles=[150000,60000,15000],screen_sizes=[1.,.45,.18],texture_max_size=2048,complex_collision=True,collision_lod=2,provider='Tripo browser H3.1',source_url='https://studio.tripo3d.ai/workspace/generate/'+job,license='Owner-generated reference; verified Max paid plan; private raw source',creator='Owner-directed generation')
        validate_plan({'schema':1,'assets':[item]});old=[x for x in plan['assets'] if x['name']==name]
        if old and old!=[item]:raise RuntimeError('Preserve conflicting import plan: '+name)
        if not old:plan['assets'].append(item)
    plan_path.write_text(json.dumps(plan,indent=2)+'\n');print('Fortress module plans validated')
if __name__=='__main__':main()
