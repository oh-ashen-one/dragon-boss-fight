#!/usr/bin/env python3
"""Compile/link a tiny Metal library before spending time on a Shipping cook.

Uses the selected Xcode toolchain without changing it. Does not run the shader,
launch a renderer, download components or accept licenses.
"""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import tempfile


def verify_metal_toolchain(report_dir):
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    report = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'sdk': 'macosx', 'success': False, 'rendererLaunched': False}
    with tempfile.TemporaryDirectory(prefix='veyr-metal-preflight-') as temp:
        folder = Path(temp)
        source, intermediate, library = [folder/name for name in ['probe.metal', 'probe.air', 'probe.metallib']]
        source.write_text('#include <metal_stdlib>\nusing namespace metal;\n'
                          'kernel void veyr_probe(device float* v [[buffer(0)]], uint i [[thread_position_in_grid]]) { v[i] = 0.0f; }\n')
        with (report_dir/'metal-preflight.log').open('w') as log:
            result = subprocess.run(['xcrun', '-sdk', 'macosx', 'metal', '-c', str(source), '-o', str(intermediate)],
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
            report['compilerExitCode'] = result.returncode
            if result.returncode == 0 and intermediate.is_file():
                result = subprocess.run(['xcrun', '-sdk', 'macosx', 'metallib', str(intermediate), '-o', str(library)],
                    stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
                report['linkerExitCode'] = result.returncode
                report['libraryBytes'] = library.stat().st_size if library.exists() else 0
                report['success'] = result.returncode == 0 and report['libraryBytes'] > 0
    (report_dir/'metal-preflight.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report-dir', required=True, type=Path)
    args = parser.parse_args()
    result = verify_metal_toolchain(args.report_dir)
    print('Metal compiler/linker preflight', 'PASS' if result['success'] else 'FAIL')
    raise SystemExit(0 if result['success'] else 1)
