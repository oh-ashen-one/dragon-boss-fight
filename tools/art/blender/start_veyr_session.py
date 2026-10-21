"""Run in a new Studio Blender instance; never attach to foreign sessions."""
import importlib.util
import os
from pathlib import Path
import sys
import bpy

ROOT = Path(os.environ['VEYR_BLENDER_WORK'])
PORT = int(os.environ.get('VEYR_BLENDER_PORT', '9881'))
OWNER = os.environ.get('VEYR_BLENDER_OWNER', 'codex-veyr-walk-20261021')
spec = importlib.util.spec_from_file_location('veyr_isolated_mcp', os.environ.get('VEYR_BLENDER_ADDON', '/Users/midir/blender-mcp-work/addons/blender_mcp.py'))
addon = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = addon
spec.loader.exec_module(addon)
real_start = addon.BlenderMCPServer.start
addon.BlenderMCPServer.start = lambda self: None
addon.register()
addon.BlenderMCPServer.start = real_start
if hasattr(bpy.types, 'blendermcp_server'):
    del bpy.types.blendermcp_server
bpy.context.scene.blendermcp_port = PORT
bpy.types.blendermcp_server = addon.BlenderMCPServer(host='127.0.0.1', port=PORT)
bpy.types.blendermcp_server.start()
bpy.context.scene.blendermcp_server_running = True
bpy.context.scene['session_owner'] = OWNER
bpy.context.scene['mcp_port'] = PORT
ROOT.joinpath('ready.txt').write_text(f'{OWNER} port={PORT} pid={os.getpid()}\n')
print(f'VEYR_BLENDER_READY owner={OWNER} port={PORT}', flush=True)
