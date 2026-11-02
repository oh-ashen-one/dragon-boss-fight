#!/usr/bin/env python3
"""Local review server with byte ranges required by Safari media playback."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*args): pass
    def send_head(self):
        self.remaining=None
        path=Path(self.translate_path(self.path))
        if path.is_file() and self.headers.get('Range'):
            match=re.fullmatch(r'bytes=(\d+)-(\d*)',self.headers['Range'])
            size=path.stat().st_size
            if not match:self.send_error(416);return None
            start=int(match[1]);end=min(int(match[2]) if match[2] else size-1,size-1)
            if start>end:self.send_error(416);return None
            stream=path.open('rb');stream.seek(start);self.remaining=end-start+1
            self.send_response(206);self.send_header('Content-Type',self.guess_type(str(path)))
            self.send_header('Content-Length',str(self.remaining));self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
            self.send_header('Accept-Ranges','bytes');self.end_headers();return stream
        return super().send_head()
    def copyfile(self,source,output):
        if self.remaining is None:return super().copyfile(source,output)
        try:
            while self.remaining:
                chunk=source.read(min(self.remaining,1024*1024))
                if not chunk:break
                output.write(chunk);self.remaining-=len(chunk)
        except (BrokenPipeError,ConnectionResetError):pass
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--port',type=int,default=8810);a=p.parse_args()
    ThreadingHTTPServer(('localhost',a.port),partial(Handler,directory=str(a.directory.resolve()))).serve_forever()
