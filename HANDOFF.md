# Veyr implementation handoff

Public repository: https://github.com/oh-ashen-one/veyr-cinder-warden

Active branch: `feat/first-playable`. Latest verified native milestone: source `6b39ddc`, build007, capture `combat-20261018T043138906Z`. This is an early playable, not visual completion. A further original arena art pass is in progress.

## Verified and preserved

- Unity6000.3.20f1 native macOS builds005–007 compile with zero errors. Exact stale generated TypeDB/runtime initialization duplicates were quarantined with hashes; prior failed reports remain local.
- Build007 accepted the original27-bone8-clip knight and28-bone14-clip dragon. Both are temporary art. Native core20.31s passed leg damage, buckle, collapse, exposed-head bonus damage, rise and damaging contact avoided by dodge.
- Build007 healing31.06s passed four charges,100HP cap and injured empty-flask rejection. Death38.42s passed settled death pose and fresh responsive restart.
- Build006 full fight passed at194.08s, eleven collapses and victory/restart. It used the earlier knight visual fallback; the same combat tuning must still be checked with the accepted rig and revised arena.
- Build005 four-leg isolation passed. Physical keyboard input exercised movement, sword, dodge, zoom and restart. Full manual camera acceptance remains pending.
- Native screenshot and20-second silent clip were uploaded to the user's Library with SHA256 source/build/capture identity. These are real executable frames, not concept renders.
- Public footage of Kalameet, Sinh and Midir was inspected; observations and limits are in `docs/references.md`. No footage or game assets are included.

## Current work and gates

1. Finish original arena lighting/material/composition refinement; inspect native frames.
2. Validate full fight and complete camera review with the current art/build.
3. Replace temporary main characters through requested Tripo workflow, then Blender cleanup, rig/weights and animation refinement.

Concrete Tripo proposal: one original quadruped basalt/copper dragon, H3.1 Best Quality,55 existing credits. The inspected profile displays200 credits but locks model export behind an upgrade. Generate in Parts and8K are off. The exact prepared prompt is `ArtSource/tripo-dragon-prompt.txt`; no generation submitted. Required user action: identify an existing export-capable subscribed Chrome profile and approve up to55 existing credits for this one dragon. No purchase or subscription change is proposed. General permissions are not treated as a spending budget.

The separately generated `ArtSource/Concept` image is art direction only. It does not replace the Tripo requirement.

## Evidence access

- Screenshot: https://chatgpt.com/api/library/files/libfile_b70d95e144a881919c8a70c9e586c429/download
- Clip: https://chatgpt.com/api/library/files/libfile_9d03e08ff3708191b3f5774ad0937f7e/download
- Identity: https://chatgpt.com/api/library/files/libfile_26308253fd8c8191b3b6e6c3c1587212/download

Local evidence, logs and generated builds are excluded from public Git. Shared GPU/capture overhead makes measurements nonexclusive; no guaranteed frame-rate claim. Only verified owned Veyr processes were managed. Ghostty and unrelated workloads were not controlled.

## Ownership

Root integrates and runs Unity through the shared GPU slot. Independent workers own arena art, reference research, Blender source/importer and replay tests. Preserve failed evidence. The task remains active; it has not reached polished completion.
