#!/usr/bin/env python3
"""Re-check the licence on the Freesound page of every sound used in the receipt (public page, no account).
  python3 tools/audio/verify_licenses.py docs/audio-20261118/recorded-set.json
Adds "licenseCheck" (the licence name read from the page, and the date) to each variant; exits 1 if any is not CC0.
"""
import datetime
import json
from pathlib import Path
import re
import subprocess
import sys
import time

path = Path(sys.argv[1])
receipt = json.loads(path.read_text())
cache, bad = {}, 0
for cue, info in receipt.items():
    for v in info['variants']:
        page = v['page']
        if page not in cache:
            html = subprocess.run(['curl', '-sS', '-L', '--max-time', '40', '-A', 'Mozilla/5.0 (Macintosh) game-sound-research', page],
                                  capture_output=True, text=True).stdout
            time.sleep(0.8)
            if 'creativecommons.org/publicdomain/zero' in html or 'Creative Commons 0' in html:
                cache[page] = 'Creative Commons 0'
            else:
                m = re.search(r'creativecommons\.org/licenses/([a-z-]+)/', html)
                cache[page] = ('CC ' + m.group(1)) if m else 'unknown'
        v['licenseCheck'] = {'name': cache[page], 'checked': datetime.date.today().isoformat()}
        if cache[page] != 'Creative Commons 0':
            bad += 1
            print('NOT CC0', cue, v['file'], page, cache[page])
path.write_text(json.dumps(receipt, indent=1) + '\n')
print(len(cache), 'pages checked,', bad, 'not CC0')
sys.exit(1 if bad else 0)
