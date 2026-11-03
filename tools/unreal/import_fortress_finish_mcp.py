#!/usr/bin/env python3
"""Create paint-on-stone and dry paving through native Unreal material/asset tools.

Fresh owned folders only. Original floor, wall materials and all four paintings
remain unchanged. This script does not launch an editor or claim visual approval.
"""
import hashlib,json,re
from pathlib import Path
from native_mcp import NativeMCP
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'Local/FortressFinishEditor20261103';STATE=OUT/'material-state.json'
MURAL='/Game/ArtPass/FortressMurals/v002';FLOOR='/Game/ArtPass/FortressMaterials/v001'
TOOLS={k:'editor_toolset.toolsets.'+v for k,v in {'asset':'asset.AssetTools','texture':'texture.TextureTools','material':'material.MaterialTools','instance':'material_instance.MaterialInstanceTools','object':'object.ObjectTools'}.items()}
OWNER='veyr-fortress-finish-20261103'
def main():
 OUT.mkdir(exist_ok=True);source=ROOT/'ArtSource/Fortress20261103/Textures/dry-paving-v1.png';digest=hashlib.sha256(source.read_bytes()).hexdigest()
 state=json.loads(STATE.read_text()) if STATE.exists() else {'owner':OWNER,'floorSourceSHA256':digest,'expressions':{},'links':[],'instances':{},'complete':False}
 assert state['owner']==OWNER and state['floorSourceSHA256']==digest
 c=NativeMCP(timeout=120);c.initialize()
 def save():STATE.write_text(json.dumps(state,indent=2)+'\n')
 def meta(name,args):
  r=c.request('tools/call',{'name':name,'arguments':args})
  if r.get('error') or r.get('result',{}).get('isError'):
   (OUT/'failed-call.json').write_text(json.dumps({'method':name,'tool':args.get('tool_name'),'response':r},indent=2)+'\n');raise RuntimeError('Native '+str(args.get('tool_name',name))+' failed; state preserved')
  return r['result']['content'][0]['text']
 def call(tool,name,args):return json.loads(meta('call_tool',{'toolset_name':TOOLS.get(tool,tool),'tool_name':name,'arguments':args}))['returnValue']
 names=re.findall(r'^- ([^:\n]+):',meta('list_toolsets',{}).replace('\\n','\n'),re.M);targets=[n for n in names if n.endswith('.veyr_integration_toolset.VeyrIntegrationTools') and 'veyr-knight-20261028' in n];assert len(targets)==1
 project=call(targets[0],'inspect_project',{});assert Path(project['project_directory']).resolve()==ROOT/'Unreal/Veyr'
 def props(ref,values):
  assert ref['refPath'].startswith((MURAL+'/',FLOOR+'/'));assert call('object','set_properties',{'instance':ref,'values':json.dumps(values)}) is True
 def get(ref,keys):
  r=call('object','get_properties',{'instance':ref,'properties':keys});return json.loads(r) if isinstance(r,str) else r
 def tag(ref):call('asset','update_metadata_tags',{'asset_path':ref['refPath'],'set_tags':{'VeyrOwner':OWNER,'VeyrRecipe':'painted stone UV1 with UV0 surface preservation; matte dry paving'}})
 if 'material' not in state:
  path=MURAL+'/M_FortressMural';assert not call('asset','exists',{'path':path}),'Preserve unowned existing material'
  state['material']=call('material','create_material',{'folder_path':MURAL,'asset_name':'M_FortressMural'});save();tag(state['material'])
 mat=state['material'];props(mat,{'BlendMode':'BLEND_Opaque','ShadingModel':'MSM_DefaultLit','bUsedWithInstancedStaticMeshes':True,'bTangentSpaceNormal':True})
 def expr(key,kind,values=None):
  if key not in state['expressions']:
   n=call('material','add_expression',{'material_or_function':mat,'expression_class':{'refPath':'/Script/Engine.MaterialExpression'+kind},'x':-1400+(len(state['expressions'])%5)*250,'y':(len(state['expressions'])//5)*180});state['expressions'][key]=n;save()
  n=state['expressions'][key]
  if values:props(n,values)
  return n
 def link(a,b,pin,output=''):
  identity='|'.join([a['refPath'],output,b['refPath'],pin])
  if identity in state['links']:return
  pins=call('material','get_expression_input_names',{'expression':b});pins=['' if x in ('None',None) else x for x in pins]
  actual='' if pin=='Input' and '' in pins else pin
  assert actual in pins,'Missing native input '+pin+' on '+b['refPath']
  call('material','connect_expressions',{'from_expression':a,'from_output_name':output,'to_expression':b,'to_input_name':actual});state['links'].append(identity);save()
 def output(n,prop,pin=''):
  call('material','connect_to_output',{'expression':n,'output_name':pin,'material_property':prop})
  assert call('material','get_property_input',{'material':mat,'material_property':prop})['expression']==n
 base='/Game/ArtPass/Tripo/FortressCurtainWall_v001/Imported/FortressCurtainWall_native-source_v001_textures_'
 def texref(i):return {'refPath':base+str(i)+'.FortressCurtainWall_native-source_v001_textures_'+str(i)}
 from normalize_customuse_glb import GLB
 wall_source=GLB(ROOT/'Local/ArtPass20261025/Tripo/Fortress20261103/FortressCurtainWall_native-source_v001.glb');source_material=wall_source.json['materials'][0]
 base_index=source_material['pbrMetallicRoughness']['baseColorTexture']['index'];normal_index=source_material['normalTexture']['index']
 for i in [base_index,normal_index]:assert call('asset','exists',{'path':texref(i)['refPath']})
 uv=expr('mural_uv','TextureCoordinate',{'CoordinateIndex':1});stone=expr('stone','TextureSampleParameter2D',{'ParameterName':'StoneAlbedo','Texture':texref(base_index),'SamplerType':'SAMPLERTYPE_Color'})
 painting=expr('painting','TextureSampleParameter2D',{'ParameterName':'MuralAlbedo','Texture':{'refPath':'/Game/ArtPass/FortressMurals/v001/T_Mural01.T_Mural01'}});link(uv,painting,'UVs')
 normal=expr('normal','TextureSampleParameter2D',{'ParameterName':'StoneNormal','Texture':texref(normal_index),'SamplerType':'SAMPLERTYPE_Normal'})
 inverse=expr('inverse_uv','OneMinus');link(uv,inverse,'Input')
 uvmin=expr('uv_min','Min');link(uv,uvmin,'A');link(inverse,uvmin,'B')
 u=expr('u_edge','ComponentMask',{'R':True,'G':False,'B':False,'A':False});v=expr('v_edge','ComponentMask',{'R':False,'G':True,'B':False,'A':False});link(uvmin,u,'Input');link(uvmin,v,'Input')
 edge=expr('edge_min','Min');link(u,edge,'A');link(v,edge,'B')
 edge_scale=expr('edge_scale','Multiply',{'ConstB':10.});link(edge,edge_scale,'A');edge_clamp=expr('edge_clamp','Saturate');link(edge_scale,edge_clamp,'Input')
 luma_weights=expr('luminance_weights','Constant3Vector',{'Constant':{'r':.2126,'g':.7152,'b':.0722,'a':1.}});luma=expr('luminance','DotProduct');link(stone,luma,'A','RGB');link(luma_weights,luma,'B')
 coverage_scale=expr('coverage_scale','Multiply',{'ConstB':12.});link(luma,coverage_scale,'A');coverage_bias=expr('coverage_bias','Add',{'ConstB':.35});link(coverage_scale,coverage_bias,'A');coverage=expr('coverage','Saturate');link(coverage_bias,coverage,'Input')
 alpha0=expr('edge_coverage','Multiply');link(edge_clamp,alpha0,'A');link(coverage,alpha0,'B');alpha=expr('paint_strength','Multiply',{'ConstB':.85});link(alpha0,alpha,'A')
 color=expr('paint_over_stone','LinearInterpolate');link(stone,color,'A','RGB');link(painting,color,'B','RGB');link(alpha,color,'Alpha')
 rough=expr('roughness','Constant',{'R':.94});spec=expr('specular','Constant',{'R':.15});metal=expr('metallic','Constant',{'R':0.})
 for n,prop,pin in [(color,'MP_BaseColor',''),(normal,'MP_Normal','RGB'),(rough,'MP_Roughness',''),(spec,'MP_Specular',''),(metal,'MP_Metallic','')]:output(n,prop,pin)
 call('material','layout_expressions',{'material_or_function':mat});errors=call('material','recompile',{'material_or_function':mat});assert not errors,errors
 for i in range(1,5):
  key=str(i);name=f'MI_Mural{i:02d}'
  if key not in state['instances']:
   assert not call('asset','exists',{'path':MURAL+'/'+name});state['instances'][key]=call('instance','create',{'folder_path':MURAL,'asset_name':name,'parent':mat});save()
  tex={'refPath':f'/Game/ArtPass/FortressMurals/v001/T_Mural{i:02d}.T_Mural{i:02d}'}
  call('instance','set_texture_parameter',{'instance':state['instances'][key],'name':'MuralAlbedo','value':tex})
  assert call('instance','get_texture_parameter',{'instance':state['instances'][key],'name':'MuralAlbedo'})==tex;tag(state['instances'][key])
 # Duplicate the owned prior floor graph, never alter it. Its bounded derivative
 # normal construction is retained, with a new neutral texture and dry finish.
 if 'floorTexture' not in state:
  assert not call('asset','exists',{'path':FLOOR+'/T_FortressFloor'})
  refs=call('texture','import_file',{'folder_path':FLOOR,'asset_name':'T_FortressFloor','source_file':str(source)});assert len(refs)==1;state['floorTexture']=refs[0];save()
 props(state['floorTexture'],{'SRGB':True,'AddressX':'TA_Wrap','AddressY':'TA_Wrap','PowerOfTwoMode':'StretchToPowerOfTwo','MaxTextureSize':2048});tag(state['floorTexture'])
 if 'floorMaterial' not in state:
  assert not call('asset','exists',{'path':FLOOR+'/M_FortressFloor'})
  assert call('asset','duplicate',{'path':'/Game/ArtPass/Floor/M_CathedralFloor_v001','new_path':FLOOR+'/M_FortressFloor'}) is True
  state['floorMaterial']={'refPath':FLOOR+'/M_FortressFloor.M_FortressFloor'};save()
 floor=state['floorMaterial'];changes=[]
 for n in call('material','get_expressions',{'material_or_function':floor}):
  name=n['refPath'].split(':')[-1]
  if 'MaterialExpressionTextureSampleParameter2D' in name:
   values=get(n,['ParameterName'])
   if values.get('ParameterName')=='FloorAlbedo':props(n,{'Texture':state['floorTexture']});changes.append('albedo')
  elif 'MaterialExpressionDivide' in name:props(n,{'ConstB':500.});changes.append('scale')
  elif 'MaterialExpressionClamp' in name:props(n,{'MinDefault':.9,'MaxDefault':.98});changes.append('roughness_limits')
  elif 'MaterialExpressionScalarParameter' in name:
   values=get(n,['ParameterName'])
   if values.get('ParameterName')=='Roughness':props(n,{'DefaultValue':.94});changes.append('roughness')
   if values.get('ParameterName')=='BumpCm':props(n,{'DefaultValue':.025});changes.append('bump')
  elif 'MaterialExpressionConstant_' in name:
   if abs(get(n,['R']).get('R',0)-.2)<.001:props(n,{'R':.12});changes.append('specular')
 assert set(changes)>={'albedo','scale','roughness_limits','roughness','bump'},changes
 errors=call('material','recompile',{'material_or_function':floor});assert not errors,errors;tag(floor)
 refs=[mat,floor,state['floorTexture']]+list(state['instances'].values());assert call('asset','save_assets',{'asset_paths':[r['refPath'] for r in refs]}) is True
 state['complete']=True;state['floorChanges']=changes;save();print('Native stone-paint and dry-floor materials saved; visual acceptance pending')
if __name__=='__main__':main()
