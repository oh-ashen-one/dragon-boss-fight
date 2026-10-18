"""Create Veyr's original world-space weathered stone graph in the owned editor.
No downloaded textures, no editor launch, and no replacement of existing assets.
"""
import datetime
import hashlib
import json
from pathlib import Path
import unreal

ROOT = Path(__file__).resolve().parents[2]
DESTINATION = '/Game/Veyr/Materials'
NAME = 'M_CathedralStone_v3'
OWNER = 'Veyr.original-weathered-stone.v1'
RECIPE = 'world-grain-subtle-stains-gradient-bump-006cm-color-roughness-metallic-emission-v3'
LIB = unreal.MaterialEditingLibrary
ASSETS = unreal.EditorAssetLibrary
NOISE_ENUM = getattr(unreal.NoiseFunction,'NOISEFUNCTION_GRADIENT_ALU',getattr(unreal.NoiseFunction,'GRADIENT_ALU',None))
if NOISE_ENUM is None: raise RuntimeError('Required native gradient noise enum is unavailable')


def run():
    if Path(unreal.Paths.project_dir()).resolve() != (ROOT/'Unreal/Veyr').resolve():
        raise RuntimeError('Incorrect project for stone authoring')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = ROOT/'Local'/('stone-material-'+stamp+'.json')
    receipt = {'success': False, 'externalTextures': False, 'nativeAppearanceAccepted': False}
    path = DESTINATION+'/'+NAME
    digest = hashlib.sha256(RECIPE.encode()).hexdigest()
    try:
        reused = ASSETS.does_asset_exist(path)
        if reused:
            material = ASSETS.load_asset(path)
            if (not isinstance(material, unreal.Material) or material.get_path_name() != path+'.'+NAME or
                ASSETS.get_metadata_tag(material,'VeyrOwner') != OWNER or
                ASSETS.get_metadata_tag(material,'VeyrRecipe') != digest):
                raise RuntimeError('Existing material is not the matching owned recipe; no changes made')
        else:
            material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(NAME, DESTINATION, unreal.Material, unreal.MaterialFactoryNew())
            if not material or material.get_path_name() != path+'.'+NAME:
                raise RuntimeError('Native creation returned an unexpected object path')
            material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_OPAQUE)
            material.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
            material.set_editor_property('tangent_space_normal', False)
            material.set_editor_property('used_with_instanced_static_meshes', True)
            count = 0
            def node(kind, **props):
                nonlocal count
                n = LIB.create_material_expression(material, getattr(unreal, 'MaterialExpression'+kind), (count%7)*220-1800, (count//7)*180)
                count += 1
                if n is None: raise RuntimeError('Expression creation failed: '+kind)
                for key,value in props.items(): n.set_editor_property(key,value)
                return n
            def link(a,b,pin):
                names = [str(x) for x in LIB.get_material_expression_input_names(b)]
                actual = ('' if names[0] in ('None','') else names[0]) if pin=='Input' and len(names)==1 else pin
                if (actual and actual not in names) or not LIB.connect_material_expressions(a,'',b,actual):
                    raise RuntimeError('Native pin mismatch: '+pin+' available='+str(names))
            def unary(kind,a):
                n=node(kind);link(a,n,'Input');return n
            def binary(kind,a,b):
                n=node(kind);link(a,n,'A');link(b,n,'B');return n
            def constant(v): return node('Constant',r=v)
            def multiply(a,b): return binary('Multiply',a,b)
            position=node('WorldPosition')
            def noise(scale):
                n=node('Noise',scale=scale,quality=1,levels=1,output_min=0.0,output_max=1.0,
                       noise_function=NOISE_ENUM)
                link(position,n,'World Position');return n
            stain=noise(.009);grain=noise(.18)
            color=node('VectorParameter',parameter_name='Color',default_value=unreal.LinearColor(.17,.195,.22,1))
            tint=binary('Add',constant(.82),multiply(stain,constant(.22)))
            fine=binary('Add',constant(.94),multiply(grain,constant(.06)))
            base=multiply(multiply(color,tint),fine)
            roughness=node('ScalarParameter',parameter_name='Roughness',default_value=.78)
            rough=multiply(roughness,binary('Add',constant(.82),multiply(grain,constant(.18))))
            metal=node('ScalarParameter',parameter_name='Metallic',default_value=0.0)
            emission=node('ScalarParameter',parameter_name='Emission',default_value=0.0)
            # World-space surface-gradient bump: normal perturbation uses the
            # actual projected position derivatives, not screen axes as normals.
            vertex_normal=node('VertexNormalWS')
            normal=node('VertexInterpolator');link(vertex_normal,normal,'VS')
            dx=unary('DDX',position);dy=unary('DDY',position)
            height=multiply(grain,constant(.06))
            dhx=unary('DDX',height);dhy=unary('DDY',height)
            r1=binary('CrossProduct',dy,normal);r2=binary('CrossProduct',normal,dx)
            det=binary('DotProduct',dx,r1)
            gradient=multiply(binary('Add',multiply(r1,dhx),multiply(r2,dhy)),unary('Sign',det))
            bumped=unary('Normalize',binary('Subtract',multiply(normal,unary('Abs',det)),gradient))
            for expression,prop in [(base,unreal.MaterialProperty.MP_BASE_COLOR),(rough,unreal.MaterialProperty.MP_ROUGHNESS),
                                    (metal,unreal.MaterialProperty.MP_METALLIC),(multiply(color,emission),unreal.MaterialProperty.MP_EMISSIVE_COLOR),
                                    (bumped,unreal.MaterialProperty.MP_NORMAL)]:
                if not LIB.connect_material_property(expression,'',prop): raise RuntimeError('Material property connection failed')
            LIB.layout_material_expressions(material)
            receipt['expressionCount']=count
        errors=[str(x) for x in LIB.recompile_material(material)]
        receipt['compileErrors']=errors
        if errors: raise RuntimeError('Material compilation failed')
        ASSETS.set_metadata_tag(material,'VeyrOwner',OWNER)
        ASSETS.set_metadata_tag(material,'VeyrRecipe',digest)
        if not ASSETS.save_loaded_asset(material,False): raise RuntimeError('Material save failed')
        loaded=ASSETS.load_asset(path)
        if loaded.get_path_name()!=material.get_path_name() or ASSETS.get_metadata_tag(loaded,'VeyrRecipe')!=digest:
            raise RuntimeError('Saved object/metadata mismatch')
        receipt.update(success=True,path=path,reused=reused,recipeSHA256=digest)
    except Exception as error:
        receipt['error']=str(error)
        raise
    finally:
        output.write_text(json.dumps(receipt,indent=2)+'\n')
        unreal.log('VEYR_STONE_MATERIAL_RECEIPT '+str(output))
    return material

if __name__ == '__main__':run()
