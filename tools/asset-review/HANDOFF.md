# Knight one-hand idle review handoff

Branch: `codex/veyr-asset-review-20261019` in `oh-ashen-one/veyr-cinder-warden`.
Laptop viewer: `http://127.0.0.1:8765/#review%2FIdleOneHand_Breathing_v3.glb`.

The owner selected the static `KnightRig.glb` / “Knight body” stance as the
reference. The prior active `Idle.glb` and breathing v1 were visually rejected.
The v3 candidate starts from that exact reference rest pose. It has a four-second
closed breathing loop: the chest lifts about 4.43 cm, the shoulders and upper
arms move, and the neck and head follow. Right and left foot world transforms
remain unchanged in sampled frames. The right hand keeps its rest local
transform. The viewer attaches `BoatGreatsword_v4.glb` to `RightHand` using the
same grip transform in both the static reference and v3; the extra viewer-only
blade pitch used in v1 was removed after the owner identified knuckle clipping.

Only the v3 candidate and static Knight body are listed in the laptop viewer.
The other source files are hidden from the list, not deleted. The accepted
`9b185634` build and active Unreal assets are unchanged. No native Unreal
preview or game integration has been claimed for v3.

Candidate SHA256:
`7a5c482cb6a363e22e41303a8162d9b7bfbf04523745cb45cfc9dacf8beec3df`.
It is cached on the laptop under `.asset-cache/review/` and copied with the
same verified hash to the Studio's
`Local/art-pass-20261019/knight/idle-review-20261019/IdleOneHand_Breathing_v3.glb`
under the Veyr checkout. `tools/art/author_knight_idle_review.py` regenerates
it from active Knight v015 `KnightRig.glb` without replacing an existing file.

Next: get owner visual feedback in the focused Chrome viewer. If accepted,
inspect the candidate in a session-owned native Unreal preview after checking
the shared renderer slots and bind-space handling, then integrate it on the
appropriate game branch. Preserve the old build and prior clips.
