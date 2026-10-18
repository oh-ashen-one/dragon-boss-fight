# Customuse character pipeline: verified capabilities and limits

Updated 2026-10-18. Inspection used the connected Customuse catalog, supported website controls, actual downloaded GLBs and first-party documentation. Both final main-model candidates originate in Customuse. No alternate generator, Blender operation, account/subscription change or public asset publication occurred.

## Executed operations

The owner approved four mesh attempts and later gave standing permission for necessary Veyr credit spending. All four P2 meshes, two rigs and four humanoid motion candidates completed. Total observed debit is **813 credits**, without paid retries. A private ledger preserves every selected input, live quote, before/after balance, node/task identity, output link and file hash. Public documentation excludes those identifiers and links.

P2 was freshly quoted at 160 credits per mesh before submission. Knights used a 30,000 polygon setting; dragons 50,000; all requested Private, PBR, 4K. Actual raw meshes have one material and three 4096×4096 textures. Knights contain 28,263 and 26,885 triangles; dragons 57,269 and 59,736. The requested polygon count was not an exact output limit. All raw mesh outputs initially had zero skins and zero clips. Source: [Generate 3D](https://customuse.com/generate-3d) and the current connected generation catalog.

## Actual rigging and motion workflow

| Operation | Directly verified evidence | Remaining limit |
| --- | --- | --- |
| Knight Auto Rig | Actual Knight B connected to Cartwheel/Humanoid; enabled Run quoted 8 credits; completed GLB has 52 joints, one skin and weights. | Requires native import/bind verification and weapon treatment. |
| Dragon Auto Rig | Actual Dragon V3-B connected to Tripo/Quadruped; enabled Run quoted 33 credits; completed GLB has 40 joints, one skin and weights. | Four limbs do not establish independent, correctly weighted wings or jaw. |
| Tripo body choices | Auto, Humanoid, Quadruped, Hexapod, Octopod, Avian, Serpentine and Aquatic are exposed. | Hexapod is not proof of winged-dragon support. No blind alternate-body re-rig was purchased. |
| Cartwheel body choices | Humanoid only in the inspected body menu. | No creature support established. |
| Humanoid Animation | Text to motion / Video to motion; Simple / Detailed; Keep rig; duration and loop controls. Actual knight walk, idle, light and heavy candidates completed at 33 credits each for requested 5 s Simple/Keep rig. | Action quality, root motion and native skeleton conventions need checking; completed does not mean accepted. |
| Rigged/animated export | Website dialogs offer GLB and FBX, JPG/PNG/TIFF/EXR textures and 1K/2K/4K/8K. Actual rig and animation GLBs were downloaded and parsed. | FBX conversion and its fidelity have not been tested in this pass. |
| Native transfer | Send to Unreal is visible for prepared meshes/PBR overrides. | Not invoked; menu presence is not proof of skeletal/animation import. |

Source: the authenticated [Nodes Editor](https://customuse.com/nodes-editor), task-owned rig/motion graph and completed output data. The graph contains exact selected assets and paid results; earlier empty configuration probes are superseded by these real outputs. Existing unrelated workflows were not changed.

## Output QA and integration implications

Knight skin structure passed a basic check across 35,003 vertices: normalized finite nonnegative weights and valid indices for all 52 joints. Provider-viewer walk samples showed intact armor and readable stepping. This is narrower than native animation acceptance.

The actual walk is 5.6 s, idle 5.2 s, light slash 5.0 s and heavy strike 5.0 s, despite all requesting 5 s. Each contains 53 animation channels. Walk has approximately 2.48 m forward root travel and lateral drift, so it is not an in-place clip. Animated exports change bone names (for example pelvis to Hips and right_wrist to RightHand) and position-scale conventions relative to the rig-only output, while joint order and skin weights were found unchanged in the first audited clip. Bind, units and root-lock handling must be verified against the actual imported skeleton.

The light motion has a low-cut action window, but decisive anticipation/contact/recovery timing is not accepted yet. The heavy candidate includes a raised-arm motion and follow-through; stronger sampled poses visibly curve the otherwise straight sword and displace its grip in Customuse's own viewer. That upstream weapon-skin defect is separate from native import distortion. A rigid weapon treatment and native checks are required before these can be called finished combat animations. Raw motions and failed/limited evidence are preserved rather than silently replaced.

The dragon's semantic names are misleading: the weight audit associates its actual muzzle mainly with generic bones, while some Head-named bones influence wings. One wing has substantial root weighting; an independent lower jaw was not demonstrated. Do not drive the anatomical head merely by the first Head-named joint. A complete dragon combat/flight animation pipeline inside Customuse is not established by the successful quadruped rig.

## Supported repair investigation

The completed model's Create menu exposes Auto Rig, Mesh Segmentation, Render Image and Generate Icon. The inspected node palette describes Mesh Edit as point/edge/face/piece manipulation and Character Tools as body/garment inspection. No manual bone-landmark editor, explicit jaw/wing joint insertion or weight-painting control was established in the inspected surfaces. An unused empty Character Tools probe was removed; no speculative repair job was run. This bounded inspection does not prove that no other service workflow exists.

The [official rigging guide](https://customuse.com/learn/what-is-3d-model-rigging) distinguishes standard humanoid auto-rigging from creature work and warns about fused parts and deformation topology. The [export guide](https://customuse.com/learn/glb-vs-fbx-for-ai-3d-assets) describes GLB/FBX paths, but actual exported data remains the acceptance criterion. The [studio offering](https://customuse.com/use-cases/game-development-studios) advertises tailored workflows through a pilot, not an entitlement established for the current self-service plan. The [Tripo schema](https://platform.tripo3d.ai/docs/schema) lists quadruped rigging and a quadruped walk preset; that alone does not show Customuse exposes this preset or supports the required combined wings/jaw/tail behavior.

## Rights

The [Customuse Consumer Terms](https://customuse.com/terms), updated 19 June 2026, retain users' input/output rights and permit lawful personal/commercial output use subject to feature, plan, asset, third-party and notice exceptions. The [Business Terms](https://customuse.com/business-terms), same date, expressly include output distribution and licensing, with analogous exceptions and applicability conditions. No output-specific raw-redistribution notice was found in the inspected result pages or GLB metadata.

Cartwheel's [production Terms of Use](https://getcartwheel.com/terms-of-use), revised 20 August 2026, distinguish User Content from service content and include generated motions in their User Content discussion. Its [Plugin Addendum](https://getcartwheel.com/plugin-addendum) retains users' rights in their User Content, subject to applicable agreements. These are relevant provider context, not proof that standalone Cartwheel subscription terms are the exact agreement governing Customuse's integration.

Keep source-code licensing separate from asset rights. Raw public redistribution and the chosen downstream asset license remain uncleared until applicable plan/provider exceptions are resolved. No asset files or signed links are included in the public documentation.

## Current work boundary

Standing owner credit permission supersedes the earlier pending 41-credit rig proposal. Further paid operations are deliberately held while the integration owner fixes native bind transforms and the weapon/dragon rig issues. This is a technical quality gate, not a request for another routine spending approval. Root owns all engine work; this inspection did not launch or control an engine.
