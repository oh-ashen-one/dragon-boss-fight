# Approved animation integration adapter

These tools perform structural GLB conversion, not motion authoring. Approved
source files remain untouched. The runtime outputs live privately under
`Local/CustomuseAssets/Integration20261025b`; input paths are command arguments.
The owner approved the 32 visible review candidates on 2026-10-25. This pipeline
also preserves approved Heal v4 and the existing praised roll, and carries
legacy dragon attacks/reactions forward as fallbacks.

## Reproduce

From the integration checkout, with Python, NumPy and SciPy available:

```sh
python3 tools/art/integration/normalize_approved.py \
  --source <authoring-checkout> \
  --output Local/CustomuseAssets/Integration20261025b \
  --legacy <original-game-checkout>/Local/CustomuseAssets
python3 tools/art/integration/make_import_plans.py \
  --root Local/CustomuseAssets/Integration20261025b \
  --legacy <original-game-checkout>/Local/CustomuseAssets --version v025b
python3 tools/art/integration/verify_normalized.py \
  --root Local/CustomuseAssets/Integration20261025b \
  --report tools/art/integration/structural-audit-v025b.json
```

`v025b` is a fresh native asset version. If the native destination already exists,
choose another version; do not overwrite a partial import or another session.
The normalizer is deterministic and may regenerate its own derived GLBs. It
refuses to overwrite an approved input file.

## Representation and compatibility

- The skeleton's named joint order and helper rest pose are canonical, while
  **each clip retains its exact source body geometry, skin weights, inverse binds
  and materials**. Native `MeshOverride` selects the right shared-skeleton mesh.
  Four Knight mesh variants exist: common review body, heavy split-vertex body,
  corrected idle/attack body, and legacy Roll. Two Dragon variants exist: the
  newer v008 71,261-vertex body and legacy v007 71,176-vertex body.
- The initial v025a experiment used one corrected Knight body everywhere. It was
  rejected by the independent critic because 83 vertices had different source
  skin weights, causing substantial posed differences. Its bone-only audit did
  not establish rendered geometry equivalence. v025b supersedes it and adds a
  full CPU-skinned vertex comparison for every source and derived clip.
- Dragon morph names are **not** interchangeable. Eight distinct payloads exist
  among `VeyrWingFold`, `VeyrWingFoldWalk` and `VeyrBreath`. Canonical morph targets
  are a union keyed by original name plus decoded payload hash. Sparse and
  implicit-zero accessors are decoded; target names get stable hash suffixes;
  all weight channels are remapped, with absent targets zeroed. The legacy body
  retains the same eight target names with zero deltas, preserving its original
  bone-only shape despite its different vertex count. The native import
  must retain all eight targets and import their animation curves.
- Both skeletons add an identity `VeyrRoot`. Knight additionally has nondeforming
  `WeaponSocket` and `CupSocket` joints: 55 joints total; Dragon has 52. Rest
  transforms and inverse binds are consistent, including invisible cup states.
  Visibility belongs in animation scale channels, never collapsed static binds.
- The weapon socket preserves its independent authored animation. A fixed wrist
  offset is insufficient for the approved thrust and death. CupSocket is a child
  of LeftHand with the original cup transform and scale visibility. The cup
  geometry is exported separately, not discarded by skeletal animation import.
- Three approved sword mesh variants and the cup have separate static exports.
  Source sword scenes have one identity mesh node. The cup remains mesh-local
  relative to CupSocket. Import glTF metres normally to Unreal centimetres and
  attach using the complete helper-bone world transform, including scale.

## Root-motion contract

The adapter adds inverse extracted motion to VeyrRoot; it does not rewrite the
approved body curves. Extracted translation is zero-origin **mesh-local Unreal
centimetres**, with glTF `[x,y,z]` converted to UE `[x,z,y] * 100`. No component
scale or relative offset has been applied. `root_sample_rate` is explicit
(normally 60; fractional-duration clips can have a slightly different uniform
rate). Native playback must reconstruct actor motion as `C * M * C^-1`, where
C is the mesh-relative transform. In particular, turns need pivot compensation
`c - Q*c` for the dragon's component offset.

Only travelling Knight backpedal-step, blink, guard-break and roll-attack paths
are extracted. In-place locomotion keeps its hip weight shifts. Knight attack
body yaw is preserved. Dragon TurnLeft removes its full 90-degree yaw and pivot
translation together; the endpoint translation is approximately [17.7,17.7,0]
mesh-local UE centimetres, before component scale. Flight vertical motion stays
authored; zero planar flight travel is not falsely marked as extracted.
`TurnLeftFine`/`TurnRightFine` preserve the legacy small-turn clips.

Native automatic root extraction/locking must stay disabled (`preserve`).
Runtime owns actor collision/movement and coordinates the emitted trajectories.
Fire and bite reuse their complete approved sequences with phase trim entries;
flight uses full Takeoff, Hover and Land. Damage windows are initial integration
choices derived from approved pose beats and must be checked against actual
native contacts. Nominal Knight movement speeds are stance-foot estimates,
not a substitute for native foot-slide review.

## Verification and remaining gates

`structural-audit-v025b.json` covers 74 normalized GLBs and times both on and
between root keys. All pass: maximum reconstructed source skinned-vertex,
bone/attachment or morph error is 3.414e-6; maximum bind-shape error is 1.222e-6.
These are source-unit numerical errors, not gameplay scores. The CPU check
includes every indexed and unindexed vertex, four bone influences and all morphs.
Both plans pass skeleton/inverse-bind compatibility against the shared skeleton
and geometry-bounds compatibility against their selected mesh variant: 25 Knight
keys and 43 Dragon keys. The legacy Roll's unreferenced old sword vertices enlarge
its POSITION accessor bounds, although its indexed triangles render only the
body. Do not compare that variant's raw bounds against the modern canonical body
or discard its source data to make that check pass.

The normalized clips and plans are ready for native import, but this report does
not claim Interchange success, correct native morph curves, rendered prop contact,
transition quality, camera quality or gameplay acceptance. Those require the
owned engine checks and critique loop led by the integration owner.

## Native import observations (2026-10-25)

- Native Knight v025b imports25 action keys and4 exact mesh/skin variants.
- Native Dragon v025d imports43 keys and2 mesh variants, with8 distinct morph
  payloads. Interchange emits a separate morph-only AnimSequence; the import
  adapter therefore reads the exact normalized glTF weight channels into the
  skeletal sequence's native float curves and verifies their saved values.
- Fractional bone-track endpoints require native frame alignment. Import uses
  300Hz with ceiling alignment, preserving motion with at most3.34ms endpoint hold.
- Native deterministic proof sampled408 poses and204 transitions withzero rejected
  requests. Independent source comparison passes all68keys, including morph
  presence and completeclip/bone/samplecoverage. Alpha endpointproof is strengthened
  for the next run; rendered/gameplay checks remain separate.
- One-hand Light has a runtime GameplayPlayRate of3 toretainfastone-hand versus
  slower two-hand combat (.933s versus1.2s). The approved source sequence remains
  unchanged; native impact windows and blade samples use the same rate. All other
  imported action rates are1.
