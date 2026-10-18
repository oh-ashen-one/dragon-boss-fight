# Temporary authored knight: export and integration plan

`ArtSource/build_knight.py` authors an original temporary armored knight, anatomical skeleton and eight animation clips. The parent completed an initial export with **27 bones, 8 clips and 3,118 vertices**. That export failed runtime duration validation; the fractional-endpoint correction below is saved in source and requires regeneration. Main character geometry still requires approved Tripo replacement before visual completion.

## Anatomical and motion choices

- Independent pelvis, spine, chest, neck and head; clavicles, upper arms, elbows and hands; hips, knees, ankles and toes; separate sword, flask and tabard plates.
- Knees and elbows use analytical two-bone solves with fixed segment lengths. Standing attacks keep foot positions fixed while the hips turn and torso counter-rotates. Locomotion has an explicit stance half-cycle: the planted foot moves backward relative to the character at the current 5.8 m/s gameplay speed.
- Pose matrices are authored in world space and converted into each bone's basis, avoiding the dragon prototype's root-axis error. Gameplay supplies horizontal travel. Dodge is a tucked shoulder roll with floor clearance; death kneels before falling and settling.
- Temporary plate armor, articulated greaves, closed visor, split tabard, diamond-section sword and ember flask are original geometry. The model is a rig and motion study, not finished character art.

## Exact current combat contract

The timing below was read from `Assets/Scripts/PlayerCombat.cs`; retain gameplay as the authority. The sword currently sends one contact event per swing at 0.23 seconds, rather than maintaining a physical blade collision interval.

| Clip | Duration | Sampling and event alignment |
| --- | ---: | --- |
| Idle | 2.40 s, loop | Subtle chest motion; knees remain articulated |
| Locomotion | 26/60 s (0.4333 s), loop | Running cadence calibrated to 5.8 m/s; stance foot motion matches root travel at full speed |
| Slash_A | 0.65 s | Gather to 0.17; sword crosses front at **0.23**; follow through to 0.39; recover by 0.65 |
| Slash_B | 0.65 s | Alternate crossing direction with the same contact time; alternate using swing count |
| Dodge | 0.58 s | Entire shoulder roll; invulnerability stays in gameplay at **0.08 < t < 0.44**; no animation events may extend it |
| Heal | 1.25 s | Left hand reaches belt and raises flask; hold through **0.85** health grant; put flask away by 1.25 |
| Hit | 0.65 s | Recoil peaks at 0.09, then relaxes; damage cooldown remains gameplay-owned |
| Death | 2.00 s | Kneel through 0.65, fall through 1.60, settle and clamp final pose |

The authoring rate is 60 FPS with explicit event keyframes, including the exact 0.23-second contact time. FBX baking samples at the export frame rate; the runtime should still sample using the authoritative floating-point combat timer. Do not derive gameplay events from animation completion.

### Fractional endpoint correction

The initial export's Dodge take declared 0.58 seconds, but inspection of the binary FBX `KeyTime` arrays showed its last actual baked key at **0.566667 seconds**. The one-frame bake omitted the fractional final frame. The runtime correctly rejected that shortened clip. The generator now holds the true final pose at the next integer sample: Dodge exports through **0.583333 seconds**, while gameplay still finishes at 0.58 seconds. Locomotion now uses an exact 26-frame interval to retain a seamless loop. Runtime validation keeps the full timing requirements with only floating-point tolerance; it does not stretch or shorten gameplay windows.

`VeyrModelImporter.InspectKnightClips` is a read-only editor entrypoint that prints each imported clip's name, duration and frame rate without building. Runtime logs also print all eight lengths before validation. Regenerate and reimport before expecting the correction in the existing FBX.

## Importer and runtime integration contract

The initial integration is now implemented in `AuthoredKnightVisual`, `PlayerCombat` presentation hooks and `VeyrModelImporter`. The contract below remains the verification checklist; the initial duration failure kept the proxy active as designed.

1. After a parent-coordinated shared-slot Blender export, import `Knight_TEMP_Rig.fbx` into `Assets/Resources/Art/`. Inspect the native `.blend` and export manifest first.
2. Use the same deterministic legacy/direct-sampling import approach as Veyr: preserve all bones, retain named takes, disable automatic animation playback and import all eight actions. Do not optimize away the `sword`, `flask`, `face_forward`, ankle or toe bones.
3. Add an `AuthoredKnightVisual` driver only after the FBX is available. Load the required clips, validate skeleton movement and visible skinned geometry, then hide the existing primitive player visual. Keep the fallback if validation fails.
4. Derive facing from `face_forward` and calibrate the imported height against the 1.9 m CharacterController. The character faces local **+Z** in gameplay; the Blender source faces **-Y**. Use an outer fitting transform so animation does not reset orientation/scale corrections.
5. Expose read-only player timing data: attack, dodge and heal elapsed seconds; remaining hurt time; swing count; planar controller velocity; temporary visual reference; and elapsed death time. Keep current attack, stamina, healing and dodge rules unchanged.
6. Sample slash clips directly at `attackTime`, alternate by swing count, and use the actual `sword` bone's exported tip for the trail. The original trail emits from 0.17–0.39 seconds; preserve that timing. Disable the old proxy trail only once the new one is bound.
7. Sample Dodge at `dodgeTime`; the driver already rolls the authored skeleton. Disable the old `visual.localRotation` roll when the authored model is active to prevent a double rotation. Preserve movement direction and invulnerability exactly.
8. Sample Heal at `healTime`; the flask bone moves the real mesh from belt to hand. Sample Hit as a brief additive upper-body reaction or an interrupt only if existing combat semantics permit it. `TakeDamage` currently cancels healing but does not cancel sword attacks or dodge; do not introduce a visual state that hides their active timing.
9. Locomotion phase should advance by planar traveled distance relative to 5.8 m/s. Blend toward Idle at low speed. When locked-on strafing or backing away, do not play the forward run unchanged: either author directional clips later or constrain the first integration to acknowledge this temporary motion limitation.
10. Death must take priority and clamp after 2.0 seconds. Restart must instantiate/reset the visual and trail; do not preserve an old death sample across scene reload.

## Required checks before accepting the integration

- Run one approved slot-managed export; preserve failures and do not launch parallel uncontrolled Blender instances.
- Check both slash clips at anticipation, exactly 0.23-second contact and recovery from front, side and player camera angles. Sword must pass through the intended forward attack volume; wrists and elbows must not pop or intersect the chest.
- Inspect stance feet and knees during idle, full-speed running, attacks and heal. The analytical solver can still need anatomical adjustment, especially sword poses at maximum reach.
- Verify dodge floor clearance, camera visibility, exact gameplay invulnerability interval, and no doubled root/visual roll.
- Confirm the health grant and visible flask pose coincide at 0.85 seconds, and interrupted healing returns to the appropriate state.
- Capture native gameplay showing sword contact, dodge, heal, hit, death and restart. Source parsing and successful FBX export alone are not visual or playability validation.
- Scan exported FBX metadata for local authoring paths before publication. The script includes same-length relative-path sanitization. Keep mesh/animation CC0 provenance separate from MIT source licensing and future Tripo terms.

## Replacement gate

No generation service is invoked by this script. Replace the temporary main mesh through the approved Tripo workflow, record its provenance and applicable rights, then clean topology, fit the anatomical rest pose, bind and hand-paint weights, and review all clips. The current rigid armor-part weights are a useful starting guide, not final organic skinning.
