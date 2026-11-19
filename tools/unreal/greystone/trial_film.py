#!/usr/bin/env python3
"""Trial T6: the side-by-side trial film, current KnightB (left) beside Greystone (right). No engine in this script.

Plan (two owned rendered launches, one at a time, only after `definition` succeeded and the editor DLL is rebuilt):
  1. tools/unreal/run_native.py --gpu-slot ~/.cache/gpu-slot/bin/gpu_slot.sh --mode blendproof --video-fps 15 \
         --extra-arg -VeyrGreystoneTrialProof
  2. the same plus --extra-arg -VeyrGreystone
  3. tools/unreal/blendproof_encode.py <each Evidence/native-blendproof-*>   (per-sequence MP4s, data overlay)
  4. this script: trial_film.py <run 1> <run 2>  -> Local/greystone/trial-film-<UTC>/trial-film.mp4
The -VeyrGreystoneTrialProof set is: 1.3 s idle, a one-hand run (side), the primary attack (side and three-quarter),
a plain roll (side), each followed by 1.5 s idle; both runs use the same sequences, camera and proof floor.
Each pair is scaled to the same height, labelled by rig only, padded to the longer clip (last frame held), then the
pairs are concatenated in sequence order. Nothing is scored here; the film goes to the critic.
"""
import argparse
import datetime
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[3]
p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument('knight_run', type=Path)
p.add_argument('greystone_run', type=Path)
p.add_argument('--height', type=int, default=540)
p.add_argument('--root', type=Path, default=ROOT)
a = p.parse_args()
ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
assert ffmpeg and ffprobe, 'ffmpeg and ffprobe are required'


def media(run):
    unreal = sorted(Path(run).resolve().glob('unreal-blendproof-*'))
    assert len(unreal) == 1, f'{run}: expected one unreal-blendproof-* folder'
    evidence = json.loads((unreal[0] / 'evidence.json').read_text())
    proof = evidence['blendProof']
    assert proof.get('greystoneTrialProof'), f'{run}: not a -VeyrGreystoneTrialProof run'
    rig = (evidence.get('knightRig') or {}).get('definition', 'unknown')
    return unreal[0] / 'blendproof-media', [s['name'] for s in proof['sequences']], rig, evidence.get('knightRig')


def duration(path):
    out = subprocess.run([ffprobe, '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


k_dir, k_seq, k_rig, k_info = media(a.knight_run)
g_dir, g_seq, g_rig, g_info = media(a.greystone_run)
assert k_seq == g_seq, f'sequence lists differ: {k_seq} vs {g_seq}'
assert g_info and g_info.get('greystone'), 'right-hand run did not show Greystone (knightRig.greystone false)'
assert not (k_info or {}).get('greystone'), 'left-hand run showed Greystone, expected KnightB'
stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
out = a.root.resolve() / 'Local/greystone' / f'trial-film-{stamp}'
out.mkdir(parents=True)
pairs = []
for name in k_seq:
    left, right = k_dir / f'{name}.mp4', g_dir / f'{name}.mp4'
    if not left.is_file() or not right.is_file():
        pairs.append({'name': name, 'skipped': 'missing ' + ('left' if not left.is_file() else 'right')})
        continue
    length = max(duration(left), duration(right))
    pair = out / f'{len(pairs):02d}-{name}.mp4'
    label = "drawtext=text='{}':x=12:y=12:fontsize=22:fontcolor=white:box=1:boxcolor=black@0.5"
    graph = (f'[0:v]scale=-2:{a.height},tpad=stop_mode=clone:stop_duration={length},trim=duration={length},'
             f'{label.format("KnightB")}[l];'
             f'[1:v]scale=-2:{a.height},tpad=stop_mode=clone:stop_duration={length},trim=duration={length},'
             f'{label.format("Greystone")}[r];[l][r]hstack=inputs=2,fps=30,format=yuv420p[v]')
    subprocess.run([ffmpeg, '-v', 'error', '-y', '-i', str(left), '-i', str(right), '-filter_complex', graph,
                    '-map', '[v]', '-an', '-c:v', 'libx264', '-crf', '18', str(pair)], check=True)
    pairs.append({'name': name, 'file': pair.name, 'seconds': length})
made = [out / x['file'] for x in pairs if 'file' in x]
assert made, 'no sequence had both clips'
concat = out / 'pairs.ffconcat'
concat.write_text('ffconcat version 1.0\n' + ''.join(f"file '{m.name}'\n" for m in made))
film = out / 'trial-film.mp4'
subprocess.run([ffmpeg, '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(concat), '-c', 'copy', str(film)], check=True)
receipt = {'film': str(film), 'seconds': duration(film), 'pairs': pairs, 'left': {'run': str(a.knight_run), 'rig': k_rig},
           'right': {'run': str(a.greystone_run), 'rig': g_rig, 'knightRig': g_info}}
(out / 'trial-film.json').write_text(json.dumps(receipt, indent=1) + '\n')
print(film)
