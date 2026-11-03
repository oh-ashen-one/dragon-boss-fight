#!/usr/bin/env python3
"""Reproduce four mural textures/materials through discovered native Unreal tools.

No editor launch, arbitrary script execution, overwrites or fallback material.
The two bootstrap objects are accepted only from this task's saved call receipts.
"""
import hashlib,json,sys
from pathlib import Path
from native_mcp import NativeMCP
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'Local/FortressEditor20261103';STATE=OUT/'mural-recipe-state.json';FOLDER='/Game/ArtPass/FortressMurals/v001'
TOOLS={k:'editor_toolset.toolsets.'+v for k,v in {'asset':'asset.AssetTools','texture':'texture.TextureTools','material':'material.MaterialTools','instance':'material_instance.MaterialInstanceTools','object':'object.ObjectTools'}.items()}
OWNER='veyr-fortress-20261103'
FILES=['mural-01-siege.png','mural-02-fallen-banners.png','mural-03-chained-wyrm.png','mural-04-war-chart.png']
def main():
    sources=[ROOT/'ArtSource/Fortress20261103/Murals'/f for f in FILES];assert all(p.is_file() for p in sources)
    hashes=[hashlib.sha256(p.read_bytes()).hexdigest() for p in sources]
    state=json.loads(STATE.read_text()) if STATE.exists() else {'owner':OWNER,'sourceHashes':hashes,'textures':{},'expressions':{},'instances':{},'completed':False}
    assert state['owner']==OWNER and state['sourceHashes']==hashes,'Preserve a conflicting recipe'
    c=NativeMCP(timeout=120);c.initialize()
    def save():
        tmp=STATE.with_suffix('.tmp');tmp.write_text(json.dumps(state,indent=2)+'\n');tmp.replace(STATE)
    def call(tool,name,args):
        response=c.request('tools/call',{'name':'call_tool','arguments':{'toolset_name':TOOLS.get(tool,tool),'tool_name':name,'arguments':args}})
        if 'error' in response or response.get('result',{}).get('isError'):
            state['failedCall']=name;save();raise RuntimeError('Native call failed; inspect receipt before retry: '+name)
        result=json.loads(response['result']['content'][0]['text']).get('returnValue');return result
    project=call('Users.midir.veyr-knight-20261028.tools.unreal.veyr_integration_toolset.VeyrIntegrationTools','inspect_project',{})
    assert Path(project['project_directory']).resolve()==ROOT/'Unreal/Veyr','Wrong editor project'
    def props(ref,values):
        assert ref['refPath'].startswith(FOLDER+'/')
        assert call('object','set_properties',{'instance':ref,'values':json.dumps(values)}) is True,'Native property write failed'
    def tag(ref,source_hash):
        call('asset','update_metadata_tags',{'asset_path':ref['refPath'],'set_tags':{'VeyrOwner':OWNER,'VeyrSourceSHA256':source_hash,'VeyrProvider':'built-in image_gen; model not exposed'}})
    save()
    for i,source in enumerate(sources,1):
        key=str(i);name=f'T_Mural{i:02d}';path=FOLDER+'/'+name
        if key not in state['textures']:
            if call('asset','exists',{'path':path}):
                receipt=OUT/'mural01-import.json'
                if i!=1 or not receipt.exists():raise RuntimeError('Preserve existing texture: '+name)
                refs=json.loads(receipt.read_text());assert refs==[{'refPath':path+'.'+name}]
            else:refs=call('texture','import_file',{'folder_path':FOLDER,'asset_name':name,'source_file':str(source)})
            assert len(refs)==1 and refs[0]['refPath']==path+'.'+name
            state['textures'][key]=refs[0];save()
        ref=state['textures'][key];props(ref,{'SRGB':True,'AddressX':'TA_Clamp','AddressY':'TA_Clamp','PowerOfTwoMode':'StretchToPowerOfTwo','MaxTextureSize':2048,'CompressionSettings':'TC_Default','MipGenSettings':'TMGS_FromTextureGroup'})
        tag(ref,hashes[i-1]);state.setdefault('textureSizes',{})[key]=call('texture','get_size',{'texture':ref});save()
    if 'material' not in state:
        name='M_FortressMural';path=FOLDER+'/'+name
        if call('asset','exists',{'path':path}):
            receipt=OUT/'mural-material-created.json';assert receipt.exists();mat=json.loads(receipt.read_text());assert mat=={'refPath':path+'.'+name}
            assert not call('material','get_expressions',{'material_or_function':mat}),'Unexpected existing graph'
        else:mat=call('material','create_material',{'folder_path':FOLDER,'asset_name':name})
        state['material']=mat;save()
    mat=state['material']
    def expression(key,kind,y):
        if key not in state['expressions']:
            ref=call('material','add_expression',{'material_or_function':mat,'expression_class':{'refPath':'/Script/Engine.MaterialExpression'+kind},'x':-400,'y':y})
            assert ref['refPath'].startswith(mat['refPath']);state['expressions'][key]=ref;save()
        return state['expressions'][key]
    color=expression('color','TextureSampleParameter2D',0)
    props(color,{'ParameterName':'MuralAlbedo','Texture':state['textures']['1']})
    outputs=call('material','get_expression_output_names',{'expression':color});assert 'RGB' in outputs
    def connect(node,output,prop):
        connection=call('material','get_property_input',{'material':mat,'material_property':prop})
        existing=connection.get('expression') if connection else None
        if existing in ('None','',None):existing=None
        if existing and existing.get('refPath'):
            assert existing==node,'Preserve conflicting material output'
        else:call('material','connect_to_output',{'expression':node,'output_name':output,'material_property':prop})
        assert call('material','get_property_input',{'material':mat,'material_property':prop})['expression']==node
    connect(color,'RGB','MP_BaseColor')
    for key,value,prop,y in [('roughness',.94,'MP_Roughness',200),('specular',.15,'MP_Specular',400),('metallic',0.,'MP_Metallic',600)]:
        node=expression(key,'ScalarParameter',y);props(node,{'ParameterName':'Mural'+key.title(),'DefaultValue':value});connect(node,'',prop)
    call('material','layout_expressions',{'material_or_function':mat});errors=call('material','recompile',{'material_or_function':mat});assert not errors,'Shader compilation errors'
    tag(mat,hashlib.sha256(''.join(hashes).encode()).hexdigest())
    for i in range(1,5):
        key=str(i);name=f'MI_Mural{i:02d}'
        if key not in state['instances']:
            assert not call('asset','exists',{'path':FOLDER+'/'+name}),'Preserve existing instance'
            state['instances'][key]=call('instance','create',{'folder_path':FOLDER,'asset_name':name,'parent':mat});save()
        ref=state['instances'][key];call('instance','set_texture_parameter',{'instance':ref,'name':'MuralAlbedo','value':state['textures'][key]})
        assert call('instance','get_texture_parameter',{'instance':ref,'name':'MuralAlbedo'})==state['textures'][key]
        tag(ref,hashes[i-1])
    paths=[r['refPath'] for r in state['textures'].values()]+[mat['refPath']]+[r['refPath'] for r in state['instances'].values()]
    assert call('asset','save_assets',{'asset_paths':paths}) is True
    state['completed']=True;state.pop('failedCall',None);save();print('FOUR_FORTRESS_MURALS_SAVED',json.dumps(state['instances']),flush=True)
if __name__=='__main__':main()
