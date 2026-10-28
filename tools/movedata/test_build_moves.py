"""Synthetic check of the move-data builder: one point moving fast for 10 frames makes one window.

    python3 -m unittest discover -s tools/movedata -p 'test_*.py' -v
"""
import json
import math
import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_moves as bm  # noqa: E402

FPS = 24.0
N = 40
VMAX = 60.0          # cm per frame at the peak = 14.4 m/s
START, LEN = 10, 10  # moving from frame 10 to frame 20


def tip_x(f):
    """Position (cm) of a point whose speed is VMAX * sin^2(pi (f - START) / LEN) while it moves."""
    u = min(max(f - START, 0.0), LEN)
    return VMAX * (u / 2.0 - LEN / (4 * math.pi) * math.sin(2 * math.pi * u / LEN))


def synthetic_sample(path):
    frames = np.arange(N)
    bones = ["root", "body", "foot"]
    eye = np.tile(np.eye(3), (N, 3, 1, 1))
    heads = np.zeros((N, 3, 3)); heads[:, 1] = [0, 0, 100]; heads[:, 2] = [50, 0, 0]
    root = np.tile(np.eye(4), (N, 1, 1))
    tip = np.zeros((N, 3)); tip[:, 0] = [tip_x(f) for f in frames]; tip[:, 2] = 200.0
    sole = np.tile([50.0, 0.0, 0.5], (N, 1))
    parts = np.stack([tip, sole, sole], axis=1)
    lows = np.tile([50.0, 0.0, 0.0], (N, 1, 1))
    rng = np.random.default_rng(0)
    verts = (rng.normal(size=(400, 3)) * [60, 20, 20] + [0, 0, 100]).astype(np.float32)
    vbone = np.ones(len(verts), dtype=np.int32)
    verts[:40] = rng.normal(size=(40, 3)) * [5, 5, 1] + [50, 0, 1]
    vbone[:40] = 2
    rig = {
        "root_bone": "root", "track_bone": "root", "body_bone": "body", "game_scale": 1.0,
        "feet": {"f": {"bones": ["foot"], "bone": "foot"}},
        "body_low": {},
        "attack_parts": {"tip": {"point": "tip"}},
        "window_only_parts": {},
        "hurt": {"body": {"bone": "body", "bones": ["body"], "kind": "body", "damage": 1.0}},
    }
    np.savez_compressed(
        path, move=np.array("swipe"), action=np.array("swipe_act"), blend=np.array("synthetic.blend"),
        blend_md5=np.array("0"), rig_map=np.array(json.dumps(rig)), fps=np.array(FPS),
        times=frames / FPS, frame_range=np.array([0, N - 1]), bone_names=np.array(bones),
        heads=heads, rots=eye, local_quat=np.tile([1.0, 0, 0, 0], (N, 3, 1)),
        rest_heads=heads[0], rest_rots=eye[0], root_name=np.array("root"), root_mat=root,
        part_names=np.array(["tip", "sole_f", "toe_f"]), parts=parts, rest_parts=parts[0],
        low_names=np.array(["foot_f"]), lows=lows,
        mesh_min=np.tile([-100.0, -50, 0], (N, 1)), mesh_max=np.tile([100.0, 50, 200], (N, 1)),
        mesh_height_cm=np.array(200.0),
        vert_rest=verts, vert_bone=vbone,
        sub_idx=np.arange(len(verts)), sub_pos=np.tile(verts, (N, 1, 1)),
    )


def crossing(level_mps, rising):
    """Analytic frame where the profile's speed equals level (m/s)."""
    x = math.asin(math.sqrt(level_mps * 100.0 / FPS / VMAX))
    return START + (x if rising else math.pi - x) * LEN / math.pi


class SyntheticWindow(unittest.TestCase):
    def test_one_fast_point_makes_one_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            sample = os.path.join(tmp, "swipe.sample.npz")
            synthetic_sample(sample)
            out = os.path.join(tmp, "data")
            bm.build_all([sample], out)
            with open(os.path.join(out, "moves.json")) as f:
                moves = json.load(f)
            for name in ("boxes.json", "tempo.json", "sounds.json"):
                self.assertTrue(os.path.exists(os.path.join(out, name)), name)
        mv = moves["moves"]["swipe"]
        self.assertEqual(len(mv["attacks"]), 1, mv["attacks"])
        w = mv["attacks"][0]
        self.assertEqual(w["part"], "tip")
        half_frame = 0.5 / FPS
        self.assertAlmostEqual(w["t0"], crossing(5.0, True) / FPS, delta=half_frame)
        self.assertAlmostEqual(w["t1"], crossing(5.0 * bm.DEFAULTS["exit_ratio"], False) / FPS, delta=half_frame)
        self.assertAlmostEqual(w["peak_t"], (START + LEN / 2) / FPS, delta=half_frame)
        self.assertAlmostEqual(w["peak_v"], VMAX * FPS / 100.0, delta=0.05 * VMAX * FPS / 100.0)
        self.assertAlmostEqual(w["at_peak"][0], tip_x(START + LEN / 2), delta=VMAX)
        self.assertEqual(mv["frames"], N)
        self.assertEqual(mv["track"][0], [0.0, 0.0, 0.0])
        self.assertEqual(mv["quality"]["slides"], 0)
        self.assertEqual(len(mv["stances"]), 1)
        self.assertEqual(mv["shocks"], [])

    def test_threshold_override_removes_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            sample = os.path.join(tmp, "swipe.sample.npz")
            synthetic_sample(sample)
            doc, _, _ = bm.build_all([sample], os.path.join(tmp, "d"), part_thresholds={"tip": 20.0})
        self.assertEqual(doc["moves"]["swipe"]["attacks"], [])

    def test_constant_speed_run(self):
        speed = np.zeros(30); speed[8:18] = 7.0
        ws = bm.find_windows(speed, FPS, 5.0)
        self.assertEqual(len(ws), 1)
        self.assertEqual((ws[0]["f0"], ws[0]["f1"]), (8, 17))
        self.assertAlmostEqual(ws[0]["peak_v"], 7.0)


if __name__ == "__main__":
    unittest.main()
