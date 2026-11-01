#!/usr/bin/env python3
"""Transfer a Blender-exported action onto unchanged canonical GLB geometry.

Copies skeletal TRS animation only. Checks every joint at all keys and interval
midpoints against the Blender export. This is representation validation, not QA.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

import numpy as np
from normalize_customuse_glb import GLB


def graft(canonical_path, exported_path, output):
    if output.exists() or output.with_suffix('.graft.json').exists():
        raise ValueError('Refusing overwrite')
    canonical, exported = GLB(canonical_path), GLB(exported_path)
    if len(exported.json.get('animations', [])) != 1:
        raise ValueError('Expected one exported action')
    result = GLB(canonical.bytes())
    def names(glb):
        found = {}
        for index, node in enumerate(glb.json['nodes']):
            name = node.get('name')
            if name:
                if name in found: raise ValueError('Duplicate node name')
                found[name] = index
        return found
    dst, src = names(result), names(exported)
    joints = [canonical.json['nodes'][i]['name'] for i in canonical.json['skins'][0]['joints']]
    if set(joints) - src.keys(): raise ValueError('Export lacks canonical joints')
    animation = copy.deepcopy(exported.json['animations'][0])
    copied = {}
    def accessor(index):
        if index in copied:return copied[index]
        item = copy.deepcopy(exported.json['accessors'][index])
        values = exported.accessor(index).copy()
        while len(result.binary) % 4:result.binary.append(0)
        view = {'buffer': 0, 'byteOffset': len(result.binary), 'byteLength': values.nbytes}
        item['bufferView'] = len(result.json['bufferViews'])
        item.pop('byteOffset', None)
        result.json['bufferViews'].append(view)
        result.binary.extend(values.tobytes())
        copied[index] = len(result.json['accessors'])
        result.json['accessors'].append(item)
        return copied[index]
    times = set()
    for sampler in animation['samplers']:
        times.update(float(t) for t in exported.accessor(sampler['input']).flat)
        sampler['input'], sampler['output'] = accessor(sampler['input']), accessor(sampler['output'])
    for channel in animation['channels']:
        target = channel['target']
        name = exported.json['nodes'][target['node']].get('name')
        if name not in joints or target['path'] not in ('translation','rotation','scale'):
            raise ValueError('Only canonical joint TRS channels may be transferred')
        target['node'] = dst[name]
    result.json['animations'] = [animation]
    result.json['buffers'][0]['byteLength'] = len(result.binary)
    ordered = sorted(times)
    samples = sorted(times | {(a+b)/2 for a,b in zip(ordered,ordered[1:])})
    error = 0.0
    for time in samples:
        a, b = exported.world_matrices(0,time), result.world_matrices(0,time)
        error = max(error,max(float(np.max(np.abs(a[src[name]]-b[dst[name]]))) for name in joints))
    if error > 1e-4:raise ValueError(f'Export/canonical evaluated poses differ: {error}')
    for key in ('nodes','skins','meshes','materials','textures','images'):
        if result.json.get(key) != canonical.json.get(key):raise ValueError('Canonical changed: '+key)
    if result.binary[:len(canonical.binary)] != canonical.binary:raise ValueError('Canonical binary changed')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(result.bytes())
    receipt = {'canonicalSHA256': hashlib.sha256(canonical.bytes()).hexdigest(),
               'blenderExportSHA256': hashlib.sha256(exported_path.read_bytes()).hexdigest(),
               'outputSHA256': hashlib.sha256(output.read_bytes()).hexdigest(),
               'sampleCount': len(samples), 'maximumJointMatrixError': error,
               'canonicalGeometrySkinMaterialsPreserved': True,
               'durationSeconds': ordered[-1]-ordered[0],
               'scope': 'Representation equivalence, not native import or visual quality'}
    output.with_suffix('.graft.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('canonical',type=Path);p.add_argument('exported',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();print(json.dumps(graft(a.canonical,a.exported,a.output),indent=2))
