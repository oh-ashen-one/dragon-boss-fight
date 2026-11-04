#!/usr/bin/env python3
"""Serve an existing bare review page and its named movies with byte ranges."""
import argparse
import json
import os
from http.server import ThreadingHTTPServer
from pathlib import Path
import re
import review_video

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('directory', type=Path)
p.add_argument('--port', type=int, default=8813)
p.add_argument('--receipt', type=Path)
a = p.parse_args()
directory = a.directory.resolve(strict=True)
page = (directory/'index.html').read_text()
names = set(re.findall(r'''["']([^"']+\.mp4)["']''', page))
assert names, 'No movie references found'
routes = {}
for name in names:
    assert Path(name).name == name, 'Only explicit local movie basenames are served'
    movie = directory/name
    assert movie.is_file() and not movie.is_symlink()
    routes['/'+name] = movie
review_video.PAGE = page.encode()
server = ThreadingHTTPServer(('localhost', a.port), review_video.Handler)
server.routes = routes
if a.receipt:
    a.receipt.parent.mkdir(parents=True,exist_ok=True)
    a.receipt.write_text(json.dumps({'pid':os.getpid(),'port':server.server_port,'directory':str(directory),'movies':sorted(names)},indent=2)+'\n')
print('Veyr review page ready; named movies only', flush=True)
server.serve_forever()
