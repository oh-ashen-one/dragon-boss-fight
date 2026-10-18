# Veyr art pipeline

## Current artifact and honest status

`ArtSource/Veyr_TEMP_Rig.blend` is the native Blender source; `Veyr_TEMP_Rig.fbx` is the Unity interchange asset. **Both contain temporary original procedural geometry**, not Tripo output. They are suitable for early timing, hit-region and silhouette integration only. Visual completion requires replacing the main mesh with an approved Tripo model, then checking deformation and materials in the actual game renderer.

The export contains 6,162 vertices, 11,916 triangles, 28 deform bones and 14 authored action clips at 30 FPS. The charcoal body, basalt horns, amber eyes, bronze folded wings and exposed ember joints are original design studies for **Veyr, the Cinder Warden**. No extracted game content is used.

## Unity integration contract

- FBX exports in meters with `-Z` forward and `Y` up. Blender source faces `-Y`, with `Z` up. Confirm the imported visual orientation against the gameplay forward direction before attaching attack volumes.
- Use a **Generic** rig. Preserve root motion disabled for this prototype: gameplay owns movement. The root animation supplies local vertical collapse and recovery offsets.
- Bones named `fore_L_upper`, `fore_L_lower`, `fore_L_foot` (and `fore_R`, `hind_L`, `hind_R`) support separate leg regions. Ember patches identify the joint region visually. Hit colliders should follow the relevant lower bone; never bind all legs to the body collider.
- `head` and `jaw` expose the head hit window. Neck segments are `neck_01` and `neck_02`. Attach fire origin ahead of the jaw along the actual imported forward axis.
- Exported take names may have the `Veyr_Rig|` prefix. Match by suffix or configure the importer explicitly.
- Suggested looping actions: `Idle`, `Walk`, `Stagger_Loop`. All other actions should clamp at their end; trigger recovery explicitly. Stagger state sequence is `Buckle_<leg>` → `Collapse` → `Stagger_Loop` → `Recover`.

| Action | Length | Intended readable beats |
| --- | ---: | --- |
| Idle | 3.00 s | Chest breath and slight neck/wing movement |
| Walk | 1.00 s | Diagonal alternating leg lift; gameplay supplies translation |
| Stomp | 2.63 s | Fore-left raised by frame 25, held to 35, impact near 43, recovery to 80 |
| Bite | 2.37 s | Neck draws back and mouth opens to 24, forward strike 33, recovery to 72 |
| Breath | 4.30 s | Inhale/turn to 30, lower and open to 43, sweep to 105, recovery to 130 |
| Tail_Sweep | 3.30 s | Coil to 31, hold to 39, sweep to 53, punish window through 100 |
| Buckle_fore_L/R, Buckle_hind_L/R | 1.50 s | Distinct damaged limb folds in 8 frames, holds through 24 |
| Collapse | 2.50 s | Loss of balance then heavy drop around 38, settled by 76 |
| Stagger_Loop | 2.00 s | Low head and small injured breathing motion |
| Recover | 2.50 s | Head rises before body pushes off the ground |
| Death | 3.97 s | Final rear, asymmetric fall, slight settling; final pose retained |

These are animation authoring beats, **not validated damage timings**. Gameplay must supply telegraphs, invulnerability and collision windows; final input-driven avoidance testing is required. Automatic bone deformation and imported clip fidelity have not yet been visually inspected in Unity.

## Regeneration

After the shared engine-slot protocol authorizes an owned Blender run:

```sh
/Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup --threads 2 --python ArtSource/build_veyr.py
```

The script clears only the newly started Blender document, creates native geometry and a 28-bone armature, binds per-part vertex groups, authors actions, saves a `.blend`, exports the `.fbx`, and records the manifest. It does not touch another Blender process, invoke a generator, open network listeners or make purchases. Existing output filenames are deterministic; preserve an approved art version before regenerating.

## Tripo replacement gate

1. Use only the Studio's supported Tripo browser workflow. Record exact generation price and obtain applicable budget approval before paid generation. No Tripo request has been made by this art worker.
2. Save the selected original dragon mesh and provenance alongside the authoring source. Confirm redistribution rights. Code licensing and generated-asset licensing are distinct.
3. Import the model into the native source; keep the temporary mesh visible as a scale/anatomy guide. Fit the mesh to this rig's rest pose (all four feet on the ground; neck and tail matching the documented axes).
4. Clean disconnected interior fragments and unwanted self intersections; apply object scale, inspect face normals, create seam-aware UVs, and decimate or retopologize with enough edge loops around hips, knees, shoulders, jaw and wing roots. Retain a pre-cleanup source.
5. Bind to `Veyr_Rig` with named deform groups. Use automatic weights only as a starting point. Paint joints, neck and wing roots by hand; ensure no opposite-leg cross weighting. The temporary rigid-part groups are not a final organic skin solution.
6. Review every action at anticipation, contact, maximum deformation and recovery frames. Refine foot contact and wing intersections, sculpt the collapse pose around the arena floor, and keep the exposed head inside the intended punish region. Final Tripo proportions will require adjustment of bone rest positions and animation poses.
7. Replace temporary materials with authored physically based materials and a restrained emissive fissure mask. Keep silhouettes and joint vulnerability readable against the arena.
8. Export and visually test in Unity, capture source/build-matched screenshots and native gameplay, then retire `TEMP_` names only once the replacement and visual checks are actually complete.

`ArtSource/bind_tripo_mesh.py` is a staging helper for an already approved and anatomically aligned local GLB, FBX or OBJ. It preserves the source rig/action set, imports a new mesh, assigns provisional smooth weights from the three closest bone segments, hides the temporary body, and saves a separately named working `.blend`. It refuses to overwrite an existing output. Its weights are explicitly provisional and must be hand-painted; it does not infer alignment, perform topology cleanup or certify redistribution rights. The helper has passed Python syntax validation but has not run because no approved Tripo mesh is available and further Blender launches are on hold.

## Validation and failure record

- First sandboxed Blender background launch exited 139 during Metal capability initialization **before script execution**. The sanitized failure location was `supports_barycentric_whitelist` / `metal_is_supported`; no generated artifact was claimed from it.
- Read-only process listing was denied by the sandbox. No bypass or unrelated process control was attempted.
- The exact two-thread background export was then run through the supported approval mechanism and completed with exit 0. Native source and FBX were saved; the exporter printed success. No render job was launched.
- The shared safety-playbook hold reached the art worker just after this approved export launched. The parent was informed immediately. The process completed promptly and **all further Blender launches are on hold** until the parent resolves the shared slot protocol.
- Source Python parses, the manifest contains the expected action set, and each action name is present in the exported FBX. This is export evidence only, not a rendered or gameplay validation claim.
- FBX metadata originally included a local authoring-source pathname. It was replaced with a same-length relative path, preserving binary offsets; the generator now performs this sanitization automatically. No local home-directory path remains in the exported FBX byte content.

## Licensing

`build_veyr.py` is original project source offered under the project's MIT code license. The temporary mesh, original materials and authored animation data are dedicated under CC0-1.0. This does not determine the license of future Tripo assets, which require their own recorded provenance and rights review.
