# Veyr implementation handoff

Public repository: https://github.com/oh-ashen-one/veyr-cinder-warden

Active branch: `feat/unreal-migration`. The user changed the target engine to Unreal and main-model provider to Customuse. Unreal native C++ compiled successfully on2026-10-18; the editor/game has not run yet. The preserved Unity branch is `checkpoint/unity-native-009`, commit `1382c42`. Latest verified historical Unity milestone: gameplay source `c3c2e16`, build009. Core capture `combat-20261018T044000328Z`; full victory capture `victory-20261018T044050061Z`. This is an early playable, not visual completion. Original arena composition and lighting were revised and reviewed natively.

## Verified and preserved

- Unity6000.3.20f1 native macOS build009 compiles with zero errors in an independent source-only snapshot/cache. Build008 reproduced182 duplicate generated-metadata errors; original cache, hashes and native output remain preserved. The writer is unproven. Fresh clones/imports build cleanly under the verified conditions.
- Build007 accepted the original27-bone8-clip knight and28-bone14-clip dragon. Both are temporary art. Native core20.31s passed leg damage, buckle, collapse, exposed-head bonus damage, rise and damaging contact avoided by dodge.
- Build007 healing31.06s passed four charges,100HP cap and injured empty-flask rejection. Death38.42s passed settled death pose and fresh responsive restart.
- Build009 full fight passed at188.22s with accepted knight and revised arena, settled boss death and fresh responsive restart. The core20.38s pass included a real Tab lock-on toggle during collapse/head approach. Earlier006/008 full runs are also preserved.
- Build005 four-leg isolation passed. Physical keyboard input exercised movement, sword, dodge, zoom and restart. Full manual camera acceptance remains pending.
- Native screenshots and silent clips are delivered through the user's Library with SHA256 source/build/capture identity. These are real executable frames, not concept renders. Full native recordings and test JSON remain local under Evidence.
- Public footage of Kalameet, Sinh and Midir was inspected; observations and limits are in `docs/references.md`. No footage or game assets are included.

## Current work and gates

1. Implement the bounded encounter natively in Unreal5.8.3 at `Unreal/Veyr/Veyr.uproject`. Source workers separately own knight, dragon and arena; root owns integration, builds, official native MCP connection and gameplay evidence. Jump, roll, light/heavy attack and guard are required. Dragon fire, flight/reposition/landing, claw, rear stomp and tail attacks retain the four-leg collapse loop.
2. No Unreal editor has been launched. Shared GPU safety requires confirmation that no unresolved system permission/crash dialog is present before launch. Computer-use inspection of the notification surface was denied; that denial is respected. Source preparation continues independently.
3. Customuse is connected. Two free previews each are ready for the original knight and dragon. Proposed P2 mesh generation is160 credits each,320 total; no paid generation or numeric spending approval has occurred. Preview selection also remains pending. Website login succeeded; rigging and animation beyond the MCP's mesh-generation APIs remain under inspection. The generic unauthenticated65-credit website button refers to P1 and is not the prepared P2 quote.
4. No Blender fallback is approved under the revised request. The former Tripo Studio proposal is superseded. Do not spend its55-credit proposal or treat earlier Unity art as the final Customuse assets.
5. Establish official native MCP project/world identity, save an owned Unreal level, and run native combat/camera/transition tests before claiming Unreal playability. Unity evidence cannot establish this.

The second native C++ build passed with source identity `55b42197e9c8487eb78f78602e6bcaba77eabe87b5345c344c91c91ffc6c8bf4`, including input-only core/death/victory replay and source stamping. Its receipt confirms no source drift during compilation. The replay implements terminal settling/restart checks but has not run. Launch helper flags verified against installed source include `-notraceserver` and `-NoZenAutoLaunch`; use a project-local filesystem DDC graph when constructing the launch to avoid starting optional listeners. Native MCP remains on-demand localhost18773, pending host safety clearance and verified project identity.

Free dragon previews were reviewed in three preserved sets. The original frontal images had cropped wings and apparent tail ambiguity. A revised prompt and then a fresh general-asset session improved some proportions but still did not fully resolve framing. No production-art acceptance or paid mesh submission followed. Customuse website rigging, animation and raw-asset redistribution remain unverified; see `docs/customuse-capabilities.md`.

Private preview identifiers and account diagnostics remain in ignored local records.

The separately generated `ArtSource/Concept` image is art direction only. It does not replace the requested main-model pipeline.

Local evidence, logs and generated builds are excluded from public Git. Shared GPU/capture overhead makes measurements nonexclusive; no guaranteed frame-rate claim. Only verified owned Veyr processes were managed. Ghostty and unrelated workloads were not controlled.

## Ownership

Root integrates and runs task-owned engines through the shared GPU slot. Current workers own native Unreal arena, knight, dragon, and Customuse website research. Unity feature work is stopped and its evidence preserved. Preserve failed evidence. The task remains active; it has not reached polished completion.
