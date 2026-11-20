#!/usr/bin/env python3
"""Per knight contact, from one tap log (-VeyrAudioTap with -VeyrAudioTiming or the tap alone; mix pass 5 or later):
the frame and game time the contact was seen, the frame and wall time the hit's first layer was requested, the wall time the audio
render first pulled that layer's samples (probe wave), and the first sample's position in the tap's own mix.

    python3 tools/audio/hit_latency.py <VeyrTap-N-cues.json>
"""
import json, sys
from pathlib import Path
import statistics as st

d = json.loads(Path(sys.argv[1]).read_text())
items = d['items']; rows = []
for e in d['events']:
    if not e['kind'].startswith('weapon'): continue
    c = [it for it in items if it['cue'] == 'Contact' and abs(it['wall'] - e['wall']) < .05]
    if not c: rows.append((e, None)); continue
    rows.append((e, c[0]))
print(f"{'kind':12} {'frame':>7} {'gameT':>8} {'req frame':>9} {'req-contact ms':>14} {'pull-req ms':>11} {'tap sample':>10}")
lat = []; same = 0
for e, it in rows:
    if it is None: print(f"{e['kind']:12} {e['frame']:7.0f} {e['gameT']:8.3f}  no Contact layer (spacing rule)"); continue
    pull = it.get('firstPullWall', -1); pl = (pull - it['wall']) * 1000 if pull and pull > 0 else float('nan')
    if pull and pull > 0: lat.append(pl)
    same += it['frame'] == e['frame']
    print(f"{e['kind']:12} {e['frame']:7.0f} {e['gameT']:8.3f} {it['frame']:9.0f} {(it['wall']-e['wall'])*1000:14.2f} {pl:11.1f} {int(it['t']*48000):10d}")
n = sum(1 for _, it in rows if it)
print(f'{n} hits with a Contact layer; requested on the contact frame: {same}/{n}')
if lat: print(f'audio render first pull after the request: median {st.median(lat):.1f} ms, min {min(lat):.1f}, max {max(lat):.1f} (n={len(lat)})')
else: print('no probe pulls (run without a sound device: -NoSound, or before mix pass 5)')
