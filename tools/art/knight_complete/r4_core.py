"""Knight fix round 4 (2026-10-29): pure-python math shared by build_round4.py (inside Blender) and measure_round4.py
(plain CPython, no bpy). No bpy, no numpy: points are 3-tuples / lists.

Conventions (Blender armature space, the one the builder works in): +X = knight's left, -Y = boss / forward, +Z = up.
Yaw (deg) of a horizontal direction: 0 = boss, + toward the knight's left (atan2(x, -y)). glTF mesh space (the measure
side) is (x, y_up, z_boss); to_blender() maps it so every function below sees one convention.
Game cm = rig m x 240."""
import math

CM = 240.0

# ------------------------------------------------------------------------------------------------ round-4 tunables
# sprint swing-plane fix
PEL_MAX = 45.0               # pelvis yaw off the boss (deg), as round 3's solver cap
SWING_GAIN = 1.0             # fraction of (pelvis - travel) the swing offset turns (prototype: 1.0 -> kick plane 46 deg)
FOOT_K = .5                  # stance foot turn = FOOT_K x hip turn (round 3)
FOOT_SWING_K = 1.0           # swing foot additionally turns with the leg plane
POLE_STANCE, POLE_SWING = .6, 1.0   # knee pole weight on pelvis-forward (rest = sourced knee direction)
GATE_PLANE_DEG, GATE_RATIO, GATE_STANCE_CM = 52.0, .80, 1.0
# roll attack
JOIN_T = 1.0                 # root prefix end (normalize root_prefix 1.0): root motion stops here, pose carries the rest
JOIN_DECEL_S = .17           # clip s (4 rendered frames at rate 1.282) over which the world hips velocity ramps down
                             # (CPU prediction on the v5 data: 13.7, 10.8, 5.4, 1.2 cm/frame vs r3 13.9, 4.0, 0.8; attack offset ~15 cm)
OUTRO_START = 1.62           # clip s (after the damage window [1.36, 1.576] and the arm recovery start 1.60)
SETTLE_HOLD_S = .13          # hips horizontally at rest for the last ~3 rendered frames
GETUP_T = .62                # contact cleanup starts when the tumble ends (feet first down, rendered f15)
LIFT_MIN_CM = 5.0
CONTACT_H_CM = 2.5           # toe within this of the local floor (lowest toe height within +-0.3 s)
TOE_FLOOR_CM = 3.3           # idle left toe-joint height: toes below it are pitched up (attack source sinks them ~3 cm)
CONTACT_V_CMS = 100.0        # and horizontal world speed below this (game cm per clip second) = contact
ROLL_RATE = 1.0 / .78        # RollAttack gameplay_play_rate (v030q); checked against the plan in --dry



# ------------------------------------------------------------------------------------------------ small helpers
def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def smooth(x):
    x = clamp(x); return x * x * (3 - 2 * x)


def smoother(x):
    x = clamp(x); return x * x * x * (x * (6 * x - 15) + 10)


def seg(t, keys):
    """Piecewise smoothstep through (time, value) keys (same as build_round3.seg)."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * smooth((t - t0) / (t1 - t0))
    return keys[-1][1]


def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def mul(a, k):
    return tuple(x * k for x in a)


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm(a):
    return math.sqrt(dot(a, a))


def unit(a):
    n = norm(a); return tuple(x / n for x in a) if n > 1e-12 else (0.0, 0.0, 0.0)


def to_blender(p):
    """glTF mesh space (x left, y up, z boss) -> Blender armature space (x left, y = -boss, z up)."""
    return (p[0], -p[2], p[1])


def yaw(v):
    """Yaw (deg) of a direction's horizontal part: 0 = boss (-Y), + toward the knight's left (+X)."""
    return math.degrees(math.atan2(v[0], -v[1]))


def wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def fold90(a):
    """Yaw of an undirected horizontal line, folded into (-90, 90]."""
    a = wrap(a)
    if a > 90:
        a -= 180
    elif a <= -90:
        a += 180
    return a


def rot_vertical(p, pivot, deg):
    """Rotate point p about the vertical (Z) axis through pivot by deg (yaw convention: + turns boss toward left)."""
    a = math.radians(deg); c, s = math.cos(a), math.sin(a)
    x, y = p[0] - pivot[0], p[1] - pivot[1]
    return (pivot[0] + c * x - s * y, pivot[1] + s * x + c * y, p[2])


def facing_of_line(left, right):
    """Facing yaw of a left-minus-right joint line (hip line, shoulder line), as build_round3.yaw_line."""
    L = sub(left, right)
    return yaw((L[1], -L[0], 0.0))


# ------------------------------------------------------------------------------------------------ sprint strafes
def swing_weights(ankle_z, toe_z, ankle_lo=2.0 / CM, ankle_span=8.0 / CM, toe_lo=1.0 / CM, toe_span=5.0 / CM, cyclic=True, passes=3):
    """Per-frame swing weight of one foot: 0 while the toe is on its stance level (so a planted toe never moves), 1 once
    both the ankle (>= ankle_lo + ankle_span above its lowest) and the toe are clear; smoothed [1 2 1] `passes` times."""
    a0, t0 = min(ankle_z), min(toe_z)
    w = [min(smooth((a - a0 - ankle_lo) / ankle_span), smooth((t - t0 - toe_lo) / toe_span)) for a, t in zip(ankle_z, toe_z)]
    n = len(w)
    for _ in range(passes):
        if cyclic:
            w = [(w[(i - 1) % n] + 2 * w[i] + w[(i + 1) % n]) / 4 for i in range(n)]
        else:
            w = [(w[max(i - 1, 0)] + 2 * w[i] + w[min(i + 1, n - 1)]) / 4 for i in range(n)]
    return w


def travel_yaw(feet_paths, fps):
    """Body travel yaw from the stance (lowest) foot's horizontal velocity, reversed. feet_paths: {side: [(x,y,z)...]}."""
    sides = list(feet_paths); n = len(feet_paths[sides[0]]); vx = vy = 0.0; floor = min(p[2] for s in sides for p in feet_paths[s])
    for i in range(n - 1):
        s = min(sides, key=lambda k: feet_paths[k][i][2])
        if feet_paths[s][i][2] - floor > 2.0 / CM:
            continue
        d = sub(feet_paths[s][i + 1], feet_paths[s][i]); vx -= d[0] * fps; vy -= d[1] * fps
    return yaw((vx, vy, 0.0)) if abs(vx) + abs(vy) > 1e-9 else None


def leg_plane(H, K, A):
    """Leg (hip-knee-ankle) plane: folded yaw of its horizontal trace (0 = the leg swings toward/away from the boss,
    +-90 = frontal plane), knee bend (deg), and the shin's horizontal spans in the front view (|x|) and side view (|y|)."""
    n = cross(sub(K, H), sub(A, K))
    trace = cross(n, (0.0, 0.0, 1.0))
    plane = fold90(yaw(trace)) if norm(trace[:2] + (0.0,)) > 1e-9 else float("nan")
    th, sh = sub(K, H), sub(A, K)
    bend = math.degrees(math.acos(clamp(dot(th, sh) / max(1e-12, norm(th) * norm(sh)), -1.0, 1.0)))
    return {"planeYaw": plane, "kneeBend": bend, "shinFront": abs(sh[0]), "shinSide": abs(sh[1])}


def full_kick(rows):
    """rows: per-frame leg_plane dicts of one leg; returns the full-kick frame (max knee bend) and its numbers."""
    i = max(range(len(rows)), key=lambda k: rows[k]["kneeBend"])
    r = rows[i]
    return {"frame": i, "planeYaw": round(r["planeYaw"], 1), "kneeBend": round(r["kneeBend"], 1),
            "shinFrontCm": round(r["shinFront"] * CM, 1), "shinSideCm": round(r["shinSide"] * CM, 1),
            "sideOverFront": round(r["shinSide"] / max(r["shinFront"], 1e-9), 2)}


def two_bone_knee(H, A, a, b, pole, reach=.98):
    """Analytic knee position for thigh a / shin b reaching from H toward A, bending toward pole (direction)."""
    d = min(max(norm(sub(A, H)), 1e-6), (a + b) * reach)
    u = unit(sub(A, H)); v = sub(pole, mul(u, dot(pole, u)))
    if norm(v) < 1e-9:
        v = (0.0, -1.0, 0.0)
    v = unit(v)
    ca = clamp((a * a + d * d - b * b) / (2 * a * d), -1.0, 1.0)
    return add(H, mul(add(mul(u, ca), mul(v, math.sqrt(max(0.0, 1 - ca * ca)))), a))


# ------------------------------------------------------------------------------------------------ paths (roll attack)
def hermite(p0, m0, p1, m1, u):
    u2, u3 = u * u, u * u * u
    h00, h10, h01, h11 = 2 * u3 - 3 * u2 + 1, u3 - 2 * u2 + u, -2 * u3 + 3 * u2, u3 - u2
    return tuple(h00 * a + h10 * b + h01 * c + h11 * d for a, b, c, d in zip(p0, m0, p1, m1))


def reprofile_velocity(path, i0, i1):
    """Re-integrate a path over [i0, i1] with its per-frame velocity blended smoothly (smoothstep) from the velocity
    entering i0 to the velocity leaving i1, so a sudden stop becomes a ramp. Returns (new points for i0..i1, offset at
    i1 = new - old, to be carried by every later frame)."""
    v0 = sub(path[i0], path[i0 - 1]); v1 = sub(path[i1 + 1], path[i1]) if i1 + 1 < len(path) else sub(path[i1], path[i1 - 1])
    out = [path[i0]]
    for k in range(i0 + 1, i1 + 1):
        w = smooth((k - i0) / float(i1 - i0))
        out.append(add(out[-1], add(mul(v0, 1 - w), mul(v1, w))))
    return out, sub(out[-1], path[i1])


def settle_path(p_start, v_start, p_end, n):
    """n+1 points from p_start (entering with per-frame velocity v_start) to p_end with zero end velocity (cubic Hermite)."""
    return [hermite(p_start, mul(v_start, n), p_end, (0.0, 0.0, 0.0), k / float(n)) for k in range(n + 1)]


def contact_runs(points, toe_z, floor_z, fps, h_tol=None, v_tol=None, min_len_s=.06, merge_gap_s=.04, floor_window_s=.30):
    """Contact intervals [(start, end)] of one foot: toe within h_tol of the floor and horizontal speed below v_tol (rig
    m per clip s, 3-frame centred difference); gaps shorter than merge_gap_s merged, runs shorter than min_len_s dropped.
    floor_z None = local floor: the lowest toe height within +-floor_window_s (the roll and the slash sources stand on
    different floor levels, so one absolute floor misses contacts)."""
    h_tol = CONTACT_H_CM / CM if h_tol is None else h_tol
    v_tol = CONTACT_V_CMS / CM if v_tol is None else v_tol
    n = len(points); on = []; win = max(1, int(round(floor_window_s * fps)))
    for i in range(n):
        a, b = points[max(i - 1, 0)], points[min(i + 1, n - 1)]
        dt = (min(i + 1, n - 1) - max(i - 1, 0)) / float(fps)
        sp = math.hypot(b[0] - a[0], b[1] - a[1]) / dt if dt > 0 else 0.0
        fl = floor_z if floor_z is not None else min(toe_z[max(0, i - win):min(n, i + win + 1)])
        on.append(toe_z[i] - fl < h_tol and sp < v_tol)
    runs, i = [], 0
    while i < n:
        if on[i]:
            j = i
            while j + 1 < n and on[j + 1]:
                j += 1
            runs.append([i, j]); i = j + 1
        else:
            i += 1
    merged = []
    for r in runs:
        if merged and r[0] - merged[-1][1] - 1 <= merge_gap_s * fps:
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    return [(a, b) for a, b in merged if (b - a + 1) >= min_len_s * fps]


def contact_targets(points, runs, lift_min, first=None, last=None, lock_z=True):
    """Per-frame ankle targets for one foot over [first, last]: locked at the run's first point while in contact
    (lock_z=False: horizontal lock only, the original height is kept so heel lift / toe roll survive); between two runs
    the original path is offset so it leaves the first lock and lands on the next one continuously, with a sine lift so
    the swing's peak clears at least lift_min above the straight line between the lock heights."""
    first = 0 if first is None else first; last = len(points) - 1 if last is None else last
    tg = {i: points[i] for i in range(first, last + 1)}
    locks = [(a, b, points[a]) for a, b in runs]

    def held(p, i):
        return p if lock_z else (p[0], p[1], points[i][2])
    for a, b, p in locks:
        for i in range(max(a, first), min(b, last) + 1):
            tg[i] = held(p, i)
    for (a0, b0, p0), (a1, b1, p1) in zip(locks, locks[1:]):
        s0, s1 = b0, a1                                 # swing frames are (b0, a1)
        if s1 - s0 < 2:
            continue
        e0, e1 = sub(held(p0, s0), points[s0]), sub(held(p1, s1), points[s1])
        z0, z1 = points[s0][2] + e0[2], points[s1][2] + e1[2]
        peak = max(points[i][2] - (z0 + (z1 - z0) * (i - s0) / (s1 - s0)) for i in range(s0, s1 + 1))
        extra = max(0.0, lift_min - peak)
        for i in range(s0 + 1, s1):
            u = (i - s0) / float(s1 - s0); w = smooth(u)
            q = add(points[i], add(mul(e0, 1 - w), mul(e1, w)))
            tg[i] = (q[0], q[1], q[2] + extra * math.sin(math.pi * u))
    # a swing that runs off either end keeps the original path, offset to stay continuous with the adjacent lock
    if locks:
        a, b, p = locks[0]
        if a > first:
            e = sub(held(p, a), points[a])
            for i in range(first, a):
                tg[i] = add(points[i], mul(e, smooth((i - first) / float(max(1, a - first)))))
        a, b, p = locks[-1]
        if b < last:
            e = sub(held(p, b), points[b])
            for i in range(b + 1, last + 1):
                tg[i] = add(points[i], mul(e, 1 - smooth((i - b) / float(max(1, last - b)))))
    return tg


# ------------------------------------------------------------------------------------------------ blinks
HIDDEN = (.207, .391)        # clip seconds (game 0.18-0.34 s of action time at rate 1.15)
BLINK_T = 0.70
BLINK_RATE = 1.15
# Round 4 keys (clip seconds). Launch crouch bottom moved to 0.115 (rendered frame 3) so frames 4 and 5 are two visible
# push frames before the hidden window (0.207); gain 0.60 -> 0.75 deepens the crouch. Landing arrives at a shallower
# crouch (frame 4 of the source squat) and compresses to the full squat by 0.46 (impact), then rises to idle by 0.66;
# the cycles stage blends the last 0.20 s into the idle's own motion (no hold).
BLINK_KEYS_R4 = {
    "crouchFrame": [(0, 0.0), (.115, 9.0), (.207, 3.5), (.391, 4.0), (.46, 9.0), (.66, 0.0)],
    "crouchGain": [(0, .75), (.70, .75)],
    "leanDeg": [(0, 0.0), (.115, -3.0), (.207, 20.0), (.391, -12.0), (.46, -6.0), (.66, 0.0)],
    "shiftM": [(0, 0.0), (.115, -.020), (.207, .050), (.391, .030), (.46, .015), (.66, 0.0)],
    "pelvisYawDeg": [(0, 0.0), (.115, 6.0), (.207, 20.0), (.391, 10.0), (.66, 0.0)],
    "armLead": [(0, 0.0), (.115, .30), (.207, 1.0), (.391, -.8), (.66, 0.0)],
}
BLINK_TAIL = (.50, .70)      # clip seconds over which the blink blends (smootherstep) into the animated idle


def blink_params(t, keys=BLINK_KEYS_R4):
    return {k: seg(t, v) for k, v in keys.items()}


def rendered_times(T=BLINK_T, rate=BLINK_RATE, fps=30):
    """Clip times of the rendered (even-sampled action) frames: n+1 frames ending exactly on T."""
    n = max(1, int(round(T / rate * fps)))
    return [i * T / n for i in range(n + 1)]


def idle_tail_time(t, T, rate, idle_T, idle_rate=1.0):
    """Idle clip time to blend toward at blink/roll clip time t: the idle runs (at idle_rate) so that it reaches its
    frame 0 (== idle_T on a closed loop) exactly at the clip end T, in game time (clip seconds / rate)."""
    tau = idle_T - (T - t) / rate * idle_rate
    return tau % idle_T if tau < idle_T - 1e-9 else 0.0


def blink_timeline():
    """Per rendered frame: clip time, visibility and the key values (dry-run report; crouch depth is measured later)."""
    out = []
    for i, t in enumerate(rendered_times()):
        p = blink_params(t)
        out.append({"frame": i, "clipS": round(t, 4), "hidden": HIDDEN[0] <= t < HIDDEN[1], "crouchFrame": round(p["crouchFrame"], 2),
                    "crouchGain": p["crouchGain"], "leanDeg": round(p["leanDeg"], 1), "shiftCm": round(p["shiftM"] * CM, 1),
                    "tailIdleWeight": round(smoother((t - BLINK_TAIL[0]) / (BLINK_TAIL[1] - BLINK_TAIL[0])), 3)})
    return out
