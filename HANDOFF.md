# Current handoff — six Knight Blender rebuilds, 2026-10-21

The six previously approved Knight motions have new **owner-approved Blender v1 versions**.
Authoring ran in the handed-off Veyr Blender MCP session on the verified Studio.
The session exited cleanly after saving and archiving the scenes; no new engine
is running for this pass. Start a fresh owned Blender session under the GPU
protocol for further authoring. The old PID/port notes below are historical.

- Public source branch: `codex/veyr-asset-review-20261019`; implementation commit `df2a422`.
- Active Studio checkout: `/Users/midir/Documents/Codex/2026-10-18/go/work/veyr-asset-review`.
- Detailed authoring, controls, tests and limitations: `tools/art/blender/rebuild/README.md`.
- Private branch: `oh-ashen-one/veyr-animation-sources`, `codex/knight-approved-blender-rebuild-20261021`, commit `85fa979`.
- Private release: `knight-approved-blender-v1-20261021`; GitHub reports both assets uploaded.
- Archive: `Veyr-Knight-Blender-Rebuild-v1.zip`, 1,172,460,045 bytes.
- SHA256: `b69a548b1fbefff017bc8af1871fe612b800a4be4fdad8f7f770f29df6b00961`; GitHub asset digest matches.
- 351 asset files verified against the archive manifest; six review films decode and match approved durations.
- All six GLBs pass independent 120 Hz checks. Full-length Blender three-view renders and pose sequences are available.
- Source/approved GLBs, original references and walk v3 remain preserved. The owner approved all six on 2026-10-21; Unreal integration is still pending.
- Local viewer: `python3 tools/asset-review/server.py --local-only --port 8774` (14 entries).

The editable sources are under `Local/Blender/approved-rebuild-20261021` after
restoring the private archive. Owner-facing films, review HTML, ZIP and checks
are under the chat's `outputs/knight-blender-review` directory. No main merge.
The two-hand walk v3 is still separately unapproved. Other existing runtime motions not covered by this six-clip batch: locomotion (walk/run/backpedal/left/right strafe), one-hand heavy attack, guards in both stances, jump, heal, stagger and death. The owner previously praised the roll; preserve it. Next review: the existing walk v3. Dragon review is requested one animation at a time after remaining Knight scope is settled. The earlier handoff below documents the preceding walk-review state.

---

# HANDOFF — Veyr Knight animation review

Date: 2026-10-21 · Branch: `codex/veyr-asset-review-20261019` · Written on laptop `Mac-106` / `Mac17,2` · Status: **ready to resume; walk v3 awaits owner review**

## What this is

Hari is reviewing the Knight's motions one at a time in Chrome on localhost.
The current work is a two-hand ready walk: hunched shoulders, full-body breathing,
weight shift through the hips/knees/feet, and responsive arms holding the sword.
Hari explicitly required Blender for character animation authoring/refinement
and asked to persist that rule. Scripts may automate Blender and check results;
external scripted joint transforms alone are not the authoring workflow.

Approved: one-hand idle, two-hand idle, one-hand overhead attack, two faster
strong attacks, and two-hand light attack. Preserve those exact clips and timing.
Walk v1 was rejected as stiff. V2 and Blender v3 are NOT approved.
Detailed approvals/hashes: [motion ledger](tools/asset-review/HANDOFF.md).
Historical game build handoff is preserved in
[docs/handoffs/HANDOFF-cathedral-build-20261019.md](docs/handoffs/HANDOFF-cathedral-build-20261019.md).

## Repo / branch map

| Repository | Branch / artifact | Purpose |
|---|---|---|
| `oh-ashen-one/veyr-cinder-warden` (public) | `codex/veyr-asset-review-20261019` | Code, viewer, Blender authoring scripts, checks and this handoff |
| `oh-ashen-one/veyr-animation-sources` (private) | `codex/knight-blender-handoff-20261021`; release `knight-blender-walk-v3-20261021` | Editable `.blend`, model/clip files, reference frames, checksums |
| `oh-ashen-one/agents-md` (private) | `codex/blender-animation-rule-20261021`, commit `e5330b7` | Tested Blender-first global rule; pushed, NOT merged to main |

Current laptop checkout:
`/Users/darkeatermidir/Documents/Codex/2026-10-19/veyr-asset-review`.
Only one worktree was listed for this repository and there are no stashes.
No main merge is authorized. This handoff request does not resolve the separate
pending approval to merge the shared-brain rule.

## Where things stand

- Animation implementation commit: `4c28e2812267007981cd49922beb99fa8149c37e`.
- `WalkTwoHand_Blender_v3.glb`: 3.5 seconds / 60 fps / 211 samples.
  SHA256 `d0713bac27cd87f6d5ed34eebb2c10a4bc6d1011a125bbe30f65bda405cd3c3d`.
- Blender 5.2.0 LTS scene has preserved reference action, editable pelvis/torso/
  breath/hilt controls, native four-limb IK, calibrated pole angles and baked
  deform animation. The deform rig's rest bones/skin were not reauthored.
- Scene SHA256 `b37a8e36dfcc1c1edb8c3df6289ae74a746ab8538f9c571fcb3d260b1fda20e9`.
- The previous work turn rendered front, side and three-quarter poses, corrected
  an elbow bend-plane mismatch, and verified the exported character/sword in
  Chrome at 1x. This handoff turn rechecked hashes and restored the bundle fresh.
- The Blender rule is active in project `AGENTS.md`; a local Codex memory update
  was also requested and saved. Other clients should follow the committed project
  instructions; local Codex memory does not travel with this repository.

## What changed for this handoff

- The public root handoff now routes to this active animation thread; the older
  game build handoff was archived without deleting its content.
- The private GitHub snapshot includes 325 files: editable Blender scene,
  reference Knight body, six approved clips, both sword grips, walk v1/v2/v3,
  original strong-attack timings, and the existing reference frames.
- `restore_review_bundle.py` validates every SHA256 before writing anything and
  refuses to overwrite differing existing files.
- `server.py --local-only` starts the review without Studio SSH or the Unreal
  project. Only the restored active Knight review assets are required.
- External Blender scripts now accept relocated Studio paths through
  `VEYR_BLENDER_WORK`, `VEYR_REVIEW_ASSETS` and `VEYR_BLENDER_ADDON`.

## Verification

This turn: restored all 325 files to a new temporary directory; started its
server with `--local-only` on port 8766; catalog returned all 8 views; fetched
walk and body over HTTP and matched their expected SHA256 hashes. Studio SSH
was not used by that test server. Python compilation and JavaScript syntax
checks pass. The temporary test server is stopped after verification.

Prior recorded checks: exported GLB sampled independently at 120 Hz; palm drift
<0.000789 rig units, stance-foot frame drift <0.000021, maximum local rotation
step <3.366 degrees per 60 Hz sample; Blender idle endpoint matrix errors
<2.3e-6. Reports: `tools/asset-review/reviews/blender-walk-v3-*.json`.
Shared-brain change passed 52 tests and catalog validation in the preceding turn.

## Not done / out of scope

- Owner has not approved walk v3. It is a start/walk/stop study, NOT a seamless
  locomotion cycle; looping resets the root after 0.72 rig units of travel.
- No Unreal import, rebuild, new installed game, or native-engine playtest.
- No modifications to approved clips, no public redistribution of private assets.
- Shared-brain rule awaits explicit permission for a main merge. Do not claim
  it is globally published merely because its task branch is pushed.
- Full simultaneous-render stress testing was not done. `powermetrics` needed
  sudo authentication; IOAccelerator samples were available and recorded.

## Resume on another machine

Use GitHub access to the owner's private repositories, Git, Python 3.11+, Node/npm,
and `gh`. Clone into a new directory; do not repurpose another session's checkout.

```sh
git clone --filter=blob:none --branch codex/veyr-asset-review-20261019 \
  https://github.com/oh-ashen-one/veyr-cinder-warden.git veyr-asset-review
cd veyr-asset-review
mkdir -p /tmp/veyr-handoff
gh release download knight-blender-walk-v3-20261021 \
  --repo oh-ashen-one/veyr-animation-sources --dir /tmp/veyr-handoff \
  --pattern 'Veyr-Knight-Blender-Handoff-20261021.zip' --pattern SHA256SUMS
(cd /tmp/veyr-handoff && shasum -a 256 -c SHA256SUMS)
python3 tools/asset-review/restore_review_bundle.py \
  /tmp/veyr-handoff/Veyr-Knight-Blender-Handoff-20261021.zip
npm ci --prefix tools/asset-review
python3 tools/asset-review/server.py --local-only --port 8765
```

Open in Chrome:
`http://127.0.0.1:8765/?review=blender-walk-v3#review%2FWalkTwoHand_Blender_v3.glb`.
Select **Body**, play at **1x**, then review the walk with Hari.
Archive: 517156410 bytes; SHA256
`c4ae59ee7da0b7d6737ab35bdd0b5ebfd12c8bf0d1f872c85066baedf8f70a61`.
The scene restores to `Local/Blender/Knight_Walk_Blender_v3.blend`.
The review cache restores to `tools/asset-review/.asset-cache`.

Heavy authoring stays on a verified Studio. To revise: preserve v3, create a
new versioned scene/export, edit the four Blender control actions and rebake
with `tools/art/blender/refine_knight_walk.py`. Run the export audit and inspect
full-body playback at intended speed before requesting owner approval. See
[Blender workflow](tools/art/blender/README.md) for commands and caveats.

## Processes / ownership

At verification: Studio `studio` is `Mac` / `Mac15,14`. This task's Blender PID
28574, owner tag `codex-veyr-walk-20261021`, loopback MCP port 9881, work folder
`/Users/midir/veyr-blender-walk-20261021`. Its editable scene and v3 export hashes
were rechecked this turn. Hari's requested handoff authorizes the receiving
Veyr session to continue this task-owned instance after verifying its owner tag
and live PID. Never assume recorded PIDs are still current.

Foreign Blender PIDs 27849 and 27888 were left untouched. Do not use their ports
or files. Shared GPU rule published at brain main `ba35669`: Blender-only cap 4,
mixed engine cap 2, shared slot lock required. Verify current policy and process
state before launch. The task Blender has a four-hour slot lease; do not assume
it will remain alive indefinitely. Do not start a second Veyr Blender while the
handed-off one is still running.

Laptop review server is task-owned on 127.0.0.1:8765. It is a foreground process
held by the tool session, not a LaunchAgent. New machines start their own server.
No new account secrets, authentication stores or terminal sessions were copied.

## Gotchas / local-only remainder

- Public repository excludes private models by design. Cloning code alone is
  insufficient; download and restore the private release above.
- The archived blend's embedded scripts retain original Studio absolute paths.
  Use current repository scripts and the documented environment variables when
  moving to a different host. The existing scene is editable without rerunning
  the initial import. Never run `prepare_knight_walk.py` over existing work.
- Hand attachment is animated `ReviewWeaponSocket`; the browser adds the preserved
  strong-grip sword. Do not add a second sword to the exported body GLB.
- Blender pole-angle conventions differed from the glTF bone axes; calibration
  in the refinement script is required to avoid bent/twisted elbows.
- `node_modules`, transient logs/QA images, unrelated rejected historical assets,
  the installed game ZIP/app and the running process state were not bundled.
  The complete current animation review and editable scene ARE in the private
  release. The historical Unreal build remains a separate workflow.

## Resume instruction

Clone `oh-ashen-one/veyr-cinder-warden` on branch
`codex/veyr-asset-review-20261019`, read root `HANDOFF.md`, restore the private
Knight bundle, and continue the Blender two-hand walk review without changing
approved animations.
