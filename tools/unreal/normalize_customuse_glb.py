#!/usr/bin/env python3
"""Exact skin-preserving GLB mesh-space normalization; no geometry/weight editing.

For one static, rigid skinned mesh instance with world matrix M, first inspect
the common bind-shape matrix C = J_rest IBM. Supported conventions are C=M
(Cartwheel knight) and C=identity (the quadruped export's redundant mesh offset).
  p' = C p; n' = inverse(C.linear).transpose() n;
  IBM' = IBM inverse(C); mesh world transform becomes identity.
Joint hierarchy and animation remain byte-for-byte unchanged. Consequently
sum(w J IBM' p') == sum(w J IBM p) at every animation time. For C=identity only
the redundant mesh-node transform changes; vertex/accessor data is untouched.

Requires installed numpy. Refuses unsupported cases and existing output files.
Only writes a derivative and CPU equivalence receipt in Local/CustomuseAssets.
This proves representation equivalence, not Unreal import or artistic acceptance.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import struct

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "Local/CustomuseAssets"
DTYPES = {5121: "u1", 5123: "<u2", 5125: "<u4", 5126: "<f4"}
WIDTHS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def trs(node):
    if "matrix" in node:
        return np.asarray(node["matrix"], dtype=np.float64).reshape(4, 4).T
    x, y, z, w = node.get("rotation", [0, 0, 0, 1])
    length = np.linalg.norm([x, y, z, w])
    if not np.isfinite(length) or length < 1.e-12:
        raise ValueError("Invalid quaternion")
    x, y, z, w = np.array([x, y, z, w]) / length
    rotation = np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                         [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                         [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
    matrix = np.eye(4)
    matrix[:3, :3] = rotation @ np.diag(node.get("scale", [1, 1, 1]))
    matrix[:3, 3] = node.get("translation", [0, 0, 0])
    return matrix


def slerp(left, right, alpha):
    left = left / np.linalg.norm(left)
    right = right / np.linalg.norm(right)
    dot = float(np.dot(left, right))
    if dot < 0:
        right = -right
        dot = -dot
    dot = min(1., max(-1., dot))
    if dot > .9995:
        result = left + alpha * (right - left)
        return result / np.linalg.norm(result)
    angle = np.arccos(dot)
    return (np.sin((1-alpha)*angle)*left + np.sin(alpha*angle)*right) / np.sin(angle)


class GLB:
    def __init__(self, path_or_bytes):
        data = path_or_bytes if isinstance(path_or_bytes, bytes) else Path(path_or_bytes).read_bytes()
        if len(data) < 28 or struct.unpack_from("<III", data) != (0x46546C67, 2, len(data)):
            raise ValueError("Invalid GLB 2 header")
        size, kind = struct.unpack_from("<II", data, 12)
        if kind != 0x4E4F534A:
            raise ValueError("Missing JSON chunk")
        self.json = json.loads(data[20:20+size])
        start = 20 + size
        size, kind = struct.unpack_from("<II", data, start)
        if kind != 0x004E4942 or start + 8 + size != len(data):
            raise ValueError("Exactly one JSON and one BIN chunk are supported")
        if len(self.json.get("buffers", [])) != 1 or "uri" in self.json["buffers"][0]:
            raise ValueError("Only one embedded buffer is supported")
        self.binary = bytearray(data[start+8:start+8+size])
        self.parents = {}
        for parent, node in enumerate(self.json["nodes"]):
            for child in node.get("children", []):
                if child in self.parents:
                    raise ValueError("Multiple node parents are unsupported")
                self.parents[child] = parent

    def accessor(self, index):
        item = self.json["accessors"][index]
        if "sparse" in item or item.get("normalized", False) or "bufferView" not in item:
            raise ValueError("Sparse/normalized/implicit accessors are unsupported")
        view = self.json["bufferViews"][item["bufferView"]]
        dtype = np.dtype(DTYPES[item["componentType"]])
        width = WIDTHS[item["type"]]
        result = np.ndarray((item["count"], width), dtype=dtype, buffer=self.binary,
                            offset=view.get("byteOffset", 0)+item.get("byteOffset", 0),
                            strides=(view.get("byteStride", dtype.itemsize*width), dtype.itemsize))
        if not np.all(np.isfinite(result)):
            raise ValueError("Non-finite accessor data")
        return result

    def world_matrices(self, animation=None, time=0.):
        nodes = copy.deepcopy(self.json["nodes"])
        if animation is not None:
            clip = self.json["animations"][animation]
            for channel in clip["channels"]:
                node = nodes[channel["target"]["node"]]
                if "matrix" in node:
                    raise ValueError("Animation on matrix nodes is unsupported")
                key = channel["target"]["path"]
                if key not in ("translation", "rotation", "scale"):
                    raise ValueError("Only skeletal TRS animation is supported")
                sampler = clip["samplers"][channel["sampler"]]
                interpolation = sampler.get("interpolation", "LINEAR")
                if interpolation not in ("LINEAR", "STEP"):
                    raise ValueError("Only LINEAR and STEP animation are supported")
                times = self.accessor(sampler["input"]).reshape(-1).astype(float)
                values = self.accessor(sampler["output"]).astype(float)
                if len(times) != len(values) or len(times) == 0 or np.any(np.diff(times) <= 0):
                    raise ValueError("Invalid animation sample timeline")
                index = max(0, min(len(times)-1, int(np.searchsorted(times, time, side="right"))-1))
                value = values[index]
                if interpolation == "LINEAR" and index + 1 < len(times) and time > times[index]:
                    alpha = min(1., (time-times[index])/(times[index+1]-times[index]))
                    value = slerp(value, values[index+1], alpha) if key == "rotation" else value*(1-alpha)+values[index+1]*alpha
                node[key] = value.tolist()
        result = [None] * len(nodes)
        visiting = set()
        def world(index):
            if result[index] is not None:
                return result[index]
            if index in visiting:
                raise ValueError("Node hierarchy contains a cycle")
            visiting.add(index)
            local = trs(nodes[index])
            result[index] = world(self.parents[index]) @ local if index in self.parents else local
            visiting.remove(index)
            return result[index]
        return np.asarray([world(i) for i in range(len(nodes))])

    def mesh_node(self):
        candidates = [i for i, node in enumerate(self.json["nodes"]) if "mesh" in node]
        if len(candidates) != 1 or "skin" not in self.json["nodes"][candidates[0]]:
            raise ValueError("Exactly one skinned mesh instance is supported")
        return candidates[0]

    def skinned_positions(self, animation=None, time=0.):
        node = self.json["nodes"][self.mesh_node()]
        skin = self.json["skins"][node["skin"]]
        worlds = self.world_matrices(animation, time)
        inverse = self.accessor(skin["inverseBindMatrices"]).reshape(-1, 4, 4).transpose(0, 2, 1)
        transforms = worlds[skin["joints"]] @ inverse
        output = []
        for primitive in self.json["meshes"][node["mesh"]]["primitives"]:
            attributes = primitive["attributes"]
            positions = self.accessor(attributes["POSITION"]).astype(float)
            joints = self.accessor(attributes["JOINTS_0"])
            weights = self.accessor(attributes["WEIGHTS_0"]).astype(float)
            if joints.shape != weights.shape or weights.shape[1] != 4 or not np.allclose(weights.sum(1), 1, atol=1.e-5):
                raise ValueError("Expected four normalized skin influences per vertex")
            if np.any(weights < 0) or np.any(weights > 1.00001):
                raise ValueError("Skin weights must be nonnegative and at most one")
            if joints.max() >= len(skin["joints"]):
                raise ValueError("Joint index outside skin")
            homogeneous = np.column_stack((positions, np.ones(len(positions))))
            result = sum(np.einsum("nij,nj->ni", transforms[joints[:, slot]], homogeneous)*weights[:, slot, None] for slot in range(4))
            output.append(result[:, :3])
        return np.concatenate(output)

    def bytes(self):
        content = json.dumps(self.json, separators=(",", ":"), ensure_ascii=False).encode()
        content += b" " * (-len(content) % 4)
        binary = bytes(self.binary)
        binary += b"\0" * (-len(binary) % 4)
        return (struct.pack("<III", 0x46546C67, 2, 28+len(content)+len(binary)) +
                struct.pack("<II", len(content), 0x4E4F534A) + content +
                struct.pack("<II", len(binary), 0x004E4942) + binary)


def normalize(original):
    derived = GLB(original.bytes())
    index = derived.mesh_node()
    node = derived.json["nodes"][index]
    if node.get("children") or len(derived.json.get("skins", [])) != 1:
        raise ValueError("Mesh children or multiple skins are unsupported")
    ancestors = {index}
    while index in derived.parents:
        index = derived.parents[index]
        ancestors.add(index)
    animated = {channel["target"]["node"] for clip in derived.json.get("animations", []) for channel in clip["channels"]}
    if ancestors & animated:
        raise ValueError("Animated mesh node/ancestor transforms cannot be normalized by a static bake")
    worlds = derived.world_matrices()
    mesh_index = derived.mesh_node()
    mesh_world = worlds[mesh_index]
    for index in ancestors:
        rotation = worlds[index][:3, :3]
        if (not np.allclose(worlds[index][3], [0, 0, 0, 1], atol=1.e-8) or
                not np.allclose(rotation.T @ rotation, np.eye(3), atol=1.e-6) or not np.isclose(np.linalg.det(rotation), 1., atol=1.e-6)):
            raise ValueError("Only rigid, orientation-preserving mesh/ancestor transforms are supported")
    skin = derived.json["skins"][node["skin"]]
    if ancestors & set(skin["joints"]):
        raise ValueError("Mesh ancestors also serving as skin joints are unsupported")
    original_inverse = derived.accessor(skin["inverseBindMatrices"]).reshape(-1, 4, 4).transpose(0, 2, 1)
    bind_products = worlds[skin["joints"]] @ original_inverse
    if np.allclose(bind_products, mesh_world, atol=2.e-6, rtol=0):
        matrix = mesh_world
    elif np.allclose(bind_products, np.eye(4), atol=2.e-6, rtol=0):
        matrix = np.eye(4)
    else:
        raise ValueError("Bind-shape products are neither mesh-world nor identity; explicit analysis required")
    identity_bake = np.array_equal(matrix, np.eye(4))
    changed = set()
    inverse_matrix = np.linalg.inv(matrix)
    for primitive in derived.json["meshes"][node["mesh"]]["primitives"]:
        if primitive.get("targets") or primitive.get("extensions") or primitive.get("mode", 4) != 4:
            raise ValueError("Morphs, compressed primitives and non-triangle topology are unsupported")
        attributes = primitive["attributes"]
        if "JOINTS_1" in attributes or "WEIGHTS_1" in attributes:
            raise ValueError("More than four skin influences are unsupported")
        if identity_bake:
            continue
        for semantic in ("POSITION", "NORMAL", "TANGENT"):
            accessor_index = attributes.get(semantic)
            if accessor_index is None or accessor_index in changed:
                continue
            item = derived.json["accessors"][accessor_index]
            if item["componentType"] != 5126:
                raise ValueError("Position, normal and tangent data must be float32")
            values = derived.accessor(accessor_index)
            if semantic == "POSITION":
                values[:, :3] = (matrix @ np.column_stack((values[:, :3], np.ones(len(values)))).T).T[:, :3]
            else:
                values[:, :3] = values[:, :3].astype(float) @ inverse_matrix[:3, :3]
                lengths = np.linalg.norm(values[:, :3], axis=1)
                if np.any(lengths < 1.e-8):
                    raise ValueError("Degenerate normal/tangent")
                values[:, :3] /= lengths[:, None]
            if semantic == "POSITION" or "min" in item:
                item["min"] = values.min(0).tolist()
                item["max"] = values.max(0).tolist()
            changed.add(accessor_index)
    if not identity_bake:
        inverse_values = derived.accessor(skin["inverseBindMatrices"])
        matrices = inverse_values.reshape(-1, 4, 4).transpose(0, 2, 1).astype(float)
        inverse_values[:] = (matrices @ inverse_matrix).transpose(0, 2, 1).reshape(-1, 16)
        changed.add(skin["inverseBindMatrices"])
    for key in ("translation", "rotation", "scale", "matrix"):
        node.pop(key, None)
    parent_inverse = np.linalg.inv(worlds[derived.parents[mesh_index]]) if mesh_index in derived.parents else np.eye(4)
    node["matrix"] = parent_inverse.T.reshape(-1).tolist()
    return derived, matrix, changed


def validate(original, derived, changed, tolerance):
    if original.json.get("animations") != derived.json.get("animations"):
        raise ValueError("Animation declarations changed")
    for field in ("meshes", "skins", "materials", "textures", "images", "samplers", "scenes"):
        if original.json.get(field) != derived.json.get(field):
            raise ValueError("Unexpected structural/material change: " + field)
    for image in original.json.get("images", []):
        if "bufferView" in image:
            view = original.json["bufferViews"][image["bufferView"]]
            start = view.get("byteOffset", 0)
            end = start + view["byteLength"]
            if original.binary[start:end] != derived.binary[start:end]:
                raise ValueError("Embedded texture pixels changed")
    mesh_index = original.mesh_node()
    for index, node in enumerate(original.json["nodes"]):
        if index != mesh_index and node != derived.json["nodes"][index]:
            raise ValueError("Joint/ancestor node changed")
    for i, _ in enumerate(original.json["accessors"]):
        if i not in changed and not np.array_equal(original.accessor(i), derived.accessor(i)):
            raise ValueError("Unexpected change to animation/skin/topology/UV accessor: " + str(i))
    cases = [(None, 0.)]
    for animation, clip in enumerate(original.json.get("animations", [])):
        time_values = np.concatenate([original.accessor(sampler["input"]).reshape(-1) for sampler in clip["samplers"]])
        lo, hi = float(time_values.min()), float(time_values.max())
        times = set(np.linspace(lo, hi, 17).tolist())
        times.update(float(t) for t in sorted(set(time_values.tolist()))[:3])
        cases.extend((animation, t) for t in sorted(times))
    checks = []
    for animation, time in cases:
        left = original.skinned_positions(animation, time)
        right = derived.skinned_positions(animation, time)
        distances = np.linalg.norm(left-right, axis=1)
        maximum = float(distances.max())
        checks.append({"animation": animation, "seconds": time, "vertices": len(left),
                       "maxWorldPositionError": maximum, "rmsWorldPositionError": float(np.sqrt(np.mean(distances**2)))})
        if maximum > tolerance:
            raise ValueError(f"Skin equivalence failed at animation {animation}, time {time}: {maximum}")
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    receipt = output.with_suffix(".normalization.json")
    if source.suffix.lower() != ".glb" or output.suffix.lower() != ".glb":
        parser.error("Source and derivative must use .glb filenames")
    if source == output or not source.is_relative_to(ASSETS.resolve()) or output.parent != ASSETS.resolve():
        parser.error("Use an existing private source and a distinct derivative in Local/CustomuseAssets")
    if output.exists() or receipt.exists():
        parser.error("Derivative or receipt exists; choose a fresh version")
    source_bytes = source.read_bytes()
    original = GLB(source_bytes)
    derived, matrix, changed = normalize(original)
    serialized = derived.bytes()
    reopened = GLB(serialized)
    checks = validate(original, reopened, changed, 2.e-6)
    # Source must remain unchanged throughout this operation.
    if source.read_bytes() != source_bytes:
        raise ValueError("Source changed during normalization")
    report = {"source": source.name, "sourceSHA256": hashlib.sha256(source_bytes).hexdigest(),
              "derivative": output.name, "derivativeSHA256": hashlib.sha256(serialized).hexdigest(),
              "operation": "rigid common bind-shape bake, inverse-bind compensation, mesh world identity",
              "equation": "C=Jrest IBM (verified common); p'=C p; IBM'=IBM C^-1; sum(w J IBM' p')=sum(w J IBM p)",
              "meshWorldBefore": original.world_matrices()[original.mesh_node()].tolist(),
              "bindShapeBake": matrix.tolist(), "changedAccessorIndices": sorted(changed),
              "absoluteWorldTolerance": 2.e-6, "coordinateSpace": "glTF world; Y up; source units preserved",
              "checks": checks, "cpuEquivalencePassed": True, "originalPreserved": True,
              "topologyWeightsUVAnimationUnchanged": True,
              "nativeImportVerified": False, "rigOrWeaponQualityAccepted": False}
    with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as stream:
        stream.write(serialized)
    with os.fdopen(os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"derivative": str(output), "receipt": str(receipt), "samples": len(checks),
                      "maxWorldError": max(c["maxWorldPositionError"] for c in checks), "nativeVerified": False}, indent=2))


if __name__ == "__main__":
    main()
