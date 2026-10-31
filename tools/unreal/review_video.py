#!/usr/bin/env python3
"""Serve a bare, local before/after page with seekable video and no directory listing."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
from urllib.parse import urlsplit

PAGE = b'''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Veyr</title><style>body{margin:0;background:#090b0e;color:#d8d9dc;font:14px system-ui}
main{max-width:1440px;margin:24px auto;display:grid;gap:24px;padding:16px}
figure{margin:0}figcaption{margin:0 0 8px;font-size:12px;letter-spacing:.15em}
video{width:100%;background:#000} @media(min-width:1100px){main{grid-template-columns:1fr 1fr}}</style>
<main><figure><figcaption>BEFORE</figcaption><video controls playsinline preload="metadata" src="/before.mp4"></video></figure>
<figure><figcaption>AFTER</figcaption><video controls playsinline preload="metadata" src="/after.mp4"></video></figure></main>'''


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_HEAD(self):
        self.respond(False)

    def do_GET(self):
        self.respond(True)

    def respond(self, body):
        path = urlsplit(self.path).path
        if path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(PAGE)))
            self.end_headers()
            if body:
                self.wfile.write(PAGE)
            return
        file = self.server.routes.get(path)
        if file is None:
            self.send_error(404)
            return
        size = file.stat().st_size
        start, end = 0, size - 1
        requested = self.headers.get("Range")
        if requested:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", requested)
            if not match or not any(match.groups()):
                self.send_error(416)
                return
            left, right = match.groups()
            if left:
                start = int(left)
                end = min(int(right), size - 1) if right else size - 1
            else:
                start = max(0, size - int(right))
            if start > end or start >= size:
                self.send_error(416)
                return
        self.send_response(206 if requested else 200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        if requested:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if body:
            try:
                with file.open("rb") as stream:
                    stream.seek(start)
                    remaining = end - start + 1
                    while remaining:
                        chunk = stream.read(min(remaining, 1024 * 1024))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--port", type=int, default=8797)
    args = parser.parse_args()
    if not all(p.is_file() for p in (args.before, args.after)):
        parser.error("Both videos must exist")
    server = ThreadingHTTPServer(("localhost", args.port), Handler)
    server.routes = {"/before.mp4": args.before.resolve(), "/after.mp4": args.after.resolve()}
    print("Veyr video review ready", flush=True)
    server.serve_forever()
