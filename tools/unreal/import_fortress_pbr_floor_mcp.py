#!/usr/bin/env python3
"""Create a real PBR slate floor in a fresh folder through native Unreal MCP."""
import json,hashlib,re
from pathlib import Path
from native_mcp import NativeMCP
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'Local/FortressPBREditor20261103';FOLDER='/Game/ArtPass/FortressMaterials/v002';STATE=OUT/'floor-state.json';OWNER='veyr-fortress-pbr-floor-20261103'
TOOLS={k:'editor_toolset.toolsets.'+v for k,v in {'asset':'asset.AssetTools','texture':'texture.TextureTools','material':'material.MaterialTools','object':'object.ObjectTools'}.items()}
def main():
 OUT.mkdir(exist_ok=True);state=json.loads(STATE.read_text()) if STATE.exists() else {'owner':OWNER,'textures':{},'expressions':{},'links':[],'complete':False};assert state['owner']==OWNER
 c=NativeMCP(timeout=120);c.initialize()
 def save():STATE.write_text(json.dumps(state,indent=2)+'\n')
 def meta(name,args):
  r=c.request('tools/call',{'name':name,'arguments':args})
  if r.get('error') or r.get('result',{}).get('isError'):(OUT/'failed-call.json').write_text(json.dumps(r,indent=2));raise RuntimeError('Native call failed: '+str(args.get('tool_name',name)))
  return r['result']['content'][0]['text']
 def call(tool,name,args):return json.loads(meta('call_tool',{'toolset_name':TOOLS.get(tool,tool),'tool_name':name,'arguments':args}))['returnValue']
 names=re.findall(r'^- ([^:\n]+):',meta('list_toolsets',{}).replace('\\n','\n'),re.M);target=next(n for n in names if n.endswith('.veyr_integration_toolset.VeyrIntegrationTools') and 'veyr-knight-20261028' in n);project=call(target,'inspect_project',{});assert Path(project['project_directory']).resolve()==ROOT/'Unreal/Veyr'
 def props(ref,values):
  assert ref['refPath'].startswith(FOLDER+'/');assert call('object','set_properties',{'instance':ref,'values':json.dumps(values)}) is True
 def tag(ref):call('asset','update_metadata_tags',{'asset_path':ref['refPath'],'set_tags':{'VeyrOwner':OWNER,'VeyrProvider':'Poly Haven CC0 Slate Floor02'}})
 for key,suffix,compression,srgb in [('albedo','diff','TC_Default',True),('normal','nor_dx','TC_Normalmap',False),('roughness','rough','TC_Masks',False)]:
  source=ROOT/'Local/Fortress20261103/PolyHaven/slate_floor_02'/f'slate_floor_02_{suffix}_2k.jpg';digest=hashlib.sha256(source.read_bytes()).hexdigest();name='T_Floor'+key.title()
  if key not in state['textures']:
   assert not call('asset','exists',{'path':FOLDER+'/'+name});refs=call('texture','import_file',{'folder_path':FOLDER,'asset_name':name,'source_file':str(source)});assert len(refs)==1;state['textures'][key]=refs[0];state.setdefault('sourceHashes',{})[key]=digest;save()
  assert state['sourceHashes'][key]==digest
  props(state['textures'][key],{'CompressionSettings':compression,'SRGB':srgb,'MipGenSettings':'TMGS_FromTextureGroup','MaxTextureSize':2048,'AddressX':'TA_Wrap','AddressY':'TA_Wrap','LODGroup':'TEXTUREGROUP_WorldNormalMap' if key=='normal' else 'TEXTUREGROUP_World'});tag(state['textures'][key])
 if 'material' not in state:
  assert not call('asset','exists',{'path':FOLDER+'/M_FortressFloor'});state['material']=call('material','create_material',{'folder_path':FOLDER,'asset_name':'M_FortressFloor'});save()
 mat=state['material'];props(mat,{'bUsedWithInstancedStaticMeshes':True,'bTangentSpaceNormal':True,'BlendMode':'BLEND_Opaque','ShadingModel':'MSM_DefaultLit'});tag(mat)
 def expr(key,kind,values=None):
  if key not in state['expressions']:state['expressions'][key]=call('material','add_expression',{'material_or_function':mat,'expression_class':{'refPath':'/Script/Engine.MaterialExpression'+kind},'x':-1400+len(state['expressions'])%5*240,'y':len(state['expressions'])//5*200});save()
  n=state['expressions'][key]
  if values:props(n,values)
  return n
 def link(a,b,pin,output=''):
  key='|'.join([a['refPath'],output,b['refPath'],pin])
  if key in state['links']:return
  pins=call('material','get_expression_input_names',{'expression':b});pins=['' if p in ('None',None) else p for p in pins];actual='' if pin=='Input' and '' in pins else pin;assert actual in pins,(pin,pins)
  call('material','connect_expressions',{'from_expression':a,'from_output_name':output,'to_expression':b,'to_input_name':actual});state['links'].append(key);save()
 position=expr('world_position','WorldPosition');xy=expr('xy','ComponentMask',{'R':True,'G':True,'B':False,'A':False});link(position,xy,'Input')
 tile=expr('tile_size','ScalarParameter',{'ParameterName':'FloorTileCm','DefaultValue':400.});uv=expr('uv','Divide');link(xy,uv,'A');link(tile,uv,'B')
 tex={}
 for key,sampler in [('albedo','SAMPLERTYPE_Color'),('normal','SAMPLERTYPE_Normal'),('roughness','SAMPLERTYPE_Masks')]:
  tex[key]=expr(key,'TextureSampleParameter2D',{'ParameterName':'Floor'+key.title(),'Texture':state['textures'][key],'SamplerType':sampler});link(uv,tex[key],'UVs')
 desat=expr('desaturate','Desaturation');fraction=expr('desaturation_fraction','ScalarParameter',{'ParameterName':'FloorDesaturation','DefaultValue':.8});link(tex['albedo'],desat,'Input','RGB');link(fraction,desat,'Fraction')
 minimum=expr('minimum_roughness','ScalarParameter',{'ParameterName':'FloorMinimumRoughness','DefaultValue':.85});rough=expr('rough_max','Max');link(tex['roughness'],rough,'A','R');link(minimum,rough,'B')
 spec=expr('specular','Constant',{'R':.15});metal=expr('metallic','Constant',{'R':0.})
 for n,pin,prop in [(desat,'','MP_BaseColor'),(tex['normal'],'RGB','MP_Normal'),(rough,'','MP_Roughness'),(spec,'','MP_Specular'),(metal,'','MP_Metallic')]:
  call('material','connect_to_output',{'expression':n,'output_name':pin,'material_property':prop});assert call('material','get_property_input',{'material':mat,'material_property':prop})['expression']==n
 call('material','layout_expressions',{'material_or_function':mat});assert not call('material','recompile',{'material_or_function':mat});assert call('asset','save_assets',{'asset_paths':[mat['refPath']]+[x['refPath'] for x in state['textures'].values()]}) is True
 state['complete']=True;save();print('PBR floor saved with real normal/roughness maps; rendered review pending')
if __name__=='__main__':main()
