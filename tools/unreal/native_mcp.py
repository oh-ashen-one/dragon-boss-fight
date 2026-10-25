#!/usr/bin/env python3
"""Small client for Epic's installed native MCP HTTP server, not a server/bridge.

Discover schemas with --list before constructing a --request tools/call JSON.
Requires an explicitly started task-owned editor on localhost:18773.
Does not start processes, change configuration, or retry mutating calls.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


class NativeMCP:
    def __init__(self, timeout=60):
        self.url = "http://127.0.0.1:18773/mcp"
        self.session = None
        self.version = "2025-06-18"
        self.sequence = 0
        self.timeout = timeout

    def request(self, method, params=None, notification=False):
        self.sequence += 1
        payload = {"jsonrpc": "2.0", "method": method}
        if not notification:
            payload["id"] = self.sequence
        if params is not None:
            payload["params"] = params
        headers = {"Content-Type": "application/json",
                   "Accept": "application/json, text/event-stream"}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
            headers["MCP-Protocol-Version"] = self.version
        request = urllib.request.Request(self.url, json.dumps(payload).encode(), headers)
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            self.session = response.headers.get("Mcp-Session-Id", self.session)
            content_type = response.headers.get("Content-Type", "")
            if "text/event-stream" in content_type:
                # Native long-running tools return progress notifications before
                # their final response. Preserve only the matching JSON-RPC result.
                for raw_line in response:
                    line = raw_line.decode().strip()
                    if line.startswith("data:"):
                        item = json.loads(line[5:].strip())
                        if item.get("id") == payload.get("id"):
                            return item
                raise RuntimeError("Native MCP stream ended without a final response; do not retry writes blindly")
            raw = response.read()
            return json.loads(raw) if raw else None

    def initialize(self):
        result = self.request("initialize", {
            "protocolVersion": self.version,
            "capabilities": {},
            "clientInfo": {"name": "veyr-native-client", "version": "0.1.0"},
        })
        if "error" in result:
            raise RuntimeError(result["error"])
        self.version = result["result"]["protocolVersion"]
        self.request("notifications/initialized", notification=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--list", action="store_true", help="Discover native MCP tools and input schemas")
    mode.add_argument("--request", type=Path, help="JSON tools/call params constructed from discovered schema")
    args = parser.parse_args()
    client = NativeMCP()
    client.initialize()
    if args.list:
        result = client.request("tools/list", {})
    else:
        params = json.loads(args.request.read_text())
        if not isinstance(params, dict) or not isinstance(params.get("name"), str):
            parser.error("Request must contain a native MCP tool name and its arguments")
        result = client.request("tools/call", params)
    print(json.dumps(result, indent=2))
    if result and ("error" in result or result.get("result", {}).get("isError")):
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
