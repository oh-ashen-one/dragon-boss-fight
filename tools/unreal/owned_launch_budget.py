#!/usr/bin/env python3
"""Enforce this task's ten renderer launches/hour before the shared GPU gate.

This never changes or bypasses gpu_slot. Receipts count actual started jobs,
including failed jobs; callers must still serialize owned renderer jobs.
"""
import datetime
import json
from pathlib import Path
import time

ROOT=Path(__file__).resolve().parents[2]

def recent_launches(root=ROOT,now=None):
    now=time.time() if now is None else now
    paths=set((root/'Evidence').glob('native-*/gpu.json'))
    paths.update((root/'Local').glob('*gpu*.json'))
    paths.update((root/'Local').glob('*/gpu.json'))
    paths.update((root/'Local').glob('*/*gpu*.json'))
    launches=[]
    for path in paths:
        try:
            data=json.loads(path.read_text())
            if not isinstance(data,dict) or not data.get('cmd'):continue
            started=data.get('started_at')
            if isinstance(started,str):started=datetime.datetime.fromisoformat(started.replace('Z','+00:00')).timestamp()
            if isinstance(started,(float,int)) and now-3600<started<=now:launches.append((started,str(path)))
        except (OSError,ValueError,TypeError):continue
    return sorted(launches)

def wait_for_budget(root=ROOT):
    announced=False
    while True:
        launches=recent_launches(root)
        if len(launches)<10:return
        wait=max(1.,launches[-10][0]+3601-time.time())
        if not announced:
            print(f'Owned launch-rate queue: {len(launches)} starts in the trailing hour; next slot in about {wait:.0f}s',flush=True)
            announced=True
        time.sleep(min(30.,wait))

if __name__=='__main__':wait_for_budget()
