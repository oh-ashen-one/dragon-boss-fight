#!/usr/bin/env python3
"""Remove only world-horizontal Hips travel from a private Customuse GLB.

The translation correction is converted through the actual static parent
transform. World Y (glTF up), rotations, other joints, skin, geometry and timing
are preserved. No animation frames are deleted. The first positive translation
sample is the default horizontal anchor; it is not a claim of visual acceptance.

The source is never overwritten. CPU validation requires every skinned vertex
to differ solely by the intended world-horizontal displacement at sampled times.
Use these derivatives with Unreal force_root_lock disabled; forcing the whole
root to its first transform would remove the vertical bob/rotation preserved here.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "Local/CustomuseAssets"
SPEC = importlib.util.spec_from_file_location("veyr_glb_cpu", ROOT / "tools/unreal/normalize_customuse_glb.py")
CPU = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CPU)


def prepare(source, anchor_time=None, root_name="Hips"):
    derived = CPU.GLB(source.bytes())
    if len(source.json.get("animations", [])) != 1 or len(source.json.get("skins", [])) != 1:
        raise ValueError("Exactly one animation and skin are supported")
    candidates = [i for i, n in enumerate(source.json["nodes"]) if n.get("name") == root_name]
    if len(candidates) != 1:
        raise ValueError("Expected exactly one named motion root")
    root = candidates[0]
    for joint in source.json["skins"][0]["joints"]:
        ancestor = joint
        visited = set()
        while ancestor != root and ancestor in source.parents:
            if ancestor in visited:
                raise ValueError("Cyclic joint ancestry")
            visited.add(ancestor)
            ancestor = source.parents[ancestor]
        if ancestor != root:
            raise ValueError("All skin joints must descend from the motion root")
    clip = source.json["animations"][0]
    channels = [c for c in clip["channels"] if c["target"].get("node") == root and c["target"].get("path") == "translation"]
    if len(channels) != 1:
        raise ValueError("Expected one motion-root translation channel")
    channel = channels[0]
    sampler = clip["samplers"][channel["sampler"]]
    if sampler.get("interpolation", "LINEAR") != "LINEAR":
        raise ValueError("Only LINEAR root translation is supported")
    output = sampler["output"]
    if sum(s["output"] == output for s in clip["samplers"]) != 1:
        raise ValueError("Root translation accessor is shared with another animation sampler")
    parents = []
    parent = source.parents.get(root)
    while parent is not None:
        if parent in parents:
            raise ValueError("Cyclic root ancestry")
        parents.append(parent)
        parent = source.parents.get(parent)
    if any(c["target"].get("node") in parents for c in clip["channels"]):
        raise ValueError("Animated root ancestors require a separate exact resampling design")
    parent_world = source.world_matrices()[source.parents[root]] if root in source.parents else np.eye(4)
    if not np.allclose(parent_world[3], [0, 0, 0, 1]) or abs(np.linalg.det(parent_world[:3, :3])) < 1.e-8:
        raise ValueError("Root parent transform must be static, affine and invertible")
    times = source.accessor(sampler["input"]).reshape(-1).astype(float)
    if len(times) < 2 or np.any(np.diff(times) <= 0):
        raise ValueError("Invalid translation sample times")
    positive = times[times > times[0]]
    anchor_time = float(positive[0]) if anchor_time is None else float(anchor_time)
    if not np.isfinite(anchor_time) or anchor_time < times[0] or anchor_time > times[-1]:
        raise ValueError("Anchor time is outside the source animation")
    anchor_world = source.world_matrices(0, anchor_time)[root, :3, 3]
    values = source.accessor(output).astype(float)
    if values.shape != (len(times), 3) or derived.json["accessors"][output]["componentType"] != 5126:
        raise ValueError("Expected float32 VEC3 root translations")
    world_positions = values @ parent_world[:3, :3].T + parent_world[:3, 3]
    displacement = world_positions - anchor_world
    displacement[:, 1] = 0.  # Global glTF up, not an assumption about root-local axes.
    correction_local = displacement @ np.linalg.inv(parent_world[:3, :3]).T
    corrected = derived.accessor(output)
    corrected[:] = values - correction_local
    accessor_json = derived.json["accessors"][output]
    if "min" in accessor_json:
        accessor_json["min"] = corrected.min(0).tolist()
    if "max" in accessor_json:
        accessor_json["max"] = corrected.max(0).tolist()
    metadata = {"rootName": root_name, "rootNodeIndex": root, "changedAccessorIndex": output,
                "anchorSeconds": anchor_time, "anchorWorldGLTF": anchor_world.tolist(),
                "rootParentNodeIndices": parents, "parentWorldMatrix": parent_world.tolist(),
                "originalRootWorldRange": np.ptp(world_positions, axis=0).tolist(),
                "frameZeroPreserved": True, "upAxis": "glTF world +Y",
                "equation": "t_local_new=t_local-P_linear^-1*project_horizontal(P*t_local-anchor_world)"}
    return derived, metadata


def validate(source, derived, metadata, tolerance=2.e-6):
    index = metadata["changedAccessorIndex"]
    # No node, rotation, animation, geometry, material or skin declarations may change.
    left, right = json.loads(json.dumps(source.json)), json.loads(json.dumps(derived.json))
    left["accessors"][index].pop("min", None);left["accessors"][index].pop("max", None)
    right["accessors"][index].pop("min", None);right["accessors"][index].pop("max", None)
    if left != right:
        raise ValueError("Unexpected JSON change outside root translation accessor bounds")
    for i in range(len(source.json["accessors"])):
        if i != index and not np.array_equal(source.accessor(i), derived.accessor(i)):
            raise ValueError("Unexpected non-root accessor edit")
    # Also check all bytes outside the exact root float locations, including images.
    item = source.json["accessors"][index];view = source.json["bufferViews"][item["bufferView"]]
    offset = view.get("byteOffset", 0) + item.get("byteOffset", 0);stride = view.get("byteStride", 12)
    old = bytearray(source.binary);new = bytearray(derived.binary)
    for i in range(item["count"]):
        old[offset+i*stride:offset+i*stride+12] = b"\0"*12
        new[offset+i*stride:offset+i*stride+12] = b"\0"*12
    if old != new:
        raise ValueError("Unexpected binary change outside root translations")
    animation = source.json["animations"][0]
    keys = np.unique(np.concatenate([source.accessor(s["input"]).reshape(-1) for s in animation["samplers"]])).astype(float)
    samples = sorted(set(np.linspace(float(keys.min()), float(keys.max()), 19).tolist()+keys[:3].tolist()+[metadata["anchorSeconds"]]))
    root = metadata["rootNodeIndex"];anchor = np.array(metadata["anchorWorldGLTF"])
    checks = []
    rest_error = float(np.abs(source.skinned_positions()-derived.skinned_positions()).max())
    if rest_error != 0:
        raise ValueError("Reference skin changed")
    for time in samples:
        before_world = source.world_matrices(0, time);after_world = derived.world_matrices(0, time)
        horizontal = before_world[root, :3, 3] - anchor;horizontal[1] = 0
        expected = source.skinned_positions(0, time) - horizontal
        actual = derived.skinned_positions(0, time)
        error = float(np.linalg.norm(expected-actual, axis=1).max())
        vertical_error = float(abs(after_world[root, 1, 3]-before_world[root, 1, 3]))
        rotation_scale_error = float(np.abs(after_world[:, :3, :3]-before_world[:, :3, :3]).max())
        root_horizontal_error = float(np.linalg.norm((after_world[root, :3, 3]-anchor)[[0, 2]]))
        if max(error, vertical_error, rotation_scale_error, root_horizontal_error) > tolerance:
            raise ValueError("Unexpected pose change at " + str(time))
        checks.append({"seconds": time, "vertices": len(actual), "maxWorldPositionResidual": error,
                       "rootVerticalResidual": vertical_error, "jointRotationScaleResidual": rotation_scale_error,
                       "rootHorizontalResidual": root_horizontal_error,
                       "intendedWorldTranslationGLTF": (-horizontal).tolist()})
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--anchor-time", type=float)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    receipt = output.with_suffix(".in-place.json")
    if source == output or source.suffix != ".glb" or output.suffix != ".glb" or not source.is_relative_to(ASSETS.resolve()) or output.parent != ASSETS.resolve():
        parser.error("Use a private GLB source and a distinct derivative inside Local/CustomuseAssets")
    if output.exists() or receipt.exists():
        parser.error("Output exists; choose a new derivative name")
    original = source.read_bytes();model = CPU.GLB(original)
    derived, metadata = prepare(model, args.anchor_time)
    payload = derived.bytes();checks = validate(model, CPU.GLB(payload), metadata)
    if source.read_bytes() != original:
        raise ValueError("Source changed during processing")
    report = {"source": source.name, "sourceSHA256": hashlib.sha256(original).hexdigest(),
              "derivative": output.name, "derivativeSHA256": hashlib.sha256(payload).hexdigest(),
              "operation": "world-horizontal root translation removal only", **metadata,
              "absoluteWorldTolerance": 2.e-6, "checks": checks, "cpuProofPassed": True,
              "rootVerticalBobAndAllRotationsPreserved": True, "geometryWeightsAndOtherTracksUnchanged": True,
              "nativeVerified": False, "trimOrLoopAccepted": False,
              "unrealImportPolicy": "force_root_lock=false; enable_root_motion=false; do not apply full-root first-frame lock"}
    with os.fdopen(os.open(output, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600), "wb") as f:
        f.write(payload)
    with os.fdopen(os.open(receipt, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600), "w") as f:
        json.dump(report, f, indent=2);f.write("\n")
    print(json.dumps({"derivative": str(output), "receipt": str(receipt), "sha256": report["derivativeSHA256"],
                      "samples": len(checks), "maxPoseResidual": max(c["maxWorldPositionResidual"] for c in checks)}, indent=2))


if __name__ == "__main__":
    main()
