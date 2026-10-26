> Update: the owner selected game integration after this initial comparison. See [the native integration record](../sourced-native-20261025/README.md). The material below preserves the initial review milestone.

# Fab 3D Rig Testing

Separate review-only branch `Fab-3D-Rig-Testing`, based on `327d3ac`.
Owner requested before/after comparisons on the existing knight, explicitly without
integrating anything into the game. No Unreal Content, Source, Config, gameplay,
installed app, or original review animation was edited.

## Delivered comparison

http://127.0.0.1:8777/ — five pairs, same knight and complete boat greatsword.

| Pair | Current version | Downloaded base |
| --- | --- | --- |
| Walk | Approved one-hand walk | Mixamo Sword and Shield Walk |
| Attack | Blender reference-led overhead light attack | Mixamo Sword and Shield Slash |
| Guard | Idle to two-hand sword guard | Mixamo Sword and Shield Block |
| Run | Tripo-based run with Blender two-hand grip | VanillaLoop A_RunFwd_Loop |
| Roll | Current Blender-refined roll | VanillaLoop A_Roll_IdleFwd |

Controls: original timing or explicitly labeled phase matching, 1x/half/quarter
speed, shared camera, front/side/three-quarter views, pause/restart/cycle scrub,
centering toggle, sword visibility, full-motion fit and body-detail framing.
Single-shot attacks/blocks/rolls repeat for review; repetition is not a claim that
they are seamless gameplay loops. Source meshes are not substituted for the knight.

## Access test and provenance

- Browser control succeeded in Chrome on both Fab and Mixamo. Mixamo's existing
  Adobe SSO completed without new credentials. Downloaded the Sword and Shield
  Pack as FBX Binary, T-pose,30fps, no keyframe reduction, through the normal UI.
- Fab's VanillaLoop free sample had an earlier browser Save dialog outstanding
  from the idle comparison chat. Saved that pending download into this isolated
  test folder, then saved the new Mixamo download there too. Browser download UI
  and filesystem both confirmed completion. No security check was bypassed.
- Fab provides a Unity package download containing ordinary FBX files; extracted
  them as data without opening Unity. Unreal-format downloads otherwise use Epic
  Launcher/Fab integration, per Epic's documentation.
- No dedicated Fab/Mixamo MCP appeared in the connected tool inventory. Community
  CLI/download scripts exist, but were not installed or validated here; do not
  describe them as official APIs. The supported browser route was sufficient.
- Public documentation retrieval used the agent-reach web route plus web search;
  its Exa mcporter backend was absent. No authenticated cookies/tokens extracted.

Sources and licenses:

- Mixamo / Adobe, Sword and Shield Pack (49 motions plus X Bot reference).
  https://www.mixamo.com/#/?page=1&query=sword%20and%20shield&type=Motion%2CMotionPack
  Adobe FAQ: https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html
  Free personal/commercial project use. Treat raw motion as restricted source;
  no public redistribution or standalone resale. No knight uploaded to Adobe.
- VanillaLoop, Free Sample Animation Set, Fab listing
  https://www.fab.com/listings/5b737d10-b4cd-4294-8f6b-757b9088039d
  Listing last updatedJune18,2026; free Standard License was visible in the UI.
  https://www.fab.com/eula — project use/modification in compatible tools; no
  standalone redistribution. Raw and derivative binaries stay private.
- Epic acquisition documentation:
  https://dev.epicgames.com/documentation/fab/purchasing-and-downloading-assets-in-fab

No purchases, paid generation, public asset uploads or model-training use.
Archive/selected-file hashes and output provenance are in `manifest.json`.

## Retargeting and limitations

Actual Blender5.2 native authoring through the isolated MCP port9891, owner tag
`codex-veyr-fab-rig-testing`. Anatomical rest-pose calibration maps source segment
directions onto the relaxed knight rig; FK action is baked locally. Limb-length
ratio scales pelvis motion. Linear horizontal travel is removed for stationary
walk/run studies; roll travel remains stored, with optional viewer centering.
Original finger bind/grip and existing hand-to-sword socket are retained; no new
shield or synthetic animation is supplied. Source timings: Mixamo30fps, Fab25fps.

Editable `.blend` files retain the source skeleton/action and target baked action.
The source/base poses remain editable. No Unreal import, gameplay transition,
weapon collision, damage-window or planted-foot validation is claimed.

Critic findings after preview fixes:

- Walk provides useful alert body language, but its empty shield arm differs from
  our one-hand sword stance.
- Attack has readable whole-body participation;1.5s diagonal slash versus2.8s
  overhead is a style comparison, not a controlled speed/quality ranking.
- Shield block cannot replace the two-hand face-covering sword guard unchanged.
- Run gait transfers, but unarmed arm swing needs a deliberate heavy-sword carry.
- Roll tuck/recovery transfers; boat blade crowds body/legs during mid-roll and
  needs a weapon-aware adaptation before gameplay use.

Two preview defects were fixed: disable stale frustum culling on moving skinned
meshes, and remove the extra Y-up/Z-up conversion from Blender prop attachment.
Only `Evidence/export_*` images are final exported-asset evidence; early render
folders are superseded. Critic rechecked live roll visibility at.24/.48/.72s and
matched Fab run frame7's sword orientation against the final native render.

## Restore / run

Restore the private `fab-rig-testing-20261025` release archive from
`oh-ashen-one/veyr-animation-sources` at this repository root. It includes the five
before files, five after GLBs/editable scenes, acquisition archives, vendor code,
sword and selected evidence. No public binary assets are required.

```
python3 tools/animation-comparison/server.py --check
python3 tools/animation-comparison/server.py --port 8777
```

Source extraction: `tools/art/blender/fab_rig_testing/prepare_sources.py`.
Fresh retargeting: run `run_all.py` through the owned Blender MCP; it refuses to
overwrite current candidate names. Shared GPU ownership/cap rules still apply.
`review_exports.py` renders the exact GLBs, not an alternate authoring action.
Future work should choose a source whose weapon/grip matches the desired behavior,
then fix contacts/carry and transitions before considering game integration.
