#!/usr/bin/env python3
"""Original deterministic fractured-basalt backdrop mesh; no generator or DCC.

Uses only Python's standard library. Each angular column is a closed manifold;
columns overlap into one decorative mesh (not a collision boolean union).
Export is glTF Y-up metres, centered 1m bounds on every axis, flat face normals,
a neutral rough PBR material, no external images, and no copied source assets.
UE imports at 100cm bounds, matching VeyrArena's existing Size/100 instances.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import random
import struct

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT/'Local/EnvironmentAssets'
SEED = 6194381


def sub(a, b): return tuple(x-y for x, y in zip(a, b))
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def length(v): return math.sqrt(sum(x*x for x in v))


def geometry(seed=SEED):
    rng = random.Random(seed);vertices = [];faces = [];components = []
    # Unequal overlapping hexagonal masses, with taller inner columns and
    # broken lower buttresses. No four-sided planar box participates.
    locations = [(0., 0., 1.35, .30)]
    for count, radius, phase, height in [(5, .26, .23, 1.1), (9, .49, .61, .70)]:
        for i in range(count):
            angle = 2*math.pi*i/count+phase+rng.uniform(-.10, .10)
            locations.append((radius*math.cos(angle), radius*math.sin(angle),
                              height*rng.uniform(.65, 1.38), rng.uniform(.21, .30)))
    for column, (cx, cy, height, radius) in enumerate(locations):
        start = len(vertices);sides = rng.choice((5, 6, 7));phase = rng.uniform(0, math.pi)
        angles = [phase+2*math.pi*i/sides+rng.uniform(-.07, .07) for i in range(sides)]
        facets = [rng.uniform(.85, 1.13) for _ in range(sides)]
        lean = (rng.uniform(-.13, .13), rng.uniform(-.13, .13))
        levels = (0., rng.uniform(.22, .32), rng.uniform(.56, .70), 1.)
        top_heights = [height*rng.uniform(.80, 1.13) for _ in range(sides)]
        for ring, level in enumerate(levels):
            taper = (1.15, 1.02, .87, .64)[ring]
            # Fracture ledges alter facet widths while preserving angular order.
            for i, angle in enumerate(angles):
                r = radius*facets[i]*taper*rng.uniform(.92, 1.08)
                z = top_heights[i] if ring == 3 else height*level
                vertices.append((cx+math.cos(angle)*r+lean[0]*level,
                                 cy+math.sin(angle)*r+lean[1]*level, z))
        for ring in range(3):
            for i in range(sides):
                j = (i+1)%sides;a = start+ring*sides+i;b = start+ring*sides+j
                c = b+sides;d = a+sides
                faces.extend(((a,b,c),(a,c,d)) if (ring+i)%2 else ((a,b,d),(b,c,d)))
        bottom = len(vertices);vertices.append((cx,cy,0.))
        # A chipped asymmetric cap gives multiple inclined planes at the crest.
        top = len(vertices);vertices.append((cx+lean[0]+radius*.12,cy+lean[1]-radius*.08,height*rng.uniform(.96,1.12)))
        for i in range(sides):
            j = (i+1)%sides;faces.append((bottom,start+j,start+i));faces.append((start+3*sides+i,start+3*sides+j,top))
        components.append({'column': column, 'sides': sides, 'vertices': len(vertices)-start})
    bounds = [(min(v[a] for v in vertices), max(v[a] for v in vertices)) for a in range(3)]
    normalized = [tuple((v[a]-(bounds[a][0]+bounds[a][1])*.5)/(bounds[a][1]-bounds[a][0]) for a in range(3)) for v in vertices]
    # X,Z,Y is a handedness flip. Reverse triangle winding while converting.
    positions = [(v[0],v[2],v[1]) for v in normalized]
    faces = [(a,c,b) for a,b,c in faces]
    edges = Counter(tuple(sorted((a,b))) for f in faces for a,b in zip(f,(f[1],f[2],f[0])))
    if any(count != 2 for count in edges.values()): raise ValueError('An individual basalt column is not closed')
    volume = sum(sum(positions[a][k]*cross(positions[b],positions[c])[k] for k in range(3))/6 for a,b,c in faces)
    if volume <= 0: raise ValueError('Mesh winding is not outward')
    flat = [];normals = []
    for face in faces:
        a,b,c = [positions[i] for i in face];n = cross(sub(b,a),sub(c,a));m = length(n)
        if m < 1e-8: raise ValueError('Degenerate rock face')
        flat.extend((a,b,c));normals.extend([tuple(x/m for x in n)]*3)
    return flat,normals,{'seed': seed, 'columns': len(components), 'triangles': len(faces),
                        'renderVertices': len(flat), 'closedColumnTopology': True,
                        'aggregateBooleanUnion': False, 'signedAggregateVolumeM3': volume,
                        'boundsMeters': [[-.5,-.5,-.5],[.5,.5,.5]], 'faceNormals': 'flat/outward/unit',
                        'source': 'Original deterministic radial basalt-column construction; no external art',
                        'expectedUEBoundsCm': [100,100,100], 'expectedUEPivotCm': [0,0,0]}


def glb(seed=SEED):
    positions,normals,report = geometry(seed)
    packed_positions = struct.pack('<'+'f'*len(positions)*3,*(x for v in positions for x in v))
    packed_normals = struct.pack('<'+'f'*len(normals)*3,*(x for v in normals for x in v))
    indices = struct.pack('<'+'H'*len(positions),*range(len(positions)))
    binary = packed_positions+packed_normals+indices;binary += b'\0'*((-len(binary))%4)
    views = [];offset = 0
    for chunk,target in [(packed_positions,34962),(packed_normals,34962),(indices,34963)]:
        views.append({'buffer':0,'byteOffset':offset,'byteLength':len(chunk),'target':target});offset += len(chunk)
    data = {'asset':{'version':'2.0','generator':'Veyr original basalt geometry v1'},
            'scene':0,'scenes':[{'nodes':[0]}],'nodes':[{'name':'SM_BasaltCliff','mesh':0}],
            'meshes':[{'name':'SM_BasaltCliff','primitives':[{'attributes':{'POSITION':0,'NORMAL':1},'indices':2,'material':0}]}],
            'materials':[{'name':'M_BasaltNeutralSource','pbrMetallicRoughness':{'baseColorFactor':[.16,.18,.20,1.],
                          'metallicFactor':0.,'roughnessFactor':.94},'doubleSided':False}],
            'buffers':[{'byteLength':len(binary)}],'bufferViews':views,
            'accessors':[{'bufferView':0,'componentType':5126,'count':len(positions),'type':'VEC3','min':[-.5,-.5,-.5],'max':[.5,.5,.5]},
                         {'bufferView':1,'componentType':5126,'count':len(normals),'type':'VEC3'},
                         {'bufferView':2,'componentType':5123,'count':len(positions),'type':'SCALAR'}]}
    text = json.dumps(data,separators=(',',':')).encode();text += b' '*((-len(text))%4)
    payload = struct.pack('<III',0x46546C67,2,12+8+len(text)+8+len(binary))+struct.pack('<II',len(text),0x4E4F534A)+text+struct.pack('<II',len(binary),0x004E4942)+binary
    report['sha256'] = hashlib.sha256(payload).hexdigest();report['bytes'] = len(payload)
    return payload,report


def main():
    parser = argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=PRIVATE/'basalt-cliff-v1.glb');parser.add_argument('--seed',type=int,default=SEED)
    args = parser.parse_args();output = args.output.resolve()
    if not output.is_relative_to(PRIVATE.resolve()) or output.suffix != '.glb': parser.error('Use a private Local/EnvironmentAssets GLB output')
    receipt = output.with_suffix('.json')
    if output.exists() or receipt.exists(): parser.error('Preserve existing artifacts; choose a fresh filename')
    payload,report = glb(args.seed)
    if payload != glb(args.seed)[0]: raise RuntimeError('Generator is not deterministic')
    output.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    for path,content in [(output,payload),(receipt,(json.dumps(report,indent=2)+'\n').encode())]:
        with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as stream:stream.write(content)
    print(json.dumps({'file':str(output),**report},indent=2))


if __name__ == '__main__':main()
