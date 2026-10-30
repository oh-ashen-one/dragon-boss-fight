# blendproof: engine footage and numbers for the knight's blend, blink and roll fixes

Replay mode `blendproof` (added 2026-10-29) answers critique round 2, items 2 and 6, which failed as UNPROVEN because no
engine footage existed:

1. the sword stays socketed to the hand during pose blends (`-VeyrNoWeaponGripLock` is the "before" flag);
2. the blink root carry and foot lock (no planted-foot skate outside the blink's hidden window);
3. root motion carries the RollAttack dive and roll with no hovering or skating feet.

It is input-only like every other replay mode. It never writes health, clocks or positions; the only non-input
effects are a passive boss, a fixed camera and the optional checker floor, all of them test-only.

## How to run

```bash
cd /Users/midir/veyr-knight-20261028
# uncooked editor-built game (needs a current `python3 tools/unreal/build.py --engine "/Users/Shared/Epic Games/UE_5.8"`)
python3 tools/unreal/run_native.py --engine "/Users/Shared/Epic Games/UE_5.8" \
  --gpu-slot ~/.cache/gpu-slot/bin/gpu_slot.sh --mode blendproof --video-fps 15 --slot-wait-seconds 3600
# packaged Shipping app (the intended proof target)
python3 tools/unreal/run_native.py --app <Veyr-Mac-Shipping.app> \
  --gpu-slot ~/.cache/gpu-slot/bin/gpu_slot.sh --mode blendproof --video-fps 15 --slot-wait-seconds 3600
# the "before" run for the sword gate: same thing plus
  --extra-arg -VeyrNoWeaponGripLock
# encode the videos (per sequence plus one whole-run file)
python3 tools/unreal/blendproof_encode.py Evidence/native-blendproof-<stamp> [--delete-frames]
```

`run_native.py` adds `-VeyrProofFloor` automatically for this mode (`--no-proof-floor` turns it off) and accepts
single `-Veyr*` flags through repeatable `--extra-arg`. The run queues on the shared GPU slot like every other mode,
so it waits while `~/.cache/gpu-slot/STREAMING` says 0 slots. Nothing here opens a focused window or an OS dialog.

## What the mode does

Lock-on is held and the boss is passive (`AVeyrDragon::bProofPassive`: the boss takes its "not yet engaged" branch,
breathing and gazing but never attacking). The knight is driven through nine sequences. Each sequence is
setup (grip, stamina at least 85, walk to the sequence start so the move is centred on the start point, 0.9 s still),
then 1.3 s idle, the action, and at least 1.5 s idle again, so the blend in and the blend out are both on film.

| # | Sequence | Input | Camera (azimuth from the boss axis) |
|---|---|---|---|
| 1 | `StrafeLeft_1H` | idle, hold left 2.4 s, idle | three-quarter front-right (35 deg) |
| 2 | `StrafeRunLeft_1H` | idle, Shift + left 1.6 s, idle | 35 deg |
| 3 | `BlinkLeft_1H` | idle, blink left, idle | 35 deg |
| 4 | `StrafeRight_2H` | two-hand grip, idle, right 2.4 s, idle | 35 deg |
| 5 | `BlinkRight_2H` | two-hand grip, idle, blink right, idle | 35 deg |
| 6 | `RollAttack_1H` | roll toward the boss, primary attack at 0.2 s into the roll, idle | side-on (90 deg) |
| 7 | `BackpedalGuard_1H` | idle, hold back 2.4 s, idle | side-on (90 deg) |
| 8 | `StrafeRunRight_1H` | idle, Shift + right 1.6 s, idle | 35 deg |
| 9 | `BlinkRight_1H` | idle, blink right, idle | 35 deg |

**Camera.** An engine `ACameraActor` becomes the view target. It sits 580 cm from the knight at 190 cm height, FOV 45,
orientation fixed in the world, and follows the capsule with a 4/s exponential lag, so a blink or sprint carries the
knight across the frame and the floor scrolls under the feet. Whole knight and sword are in frame.

**Floor.** `-VeyrProofFloor` lays 25 cm light cells on a checker over +/-16 m of the floor (one
`UInstancedStaticMeshComponent` of the engine `Cube` with a `BasicShapeMaterial` instance, 4 mm thick, 6 mm above the
walking plane, no collision, no shadow). It needs no new asset, so it works in the Shipping package. It is applied only
in this mode and only with the flag.

**Screenshots.** One PNG at every pose-blend midpoint (the first frame at alpha >= 0.5 of each new pose transition,
named `bp_NN_<sequence>_blend_<from>_to_<to>_aXX`), one at the start and end of each sequence and one mid-cycle.
The screenshot request carries the sampled blend state in `screenshots[].stateAtRequest.blendProofState`.

**Video.** `--video-fps 15` is the highest native cadence (`encode_video.py` accepts 1 to 15). `blendproof_encode.py`
cuts one MP4 per sequence plus one whole-run MP4 by game time, encodes with `encode_video.py` (variable frame rate from the
real capture timestamps), then resamples to a constant 30 fps (held frames stay held; nothing is interpolated) as H.264
and burns in a data line: sequence, phase, clip, blend alpha, sword-to-hand excess, hand-space error, worst planted-foot
travel of the nearest recorded game frame.

## Evidence

`Evidence/native-blendproof-<stamp>/unreal-blendproof-<stamp>-<id>/`

* `evidence.json` -> `blendProof` (`setup`, `gateThresholds`, one object per sequence) and the ordinary replay fields.
* `blendproof-frames.jsonl`: one line per game frame of every recorded sequence: game time `t`, `dt`, `clip`, `blendFrom`,
  `blendAlpha`, `blending`, `transition` serial, `action`, `actionElapsed`, `blinkHidden`, capsule world position and
  per-frame travel, both toe-base and both ankle world positions, their height above the floor, planted flags and per-frame
  travel, sword world position, right-hand bone world position, the sword in hand space, `swordToHandCm`,
  `swordExcessCm`, `swordHandSpaceErrorCm`.
* `native.log`: one `VEYR_GATE blendproof ...` line per sequence and a `... summary` line.
* `native-video/frames.jsonl` plus PNGs, `frame-*-bp_*.png` screenshots, `blendproof-media/*.mp4`.

## The gate lines

```
VEYR_GATE blendproof seq=N name=<sequence> PASS|FAIL swordExcessMaxCm=.. swordHandSpaceErrMaxCm=.. swordRawHandToGripCm=min..max
  footSlideMaxCmPerSecond=.. footSlideSteadyCmPerSecond=.. footSlideTransitionCmPerSecond=.. legacyFootSlideMaxCmPerFrame=..
  [travel fields] frames=.. maxFrameSeconds=.. reason=..
```

A sequence passes only when every item below holds. Frame timing under GPU load is long (frames up to 0.4 s), so the
foot gate is a speed (cm/s) since 2026-10-30; the sword gate stays in cm.

* **Sword (`swordExcessMaxCm`, `swordHandSpaceErrMaxCm`, limit 2 cm).** The distance from the sword's actual world
  position (the visible mesh) to the right-hand bone is about 14.9 cm in every steady pose, because the grip
  socket is not at the wrist; a raw "<= 2 cm to the hand bone" can never hold and is reported as
  `swordRawHandToGripCm` for reference. The gate measures what a blend adds instead:
  * Inside a pose blend (alpha < 1): `swordExcessMaxCm` is the distance outside the range spanned by the hand-to-grip
    distance of the last frame before the blend and the first frame after it (the endpoint poses' own grips), the same
    definition as `round2-handslip.json`; `swordHandSpaceErrMaxCm` is the distance between the sword's hand-space position
    and the expected interpolation between those two endpoints at the current alpha.
  * Outside blends: the deviation of the hand-to-grip distance from that clip's own median.
  The blink's vanish window (sword hidden) is skipped; the endpoints are the nearest frames with a visible sword.
* **Planted foot (`footSlideMaxCmPerSecond`, limit 60 cm/s = 2 cm per 1/30 s; rework 2026-10-30, see
  `blendproof-footgate-diagnosis.md`).** A foot is planted in a frame when its toe-base AND ankle are both within 2.5 cm
  of a contact reference: per clip, foot and bone, the 10th percentile of that clip's unblended heights in the sequence,
  never above the idle stance (while blending, the looser of source and target). Slide is the horizontal world travel
  of the foot (max of toe and ankle) divided by elapsed game time, accumulated over a contiguous planted window of at
  least 1/30 s, so capture hitches do not change the number. Pairs touching the blink's hidden window [0.18, 0.34) s,
  zero-dt pairs and capsule teleports (> 2500 cm/s) break the window. The worst window is labelled `steady` or
  `transition` (a pose blend inside the window); idle-to-move and move-to-idle blends are gated, since a foot dragged
  by the capsule or swept by a crossfade is exactly the skate this tool exposes. The old idle-only, per-bone, cm-per-frame
  figure is still reported as `legacy*` for comparison.
* **Travel.** Strafe/backpedal: capsule net travel >= 60 cm. Blink: >= 100 cm root carry (`blinkCarryCm`,
  `hiddenWindowCarryCm` is the part inside the hidden window). RollAttack: the roll must upgrade to RollAttack, and the
  dive-plus-roll net travel (`rollTravelCm`) must be above 1 cm; `diveCm`, `rollCm`, `slashCm`, `exitCm` are the net capsule
  travel per phase (dive to 0.17 s, roll to the end of the Roll prefix, slash to the end of the strike window, exit after)
  and `rollSlide` / `exitSlide` are the worst planted-foot slide (cm/s) in those phases.
* **Completion.** No setup or action timeout and the expected clip seen in at least two frames.

The last line, `VEYR_GATE blendproof summary passed=N/9`, decides the mode's pass flag.

## Limits

* Frame times are whatever the machine gives; at low frame rates a blend is only one to three frames and the
  midpoint screenshot is the first frame past alpha 0.5.
* Planted detection uses bone height, so a foot that skates while slightly lifted is not counted.
* Foot lock is measured on the bones of the evaluated pose, not on the mesh surface.
* The proof boss does not attack, so none of this covers hit reactions.
