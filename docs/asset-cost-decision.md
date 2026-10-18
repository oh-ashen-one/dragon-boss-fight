# Main-character asset spending and integration gates

Updated 2026-10-18. The owner first approved four P2 mesh attempts, then granted standing Veyr permission for necessary credit spending. That standing permission supersedes the earlier mesh-only and pending-rig approval gates. No credit top-up, subscription/account change or alternate generator was used.

## Recorded spending

| Completed operations | Credits each | Total |
| --- | ---: | ---: |
| Two knight and two dragon P2 meshes | 160 | 640 |
| Knight B Cartwheel Humanoid rig | 8 | 8 |
| Dragon V3-B Tripo Quadruped rig | 33 | 33 |
| Eleven knight motion candidates, including the seven remaining states | 33 | 363 |
| **Total observed debit** | | **1,044 credits** |

Every paid operation was started once, with a local record written before submission and its status/result preserved afterward. No failed/unknown paid call was automatically retried. The original ten operations completed: four meshes, two rigs and four motion candidates. Seven additional state candidates were then submitted once each after the integration owner reported the native bind fix: run, roll, jump, guard, heal, stagger and death. All seven additional clips completed and were downloaded. The live remaining balance was rechecked at 1,552 credits. Completion is not artistic or native acceptance.

## Actual mesh outputs

Requests used Customuse P2, Private, PBR and 4K textures. Each raw mesh has one primitive/material and three embedded 4096×4096 base-color, normal and metallic/roughness textures. Raw meshes contain no skeleton or clips.

| Candidate | Actual triangles | File size |
| --- | ---: | ---: |
| Knight A | 28,263 | 12,996,084 bytes |
| Knight B — selected | 26,885 | 11,363,296 bytes |
| Dragon V2-B | 57,269 | 13,724,092 bytes |
| Dragon V3-B — selected | 59,736 | 14,179,368 bytes |

The dragon results exceed the requested 50,000 polygon setting. V3-B was selected after actual fullscreen model comparison for its broader chest/forelegs and heavier head posture; V2-B has a slimmer upright neck. Knight B retains the broad armor and substantial sword with fewer triangles than A. These choices do not establish final native visual acceptance.

## Rig and motion results

Knight B's rig has one skin and 52 joints. Basic skin structure passed: 35,003 weighted vertices, normalized weights, no zero/negative/nonfinite weights and no invalid joint indices. Dragon V3-B's rig has one skin and 40 joints, but the weight audit found mislabeled head/wing anatomy, root coupling on a wing and no demonstrated independent jaw. Bone labels alone are not reliable semantic mappings.

| Knight candidate | Requested duration | Actual raw duration | Current evidence |
| --- | ---: | ---: | --- |
| Walk | 5 s | 5.6 s | Readable provider-viewer stepping; forward root travel, not in-place. |
| Idle breathing | 5 s | 5.2 s | Provider midpoint posture intact; still requires native and loop-seam review. |
| Light slash | 5 s | 5.0 s | Low sword motion around the measured middle action window; decisive combat timing not accepted. |
| Heavy overhead | 5 s | 5.0 s | Raised-arm action and follow-through present; sword visibly bends/displaces in stronger provider-viewer poses. Single-action recovery still needs review. |
| Run | 5 s | 6.0 s | Downloaded; normalized bind space and approved rigid sword verified on CPU. Native gait and loop seam remain open. |
| Guard | 5 s | 5.2 s | Downloaded; normalized bind space and approved rigid sword verified on CPU. Native pose and loop seam remain open. |
| Roll, jump, healing gesture, stagger, death | 5 s each | 5.0 s each | Five separate completed clips; normalized bind space and approved rigid sword verified on CPU. Native action windows and pose quality remain open. |

All eleven animation exports retain one skin, 52 joints and 53 animation channels. They use Cartwheel Simple, Keep rig; walk/idle/run/guard generation loop enabled; all other action clips disabled. Raw outputs are preserved unchanged. The animated export changes bone aliases and position-scale conventions relative to the rig export; root motion, bind transforms and skeleton compatibility must be normalized before native reuse.

The sword deformation is visible in Customuse itself and is separate from the subsequently observed Unreal import distortion. More generation is not a substitute for correcting bind transforms and rigid weapon attachment. Root subsequently passed a native visual review of the complete sword mask. Eleven new normalized derivatives now rigidly weight exactly that 1,245-vertex surface to RightHand; CPU checks preserve every non-weapon weight and sampled position and all sword pairwise distances. Native rigid-sword QA remains separate. No dragon animation was purchased to test an unsupported humanoid route.

CPU orthographic diagnostics show that the geodesic wing candidates follow both wings, with a narrow shoulder transition requiring review. The disconnected mouth island is an internal tongue-like surface, not the external lower jaw; it must not be reused as a full-jaw mask. The integration owner reviewed the wing and outer-mandible masks and authorized an experimental deterministic correction. Two independent five-joint wing branches and a head-parented jaw were added, with smooth shoulder and hinge weights. Weight-only jaw probes exposed fused lip surfaces; the reviewed oral seam now duplicates 55 vertices while retaining all 59,736 faces, original face positions/normals/UVs and texture bytes. The nine-vertex underside/throat boundary remains shared. CPU views at 15° and 25° show opening without the prior stretched curtains; native acceptance is still required. Rest-skin deviation from the original normalized export is below 3.23e-7 source world units, including duplicated identities. No extra generator or credits were used.

## Rights and next work

Raw meshes, rigs, clips, signed output links, identifiers and receipts remain in ignored local storage. Output metadata identifies the generator but supplies no embedded raw-redistribution license. Keep code licensing separate from asset rights and resolve applicable plan/provider notices before raw public asset publication.

Next work is verification of the rigid sword in native playback, native review of the experimental dragon wing/jaw correction, review of the additional state candidates, action-window/loop review and actual game QA. The [capability report](customuse-capabilities.md) records verified website capabilities and their limits. Standing credit permission remains valid; no routine re-approval is needed once a credible next operation is ready.
