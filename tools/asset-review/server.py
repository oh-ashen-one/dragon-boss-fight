#!/usr/bin/env python3
"""Loopback-only Veyr GLB viewer, streaming a fixed active set over Studio SSH.

Run on the laptop. Models stay on the Studio until individually opened in the
viewer; fetched files are cached locally under .asset-cache for quick revisits.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import struct
import subprocess
import sys
import tempfile
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


HERE = Path(__file__).resolve().parent
CACHE = HERE / ".asset-cache"
REVIEW = CACHE / "review"
REMOTE_CATALOG = r'''
import json, struct, sys
from pathlib import Path
root = Path(sys.argv[1])
specs = {
    "knight": (root / "Local/CustomuseAssets/ImportSet015", "*.glb"),
    "dragon": (root / "Local/CustomuseAssets/ImportSetDragon007", "*.glb"),
    "objects": (root / "Local/art-pass-20261019/tripo", "*.glb"),
}
allowed_objects = {
    "BoatGreatsword_v4.glb", "CathedralArch_v1.glb",
    "CathedralBrazier_v1.glb", "CathedralFacade_v1.glb",
    "CathedralWall_v1.glb",
}
items = []
for group, (folder, pattern) in specs.items():
    for path in sorted(folder.glob(pattern)):
        if group == "objects" and path.name not in allowed_objects:
            continue
        if not path.is_file():
            continue
        with path.open("rb") as stream:
            header = stream.read(20)
            if len(header) < 20 or header[:4] != b"glTF":
                continue
            json_size, chunk_type = struct.unpack_from("<II", header, 12)
            if chunk_type != 0x4E4F534A:
                continue
            document = json.loads(stream.read(json_size))
        items.append({
            "id": f"{group}/{path.name}",
            "group": group,
            "name": path.stem,
            "file": path.name,
            "bytes": path.stat().st_size,
            "animationNames": [a.get("name", "Clip") for a in document.get("animations", [])],
            "remotePath": str(path),
        })
print(json.dumps(items))
'''


def ssh_command(host: str, *tokens: str) -> list[str]:
    return ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", host,
            " ".join(shlex.quote(token) for token in tokens)]


def catalog_from_studio(host: str, root: Path) -> list[dict]:
    result = subprocess.run(
        ssh_command(host, "python3", "-c", REMOTE_CATALOG, str(root)),
        text=True, capture_output=True, check=True, timeout=45,
    )
    items = json.loads(result.stdout)
    expected = {"knight", "dragon", "objects"}
    if {item["group"] for item in items} != expected:
        raise RuntimeError("The active Knight, Dragon, or object GLBs are missing on the Studio")
    return items


def local_review_items() -> list[dict]:
    """Expose only explicit, locally authored review clips; never alter Studio assets."""
    items = []
    for path in sorted(REVIEW.glob("IdleOneHand_Breathing_v*.glb")):
        with path.open("rb") as stream:
            header = stream.read(20)
            if len(header) < 20 or header[:4] != b"glTF":
                continue
            json_size, chunk_type = struct.unpack_from("<II", header, 12)
            if chunk_type != 0x4E4F534A:
                continue
            document = json.loads(stream.read(json_size))
        items.append({
            "id": f"review/{path.name}",
            "group": "knight",
            "name": path.stem,
            "file": path.name,
            "bytes": path.stat().st_size,
            "animationNames": [a.get("name", "Clip") for a in document.get("animations", [])],
            "localPath": str(path),
        })
    return items


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(HERE), **kwargs)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/catalog":
            payload = json.dumps({
                "build": "9b185634",
                "source": "Knight v015 · Dragon v007 · cathedral pass",
                "items": [{key: value for key, value in item.items() if key not in {"remotePath", "localPath"}}
                          for item in self.server.catalog],
            }).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
            return
        if path.startswith("/api/asset/"):
            asset_id = unquote(path.removeprefix("/api/asset/"))
            item = self.server.assets.get(asset_id)
            if item is None:
                self.send_error(HTTPStatus.NOT_FOUND, "Unknown asset")
                return
            self.serve_asset(item)
            return
        if path.startswith("/node_modules/"):
            # Only the pinned Three.js package is exposed to the local page.
            rel = path.removeprefix("/node_modules/")
            if not rel.startswith("three/"):
                self.send_error(HTTPStatus.NOT_FOUND)
                return
        return super().do_GET()

    def serve_asset(self, item: dict):
        group, filename = item["group"], item["file"]
        target = Path(item["localPath"]) if "localPath" in item else CACHE / group / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file() and target.stat().st_size == item["bytes"]:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "model/gltf-binary")
            self.send_header("Content-Length", str(item["bytes"]))
            self.end_headers()
            with target.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    self.wfile.write(chunk)
            return

        process = subprocess.Popen(
            ssh_command(self.server.studio_host, "cat", item["remotePath"]),
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        written = 0
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".fetch-", delete=False) as cache_file:
                temp_name = cache_file.name
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "model/gltf-binary")
                self.send_header("Content-Length", str(item["bytes"]))
                self.send_header("Cache-Control", "private, max-age=3600")
                self.end_headers()
                while chunk := process.stdout.read(1024 * 1024):
                    self.wfile.write(chunk)
                    cache_file.write(chunk)
                    written += len(chunk)
            if process.wait(timeout=5) == 0 and written == item["bytes"]:
                os.replace(temp_name, target)
                temp_name = None
            else:
                self.log_error("Incomplete Studio transfer for %s (%s/%s bytes)", item["id"], written, item["bytes"])
        except (BrokenPipeError, ConnectionResetError):
            self.log_message("Browser cancelled %s", item["id"])
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            if temp_name and os.path.exists(temp_name):
                os.unlink(temp_name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--studio-host", default="studio")
    parser.add_argument("--studio-root", required=True, type=Path)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    catalog = local_review_items() + catalog_from_studio(args.studio_host, args.studio_root)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.catalog = catalog
    server.assets = {item["id"]: item for item in catalog}
    server.studio_host = args.studio_host
    print(f"Veyr asset review: http://127.0.0.1:{args.port}/ ({len(catalog)} assets)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
