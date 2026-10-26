"""Owned Blender PBR review of existing generated GLBs; source files unchanged."""
import hashlib
import json
import math
from pathlib import Path
import bpy
import bmesh
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'Local/Overhaul20261026/generated-review'
OWNER = 'codex-veyr-flight-join-r2'
ASSETS = ['GeneratedChandelier_Normalized', 'GeneratedVault_Normalized']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_mesh(obj):
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    diag = obj.dimensions.length
    degenerate = sum(f.calc_area() < max(1e-14, diag*diag*1e-12) for f in bm.faces)
    boundary = sum(e.is_boundary for e in bm.edges)
    nonmanifold = sum(not e.is_manifold for e in bm.edges)
    loose = sum(not v.link_edges for v in bm.verts)
    invalid = sum(not all(math.isfinite(c) for c in v.co) for v in bm.verts)
    # Connected components make floating generated pieces visible to the audit.
    components = []
    remaining = set(bm.verts)
    while remaining:
        stack = [remaining.pop()]
        count = 0
        while stack:
            vert = stack.pop()
            count += 1
            for edge in vert.link_edges:
                other = edge.other_vert(vert)
                if other in remaining:
                    remaining.remove(other)
                    stack.append(other)
        components.append(count)
    result = dict(name=obj.name, vertices=len(bm.verts), edges=len(bm.edges),
                  faces=len(bm.faces), triangles=sum(len(p.vertices)-2 for p in mesh.polygons),
                  boundaryEdges=boundary, nonManifoldEdges=nonmanifold,
                  degenerateFaces=degenerate, looseVertices=loose, invalidVertices=invalid,
                  connectedComponents=len(components), largestComponentVertexCounts=sorted(components, reverse=True)[:20],
                  uvLayers=[uv.name for uv in mesh.uv_layers])
    # UV seams split GLB vertices. This welded diagnostic copy is never written
    # into the imported scene or source asset.
    weld_distance = diag*1e-7
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=weld_distance)
    result['weldedDiagnostic'] = {
        'distanceMeters': weld_distance, 'vertices': len(bm.verts),
        'boundaryEdges': sum(e.is_boundary for e in bm.edges),
        'nonManifoldEdges': sum(not e.is_manifold for e in bm.edges),
        'degenerateFaces': sum(f.calc_area() < max(1e-14, diag*diag*1e-12) for f in bm.faces),
        'boundaryEdgeLengthMeters': sum(e.calc_length() for e in bm.edges if e.is_boundary),
    }
    bm.free()
    return result


def area(scene, name, position, target, power, size, color):
    light = bpy.data.lights.new(name, 'AREA')
    light.energy, light.shape, light.size, light.color = power, 'DISK', size, color
    obj = bpy.data.objects.new(name, light)
    scene.collection.objects.link(obj)
    obj.location = position
    obj.rotation_euler = (target-position).to_track_quat('-Z', 'Y').to_euler()


def review(name):
    scene = bpy.context.scene
    assert scene.get('session_owner') == OWNER, 'Foreign Blender'
    for obj in list(scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    source = ROOT / 'Local/Overhaul20261026/architecture' / (name+'.glb')
    source_sha = sha(source)
    bpy.ops.import_scene.gltf(filepath=str(source))
    scene['session_owner'], scene['mcp_port'] = OWNER, 9892
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1
    assets = [o for o in scene.objects if o.type == 'MESH']
    bounds = [o.matrix_world @ Vector(v) for o in assets for v in o.bound_box]
    low = Vector(tuple(min(v[i] for v in bounds) for i in range(3)))
    high = Vector(tuple(max(v[i] for v in bounds) for i in range(3)))
    center, dimensions = (low+high)*.5, high-low
    size = max(dimensions)
    geometry = [audit_mesh(o) for o in assets]
    materials = []
    for material in {m for o in assets for m in o.data.materials if m}:
        images = [{'name': n.image.name, 'size': list(n.image.size),
                   'colorSpace': n.image.colorspace_settings.name,
                   'packed': bool(n.image.packed_file),
                   'linkedOutputs': [(link.from_socket.name, link.to_node.type, link.to_socket.name)
                                     for link in material.node_tree.links if link.from_node == n]}
                  for n in material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image]
        bsdf = next(n for n in material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        materials.append({'name': material.name, 'images': images,
                          'inputs': {n: {'linked': bsdf.inputs[n].is_linked,
                                         'default': list(bsdf.inputs[n].default_value)
                                         if n == 'Base Color' else float(bsdf.inputs[n].default_value)}
                                     for n in ('Base Color', 'Metallic', 'Roughness')}})
    world = bpy.data.worlds.new(name+'_ReviewWorld')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (.32, .35, .4, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = .35
    scene.world = world
    area(scene, 'REVIEW_Key', center+Vector((-1.0,-1.3,1.4))*size, center,
         1500*size*size, size*.9, (1.0,.93,.84))
    area(scene, 'REVIEW_Fill', center+Vector((1.2,-.4,.65))*size, center,
         700*size*size, size*1.2, (.79,.88,1.0))
    area(scene, 'REVIEW_Rim', center+Vector((.3,1.0,1.0))*size, center,
         1800*size*size, size*.7, (1.0,.96,.9))
    bpy.ops.mesh.primitive_plane_add(size=size*200, location=(center.x,center.y,low.z-size*.005))
    ground = bpy.context.object
    ground.name = 'REVIEW_Ground'
    mat = bpy.data.materials.new('REVIEW_MatteGround')
    mat.use_nodes = True
    mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.15,.16,.18,1)
    mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = .8
    ground.data.materials.append(mat)
    camera = bpy.data.objects.new('REVIEW_Camera', bpy.data.cameras.new('REVIEW_Camera'))
    scene.collection.objects.link(camera)
    camera.data.type = 'ORTHO'
    camera.data.clip_start, camera.data.clip_end = .01, size*1000
    scene.camera = camera
    scene.render.engine = 'CYCLES'
    # CPU rendering avoids adding a sustained Eevee shader load to the live editor.
    # The result uses actual imported Principled PBR textures and lighting.
    scene.cycles.device = 'CPU'
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 8
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 768
    scene.render.resolution_y = 768
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.view_settings.exposure = -3
    paths = []
    for view, offset in [('front', (0,-3,.12)), ('side', (3,0,.12)),
                         ('three_quarter', (2.6,-3,1.0))]:
        camera.location = center+Vector(offset)*size
        camera.rotation_euler = (center-camera.location).to_track_quat('-Z','Y').to_euler()
        bpy.context.view_layer.update()
        projected = [camera.matrix_world.inverted() @ v for v in bounds]
        camera.data.ortho_scale = max(max(v.x for v in projected)-min(v.x for v in projected),
                                     max(v.y for v in projected)-min(v.y for v in projected))*1.16
        path = OUT / (name+'-'+view+'.png')
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        paths.append(str(path))
    for obj in scene.objects:
        obj.select_set(obj in assets)
    bpy.context.view_layer.objects.active = assets[0]
    bpy.ops.file.pack_all()
    script = bpy.data.texts.get('review_generated_assets.py') or bpy.data.texts.new('review_generated_assets.py')
    script.clear()
    script.write(Path(__file__).read_text())
    blend = OUT / (name+'.blend')
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True)
    assert sha(source) == source_sha, 'Input GLB changed'
    report = {'name': name, 'source': str(source), 'sourceSHA256': source_sha,
              'sourceUnchanged': True, 'dimensionsMetersXYZ': list(dimensions),
              'boundsMeters': [list(low),list(high)], 'geometry': geometry,
              'materials': materials, 'renderer': 'Cycles CPU 32spp, actual PBR, three area lights',
              'renders': paths, 'blend': str(blend), 'blendSHA256': sha(blend),
              'nativeImportVerified': False}
    (OUT/(name+'.json')).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


OUT.mkdir(parents=True, exist_ok=True)
for asset in globals().get('REVIEW_ASSETS', ASSETS):
    review(asset)
