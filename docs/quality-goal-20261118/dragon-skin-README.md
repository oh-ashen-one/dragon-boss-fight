# Dragon skin weights (Blender only, 2026-11-18/19)

Scripts in `tools/dragon_refine/`:

- `skin_stretch.py` measures per-triangle skinning stretch per clip (`--reference bind` = against the sculpted mesh with the same morph weights; `--reference frame0 --no-morph` = the A123 rule) and compares a candidate weight NPZ.
- `skin_fit.py` + `dragon_skin_fix.py` refit wing-root weights on the existing 52 bones (projected-gradient fit of hinge^p edge stretch over all clips, idle anchor), and mirror the right front paw's weight layout onto the left (`skin_paw.py`). `--base-weights` stacks a paw pass on a finished wing fit.
- `author_dragon_skin.py` builds/reads the editable .blend; `patch_glb_weights.py` writes re-import-ready GLBs changing only JOINTS_0/WEIGHTS_0.
- `render_skin_views.py` (stills) and `render_skin_turntable.py` (matched before/after clips, camera from bones only) render in background Blender through gpu_slot; `encode_skin_pairs.py` makes the MP4 pairs.

Results, numbers, asset list and Unreal steps live outside git in `Local/quality-goal/dragon-skin-notes.md` and `Local/quality-goal/dragon-skin-20261118/manifest.json`.
