#!/usr/bin/env python3
"""Run a Blender Python file (optionally prefixed with 'NAME=value' assignments) in MY session (owner guard, port 9886).
usage: dr.py <script.py> [prefix-python]   prints RES lines (or the error)."""
import json, socket, sys
from pathlib import Path
OWNER, PORT = 'fable-veyr-knight-walk-20261021', 9886
code = (sys.argv[2] + '\n' if len(sys.argv) > 2 else '') + Path(sys.argv[1]).read_text()
guard = f"import bpy\nassert bpy.context.scene.get('session_owner') == {OWNER!r}, 'Foreign Blender session'\n"
with socket.create_connection(('127.0.0.1', PORT), timeout=10) as sock:
    sock.settimeout(1800); sock.sendall(json.dumps({'type': 'execute_code', 'params': {'code': guard + code}}).encode()); data = b''
    while True:
        part = sock.recv(1 << 16)
        if not part: raise RuntimeError('Blender disconnected')
        data += part
        try: r = json.loads(data); break
        except (json.JSONDecodeError, UnicodeDecodeError): continue
txt = r.get('result', {}).get('result', '') if isinstance(r.get('result'), dict) else str(r.get('result', ''))
if r.get('status') == 'error': print(json.dumps(r)[-5000:]); sys.exit(1)
lines = [l for l in txt.splitlines() if l.startswith('RES')]
print('\n'.join(lines) if lines else txt[-3000:])
