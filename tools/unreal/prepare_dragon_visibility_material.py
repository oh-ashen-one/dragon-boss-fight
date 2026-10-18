"""Owner-run native UE 5.8 material clone for a bounded camera visibility tunnel.

No editor launch, source-material mutation, mesh assignment, external asset or
MPC. Call run(source_material_path, destination_path=None) through the owned
native editor, or run_from_import_receipt(private_import_receipt). Source must
be a direct UMaterial inside the task's private DragonV3B import version.

The clone preserves original PBR graph/texture connections. Only its opacity
mask is extended, using native DitherTemporalAA and ShadowReplace when present.
All runtime controls are ordinary MID vector/scalar parameters; Enabled=0 is
safe/default and degenerate camera/focus segments also keep the dragon opaque.

Verified against installed 5.8 MaterialEditingLibrary, Custom, WorldPosition,
ShadowReplace headers and the bundled DitherTemporalAA material function.
Source/compile/rendered acceptance are distinct; this helper never claims the
last one. Failed partial clones remain preserved with a private receipt.
"""
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / 'Unreal/Veyr'
OWNER = 'Veyr.dragon-camera-tunnel.v1'
GRAPH_VERSION = 'finite-soft-tunnel-protected-head-native-temporal-dither-v1'
FUNCTION_PATH = '/Engine/Functions/Engine_MaterialFunctions02/Utility/DitherTemporalAA.DitherTemporalAA'
PREFIX = 'Veyr camera tunnel / '
SCALARS = {'VeyrOcclusionRadius': 100., 'VeyrProtectedHeadRadius': 180., 'VeyrOcclusionEnabled': 0.}
VECTORS = ('VeyrCameraStart', 'VeyrPlayerFocus', 'VeyrProtectedHead')
TAG_OWNER = 'VeyrVisibilityOwner'
TAG_RECIPE = 'VeyrVisibilityRecipeSHA256'
TAG_GRAPH = 'VeyrVisibilityGraphSHA256'
TAG_SOURCE = 'VeyrVisibilitySource'
TAG_STATE = 'VeyrVisibilityState'

HLSL = r'''
// Original Veyr finite camera/player visibility mask. All positions are world cm.
float3 segment = PlayerFocus - CameraStart;
float lengthSquared = dot(segment, segment);
if (Enabled <= 0.0 || lengthSquared <= 1.0) return 1.0;
float segmentLength = sqrt(lengthSquared);
float along = dot(WorldPosition - CameraStart, segment) / segmentLength;
// Strictly preserve geometry behind the camera and beyond player focus.
if (along <= 0.0 || along >= segmentLength) return 1.0;
float radius = max(Radius, 1.0);
float feather = max(radius * 0.25, 1.0);
float3 closest = CameraStart + segment * (along / segmentLength);
float radial = 1.0 - smoothstep(radius - feather, radius, length(WorldPosition - closest));
float endpointFeather = min(feather, segmentLength * 0.25);
float axial = smoothstep(0.0, endpointFeather, along) * smoothstep(0.0, endpointFeather, segmentLength - along);
float headRadius = max(ProtectedHeadRadius, 0.0);
float headFeather = max(headRadius * 0.10, 1.0);
float headProtection = 1.0 - smoothstep(headRadius, headRadius + headFeather, length(WorldPosition - ProtectedHead));
float removal = saturate(Enabled) * radial * axial * (1.0 - headProtection);
return saturate(1.0 - removal);
'''.strip()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def reference_visibility(point, camera, focus, head, radius=100., head_radius=180., enabled=0.):
    """CPU geometric reference for meaningful boundedness checks, no renderer."""
    def sub(a, b): return [x-y for x,y in zip(a,b)]
    def dot(a, b): return sum(x*y for x,y in zip(a,b))
    def length(a): return math.sqrt(dot(a,a))
    def smooth(a, b, x):
        t=max(0.,min(1.,(x-a)/(b-a)));return t*t*(3.-2.*t)
    segment=sub(focus,camera);length_squared=dot(segment,segment)
    if enabled<=0 or length_squared<=1:return 1.
    segment_length=math.sqrt(length_squared);along=dot(sub(point,camera),segment)/segment_length
    if along<=0 or along>=segment_length:return 1.
    radius=max(radius,1.);feather=max(radius*.25,1.)
    closest=[a+d*along/segment_length for a,d in zip(camera,segment)]
    radial=1-smooth(radius-feather,radius,length(sub(point,closest)))
    ef=min(feather,segment_length*.25);axial=smooth(0,ef,along)*smooth(0,ef,segment_length-along)
    hr=max(head_radius,0.);hf=max(hr*.1,1.);protection=1-smooth(hr,hr+hf,length(sub(point,head)))
    return max(0.,min(1.,1-min(1.,enabled)*radial*axial*(1-protection)))


def geometry_checks():
    camera=(0,0,0);focus=(1000,0,0);far_head=(500,1000,0)
    cases=[('disabled',(500,0,0),far_head,0.,1.),('interior',(500,0,0),far_head,1.,0.),
           ('behind camera',(-50,0,0),far_head,1.,1.),('beyond focus',(1050,0,0),far_head,1.,1.),
           ('outside radius',(500,101,0),far_head,1.,1.),('protected head center',(500,0,0),(500,0,0),1.,1.),
           ('protected head surface',(500,0,0),(500,180,0),1.,1.)]
    rows=[]
    for label,p,h,e,expected in cases:
        value=reference_visibility(p,camera,focus,h,enabled=e)
        if abs(value-expected)>1e-9:raise RuntimeError('Visibility geometric invariant failed: '+label)
        rows.append({'case':label,'visibility':value})
    feather=reference_visibility((500,87.5,0),camera,focus,far_head,enabled=1.)
    if not 0<feather<1:raise RuntimeError('Soft edge is not fractional')
    if reference_visibility((0,0,0),camera,camera,far_head,enabled=1.)!=1:raise RuntimeError('Degenerate segment is not safe')
    rows.append({'case':'soft radial edge','visibility':feather});return rows


def run(source_material_path, destination_path=None):
    import unreal
    lib=unreal.MaterialEditingLibrary;assets=unreal.EditorAssetLibrary
    if Path(unreal.Paths.project_dir()).resolve()!=PROJECT.resolve():raise RuntimeError('Wrong owned project')
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None:
        raise RuntimeError('Stop the owned PIE session before material authoring')
    match=re.fullmatch(r'(/Game/Characters/Customuse/DragonV3B/[A-Za-z][A-Za-z0-9_]*)/Rig/[^/]+(?:\.[^/]+)?',source_material_path)
    if not match:raise ValueError('Source must be inside one private DragonV3B version/Rig folder')
    version_root=match.group(1);destination_path=destination_path or version_root+'/Visibility/M_VeyrDragonCameraTunnel'
    if not re.fullmatch(re.escape(version_root)+r'/Visibility/[A-Za-z][A-Za-z0-9_]*',destination_path):
        raise ValueError('Destination must be a named clone in the same private version/Visibility folder')
    source=assets.load_asset(source_material_path)
    if not isinstance(source,unreal.Material):raise RuntimeError('Expected direct UMaterial; no implicit instance flattening or parent edits')
    if source.get_editor_property('use_material_attributes'):raise RuntimeError('Material-attributes source needs a separately reviewed attributes wrapper')
    if source.get_editor_property('material_domain')!=unreal.MaterialDomain.MD_SURFACE:raise RuntimeError('Source is not a surface material')
    if source.get_editor_property('blend_mode') not in (unreal.BlendMode.BLEND_OPAQUE,unreal.BlendMode.BLEND_MASKED):
        raise RuntimeError('Only opaque/masked source materials are supported')
    needed=('MaterialExpressionCustom','CustomInput','MaterialExpressionWorldPosition','MaterialExpressionVectorParameter','MaterialExpressionScalarParameter','MaterialExpressionMaterialFunctionCall','MaterialExpressionConstant','MaterialExpressionMultiply')
    if any(not hasattr(unreal,name) for name in needed):raise RuntimeError('Required native expression class is unavailable')
    function=assets.load_asset(FUNCTION_PATH)
    if function is None:raise RuntimeError('Bundled native DitherTemporalAA function unavailable; no guessed substitute')
    shadow_available=hasattr(unreal,'MaterialExpressionShadowReplace')
    properties=['MP_BASE_COLOR','MP_METALLIC','MP_SPECULAR','MP_ROUGHNESS','MP_NORMAL','MP_EMISSIVE_COLOR','MP_AMBIENT_OCCLUSION','MP_WORLD_POSITION_OFFSET','MP_OPACITY','MP_OPACITY_MASK']
    properties=[(name,getattr(unreal.MaterialProperty,name)) for name in properties if hasattr(unreal.MaterialProperty,name)]
    optional_properties=('parameter_name','default_value','texture','r','g','b','a','const_a','const_b','const_exponent','code','description','material_function','coordinate_index','u_tiling','v_tiling','sampler_type')

    def simple(value):
        if value is None or isinstance(value,(str,int,float,bool)):return value
        if hasattr(value,'get_path_name'):return value.get_path_name()
        if all(hasattr(value,k) for k in ('r','g','b','a')):return [float(getattr(value,k)) for k in ('r','g','b','a')]
        if isinstance(value,(list,tuple)):return [simple(x) for x in value]
        return str(value)

    def graph(material, only_names=None, exclude_mask=False):
        rows=[]
        for expression in lib.get_material_expressions(material):
            if only_names is not None and expression.get_name() not in only_names:continue
            row={'name':expression.get_name(),'class':expression.get_class().get_name(),'inputs':[],'properties':{}}
            input_names=[str(n) for n in lib.get_material_expression_input_names(expression)]
            input_nodes=list(lib.get_inputs_for_material_expression(material,expression))
            if len(input_names)!=len(input_nodes):raise RuntimeError('Native input introspection lengths disagree')
            for name,node in zip(input_names,input_nodes):
                output=simple(lib.get_input_node_output_name_for_material_expression(expression,node)) if node is not None else None
                row['inputs'].append({'pin':name,'node':node.get_name() if node else None,'output':output})
            for name in optional_properties:
                try:row['properties'][name]=simple(expression.get_editor_property(name))
                except Exception:pass
            rows.append(row)
        roots={}
        for name,prop in properties:
            if exclude_mask and name=='MP_OPACITY_MASK':continue
            node=lib.get_material_property_input_node(material,prop)
            roots[name]={'node':node.get_name() if node else None,'output':str(lib.get_material_property_input_node_output_name(material,prop))}
        settings={key:simple(material.get_editor_property(key)) for key in ('material_domain','shading_model','two_sided','tangent_space_normal','use_material_attributes')}
        return {'expressions':sorted(rows,key=lambda x:x['name']),'roots':roots,'settings':settings}

    source_graph=graph(source);source_names={e['name'] for e in source_graph['expressions']};source_pbr=graph(source,source_names,True)
    conflicts=set(str(n) for n in lib.get_scalar_parameter_names(source))|set(str(n) for n in lib.get_vector_parameter_names(source))
    if conflicts.intersection(set(SCALARS)|set(VECTORS)):raise RuntimeError('Source already contains reserved visibility parameter names')
    source_textures=sorted(x.get_path_name() for x in lib.get_material_used_textures(source))
    recipe={'owner':OWNER,'version':GRAPH_VERSION,'source':source.get_path_name(),'sourceGraphSHA256':digest(source_graph),'code':HLSL,'function':FUNCTION_PATH,'scalars':SCALARS,'vectors':VECTORS,'shadowReplace':shadow_available}
    recipe_sha=digest(recipe)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');receipt_dir=ROOT/'Local/CustomuseMaterials';receipt_dir.mkdir(parents=True,exist_ok=True,mode=0o700);receipt_path=receipt_dir/(stamp+'-dragon-visibility.json')
    receipt={'success':False,'recipe':recipe,'recipeSHA256':recipe_sha,'destination':destination_path,'geometryChecks':geometry_checks(),'engineVersion':unreal.SystemLibrary.get_engine_version(),'sourceUnmodified':False,'nativeRenderedAcceptance':False,'shadowPassPreservationRequested':shadow_available}

    def save_receipt():
        tmp=receipt_path.with_suffix('.tmp')
        with os.fdopen(os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600),'w') as stream:json.dump(receipt,stream,indent=2)
        tmp.replace(receipt_path)

    def validate(material, recorded_graph=True):
        if not isinstance(material,unreal.Material):raise RuntimeError('Owned destination is not a Material')
        if str(assets.get_metadata_tag(material,TAG_OWNER))!=OWNER or str(assets.get_metadata_tag(material,TAG_RECIPE))!=recipe_sha or str(assets.get_metadata_tag(material,TAG_SOURCE))!=source.get_path_name():raise RuntimeError('Destination lacks exact owned source/recipe tags; refusing overwrite')
        if graph(material,source_names,True)!=source_pbr:raise RuntimeError('Original PBR graph/connections/settings changed')
        textures=sorted(x.get_path_name() for x in lib.get_material_used_textures(material))
        if not set(source_textures).issubset(textures) or any(x not in source_textures and not x.startswith('/Engine/') for x in textures):raise RuntimeError('Unexpected source texture changes')
        if material.get_editor_property('blend_mode')!=unreal.BlendMode.BLEND_MASKED:raise RuntimeError('Clone is not masked')
        for name,value in SCALARS.items():
            if abs(float(lib.get_material_default_scalar_parameter_value(material,name))-value)>1e-6:raise RuntimeError('Default scalar changed: '+name)
        if not set(VECTORS).issubset(str(n) for n in lib.get_vector_parameter_names(material)):raise RuntimeError('Required vector controls missing')
        custom=[x for x in lib.get_material_expressions(material) if isinstance(x,unreal.MaterialExpressionCustom) and str(x.get_editor_property('desc'))==PREFIX+'visibility_math']
        if len(custom)!=1 or custom[0].get_editor_property('code')!=HLSL:raise RuntimeError('Visibility math node/code mismatch')
        output=lib.get_material_property_input_node(material,unreal.MaterialProperty.MP_OPACITY_MASK)
        if output is None or str(output.get_editor_property('desc'))!=PREFIX+'final_mask':raise RuntimeError('Final opacity-mask connection missing')
        if recorded_graph and (str(assets.get_metadata_tag(material,TAG_STATE))!='complete' or str(assets.get_metadata_tag(material,TAG_GRAPH))!=digest(graph(material))):raise RuntimeError('Owned graph is partial or differs from its completed fingerprint')

    save_receipt()
    try:
        if assets.does_asset_exist(destination_path):
            material=assets.load_asset(destination_path);validate(material);receipt['reused']=True
        else:
            material=assets.duplicate_asset(source.get_path_name(),destination_path)
            if not isinstance(material,unreal.Material):raise RuntimeError('Native clone failed')
            receipt['reused']=False;receipt['createdObject']=material.get_path_name()
            for tag,value in ((TAG_OWNER,OWNER),(TAG_RECIPE,recipe_sha),(TAG_SOURCE,source.get_path_name()),(TAG_STATE,'building')):assets.set_metadata_tag(material,tag,value)
            save_receipt();count=0
            def node(class_name,label,**props):
                nonlocal count
                expression=lib.create_material_expression(material,getattr(unreal,class_name),-3000+(count%4)*260,-900+(count//4)*210)
                if expression is None:raise RuntimeError('Native node creation failed: '+class_name)
                count+=1;expression.set_editor_property('desc',PREFIX+label)
                for key,value in props.items():expression.set_editor_property(key,value)
                return expression
            def link(source_node,target,pin,source_output=''):
                names=[str(n) for n in lib.get_material_expression_input_names(target)];actual='' if pin=='Input' and names in (['None'],['']) else pin
                if (actual and actual not in names) or not lib.connect_material_expressions(source_node,source_output,target,actual):raise RuntimeError('Native graph connection failed: '+pin+'; available='+str(names))
            old_mask=lib.get_material_property_input_node(material,unreal.MaterialProperty.MP_OPACITY_MASK);old_output=str(lib.get_material_property_input_node_output_name(material,unreal.MaterialProperty.MP_OPACITY_MASK))
            one=node('MaterialExpressionConstant','one',r=1.)
            world=node('MaterialExpressionWorldPosition','world_position')
            params={name:node('MaterialExpressionVectorParameter',name,parameter_name=name,default_value=unreal.LinearColor(0,0,0,0)) for name in VECTORS}
            params.update({name:node('MaterialExpressionScalarParameter',name,parameter_name=name,default_value=value) for name,value in SCALARS.items()})
            inputs=['WorldPosition','CameraStart','PlayerFocus','ProtectedHead','Radius','ProtectedHeadRadius','Enabled'];custom_inputs=[]
            for name in inputs:
                entry=unreal.CustomInput();entry.set_editor_property('input_name',name);custom_inputs.append(entry)
            custom=node('MaterialExpressionCustom','visibility_math',code=HLSL,output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT1,inputs=custom_inputs,description='Finite camera tunnel with protected dragon head')
            for source_node,pin in [(world,'WorldPosition'),(params['VeyrCameraStart'],'CameraStart'),(params['VeyrPlayerFocus'],'PlayerFocus'),(params['VeyrProtectedHead'],'ProtectedHead'),(params['VeyrOcclusionRadius'],'Radius'),(params['VeyrProtectedHeadRadius'],'ProtectedHeadRadius'),(params['VeyrOcclusionEnabled'],'Enabled')]:link(source_node,custom,pin)
            dither=node('MaterialExpressionMaterialFunctionCall','native_temporal_dither',material_function=function)
            names=[str(n) for n in lib.get_material_expression_input_names(dither)];alpha=[n for n in names if re.sub(r'[^a-z]','',n.lower())=='alphathreshold']
            if len(alpha)!=1:raise RuntimeError('Bundled DitherTemporalAA Alpha Threshold input unavailable: '+str(names))
            link(custom,dither,alpha[0]);visibility=dither
            if shadow_available:
                visibility=node('MaterialExpressionShadowReplace','preserve_shadow_mask');link(dither,visibility,'Default');link(one,visibility,'Shadow')
            final=node('MaterialExpressionMultiply','final_mask');link(old_mask or one,final,'A',old_output if old_mask else '');link(visibility,final,'B')
            if not lib.connect_material_property(final,'',unreal.MaterialProperty.MP_OPACITY_MASK):raise RuntimeError('Opacity mask output connection failed')
            material.set_editor_property('blend_mode',unreal.BlendMode.BLEND_MASKED)
            material.set_editor_property('used_with_skeletal_mesh',True)
            if source.get_editor_property('blend_mode')==unreal.BlendMode.BLEND_OPAQUE:material.set_editor_property('opacity_mask_clip_value',.333333)
            receipt['addedExpressionCount']=count
            validate(material,False)
        errors=[str(e) for e in lib.recompile_material(material)];receipt['compileErrors']=errors
        if errors:raise RuntimeError('Native material compilation failed; partial clone preserved')
        if graph(source)!=source_graph:raise RuntimeError('Source material unexpectedly changed')
        receipt['sourceUnmodified']=True
        assets.set_metadata_tag(material,TAG_GRAPH,digest(graph(material)));assets.set_metadata_tag(material,TAG_STATE,'complete')
        if not assets.save_loaded_asset(material,False):raise RuntimeError('Clone save failed')
        validate(assets.load_asset(destination_path));receipt['success']=True;receipt['material']=material.get_path_name();receipt['expressionCount']=lib.get_num_material_expressions(material);receipt['graphSHA256']=digest(graph(material));receipt['runtimeParameters']={'vectors':list(VECTORS),'scalars':SCALARS};return receipt
    except Exception as error:
        receipt['error']=str(error);raise
    finally:
        save_receipt();unreal.log('VEYR_DRAGON_VISIBILITY_RECEIPT '+str(receipt_path))


def run_from_import_receipt(receipt_file, destination_path=None):
    path=Path(receipt_file).resolve()
    if not path.is_relative_to((ROOT/'Local/CustomuseImports').resolve()):raise ValueError('Use the task private native import receipt')
    data=json.loads(path.read_text())
    if not data.get('success'):raise ValueError('Import receipt is not successful')
    candidates=[obj['path'] for step in data.get('steps',[]) if step.get('destination','').endswith('/Rig') for obj in step.get('objects',[]) if obj.get('class')=='Material']
    if len(candidates)!=1:raise ValueError('Expected exactly one direct imported dragon material')
    return run(candidates[0],destination_path)
