# Veyr asset review

A laptop-local Three.js viewer for the active Cathedral Pass source GLBs. It shows
Knight v015, Dragon v007, boat greatsword v004, and the four cathedral pieces.
Each animation GLB contains its own skinned model and clip. The viewer loads one
file at a time, with orbit, scrub, speed, loop, wireframe, and bone controls.
Knight previews attach the separate boat greatsword to the right hand. The
standing idle review holds that sword slightly downward for clearance.

The browser and renderer run on the laptop. `server.py` binds only to
`127.0.0.1`; it reads the selected GLB from the Studio over the existing SSH
connection and caches it in `.asset-cache/`. It never starts Unreal or a game
on the Studio. This is a GLB preview, not proof of how Unreal renders a clip.

```sh
cd tools/asset-review
npm ci --ignore-scripts
python3 server.py \
  --studio-host studio \
  --studio-root /Users/midir/Documents/Codex/2026-10-17/task-3 \
  --port 8765
```

Open `http://127.0.0.1:8765/` in Chrome on the laptop. Stop the server with
Ctrl-C in its owning session. The model cache can be removed after review.

## Standing one-hand idle review

`tools/art/author_knight_idle_review.py` makes a four-second breathing clip
from the animation-free Knight v015 rig. It preserves the source geometry,
bind data, arm and hand transforms, and planted legs. It moves the upper chest
and shoulders with a closed inhale/exhale cycle. The script refuses to replace
an existing output:

```sh
python3 tools/art/author_knight_idle_review.py \
  --source tools/asset-review/.asset-cache/knight/KnightRig.glb \
  --output tools/asset-review/.asset-cache/review/IdleOneHand_Breathing_v1.glb
```

Open `http://127.0.0.1:8765/#review%2FIdleOneHand_Breathing_v1.glb` after
restarting the viewer server. This is a local review clip; the accepted build
and Studio authoring assets remain unchanged. It needs a separate native Unreal
preview before replacing the active idle in the game.
