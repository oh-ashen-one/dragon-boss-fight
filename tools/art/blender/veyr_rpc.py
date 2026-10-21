"""Execute a supplied Blender Python file on this task's loopback MCP port."""
import json
import os
from pathlib import Path
import socket
import sys

code = Path(sys.argv[1]).read_text() if len(sys.argv) > 1 else "import bpy; print(dict(bpy.context.scene.items()))"
owner = os.environ.get('VEYR_BLENDER_OWNER', 'codex-veyr-walk-20261021')
guard = f"import bpy\nassert bpy.context.scene.get('session_owner') == {owner!r}, 'Foreign Blender session'\n"
with socket.create_connection(('127.0.0.1', int(os.environ.get('VEYR_BLENDER_PORT', '9881'))), timeout=10) as sock:
    sock.settimeout(180)
    sock.sendall(json.dumps({'type': 'execute_code', 'params': {'code': guard + code}}).encode())
    data = b''
    while True:
        part = sock.recv(65536)
        if not part:
            raise RuntimeError('Blender disconnected before completing response')
        data += part
        try:
            result = json.loads(data)
            break
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
print(json.dumps(result, indent=2))
if result.get('status') == 'error':
    raise SystemExit(1)
