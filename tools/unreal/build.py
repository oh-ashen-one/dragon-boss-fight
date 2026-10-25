#!/usr/bin/env python3
"""Build the native project with a reproducible, embedded source identity.

Does not launch an editor, renderer, listener or game. Build receipts and logs
stay local; subsequent runtime evidence can name the embedded source SHA256.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil
import tempfile


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "Unreal" / "Veyr"


def run_logged(command, log, *, env=None):
    """Keep build output private and give nested tools valid standard input."""
    with os.fdopen(os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
        result = subprocess.run(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                stdout=stream, stderr=subprocess.STDOUT)
    return result.returncode


def finalize_standalone(build_tool, configuration, evidence):
    """Generate only task-owned Xcode files, then finalize outside UBA.

    Flags mirror UE 5.8 AppleToolChain.GenerateRunOnlyXcodeProject. The direct
    Xcode invocation avoids the nested launcher whose invalid descriptor stopped
    scheme pre-actions. This is an unsigned local app, not distribution signing.
    """
    result = {"projectGenerationExitCode": None, "exitCode": None, "success": False,
              "codeSigningAllowed": False, "provisioningUpdatesAllowed": False}
    generate = [str(build_tool), "-Mode=GenerateProjectFiles",
                "-project=" + str(PROJECT / "Veyr.uproject"), "-game", "-platforms=Mac",
                "-DeployOnly", "-NoIntellisense", "-NoDotNet", "-IgnoreJunk", "-development",
                "-IncludeTempTargets", "-projectfileformat=XCode", "-automated", "-singletarget=Veyr"]
    result["projectGenerationExitCode"] = run_logged(generate, evidence / "xcode-project.log")
    if result["projectGenerationExitCode"] != 0:
        result["reason"] = "deploy-only Xcode project generation failed"
        return result
    workspace = PROJECT / "Intermediate/ProjectFiles/Veyr_Mac_Veyr.xcworkspace"
    if not (workspace / "contents.xcworkspacedata").is_file():
        result["reason"] = "expected generated task workspace is missing"
        return result
    selected = subprocess.run(["/usr/bin/xcrun", "--find", "xcodebuild"], stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    xcodebuild = Path(selected.stdout.strip())
    if selected.returncode != 0 or not xcodebuild.is_absolute() or not xcodebuild.is_file():
        result["reason"] = "selected Xcode build tool unavailable"
        return result
    command = [str(xcodebuild), "build", "-workspace", str(workspace), "-scheme", "Veyr",
               "-configuration", configuration, "-destination", "generic/platform=macOS",
               "CODE_SIGNING_ALLOWED=NO", "UE_XCODE_BUILD_MODE=PostBuildSync", "-hideShellScriptEnvironment"]
    environment = os.environ.copy()
    environment["UBT_NO_POST_DEPLOY"] = "true"
    result["exitCode"] = run_logged(command, evidence / "xcode-finalize.log", env=environment)
    text = (evidence / "xcode-finalize.log").read_text(errors="replace")
    result["success"] = result["exitCode"] == 0 and "** BUILD SUCCEEDED **" in text
    result["reason"] = "direct Xcode finalization succeeded" if result["success"] else "direct Xcode finalization failed"
    return result


def standalone_bundle(configuration):
    executable = "Veyr" if configuration == "Development" else "Veyr-Mac-Shipping"
    return PROJECT / "Binaries/Mac" / (executable + ".app"), executable


def sign_local_bundle(configuration, evidence):
    """Ad-hoc seal this generated app for local UAT staging, without accounts.

    Remove only the two Finder metadata attributes that codesign rejects. Never
    clear all attributes, remove quarantine, or follow a link outside the app.
    """
    app, _ = standalone_bundle(configuration)
    result = {"success": False, "identity": "ad-hoc", "timestamped": False,
              "bundle": str(app.relative_to(PROJECT)), "signExitCode": None,
              "verifyExitCode": None, "attributeCleanupExitCodes": {}, "codeResourcesSHA256": None}
    expected = PROJECT.resolve() / "Binaries/Mac" / app.name
    if not app.is_dir() or app.is_symlink() or app.resolve() != expected:
        result["reason"] = "expected task-owned generated app is missing or redirected"
        return result
    attributes = ("com.apple.FinderInfo", "com.apple.ResourceFork")
    try:
        # Validate the complete path set before modifying anything. Internal
        # framework symlinks are allowed only when their targets remain owned.
        paths = [app]
        for directory, directories, files in os.walk(app, followlinks=False):
            paths.extend(Path(directory) / name for name in directories + files)
        for path in paths:
            if not path.resolve().is_relative_to(app.resolve()):
                raise ValueError("generated bundle contains a path outside its owned directory")
    except (OSError, ValueError, RuntimeError) as error:
        result["reason"] = "generated bundle metadata preparation failed: " + str(error)
        return result
    # macOS Python does not expose os.removexattr. Native xattr -dr is idempotent
    # when the named attribute is absent; never use -c or remove any other name.
    for name in attributes:
        status = run_logged(["/usr/bin/xattr", "-dr", name, str(app)],
                            evidence / ("bundle-xattr-" + name.rsplit(".", 1)[-1] + ".log"))
        result["attributeCleanupExitCodes"][name] = status
        if status != 0:
            result["reason"] = "generated bundle metadata cleanup failed for " + name
            return result
    result["signExitCode"] = run_logged(
        ["/usr/bin/codesign", "--force", "--deep", "--sign", "-", "--timestamp=none", str(app)],
        evidence / "bundle-sign.log")
    if result["signExitCode"] == 0:
        result["verifyExitCode"] = run_logged(
            ["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)],
            evidence / "bundle-verify.log")
    resources = app / "Contents/_CodeSignature/CodeResources"
    if result["signExitCode"] != 0 or result["verifyExitCode"] != 0 or not resources.is_file():
        verification_log = "\n".join(path.read_text(errors="replace") for path in
            (evidence / "bundle-sign.log", evidence / "bundle-verify.log") if path.exists())
        if "resource fork, Finder information, or similar detritus" in verification_log:
            # Documents FileProvider can reattach FinderInfo immediately after
            # signing. Verify an exact private copy outside that provider. The
            # staged/final app still receives its own full dependency and ZIP
            # signature audit; this is only the pre-staging build signature.
            from audit_bundle import sign_in_place, manifest, is_macho
            folder = Path(tempfile.mkdtemp(prefix="veyr-build-sign-", dir="/private/tmp"))
            copied = folder / app.name
            try:
                original_manifest = manifest(app)
                shutil.copytree(app, copied, symlinks=True)
                if manifest(copied) != original_manifest:
                    raise ValueError("temporary build copy differs before signing")
                proof = sign_in_place(copied)
                signed_manifest = manifest(copied)
                changed = [name for name in set(original_manifest) | set(signed_manifest)
                           if original_manifest.get(name) != signed_manifest.get(name)]
                for name in changed:
                    path = copied / name
                    if "/_CodeSignature/" not in name and not (path.is_file() and is_macho(path)):
                        raise ValueError("signing changed a non-signature payload: " + name)
                if manifest(app) != original_manifest:
                    raise ValueError("build payload changed concurrently during signing")
                # UAT still stages from the generated build path. Copy only
                # signer-produced bytes back, then require exact payload parity.
                # Finder metadata may recur there; final delivery is verified
                # separately on its signed, extracted ZIP.
                for name in changed:
                    destination = app / name
                    if name in signed_manifest:
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(copied / name, destination)
                    elif "/_CodeSignature/" in name:
                        destination.unlink()
                if manifest(app) != signed_manifest:
                    raise ValueError("staging payload differs from verified signed copy")
                result.update(success=True, originalPathVerified=False, verifiedCopyApp=str(copied),
                    verifiedCopySignature=proof, signatureChangedFiles=changed, stagingPayloadMatchesVerifiedCopy=True,
                    codeResourcesSHA256=hashlib.sha256((copied / "Contents/_CodeSignature/CodeResources").read_bytes()).hexdigest(),
                    reason="pre-staging signature verified on an exact private copy outside Documents FileProvider; final packaged audit still required")
                return result
            except (OSError, ValueError, RuntimeError) as error:
                result["temporaryCopyError"] = str(error)
        result["reason"] = "local bundle signature verification failed or CodeResources missing"
        return result
    result["codeResourcesSHA256"] = hashlib.sha256(resources.read_bytes()).hexdigest()
    result["success"] = True
    result["reason"] = "local ad-hoc bundle signature verified; no distribution signing or notarization"
    return result


def snapshot():
    files = [PROJECT / "Veyr.uproject"]
    for name in ("Source", "Config", "Content"):
        folder = PROJECT / name
        if folder.exists():
            files.extend(p for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
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
    identity_header = '#pragma once\n#define VEYR_SOURCE_ID TEXT("' + identity + '")\n'
    if not generated.exists() or generated.read_text() != identity_header:
        generated.write_text(identity_header)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    evidence = ROOT / "Local" / ("unreal-build-" + stamp)
    evidence.mkdir(mode=0o700, exist_ok=False)
    command = [str(build_tool), args.target, "Mac", args.configuration,
               str(PROJECT / "Veyr.uproject"), "-NoUBA", "-NoXGE", "-NoFASTBuild",
               "-NoSNDBS", "-MaxParallelActions=4", "-NoHotReloadFromIDE"]
    log = evidence / "build.log"
    print("Build log:", log, flush=True)
    environment = None
    if args.target == "Veyr":
        # Installed UE 5.8 AppleToolChain.cs:1268 explicitly skips its nested
        # Xcode finalizer for this process-scoped handoff. The same flag is used
        # by Epic's XcodeBuild.sh; no engine or global configuration is changed.
        environment = os.environ.copy()
        environment["UE_BUILD_FROM_XCODE"] = "1"
    compile_exit = run_logged(command, log, env=environment)
    text = log.read_text(errors="replace")
    compile_success = compile_exit == 0 and "Result: Succeeded" in text
    unchanged_after_compile = snapshot() == before
    finalization = None
    local_signature = None
    if args.target == "Veyr" and compile_success and unchanged_after_compile:
        finalization = finalize_standalone(build_tool, args.configuration, evidence)
        if finalization["success"] and snapshot() == before:
            local_signature = sign_local_bundle(args.configuration, evidence)
    unchanged = snapshot() == before
    success = compile_success and unchanged
    if args.target == "VeyrEditor":
        binary_paths = list((PROJECT / "Binaries/Mac").glob("libUnrealEditor-Veyr*.dylib"))
    else:
        success = (success and finalization is not None and finalization["success"] and
                   local_signature is not None and local_signature["success"])
        # Do not accidentally accept an older Development .app for Shipping.
        app, executable = standalone_bundle(args.configuration)
        binary_paths = [app / "Contents/MacOS" / executable]
    binaries = {str(p.relative_to(PROJECT)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(binary_paths) if p.is_file()}
    success = success and bool(binaries)
    receipt = {"sourceId": identity, "sourceFiles": before, "sourceUnchangedDuringBuild": unchanged,
               "target": args.target, "configuration": args.configuration,
               "exitCode": 0 if success else compile_exit or (finalization or {}).get("exitCode") or 1,
               "compileExitCode": compile_exit, "compileSucceeded": compile_success,
               "sourceUnchangedAfterCompile": unchanged_after_compile,
               "standaloneFinalization": finalization,
               "localBundleSignature": local_signature,
               "success": bool(success), "binaryHashes": binaries,
               "editorLaunched": False, "nativeGameplayVerified": False}
    with os.fdopen(os.open(evidence / "receipt.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
        stream.write(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"success": success, "sourceId": identity, "receipt": str(evidence / "receipt.json")}))
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
