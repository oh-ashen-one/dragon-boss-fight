#!/usr/bin/env python3
"""Prepare a neutral full-frame source comparison; keep mapping outside packet."""
import json
from pathlib import Path
import secrets
import tempfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'Local/AttackSources20261105/ACCADMale1/WeaponPairInspection'
MAPPING = ROOT/'Local/Fortress20261103/accad-weapon-blind-mapping.json'
assert not MAPPING.exists(), 'Do not silently rerun a first blind round'
names = ['ACCAD_StandToRun_v5support', 'ACCAD_StandToRunTwoHand_v6weapon']
metadata = [json.loads((SOURCE/(n+'.json')).read_text()) for n in names]
assert metadata[0]['frames'] == metadata[1]['frames']
assert metadata[0]['viewOrthoScales'] == metadata[1]['viewOrthoScales']
assert all(m['groundHeightSourceUnits'] == 0 and m['reviewFPS'] == 30 for m in metadata)
secrets.SystemRandom().shuffle(names)
out = Path(tempfile.mkdtemp(prefix='veyr-source-review-'))
packet = {'scope': 'Two versions of a two-handed greatsword run-start, matched floor0, cameras, timing and lighting. '
          'All30fps sampled frames from all three views appear on sheets in five columns, left-to-right then top-to-bottom; black cells are padding. '
          'Full-size side details and unchanged-pixel upper-body crops supplement the sheets. '
          'Assess visible whole-body quality, weight, sword hold/contact, shoulders/elbows/wrists, foot support and motion continuity. '
          'No numerical metrics or development identity are supplied. This is source-animation review, not native gameplay or live-video proof.',
          'variants': {}}
mapping = {}
for label, name in zip(['A', 'B'], names):
    meta = json.loads((SOURCE/(name+'.json')).read_text())
    frames = meta['frames']; packet['variants'][label] = {'sheets': [], 'details': []}
    for view in ['front', 'side', 'threequarter']:
        for page, start in enumerate(range(0, len(frames), 25), 1):
            chosen = frames[start:start+25]; sheet = Image.new('RGB', (1600, 1600))
            for i, f in enumerate(chosen):
                with Image.open(SOURCE/'Evidence'/name/f'{view}_{f:04d}.png') as im:
                    sheet.paste(im.convert('RGB').resize((320, 320), Image.Resampling.LANCZOS), ((i%5)*320, (i//5)*320))
            filename = f'{label}-{view}-{page}.jpg'; sheet.save(out/filename, quality=95)
            packet['variants'][label]['sheets'].append({'file': filename, 'seconds': [f/meta['sourceFPS'] for f in chosen]})
    for i, f in enumerate([0, 128, 204], 1):
        im = Image.open(SOURCE/'Evidence'/name/f'side_{f:04d}.png').convert('RGB')
        full = f'{label}-detail-{i}.png'; crop = f'{label}-upper-{i}.png'
        im.save(out/full); im.crop((180, 160, 780, 650)).save(out/crop)
        packet['variants'][label]['details'].append({'file': full, 'upperBodyCrop': crop, 'seconds': f/meta['sourceFPS']})
    mapping[label] = name
assert len(list(out.glob('*.jpg')))+len(list(out.glob('*.png'))) == 30
(out/'sequence.json').write_text(json.dumps(packet, indent=2)+'\n')
MAPPING.write_text(json.dumps({'packet': str(out), 'mapping': mapping}, indent=2)+'\n')
print('Prepared neutral full-source packet:', out)
