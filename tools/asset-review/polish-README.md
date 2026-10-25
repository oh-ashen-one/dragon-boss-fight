# October 25 polish viewer

Independent loopback-only reviewer for the eight final entries in
`Local/Blender/polish-20261025/manifest.json`: three Dragon flight revisions and
five Knight run/grip/roll revisions. It does not modify or replace the earlier
reviewer on port8775, its process, catalog, or cached assets.

Run `python3 tools/asset-review/polish-server.py --check` to verify all eight
source hashes, the intact sword and the static module allowlist. Then run
`python3 tools/asset-review/polish-server.py --port 8776` headlessly.

Open `http://127.0.0.1:8776/`. Direct hover view:
`http://127.0.0.1:8776/#polish%2FDragon_FlyHover_Blender_polish_v1.glb`.

The UI has explicit Dragon/Knight groups, per-clip candidate labels, 1× playback,
scrubbing, loop toggles, front/side/three-quarter views, current-pose/full-motion
framing and a Knight hand close-up. Native Three.js morph animation remains
active. Every Knight uses the intact `BoatGreatsword_OneHand_v4.glb`, attached at
identity to its authored ReviewWeaponSocket; shaft geometry is never reduced.

Runtime cache: `Local/polish-review-20261025`. It contains the exact intact sword
(SHA256 `bfb0bd2d6580882236e499833d28564712e08ff9323d76d3c55715d0ee558ab4`)
and six JavaScript modules from the project's already pinned Three.js dependency:
`build/three.module.js`, `build/three.core.js`, GLTFLoader, OrbitControls,
BufferGeometryUtils and SkeletonUtils. The upstream license and a dependency
manifest are retained in the private cache. These files are ordinary dependency
cache, not new model assets; restore them from the same pinned npm dependency
when moving machines.

The HTTP handler serves an explicit mapping of candidate IDs, that sword, its
own HTML/JS, existing style.css and the six vendor modules. Unknown routes return
404. It never joins a request path onto the filesystem, serves directories,
executes commands, calls SSH, exposes authoring paths in the catalog or binds to
an external interface.

Validation in this pass: eight GET responses match the exact source hashes and
GLB MIME/header, source manifest hashes pass, 3Dragon/5Knight inventory matches,
unknown/directory/traversal paths return404, JavaScript/Python syntax passes.
Actual browser rendering is reserved for the parent session and is not claimed
by those HTTP checks. Native-game and owner acceptance remain separate gates.
