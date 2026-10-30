# Dragon "rise from lying" start picture (2026-10-29/30)

Start picture for `Local/video2rig/dragon/clips/rise_lying.prompt.txt`: the collapse clip's end pose, same cameras as the standing ground picture.

- PNG: `/Users/midir/dragon-boss-fight/Local/video2rig/dragon-lying/start/start.png` (1920x1080, front 840 px | side 1080 px, 4 px divider)
- Cameras: `Local/video2rig/dragon-lying/start/cameras.json`, identical (parsed JSON equal) to `Local/video2rig/dragon/start/cameras.json`: orthographic, ortho height 1.2735, floor z = 0, hover 0.
- Project: `Local/video2rig/dragon-lying/` (`creature.json` copied from `dragon/creature.json`, `"floor": 0.0` plus a `note`; `render_start.log`).
- Pose: `Local/video2rig/dragon/Dragon_Collapse_sd_v2r_v4.blend`, Action `collapse_v4` (range 0-144, 24 fps), frame 144 = last frame.
- Wrapper (renderer unchanged): `tools/dragon_refine/v4/render_start_lying.py`. It sets the frame (default = last frame of the active Action), prints the contact numbers, then runs `Local/video2rig/dragon-air/render_start_air.py` unchanged via runpy.

## Command (run from `Local/video2rig/dragon`)

```
~/.cache/gpu-slot/bin/gpu_slot.sh capture --label dragon-rise-start -- /Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup Dragon_Collapse_sd_v2r_v4.blend --python /Users/midir/dragon-boss-fight/tools/dragon_refine/v4/render_start_lying.py -- --out /Users/midir/dragon-boss-fight/Local/video2rig/dragon-lying/start --cameras-from /Users/midir/dragon-boss-fight/Local/video2rig/dragon/start/cameras.json --floor-z 0 --facing +X --widths 840,1080
```

`--facing +X` (creature.json facing) and `--widths 840,1080` (the ground cameras' panel widths) are required: auto-facing fails on the lying pose (no foot direction) and `--cameras-from` asserts the panel widths. The slot wait was 145 s (cap full: ml + unreal-game clients); no 75 exit.

## Contact check (evaluated mesh at frame 144, world units; floor plane z = 0)

- lowest vertex z = **0.0015** (x=-0.362, y=0.039; belly/hind end); 0 vertices below z=-0.0001; 173 vertices within 1 cm of the floor
- head/chin region (front 15% of body length along +X): lowest z = 0.0142
- bbox x[-0.499, 0.705] y[-0.306, 0.357] z[0.001, 0.273]
- Nothing is below the floor. Belly and chin rest on the floor (belly 1.5 mm, chin 14 mm above it, 1.4 cm is about 1.5% of the standing height); visually in the render the chin is down on the floor.

## Caveats

- The ground picture is the ortho one in `dragon/start/`. `dragon-air/start-ground/cameras.json` is a different set (perspective lens 50 mm); it was not used. If the lying clip must use that one, add `--cameras-from .../dragon-air/start-ground/cameras.json` (same wrapper, `--widths` as in that file).
- Because the cameras are the standing ones, the lying dragon is small in the frame (about 0.27 high in a 1.27 tall view) and the far wing tip next to the head is cut by the left edge of the side panel (body x max 0.705 vs the side view's +-0.635). The head itself is fully inside.
- No Seedance/Higgsfield clip was generated. Nothing committed.
