#!/usr/bin/env python3
"""Live local dashboard for the overnight dragon pass: GPU/CPU usage, per-move status, before/after videos.

Serves one directory read-only on localhost (index.html, status.json and media files with byte ranges)
plus /metrics.json sampled every 3 s: GPU "Device Utilization %", CPU busy %, the gpu_slot holders.
"""
import argparse
import json
import os
import re
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('directory', type=Path)
p.add_argument('--port', type=int, default=8815)
a = p.parse_args()
ROOT = a.directory.resolve(strict=True)
SLOT = Path.home() / '.cache/gpu-slot/bin/gpu_slot.sh'
history, lock = [], threading.Lock()
TYPES = {'.html': 'text/html; charset=utf-8', '.json': 'application/json', '.mp4': 'video/mp4', '.png': 'image/png', '.jpg': 'image/jpeg'}


def sample():
    while True:
        gpu = cpu = None
        holders = []
        try:
            out = subprocess.run(['ioreg', '-r', '-c', 'IOAccelerator', '-d', '1'], capture_output=True, text=True, timeout=5).stdout
            m = re.search(r'"Device Utilization %"=(\d+)', out)
            gpu = int(m.group(1)) if m else None
        except Exception:
            pass
        try:
            out = subprocess.run(['top', '-l', '2', '-n', '0', '-s', '1'], capture_output=True, text=True, timeout=8).stdout
            idle = re.findall(r'([\d.]+)% idle', out)
            cpu = round(100 - float(idle[-1]), 1) if idle else None
        except Exception:
            pass
        try:
            out = subprocess.run([str(SLOT), 'status'], capture_output=True, text=True, timeout=8).stdout
            holders = [re.sub(r'\s+', ' ', l.strip())[:140] for l in out.splitlines() if 'label=' in l]
        except Exception:
            pass
        with lock:
            history.append({'t': time.time(), 'gpu': gpu, 'cpu': cpu, 'holders': holders})
            del history[:-400]
        time.sleep(3)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send_bytes(self, body, ctype, code=200, extra=None):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = self.path.split('?', 1)[0]
        if path == '/metrics.json':
            with lock:
                body = json.dumps(history[-200:]).encode()
            return self.send_bytes(body, 'application/json')
        name = 'index.html' if path == '/' else path.lstrip('/')
        target = (ROOT / name).resolve()
        if not target.is_relative_to(ROOT) or not target.is_file() or target.suffix not in TYPES:
            return self.send_bytes(b'not found', 'text/plain', 404)
        size = target.stat().st_size
        rng = self.headers.get('Range')
        if rng and target.suffix == '.mp4':
            m = re.match(r'bytes=(\d*)-(\d*)', rng)
            start = int(m.group(1) or 0)
            end = int(m.group(2)) if m.group(2) else size - 1
            end = min(end, size - 1)
            with open(target, 'rb') as fh:
                fh.seek(start)
                body = fh.read(end - start + 1)
            return self.send_bytes(body, TYPES[target.suffix], 206,
                                   {'Content-Range': f'bytes {start}-{end}/{size}', 'Accept-Ranges': 'bytes'})
        return self.send_bytes(target.read_bytes(), TYPES[target.suffix], 200, {'Accept-Ranges': 'bytes'})


threading.Thread(target=sample, daemon=True).start()
print('Dashboard on http://127.0.0.1:%d serving %s' % (a.port, ROOT), flush=True)
ThreadingHTTPServer(('127.0.0.1', a.port), Handler).serve_forever()
