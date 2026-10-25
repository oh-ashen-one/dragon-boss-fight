"""Author texture-backed FXv3 inside the verified native Unreal editor.

Run run() through the root-owned MCP session. Does not launch an engine.
Uses the approved built-in ImageGen fire atlas and smoke density under Local.
Preserves FXv2 and refuses to overwrite unowned/differing v3 assets.
"""
from pathlib import Path
import datetime,hashlib,json,struct
import unreal
ROOT=Path(__file__).resolve().parents[2]
DEST='/Game/Veyr/FX/v3'
OWNER='Veyr.generated-fire-atlas.v3'
TAG='VeyrFXv3Recipe'
LIB=unreal.MaterialEditingLibrary
ASSETS=unreal.EditorAssetLibrary

FIRE_CODE=r'''
float2 uv=saturate(UV);
float noise=Texture2DSample(Density,DensitySampler,frac(uv*2.7+float2(-Clock*.37+Seed*7,Seed*13))).r;
float2 flow=uv+float2((noise-.5)*.055,sin(uv.x*13-Clock*7+Seed*21)*.022*sin(uv.y*3.14159));
flow=saturate(flow);
float frame=frac(Clock*1.35+Seed*.91+Age*.13)*16.0;
float a=floor(frame),b=fmod(a+1.0,16.0);
// The generated 1254px image is NPOT. Normalised quarters plus a pixel inset
// avoid filtering across cell borders without resizing or stretching the atlas.
float inset=min(.08,TexelSize*16.0);
float2 celluv=lerp(float2(inset,inset),float2(1-inset,1-inset),flow);
float2 uva=(float2(fmod(a,4),floor(a/4))+celluv)/4.0;
float2 uvb=(float2(fmod(b,4),floor(b/4))+celluv)/4.0;
float4 flame=lerp(Texture2DSample(Atlas,AtlasSampler,uva),Texture2DSample(Atlas,AtlasSampler,uvb),frac(frame));
float edge=smoothstep(0,.055,uv.x)*smoothstep(0,.08,1-uv.x)*smoothstep(0,.075,uv.y)*smoothstep(0,.075,1-uv.y);
float density=saturate(max(flame.r,max(flame.g,flame.b))*1.4);
return float4(flame.rgb,flame.a*density*edge);
'''
SMOKE_CODE=r'''
float2 uv=UV-.5;
float a=Seed*6.283185;float2 q=float2(uv.x*cos(a)-uv.y*sin(a),uv.x*sin(a)+uv.y*cos(a));
float d0=Texture2DSample(Density,DensitySampler,frac(q*.85+.5+float2(Seed*7,-Clock*.035))).r;
float d1=Texture2DSample(Density,DensitySampler,frac(q*1.9+.5+float2(Clock*.018,Seed*11))).r;
float edge=1-smoothstep(.26,.50,length(uv));
float opacity=saturate(d0*.72+d1*.28)*edge;
return float4(float3(.65,.61,.57)*(0.55+0.45*d1),opacity);
'''
EMBER_CODE=r'''
float2 p=(UV-.5)*float2(1.0,1.7);
float glow=pow(saturate(1-length(p)*2),2.5);
return float4(float3(1,.48,.08),glow);
'''
RECIPES={
 'M_VeyrBreathCore':{'kind':'fire','brightness':4.5,'tint':[1.,.93,.78,1.],'blend':'additive'},
 'M_VeyrBreathFlame':{'kind':'fire','brightness':3.2,'tint':[1.,.83,.65,1.],'blend':'additive'},
 'M_VeyrBreathSmoke':{'kind':'smoke','brightness':.08,'tint':[.22,.21,.20,1.],'blend':'translucent'},
 'M_VeyrBreathEmber':{'kind':'ember','brightness':7.,'tint':[1.,.75,.35,1.],'blend':'additive'},
}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def enum(cls,*names):
 for n in names:
  if hasattr(cls,n):return getattr(cls,n)
 raise RuntimeError('Native enum unavailable: '+str(names))

def texture(path,name,colour):
 path=Path(path).resolve()
 if not path.is_relative_to((ROOT/'Local/ArtPass20261025/FX').resolve()) or not path.is_file():raise ValueError('Expected generated project-local fire texture')
 raw=path.read_bytes()
 if raw[:8]!=b'\x89PNG\r\n\x1a\n':raise ValueError('Expected PNG')
 width,height=struct.unpack('>II',raw[16:24]);asset_path=DEST+'/'+name;fingerprint=sha(path)
 if ASSETS.does_asset_exist(asset_path):
  obj=ASSETS.load_asset(asset_path)
  if not isinstance(obj,unreal.Texture2D) or str(ASSETS.get_metadata_tag(obj,'VeyrFXv3SourceSHA256'))!=fingerprint:raise RuntimeError('Preserving unrelated/different texture: '+asset_path)
  return obj,width,height
 task=unreal.AssetImportTask();task.filename=str(path);task.destination_path=DEST;task.destination_name=name
 task.automated=True;task.replace_existing=False;task.save=True
 unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
 obj=ASSETS.load_asset(asset_path)
 if not isinstance(obj,unreal.Texture2D):raise RuntimeError('Native texture import failed: '+name)
 obj.set_editor_property('srgb',colour)
 obj.set_editor_property('compression_settings',enum(unreal.TextureCompressionSettings,'TC_DEFAULT') if colour else enum(unreal.TextureCompressionSettings,'TC_MASKS'))
 obj.set_editor_property('address_x',enum(unreal.TextureAddress,'TA_CLAMP') if colour else enum(unreal.TextureAddress,'TA_WRAP'))
 obj.set_editor_property('address_y',enum(unreal.TextureAddress,'TA_CLAMP') if colour else enum(unreal.TextureAddress,'TA_WRAP'))
 if width&(width-1) or height&(height-1):
  obj.set_editor_property('mip_gen_settings',enum(unreal.TextureMipGenSettings,'TMGS_NO_MIPMAPS'))
  obj.set_editor_property('never_stream',True)
 ASSETS.set_metadata_tag(obj,'VeyrFXv3SourceSHA256',fingerprint);ASSETS.set_metadata_tag(obj,'VeyrFXv3Owner',OWNER)
 if not ASSETS.save_loaded_asset(obj,False):raise RuntimeError('Texture save failed: '+name)
 return obj,width,height

def create_graph(material,recipe,atlas,density,atlas_width):
 count=0
 def node(kind,**props):
  nonlocal count
  e=LIB.create_material_expression(material,getattr(unreal,kind),-1800+(count%5)*260,-600+(count//5)*210)
  if e is None:raise RuntimeError('Native node failed: '+kind)
  e.set_editor_property('desc','Veyr textured fire v3 / '+str(count));count+=1
  for k,v in props.items():e.set_editor_property(k,v)
  return e
 def link(a,b,pin='',output=''):
  names=[str(n) for n in LIB.get_material_expression_input_names(b)]
  if pin=='Input' and names in (['None'],['']):pin=''
  if not LIB.connect_material_expressions(a,output,b,pin):raise RuntimeError('Native graph link failed: '+pin)
 def mul(a,b):
  e=node('MaterialExpressionMultiply');link(a,e,'A');link(b,e,'B');return e
 def data(index,default):
  raw=node('MaterialExpressionPerInstanceCustomData',data_index=index,const_default_value=default)
  e=node('MaterialExpressionVertexInterpolator');link(raw,e,'VS');return e
 material.set_editor_property('blend_mode',unreal.BlendMode.BLEND_ADDITIVE if recipe['blend']=='additive' else unreal.BlendMode.BLEND_TRANSLUCENT)
 material.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_DEFAULT_LIT if recipe['kind']=='smoke' else unreal.MaterialShadingModel.MSM_UNLIT)
 material.set_editor_property('two_sided',True);material.set_editor_property('disable_depth_test',False)
 material.set_editor_property('used_with_instanced_static_meshes',True)
 if recipe['kind']=='smoke':material.set_editor_property('translucency_lighting_mode',enum(unreal.TranslucencyLightingMode,'TLM_VOLUMETRIC_NON_DIRECTIONAL','TLM_VOLUMETRICNONDIRECTIONAL'))
 uv=node('MaterialExpressionTextureCoordinate');clock=node('MaterialExpressionTime')
 alpha,seed,age,heat=[data(i,v) for i,v in enumerate([0.,0.,0.,1.])]
 inp={'UV':uv,'Clock':clock,'Seed':seed,'Age':age}
 if recipe['kind'] in ('fire','smoke'):inp['Density']=node('MaterialExpressionTextureObjectParameter',parameter_name='Density',texture=density,sampler_type=enum(unreal.MaterialSamplerType,'SAMPLERTYPE_MASKS'))
 if recipe['kind']=='fire':
  inp['Atlas']=node('MaterialExpressionTextureObjectParameter',parameter_name='Atlas',texture=atlas,sampler_type=enum(unreal.MaterialSamplerType,'SAMPLERTYPE_COLOR'))
  inp['TexelSize']=node('MaterialExpressionScalarParameter',parameter_name='AtlasTexelSize',default_value=1./atlas_width)
 code=FIRE_CODE if recipe['kind']=='fire' else SMOKE_CODE if recipe['kind']=='smoke' else EMBER_CODE
 inputs=[]
 for name in inp:
  entry=unreal.CustomInput();entry.set_editor_property('input_name',name);inputs.append(entry)
 custom=node('MaterialExpressionCustom',code=code,output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT4,inputs=inputs,description='Generated atlas flow / smoke density v3')
 for name,e in inp.items():link(e,custom,name)
 rgb=node('MaterialExpressionComponentMask',r=True,g=True,b=True,a=False);link(custom,rgb,'Input')
 opacity=node('MaterialExpressionComponentMask',r=False,g=False,b=False,a=True);link(custom,opacity,'Input')
 fade=node('MaterialExpressionDepthFade',fade_distance_default=28.);link(mul(opacity,alpha),fade,'Opacity')
 tint=node('MaterialExpressionVectorParameter',parameter_name='Tint',default_value=unreal.LinearColor(*recipe['tint']))
 bright=node('MaterialExpressionScalarParameter',parameter_name='Brightness',default_value=recipe['brightness'])
 colour=mul(rgb,tint);emission=mul(mul(colour,bright),heat)
 if not LIB.connect_material_property(emission,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR):raise RuntimeError('Emissive link failed')
 if not LIB.connect_material_property(fade,'',unreal.MaterialProperty.MP_OPACITY):raise RuntimeError('Opacity link failed')
 if recipe['kind']=='smoke':
  if not LIB.connect_material_property(colour,'',unreal.MaterialProperty.MP_BASE_COLOR):raise RuntimeError('Smoke diffuse link failed')
  rough=node('MaterialExpressionConstant',r=1.)
  LIB.connect_material_property(rough,'',unreal.MaterialProperty.MP_ROUGHNESS)
 LIB.layout_material_expressions(material)
 return count

def run():
 if Path(unreal.Paths.project_dir()).resolve()!=(ROOT/'Unreal/Veyr').resolve():raise RuntimeError('Wrong Unreal project')
 inputs=ROOT/'Local/ArtPass20261025/FX';paths=[inputs/'fire-atlas.png',inputs/'smoke-density.png']
 fingerprint=hashlib.sha256(json.dumps({'source':[sha(p) for p in paths],'fire':FIRE_CODE,'smoke':SMOKE_CODE,'ember':EMBER_CODE,'recipes':RECIPES},sort_keys=True).encode()).hexdigest()
 receipt={'owner':OWNER,'recipeSHA256':fingerprint,'sourceTextures':[{ 'file':p.name,'sha256':sha(p)} for p in paths],'materials':[],'success':False,'nativeVisualAcceptance':False}
 folder=ROOT/'Local/FireMaterials';folder.mkdir(parents=True,exist_ok=True);out=folder/(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-v3.json')
 try:
  for name in RECIPES:
   path=DEST+'/'+name
   if ASSETS.does_asset_exist(path) and str(ASSETS.get_metadata_tag(ASSETS.load_asset(path),TAG))!=fingerprint:raise RuntimeError('Preserving existing different material: '+path)
  atlas,width,height=texture(paths[0],'T_FireAtlas',True);density,sw,sh=texture(paths[1],'T_SmokeDensity',False)
  if width!=height:raise RuntimeError('Expected square 4x4 fire atlas')
  receipt['atlasSize']=[width,height];receipt['atlasGrid']=[4,4];receipt['cellUVInsetPixels']=4;receipt['smokeSize']=[sw,sh]
  for name,recipe in RECIPES.items():
   path=DEST+'/'+name;existing=ASSETS.does_asset_exist(path)
   material=ASSETS.load_asset(path) if existing else unreal.AssetToolsHelpers.get_asset_tools().create_asset(name,DEST,unreal.Material,unreal.MaterialFactoryNew())
   if not isinstance(material,unreal.Material):raise RuntimeError('Material creation failed: '+name)
   if not existing:create_graph(material,recipe,atlas,density,width)
   errors=[str(e) for e in LIB.recompile_material(material)]
   if errors:raise RuntimeError('Material compile errors: '+name+' '+str(errors))
   ASSETS.set_metadata_tag(material,TAG,fingerprint);ASSETS.set_metadata_tag(material,'VeyrFXv3Owner',OWNER)
   if not ASSETS.save_loaded_asset(material,False):raise RuntimeError('Material save failed: '+name)
   receipt['materials'].append({'path':material.get_path_name(),'reused':existing,'expressionCount':LIB.get_num_material_expressions(material)})
  receipt['success']=True
 except Exception as e:receipt['error']=str(e);raise
 finally:out.write_text(json.dumps(receipt,indent=2)+'\n');unreal.log('VEYR_FIRE_V3_RECEIPT '+str(out))
 return receipt

if __name__=='__main__':run()
