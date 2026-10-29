#!/usr/bin/env python3
"""Round-3 metrics (critic definitions) on the normalized GLBs the game imports, glTF mesh space (+Z boss, +X knight's
left, Y up), game cm = rig m x 240, frames = 30 fps of game time at the in-game rate.

Pose: chest yaw (shoulder line), pelvis yaw (hip line), pelvis-to-chest twist, knee-vs-travel, free (left) hand swing in
the chest frame, ankle width first/last vs idle, first/last vs idle (root-relative joints + sword tip/base), seam step vs
in-cycle steps in three bands (loops sampled at evenly spaced phases, as rendered), blink crouch depth/frames and
afterimage poses, roll-attack exit feet and blade pitch per rendered frame, backpedal guard hand height and the blade vs
the helmet seen from the boss. Pixels: the critic's seam method on the review MP4s (knight crop, three bands).

Usage: measure_round3.py OUT.json            (reads the v030q and v030p plans, the review videos if present)"""
import json, math, struct, subprocess, sys, hashlib
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/art/integration"))
from normalize_approved import GLB  # noqa: E402
CM = 240.0
TIP, BASE = np.array([0, 2.35, 0, 1.0]), np.array([0, .6, 0, 1.0])
K = ROOT / "Local/CustomuseAssets/Polish20261025/knight"
PLAN3 = ROOT / "Local/CustomuseAssets/Polish20261025/knight-v030q/import-plan-KnightB.json"
PLAN2 = ROOT / "Local/CustomuseAssets/Polish20261025/knight-v030p/import-plan-KnightB.json"
REVIEW = ROOT / "Local/knight-review-20261028/serve-round3/media"
BANDS = {"headChest": ["Head", "Neck", "Spine2", "LeftShoulder", "RightShoulder", "LeftArm", "RightArm"],
         "hipsSword": ["Hips", "Spine", "LeftUpLeg", "RightUpLeg", "LeftHand", "RightHand", "LeftForeArm", "RightForeArm", "#tip", "#base"],
         "legsFeet": ["LeftLeg", "RightLeg", "LeftFoot", "RightFoot", "LeftToeBase", "RightToeBase"]}
HIDDEN = (.207, .391)
ECHO = (.184, .391)


def yaw(v):
    return math.degrees(math.atan2(v[0], v[2]))


def wrap(a):
    return (a + 180) % 360 - 180


def facing(Lv):
    return np.array([-Lv[2], 0, Lv[0]])


def sword_points():
    raw = (ROOT / "Local/polish-review-20261025/BoatGreatsword_OneHand_v4.glb").read_bytes()
    n = struct.unpack_from("<I", raw, 12)[0]; doc = json.loads(raw[20:20 + n]); blob = raw[28 + n:]
    a = doc["accessors"][doc["meshes"][0]["primitives"][0]["attributes"]["POSITION"]]; v = doc["bufferViews"][a["bufferView"]]
    off = v.get("byteOffset", 0) + a.get("byteOffset", 0)
    pts = np.frombuffer(blob, dtype="<f4", count=a["count"] * 3, offset=off).reshape(-1, 3)
    pts = pts[pts[:, 1] > .55]  # blade only (as clearance.py)
    return np.c_[pts[::6], np.ones(len(pts[::6]))]


SWORD = sword_points()


def frame(g, w):
    P = lambda n: w[g.names[n]][:3, 3]
    so = w[g.names["WeaponSocket"]]
    out = {"P": {n: P(n) * CM for n in g.names if n in g.skin_names() or n == "WeaponSocket"}}
    out["P"]["#tip"] = (so @ TIP)[:3] * CM; out["P"]["#base"] = (so @ BASE)[:3] * CM
    out["chest"] = yaw(facing(P("LeftArm") - P("RightArm"))); out["pelvis"] = yaw(facing(P("LeftUpLeg") - P("RightUpLeg")))
    knees = []
    for s in ("Left", "Right"):
        h, k, a = P(s + "UpLeg"), P(s + "Leg"), P(s + "Foot")
        d = (a - h) / np.linalg.norm(a - h); off = (k - h) - d * ((k - h) @ d); off[1] = 0
        if np.linalg.norm(off) > 1e-4:
            knees.append(yaw(off))
    out["knees"] = knees
    b = so[:3, :3] @ np.array([0, 1.0, 0]); b /= np.linalg.norm(b)
    out["pitch"] = math.degrees(math.asin(max(-1, min(1, b[1])))); out["blade"] = b
    out["ankles"] = float(np.linalg.norm((P("LeftFoot") - P("RightFoot"))[[0, 2]]) * CM)
    # chest frame: x = knight's left along the shoulder line, y = up, z = chest forward
    L = P("LeftArm") - P("RightArm"); L[1] = 0; L /= np.linalg.norm(L); F = np.array([-L[2], 0, L[0]])
    out["leftHandChest"] = np.array([(P("LeftHand") - P("Spine2")) @ L, (P("LeftHand") - P("Spine2"))[1], (P("LeftHand") - P("Spine2")) @ F]) * CM
    out["handMinusChestY"] = (P("RightHand")[1] - P("Spine2")[1]) * CM
    out["handMinusHipsY"] = (P("RightHand")[1] - P("Hips")[1]) * CM
    out["sword2d"] = (so @ SWORD.T).T[:, :3] * CM
    return out


def hull(pts):
    pts = sorted(map(tuple, pts))
    if len(pts) < 3:
        return pts
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def inside(poly, p):
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        if (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) < 0:
            return False
    return True


def helmet_cover(f):
    """Boss view (orthographic along -Z): fraction of the helmet disk (Head joint + 14 cm up, r 15 cm) covered by the hull
    of the blade points that are in front of the head, and the frontal-plane blade angle from vertical."""
    c = f["P"]["Head"] + np.array([0, 14.0, 0]); r = 15.0
    sw = f["sword2d"]; front = sw[sw[:, 2] > c[2] - 10.0]
    disk = [(c[0] + r * x, c[1] + r * y) for x in np.linspace(-1, 1, 15) for y in np.linspace(-1, 1, 15) if x * x + y * y <= 1]
    frac = 0.0
    if len(front) >= 3:
        hp = hull(front[:, :2]); frac = sum(inside(hp, p) for p in disk) / len(disk)
    tip, base = f["P"]["#tip"], f["P"]["#base"]; d = (tip - base)[:2]
    ang = math.degrees(math.atan2(abs(d[0]), d[1]))
    # 2D distance from the helmet centre to the blade axis segment (base..tip)
    a, b, p = base[:2], tip[:2], c[:2]; u = np.clip((p - a) @ (b - a) / max(1e-9, (b - a) @ (b - a)), 0, 1)
    return frac, ang, float(np.linalg.norm(a + u * (b - a) - p))


IDLE = {}
for grip, fn in (("one", "IdleOneHand_Blender_v2r4.glb"), ("two", "IdleTwoHand_Blender_v2r4.glb")):
    g = GLB(K / fn); IDLE[grip] = frame(g, g.sample(0)[0])


def times(T, rate, loop):
    if loop:
        n = max(8, int(round(T / rate * 30)))
        return [i * T / n for i in range(n)]
    out, i = [], 0
    while i * rate / 30.0 <= T + 1e-9:
        out.append(i * rate / 30.0); i += 1
    if out[-1] < T - 1e-6:
        out.append(T)
    return out


def pose_dist(a, b, names=None):
    names = names or [n for n in a["P"] if n in b["P"]]
    d = [float(np.linalg.norm(a["P"][n] - b["P"][n])) for n in names]
    return max(d), float(np.mean(d))


def measure(c, label):
    path = Path(c["file"]); g = GLB(path); T = g.duration(); name = c["name"]; loop = c["loop"]
    grip = "two" if "TwoHand" in name else "one"
    rate = rate_of(c)
    ts = times(T, rate, loop); F = [frame(g, g.sample(float(t))[0]) for t in ts]; I = IDLE[grip]
    r = {"round": label, "file": path.name, "sha256": c["sha256"], "duration": round(T, 4), "rate": round(rate, 4), "frames30": len(F)}
    ch = [f["chest"] for f in F]; pe = [f["pelvis"] for f in F]; tw = [abs(wrap(p - q)) for p, q in zip(pe, ch)]
    r["chestYaw"] = [round(min(ch), 1), round(max(ch), 1), round(float(np.mean(ch)), 1)]; r["chestToBossMaxDeg"] = round(max(abs(x) for x in ch), 1)
    r["pelvisYaw"] = [round(min(pe), 1), round(max(pe), 1), round(float(np.mean(pe)), 1)]
    r["pelvisToChestTwistMaxDeg"] = round(max(tw), 1); r["pelvisToChestTwistMeanDeg"] = round(float(np.mean(tw)), 1)
    lh = np.array([f["leftHandChest"] for f in F]); rng = lh.max(0) - lh.min(0)
    r["freeArmSwingCm"] = {"lateral": round(float(rng[0]), 1), "up": round(float(rng[1]), 1), "forward": round(float(rng[2]), 1), "max": round(float(rng.max()), 1)}
    r["anklesFirstLastCm"] = [round(F[0]["ankles"], 1), round(F[-1]["ankles"], 1)]; r["idleAnklesCm"] = round(I["ankles"], 1)
    common = [n for n in I["P"] if n in F[0]["P"]]
    r["firstVsIdleCm"] = dict(zip(("max", "mean"), map(lambda x: round(x, 2), pose_dist(F[0], I, common))))
    lastF = frame(g, g.sample(float(T))[0])
    r["lastVsIdleCm"] = dict(zip(("max", "mean"), map(lambda x: round(x, 2), pose_dist(lastF, I, common))))
    # knee vs travel (stance toe velocity reversed), as round 2
    vel = []
    for s in ("Left", "Right"):
        ys = [f["P"][s + "ToeBase"][1] for f in F]; floor = min(ys)
        for i in range(len(F) - 1):
            if F[i]["P"][s + "ToeBase"][1] - floor < 2.0 and F[i + 1]["P"][s + "ToeBase"][1] - floor < 4.0:
                vel.append((F[i + 1]["P"][s + "ToeBase"] - F[i]["P"][s + "ToeBase"])[[0, 2]])
    if vel and loop:
        v = -np.mean(vel, axis=0); tr = math.degrees(math.atan2(v[0], v[1])); r["travelYaw"] = round(tr, 1)
        kn = [k for f in F for k in f["knees"]]
        r["kneeVsTravelDeg"] = round(max(abs(wrap(k - tr)) for k in kn), 1) if kn else None
        r["pelvisOffTravelDeg"] = round(float(np.mean([abs(wrap(p - tr)) for p in pe])), 1)
        sep = [float(np.linalg.norm((f["P"]["LeftFoot"] - f["P"]["RightFoot"])[[0, 2]])) for f in F]
        toe = [float(np.linalg.norm((f["P"]["LeftToeBase"] - f["P"]["RightToeBase"])[[0, 2]])) for f in F]
        r["feetMinSeparationCm"] = {"ankles": round(min(sep), 1), "toes": round(min(toe), 1)}
    if loop:
        seam = {}
        for bd, names in BANDS.items():
            st = [float(np.mean([np.linalg.norm(F[(i + 1) % len(F)]["P"][n] - F[i]["P"][n]) for n in names])) for i in range(len(F))]
            inner, last = st[:-1], st[-1]
            seam[bd] = {"seam": round(last, 2), "mean": round(float(np.mean(inner)), 2), "max": round(max(inner), 2), "seamOverMean": round(last / float(np.mean(inner)), 2)}
        r["seamPoseCmPerFrame"] = seam
    if name.startswith("Blink"):
        hy = [f["P"]["Hips"][1] - I["P"]["Hips"][1] for f in F]; at = [t / rate for t in ts]
        pre = [(a, h) for a, h in zip(at, hy) if a < .18]
        deep = min(range(len(pre)), key=lambda i: pre[i][1])
        start = next(i for i, (a, h) in enumerate(pre) if h < -1.0)
        r["blinkCrouch"] = {"launchDepthCm": round(pre[deep][1], 1), "launchCrouchFrames": deep - start + 1, "framesBelowIdleMinus2CmBeforeHidden": sum(1 for a, h in pre if h < -2),
                            "landingDepthCm": round(min(h for a, h in zip(at, hy) if a >= .34), 1),
                            "hipsVsIdleCmPerGameFrame": [round(h, 1) for h in hy], "gameFrameTimes": [round(a, 3) for a in at]}
        echo = {}
        for k, tc in zip(("departure", "arrival"), ECHO):
            e = frame(g, g.sample(tc)[0]); echo[k] = {"clipSeconds": tc, "hipsVsIdleCm": round(e["P"]["Hips"][1] - I["P"]["Hips"][1], 1),
                                                      "chestYaw": round(e["chest"], 1), "pelvisYaw": round(e["pelvis"], 1)}
        r["afterimagePoses"] = echo
        rs = np.array(c["root_translation_samples_cm"]); rr = c["root_sample_rate"]
        def root(tc):
            u = min(len(rs) - 1, tc * rr); i = int(u); j = min(i + 1, len(rs) - 1); return rs[i] * (1 - (u - i)) + rs[j] * (u - i)
        vis = [float(np.linalg.norm(root(min(T, tc + rate / 30)) - root(tc))) for tc in ts if tc + rate / 30 <= HIDDEN[0] + 1e-6 or tc >= HIDDEN[1] - 1e-6]
        r["rootTravelMeshCm"] = {"total": round(float(np.linalg.norm(rs[-1])), 1), "maxVisibleStep": round(max(vis) if vis else 0, 3), "gameCmApprox": round(float(np.linalg.norm(rs[-1])) * 2.44, 1)}
    if name == "RollAttack":
        rows = []
        for fi in range(33, 52):
            tc = min(T, fi / 30 * rate); f = frame(g, g.sample(tc)[0]); rows.append((fi, tc, f))
        feet = {}
        for s in ("Left", "Right"):
            floor = min(min(x[2]["P"][s + "Foot"][1] for x in rows), 1e9)
            feet[s] = [{"f": fi, "dxzCm": round(float(np.linalg.norm((f["P"][s + "Foot"] - p["P"][s + "Foot"])[[0, 2]])), 1),
                        "liftCm": round(f["P"][s + "Foot"][1] - floor, 1)} for (fi, tc, f), (_, _, p) in zip(rows[1:], rows[:-1])]
        r["rollExitFeet"] = feet
        r["bladePitchF33to51"] = {fi: round(f["pitch"], 1) for fi, tc, f in rows}
        p40 = [f["pitch"] for fi, tc, f in rows if 40 <= fi <= 50]
        r["bladePitchF40to50"] = {"min": round(min(p40), 1), "max": round(max(p40), 1), "maxRiseBetweenFrames": round(max(0, max(b - a for a, b in zip(p40, p40[1:]))), 1)}
    if name.startswith("BackpedalGuard"):
        cov = [helmet_cover(f) for f in F]
        r["guard"] = {"handMinusChestYCm": [round(min(f["handMinusChestY"] for f in F), 1), round(max(f["handMinusChestY"] for f in F), 1)],
                      "handMinusHipsYCm": [round(min(f["handMinusHipsY"] for f in F), 1), round(max(f["handMinusHipsY"] for f in F), 1)],
                      "helmetCoveredFractionMax": round(max(c_[0] for c_ in cov), 3), "bladeFrontalAngleFromVerticalDeg": [round(min(c_[1] for c_ in cov), 1), round(max(c_[1] for c_ in cov), 1)],
                      "helmetToBladeAxisCm": round(min(c_[2] for c_ in cov), 1), "bladePitch": [round(min(f["pitch"] for f in F), 1), round(max(f["pitch"] for f in F), 1)]}
    return r


def rate_of(c):
    if c["loop"]:
        n = c["nominal_speed_cm_per_second"]
        cap = 100.0 if c["name"].startswith("Backpedal") else (min(580, n * 1.1) if "Run" in c["name"] else min(240, n * 1.2))
        return cap / n
    return c["gameplay_play_rate"]


def pixels(mp4):
    """Critic's seam method: mean abs pixel diff of consecutive frames on the knight crop of each 360 px panel,
    rows 60-275 split into head/chest (<159), hips/sword (159-209) and legs/feet (>=209), columns centre +/-100."""
    if not mp4.exists():
        return None
    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", str(mp4)],
                                     capture_output=True, text=True, check=True).stdout)["streams"][0]
    W, H = info["width"], info["height"]
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp4), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3).astype(np.float32)
    cols = np.concatenate([np.arange(c - 100, c + 100) for c in (180, 540, 900)])
    bands = {"headChest": (60, 159), "hipsSword": (159, 209), "legsFeet": (209, 275), "all": (60, 275)}
    out = {}
    for bd, (a, b) in bands.items():
        crop = fr[:, a:b][:, :, cols]
        st = [float(np.abs(crop[(i + 1) % len(crop)] - crop[i]).mean()) for i in range(len(crop))]
        inner, last = st[:-1], st[-1]
        out[bd] = {"seam": round(last, 2), "mean": round(float(np.mean(inner)), 2), "max": round(max(inner), 2)}
    return out


def first_last_pixels(mp4, idle_mp4):
    if not (mp4.exists() and idle_mp4.exists()):
        return None
    def frames(p):
        info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", str(p)],
                                         capture_output=True, text=True, check=True).stdout)["streams"][0]
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
        return np.frombuffer(raw, np.uint8).reshape(-1, info["height"], info["width"], 3).astype(np.float32)
    a, i = frames(mp4), frames(idle_mp4)
    cols = np.concatenate([np.arange(c - 100, c + 100) for c in (180, 540, 900)])
    d = lambda x, y: round(float(np.abs(x[60:275][:, cols] - y[60:275][:, cols]).mean()), 2)
    return {"firstVsIdle": d(a[0], i[0]), "lastVsIdle": d(a[-1], i[0]), "idleNoise": d(i[0], i[-1]) if len(i) > 1 else None}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


if __name__ == "__main__":
    out = Path(sys.argv[1])
    p3 = {c["name"]: c for c in json.loads(PLAN3.read_text())["clips"]}; p2 = {c["name"]: c for c in json.loads(PLAN2.read_text())["clips"]}
    rows = {}
    for name in p3:
        rows[name] = {"r3": measure(p3[name], "r3"), "r2": measure(p2[name], "r2") if name in p2 else None}
        for lab in ("r3", "r2"):
            px = pixels(REVIEW / ("%s-%s.mp4" % (lab, name)))
            if px and rows[name][lab]:
                rows[name][lab]["seamPixels"] = px
        if name.startswith("Blink"):
            idle = REVIEW / ("r3-Idle%s.mp4" % ("TwoHand" if "TwoHand" in name else ""))
            for lab in ("r3", "r2"):
                fl = first_last_pixels(REVIEW / ("%s-%s.mp4" % (lab, name)), idle)
                if fl and rows[name][lab]:
                    rows[name][lab]["firstLastPixelsVsIdle"] = fl
        print(name, json.dumps({k: (v or {}).get("seamPoseCmPerFrame") or (v or {}).get("blinkCrouch", {}).get("launchDepthCm") for k, v in rows[name].items()}), flush=True)
    # inherited, protected clips: measured for reference only (unchanged files)
    prot = {}
    for name in ("StrafeLeft", "StrafeLeftTwoHand"):
        prot[name] = measure(p2[name], "r2 (unchanged)")
        px = pixels(REVIEW / ("r3-%s.mp4" % name))
        if px:
            prot[name]["seamPixels"] = px
    digest_before = ROOT / "docs/knight-complete-20261028/data/round3-protected-sha256-before.txt"
    ident = {}
    if digest_before.exists():
        for line in digest_before.read_text().splitlines():
            h, p = line.split(None, 1); now = sha(ROOT / p) if (ROOT / p).exists() else None
            ident[p] = {"before": h, "after": now, "identical": h == now}
    out.write_text(json.dumps({"definitions": __doc__, "idle": {k: {"hipsYcm": round(float(v["P"]["Hips"][1]), 1), "anklesCm": round(v["ankles"], 1), "bladePitch": round(v["pitch"], 1)} for k, v in IDLE.items()},
                               "clips": rows, "protectedReference": prot, "byteIdentical": ident,
                               "byteIdenticalAll": all(v["identical"] for v in ident.values()) if ident else None}, indent=1) + "\n")
    print("WROTE", out)
