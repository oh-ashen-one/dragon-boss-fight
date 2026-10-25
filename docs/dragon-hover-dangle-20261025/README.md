# Dragon hover v2 — relaxed dangling limbs

Owner correction: all four paws should point down; front hands should hang clear
of the waist/body. This is a new review candidate, not an owner approval or native
integration claim.

## Authoring and review

- Blender 5.2 GUI, isolated Blender MCP on loopback9891, owned scene guard
  `codex-veyr-dangle-20261025`. The `.py` files execute inside Blender and author
  actual controls, IK constraints, keys and bake actions.
- Base: `Local/Blender/polish-20261025/Dragon_FlyHover_Blender_polish_v1.blend`.
  This retains the original v1r2 wing/body motion. Older approved files are intact.
- Four IK targets now hang below shoulders/hips. Planted-paw orientation provides
  the roll reference; downward pitch replaces the cupped pose. Front wrists move
  forward clear of the belly; a right elbow pole keeps the bend outside the ribs.
  Small synchronized limb sway retains the two-second loop.
- Exact exported GLB reimported into Blender, rendered at30fps for its full2s
  duration from front/side/three-quarter views. Matching review films are in the
  private archive. Live localhost playback checked at1x with loop enabled.
- Independent critic inspected all12 phase/view images: no blocking wrist kink,
  knee inversion, torso penetration or hand/foot collision visible. That sampled
  critique alone is not proof of transitions or native playback.
- Export audit:154 tracks;136 unchanged. Only limb/shoulder/palm-helper tracks
  change. Wing/head/tail/body and morph animation retained. Maximum loop transform
  endpoint difference:2.98e-7. One skin,51 joints,3 morph targets in this review GLB.

## Source-first check

Checked Mixamo and Fab before authoring under the October25 source-first policy.
[Adobe's Mixamo FAQ](https://helpx.adobe.com/be_en/creative-cloud/faq/mixamo-faq.html)
limits its library/auto-rigging to bipedal humanoids, incompatible with this rig.
[Fab's Cute Dragon:Fire](https://www.fab.com/listings/9577c89a-3a09-4c4a-b44b-8ed55043e4ec)
is a different stylized dragon set including flight animations; compatible bone
mapping and an animation-only license were not established. No assets purchased,
downloaded or relicensed. This is enhancement of an already compatible existing
hover base, not a newly synthesized wing loop. Existing private generated-model
provenance and restrictions continue to apply; generated binaries stay private.

## Restore and review

Private release: `oh-ashen-one/veyr-animation-sources`, tag
`dragon-hover-dangle-20261025`, asset `Veyr-Dragon-Hover-Dangle-v2.zip`.
Extract at repository root. Original eight-candidate reviewer dependencies must
also be present. `python3 tools/asset-review/polish-server.py --check` validates
hashes. The server overlays only the hover row with `manifest.json`; old files and
reviewer8775 remain untouched.

Review: http://127.0.0.1:8776/#polish%2FDragon_FlyHover_Blender_dangle_v2.glb

Next native step: adapt takeoff/landing airborne endpoints to this new pose while
preserving ground endpoints, rebuild the shared RuntimePolish clip bank and verify
native takeoff → hover → landing. The packaged Moonlit Silver B app still contains
the previous hover. Do not substitute this standalone51-joint review GLB directly
for the normalized52-joint shared game bank.
