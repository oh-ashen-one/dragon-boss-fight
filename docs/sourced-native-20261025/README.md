# Sourced knight animation integration

The owner selected the sourced walk, slash, run and forward roll for the game and
explicitly retained the original guard. Work remains on `Fab-3D-Rig-Testing`.

## Runtime mapping

| Runtime keys | Source and fit |
| --- | --- |
| Walk / WalkTwoHand | Mixamo Sword and Shield Walk, fitted one-/two-hand carries |
| Run / RunTwoHand | VanillaLoop Fab run, fitted one-/two-hand carries |
| LightAttack | Mixamo slash body/footwork with a boat-sword arm path and stable grip |
| Roll | VanillaLoop Fab roll with the knight's forward-held carry adapted in Blender |
| RollAttack | New roll prefix plus sourced slash, with a short local-pose join |
| GuardTwoHand | Original v026 sequence and original Grip_v6 weapon, unchanged |

Ordinary WASD selects the walk in the current grip; Shift selects the run.
Walking is240cm/s with a measured nominal cadence of200cm/s; sprint remains580cm/s
with the sourced run's nominal cadence800cm/s. Ctrl remains unbound.
The normal one-hand primary chain uses the new slash for steps1/2. Separate heavy
styles, the two-hand combo and the other previously approved clips are retained.

The slash's1.5s source plays at1.6x, yielding0.9375s, close to the previous ordinary
attack cadence. The1s roll plays at1/0.78, preserving0.78s and the existing stamina
and invulnerability window. The counter contains a1s source prefix followed by a
1.2s retimed slash. Both roll actions use the extracted planar path through swept
character movement; constant roll velocity is not added a second time.

## Asset integrity and fitting

Source acquisition/license details remain in `docs/fab-rig-testing/README.md`.
The approved knight mesh and full boat sword remain intact. Final fitting is
performed inside owned Blender MCP: anatomical two-bone IK, palm targets parented
to the hilt, separate supporting-hand placement, forearm twist reconciliation,
clearance paths and high-rate baking. Quaternion hemispheres are made consistent
before interpolation. Mixamo exports are baked at120Hz; Fab exports at100Hz.
These are adapted licensed motions, not untouched downloads or newly invented
whole-body animation. The guard source study is not installed into the game.

The structural adapter handles the existing55-joint rig by name, canonicalizes
nondeforming helper inverse binds, preserves the authored WeaponSocket path, and
factors explicit actor travel without modifying the original inputs. The source
body gait keyframes and exported palm stability are independently audited through
the actual GLB sampler. All intermediate/rejected fits remain separate from v1
and the final selected files until verified cleanup.

Native v027 reuses the existing skeleton and inherits the other native clip
references. Import and activation verify the expected old version, original guard
sequence/weapon/source hash, every replacement source hash, clip timing, gameplay
rate, damage windows and root samples. Finalization modifies only new v027 props.
The initial receipt serialization error occurred after the assets were saved;
finalization and native pose/metadata verification recovered and verified those
saved assets without repeating the import.

## Verification and delivery state

See `validation.json` for current checks and exact evidence paths. Native editor
verification passed168 pose samples and84 transition checks, all18 integration
features, eight collision stages and original guard combat behavior. Packaged
validation is recorded separately; editor success alone is not packaged success.
The original guard `.uasset` SHA256 remains:
`1d7b990ae0e0e25fce5e97fa34d11d57de3cff86e748b47867d75a61d5efa069`.

The localhost comparison remains at http://127.0.0.1:8777/ and offers the initial
retarget as an optional Before view. The guard row clearly identifies the original
retained motion. Comparison source timing differs from game cadence metadata.

Shared-brain PR22 was approved, merged and synchronized at
`1bc7f80f2b4b88099ca926fe70282d0fa6d09ff9`. Future animation sourcing directly checks
Mixamo, Fab, NVIDIA SimReady and ThreeJS Assets, then wider licensed sources.
Whole-motion custom authoring requires an explicit exception; corrections and
adaptations of suitable sourced motion remain permitted. Other running sessions
are not claimed to have automatically reloaded their context.

Private source/Blender/native-input backup and restore identity are in
`authoring-backup-receipt.json`. Keep restricted assets out of public Git.
