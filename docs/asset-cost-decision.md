# Main-character asset spending and next decision

Updated 2026-10-18. The owner approved **two knight and two dragon P2 mesh attempts**, at 160 credits each and a total cap of 640 credits. All four completed successfully. Four individual receipts each report 160 credits: **640 credits actually charged**. No paid retry, rigging or animation operation was run.

## Completed meshes

All were requested through Customuse with P2, Private, PBR and 4K textures. Knight polygon setting was 30,000; dragon setting was 50,000. Actual decoded GLB triangle counts differ from requested settings.

| Saved candidate | Actual triangles | File size | Skeleton / animations |
| --- | ---: | ---: | --- |
| Knight A | 28,263 | 12,996,084 bytes | None / none |
| Knight B | 26,885 | 11,363,296 bytes | None / none |
| Dragon V2-B | 57,269 | 13,724,092 bytes | None / none |
| Dragon V3-B | 59,736 | 14,179,368 bytes | None / none |

Each file has one mesh primitive, one material, and three embedded 4096×4096 textures: base color, normal and metallic/roughness. Every file's hash and inspection receipt are preserved privately. The completed assets are candidate meshes, not rigged or integrated final characters.

## Proposed next paid step — not approved

A task-owned, unpublished Customuse workflow contains the actual selected GLBs connected to separate rig nodes. The enabled per-node actions were inspected without pressing Run:

| Actual input | Selected rig operation | Displayed price |
| --- | --- | ---: |
| Knight B | Cartwheel / Humanoid | 8 credits |
| Dragon V3-B | Tripo / Quadruped | 33 credits |
| **Two single rig attempts** | **No animation, no retry** | **41 credits** |

These quotes now use the real chosen models rather than the earlier unrelated humanoid or empty-node probes. No rig output exists yet. The unused empty Humanoid Animation node was removed from this task-owned graph, so there is no downstream animation node in the prepared rig branches. Recheck price before any separately authorized run; displayed estimates are not enforced spending ceilings.

Knight B is the recommended humanoid candidate: its actual PBR model retains broad armor and a substantial sword, with fewer triangles than A. After comparing both actual meshes in the website fullscreen viewer, Dragon V3-B is the recommended rig candidate for its broader chest/forelegs and lower, heavier head posture. V2-B has a slimmer, more upright long neck and slightly fewer triangles. Their current rest poses, metal roughness, weapon separation and deformation still require assessment after rigging and in Unreal. The dragon's four legs plus independent wings, tail and jaw are not guaranteed by the generic Quadruped choice. No creature combat-animation route has been validated.

The 640-credit mesh approval does **not** authorize these 41 credits, motion generation, additional meshes or retries. Keep all raw files in ignored local storage until the applicable output/provider notices and raw redistribution rights are resolved. The [capability report](customuse-capabilities.md) separates observed controls from validated results.
