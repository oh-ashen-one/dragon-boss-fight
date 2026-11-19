#!/usr/bin/env python3
"""Trial T6: the side-by-side trial film, current KnightB (left) beside Greystone (right). No engine in this script.

Plan (two owned rendered launches, one at a time, only after `definition` succeeded and the editor DLL is rebuilt):
  1. tools/unreal/run_native.py --engine "/Users/Shared/Epic Games/UE_5.8" --gpu-slot ~/.cache/gpu-slot/bin/gpu_slot.sh \
         --mode blendproof --video-fps 15 --extra-arg=-VeyrGreystoneTrialProof
  2. the same plus --extra-arg=-VeyrGreystone   (write --extra-arg=-Flag: argparse rejects a bare leading dash)
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
# E3 arena film (2026-11-19): runs made with -VeyrKnightFilm and --no-proof-floor; a real fight clip per rig is appended.
p.add_argument('--fight', nargs=2, type=Path, metavar=('KNIGHT_MP4', 'GREYSTONE_MP4'),
               help='gameplay videos of a real fight (encode_video.py output), one per rig')
p.add_argument('--fight-start', nargs=2, type=float, default=(0.0, 0.0), metavar=('KNIGHT_S', 'GREYSTONE_S'))
p.add_argument('--fight-seconds', type=float, default=15.0)
a = p.parse_args()
ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
assert ffmpeg and ffprobe, 'ffmpeg and ffprobe are required'


def media(run):
    unreal = sorted(Path(run).resolve().glob('unreal-blendproof-*'))
    assert len(unreal) == 1, f'{run}: expected one unreal-blendproof-* folder'
    evidence = json.loads((unreal[0] / 'evidence.json').read_text())
    proof = evidence['blendProof']
    assert proof.get('greystoneTrialProof') or proof.get('knightFilm'), f'{run}: not a -VeyrGreystoneTrialProof or -VeyrKnightFilm run'
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
for index, name in enumerate(k_seq, 1):
    # blendproof_encode names per-sequence media '<NN>-<name>.mp4' (NN = 1-based sequence order).
    left, right = (d / f'{index:02d}-{name}.mp4' for d in (k_dir, g_dir))
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
if a.fight:
    # Both fights cut to the same length from their own start; scaled to the same height as the pairs.
    label = "drawtext=text='{}':x=12:y=12:fontsize=22:fontcolor=white:box=1:boxcolor=black@0.5"
    n = a.fight_seconds
    graph = (f'[0:v]trim=start={a.fight_start[0]}:duration={n},setpts=PTS-STARTPTS,fps=30,scale=-2:{a.height},{label.format("KnightB")}[l];'
             f'[1:v]trim=start={a.fight_start[1]}:duration={n},setpts=PTS-STARTPTS,fps=30,scale=-2:{a.height},{label.format("Greystone")}[r];'
             f'[l][r]hstack=inputs=2,format=yuv420p[v]')
    pair = out / f'{len(pairs):02d}-fight.mp4'
    subprocess.run([ffmpeg, '-v', 'error', '-y', '-i', str(a.fight[0]), '-i', str(a.fight[1]), '-filter_complex', graph,
                    '-map', '[v]', '-an', '-c:v', 'libx264', '-crf', '18', str(pair)], check=True)
    pairs.append({'name': 'fight', 'file': pair.name, 'seconds': duration(pair), 'sources': [str(x) for x in a.fight],
                  'starts': list(a.fight_start)})
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
