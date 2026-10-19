#!/usr/bin/env python3
"""Make a standing one-hand idle candidate from the active Knight v015 rest rig.

The active stance generator moves the right arm and re-solves both legs for a
simple idle, which visibly damages the silhouette in the browser preview. This
candidate keeps all arm, hand, hip, and leg transforms at their intact rest
values. Only the upper torso, neck, and shoulder armor breathe. The boat sword
remains a separate mesh and is attached for review by the asset viewer.

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
BREATH_LIFT = 0.008  # Rig units; 1.95 cm at the Knight's 244 cm scale.


def local_world_turn(model: GLB, rest: np.ndarray, node: int, axis: tuple[float, float, float], degrees: float) -> np.ndarray:
    """Turn a rest bone around a world-space axis, returning local glTF XYZW."""
    parent = model.parents.get(node)
    parent_world = Rotation.from_matrix(rest[parent, :3, :3]) if parent is not None else Rotation.identity()
    reference = Rotation.from_quat(model.json["nodes"][node].get("rotation", [0, 0, 0, 1]))
    turn = Rotation.from_rotvec(np.asarray(axis, dtype=float) * math.radians(degrees))
    return (parent_world.inv() * turn * parent_world * reference).as_quat()


def write_candidate(source: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError(f"Refusing to replace an existing review: {output}")
    model = GLB(source)
    if model.json.get("animations"):
        raise ValueError("Expected the animation-free Knight v015 rig")
    names = {node.get("name"): index for index, node in enumerate(model.json["nodes"])}
    required = {"Hips", "Spine", "Spine1", "Spine2", "Neck", "Head", "RightShoulder", "LeftShoulder", "RightArm", "RightForeArm", "RightHand", "RightUpLeg", "RightLeg", "RightFoot", "LeftUpLeg", "LeftLeg", "LeftFoot"}
    if not required.issubset(names):
        raise ValueError("The input is not the expected Knight v015 skeleton")
    rest = model.world_matrices()
    torso = ["Spine", "Spine1", "Spine2", "Neck", "RightShoulder", "LeftShoulder"]
    chest = names["Spine2"]
    chest_reference = np.asarray(model.json["nodes"][chest].get("translation", [0, 0, 0]), dtype=float)
    chest_parent = model.parents[chest]
    chest_lift_local = rest[chest_parent, :3, :3].T @ np.array([0.0, BREATH_LIFT, 0.0])

    times = np.linspace(0.0, DURATION, SAMPLES)
    poses: list[dict] = []
    for t in times:
        inhale = 0.5 - 0.5 * math.cos(2.0 * math.pi * float(t) / DURATION)
        pose = {
            (names["Spine"], "rotation"): local_world_turn(model, rest, names["Spine"], (1, 0, 0), -0.18 * inhale),
            (names["Spine1"], "rotation"): local_world_turn(model, rest, names["Spine1"], (1, 0, 0), -0.28 * inhale),
            (names["Spine2"], "rotation"): local_world_turn(model, rest, names["Spine2"], (1, 0, 0), 0.38 * inhale),
            (names["Neck"], "rotation"): local_world_turn(model, rest, names["Neck"], (1, 0, 0), 0.08 * inhale),
            (names["RightShoulder"], "rotation"): local_world_turn(model, rest, names["RightShoulder"], (0, 0, 1), -1.5 * inhale),
            (names["LeftShoulder"], "rotation"): local_world_turn(model, rest, names["LeftShoulder"], (0, 0, 1), 1.5 * inhale),
            (chest, "translation"): chest_reference + chest_lift_local * inhale,
        }
        poses.append(pose)

    for key in poses[0]:
        if not np.allclose(poses[0][key], poses[-1][key], atol=1e-8):
            raise ValueError(f"Breathing loop does not close: {key}")
    result = build(model, poses, times, "IdleOneHand_Breathing_v1")
    if result.binary[:len(model.binary)] != model.binary:
        raise ValueError("Source geometry or bind data changed")
    for section in ("nodes", "meshes", "skins", "materials", "textures", "images"):
        if result.json.get(section) != model.json.get(section):
            raise ValueError(f"Source {section} changed")
    targets = {channel["target"]["node"] for channel in result.json["animations"][0]["channels"]}
    if targets != {names[name] for name in torso}:
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
        "animatedBones": torso,
        "hipsLegsArmsHandsRestPose": True,
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
