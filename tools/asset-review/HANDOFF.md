# Knight motion review handoff

Branch: `codex/veyr-asset-review-20261019` in `oh-ashen-one/veyr-cinder-warden`.
Laptop viewer: `http://127.0.0.1:8765/?review=blender-walk-v3#review%2FWalkTwoHand_Blender_v3.glb`.
Loopback server on verified laptop model `Mac17,2` (current hostname `Mac-106`).

## Cross-machine entry point — 2026-10-21

Read the root `HANDOFF.md` first for GitHub assets, fresh restore verification,
process ownership, and exact commands. This document preserves detailed motion
approvals and technical history.

## Blender walk v3 candidate — 2026-10-21

- Authored in live Blender 5.2.0 LTS with sparse pelvis/torso/breath/hilt curves,
  native anatomical IK, calibrated pole angles and a 60fps baked deform action.
  The embedded refinement script rebakes edited control curves.
  On another Studio, use current repository scripts with `VEYR_BLENDER_WORK`;
  the archived embedded scripts retain the original Studio paths.
- `WalkTwoHand_Blender_v3.glb`, 3.5 seconds, SHA256
  `d0713bac27cd87f6d5ed34eebb2c10a4bc6d1011a125bbe30f65bda405cd3c3d`.
- Editable scene: `/Users/midir/veyr-blender-walk-20261021/Knight_Walk_Blender_v3.blend`
  on the Studio; SHA256 `b37a8e36dfcc1c1edb8c3df6289ae74a746ab8538f9c571fcb3d260b1fda20e9`.
- Scripts and usage: `tools/art/blender/README.md`. Reports:
  `reviews/blender-walk-v3-{authoring,export,audit}.json`.
- Final idle endpoint matrix errors <2.3e-6; independent 120Hz GLB audit:
  palm drift <0.000789 rig units, stance-foot frame drift <0.000021,
  maximum local joint step <3.366 degrees per 60Hz sample.
- Inspected Blender renders from front, side and three-quarter views; corrected
  an initial elbow bend-plane mismatch before the final export.
- Chrome extension control is now available. Opened the actual v3 GLB on laptop
  localhost, verified textured character/sword, 3.5-second playback at 1x and
  Body view. The deliverable tab is marked to remain open. Snapshot saved at
  `/tmp/veyr-blender-chrome-review.png` on the laptop.
- All approved clips and the v1/v2 walk files are preserved. V3 is unapproved,
  still a start/walk/stop study, with no Unreal integration/rebuild.
- Public project repository: character derivatives remain private as before;
  Blender scene and export are preserved in the private GitHub handoff bundle;
  see the root `HANDOFF.md` for the portable restore commands.
- Shared-brain rule commit `e5330b7` pushed to
  `oh-ashen-one/agents-md:codex/blender-animation-rule-20261021`.
  52 tests and catalog validation passed. Not merged to main; no global rollout
  is claimed. Project AGENTS.md and user-requested local memory note are active.

## Blender workflow correction — 2026-10-21

Owner requires Blender for all character animation authoring/refinement and asked
for this rule in project files and the shared brain. Walk v2 is a reference only;
it remains unapproved. Next work must refine the full-body ready walk in Blender,
retain editable rig/actions and inspect motion visually before exporting.

Owner explicitly authorized a third session. Published brain main `ba35669`
also permits up to four Blender-only processes. Verified Studio `Mac15,14`;
foreign Blender PIDs 27849 and 27888 remain untouched. Task session launched
through the shared GPU slot wrapper: owner `codex-veyr-walk-20261021`,
loopback MCP port 9881, Blender PID 28574, work folder
`/Users/midir/veyr-blender-walk-20261021`. Query the owner tag before mutation.
Do not reuse stale PIDs without checking live state. No game engine was running
or queued at launch. `powermetrics` required sudo authentication; the slot tool's
IOAccelerator sample was 13 percent before launch. No claim of a completed
three-renderer stress test is made.

## Active two-hand walk review — 2026-10-21

Owner authorized the two-hand walk after approving every currently displayed
attack and idle. Walk v1 was rejected as too stiff: only the feet seemed to move.
Owner requested a ready-to-hit posture, hunched shoulders, whole-body breathing,
sway and idle movement. **Walk v2 remains a review candidate, not approved.**

- `WalkTwoHand_Ready_v2.glb`: 3.5 seconds, 426 samples, five alternating steps.
  SHA256 `0947c437e48a47b0590619ce25fc977a5072d96f9be8b9eafab4b1a061723dfe`.
- Starts in approved idle, walks 0.72 rig units forward, returns to exact approved
  idle at its new position. This is a start/walk/stop study, not a seamless
  locomotion cycle ready for engine blending. Looping repeats that study.
- v2: forward torso lean, shoulder protraction/elevation, pelvis/chest counter
  rotation, stronger lateral weight shift, 1.8-second breathing layer, and
  animated shared hilt solved to both palms with flexible elbows.
- `author_knight_twohand_walk_review.py` is the v2 generator.
  `verify_knight_twohand_walk_review.py` independently checks exported contacts,
  start/end pose (accounting for translated Hips descendants), and continuity.
- v2 audit at 120Hz: stance-foot frame drift <8.8e-8 rig units, palm drift
  <7.8e-8, knee flexion 24.43–60.79 degrees, maximum local joint step <1.81 degrees.
  Authoring wrist deviation <0.52 degrees; mesh/skin/bind bytes preserved.
- Reports: `reviews/twohand-walk-v2-{authoring,audit}-20261021.json`.
  Rejected v1 export and its separate reports remain preserved.
- CPU authoring and audit ran on verified Studio `Mac15,14`; no engine launch.
  Both exports are saved in the Studio review destination below, SHA verified.
- Viewer follows root travel with the camera. Uses the continuous strong grip
  sword on `ReviewWeaponSocket`. Existing approved assets are untouched.
- Chrome native access now works. Loaded v2 and verified playback at 1x, inspected
  the closer Body view. Browser changed back to a New Tab during further scrub
  inspection; do not claim a comprehensive visual acceptance or current open tab.
- Next: owner review of the fuller body motion. Preserve v2 until feedback.

## Approved two-hand light attack — 2026-10-20

Owner approved the faster strong attacks, then authorized the proposed two-hand
light attack starting from the approved two-hand idle. No new reference was
supplied for this move; it is an original compact cut using the established rig.

- Approved: `LightAttackTwoHand_Compact_v1.glb`, 1.1 seconds, 73 baked samples.
- SHA256 `cf2fdf2063824184251f2537efda74c95ab7fdb13df0e97289b8d7548ae78d56`.
- Generator: `tools/art/author_knight_twohand_light_review.py`; shared solver
  now accepts an optional profile, preserving the original strong profiles.
- Short windup, fast cut, modest body/hip turn and left step, direct recovery.
- Runs on verified Studio `Mac15,14` with NumPy/SciPy, headless CPU only.
- Uses `BoatGreatsword_StrongGrip_v1.glb` on animated `ReviewWeaponSocket`.
- Authoring report: `reviews/twohand-light-authoring-20261020.json`.
  Wrist deviation <1.79 degrees; grip and foot target error <6e-16 rig units.
- Independent exported audit: `reviews/twohand-light-audit-20261020.json`.
  At 120Hz, both endpoints exactly equal the approved idle. Worst between-key
  palm drift <0.000727 rig units; largest local joint step <3.24 degrees.
  Body geometry, skin, bind nodes and materials preserved byte-for-byte.
- Local API clip hash verified. Export preserved on Studio in the same dedicated
  review destination listed below. Source pushed on this thread's branch.
- Owner explicitly approved this candidate in the conversation on 2026-10-20:
  "approved". Preserve the clip and its 1.1-second timing.
- Agent visual inspection was blocked by Chrome tool permissions; owner approval
  is recorded separately from that unavailable inspection. No native Unreal
  import, integration, or playtest is claimed.
- Await the owner's next move selection; do not change approved motions.

## Approved two-hand strong attacks

Owner approved one-hand attack v10, then requested the two-hand strong attack.
After selecting the first sweep in the supplied GIF, owner added "do both ok".
Both the first sweep and later forward thrust are now separate review clips.
Owner approved BOTH motions on 2026-10-20, requesting much faster timing.
Separate timing copies run 3x faster. Owner approved the faster timing before
requesting the next move on 2026-10-20; sweep v9 and thrust v7 are approved.
This is browser motion review;
no Unreal rebuild, import, native preview, or game release was performed.

### Faster timing, 2026-10-20

- Sweep v9: 1.466667 seconds, SHA256 `cc900aa0c77e5e29a0a76e84c7f448a867b12df58505d7c7741b957394156deb`.
- Thrust v7: 2.306667 seconds, SHA256 `ea2234f8e5e0cf4aa482c1a8ab510626393365639e57d88b7a84aecf38d55a92`.
- `tools/art/retime_knight_strong_review.py` divides each unique animation time
  accessor by 3 exactly once. All joint/socket output samples, mesh, skin,
  materials, nodes, channels and sampler mappings verified unchanged.
- Report: `reviews/twohand-strong-timing-20261020.json`. Originals below preserved.
- Viewer serves v9/v7 by default, uses normal 1x playback, and maps the reference
  inset back to original time. Both API asset hashes verified by HTTP.
- New files copied exclusively to the Studio destination below; SHA256 verified.
- Visual verification of NEW timing is pending: browser extension unavailable
  and native Chrome access rejected with "Computer Use was not approved to use
  Google Chrome". User asked how to grant access; official Settings > Computer
  Use > Google Chrome setup and site permissions explained. Do not claim a new
  visual review until Chrome control is restored or owner reviews the timing.

### Preserved approved motion sources

- `StrongAttackTwoHand_Sweep_v8.glb`: 4.4 seconds / 265 samples.
  SHA256 `9ac6e44a9e68af840dd2942375fd0131ebdcb0e03c077db2305abb34653da808`.
- `StrongAttackTwoHand_Thrust_v6.glb`: 6.92 seconds / 425 samples.
  SHA256 `42320336c2c7d09ab65576f9f3bf1f94d6dee82eb7a163e1ef6db2854fc07e89`.
- `BoatGreatsword_StrongGrip_v1.glb` uses the original boat sword with a
  continuous handle tapered to 48% width in the grip region. All blade vertices
  and all triangles are preserved. The approved idle sword remains unchanged.
  SHA256 `40d17087f2e97a03f0b630851a0ddc28a9deda30933e5bca624098800716181b`.

`tools/art/author_knight_twohand_strong_review.py` accepts `--move sweep|thrust`,
`--body`, `--approved-idle`, and exclusive `--output`. Its `make_review_sword`
function regenerates the strong-attack sword from `BoatGreatsword_v4.glb`.
Both motions use the approved two-hand idle v6 for exact starting/recovery pose.
A single weapon transform drives both hilt contacts; arms use elbow hinges and
bounded forearm rotation. Knees follow the pelvis/foot heading, with foot targets
preserved through weight shift and the left step. Strong sweep is driven by a
hip/torso turn; thrust includes a 30/15-degree right/left oblique palm adjustment
at extension, instead of forcing backward wrist bend.

IMPORTANT FOR FUTURE ENGINE INTEGRATION: these strong clips append an animated
non-skin `ReviewWeaponSocket` node. The browser attaches the strong sword there,
not to the fixed one-hand RightHand socket. Preserve/bake that weapon transform
when importing into Unreal; dropping it loses the corrected thrust grip. All
original body nodes, bind skeleton, skin weights and mesh bytes are unchanged.
This is not a general mesh reweighting pass.

Independent exported-GLB audit at 60Hz is in
`reviews/twohand-strong-20261019.json`: worst palm-to-hilt drift <6.6e-8 rig units;
start matrix error zero, end error <9e-8; maximum adjacent shoulder rotation
6.08 degrees for sweep and 7.57 for thrust. No 180-degree joint reversals.
Authoring wrist deviation from approved local grip stays below 27.6/23.1 degrees.
Chrome checked windup, mid-cut, follow-through, thrust extension from the side,
and both palms close up. The reference uses a different weapon/proportions;
these are authored adaptations, not extracted original game animation tracks.
No rendered performance or Unreal acceptance is claimed.

Reference GIF: `d7965ok-b28aa032-999c-41e8-9825-33113292d5a7.gif`,
640x360, 686 frames at 20ms, total 13.72s; SHA256
`689fbf1cc5055d4270cfcca77bd84ba65b28a4761fb5b680674f0a5a22e37066`.
The exact signed owner URL remains in the conversation. The local private file
is `/tmp/veyr-twohand-strong-reference.gif`.
`prepare_knight_twohand_reference.py` extracts 97 sweep frames from 0.00s and
173 thrust frames from 6.80s, downsampled to 40ms. The viewer synchronizes the
selected segment and offers normal/half/quarter speed. Earlier drafts remain
in the ignored asset cache. Approved one-hand v10 and both idles are unchanged.

Studio copy destination (verified `Mac15,14`):
`/Users/midir/Documents/Codex/2026-10-17/task-3/Local/art-pass-20261019/knight/twohand-strong-review-20261019-codex/`.
Both clips, strong-grip sword, and original GIF were copied with exclusive file
creation and verified matching SHA256 hashes. Re-running the final generator
reproduced both clips byte-for-byte. The approved one-hand attack and both idle
hashes were rechecked unchanged before publication.

## Approved one-hand attack

Owner rejected v3 and subsequent IK revisions: both arms appeared to bend down,
the windup stopped at separate keys, and shoulder/elbow rotations pinched the
mesh. Owner's latest direction is a single continuous rest -> behind head ->
floor swing, with anatomically plausible shoulders, elbows, and knees.
Owner explicitly approved v10 on 2026-10-19: "Nice Nice. This looks much, much better. This one is approved". Preserve it and both approved idles. The active task is now both two-hand strong attacks: first sweep and later thrust.

Approved browser motion: `LightAttack_BlackKnightReference_v10.glb`, 2.8 seconds,
176 baked samples. SHA256:
`6bbe88f658f2e72659aca48d41e141f6ab5faf6c3d82d3d076610880689b4665`.
Generator: `tools/art/author_knight_light_attack_review.py`.
Earlier candidates remain in the ignored asset cache and older scripts preserve
the prior implementations. The native game/build 9b185634 is unchanged.

Arms now use torso-relative FK shoulder flexion/abduction and single-axis elbow
hinges. Approved local wrists/fingers remain fixed; free arm guards independently.
Continuous PCHIP channels carry velocity through intermediate lift poses, with
staggered shoulder/elbow peaks. A bounded shoulder-flexion correction lands the
blade, without rotating the wrist. Knee poles derive from approved leg planes;
foot targets stay planted except for a small right step. Original mesh, skin,
bind skeleton and materials are byte-preserved; this is a motion correction,
not a general reskinning or corrective-shape pass.

Checks: exact approved start/end pose, unchanged source hashes, no reach clamp,
maximum authored foot target error <5e-16 rig units, exported world matrix error
<8.6e-7. Independent 60Hz evaluation: right elbow flexion 14.25..74.20 degrees,
left elbow 29.17..94.17, fixed bone lengths, zero local wrist rotation changes.
Largest right shoulder/forearm frame changes are 20.05/12.18 degrees, removing
the prior ~175-degree IK reversal. Blade tip stays above floor (minimum .00395);
held contact tip is .025 rig units. Owner approval applies to browser motion only.
Chrome inspected at lift, overhead, and impact, including body closeups. Native
Unreal preview remains untested. Source weighting may still need a separate
review if deformation remains visible; do not claim a fully corrected rig.

The exact owner reference is shown alongside the model on the same timeline:
https://cdnb.artstation.com/p/assets/images/images/032/421/303/original/elhuevocosmic-black-knight-gif-2.gif?1606387799
37 frames, 50ms each, SHA256
`7406671d0795781d5d835928effda4ee5937bec928845a98077e52ced4da685b`.
`tools/art/prepare_knight_onehand_reference.py` extracts the verified reference
into ignored `.asset-cache/reference/onehand/`; it refuses a mismatched source.

Private candidate destination on verified Studio `Mac15,14`:
`/Users/midir/Documents/Codex/2026-10-17/task-3/Local/art-pass-20261019/knight/light-attack-review-20261019/LightAttack_BlackKnightReference_v10.glb`.
Copied with matching SHA256 and exclusive destination creation. Generator replay
produced the identical SHA256. No Studio engine/game launch or Unreal rebuild
is part of this review.

The owner supplied the same Wix-hosted GIF ending in
`d7965ok-b28aa032-999c-41e8-9825-33113292d5a7.gif` for both the
two-hand strong and charged strong descriptions; the full signed URL is in the
conversation. Owner initially selected the first sweep, then explicitly asked to do both the sweep and later thrust. A separate charged-hold gameplay variant has not been integrated.

The owner approved the one-hand idle v3. It remains available in the viewer and
unchanged, alongside the static Knight body reference. The original two-hand
idle and the remaining animations are preserved but hidden from this focused list.
Approved one-hand v3 SHA256:
`7a5c482cb6a363e22e41303a8162d9b7bfbf04523745cb45cfc9dacf8beec3df`.
It remains on the Studio at
`Local/art-pass-20261019/knight/idle-review-20261019/IdleOneHand_Breathing_v3.glb`.
`tools/art/author_knight_idle_review.py` recreates it from the preserved rig.

The owner approved the two-hand v6 in the laptop browser review on 2026-10-19.
It uses the static
Knight body pelvis and straight leg stance, re-solves both arms onto one sword
axis, and breathes through hips, knees, ankles, back, chest, shoulders, neck,
head, hands and weapon. A four-second 97-sample GLB loop is exported. The
review sword copy tapers its handle and omits only the handle faces buried in
the two palms. The approved one-hand sword and source boat sword are untouched.
The viewer offers Full model, Body, and Hands views for review.

Source static rig SHA256:
`6461729b8f638f84a1d6e1acb85aa5e3f2b5d1431594b36c450f53a53028d213`.
Original two-hand clip SHA256:
`2e49c0b6503ad631ea3ffcc7276db6ec42c3c73d4211722f7ee84f7b9845aef8`.
Two-hand v6 review SHA256:
`297b43eb9f240a1b166d815019a8914631549db207e79c6c52c219a8dd1cde01`.
Sword grip v6 review SHA256:
`3e9b91f629a96a2078e130ffb549c1bc6e5d443f2733d94bc0fa55cfbd20045e`.
The two review GLBs are cached on the laptop under `.asset-cache/review/` and
copied with matching SHA256 hashes to the verified Studio (`Mac15,14`) at
`Local/art-pass-20261019/knight/idle-review-20261019/two-hand-v6/` in the
existing Veyr checkout. The Studio checkout's active branch and unrelated
untracked file were left alone; no engine was launched there.

`tools/art/author_knight_two_hand_review.py` recreates the two v6 files from
the preserved source GLBs with exclusive output creation. It verifies the loop
closes, all animation tracks start at frame zero, source body geometry and bind
data are preserved, and both palms and foot pivots meet their targets. A
separate evaluator of the exported GLB checked all 97 samples: worst world
matrix discrepancy from authored poses was 1.6e-7 rig units; foot pivot drift
was below 5e-8 rig units. Knees moved 0.022/0.023 rig units and hands
0.029/0.029 rig units. The chest moved 0.0227 rig units (~5.55 cm), and hips
0.012 rig units (~2.93 cm) at the Knight's 244 cm scale. Chrome was visually
checked at rest and inhale, full body and palm close-up.

The original 9b185634 Mac build and active Unreal assets remain unchanged.
The owner's approval applies to the browser motion review; no native Unreal
preview or game integration is claimed. Before integrating either approved
clip, check Studio renderer slots and native bind-space behavior; preserve the
earlier build. The browser preview can differ from Unreal.


## 2026-10-21 — Six Blender rebuild candidates

All six approved Knight idles/attacks now have separate Blender-authored v1 candidates. See `tools/art/blender/rebuild/README.md` and its `reports/` for exact provenance, timings, checks, editable controls, and limitations. Approved source GLBs and walk v3 are unchanged. The viewer lists all six new candidates beside approved originals, uses the baked socket for the Blender exports, and keeps the original attack references and 3x strong timing. Private release: `oh-ashen-one/veyr-animation-sources`, `knight-approved-blender-v1-20261021`. All six exports pass the independent 120 Hz audit. New owner review and Unreal integration remain pending.


## Owner approval — 2026-10-21

Owner: “These are all approved.” This approves the six Blender v1 rebuilds delivered together: one-hand idle, two-hand idle, overhead, strong sweep, strong thrust, and compact two-hand light attack. Exact files and hashes are in `tools/art/blender/rebuild/approvals.json`. It does not implicitly approve the separate Blender walk v3 or native Unreal integration.

Runtime inventory confirms additional character motions: walk/run/backpedal/strafe left/right, one-hand heavy, one-/two-hand guard, jump, heal, stagger, death, and roll. These exist as earlier clips; presence does not mean a new Blender review. Preserve the roll the owner previously praised. Walk v3 is the immediate outstanding review. Owner requests the dragon next, one animation at a time, conditional on finishing remaining Knight scope.


## Remaining Knight set — 2026-10-21

13 Blender-authored review candidates now cover one-hand walk, two-hand ready walk v4, run, backpedal, both strafes, both guards, one-hand heavy, jump, heal, stagger, and death. They are not yet owner-approved. All six previously approved hashes are unchanged; roll is preserved. See `tools/art/blender/remainder/README.md`, `reports/`, and `tools/asset-review/remainder-catalog.json`. The local viewer at port 8775 lists new motions first and defaults one-shots to Loop off. Chrome playback, death terminal hold, and jump scrubbing were verified. Private release: `knight-remainder-blender-v1-20261021` in `oh-ashen-one/veyr-animation-sources`. No Unreal integration. Dragon work has not begun.
