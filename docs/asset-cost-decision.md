# Main-character asset spending and integration gates

Updated 2026-10-18. The owner first approved four P2 mesh attempts, then granted standing Veyr permission for necessary credit spending. That standing permission supersedes the earlier mesh-only and pending-rig approval gates. No credit top-up, subscription/account change or alternate generator was used.

## Recorded spending

| Completed operations | Credits each | Total |
| --- | ---: | ---: |
| Two knight and two dragon P2 meshes | 160 | 640 |
| Knight B Cartwheel Humanoid rig | 8 | 8 |
| Dragon V3-B Tripo Quadruped rig | 33 | 33 |
| Knight walk, idle, light slash and heavy strike candidates | 33 | 132 |
| **Total observed debit** | | **813 credits** |

Every paid operation was started once, with a local record written before submission and its status/result preserved afterward. No failed/unknown paid call was automatically retried. All ten operations completed: four meshes, two rigs and four motion candidates. Further paid operations are on hold while native bind transforms and weapon skinning are corrected; the hold is an integration decision, not missing owner credit permission.

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

All four animation exports retain one skin, 52 joints and 53 animation channels. They use Cartwheel Simple, Keep rig; walk/idle generation loop enabled, attacks disabled. Raw outputs are preserved unchanged. The animated export changes bone aliases and position-scale conventions relative to the rig export; root motion, bind transforms and skeleton compatibility must be normalized before native reuse.

The sword deformation is visible in Customuse itself and is separate from the subsequently observed Unreal import distortion. More generation is not a substitute for correcting bind transforms and rigid weapon attachment. No dragon animation was purchased to test an unsupported humanoid route.

## Rights and next work

Raw meshes, rigs, clips, signed output links, identifiers and receipts remain in ignored local storage. Output metadata identifies the generator but supplies no embedded raw-redistribution license. Keep code licensing separate from asset rights and resolve applicable plan/provider notices before raw public asset publication.

Next work is native bind/scale normalization, a reviewed rigid sword treatment, safe dragon wing/jaw correction, action-window/loop review and actual game QA. The [capability report](customuse-capabilities.md) records verified website capabilities and their limits. Standing credit permission remains valid; no routine re-approval is needed once a credible next operation is ready.
