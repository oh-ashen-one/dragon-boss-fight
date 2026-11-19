#!/usr/bin/env python3
"""Write a copy of a dragon GLB whose JOINTS_0 / WEIGHTS_0 come from an NPZ; every other byte is kept (2026-11-18).

The skeleton, inverse binds, geometry, UVs, normals, morph targets, materials and animation stay
byte-identical, so the copy is a drop-in re-import source for the same Unreal skeleton. Refuses to
overwrite, checks the vertex count and joint names, and reports the changed byte ranges.

python3 tools/dragon_refine/patch_glb_weights.py --glb SRC.glb --weights fixed.npz --output OUT.glb
"""
import argparse, hashlib, json, struct, sys
from pathlib import Path
import numpy as np


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--glb', type=Path, required=True)
    ap.add_argument('--weights', type=Path, required=True); ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    if a.output.exists(): sys.exit('Refusing to overwrite ' + str(a.output))
    raw = bytearray(a.glb.read_bytes())
    jlen = struct.unpack_from('<I', raw, 12)[0]; js = json.loads(raw[20:20 + jlen]); bin0 = 20 + jlen + 8
    assert struct.unpack_from('<I', raw, 20 + jlen + 4)[0] == 0x004E4942
    prim = js['meshes'][0]['primitives'][0]
    names = [js['nodes'][j]['name'] for j in js['skins'][0]['joints']]
    d = np.load(a.weights); assert [str(x) for x in d['names']] == names, 'joint names differ'
    J = d['joints'].astype(np.uint16); W = d['weights'].astype(np.float32)
    ranges = []
    for key, arr, ctype in (('JOINTS_0', J, 5123), ('WEIGHTS_0', W, 5126)):
        acc = js['accessors'][prim['attributes'][key]]; view = js['bufferViews'][acc['bufferView']]
        assert acc['componentType'] == ctype and acc['type'] == 'VEC4' and acc['count'] == len(arr), (key, acc)
        assert view.get('byteStride', arr.itemsize * 4) == arr.itemsize * 4 and 'sparse' not in acc
        start = bin0 + view.get('byteOffset', 0) + acc.get('byteOffset', 0)
        payload = np.ascontiguousarray(arr).tobytes(); raw[start:start + len(payload)] = payload
        ranges.append([key, start, len(payload)])
        if key == 'WEIGHTS_0':
            assert np.allclose(arr.sum(1), 1, atol=1e-5)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_bytes(bytes(raw))
    src = a.glb.read_bytes(); diff = np.flatnonzero(np.frombuffer(src, np.uint8) != np.frombuffer(bytes(raw), np.uint8))
    inside = all(any(s <= i < s + n for _, s, n in ranges) for i in (diff[0], diff[-1])) if len(diff) else True
    print(json.dumps(dict(source=str(a.glb), sourceSHA256=hashlib.sha256(src).hexdigest(), output=str(a.output),
                          outputSHA256=hashlib.sha256(bytes(raw)).hexdigest(), changedBytes=int(len(diff)),
                          changedOnlyInWeightRanges=bool(inside), ranges=ranges)))


if __name__ == '__main__':
    main()
