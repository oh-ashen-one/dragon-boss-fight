#!/usr/bin/env python3
"""Create reversible, measured grounding/wrist-lift candidates for native review.

Only Hips translation and (Idle/Walk) RightHand rotation key values may change.
The Hips correction is constant world-up, converted through the actual parent.
The wrist correction is one constant bone-local quaternion from the reviewed
diagnosis, not a per-frame clearance clamp. Geometry and weights never change.
Candidates are not enabled in the game and do not imply visual acceptance.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "Local/CustomuseAssets"
SPEC = importlib.util.spec_from_file_location("veyr_motion_cpu", ROOT / "tools/unreal/normalize_customuse_glb.py")
CPU = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CPU)
PROFILES = {"idle": (11.81, 16.), "walk": (9.06, 3.1), "light": (12.54, 0.), "heavy": (3.66, 0.)}


def quaternion_product(left, right):
    return np.concatenate((left[3]*right[:3]+right[3]*left[:3]+np.cross(left[:3], right[:3]),
                           [left[3]*right[3]-np.dot(left[:3], right[:3])]))


def output_track(model, node, path):
    clip = model.json["animations"][0]
    channels = [c for c in clip["channels"] if c["target"].get("node") == node and c["target"].get("path") == path]
    if len(channels) != 1:
        raise ValueError("Expected one " + path + " track for the selected joint")
    sampler = clip["samplers"][channels[0]["sampler"]]
    if sampler.get("interpolation", "LINEAR") != "LINEAR":
        raise ValueError("Only LINEAR TRS animation is supported")
    if sum(s["output"] == sampler["output"] for s in clip["samplers"]) != 1:
        raise ValueError("Edited animation accessor is shared")
    item = model.json["accessors"][sampler["output"]]
    expected_type = "VEC3" if path == "translation" else "VEC4"
    if item["componentType"] != 5126 or item["type"] != expected_type:
        raise ValueError("Expected float32 " + expected_type + " animation keys")
    return sampler["output"]


def descendants(model, root):
    result, pending = set(), [root]
    while pending:
        node = pending.pop()
        if node in result:
            raise ValueError("Cyclic hierarchy")
        result.add(node)
        pending.extend(model.json["nodes"][node].get("children", []))
    return result


def prepare(source, label, diagnosis):
    if len(source.json.get("animations", [])) != 1 or len(source.json.get("skins", [])) != 1:
        raise ValueError("Exactly one animation and skin are required")
    lookup = {n.get("name"): i for i, n in enumerate(source.json["nodes"])}
    hips, hand = lookup["Hips"], lookup["RightHand"]
    if not set(source.json["skins"][0]["joints"]).issubset(descendants(source, hips)):
        raise ValueError("Every skin joint must descend from Hips")
    parents = []
    p = source.parents.get(hips)
    while p is not None:
        if p in parents:
            raise ValueError("Cyclic root ancestry")
        parents.append(p);p = source.parents.get(p)
    if any(c["target"].get("node") in parents for c in source.json["animations"][0]["channels"]):
        raise ValueError("Animated Hips parent is unsupported for constant world-up correction")
    parent = source.world_matrices()[source.parents[hips]] if hips in source.parents else np.eye(4)
    rest = source.skinned_positions()
    world_to_cm = 244. / np.ptp(rest[:, 1])
    grounding_cm, degrees = PROFILES[label]
    if not 0 <= degrees <= 18:
        raise ValueError("Wrist candidate exceeds the authorized 18 degree bound")
    displacement = np.array([0., grounding_cm/world_to_cm, 0.])
    local_delta = np.linalg.inv(parent[:3, :3]) @ displacement
    derived = CPU.GLB(source.bytes())
    root_track = output_track(source, hips, "translation")
    derived.accessor(root_track)[:] = source.accessor(root_track).astype(float) + local_delta
    changed = {root_track}
    axis = None
    if degrees:
        orientation = diagnosis["worstClearancePoseOrientation"]
        # UE quaternion conversion is (-qx,-qz,-qy,qw); invert it to obtain
        # the exact glTF bone-local lift axis. The axis is fixed for the clip.
        axis = -np.asarray(orientation["wristLocalTipLiftAxisUE"], dtype=float)[[0, 2, 1]]
        if not np.all(np.isfinite(axis)) or np.linalg.norm(axis) < 1.e-8:
            raise ValueError("Invalid measured wrist axis")
        axis /= np.linalg.norm(axis)
        radians = math.radians(degrees)
        delta = np.append(axis*math.sin(radians/2), math.cos(radians/2))
        hand_track = output_track(source, hand, "rotation")
        keys = source.accessor(hand_track).astype(float)
        edited = []
        for key in keys:
            key /= np.linalg.norm(key)
            rotated = quaternion_product(key, delta)  # constant post-rotation in hand-local space
            edited.append(rotated/np.linalg.norm(rotated))
        derived.accessor(hand_track)[:] = np.asarray(edited)
        changed.add(hand_track)
    for index in changed:
        item = derived.json["accessors"][index];values = derived.accessor(index)
        if "min" in item:item["min"] = values.min(0).tolist()
        if "max" in item:item["max"] = values.max(0).tolist()
    return derived, {"hipsNode": hips, "handNode": hand, "changedAccessors": sorted(changed),
                     "groundingWorldCm": grounding_cm, "groundingWorldGLTF": displacement.tolist(),
                     "hipsLocalTranslationDelta": local_delta.tolist(), "hipsParentWorld": parent.tolist(),
                     "wristLiftDegrees": degrees, "fixedWristLocalAxisGLTF": axis.tolist() if axis is not None else None,
                     "axisConvention": "One constant measured hand-local post-rotation per clip; no time-varying clamp",
                     "avatarHeightCm": 244., "sourceWorldToCm": float(world_to_cm)}


def validate(source, derived, metadata, weapon_ids):
    changed = set(metadata["changedAccessors"])
    left, right = json.loads(json.dumps(source.json)), json.loads(json.dumps(derived.json))
    for index in changed:
        for d in (left, right):
            d["accessors"][index].pop("min", None);d["accessors"][index].pop("max", None)
    if left != right:
        raise ValueError("Unexpected structural/animation declaration change")
    old, new = bytearray(source.binary), bytearray(derived.binary)
    for index in changed:
        item = source.json["accessors"][index];view = source.json["bufferViews"][item["bufferView"]]
        width = CPU.WIDTHS[item["type"]]*4;stride = view.get("byteStride", width)
        offset = view.get("byteOffset", 0)+item.get("byteOffset", 0)
        for i in range(item["count"]):
            old[offset+i*stride:offset+i*stride+width] = b"\0"*width
            new[offset+i*stride:offset+i*stride+width] = b"\0"*width
    if old != new:
        raise ValueError("Binary changes outside authorized animation keys")
    for i in range(len(source.json["accessors"])):
        if i not in changed and not np.array_equal(source.accessor(i), derived.accessor(i)):
            raise ValueError("Geometry, weights or other animation tracks changed")
    node = source.json["nodes"][source.mesh_node()];skin = source.json["skins"][node["skin"]]
    primitives = source.json["meshes"][node["mesh"]]["primitives"]
    if len(primitives) != 1:
        raise ValueError("This calibration validator requires one primitive")
    attrs = primitives[0]["attributes"]
    joints = source.accessor(attrs["JOINTS_0"]);weights = source.accessor(attrs["WEIGHTS_0"])
    affected_nodes = descendants(source, metadata["handNode"]) if metadata["wristLiftDegrees"] else set()
    affected_slots = [i for i, node_index in enumerate(skin["joints"]) if node_index in affected_nodes]
    unaffected = ~np.any(np.isin(joints, affected_slots) & (weights > 0), axis=1)
    displacement = np.asarray(metadata["groundingWorldGLTF"])
    clip = source.json["animations"][0]
    timeline = np.unique(np.concatenate([source.accessor(s["input"]).reshape(-1) for s in clip["samplers"]])).astype(float)
    times = sorted(set(np.linspace(timeline.min(), timeline.max(), 17).tolist()+timeline[:3].tolist()))
    def distances(points):
        squared = np.sum(points*points, axis=1)
        return np.sqrt(np.maximum(0., squared[:, None]+squared[None, :]-2*(points@points.T)))
    rest_error = float(np.abs(source.skinned_positions()-derived.skinned_positions()).max())
    if rest_error != 0:raise ValueError("Reference skin changed")
    checks = []
    for t in times:
        before = source.skinned_positions(0, t);after = derived.skinned_positions(0, t)
        residual = float(np.linalg.norm(after[unaffected]-before[unaffected]-displacement, axis=1).max())
        rigid_error = float(np.abs(distances(after[weapon_ids])-distances(before[weapon_ids])).max())
        if residual > 2.e-6 or rigid_error > 2.e-6:
            raise ValueError("Unexpected unaffected-body displacement or weapon deformation")
        checks.append({"seconds": float(t), "unaffectedVertices": int(unaffected.sum()),
                       "maxUnaffectedPositionResidual": residual, "maxWeaponPairDistanceResidual": rigid_error,
                       "weaponVertices": len(weapon_ids), "weaponUniquePairs": len(weapon_ids)*(len(weapon_ids)-1)//2})
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--clip", choices=tuple(PROFILES), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    receipt = output.with_suffix(".calibration.json")
    if source == output or not source.is_relative_to(ASSETS.resolve()) or output.parent != ASSETS.resolve() or output.suffix != ".glb":
        parser.error("Use a private source and distinct GLB derivative inside Local/CustomuseAssets")
    if output.exists() or receipt.exists():parser.error("Output exists; choose a fresh candidate")
    raw = source.read_bytes();digest = hashlib.sha256(raw).hexdigest()
    diagnosis = json.loads((ASSETS/"knight-sole-floor-diagnosis-v1.json").read_text())["clips"][args.clip]
    if diagnosis["sha256"] != digest or diagnosis["file"] != source.name:
        raise ValueError("Source does not match the measured diagnosis")
    mask = json.loads((ASSETS/"weapon-topology-v1/candidate-mask.json").read_text())
    weapon_ids = np.asarray(mask["vertexIndices"], dtype=int)
    model = CPU.GLB(raw);derived, metadata = prepare(model, args.clip, diagnosis)
    payload = derived.bytes();checks = validate(model, CPU.GLB(payload), metadata, weapon_ids)
    if source.read_bytes() != raw:raise ValueError("Original changed during processing")
    report = {"status": "CORRECTIVE_CANDIDATE_REQUIRES_NATIVE_VISUAL_REVIEW", "source": source.name,
              "sourceSHA256": digest, "derivative": output.name, "derivativeSHA256": hashlib.sha256(payload).hexdigest(),
              **metadata, "checks": checks, "cpuProofPassed": True, "referenceSkinUnchanged": True,
              "geometryWeightsOtherRotationTracksUnchanged": True, "nativeAccepted": False,
              "unrealImportPolicy": "force_root_lock=false; enable_root_motion=false; preserve these root corrections"}
    with os.fdopen(os.open(output, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600), "wb") as f:f.write(payload)
    with os.fdopen(os.open(receipt, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600), "w") as f:json.dump(report, f, indent=2);f.write("\n")
    print(json.dumps({"derivative": str(output), "receipt": str(receipt), "sha256": report["derivativeSHA256"],
                      "maxUnaffectedResidual": max(c["maxUnaffectedPositionResidual"] for c in checks),
                      "maxWeaponShapeResidual": max(c["maxWeaponPairDistanceResidual"] for c in checks)}, indent=2))


if __name__ == "__main__":main()
