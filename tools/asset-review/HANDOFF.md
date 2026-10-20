# Knight motion review handoff

Branch: `codex/veyr-asset-review-20261019` in `oh-ashen-one/veyr-cinder-warden`.
Laptop viewer: `http://127.0.0.1:8765/?review=continuous-onehand-v10#review%2FLightAttack_BlackKnightReference_v10.glb`.
Loopback server on verified laptop `MacBook-Pro.local`, `Mac17,2`.

## Current request and candidate

Owner rejected v3 and subsequent IK revisions: both arms appeared to bend down,
the windup stopped at separate keys, and shoulder/elbow rotations pinched the
mesh. Owner's latest direction is a single continuous rest -> behind head ->
floor swing, with anatomically plausible shoulders, elbows, and knees.
Approved idles must remain unchanged. No acceptance of this attack is implied.

Current candidate: `LightAttack_BlackKnightReference_v10.glb`, 2.8 seconds,
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
held contact tip is .025 rig units. These are checks, not owner acceptance.
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
conversation. Work on that move after the owner reviews the one-hand candidate.

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
