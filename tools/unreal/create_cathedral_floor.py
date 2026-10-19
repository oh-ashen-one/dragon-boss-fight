"""Create the generated-albedo cathedral floor in the owned Unreal editor.

Native invocation only; no engine launch, paid generation, baked normal map or
asset overwrite. The shallow derivative bump is explicitly an albedo-derived
surface detail approximation. Flat gameplay collision is independent.
"""
import datetime
import hashlib
import json
from pathlib import Path
import unreal

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'Local/art-pass-20261019/references/cathedral-floor-albedo-v1.png'
DEST='/Game/ArtPass/Floor'
MATERIAL=DEST+'/M_CathedralFloor_v001'
TEXTURE=DEST+'/T_CathedralFloorAlbedo_v001'
OWNER='Veyr.cathedral-floor.v001'
NORMAL_CODE=r'''
float3 N=normalize(SurfaceNormal);
float3 dx=ddx(Position),dy=ddy(Position);
float3 r1=cross(dy,N),r2=cross(N,dx);
float surfaceDet=dot(dx,r1);
float luminance=dot(Albedo,float3(0.2126,0.7152,0.0722));
// At most1.2mm of apparent depth; color is not asserted to be measured height.
float height=(smoothstep(0.015,0.12,luminance)*0.8+saturate(luminance)*0.2)*clamp(BumpCm,0.0,0.12);
float3 gradient=(ddx(height)*r1+ddy(height)*r2)*sign(surfaceDet)/max(abs(surfaceDet),0.00001);
// Limit steep grazing derivatives instead of allowing unstable dark spikes.
gradient*=min(1.0,0.18/max(length(gradient),0.00001));
return normalize(N-gradient);
'''


def run():
    if Path(unreal.Paths.project_dir()).resolve()!=(ROOT/'Unreal/Veyr').resolve():
        raise RuntimeError('Incorrect owned project for cathedral floor')
    if not SOURCE.is_file():raise RuntimeError('Generated floor albedo missing')
    source_hash=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    recipe=hashlib.sha256((OWNER+source_hash+NORMAL_CODE+'worldXY400-rough080-spec020-metal0').encode()).hexdigest()
    output=ROOT/'Local/art-pass-20261019'/('floor-native-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    output.parent.mkdir(parents=True,exist_ok=True)
    receipt={'success':False,'nativeAppearanceAccepted':False,'material':MATERIAL,'texture':TEXTURE,
             'sourceSHA256':source_hash,'recipeSHA256':recipe,'tileWorldCm':400,'roughness':.8,'specular':.2,'metallic':0,
             'normalMethod':'world-space surface gradient using DDX/DDY of bounded albedo-luminance relief; not a supplied or baked normal map'}
    assets,lib=unreal.EditorAssetLibrary,unreal.MaterialEditingLibrary
    try:
        material=assets.load_asset(MATERIAL) if assets.does_asset_exist(MATERIAL) else None
        texture=assets.load_asset(TEXTURE) if assets.does_asset_exist(TEXTURE) else None
        recovery_nodes={}
        if material is not None:
            if not isinstance(material,unreal.Material):raise RuntimeError('Existing floor path is not a Material')
            if assets.get_metadata_tag(material,'VeyrOwner')==OWNER and assets.get_metadata_tag(material,'VeyrRecipe')==recipe:
                if not isinstance(texture,unreal.Texture2D) or assets.get_metadata_tag(texture,'VeyrSourceSHA256')!=source_hash:
                    raise RuntimeError('Existing material lacks matching source texture')
                receipt.update(success=True,reused=True);return material
            # One narrowly identified task-owned failure predates completion
            # metadata. Prove its receipt, graph, links and texture before reuse.
            failed_path=ROOT/'Local/art-pass-20261019/floor-native-20261019T194501252971Z.json'
            failed=json.loads(failed_path.read_text()) if failed_path.is_file() else {}
            if (failed.get('success') is not False or failed.get('material')!=MATERIAL or
                failed.get('texture')!=TEXTURE or failed.get('sourceSHA256')!=source_hash or failed.get('recipeSHA256')!=recipe or
                failed.get('error')!='Native expression connection failed: MaterialExpressionTextureSampleParameter2D.Coordinates' or
                assets.get_metadata_tag(material,'VeyrOwner') not in ('',OWNER) or
                material.get_path_name()!=MATERIAL+'.M_CathedralFloor_v001'):
                raise RuntimeError('Existing material is not the identified owned partial; no changes made')
            old=list(lib.get_material_expressions(material))
            expected={'MaterialExpressionWorldPosition','MaterialExpressionComponentMask','MaterialExpressionDivide','MaterialExpressionTextureSampleParameter2D'}
            if len(old)!=4 or {n.get_class().get_name() for n in old}!=expected:
                raise RuntimeError('Owned partial graph no longer matches the four-node failure; no changes made')
            recovery_nodes={n.get_class().get_name():n for n in old}
            world=recovery_nodes['MaterialExpressionWorldPosition'];mask=recovery_nodes['MaterialExpressionComponentMask']
            divide=recovery_nodes['MaterialExpressionDivide'];albedo=recovery_nodes['MaterialExpressionTextureSampleParameter2D']
            linked=lambda n:[x for x in lib.get_inputs_for_material_expression(material,n) if x is not None]
            if (linked(mask)!=[world] or linked(divide)!=[mask] or linked(albedo) or
                abs(divide.get_editor_property('const_b')-400.0)>.001 or
                str(albedo.get_editor_property('parameter_name'))!='FloorAlbedo' or
                albedo.get_editor_property('texture')!=texture or
                [bool(mask.get_editor_property(k)) for k in ('r','g','b','a')]!=[True,True,False,False]):
                raise RuntimeError('Owned partial inputs/parameters differ; no changes made')
            for prop in (unreal.MaterialProperty.MP_BASE_COLOR,unreal.MaterialProperty.MP_ROUGHNESS,
                         unreal.MaterialProperty.MP_SPECULAR,unreal.MaterialProperty.MP_METALLIC,unreal.MaterialProperty.MP_NORMAL):
                if lib.get_material_property_input_node(material,prop) is not None:
                    raise RuntimeError('Partial material already has a connected output; no changes made')
            receipt.update(recoveredOwnedPartial=True,recoveryReceipt=str(failed_path),reusedExpressionCount=4)
        if texture is not None:
            if not isinstance(texture,unreal.Texture2D) or assets.get_metadata_tag(texture,'VeyrOwner')!=OWNER or assets.get_metadata_tag(texture,'VeyrSourceSHA256')!=source_hash:
                raise RuntimeError('Existing floor texture differs; no overwrite')
        else:
            task=unreal.AssetImportTask()
            for key,value in {'filename':str(SOURCE),'destination_path':DEST,'destination_name':'T_CathedralFloorAlbedo_v001',
                              'automated':True,'replace_existing':False,'save':False}.items():task.set_editor_property(key,value)
            unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
            texture=assets.load_asset(TEXTURE)
            if not isinstance(texture,unreal.Texture2D):raise RuntimeError('Native floor Texture2D import failed')
            texture.set_editor_property('srgb',True)
            texture.set_editor_property('address_x',unreal.TextureAddress.TA_WRAP)
            texture.set_editor_property('address_y',unreal.TextureAddress.TA_WRAP)
            assets.set_metadata_tag(texture,'VeyrOwner',OWNER);assets.set_metadata_tag(texture,'VeyrSourceSHA256',source_hash)
            if not assets.save_loaded_asset(texture,False):raise RuntimeError('Floor texture save failed')
        if material is None:
            material=unreal.AssetToolsHelpers.get_asset_tools().create_asset('M_CathedralFloor_v001',DEST,unreal.Material,unreal.MaterialFactoryNew())
        if not isinstance(material,unreal.Material):raise RuntimeError('Native floor material creation failed')
        material.set_editor_property('blend_mode',unreal.BlendMode.BLEND_OPAQUE)
        material.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
        material.set_editor_property('tangent_space_normal',False)
        material.set_editor_property('used_with_instanced_static_meshes',True)
        expressions=[]
        def node(kind,**props):
            n=recovery_nodes.pop('MaterialExpression'+kind,None)
            if n is None:n=lib.create_material_expression(material,getattr(unreal,'MaterialExpression'+kind),-1200+(len(expressions)%5)*230,(len(expressions)//5)*200)
            if n is None:raise RuntimeError('Native expression creation failed: '+kind)
            for key,value in props.items():n.set_editor_property(key,value)
            expressions.append(n);return n
        def link(source,target,pin,output_name=''):
            pins=[str(x) for x in lib.get_material_expression_input_names(target)]
            actual={'Coordinates':'UVs','TextureObject':'Tex','Input':''}.get(pin,pin)
            available=['' if name in ('None','') else name for name in pins]
            if actual not in available:raise RuntimeError('Native input pin unavailable: '+kind_name(target)+'.'+actual+'; pins='+repr(pins))
            if not lib.connect_material_expressions(source,output_name,target,actual):raise RuntimeError('Native expression connection failed: '+kind_name(target)+'.'+actual+'; pins='+repr(pins))
        def kind_name(obj):return obj.get_class().get_name()
        position=node('WorldPosition')
        xy=node('ComponentMask',r=True,g=True,b=False,a=False);link(position,xy,'Input')
        divide=node('Divide',const_b=400.0);link(xy,divide,'A')
        albedo=node('TextureSampleParameter2D',parameter_name='FloorAlbedo',texture=texture);link(divide,albedo,'UVs')
        rough=node('ScalarParameter',parameter_name='Roughness',default_value=.8)
        rough_limit=node('Clamp',min_default=.7,max_default=.85);link(rough,rough_limit,'Input')
        spec=node('Constant',r=.2);metal=node('Constant',r=0.0)
        vertex=node('VertexNormalWS');normal=node('VertexInterpolator');link(vertex,normal,'VS')
        bump=node('ScalarParameter',parameter_name='BumpCm',default_value=.08)
        inputs={'Position':position,'SurfaceNormal':normal,'Albedo':albedo,'BumpCm':bump}
        custom_inputs=[]
        for name in inputs:
            entry=unreal.CustomInput();entry.set_editor_property('input_name',name);custom_inputs.append(entry)
        gradient=node('Custom',code=NORMAL_CODE,description='Bounded world-space luminance surface gradient',
                      output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3,inputs=custom_inputs)
        for name,expression in inputs.items():link(expression,gradient,name,'RGB' if name=='Albedo' else '')
        for expression,pin,prop in [(albedo,'RGB',unreal.MaterialProperty.MP_BASE_COLOR),(rough_limit,'',unreal.MaterialProperty.MP_ROUGHNESS),
                                    (spec,'',unreal.MaterialProperty.MP_SPECULAR),(metal,'',unreal.MaterialProperty.MP_METALLIC),
                                    (gradient,'',unreal.MaterialProperty.MP_NORMAL)]:
            if not lib.connect_material_property(expression,pin,prop):raise RuntimeError('Native material property connection failed')
        lib.layout_material_expressions(material)
        errors=[str(x) for x in lib.recompile_material(material)];receipt['compileErrors']=errors
        if errors:raise RuntimeError('Native floor shader compilation failed')
        assets.set_metadata_tag(material,'VeyrOwner',OWNER);assets.set_metadata_tag(material,'VeyrRecipe',recipe)
        if not assets.save_loaded_asset(material,False):raise RuntimeError('Native floor material save failed')
        receipt.update(success=True,reused=bool(receipt.get('recoveredOwnedPartial')),expressionCount=len(expressions));return material
    except Exception as error:
        receipt['error']=str(error);raise
    finally:
        output.write_text(json.dumps(receipt,indent=2)+'\n');unreal.log('VEYR_CATHEDRAL_FLOOR_RECEIPT '+str(output))


if __name__=='__main__':run()
