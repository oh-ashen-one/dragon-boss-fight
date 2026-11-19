#!/usr/bin/env python3
"""Enforce this task's ten renderer launches/hour before the shared GPU gate, across every checkout of the project.

This never changes or bypasses gpu_slot. Receipts count actual started jobs,
including failed jobs; callers must still serialize owned renderer jobs.

The budget is machine-wide for this project, not per checkout. The trailing-hour launch list is the longest of:
  1. this tree's receipts (Evidence/native-*/gpu.json, Local/**/gpu*.json) - the original per-tree count, kept as a floor;
  2. the receipts of every git worktree of this repository (so a builder in another tree is counted even when its
     tools are older and write no shared record);
  3. ~/.cache/veyr-engine/rendered-launches.jsonl, appended by every rendered launch through launch_gate() - this
     survives a worktree being deleted.
launch_gate() also takes the engine lock (engine_lock.py), re-checks the budget while holding it, and the caller records
the launch before releasing, so two builders cannot both pass the check for the tenth slot.
"""
import contextlib
import datetime
import json
from pathlib import Path
import subprocess
import time

from engine_lock import EngineLockTimeout, engine_lock, lock_dir, DEFAULT_WAIT

ROOT=Path(__file__).resolve().parents[2]
BUDGET=10

def shared_log():
    return lock_dir()/'rendered-launches.jsonl'

def worktree_roots(root=ROOT):
    """This tree plus every worktree of the same repository (git worktree list); missing git means just this tree."""
    roots=[Path(root).resolve()]
    try:
        out=subprocess.run(['git','-C',str(root),'worktree','list','--porcelain'],capture_output=True,text=True,timeout=20)
    except (OSError,subprocess.SubprocessError):
        return roots
    for line in out.stdout.splitlines():
        if line.startswith('worktree '):
            path=Path(line[len('worktree '):]).resolve()
            if path not in roots and path.is_dir():roots.append(path)
    return roots

def _receipt_start(data):
    started=data.get('started_at')
    if isinstance(started,str):started=datetime.datetime.fromisoformat(started.replace('Z','+00:00')).timestamp()
    return started if isinstance(started,(float,int)) else None

def tree_launches(root=ROOT,now=None):
    """The original per-tree count: gpu_slot receipts of started jobs in the trailing hour."""
    now=time.time() if now is None else now
    paths=set((root/'Evidence').glob('native-*/gpu.json'))
    paths.update((root/'Local').glob('*gpu*.json'))
    paths.update((root/'Local').glob('*/gpu.json'))
    paths.update((root/'Local').glob('*/*gpu*.json'))
    launches=[]
    for path in paths:
        try:
            if path.stat().st_mtime<now-7200:continue  # a receipt is written at start and updated later: mtime >= start
            data=json.loads(path.read_text())
            if not isinstance(data,dict) or not data.get('cmd'):continue
            started=_receipt_start(data)
            if started is not None and now-3600<started<=now:launches.append((started,str(path)))
        except (OSError,ValueError,TypeError):continue
    return sorted(launches)

def all_tree_launches(root=ROOT,now=None):
    launches=[]
    for tree in worktree_roots(root):launches.extend(tree_launches(tree,now))
    return sorted(launches)

def shared_launches(now=None):
    now=time.time() if now is None else now
    launches=[]
    try:lines=shared_log().read_text().splitlines()
    except OSError:return launches
    for line in lines:
        try:
            data=json.loads(line)
            started=data.get('startedAt')
            if isinstance(started,(float,int)) and now-3600<started<=now:launches.append((started,'shared:'+str(data.get('tree'))))
        except (ValueError,TypeError,AttributeError):continue
    return sorted(launches)

def recent_launches(root=ROOT,now=None):
    """Trailing-hour rendered launches across all checkouts: the longest of per-tree (floor), all worktrees and the shared log."""
    now=time.time() if now is None else now
    candidates=[tree_launches(root,now),all_tree_launches(root,now),shared_launches(now)]
    return max(candidates,key=len)

def record_rendered_launch(root,label,receipt=None,run=None):
    """Append one started rendered launch to the shared log. The start time comes from the gpu_slot receipt; with no
    receipt (the gate declined, exit 75) nothing started and nothing is recorded."""
    try:
        data=json.loads(Path(receipt).read_text()) if receipt else None
    except (OSError,ValueError):data=None
    if not isinstance(data,dict) or not data.get('cmd'):return False
    try:started=_receipt_start(data)
    except (ValueError,TypeError):started=None
    if started is None:return False
    entry={'startedAt':started,'at':datetime.datetime.fromtimestamp(started,datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
           'tree':str(root),'label':label,'receipt':str(receipt),'run':str(run) if run else None}
    with contextlib.suppress(OSError):
        shared_log().parent.mkdir(parents=True,exist_ok=True)
        with open(shared_log(),'a') as stream:stream.write(json.dumps(entry)+'\n')
    return True

def wait_for_budget(root=ROOT):
    announced=False
    while True:
        launches=recent_launches(root)
        if len(launches)<BUDGET:return
        wait=max(1.,launches[-BUDGET][0]+3601-time.time())
        if not announced:
            print(f'Owned launch-rate queue: {len(launches)} starts in the trailing hour across all checkouts; next slot in about {wait:.0f}s',flush=True)
            announced=True
        time.sleep(min(30.,wait))

@contextlib.contextmanager
def launch_gate(root,label,wait_seconds=DEFAULT_WAIT):
    """Wait for launch budget, then hold the engine lock; the budget is re-checked under the lock.

    The budget wait happens before the lock is taken so a builder waiting on the hourly budget does not block the other
    builder's windowless work. Exits 75 (nothing started) when the lock wait runs out.
    """
    while True:
        wait_for_budget(root)
        lock=engine_lock(label,tree=root,wait_seconds=wait_seconds)
        try:lock.acquire()
        except EngineLockTimeout as error:
            print('engine_lock: '+str(error),flush=True)
            raise SystemExit(75)
        if len(recent_launches(root))<BUDGET:break
        lock.release()  # another builder used the last slot while we queued for the lock
    try:
        yield lock
    except BaseException as error:
        lock.exit_code=error.code if isinstance(error,SystemExit) and isinstance(error.code,int) else (0 if isinstance(error,SystemExit) and error.code is None else 1)
        raise
    finally:
        lock.release()

if __name__=='__main__':wait_for_budget()
