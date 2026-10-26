# Veyr local storage cleanup — 2026-10-26

Owner requested removal of excess local renditions and temporary storage after delivery.
The cleanup ran on `Fab-3D-Rig-Testing` after its work was pushed at `8f203f8`.

Removed 99.50 GiB of allocated file footprint across 33,883 targets. Actual free
space increased by **82.70 GiB**, from 40.42 to 123.13 GiB during deletion. APFS
shared blocks and concurrent activity mean these are different measurements.
No deletion errors occurred. See `result.json` for category totals and checks.

Removed repeated packaged builds, obsolete Downloads deliveries, duplicate ZIPs
and staging copies, rejected animation fits, automatic Blender backups, bulk test
PNG frames, temporary rig files and duplicate compiler outputs. Tracked project
files were excluded. The current app, final editable sources, current engine assets,
reviewer inputs, original guard and personal recordings were preserved.

Both final gameplay captures were retained as compact, full-decode-verified videos:
- `Local/FabRigTesting/Packaged-Stance-a2e260.mp4`
- `Local/FabRigTesting/Packaged-Victory-a2e260.mp4`

First/last test frames and selected contact/integration frames remain alongside JSON
results. Historical `frames.jsonl` records still describe the original captures;
most corresponding PNGs were intentionally removed and cannot be re-encoded from
those lists alone. Build receipts also describe historical local paths that were
removed. The playable app remains in `~/Downloads/Veyr-Sourced-Animations-v027/`.

Private backups were verified before cleanup in `oh-ashen-one/veyr-animation-sources`:
- `sourced-animation-authoring-20261025`: final editable animation source archive.
- `sourced-animation-game-v027`: native delta and signed game ZIP.
- `fab-rig-testing-20261025`: original sourced comparison archive.

Use the existing receipt/acquisition instructions for restoration. Restricted raw
assets remain excluded from the public code repository. The compact local deletion
ledger is `Local/storage-cleanup/deleted-files.jsonl.gz`.

After cleanup: 97 retained files passed before/after SHA-256 comparison; no tracked
file changed; the final app passed deep strict signature verification and its
existing owner-review process remained alive. Both localhost viewers returned
HTTP 200 and passed all asset inventory checks (8777: 5 pairs/26 files; 8776:
8 candidates/20 routes). Cleanup did not perform another gameplay test.
