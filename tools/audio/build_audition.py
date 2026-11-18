#!/usr/bin/env python3
"""Build the old-against-new audition page for the recorded set.

  python3 tools/audio/build_audition.py --receipt docs/audio-20261118/recorded-set.json \
      --audio-root Unreal/Veyr/Content/Audio --code-tones Local/AudioSources20261118/_code_tones \
      --out Local/playtest-goal-review
Writes <out>/audio/{old,new}/*.wav and <out>/audio.html. Old = what the game plays by default today (the Overhaul
file, else the code-generated tone rendered by render_code_tones.py).
"""
import argparse
import html
import json
from pathlib import Path
import wave

p = argparse.ArgumentParser()
p.add_argument('--receipt', type=Path, required=True)
p.add_argument('--audio-root', type=Path, required=True)
p.add_argument('--code-tones', type=Path, required=True)
p.add_argument('--recorded', type=Path, required=True, help='folder with the <Cue>_<n>.pcm variants (the staged set)')
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
receipt = json.loads(a.receipt.read_text())
RATE = 24000
GROUPS = [
    ('Knight', [('Swing', 'Sword swing'), ('HeavySwing', 'Heavy swing'), ('Footstep', 'Footstep'), ('Roll', 'Roll'),
                ('Blink', 'Blink'), ('Heal', 'Drink')]),
    ('Hits', [('Contact', 'Blade hit'), ('Guard', 'Guard'), ('ArmorHit', 'Armour hit'), ('Death', 'Knight falls')]),
    ('Dragon', [('DragonStep', 'Dragon step'), ('DragonSwing', 'Limb and tail whoosh'), ('Bite', 'Bite'),
                ('Wing', 'Wing flap'), ('DragonBreathIn', 'Breath in'), ('DragonBreathOut', 'Breath out'),
                ('DragonGrowlLow', 'Low growl'), ('DragonSnort', 'Snort'), ('Breath', 'Fire ignite'),
                ('Fire', 'Fire roar'), ('Exposed', 'Collapse')]),
    ('World', [('Impact', 'Ground impact'), ('Break', 'Stone break'), ('Debris', 'Debris'), ('Victory', 'Victory')]),
]
OLD_DIRS = ['Overhaul', 'Polish20261102', 'DragonLibrary20261103']
for sub in ('old', 'new'):
    for stale in (a.out / 'audio' / sub).glob('*.wav'):
        stale.unlink()
(a.out / 'audio/old').mkdir(parents=True, exist_ok=True)
(a.out / 'audio/new').mkdir(parents=True, exist_ok=True)


def to_wav(pcm, target):
    with wave.open(str(target), 'wb') as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(RATE)
        w.writeframes(Path(pcm).read_bytes())


def old_for(cue):
    for d in OLD_DIRS:
        f = a.audio_root / d / (cue + '.pcm')
        if f.exists():
            return f
    f = a.code_tones / (cue + '.pcm')
    return f if f.exists() else None


rows = []
for group, cues in GROUPS:
    rows.append(f'<h2>{group}</h2>')
    for cue, label in cues:
        info = receipt.get(cue, {})
        old = old_for(cue)
        cells = []
        if old:
            to_wav(old, a.out / f'audio/old/{cue}.wav')
            cells.append(f'<button class="old" data-src="audio/old/{cue}.wav">now</button>')
        else:
            cells.append('<span class="none">none</span>')
        loop = ' data-loop="1"' if info.get('loop') else ''
        for v in info.get('variants', []):
            n = v['file'].rsplit('_', 1)[1].split('.')[0]
            to_wav(a.recorded / v['file'], a.out / f'audio/new/{cue}_{n}.wav')
            title = html.escape(v['title'].rsplit('.', 1)[0] if v['title'].lower().endswith(('.wav', '.mp3', '.flac', '.ogg', '.aiff')) else v['title'])
            cells.append(f'<span class="v"><button data-src="audio/new/{cue}_{n}.wav"{loop}>{n}</button>'
                         f'<a href="{v["page"]}" target="_blank" rel="noopener" title="{title}">{title[:26]}</a></span>')
        rows.append(f'<div class="row"><div class="name">{html.escape(label)}</div><div class="cells">{"".join(cells)}</div></div>')

page = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Veyr audio audition</title><style>
:root{color-scheme:dark;--bg:#101012;--panel:#18181b;--line:#2a2a30;--text:#e7e4dc;--dim:#8d8a82;--gold:#c8a45a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.4 ui-sans-serif,system-ui,sans-serif;padding:20px 16px 60px;max-width:1100px;margin:0 auto}
h1{font-size:18px;font-weight:600;margin:0 0 12px}h2{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--gold);margin:26px 0 8px;font-weight:600}
.row{display:grid;grid-template-columns:170px 1fr;gap:12px;padding:10px 0;border-top:1px solid var(--line);align-items:start}
.name{font-weight:500;padding-top:6px}.cells{display:flex;flex-wrap:wrap;gap:10px 14px}
.v{display:flex;align-items:center;gap:6px}
button{background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:6px;min-width:44px;height:34px;padding:0 12px;font:inherit;cursor:pointer}
button:hover{border-color:var(--gold)}button.on{background:var(--gold);color:#111;border-color:var(--gold)}
button.old{color:var(--dim);border-style:dashed}.none{color:var(--dim);padding:6px 10px;border:1px dashed var(--line);border-radius:6px}
a{color:var(--dim);font-size:12px;text-decoration:none;max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}a:hover{color:var(--text)}
@media(max-width:640px){.row{grid-template-columns:1fr}.name{padding-top:0}}
</style></head><body><h1>Veyr audio</h1>
''' + '\n'.join(rows) + '''
<script>
let cur=null,btn=null;const audio=new Audio();
function stop(){audio.pause();if(btn)btn.classList.remove('on');btn=null}
document.querySelectorAll('button[data-src]').forEach(b=>b.onclick=()=>{
 if(btn===b){stop();return}
 stop();audio.src=b.dataset.src;audio.loop=!!b.dataset.loop;audio.currentTime=0;audio.play();btn=b;b.classList.add('on');
});
audio.onended=()=>{if(btn)btn.classList.remove('on');btn=null};
document.addEventListener('keydown',e=>{if(e.key===' '){e.preventDefault();stop()}});
</script></body></html>'''
(a.out / 'audio.html').write_text(page)
print('wrote', a.out / 'audio.html', 'rows', page.count('class="row"'))
