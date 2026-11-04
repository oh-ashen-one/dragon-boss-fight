#!/usr/bin/env python3
"""Blind all four ordinary-camera heal windows with native framing diagnostics.

Retains every captured frame in each heal/entry/recovery window. Sheet inspection
and geometric visibility metrics do not establish continuous-motion acceptance.
"""
import argparse
import json
from pathlib import Path
import secrets
import shutil

from encode_video import read_capture
from prepare_pacing_review import make_sheets


def load(path):
    d = json.loads(path.read_text())
    assert d['mode'] == 'healing' and d['passed'] and d['finished'] and d['finalWrite']
    assert d['verifiedHealCharges'] == 4 and d['healCapVerified'] and d['injuredEmptyFlaskRejected']
    starts = [e['seconds'] for e in d['events'] if e['event'] == 'healing_charge_requested']
    ends = [e['seconds'] for e in d['events'] if e['event'] == 'healing_seek_next_natural_injury']
    assert len(starts) == len(ends) == 4
    manifest = path.parent/'native-video/frames.jsonl'
    _, frames, _, tail, _ = read_capture(manifest, world_index=0)
    assert frames and tail
    return path, d, manifest, frames, list(zip(starts, ends))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('before', type=Path)
    p.add_argument('after', type=Path)
    p.add_argument('out', type=Path)
    p.add_argument('--mapping', type=Path, required=True)
    p.add_argument('--metrics', type=Path, required=True)
    a = p.parse_args()
    assert not a.out.exists() and not a.mapping.exists()
    assert not a.mapping.resolve().is_relative_to(a.out.resolve())
    assert not a.metrics.resolve().is_relative_to(a.out.resolve())
    versions = [load(a.before.resolve()), load(a.after.resolve())]
    assert versions[0][1]['sourceId'] == versions[1][1]['sourceId']
    secrets.SystemRandom().shuffle(versions)
    a.out.mkdir(parents=True)
    packet = {'scope': 'Four natural-injury/heal trials, ordinary gameplay camera. '
              'Each sheet has four columns, eight rows; read left-to-right, then top-to-bottom. '
              'Black cells are padding. All captured frames from 0.15s before heal through '
              '0.15s after recovery are included. Judge visibility of the knight/feet/cup and '
              'dragon threats, animation entry/exit and any camera tradeoff. '
              'This is sampled visual evidence, not continuous playback or audio proof.', 'variants': {}}
    mapping, metrics = {}, {}
    for label, (path, data, manifest, frames, trials) in zip(('A', 'B'), versions):
        packet['variants'][label] = []
        origin = frames[0]['wallSeconds']
        for n, (start, end) in enumerate(trials, 1):
            selected = [f for f in frames if start-.15 <= f['requestedGameSeconds'] <= end+.15]
            assert len(selected) >= 30
            sheets = make_sheets(manifest.parent, selected, origin, a.out, f'{label}-heal-{n}', rows=8)
            detail = min(frames, key=lambda f: abs(f['requestedGameSeconds']-start-1.25))
            name = f'{label}-heal-{n}-detail.png'
            shutil.copyfile(manifest.parent/detail['file'], a.out/name)
            packet['variants'][label].append({'trial': n, 'sheets': sheets, 'detail': name,
                                              'detailSecondsIntoHeal': detail['requestedGameSeconds']-start})
        heal = [s for s in data['samples'] if s['action'] == 'Heal']
        assert heal and all('feetViewportY' in s['camera'] for s in heal)
        ys = [s['camera']['feetViewportY'] for s in heal]
        metrics[label] = {'healSamples': len(heal), 'feetOutsideVerticalViewport': sum(y < 0 or y > 1 for y in ys),
                          'feetViewportYRange': [min(ys), max(ys)], 'verifiedCharges': 4,
                          'readableAutoLock': data['latest']['camera']['readableAutoLockEnabled'],
                          'scope': 'Same-frame geometric projection only; inspect rendered frames.'}
        mapping[label] = str(path)
    (a.out/'sequence.json').write_text(json.dumps(packet, indent=2)+'\n')
    a.mapping.write_text(json.dumps(mapping, indent=2)+'\n')
    a.metrics.write_text(json.dumps(metrics, indent=2)+'\n')
    print('Prepared heal camera comparison; no quality verdict')


if __name__ == '__main__':
    main()
