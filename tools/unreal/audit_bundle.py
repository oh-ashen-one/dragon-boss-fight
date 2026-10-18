#!/usr/bin/env python3
"""Static, relocation-safe Mac bundle audit and copy-only runtime repair.

Never executes the game, cooker or editor. Engine-installation fallbacks are
reported but never satisfy a dependency. Weak non-system imports must also be
present. This is a packaging gate, not gameplay, notarization or launch proof.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / 'Unreal/Veyr'
MAGIC = {bytes.fromhex(x) for x in ('cffaedfe', 'feedfacf', 'cefaedfe', 'feedface',
                                   'cafebabe', 'bebafeca', 'cafebabf', 'bfbafeca')}
LOADS = {'LC_LOAD_DYLIB', 'LC_LOAD_WEAK_DYLIB', 'LC_REEXPORT_DYLIB', 'LC_LOAD_UPWARD_DYLIB'}


def command(args):
    result = subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True, text=True)
    if result.returncode:
        raise ValueError(f'{args[0]} failed ({result.returncode}): {result.stderr.strip()}')
    return result.stdout


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def files_inside(directory):
    """Reject redirected paths before copy/sign/audit; retain internal symlinks."""
    base = directory.resolve()
    paths = [directory, *directory.rglob('*')]
    for path in paths:
        if path.is_symlink() and Path(os.readlink(path)).is_absolute():
            raise ValueError(f'nonrelocatable absolute symlink: {path}')
        if not path.resolve().is_relative_to(base):
            raise ValueError(f'path escapes bundle: {path}')
    return paths


def manifest(directory):
    return {str(p.relative_to(directory)): ('symlink:' + os.readlink(p) if p.is_symlink() else sha(p))
            for p in files_inside(directory) if p.is_file() or p.is_symlink()}


def executable(app):
    with (app / 'Contents/Info.plist').open('rb') as stream:
        name = plistlib.load(stream)['CFBundleExecutable']
    if Path(name).name != name:
        raise ValueError('unsafe CFBundleExecutable')
    return app / 'Contents/MacOS' / name


def is_macho(path):
    with path.open('rb') as stream:
        return stream.read(4) in MAGIC


def macho(path, arch='arm64'):
    arches = command(['/usr/bin/lipo', '-archs', str(path)]).strip().split()
    if arch not in arches:
        raise ValueError(f'{path.name} has no {arch} slice: {arches}')
    output = command(['/usr/bin/otool', '-arch', arch, '-l', str(path)])
    result = {'architectures': arches, 'rpaths': [], 'dependencies': [], 'id': None,
              'uuid': None, 'sections': []}
    for block in re.split(r'Load command \d+\n', output)[1:]:
        match = re.search(r'^\s*cmd (\S+)', block, re.M)
        kind = match.group(1) if match else ''
        if kind == 'LC_RPATH':
            result['rpaths'].append(re.search(r'^\s*path (.+) \(offset ', block, re.M).group(1))
        elif kind in LOADS or kind == 'LC_ID_DYLIB':
            name = re.search(r'^\s*name (.+) \(offset ', block, re.M).group(1)
            if kind == 'LC_ID_DYLIB':
                result['id'] = name
            else:
                result['dependencies'].append({'name': name, 'weak': kind == 'LC_LOAD_WEAK_DYLIB'})
        elif kind == 'LC_UUID':
            result['uuid'] = re.search(r'^\s*uuid (\S+)', block, re.M).group(1)
        elif kind == 'LC_SEGMENT_64':
            for section in block.split('Section\n')[1:]:
                name = re.search(r'^\s*sectname (\S+)', section, re.M).group(1)
                if name in ('__text', '__cstring'):
                    offset = int(re.search(r'^\s*offset (\d+)', section, re.M).group(1))
                    size = int(re.search(r'^\s*size (\S+)', section, re.M).group(1), 16)
                    result['sections'].append((name, offset, size))
    return result


def code_identity(path):
    """Signing changes whole-file hashes; UUID and code/string bytes stay fixed.

    Veyr is a thin arm64 executable. Refuse universal executables here rather
    than accidentally interpreting section offsets relative to the wrong slice.
    """
    info = macho(path)
    if info['architectures'] != ['arm64'] or not info['uuid'] or len(info['sections']) != 2:
        raise ValueError('expected thin arm64 Veyr with UUID, __text and __cstring')
    result = {'uuid': info['uuid']}
    with path.open('rb') as stream:
        for name, offset, size in info['sections']:
            stream.seek(offset)
            result[name] = hashlib.sha256(stream.read(size)).hexdigest()
    return result


def embedded_build_identity(path):
    """Map the embedded stamp to successful local standalone-build evidence."""
    binary = path.read_bytes()
    matches = {}
    for receipt in sorted((ROOT / 'Local').glob('unreal-build-*/receipt.json')):
        build = json.loads(receipt.read_text())
        stamp = build.get('sourceId', '')
        if build.get('target') != 'Veyr' or not build.get('compileSucceeded') or not build.get('sourceUnchangedAfterCompile'):
            continue
        if re.fullmatch('[0-9a-f]{64}', stamp) and any(stamp.encode(encoding) in binary for encoding in ('ascii', 'utf-16le', 'utf-32le')):
            matches[stamp] = str(receipt)
    if len(matches) != 1:
        raise ValueError('cannot map exactly one embedded source stamp to standalone build evidence')
    stamp, receipt = next(iter(matches.items()))
    return {'sourceId': stamp, 'buildReceipt': receipt, 'embeddedStampVerified': True}


def expand(value, loader, main):
    for token, base in (('@loader_path', loader.parent), ('@executable_path', main.parent)):
        if value == token or value.startswith(token + '/'):
            return (base / value[len(token):].lstrip('/')).resolve()
    if value.startswith('/'):
        return Path(value).resolve()
    return None  # Unsupported relative/@rpath-in-rpath forms fail closed.


def system_library(name):
    normalized = os.path.normpath(name)
    return normalized.startswith('/usr/lib/') or normalized.startswith('/System/Library/')


def audit_bundle(app):
    app = app.resolve()
    report = {'bundle': str(app), 'staticDependencyAuditPassed': False,
              'nativePackagedGameplayVerified': False, 'architecture': 'arm64',
              'scope': 'all bundled Mach-O imports, including weak imports; system libraries assumed from macOS; no dlopen/content/launch proof',
              'unresolved': [], 'errors': [], 'images': [], 'externalSearchPathsIgnored': []}
    try:
        all_paths = files_inside(app)
        main = executable(app)
        images = sorted({p.resolve() for p in all_paths if p.is_file() and is_macho(p)})
        if main not in images:
            raise ValueError('bundle executable is not a Mach-O image')
        info = {p: macho(p) for p in images}
        main_rpaths = [(x, main) for x in info[main]['rpaths']]
        # Audit every bundled image, including optional/dlopen libraries. Also
        # follow actual import chains so loader-relative inherited rpaths retain
        # their original owner instead of being expanded against the child.
        pending = [(p, main_rpaths) for p in images]
        visited = set()
        emitted = set()
        while pending:
            loader, inherited = pending.pop()
            own = [(x, loader) for x in info[loader]['rpaths']]
            stack = list(dict.fromkeys(own + inherited))
            key = (loader, tuple(stack))
            if key in visited:
                continue
            visited.add(key)
            for dependency in info[loader]['dependencies']:
                name = dependency['name']
                if system_library(name):
                    continue
                if name.startswith('@rpath/'):
                    candidates = [base / name[len('@rpath/'):]
                                  for value, owner in stack if (base := expand(value, owner, main)) is not None]
                else:
                    candidate = expand(name, loader, main)
                    candidates = [candidate] if candidate else []
                local = [p.resolve() for p in candidates if p.resolve().is_relative_to(app) and not name.startswith('/')]
                outside = [str(p) for p in candidates if not p.resolve().is_relative_to(app)]
                report['externalSearchPathsIgnored'].extend(outside)
                resolved = next((p for p in local if p.is_file()), None)
                edge = (str(loader.relative_to(app)), name)
                if resolved is None:
                    if edge not in emitted:
                        report['unresolved'].append({'loader': edge[0], **dependency,
                                                     'internalCandidates': [str(p.relative_to(app)) for p in local],
                                                     'externalCandidatesIgnored': outside})
                        emitted.add(edge)
                elif resolved not in info:
                    report['errors'].append(f'non-Mach-O dependency: {resolved.relative_to(app)}')
                else:
                    pending.append((resolved, stack))
        report['images'] = [{'path': str(p.relative_to(app)), 'sha256': sha(p),
                             'id': info[p]['id'], 'architectures': info[p]['architectures'],
                             'nonSystemImports': [d for d in info[p]['dependencies'] if not system_library(d['name'])]}
                            for p in images]
        payload = app / 'Contents/UE/Veyr/Content/Paks'
        missing = [suffix for suffix in ('.pak', '.utoc', '.ucas') if not any(payload.glob('*' + suffix))]
        report['cookedPayloadPresent'] = not missing
        if missing:
            report['errors'].append('missing cooked payload extensions: ' + ', '.join(missing))
    except (OSError, ValueError, KeyError) as error:
        report['errors'].append(str(error))
    report['externalSearchPathsIgnored'] = sorted(set(report['externalSearchPathsIgnored']))
    report['staticDependencyAuditPassed'] = not report['errors'] and not report['unresolved']
    return report


def receipt_libraries(receipt, engine):
    data = json.loads(receipt.read_text())
    candidates = {}
    for row in data['RuntimeDependencies']:
        name = row['Path']
        if row.get('Type') != 'NonUFS' or not name.endswith('.dylib'):
            continue
        path = Path(name.replace('$(EngineDir)', str(engine / 'Engine')).replace('$(ProjectDir)', str(PROJECT)))
        if '$(' in str(path) or not path.is_absolute() or not path.is_file():
            raise ValueError(f'unsupported/missing runtime receipt entry: {name}')
        path = path.resolve()
        if not any(path.is_relative_to(base.resolve()) for base in (PROJECT, engine)):
            raise ValueError('runtime receipt source outside project/selected engine')
        identity = macho(path)['id']
        for alias in {path.name, Path(identity).name if identity else path.name}:
            if alias in candidates and sha(candidates[alias]) != sha(path):
                raise ValueError(f'ambiguous runtime receipt library: {alias}')
            candidates[alias] = path
    return candidates


def sign_in_place(app):
    removed = {}
    for path in files_inside(app):
        if path.is_symlink():
            continue
        present = command(['/usr/bin/xattr', str(path)]).splitlines()
        for name in ('com.apple.FinderInfo', 'com.apple.ResourceFork'):
            if name in present:
                command(['/usr/bin/xattr', '-d', name, str(path)])
                removed[name] = removed.get(name, 0) + 1
    # Newly copied libraries may not reside in Apple's standard nested-code
    # directories. Seal every Mach-O first, then the outer application.
    main = executable(app)
    for path in files_inside(app):
        if path != main and path.is_file() and not path.is_symlink() and is_macho(path):
            command(['/usr/bin/codesign', '--force', '--sign', '-', '--timestamp=none', str(path)])
    # macOS FileProvider may reattach Finder metadata to the .app directory
    # during file writes. Clear only the same two attributes immediately before
    # sealing the enclosing app; never use xattr -c or touch quarantine.
    for name in ('com.apple.FinderInfo', 'com.apple.ResourceFork'):
        command(['/usr/bin/xattr', '-dr', name, str(app)])
    command(['/usr/bin/codesign', '--force', '--deep', '--sign', '-', '--timestamp=none', str(app)])
    command(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(app)])
    return {'verified': True, 'identity': 'ad-hoc', 'removedAttributes': removed,
            'notarized': False, 'quarantineChanged': False}


def sign_copy(app):
    # Documents FileProvider can immediately recreate FinderInfo during signing.
    # Seal outside it and deliver a ZIP, then verify an exact fresh extraction.
    # Do not change the provider, quarantine, credentials or original archive.
    archive = app.with_suffix('.zip')
    if archive.exists():
        raise ValueError('refusing to replace an existing signed ZIP')
    with tempfile.TemporaryDirectory(prefix='veyr-static-bundle-sign-') as folder:
        temporary = Path(folder) / app.name
        shutil.copytree(app, temporary, symlinks=True)
        result = sign_in_place(temporary)
        signed_manifest = manifest(temporary)
        paths = files_inside(temporary)
        for path in paths:
            if path.is_symlink():
                raise ValueError('ZIP symlinks require explicit handling')
            if 'com.apple.quarantine' in command(['/usr/bin/xattr', str(path)]).splitlines():
                raise ValueError('quarantined input requires a metadata-preserving delivery workflow')
        with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as zipped:
            for path in paths:
                zipped.write(path, path.relative_to(temporary.parent))
    extraction = Path(tempfile.mkdtemp(prefix='veyr-verified-bundle-', dir='/private/tmp'))
    with zipfile.ZipFile(archive) as zipped:
        bad = zipped.testzip()
        if bad:
            raise ValueError('ZIP CRC check failed: ' + bad)
        for member in zipped.infolist():
            target = extraction / member.filename
            if not target.resolve().is_relative_to(extraction.resolve()):
                raise ValueError('ZIP path escapes extraction')
            zipped.extract(member, extraction)
            if not member.is_dir():
                target.chmod((member.external_attr >> 16) & 0o777)
    runtime = extraction / app.name
    if manifest(runtime) != signed_manifest:
        raise ValueError('extracted ZIP differs from signed bundle manifest')
    command(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(runtime)])
    runtime_audit = audit_bundle(runtime)
    if not runtime_audit['staticDependencyAuditPassed']:
        raise ValueError('fresh signed ZIP extraction failed dependency audit')
    result.update({'finalPathVerified': True, 'signedZip': str(archive), 'archiveSHA256': sha(archive),
                   'verifiedRuntimeApp': str(runtime), 'extractedManifestMatchesSignedBundle': True,
                   'extractionAudit': runtime_audit,
                   'signingWorkspace': 'private temporary copy outside Documents FileProvider',
                   'filesystemLimitation': 'Documents FileProvider reattaches FinderInfo to .app directories; ZIP is durable delivery, runtime extraction is task-owned /private/tmp and may be removed by OS cleanup'})
    return result


def repair_copy(source, staged, destination, receipt, engine):
    source, staged, destination = source.resolve(), staged.resolve(), destination.resolve()
    if not source.is_relative_to(ROOT / 'Builds') or not destination.is_relative_to(ROOT / 'Builds'):
        raise ValueError('repair source and output must be task-local Builds paths')
    if not staged.is_relative_to(PROJECT / 'Saved/StagedBuilds'):
        raise ValueError('payload source must be this task\'s staged build')
    if destination.exists() or destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError('repair requires a new nonoverlapping output app; source stays unchanged')
    original = manifest(source)
    files_inside(staged)
    ufs_manifest = staged.parent / 'Manifest_UFSFiles_Mac.txt'
    required_map = 'Veyr/Content/Maps/VeyrArena.umap'
    if not ufs_manifest.is_file() or required_map not in {line.split('\t', 1)[0] for line in ufs_manifest.read_text().splitlines()}:
        raise ValueError('matching stage UFS manifest does not list VeyrArena.umap')
    identity = code_identity(executable(source))
    build_identity = embedded_build_identity(executable(source))
    if code_identity(executable(staged)) != identity:
        raise ValueError('archive and staged executable UUID/code/string sections differ')
    payload = staged / 'Contents/UE'
    if not payload.is_dir():
        raise ValueError('matching staged app lacks Contents/UE payload')
    libraries = receipt_libraries(receipt, engine.resolve())
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, symlinks=True)
    copied = []
    # The observed archive lost the whole UE tree. Also verify any preexisting
    # files against the matching stage instead of silently overwriting them.
    for path in files_inside(payload):
        if path.is_symlink():
            raise ValueError('staged payload symlinks require explicit handling')
        target = destination / 'Contents/UE' / path.relative_to(payload)
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            if target.exists():
                if sha(target) != sha(path):
                    raise ValueError(f'archive/staged payload conflict: {target}')
            else:
                shutil.copy2(path, target)
                copied.append(str(target.relative_to(destination)))
    aliases = []
    for _ in range(8):
        audit = audit_bundle(destination)
        if not audit['unresolved']:
            break
        changed = False
        for missing in audit['unresolved']:
            library = libraries.get(Path(missing['name']).name)
            if library is None or not missing['internalCandidates']:
                continue
            target = destination / missing['internalCandidates'][0]
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(library, target)
            aliases.append({'source': str(library), 'destination': str(target.relative_to(destination)),
                            'sourceSHA256': sha(library), 'installName': macho(library)['id']})
            changed = True
        if not changed:
            break
    audit = audit_bundle(destination)
    signature = None
    if audit['staticDependencyAuditPassed']:
        try:
            signature = sign_copy(destination)
        except (OSError, ValueError) as error:
            signature = {'verified': False, 'error': str(error)}
    # Codesigning must not alter game code or introduce unresolved dependencies.
    final = audit_bundle(destination)
    unchanged = manifest(source) == original
    same_code = code_identity(executable(destination)) == identity
    return {'sourceApp': str(source), 'repairedApp': str(destination), 'stagedApp': str(staged),
            'originalArchiveUnchanged': unchanged, 'gameCodeIdentityUnchanged': same_code,
            'gameCodeIdentity': identity, 'copiedPayloadFiles': copied, 'libraryRepairs': aliases,
            'sourceBuildIdentity': build_identity,
            'cookedMapManifest': {'map': required_map, 'source': str(ufs_manifest), 'sha256': sha(ufs_manifest)},
            'signature': signature, 'audit': final,
            'packagingSucceeded': bool(unchanged and same_code and signature and signature['verified'] and final['staticDependencyAuditPassed']),
            'nativePackagedGameplayVerified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--repair-from-staged', type=Path)
    parser.add_argument('--output-app', type=Path)
    parser.add_argument('--target-receipt', type=Path, default=PROJECT / 'Binaries/Mac/Veyr.target')
    parser.add_argument('--engine', type=Path)
    args = parser.parse_args()
    try:
        if args.repair_from_staged:
            if not args.output_app or not args.engine:
                parser.error('repair requires --output-app and --engine')
            result = repair_copy(args.app, args.repair_from_staged, args.output_app, args.target_receipt, args.engine)
            success = result['packagingSucceeded']
        else:
            result = audit_bundle(args.app)
            success = result['staticDependencyAuditPassed']
    except (OSError, ValueError, KeyError) as error:
        result = {'packagingSucceeded': False, 'error': str(error), 'nativePackagedGameplayVerified': False}
        success = False
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'success': success, 'report': str(args.report), 'nativePackagedGameplayVerified': False}))
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())
