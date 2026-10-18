#!/usr/bin/env python3
"""Build the native project with a reproducible, embedded source identity.

Does not launch an editor, renderer, listener or game. Build receipts and logs
stay local; subsequent runtime evidence can name the embedded source SHA256.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "Unreal" / "Veyr"


def snapshot():
    files = [PROJECT / "Veyr.uproject"]
    for name in ("Source", "Config", "Content"):
        folder = PROJECT / name
        if folder.exists():
            files.extend(p for p in folder.rglob("*") if p.is_file())
    return {str(p.relative_to(PROJECT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(files)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", required=True, type=Path)
    parser.add_argument("--target", choices=("VeyrEditor", "Veyr"), default="VeyrEditor")
    parser.add_argument("--configuration", choices=("Development", "Shipping"), default="Development")
    args = parser.parse_args()
    build_tool = args.engine.resolve() / "Engine/Build/BatchFiles/Mac/Build.sh"
    if not build_tool.is_file():
        parser.error("Installed native Mac Build.sh not found")
    before = snapshot()
    identity = hashlib.sha256(json.dumps(before, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    generated = PROJECT / "Intermediate/VeyrBuild/VeyrGeneratedIdentity.h"
    generated.parent.mkdir(parents=True, exist_ok=True)
    generated.write_text('#pragma once\n#define VEYR_SOURCE_ID TEXT("' + identity + '")\n')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    evidence = ROOT / "Local" / ("unreal-build-" + stamp)
    evidence.mkdir(exist_ok=False)
    command = [str(build_tool), args.target, "Mac", args.configuration,
               str(PROJECT / "Veyr.uproject"), "-NoUBA", "-NoXGE", "-NoFASTBuild",
               "-NoSNDBS", "-MaxParallelActions=4", "-NoHotReloadFromIDE"]
    log = evidence / "build.log"
    print("Build log:", log, flush=True)
    with log.open("w") as stream:
        result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
    unchanged = snapshot() == before
    text = log.read_text(errors="replace")
    success = result.returncode == 0 and "Result: Succeeded" in text and unchanged
    binaries = {str(p.relative_to(PROJECT)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted((PROJECT / "Binaries/Mac").glob("libUnrealEditor-Veyr*.dylib"))}
    receipt = {"sourceId": identity, "sourceFiles": before, "sourceUnchangedDuringBuild": unchanged,
               "target": args.target, "configuration": args.configuration,
               "exitCode": result.returncode, "success": success, "binaryHashes": binaries,
               "editorLaunched": False, "nativeGameplayVerified": False}
    (evidence / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"success": success, "sourceId": identity, "receipt": str(evidence / "receipt.json")}))
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
