#!/usr/bin/env python3
"""Make a standing one-hand idle candidate from the active Knight v015 rest rig.

The active stance generator moves the right arm and re-solves both legs for a
simple idle, which visibly damages the silhouette in the browser preview. This
candidate starts from the intact rest pose. The feet, legs, forearms, hands, and
finger joints keep their rest transforms while the torso, shoulders, upper
arms, neck, and head breathe and sway. The boat sword remains a separate mesh
and is attached for review by the asset viewer with the same grip as Knight body.

This script writes an exclusive review candidate. It does not change an active
Unreal asset, the accepted build, or a prior GLB.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from author_knight_actions import build
from inspect_weapon_topology import GLB


DURATION = 4.0
SAMPLES = 97
BREATH_LIFT = 0.016  # Rig units; 3.91 cm at the Knight's 244 cm scale.
LOWER_TORSO_LIFT = 0.002  # Another 0.49 cm through the abdomen.


def local_world_turn(model: GLB, rest: np.ndarray, node: int, degrees_xyz: tuple[float, float, float]) -> np.ndarray:
    """Turn a rest bone by a small world-space rotation vector; return glTF XYZW."""
    parent = model.parents.get(node)
    parent_world = Rotation.from_matrix(rest[parent, :3, :3]) if parent is not None else Rotation.identity()
    reference = Rotation.from_quat(model.json["nodes"][node].get("rotation", [0, 0, 0, 1]))
    turn = Rotation.from_rotvec(np.deg2rad(np.asarray(degrees_xyz, dtype=float)))
    return (parent_world.inv() * turn * parent_world * reference).as_quat()


def write_candidate(source: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError(f"Refusing to replace an existing review: {output}")
    model = GLB(source)
    if model.json.get("animations"):
        raise ValueError("Expected the animation-free Knight v015 rig")
    names = {node.get("name"): index for index, node in enumerate(model.json["nodes"])}
    required = {"Hips", "Spine", "Spine1", "Spine2", "Neck", "Head", "RightShoulder", "LeftShoulder", "RightArm", "LeftArm", "RightForeArm", "RightHand", "RightUpLeg", "RightLeg", "RightFoot", "LeftUpLeg", "LeftLeg", "LeftFoot"}
    if not required.issubset(names):
        raise ValueError("The input is not the expected Knight v015 skeleton")
    rest = model.world_matrices()
    animated_bones = ["Spine", "Spine1", "Spine2", "Neck", "Head", "RightShoulder", "LeftShoulder", "RightArm", "LeftArm"]
    lower_torso = names["Spine"]
    lower_reference = np.asarray(model.json["nodes"][lower_torso].get("translation", [0, 0, 0]), dtype=float)
    lower_parent = model.parents[lower_torso]
    lower_lift_local = rest[lower_parent, :3, :3].T @ np.array([0.0, LOWER_TORSO_LIFT, 0.0])
    chest = names["Spine2"]
    chest_reference = np.asarray(model.json["nodes"][chest].get("translation", [0, 0, 0]), dtype=float)
    chest_parent = model.parents[chest]
    chest_lift_local = rest[chest_parent, :3, :3].T @ np.array([0.0, BREATH_LIFT, 0.0])

    times = np.linspace(0.0, DURATION, SAMPLES)
    poses: list[dict] = []
    for t in times:
        inhale = 0.5 - 0.5 * math.cos(2.0 * math.pi * float(t) / DURATION)
        sway = math.sin(2.0 * math.pi * float(t) / DURATION)
        pose = {
            (names["Spine"], "rotation"): local_world_turn(model, rest, names["Spine"], (-0.7 * inhale, 0, 0.7 * sway)),
            (names["Spine1"], "rotation"): local_world_turn(model, rest, names["Spine1"], (-0.8 * inhale, 0, -0.25 * sway)),
            (names["Spine2"], "rotation"): local_world_turn(model, rest, names["Spine2"], (1.2 * inhale, 0, 0.1 * sway)),
            (names["Neck"], "rotation"): local_world_turn(model, rest, names["Neck"], (0.3 * inhale, 0, -0.15 * sway)),
            (names["Head"], "rotation"): local_world_turn(model, rest, names["Head"], (-0.25 * inhale, 0, -0.25 * sway)),
            (names["RightShoulder"], "rotation"): local_world_turn(model, rest, names["RightShoulder"], (0, 0, -4.0 * inhale)),
            (names["LeftShoulder"], "rotation"): local_world_turn(model, rest, names["LeftShoulder"], (0, 0, 4.0 * inhale)),
            (names["RightArm"], "rotation"): local_world_turn(model, rest, names["RightArm"], (0, 0, -1.0 * inhale)),
            (names["LeftArm"], "rotation"): local_world_turn(model, rest, names["LeftArm"], (0, 0, 1.0 * inhale)),
            (lower_torso, "translation"): lower_reference + lower_lift_local * inhale,
            (chest, "translation"): chest_reference + chest_lift_local * inhale,
        }
        poses.append(pose)

    for key in poses[0]:
        if not np.allclose(poses[0][key], poses[-1][key], atol=1e-8):
            raise ValueError(f"Breathing loop does not close: {key}")
    result = build(model, poses, times, output.stem)
    if result.binary[:len(model.binary)] != model.binary:
        raise ValueError("Source geometry or bind data changed")
    for section in ("nodes", "meshes", "skins", "materials", "textures", "images"):
        if result.json.get(section) != model.json.get(section):
            raise ValueError(f"Source {section} changed")
    targets = {channel["target"]["node"] for channel in result.json["animations"][0]["channels"]}
    if targets != {names[name] for name in animated_bones}:
        raise ValueError("Animation affects something other than the upper body")
    output.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as stream:
        stream.write(result.bytes())
    return {
        "source": str(source),
        "sourceSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "output": str(output),
        "outputSha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "durationSeconds": DURATION,
        "sampleCount": SAMPLES,
        "maximumChestLiftRigUnits": BREATH_LIFT,
        "animatedBones": animated_bones,
        "hipsLegsForearmsHandsRestPose": True,
        "meshAndBindDataPreserved": True,
        "nativeUnrealReview": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(write_candidate(args.source, args.output), indent=2))


if __name__ == "__main__":
    main()
