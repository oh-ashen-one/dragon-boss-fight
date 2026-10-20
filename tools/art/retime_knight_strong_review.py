#!/usr/bin/env python3
"""Retime approved strong motions without resampling poses or weapon contacts."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from inspect_weapon_topology import GLB


SOURCES = (
    ("StrongAttackTwoHand_Sweep_v8", "StrongAttackTwoHand_Sweep_v9",
     "9ac6e44a9e68af840dd2942375fd0131ebdcb0e03c077db2305abb34653da808"),
    ("StrongAttackTwoHand_Thrust_v6", "StrongAttackTwoHand_Thrust_v7",
     "42320336c2c7d09ab65576f9f3bf1f94d6dee82eb7a163e1ef6db2854fc07e89"),
)
RATE = 3.0


def retime(folder, source_name, output_name, expected_hash):
    source = folder / f"{source_name}.glb"
    original = source.read_bytes()
    assert hashlib.sha256(original).hexdigest() == expected_hash
    before = GLB(original)
    after = GLB(original)
    assert len(after.json["animations"]) == 1
    clip = after.json["animations"][0]
    # These baked clips use LINEAR interpolation; no cubic tangents to rescale.
    assert all(s.get("interpolation", "LINEAR") == "LINEAR" for s in clip["samplers"])
    inputs = {s["input"] for s in clip["samplers"]}
    outputs = {s["output"] for s in clip["samplers"]}
    assert not inputs & outputs
    duration = max(float(before.accessor(i).max()) for i in inputs)
    for index in inputs:
        times = after.accessor(index)
        times[:] /= RATE
        assert np.all(np.diff(times[:, 0]) > 0)
        after.json["accessors"][index]["min"] = [float(times.min())]
        after.json["accessors"][index]["max"] = [float(times.max())]
    clip["name"] = f"Veyr_Authored_{output_name}"
    result = after.bytes()
    verified = GLB(result)
    # Every non-time accessor, including mesh/skin and all joint/socket outputs,
    # must retain identical bytes. This also preserves exact endpoint poses.
    for index in range(len(before.json["accessors"])):
        if index not in inputs:
            assert before.accessor(index).tobytes() == verified.accessor(index).tobytes()
    for key in ("nodes", "skins", "meshes", "materials"):
        assert before.json.get(key) == verified.json.get(key)
    assert before.json["animations"][0]["channels"] == clip["channels"]
    assert before.json["animations"][0]["samplers"] == clip["samplers"]
    output = folder / f"{output_name}.glb"
    with output.open("xb") as stream:
        stream.write(result)
    assert source.read_bytes() == original
    return {
        "source": source.name, "sourceSHA256": expected_hash,
        "output": output.name, "outputSHA256": hashlib.sha256(result).hexdigest(),
        "speedFactor": RATE, "originalDurationSeconds": duration,
        "durationSeconds": max(float(verified.accessor(i).max()) for i in inputs),
        "sampleCounts": [len(verified.accessor(i)) for i in sorted(inputs)],
        "allPoseAndWeaponOutputsByteIdentical": True,
        "meshSkinMaterialsNodesUnchanged": True, "sourceUnchanged": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-folder", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = {
        "date": "2026-10-20",
        "approval": "Both source motions approved; faster timing awaiting review",
        "clips": [retime(args.review_folder, *source) for source in SOURCES],
    }
    with args.report.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
