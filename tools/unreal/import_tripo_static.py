"""Owner-run UE5.8 native Interchange import of private normalized Tripo GLBs.

This module NEVER launches an editor, creates substitute geometry, or overwrites
assets. Call run(private_plan_json) through native MCP Python or an owned editor
commandlet; VEYR_TRIPO_IMPORT_PLAN is supported when executed as a script.

Plan: {"schema":1,"assets":[{"name":"BoatGreatsword","version":"v001",
 "kind":"weapon"|"architecture","source":{"file":absolute_glb,"sha256":hex},
 "lod_triangles":[17242,8500,3500],"screen_sizes":[1.0,.45,.18]}]}.
Architecture defaults:150000/60000/15000 triangles. Source must have exactly one
identity-transformed static mesh instance and embedded PBR images; normalization
and grip/ground pivot decisions precede this importer. It verifies native bounds
against the GLB POSITION bounds using UE's (X,Z,Y)*100 conversion.

Installed API evidence (UE5.8, no guessed deprecated scripting library):
 StaticMeshEditorSubsystem.h/Helpers.h: set_lods, StaticMeshReductionOptions,
 StaticMeshReductionSettings; subsystem.cpp: set_lods updates LOD0 percent and
 copies LOD0 settings to later LODs. StaticMeshBuilder.cpp reduces later
 levels against the already reduced LOD0 mesh description, so their percentages
 are target/LOD0-budget rather than target/original-triangle-count. MeshReductionSettings.h: base_lod_model=0,
 silhouette/texture/shading_importance=HIGH, welding_threshold=0, triangle stop.
 StaticMesh.get_num_triangles/get_num_sections/get_num_vertices/get_num_tex_coords
 are UFUNCTIONs. get_num_tex_coords reads actual built render vertex buffers;
 subsystem.get_num_uv_channels reads editable MeshDescription and returns0 for
 generated LODs without a stored source description, so it is diagnostic only.
 GetNumTriangles uses GetRenderData(), which waits on asynchronous RenderData.
Native reduction preserves material sections and existing UV channels, but may
resample UV vertices; it does NOT promise byte-identical UVs or visual quality.
No Nanite assumption: explicitly disabled for predictable conventional budgets.
"""
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import uuid

ROOT=Path(__file__).resolve().parents[2]
PROJECT=ROOT/'Unreal/Veyr'
SOURCES=ROOT/'Local/art-pass-20261019/tripo'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inspect_source(entry):
    path=Path(entry['file']).resolve()
    if path.suffix.lower()!='.glb' or not path.is_relative_to(SOURCES.resolve()):
        raise ValueError('Use a normalized private GLB inside the task Tripo directory')
    data=path.read_bytes();sha=hashlib.sha256(data).hexdigest()
    if entry.get('sha256')!=sha:raise ValueError('Source SHA256 mismatch: '+path.name)
    if len(data)<28 or struct.unpack_from('<III',data)!=(0x46546C67,2,len(data)):
        raise ValueError('Invalid GLB header')
    size,kind=struct.unpack_from('<II',data,12)
    if kind!=0x4E4F534A or 20+size>len(data):raise ValueError('Missing GLB JSON')
    doc=json.loads(data[20:20+size]);accessors=doc.get('accessors',[])
    if doc.get('skins') or doc.get('animations'):raise ValueError('Expected static, animation-free source')
    if len(doc.get('meshes',[]))!=1 or sum('mesh' in n for n in doc.get('nodes',[]))!=1:
        raise ValueError('Expected exactly one normalized mesh instance')
    for node in doc.get('nodes',[]):
        if (node.get('translation',[0,0,0])!=[0,0,0] or node.get('scale',[1,1,1])!=[1,1,1] or
            node.get('rotation',[0,0,0,1])!=[0,0,0,1] or 'matrix' in node):
            raise ValueError('Bake source node transforms in the offline normalization step')
    if len(doc.get('buffers',[]))!=1 or any('uri' in v for v in doc.get('buffers',[])+doc.get('images',[])):
        raise ValueError('Only self-contained embedded GLBs are supported')
    low=[math.inf]*3;high=[-math.inf]*3;triangles=0
    for primitive in doc['meshes'][0]['primitives']:
        if primitive.get('mode',4)!=4 or 'indices' not in primitive:raise ValueError('Indexed triangles required')
        count=accessors[primitive['indices']]['count']
        if count%3:raise ValueError('Incomplete indexed triangle')
        triangles+=count//3
        attrs=primitive['attributes']
        if 'TEXCOORD_0' not in attrs or 'NORMAL' not in attrs or 'material' not in primitive:
            raise ValueError('Expected existing normals, UV0 and PBR material on every primitive')
        bounds=accessors[attrs['POSITION']]
        if len(bounds.get('min',[]))!=3 or len(bounds.get('max',[]))!=3:raise ValueError('Position bounds missing')
        for i in range(3):low[i]=min(low[i],bounds['min'][i]);high[i]=max(high[i],bounds['max'][i])
    if not triangles or not all(math.isfinite(x) for x in low+high):raise ValueError('Invalid geometry bounds')
    return {'file':str(path),'sha256':sha,'triangles':triangles,'sourceMaterialCount':len(doc.get('materials',[])),
            'sourceImageCount':len(doc.get('images',[])),
            'expectedBoundsCm':[[v[i]*100 for i in (0,2,1)] for v in (low,high)]}


def validate_plan(plan):
    if plan.get('schema')!=1 or not plan.get('assets'):raise ValueError('Expected schema1 nonempty asset list')
    checked=[];destinations=set()
    for item in plan['assets']:
        name,version=item['name'],item['version']
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,39}',name) or not re.fullmatch(r'v[0-9]{3,4}',version):
            raise ValueError('Safe asset name and fresh vNNN version required')
        if item['kind'] not in ('weapon','architecture'):raise ValueError('Unsupported asset kind')
        source=inspect_source(item['source'])
        targets=item.get('lod_triangles',[150000,60000,15000] if item['kind']=='architecture' else [source['triangles'],8500,3500])
        targets=[min(int(x),source['triangles']) for x in targets]
        screens=list(map(float,item.get('screen_sizes',[1.,.45,.18])))
        if len(targets)!=3 or len(screens)!=3 or any(x<100 for x in targets) or any(a<b for a,b in zip(targets,targets[1:])):
            raise ValueError('Require three descending positive triangle budgets')
        if screens[0]!=1. or not all(0<b<a<=1 for a,b in zip(screens,screens[1:])):
            raise ValueError('Screen sizes must start1 and decrease strictly above0')
        destination=f'/Game/ArtPass/Tripo/{name}_{version}'
        if destination in destinations:raise ValueError('Duplicate plan destination')
        destinations.add(destination)
        checked.append({'name':name,'version':version,'kind':item['kind'],'source':source,
                        'destination':destination,'lodTargets':targets,'screenSizes':screens})
    return checked


def run(plan_file):
    import unreal
    plan_path=Path(plan_file).resolve()
    if not plan_path.is_relative_to(SOURCES.resolve()):raise ValueError('Plan must remain in the private Tripo directory')
    checked=validate_plan(json.loads(plan_path.read_text()))
    if Path(unreal.Paths.project_dir()).resolve()!=PROJECT.resolve():raise RuntimeError('Wrong owned project')
    if unreal.EditorLevelLibrary.get_pie_worlds(False):raise RuntimeError('Stop PIE before import')
    library=unreal.EditorAssetLibrary
    for item in checked:
        folder=PROJECT/'Content'/item['destination'].removeprefix('/Game/')
        if folder.exists() or library.does_directory_exist(item['destination']):
            raise ValueError('Version exists; preserve partial/completed assets and choose a new version')
    for name in ('InterchangeManager','InterchangeGenericAssetsPipeline','ImportAssetParameters',
                 'StaticMeshEditorSubsystem','StaticMeshReductionOptions','StaticMeshReductionSettings',
                 'MeshFeatureImportance','StaticMeshReductionTerimationCriterion'):
        if not hasattr(unreal,name):raise RuntimeError('Required installed API not reflected: '+name)
    subsystem=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    for name in ('set_lods','get_lod_count','get_lod_reduction_settings','set_lod_reduction_settings','get_lod_material_slot'):
        if not hasattr(subsystem,name):raise RuntimeError('Required subsystem method unavailable: '+name)
    if not hasattr(unreal.StaticMesh,'get_num_tex_coords'):
        raise RuntimeError('Required render-buffer UV query get_num_tex_coords unavailable')
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    receipts=SOURCES/'native-imports';receipts.mkdir(parents=True,exist_ok=True)
    receipt_path=receipts/(stamp+'.json')
    receipt={'success':False,'planSHA256':digest(plan_path),'scriptSHA256':digest(Path(__file__)),
             'nativeVisualAcceptance':False,'naniteEnabled':False,'assets':[]}
    def save_receipt():
        with os.fdopen(os.open(receipt_path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600),'w') as stream:
            json.dump(receipt,stream,indent=2);stream.write('\n')
    def sanitize(obj,source_sha):
        # StaticMesh exposes writable import data. Texture import data is a
        # read-only native property in UE5.8; preserve it in this PRIVATE asset
        # namespace instead of bypassing reflection restrictions. No raw assets
        # from this namespace are published in the source repository.
        if isinstance(obj,unreal.StaticMesh):
            obj.set_editor_property('asset_import_data',None)
            if obj.get_editor_property('asset_import_data') is not None:raise RuntimeError('Mesh import metadata was not cleared')
        else:
            receipt.setdefault('privateImportMetadataRetained',[]).append(obj.get_path_name())
        for key in library.get_metadata_tag_values(obj):library.remove_metadata_tag(obj,key)
        library.set_metadata_tag(obj,'VeyrSourceSHA256',source_sha)
        library.set_metadata_tag(obj,'VeyrSourceProvider','Tripo')
        library.set_metadata_tag(obj,'VeyrImportRecipe','NativeInterchangeStaticLOD_v1')
    def bounds(mesh):
        b=mesh.get_bounds();origin=[getattr(b.origin,a) for a in ('x','y','z')];extent=[getattr(b.box_extent,a) for a in ('x','y','z')]
        return [[o-e for o,e in zip(origin,extent)],[o+e for o,e in zip(origin,extent)]]
    save_receipt()
    try:
        for item in checked:
            source=item['source'];destination=item['destination'];record={**item,'status':'IMPORTING','objects':[]};receipt['assets'].append(record);save_receipt()
            pipeline=unreal.InterchangeGenericAssetsPipeline();mesh_pipeline=pipeline.get_editor_property('mesh_pipeline')
            for key,value in [('import_static_meshes',True),('import_skeletal_meshes',False),('collision',False),('build_nanite',False)]:mesh_pipeline.set_editor_property(key,value)
            pipeline.get_editor_property('common_meshes_properties').set_editor_property('recompute_normals',False)
            pipeline.get_editor_property('animation_pipeline').set_editor_property('import_animations',False)
            material_pipeline=pipeline.get_editor_property('material_pipeline')
            material_pipeline.set_editor_property('import_materials',True);material_pipeline.set_editor_property('reuse_existing_materials',False)
            material_pipeline.get_editor_property('texture_pipeline').set_editor_property('import_textures',True)
            params=unreal.ImportAssetParameters()
            for key,value in [('is_automated',True),('force_show_dialog',False),('replace_existing',False),('follow_redirectors',False)]:params.set_editor_property(key,value)
            params.set_editor_property('override_pipelines',[unreal.SoftObjectPath(pipeline.get_path_name())])
            manager=unreal.InterchangeManager.get_interchange_manager_scripted()
            objects=list(manager.import_asset(destination+'/Imported',unreal.InterchangeManager.create_source_data(source['file']),params) or [])
            record['objects']=[{'path':o.get_path_name(),'class':o.get_class().get_name()} for o in objects];save_receipt()
            if not objects or any(not o.get_path_name().startswith(destination+'/') for o in objects):raise RuntimeError('Import failed or returned assets outside the fresh version')
            meshes=[o for o in objects if isinstance(o,unreal.StaticMesh)]
            if len(meshes)!=1:raise RuntimeError('Expected exactly one imported StaticMesh')
            for obj in objects:
                if not isinstance(obj,(unreal.StaticMesh,unreal.MaterialInterface,unreal.Texture)):
                    raise RuntimeError('Unexpected returned asset class; metadata sanitation needs explicit support')
                sanitize(obj,source['sha256'])
            mesh=meshes[0];before=int(mesh.get_num_triangles(0));record['importedTriangles']=before;record['importedBoundsCm']=bounds(mesh)
            if before<=0:raise RuntimeError('No built native triangles')
            if max(abs(a-b) for aa,bb in zip(record['importedBoundsCm'],source['expectedBoundsCm']) for a,b in zip(aa,bb))>1.:
                raise RuntimeError('Native units/pivot differ from normalized source by more than1cm')
            materials=[slot.material_interface.get_path_name() if slot.material_interface else None for slot in mesh.get_editor_property('static_materials')]
            if not materials or any(m is None for m in materials):raise RuntimeError('Imported PBR material slot missing')
            record['materials']=materials
            original_slots={int(subsystem.get_lod_material_slot(mesh,0,i)) for i in range(int(mesh.get_num_sections(0)))}
            record['originalSectionMaterialSlots']=sorted(original_slots)
            if source['sourceImageCount'] and not any(isinstance(o,unreal.Texture) for o in objects):raise RuntimeError('GLB images did not yield native textures')
            # Configure quality priorities before set_lods copies LOD0 settings.
            settings=subsystem.get_lod_reduction_settings(mesh,0)
            for key,value in [('base_lod_model',0),('percent_triangles',1.),('percent_vertices',1.),('welding_threshold',0.),('max_deviation',0.),
                              ('recalculate_normals',False),('generate_unique_lightmap_u_vs',False),
                              ('silhouette_importance',unreal.MeshFeatureImportance.HIGH),('texture_importance',unreal.MeshFeatureImportance.HIGH),
                              ('shading_importance',unreal.MeshFeatureImportance.HIGH),('termination_criterion',unreal.StaticMeshReductionTerimationCriterion.TRIANGLES)]:
                settings.set_editor_property(key,value)
            subsystem.set_lod_reduction_settings(mesh,0,settings)
            options=unreal.StaticMeshReductionOptions();options.set_editor_property('auto_compute_lod_screen_size',False)
            reductions=[]
            for lod,(target,screen) in enumerate(zip(item['lodTargets'],item['screenSizes'])):
                base_count=before if lod==0 else min(before,item['lodTargets'][0])
                reduction=unreal.StaticMeshReductionSettings();reduction.set_editor_property('percent_triangles',min(1.,target/base_count));reduction.set_editor_property('screen_size',screen);reductions.append(reduction)
            options.set_editor_property('reduction_settings',reductions)
            if subsystem.set_lods(mesh,options)!=3:raise RuntimeError('Native set_lods did not create exactly3 LODs')
            record['lods']=[]
            for lod,target in enumerate(item['lodTargets']):
                count=int(mesh.get_num_triangles(lod));uv=int(mesh.get_num_tex_coords(lod));sections=int(mesh.get_num_sections(lod))
                slots=[int(subsystem.get_lod_material_slot(mesh,lod,i)) for i in range(sections)]
                record['lods'].append({'lod':lod,'targetTriangles':target,'triangles':count,'vertices':int(mesh.get_num_vertices(lod)),
                                      'uvChannels':uv,'uvValidationSource':'StaticMeshVertexBuffer via get_num_tex_coords','sectionMaterialSlots':slots,'screenSize':item['screenSizes'][lod]})
                save_receipt()
                if count<target*.5 or count>target*1.15+32:raise RuntimeError('Native triangle budget not achieved; no substitute or retry')
                if uv<1 or not slots or any(i<0 or i>=len(materials) for i in slots) or set(slots)!=original_slots:
                    raise RuntimeError('Reduction lost UVs or an original material section')
            if [s.material_interface.get_path_name() if s.material_interface else None for s in mesh.get_editor_property('static_materials')]!=materials:
                raise RuntimeError('Reduction altered material assignments')
            record['reducedBoundsCm']=bounds(mesh)
            canonical=destination+'/SM_'+item['name']+'_'+item['version']
            if library.does_asset_exist(canonical):raise RuntimeError('Canonical mesh unexpectedly exists')
            if not library.rename_asset(mesh.get_path_name(),canonical):raise RuntimeError('Canonical rename failed')
            record['mesh']=canonical
            for obj in objects:
                sanitize(obj,source['sha256'])
                if not library.save_loaded_asset(obj,False):raise RuntimeError('Native save failed')
            if digest(source['file'])!=source['sha256']:raise RuntimeError('Original source changed during import')
            record['status']='IMPORTED_REDUCED_SAVED_NATIVE_VISUAL_REVIEW_PENDING';save_receipt()
        receipt['success']=True
    except Exception as error:
        receipt['error']=str(error);receipt['failurePolicy']='Partial assets preserved. No automatic retry or overwrite. Choose a fresh version after diagnosis.'
        raise
    finally:
        save_receipt();unreal.log('VEYR_TRIPO_IMPORT_RECEIPT '+str(receipt_path))
    return receipt


def inspect_partial(receipt_file):
    """Read-only revalidation of an exact failed import; never imports/reduces.

    Requires the original failure receipt and its source-hash provenance tags.
    Uses render-buffer UV counts, including generated LODs. On success returns
    all evidence needed by finish_partial; originals/failure receipts stay intact.
    """
    import unreal
    receipt_path=Path(receipt_file).resolve()
    if not receipt_path.is_relative_to((SOURCES/'native-imports').resolve()):
        raise ValueError("Expected this task's exact private import receipt")
    if Path(unreal.Paths.project_dir()).resolve()!=PROJECT.resolve():raise RuntimeError('Wrong owned project')
    if unreal.EditorLevelLibrary.get_pie_worlds(False):raise RuntimeError('Stop PIE before partial finalization')
    original=json.loads(receipt_path.read_text())
    if original.get('success') or original.get('error')!='Reduction lost UVs or an original material section':
        raise ValueError('Only the diagnosed UV-query failure is supported; other failures require separate diagnosis')
    library=unreal.EditorAssetLibrary;subsystem=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    result={'success':False,'validationOnly':True,'parentReceiptSHA256':digest(receipt_path),
            'scriptSHA256':digest(Path(__file__)),'assets':[],'nativeVisualAcceptance':False}
    for record in original['assets']:
        destination=record['destination']
        if not re.fullmatch(r'/Game/ArtPass/Tripo/[A-Za-z][A-Za-z0-9_]{0,39}_v[0-9]{3,4}',destination):
            raise ValueError('Unexpected partial destination')
        source=inspect_source(record['source'])
        objects=[]
        for obj_info in record['objects']:
            path=obj_info['path']
            if not path.startswith(destination+'/'):raise ValueError('Partial object outside version')
            obj=library.load_asset(path)
            if not obj or library.get_metadata_tag(obj,'VeyrSourceSHA256')!=source['sha256']:
                raise RuntimeError('Partial object missing or source provenance differs: '+path)
            objects.append(obj)
        meshes=[obj for obj in objects if isinstance(obj,unreal.StaticMesh)]
        if len(meshes)!=1:raise RuntimeError('Exactly one existing static mesh required')
        mesh=meshes[0]
        if int(subsystem.get_lod_count(mesh))!=3:raise RuntimeError('Existing partial does not contain3 built LODs')
        materials=[s.material_interface.get_path_name() if s.material_interface else None for s in mesh.get_editor_property('static_materials')]
        if materials!=record['materials']:raise RuntimeError('Existing material assignments changed')
        lods=[]
        for lod,target in enumerate(record['lodTargets']):
            count=int(mesh.get_num_triangles(lod));uv=int(mesh.get_num_tex_coords(lod))
            slots=[int(subsystem.get_lod_material_slot(mesh,lod,i)) for i in range(int(mesh.get_num_sections(lod)))]
            lods.append({'lod':lod,'targetTriangles':target,'triangles':count,'vertices':int(mesh.get_num_vertices(lod)),
                         'uvChannels':uv,'uvValidationSource':'StaticMeshVertexBuffer via get_num_tex_coords',
                         'editableMeshDescriptionUVChannels':int(subsystem.get_num_uv_channels(mesh,lod)),
                         'sectionMaterialSlots':slots})
            if count<target*.5 or count>target*1.15+32:raise RuntimeError('Existing built triangle budget failed')
            if uv<1 or set(slots)!=set(record['originalSectionMaterialSlots']):
                raise RuntimeError('Actual render UVs or original material sections missing')
        b=mesh.get_bounds();origin=[getattr(b.origin,a) for a in ('x','y','z')];extent=[getattr(b.box_extent,a) for a in ('x','y','z')]
        measured=[[o-e for o,e in zip(origin,extent)],[o+e for o,e in zip(origin,extent)]]
        result['assets'].append({'name':record['name'],'version':record['version'],'destination':destination,
            'mesh':mesh.get_path_name(),'sourceSHA256':source['sha256'],'boundsCm':measured,
            'materials':materials,'lods':lods,'objects':record['objects']})
    result['success']=True
    return result


def finish_partial(receipt_file):
    """Validate, rename and save exact diagnosed partial; NO import or reduction.

    Root invokes explicitly. Fresh completion receipt preserves the failed one.
    If canonical already exists, stop: never overwrite or infer a safe retry.
    Read-only inspect_partial may be called first to review actual render UVs.
    """
    import unreal
    result=inspect_partial(receipt_file);library=unreal.EditorAssetLibrary
    for record in result['assets']:
        canonical=record['destination']+'/SM_'+record['name']+'_'+record['version']
        if library.does_asset_exist(canonical):raise RuntimeError('Canonical target exists; do not overwrite or retry')
        record['canonicalTarget']=canonical
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    path=SOURCES/'native-imports'/('finalize-'+stamp+'.json')
    result.update(success=False,validationOnly=False,parentReceipt=str(Path(receipt_file).resolve()),
                  operation='VALIDATE_EXISTING_RENAME_SAVE_NO_IMPORT_NO_REDUCTION')
    def save():
        with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600),'w') as stream:
            json.dump(result,stream,indent=2);stream.write('\n')
    save()
    try:
        for record in result['assets']:
            objects=[library.load_asset(obj['path']) for obj in record['objects']]
            mesh=library.load_asset(record['mesh'])
            if not library.rename_asset(record['mesh'],record['canonicalTarget']):raise RuntimeError('Canonical rename failed')
            record['mesh']=mesh.get_path_name();save()
            # Preserve root's private metadata policy: do not mutate read-only
            # Texture2D import-data properties or bypass reflection restrictions.
            for obj in objects:
                if not library.save_loaded_asset(obj,False):raise RuntimeError('Saving existing partial failed')
            record['status']='EXISTING_PARTIAL_VALIDATED_AND_SAVED_NATIVE_VISUAL_REVIEW_PENDING';save()
        result['success']=True
    except Exception as error:
        result['error']=str(error);raise
    finally:
        save();unreal.log('VEYR_TRIPO_FINALIZATION_RECEIPT '+str(path))
    return result


if __name__=='__main__':
    plan=os.environ.get('VEYR_TRIPO_IMPORT_PLAN')
    if not plan:raise RuntimeError('Set VEYR_TRIPO_IMPORT_PLAN; this script never launches an editor')
    run(plan)
