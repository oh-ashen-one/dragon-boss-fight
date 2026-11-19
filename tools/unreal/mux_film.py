#!/usr/bin/env python3
"""Join one native film run's video frames and its recorded game audio into a single MP4.

Input: an Evidence/native-*/unreal-* run captured with --video-fps and --audio-capture-seconds.
The video is the unchanged native frames at their capture times (encode_video.py); the audio is
the game's own master recording. They are aligned with the offset the game wrote to evidence.json
(audioStartVideoSeconds). Nothing is generated, retimed or mixed in.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('run', type=Path)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--world-index', type=int, default=0)
p.add_argument('--clock', choices=('callback', 'requested'), default='callback', help='passed to encode_video.py')
a = p.parse_args()
run = a.run.resolve(strict=True)
manifest = run / 'native-video' / 'frames.jsonl'
evidence = json.loads((run / 'evidence.json').read_text())
audio = sorted((run.parent / 'master-audio').glob('*.wav'))
assert manifest.is_file(), 'run has no native video'
assert audio, 'run has no master recording'
assert not a.output.exists(), 'refusing to overwrite the output'
silent = a.output.with_suffix('.silent.mp4')
if not silent.exists():
    subprocess.run([sys.executable, str(Path(__file__).with_name('encode_video.py')), str(manifest),
                    '--world-index', str(a.world_index), '--output', str(silent), '--threads', '4', '--clock', a.clock], check=True)
first = next(json.loads(line) for line in manifest.read_text().splitlines()
             if line.strip() and json.loads(line).get('type') == 'frame' and json.loads(line).get('worldIndex', 0) == a.world_index)
# A run that restarts the world after its ending leaves one recording per world. Their file names carry the
# start time in 100 ns ticks; evidence.json holds the video-clock start of the last one. The film uses the
# recording of the requested world.
ticks = [int(path.stem.rsplit('-', 1)[1]) for path in audio]
chosen = min(a.world_index, len(audio) - 1)
audio_start = float(evidence.get('audioStartVideoSeconds', 0.0)) - (ticks[-1] - ticks[chosen]) / 1e7
audio = [audio[chosen]]
# Audio position of the first encoded video frame.
offset = first['wallSeconds'] - audio_start
cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', str(silent)]
cmd += (['-ss', f'{offset:.4f}'] if offset >= 0 else ['-itsoffset', f'{-offset:.4f}']) + ['-i', str(audio[0])]
cmd += ['-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', str(a.output)]
subprocess.run(cmd, check=True)
probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_type,codec_name', '-of', 'json', str(a.output)],
                       check=True, capture_output=True, text=True)
(a.output.with_suffix('.json')).write_text(json.dumps({
    'run': str(run), 'audio': str(audio[0]), 'audioOffsetSeconds': offset, 'sourceId': evidence.get('sourceId'),
    'mode': evidence.get('mode'), 'passed': evidence.get('passed'), 'probe': json.loads(probe.stdout)}, indent=1) + '\n')
print('film', a.output)
