"""Remove unused imported datablocks from this test's editable Blender scenes."""
import bpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
assert bpy.context.scene.get('session_owner')=='codex-veyr-fab-rig-testing'
for p in sorted((ROOT/'Local/FabRigTesting/Exports').glob('*.blend')):
 bpy.ops.wm.open_mainfile(filepath=str(p),load_ui=False)
 for a in bpy.data.actions:
  if a.use_fake_user and a.users==1:a.use_fake_user=False
 bpy.data.orphans_purge(do_local_ids=True,do_linked_ids=False,do_recursive=True)
 bpy.ops.wm.save_as_mainfile(filepath=str(p),compress=True)
 print(p.name,p.stat().st_size)
