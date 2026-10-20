#!/usr/bin/env python3
"""Compact two-hand light cut, returning to the exact approved ready idle.

Uses the established rigid hilt / two-palm constraint and anatomical limb solver.
The authored timing is normal playback speed; no browser speed override.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from author_knight_twohand_strong_review import write_candidate

KEYS = np.array([0, .10, .24, .33, .43, .54, .66, .83, 1.10])
VALUES = {
    "bladeYaw": [0, -5, -16, -8, 12, 20, 20, 8, 0],
    "bladeElev": [0, -16, -28, -36, -45, -50, -42, -16, 0],
    "torsoYaw": [0, -10, -28, -22, 23, 50, 45, 14, 0],
    "hipYaw": [0, -3, -13, -9, 10, 25, 22, 7, 0],
    "pitch": [0, 1, 2, 4, 7, 10, 8, 3, 0],
    "hipY": [0, -.003, -.012, -.018, -.030, -.035, -.028, -.01, 0],
    "hipZ": [0, -.003, -.012, 0, .035, .05, .045, .018, 0],
    "gripX": [0, -.005, -.015, -.008, .005, .012, .01, .003, 0],
    "gripY": [0, -.02, -.04, -.035, -.04, -.05, -.04, -.015, 0],
    "gripZ": [0, -.005, -.01, .005, .025, .03, .02, .005, 0],
    "stepY": [0, 0, .01, .022, .012, 0, 0, .018, 0],
    "stepZ": [0, 0, .005, .025, .065, .08, .08, .04, 0],
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--body", type=Path, required=True)
    parser.add_argument("--approved-idle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise FileExistsError(args.report)
    report = write_candidate(args.body, args.approved_idle, args.output,
                             "light-cut", profile=(KEYS, VALUES))
    with args.report.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({k: v for k, v in report.items() if k != "keyMoments"}, indent=2))
