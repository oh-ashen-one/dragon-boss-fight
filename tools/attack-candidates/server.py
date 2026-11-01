#!/usr/bin/env python3
"""Serve only the owner-facing candidate page and its public source ledger."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parent

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        routes = {'/': ('index.html', 'text/html; charset=utf-8'),
                  '/candidates.json': ('candidates.json', 'application/json')}
        if self.path not in routes:
            self.send_error(404); return
        file, mime = routes[self.path]
        payload = (ROOT / file).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers(); self.wfile.write(payload)
    def log_message(self, *_):
        pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8807)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('localhost', args.port), Handler)
    print('Knight attack candidate page ready', flush=True)
    server.serve_forever()
