# Veyr implementation handoff

Public repository: https://github.com/oh-ashen-one/veyr-cinder-warden

Active branch: `feat/first-playable`. Latest verified native milestone: gameplay source `c3c2e16`, build009. Core capture `combat-20261018T044000328Z`; full victory capture `victory-20261018T044050061Z`. This is an early playable, not visual completion. Original arena composition and lighting were revised and reviewed natively.

## Verified and preserved

- Unity6000.3.20f1 native macOS build009 compiles with zero errors in an independent source-only snapshot/cache. Build008 reproduced182 duplicate generated-metadata errors; original cache, hashes and native output remain preserved. The writer is unproven. Fresh clones/imports build cleanly under the verified conditions.
- Build007 accepted the original27-bone8-clip knight and28-bone14-clip dragon. Both are temporary art. Native core20.31s passed leg damage, buckle, collapse, exposed-head bonus damage, rise and damaging contact avoided by dodge.
- Build007 healing31.06s passed four charges,100HP cap and injured empty-flask rejection. Death38.42s passed settled death pose and fresh responsive restart.
- Build009 full fight passed at188.22s with accepted knight and revised arena, settled boss death and fresh responsive restart. The core20.38s pass included a real Tab lock-on toggle during collapse/head approach. Earlier006/008 full runs are also preserved.
- Build005 four-leg isolation passed. Physical keyboard input exercised movement, sword, dodge, zoom and restart. Full manual camera acceptance remains pending.
- Native screenshots and silent clips are delivered through the user's Library with SHA256 source/build/capture identity. These are real executable frames, not concept renders. Full native recordings and test JSON remain local under Evidence.
- Public footage of Kalameet, Sinh and Midir was inspected; observations and limits are in `docs/references.md`. No footage or game assets are included.

## Current work and gates

1. Replace temporary main characters through requested Tripo workflow, then Blender cleanup, rig/weights and animation refinement.
2. Refine final character/arena composition together and complete manual camera review, including RMB orbit.
3. Repeat affected native checks and deliver the polished runnable handoff. Current standalone app is Builds/Veyr.app; build008 is preserved separately.

Concrete Tripo proposal: one original quadruped basalt/copper dragon, H3.1 Best Quality,55 existing credits. The inspected profile displays200 credits but locks model export behind an upgrade. Generate in Parts and8K are off. The exact prepared prompt is `ArtSource/tripo-dragon-prompt.txt`; no generation submitted. Required user action: identify an existing export-capable subscribed Chrome profile and approve up to55 existing credits for this one dragon. No purchase or subscription change is proposed. General permissions are not treated as a spending budget.

The separately generated `ArtSource/Concept` image is art direction only. It does not replace the Tripo requirement.

Local evidence, logs and generated builds are excluded from public Git. Shared GPU/capture overhead makes measurements nonexclusive; no guaranteed frame-rate claim. Only verified owned Veyr processes were managed. Ghostty and unrelated workloads were not controlled.

## Ownership

Root integrates and runs Unity through the shared GPU slot. Independent workers own arena art, reference research, Blender source/importer and replay tests. Preserve failed evidence. The task remains active; it has not reached polished completion.
