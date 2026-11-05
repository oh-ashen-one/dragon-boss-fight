"""Run a fixed, hashed sequence of this checkout's scripts in one owned Blender.

This is not a server or a replacement for gpu_slot: launch the batch through the
ordinary shared gate and launch budget. Scripts execute serially in the same
process, and a failure stops the batch. No queue polling or automatic relaunch.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys

ROOT=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--plan',type=Path,required=True)
p.add_argument('--receipt',type=Path,required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
planpath=a.plan.resolve(strict=True);receipt=a.receipt.resolve()
assert planpath.is_relative_to(ROOT/'Local') and receipt.is_relative_to(ROOT/'Local') and not receipt.exists()
assert planpath.stat().st_size<65536
plan=json.loads(planpath.read_text());assert 1<=len(plan['jobs'])<=3
report={'pid':os.getpid(),'planSHA256':hashlib.sha256(planpath.read_bytes()).hexdigest(),'jobs':[],'finished':False}
def save():
    receipt.parent.mkdir(parents=True,exist_ok=True);receipt.write_text(json.dumps(report,indent=2)+'\n')
for job in plan['jobs']:
    script=(ROOT/job['script']).resolve(strict=True)
    assert script.is_relative_to(ROOT/'tools') and script.suffix=='.py'
    assert hashlib.sha256(script.read_bytes()).hexdigest()==job['sha256'], 'Batch script changed since plan was sealed'
    outputs=[(ROOT/name).resolve() for name in job['expectedOutputs']]
    assert outputs and all(path.is_relative_to(ROOT/'Local') and not path.exists() for path in outputs)
save()
for job in plan['jobs']:
    script=(ROOT/job['script']).resolve(strict=True)
    assert hashlib.sha256(script.read_bytes()).hexdigest()==job['sha256']
    row={'script':job['script'],'startedUTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'finished':False}
    report['jobs'].append(row);save();previous=sys.argv
    try:
        sys.argv=[str(script),'--',*job['args']]
        runpy.run_path(str(script),run_name='__main__')
        assert all((ROOT/name).is_file() for name in job['expectedOutputs']), 'Expected artifacts absent after script'
    except BaseException as error:
        row['errorType']=type(error).__name__;save();raise
    finally:sys.argv=previous
    row['finished']=True;row['endedUTC']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
report['finished']=True;save()
print('OWNED_BLENDER_BATCH_COMPLETED',len(report['jobs']),flush=True)
