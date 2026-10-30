"""Knight fix round 5 (2026-10-30): pure-python tunables and step shapes shared by build_round5.py (inside Blender) and
measure_round5.py (plain CPython). Clip seconds unless noted; RollAttack rate 1.282 (rendered frame k <-> clip k*0.04274 s).
Game cm = rig m x 240."""
import math

CM = 240.0


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def smooth(x):
    x = clamp(x); return x * x * (3 - 2 * x)


# ------------------------------------------------------------------------------------------------ roll attack
# The round-4 composition is kept up to the strike (roll, join ramp + 15 cm carry, slash, damage window [1.36, 1.576]).
# Round 5 replaces (1) the get-up/lunge foot cleanup with an explicit footstep plan and (2) the recovery (outro, arm
# recovery, hips settle, two quick steps) with one slower recovery that shares a single smoothstep progress.
REC_START = 1.54             # recovery starts at the end of the follow-through (damage window ends 1.576; progress there 0.3 %)
REC_END = 2.17               # body, arm, blade and hips reach the idle target (rendered f36-f50.8; r4: a 4-frame pop at f41-45)
REC_RAMP = .28               # progress = ramped constant-velocity profile: velocity eases in over 28 %, out over the last 28 % (peak 1.39x mean, smoothstep 1.5x)
# footstep plan (clip s). Plants are fixed foot matrices (no slide); steps move the ankle only while it is lifted.
#   Right (rear) foot: lands from the roll straight onto its FINAL idle spot and stays there to the end
#   Left (front) foot: plants after the roll, one lifted lunge step to the lunge spot (lands with the strike), one lifted
#   step back to its final idle spot during the recovery
RIGHT_LEAD = (.52, .77)      # roll landing: the in-air path is offset so it touches down on the final spot
LEFT_LEAD = (.56, .643)
LEFT_L0_REF = .70            # source time of the post-roll plant
LEFT_L1_REF = 1.50           # source time of the lunge plant (the source slides the foot into it until 1.50)
STEPS_LEFT = (               # (start, end, lift game cm, horizontal from u, horizontal until u)
    (.98, 1.368, 11.0, .14, .84),     # lunge step: lands at rendered f32, with the strike (damage window 1.36)
    (1.64, 2.15, 14.0, .18, .82),     # recovery step back: horizontal only while the ankle is >= ~14 cm up
)
LIFT_RAMP = .22              # fraction of a step spent lifting (and setting down)
REACH = .99                  # hips drop so both ankle targets stay within 99 % of the leg length
DROP_SMOOTH_S = .08

# ------------------------------------------------------------------------------------------------ blinks
# Foot pass on the round-4 v6c blinks (no other channel changes): every 120 Hz key re-planted on the idle stance (the
# local-space resample in round 4 left 6-12 cm dips into the floor between the 30 Hz authoring keys: f0.14-0.16,
# 0.41-0.42 (the engine blend proof's BlinkLeft 0.38-0.40 s action-time pop), 0.54-0.56), plus a toe-off on the push frames:
# the heel rolls up about the planted toe joint (toes stay flat), trailing foot full, leading foot half.
TOE_OFF_DEG = [(0, 0.0), (.115, 0.0), (.207, 30.0), (.30, 30.0), (.391, 0.0)]   # hidden window 0.207-0.391
TOE_OFF_LEAD = .5


def seg(t, keys):
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * smooth((t - t0) / (t1 - t0))
    return keys[-1][1]


def step_shape(u, lo, hi, lift_cm, ramp=LIFT_RAMP):
    """Step at phase u in [0, 1]: (horizontal progress 0..1, lift in game cm). The ankle rises over [0, ramp], holds a
    plateau (plus a gentle 25 % arc) and sets down over [1 - ramp, 1]; horizontal progress is a smoothstep over [lo, hi],
    so there is no horizontal motion while the foot is near the ground."""
    h = smooth((u - lo) / (hi - lo))
    z = lift_cm * min(smooth(u / ramp), smooth((1 - u) / ramp)) + .25 * lift_cm * math.sin(math.pi * clamp(u))
    return h, z


def ramp_profile(x, r=None):
    """Position 0..1 for a velocity that rises (smoothstep-shaped) over [0, r], stays constant, and falls over [1-r, 1];
    peak velocity 1/(1-r) x the mean (smoothstep: 1.5x), zero velocity and acceleration-continuous ends."""
    r = REC_RAMP if r is None else r; x = clamp(x)
    I = lambda y: y ** 3 - y ** 4 / 2          # integral of smoothstep(0..y)
    tot = 1.0 - r
    if x < r:
        p = r * I(x / r)
    elif x <= 1 - r:
        p = r * .5 + (x - r)
    else:
        p = tot - r * I((1 - x) / r)
    return p / tot


def progress(t, t0=REC_START, t1=REC_END):
    return ramp_profile((t - t0) / (t1 - t0))
