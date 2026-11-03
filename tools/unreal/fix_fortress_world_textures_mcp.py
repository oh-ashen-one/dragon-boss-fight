#!/usr/bin/env python3
"""Correct this task's image textures for world-surface rendering; preserve source pixels."""
import json,sys
from pathlib import Path
from native_mcp import NativeMCP
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'Local/FortressRuntimeEditor20261103'
c=NativeMCP(timeout=120);c.initialize()
def call(tool,name,args):
 r=c.request('tools/call',{'name':'call_tool','arguments':{'toolset_name':'editor_toolset.toolsets.'+tool,'tool_name':name,'arguments':args}})
 if r.get('error') or r.get('result',{}).get('isError'):
  (OUT/'texture-failure.json').write_text(json.dumps(r,indent=2));raise RuntimeError('Native texture correction failed: '+name)
 return json.loads(r['result']['content'][0]['text'])['returnValue']
paths=['/Game/ArtPass/FortressMaterials/v001/T_FortressFloor.T_FortressFloor']+[f'/Game/ArtPass/FortressMurals/v001/T_Mural{i:02d}.T_Mural{i:02d}' for i in range(1,5)]
rows=[];keys=['CompressionSettings','MipGenSettings','SRGB','MaxTextureSize','LODGroup']
for path in paths:
 tags=call('asset.AssetTools','get_metadata_tags',{'asset_path':path});assert tags.get('VeyrOwner') in ['veyr-fortress-20261103','veyr-fortress-finish-20261103'],('Not a task-owned texture',path)
 ref={'refPath':path};before=json.loads(call('object.ObjectTools','get_properties',{'instance':ref,'properties':keys}))
 assert call('object.ObjectTools','set_properties',{'instance':ref,'values':json.dumps({'CompressionSettings':'TC_Default','MipGenSettings':'TMGS_FromTextureGroup','LODGroup':'TEXTUREGROUP_World','SRGB':True,'MaxTextureSize':2048})}) is True
 after=json.loads(call('object.ObjectTools','get_properties',{'instance':ref,'properties':keys}));assert after['CompressionSettings']=='TC_Default' and after['MipGenSettings']=='TMGS_FromTextureGroup'
 rows.append({'asset':path,'before':before,'after':after})
assert call('asset.AssetTools','save_assets',{'asset_paths':paths}) is True
for path in ['/Game/ArtPass/FortressMaterials/v001/M_FortressFloor.M_FortressFloor','/Game/ArtPass/FortressMurals/v002/M_FortressMural.M_FortressMural']:
 assert not call('material.MaterialTools','recompile',{'material_or_function':{'refPath':path}})
report={'nativePropertiesVerified':True,'sourcePixelsEdited':False,'textures':rows,'renderedImprovementVerified':False,'scope':'Mipmapped world-texture configuration; next Shipping capture must determine visual effect.'}
(ROOT/'docs/master-goal-20261103/world-texture-correction.json').write_text(json.dumps(report,indent=2)+'\n');print('Five owned textures configured for world rendering; capture verification pending')
