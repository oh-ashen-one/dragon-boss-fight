# Video2rig bite through the full pipeline — 2026-11-05 (opt-in, awaiting owner review)

One dragon move (bite) taken end to end, Leshy-style, from an existing generated clip. No new generation or spend.

## Pipeline and evidence

1. Source: Higgsfield Seedance 2.5 job `1e68df15-5bc6-4181-b3a9-b8b3d714384e` (2026-10-28), re-downloaded from generation history. The video2rig creature project (rig, start picture, readers) was restored from private release `oh-ashen-one/veyr-animation-sources` `v2r-dragon-20261028` into `Local/video2rig/dragon/` (gitignored).
2. Fit: `video2rig check` OK (body 0.92 %, limbs 1.22 % of height); `video2rig run` with reader-64 on MPS: median keypoint miss 3.76 px, outline 0.78 / 0.80, max twist 24.9 deg, no warnings, 0 frames under the floor.
3. Blender (5.2 LTS): `blender/import_motion.py` → `Dragon_Bite_v2r_raw.blend`; `tools/dragon_refine/cut_v2r_move.py` with `Local/video2rig/dragon/refine/bite_cut/spec_v1.json` → editable `Dragon_Bite_v2r_cut_v1.blend` (raw and cut actions both kept). Time-only remap at 30 fps, per-phase rates joined by cosine blends: lead-in trimmed (source frames 0–4), wind-up 1.6x, strike 1.25x, settle 1.0x, the 1.6 s dead hold 6x, recovery 1.6x. Result 2.47 s (source 5.0 s). Fitted body lunge, feet, wings and tail unchanged; additive jaw layer opens on the wind-up and snaps shut at contact. No whole-clip foot pinning, no forced blend back to the stance. Three-view EEVEE renders were inspected.
4. Export/graft: `export_native_action.py` onto the canonical rig (evaluated pose error 2.2e-6), `tools/unreal/prepare_video_bite_plan.py` → plan `videobite-v034videobite` with adjacent trims `BiteV2rWindup` 0–0.743 s, `BiteV2rActive` 0.743–1.443 s (impact 1.167 s), `BiteV2rRecovery` 1.443–2.467 s.
5. Native: owned editor through `gpu_slot` (new `open_owned_editor.py --capture-slots 3`, matching the owner's 3-client cap), native Epic MCP `import/finalize/verify/activate_polish_character DragonV3B`: 300 pose samples + 150 transitions, 0 failures. RuntimePolish/DA_Dragon promoted v033wings → v034videobite; keyed `Bite*` clips retained. Editor closed with SIGTERM, exited in 6 s.
6. Runtime (C++): `-VeyrVideoBite` selects the `BiteV2r*` trims (`AVeyrDragon::BiteClipStem`); off by default. The keyed bite's neck-pitch ground aim is not applied to it; its own native muzzle height at impact is measured instead (77.18 cm, reachable with the unchanged 100 cm jaw capsule). Showcase and replay phase lookups follow the selected stem.
7. Shipping package `Local/package-20261106T001217Z/receipt.json`, source `ebe0278b44c7…`. Showcase runs on that one app: before `Evidence/native-showcase-20261106T001505Z` PASS (20/20 segments), after with `-VeyrVideoBite` `Evidence/native-showcase-20261106T001807Z` PASS (20/20). Bite chapter: before 1.82 s, after 2.49 s.

## Review

Bare page `Local/bite-review-20261105/serve/` (port 8814): in-game side by side at real and half speed, plus Seedance source, video2rig fit film, Blender cut and raw fit. Owner visual acceptance pending; no blind Opus review run. Not yet default; combat balance with the longer bite not measured.

## Not done here

Root-motion actor travel (the bite's body lunge is skeletal only), the other moves, dense reader / upstream video2rig update, removing the floor telegraph.
