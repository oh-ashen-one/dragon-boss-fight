# Dragon skin weights: wing-root fins and left front paw (paused 2026-11-19)

Scripts in `tools/dragon_refine/` (assets stay in `Local/`, never in git):

- `skin_stretch.py` - CPU-skins every clip GLB (four influences, morph animation) and counts triangles that stretch
  more than 2 % of body height, against the clip's first frame (`--reference frame0 --no-morph`, the A123 rule) or
  against the sculpted mesh at the same morph weights (`--reference bind`). `--weights NPZ` compares a new weight set.
- `skin_smooth.py` - welded (UV-seam-safe) Laplacian weight smoothing in a region.
- `skin_fit.py` - convex fit of region weights against stretch over sampled frames of all clips.
- `skin_paw.py` - leg-0 paw weights from the mirrored leg-1 layout, toe share to the shin-locked 1_Left_Limb_1.
- `dragon_skin_fix.py` - runs fit + paw and writes the NPZ.
- `author_dragon_skin.py` - Blender: builds the editable .blend from the NPZ, reads weights back out.
- `patch_glb_weights.py` - writes GLB copies with only JOINTS_0/WEIGHTS_0 replaced.
- `render_skin_views.py` - Blender: fixed front/side/three-quarter renders for before/after sheets (through gpu_slot).

State, numbers and the next commands: `Local/quality-goal/dragon-skin-notes.md`. No fix is verified yet.
