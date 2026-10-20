# Knight idle review handoff

Branch: `codex/veyr-asset-review-20261019` in `oh-ashen-one/veyr-cinder-warden`.
Laptop viewer: `http://127.0.0.1:8765/?review=twohand-v6#review%2FIdleTwoHand_ReadyBreath_v6.glb`.
The server is loopback-only on the verified laptop (`MacBook-Pro.local`, `Mac17,2`).

The owner approved the one-hand idle v3. It remains available in the viewer and
unchanged, alongside the static Knight body reference. The original two-hand
idle and all other animations are preserved but hidden from this focused list.
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
