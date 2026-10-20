#!/usr/bin/env python3
"""Independently inspect a baked two-hand clip against its approved idle."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from author_knight_actions import sample
from author_knight_twohand_strong_review import GRIP, SOCKET, SCALE
from inspect_weapon_topology import GLB


def verify(body, idle, clip):
    source, approved, g = GLB(body), GLB(idle), GLB(clip)
    names = {n.get("name"): i for i, n in enumerate(g.json["nodes"])}
    count = len(source.json["nodes"])
    assert g.binary[:len(source.binary)] == source.binary
    assert g.json["nodes"][:count] == source.json["nodes"]
    assert all(g.json[k] == source.json[k] for k in ("skins", "meshes", "materials"))
    duration = max(float(g.accessor(s["input"]).max())
                   for s in g.json["animations"][0]["samplers"])
    base = approved.world_matrices(0, 0)
    right = names["RightHand"]
    grip = base[right, :3, 3] + base[right, :3, :3] @ GRIP
    axis = base[right, :3, :3] @ SOCKET[:, 1]
    palm_locals = {}
    for side, offset in (("Right", 0), ("Left", -.18*SCALE)):
        h = names[side+"Hand"]
        palm_locals[side] = np.linalg.solve(base[h, :3, :3], grip+axis*offset-base[h, :3, 3])
    palm_errors = {"Right": 0., "Left": 0.}
    joint_names = [s+n for s in ("Right", "Left") for n in ("Arm", "ForeArm", "Hand", "Leg")]
    rotations = {name: [] for name in joint_names}
    for t in np.linspace(0, duration, int(np.ceil(duration*120))+1):
        w = g.world_matrices(0, float(t))
        pose = sample(g, float(t))
        socket = w[names["ReviewWeaponSocket"]]
        for side, offset in (("Right", -.075), ("Left", -.255)):
            h = w[names[side+"Hand"]]
            palm = h[:3, 3] + h[:3, :3] @ palm_locals[side]
            target = socket[:3, 3] + socket[:3, :3] @ np.array([0, offset, 0])
            palm_errors[side] = max(palm_errors[side], float(np.linalg.norm(palm-target)))
        for name in joint_names:
            rotations[name].append(pose[(names[name], "rotation")])
    steps = {}
    for name, values in rotations.items():
        rots = Rotation.from_quat(values)
        steps[name] = float(np.rad2deg((rots[:-1].inv()*rots[1:]).magnitude()).max())
    start_error = float(np.abs(g.world_matrices(0, 0)[:count]-base).max())
    end_error = float(np.abs(g.world_matrices(0, duration)[:count]-base).max())
    assert max(start_error, end_error) < 1e-6
    # Interpolated rotations can produce tiny contact deviations between baked keys.
    assert max(palm_errors.values()) < .002, palm_errors
    assert max(steps.values()) < 30, steps
    return {
        "sha256": hashlib.sha256(Path(clip).read_bytes()).hexdigest(),
        "durationSeconds": duration, "auditHz": 120,
        "startPoseError": start_error, "endPoseError": end_error,
        "maximumPalmDriftRigUnits": palm_errors,
        "maximumFrameRotationDegrees": steps,
        "sourceMeshSkinBindMaterialsPreserved": True,
        "visualReview": "pending", "ownerApproved": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("body", "idle", "clip", "report"):
        parser.add_argument("--"+name, type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.body, args.idle, args.clip)
    with args.report.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps(report, indent=2))
