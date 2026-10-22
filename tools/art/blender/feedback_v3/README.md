# Knight feedback revision 3 — 2026-10-21

**2026-10-21 owner decision (2):** Heal_Blender_v4 and WalkTwoHand_Blender_v5r2 (two-hand ready walk) approved as-is ("Heal and ready walk is approved."; 14 approved clips, hashes in `tools/art/blender/feedback/decisions.json`). Backpedal round 4 rejected. Pending: backpedal r5, run r5 (sword held up like a bat), heavy r3.

**2026-10-21 owner decision:** GuardReadyTwoHand_Blender_v3, StrafeLeft_Blender_v3 and StrafeRight_Blender_v3 approved as-is (hashes in `tools/art/blender/feedback/decisions.json`; 12 approved clips). Pending owner notes: Backpedal v3, HeavyAttackOneHand v3, Heal v3, Run, ready walk (WalkTwoHand v4).

The owner approved **WalkOneHand_Blender_v1** and requested six final corrections,
then a stop. No dragon work or Unreal integration is included. Death, stagger and
the six earlier approved Blender actions remain unchanged; nine approval hashes
were verified. Jump and one-hand guard stay removed.

| Candidate | Native Blender change | Timing |
|---|---|---|
| GuardReadyTwoHand v3 | Low two-handed ready pose with the face exposed; rapid raise, slight settle, held face-covering guard | 0.08 s idle + 0.22 s raise; 0.7 s total |
| StrafeLeft / StrafeRight v3 | Anticipation, lateral hop, hidden transit, landing, idle recovery | 0.7 s; hidden 0.18–0.34 s; root moves ±1.0 source unit |
| Backpedal v3 | Alternating planted steps, hip weight transfer, torso/head counterrotation and raised ready arms | 2.4 s; .36 source unit backward |
| HeavyAttackOneHand v3 | Right hand alone carries the sword; free left arm moves outward/back as a counterbalance; neutral wrist relationship | 1.4 s |
| Heal v3 | Existing drink gesture/timing; native hollow cup with exterior D handle; small mouth-approach clearance adjustment | 2.4 s |

## Authoring and reference

`revise.py` runs **inside the owned Blender MCP session**. It authors native FK
poses, hand/foot targets, pole controls and hilt curves, evaluates Blender's IK,
and separately bakes the deform rig. It is not an external motion generator.
The editable scenes embed the recipe and retain reference, control and baked
actions. Blender 5.2.0 LTS ran on the verified Studio through the shared GPU slot.

The owner's Vergil reference is recorded with hash and observed timing in
`decisions.json`. The 145-frame / 14.5-second GIF was inspected, including the
8.1–8.7-second launch, ghost/transit, reappearance and recovery sequence. Only its
motion principle is used; the approved Knight and sword are unchanged.

The v3 scene directory is `Local/Blender/feedback-v3-20261021`. Internal utility
filenames remain `<job>_Blender_v1.blend`; catalog/export filenames are v3. Prior
v2 scenes are preserved separately. Heal derives from the v2 editable scene.
Source inputs therefore require the previous private archive as well as this delta.

## Blink VFX contract

Blender meshes have native `hide_render` keys at the authored times. The glTF
armature exports a `veyrBlink` JSON extra with vanish/reappear/distance/direction.
Standard glTF does not support visibility animation: `viewer.js` consumes the
same catalog contract, hides the entire Knight/sword together, and displays a
fading blue snapshot of the launch pose and a brief arrival ghost. The skin is
never collapsed to zero scale. Scrubbing, replay and looping use action-local
time. The reviewer camera accommodates the full displacement.

The Blender films show native disappearance/reappearance. Blue afterimages are
currently a reviewer VFX layer, not an Unreal implementation. Future integration
must reproduce the visibility/afterimage contract and coordinate root motion
with actor movement. The hop is part of the dodge; it does not restore jump.

## Checks and visual limits

- All six independent 120 Hz GLB audits pass for duration, finite transforms,
  limb lengths, held-palm drift, rotation steps and relevant motion requirements.
- Guard raises the right hand .256 source unit and settles by .4 s. Its starting
  pose is intentionally a newly lowered ready pose, not the previously approved
  upright two-hand idle which the owner found already looked like guarding.
- Backpedal torso turn is 8.28 degrees, with independent weight transfer and
  noncrossing feet. Both blink dodges preserve lateral foot order and return to
  the translated one-hand idle.
- Native evaluated-mesh checks sample 2,031–2,033 free-hand vertices at 75 Hz.
  Cup bowl clearance is at least .0131 source unit; the heavy attack's left
  glove stays at least .0743 source unit from the sword surface. Contact with
  the cup's handle is intentional. These checks supplement visual inspection.
- Front/side/three-quarter full sequences were rendered at 30 fps. All six
  normal-speed films decode and match the clip durations. Close-ups cover the
  cup grip and mouth approach; exported textured playback is inspected in Chrome.
- No owner approval is implied for these six candidates. No game build, Unreal
  import, packaged runtime test or gameplay-feel acceptance occurred this pass.

Reports are in `reports/`. `render.py` and `contact_audit.py` run in the owned
Blender MCP session; `audit_exports.py` independently reads the delivered GLBs.
Do not weaken an audit to accept a visible contact fault.

## Review and storage

The existing private laptop-accessible reviewer serves v3 without an SSH command.
`remainder-catalog.json` places the six corrections first, marks the one-hand walk
approved, and retains Run/Ready walk unchanged. A private film page lives at
`.asset-cache/feedback-v3-media/index.html`. Use the existing tailnet bookmark.

Editable scenes, exports, reference and media are backed up privately in
`oh-ashen-one/veyr-animation-sources`, release `knight-feedback-v3-20261021`.
The public repository contains recipes, metadata and sanitized reports only.
This pass ends here; do not start the dragon or replace the installed game.
