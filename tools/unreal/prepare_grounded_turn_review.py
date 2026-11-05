#!/usr/bin/env python3
"""Blind a matched full-source turn comparison without dropping sampled poses."""
import json
from pathlib import Path
import secrets

from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'Local/AttackSources20261105/GroundedTurnPair'
OUT=Path('/private/tmp/veyr-grounded-turn-review-20261105')
MAPPING=ROOT/'Local/Fortress20261103/grounded-turn-blind-mapping.json'
assert not OUT.exists() and not MAPPING.exists()
versions=['Mixamo_Turn180_A_v3contacts','Mixamo_Turn180_A_v4grounded']
secrets.SystemRandom().shuffle(versions);OUT.mkdir()
packet={'scope':'Same sourced turn at30fps, matched fixed cameras/scale/light/floor0. '
        'Each sheet has five columns and five rows, left-to-right then top-to-bottom; black cells are padding. '
        'All sampled frames from three views are present, with full-size side details and unchanged-pixel foot crops. '
        'Judge grounding, weight transfer, pose/limb/weapon regressions. This is source-only, not engine/contact or continuous-playback proof.',
        'variants':{}}
mapping={}
for label,name in zip(['A','B'],versions):
    meta=json.loads((SOURCE/(name+'.json')).read_text());frames=meta['frames']
    assert meta['reviewFPS']==30 and meta['groundHeightSourceUnits']==0
    packet['variants'][label]={'sheets':[],'details':[]}
    for view in ['front','side','threequarter']:
        for page,start in enumerate(range(0,len(frames),25),1):
            chosen=frames[start:start+25];sheet=Image.new('RGB',(1600,1600))
            for i,f in enumerate(chosen):
                with Image.open(SOURCE/'Evidence'/name/f'{view}_{f:04d}.png') as im:
                    sheet.paste(im.convert('RGB').resize((320,320),Image.Resampling.LANCZOS),((i%5)*320,(i//5)*320))
            filename=f'{label}-{view}-{page}.jpg';sheet.save(OUT/filename,quality=95)
            packet['variants'][label]['sheets'].append({'file':filename,'seconds':[f/meta['sourceFPS'] for f in chosen]})
    for i,index in enumerate([0,len(frames)//3,2*len(frames)//3,len(frames)-1],1):
        f=frames[index];image=Image.open(SOURCE/'Evidence'/name/f'side_{f:04d}.png').convert('RGB')
        # Re-encode losslessly to remove source filenames/timestamps in PNG metadata.
        full=f'{label}-detail-{i}.png';crop=f'{label}-feet-{i}.png'
        image.save(OUT/full);image.crop((230,440,750,790)).save(OUT/crop)
        packet['variants'][label]['details'].append({'file':full,'feetCrop':crop,'seconds':f/meta['sourceFPS']})
    mapping[label]=name
(OUT/'sequence.json').write_text(json.dumps(packet,indent=2)+'\n')
MAPPING.write_text(json.dumps(mapping,indent=2)+'\n')
print('Prepared blinded source turn comparison,22 images')
