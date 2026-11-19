#!/usr/bin/env python3
"""Quality goal F: per-move table from one or more evidence.json files (dragonPlayback block).

  playback_table.py <evidence.json or run dir> [...] [--json out.json]

Per clip: mean source rate outside holds, worst one-frame rate, planted-foot slide (gate number), steps/slips, pops
(in blend / total, worst ratio), travel against the clip's root track. Several files are pooled (time-weighted rates,
max of slides).
"""
import json
import sys
from pathlib import Path


def load(path):
    p = Path(path)
    if p.is_dir():
        found = sorted(p.rglob('evidence.json'))
        if not found:
            raise SystemExit('no evidence.json under ' + str(p))
        p = found[-1]
    e = json.loads(p.read_text())
    return p, e.get('dragonPlayback', {})


def main(argv):
    out = None
    if '--json' in argv:
        i = argv.index('--json'); out = argv[i+1]; argv = argv[:i] + argv[i+2:]
    pooled = {}
    tops = []
    for a in argv:
        p, d = load(a)
        tops.append({'file': str(p), **{k: d.get(k) for k in ('clipTempo', 'twoClipBlend', 'footLock', 'slowSnapTurn', 'rootTracks',
                     'worstFrameSourceRateOutsideHolds', 'worstRateClip', 'worstPlantedSlideCmPerSec', 'worstSlideClip',
                     'poseDeltaPops', 'poseDeltaPopsInBlend', 'worstPopRatio', 'worstPopClipBone', 'gateRateAtMost1_25',
                     'gateSlideUnder5', 'gateNoBlendPops', 'dragonSkin', 'footLockDiagnostic', 'data')}})
        for k, c in d.get('clips', {}).items():
            q = pooled.setdefault(k, {'real': 0., 'source': 0., 'realNH': 0., 'sourceNH': 0., 'maxRate': 0., 'slide': 0.,
                                       'steps': 0, 'slips': 0, 'pops': 0, 'popsInBlend': 0, 'popRatio': 0., 'popBone': '',
                                       'travel': 0., 'track': 0., 'blends': {}, 'frames': 0, 'planted': 0.})
            rs = c.get('realSeconds', 0); q['real'] += rs; q['source'] += c.get('meanSourceRate', 0) * rs
            rn = rs if c.get('meanSourceRateOutsideHolds', 0) else 0
            # meanSourceRateOutsideHolds is per-file; weight by realSeconds (approximation for pooling)
            q['realNH'] += rn; q['sourceNH'] += c.get('meanSourceRateOutsideHolds', 0) * rn
            q['maxRate'] = max(q['maxRate'], c.get('maxFrameSourceRateOutsideHolds', 0))
            q['slide'] = max(q['slide'], c.get('worstPlantedSlideCmPerSec', 0))
            q['planted'] += sum(f.get('plantedSeconds', 0) for f in c.get('feet', {}).values())
            for f in ('steps', 'slips', 'pops', 'popsInBlend'):
                q[f] += c.get(f, 0)
            q['frames'] += c.get('frames', 0)
            if c.get('maxPopRatio', 0) > q['popRatio']:
                q['popRatio'] = c.get('maxPopRatio', 0); q['popBone'] = c.get('worstPopBone', '')
            q['travel'] += c.get('travelWorldCm', 0); q['track'] += c.get('trackPathWorldCm', 0)
            for b, n in c.get('blends', {}).items():
                q['blends'][b] = q['blends'].get(b, 0) + n
    for t in tops:
        print(json.dumps(t))
    print('%-22s %6s %6s %6s %7s %6s %5s %5s %9s %6s %8s %8s  %s' % ('clip', 'rate', 'rateNH', 'maxNH', 'slide', 'plantS',
          'steps', 'slips', 'pops(b/t)', 'popR', 'travel', 'track', 'blends'))
    rows = {}
    for k in sorted(pooled):
        q = pooled[k]
        rate = q['source'] / q['real'] if q['real'] else 0
        rnh = q['sourceNH'] / q['realNH'] if q['realNH'] else 0
        rows[k] = {'rate': round(rate, 3), 'rateOutsideHolds': round(rnh, 3), 'maxFrameRateOutsideHolds': round(q['maxRate'], 3),
                   'slideCmPerSec': round(q['slide'], 2), 'plantedSeconds': round(q['planted'], 2), 'steps': q['steps'],
                   'slips': q['slips'], 'pops': q['pops'], 'popsInBlend': q['popsInBlend'], 'maxPopRatio': round(q['popRatio'], 2),
                   'popBone': q['popBone'], 'travelCm': round(q['travel'], 1), 'trackCm': round(q['track'], 1), 'blends': q['blends']}
        print('%-22s %6.3f %6.3f %6.3f %7.2f %6.1f %5d %5d %4d/%-4d %6.2f %8.1f %8.1f  %s' % (k, rate, rnh, q['maxRate'], q['slide'],
              q['planted'], q['steps'], q['slips'], q['popsInBlend'], q['pops'], q['popRatio'], q['travel'], q['track'],
              ','.join('%s:%d' % kv for kv in sorted(q['blends'].items()))))
    if out:
        Path(out).write_text(json.dumps({'files': tops, 'clips': rows}, indent=1) + '\n')


if __name__ == '__main__':
    main(sys.argv[1:])
