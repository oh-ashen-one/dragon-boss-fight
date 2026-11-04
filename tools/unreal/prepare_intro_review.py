#!/usr/bin/env python3
"""Prepare blinded native intro/handoff frames; preserve original movies.

The owner already approved the exact tour. This packet reviews integration and
first-use rendering, not another arena redesign. Ordered stills do not establish
continuous playback or audio quality; the accompanying movies remain required.
"""
import argparse
import json
from pathlib import Path
import secrets
import shutil

from encode_video import read_capture
from prepare_pacing_review import make_sheets


def load(path):
    data = json.loads(path.read_text())
    assert data['mode'] == 'intro' and data['passed'] and data['finished'] and data['finalWrite']
    assert data['latest']['introCompleted'] and not data['latest']['introSkipped']
    assert data['latest']['introShotsSeen'] == 8
    handoff = [e['seconds'] for e in data['events'] if e.get('event') == 'intro_handoff_complete']
    assert len(handoff) == 1
    manifest = path.parent/'native-video/frames.jsonl'
    _, frames, _, tail, _ = read_capture(manifest, world_index=0)
    assert tail and frames
    return path, manifest, frames, handoff[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    parser.add_argument('out', type=Path)
    parser.add_argument('--mapping', type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists() and not args.mapping.exists()
    assert not args.mapping.resolve().is_relative_to(args.out.resolve())
    versions = [load(args.before.resolve()), load(args.after.resolve())]
    secrets.SystemRandom().shuffle(versions)
    args.out.mkdir(parents=True)
    packet = {'scope': 'Anonymous native frame sequences. Read each sheet left-to-right, top-to-bottom. '
              'Black tiles are padding. The eight-shot environment tour is owner-approved and must remain. '
              'Assess handoff material consistency, character visibility and pose continuity in these samples. '
              'This is not proof of continuous playback, audio quality or the unfinished combat backlog.', 'variants': {}}
    mapping = {}
    for label, (path, manifest, frames, handoff) in zip(['A', 'B'], versions):
        origin = frames[0]['wallSeconds']
        overview = [min(frames, key=lambda f: abs(f['requestedGameSeconds']-(2+4*i))) for i in range(8)]
        handback = [f for f in frames if handoff-1 <= f['requestedGameSeconds'] <= handoff+3]
        assert handback and len(handback) >= 30
        detail = []
        for i, offset in enumerate([0., .10, .20, .40, .75]):
            frame = min(frames, key=lambda f: abs(f['requestedGameSeconds']-handoff-offset))
            name = f'{label}-handoff-detail-{i+1}.png'
            shutil.copyfile(manifest.parent/frame['file'], args.out/name)
            detail.append({'file': name, 'secondsFromHandoff': frame['requestedGameSeconds']-handoff})
        packet['variants'][label] = {
            'tourSheets': make_sheets(manifest.parent, overview, origin, args.out, label+'-tour'),
            'handoffEveryCapturedFrame': make_sheets(manifest.parent, handback, origin, args.out, label+'-handoff'),
            'fullResolutionDetails': detail}
        mapping[label] = {'evidence': str(path), 'handoffReplaySeconds': handoff}
    (args.out/'sequence.json').write_text(json.dumps(packet, indent=2)+'\n')
    args.mapping.parent.mkdir(parents=True, exist_ok=True)
    args.mapping.write_text(json.dumps(mapping, indent=2)+'\n')
    print('Blind intro integration packet prepared; no quality verdict')


if __name__ == '__main__':
    main()
