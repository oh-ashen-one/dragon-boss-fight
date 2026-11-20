#!/usr/bin/env python3
"""Join one native film run's video frames and its recorded game audio into a single MP4.

Input: an Evidence/native-*/unreal-* run captured with --video-fps and --audio-capture-seconds.
The video is the unchanged native frames at their capture times (encode_video.py); the audio is
the game's own master recording. They are aligned with the offset the game wrote to evidence.json
(audioStartVideoSeconds). Nothing is generated, retimed or mixed in.

Default alignment is from content when the run has an audio tap (-VeyrAudioTap=<dir>, found through launch.json or --tap):
tools/audio/content_offset.py. The clock offset is wrong by tenths of a second because the master recording drops time while the
game stalls (sync test: clicks 0.2-0.5 s off their white frames; content: within 12 ms). --clock-offset restores the clock
alignment; a run without a tap falls back to it with a warning.
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
p.add_argument('--tap', type=Path, help="the run's tap VeyrTap-N-cues.json (default: from launch.json's -VeyrAudioTap)")
p.add_argument('--offset', type=float, help='audio position of video time 0 (s); overrides both alignments')
p.add_argument('--clock-offset', action='store_true', help='old alignment: recording start time against video start time')
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
alignment = 'clock'
if a.offset is not None:
    offset, alignment = first['wallSeconds'] + a.offset, 'given'
elif not a.clock_offset:
    tap = a.tap
    if tap is None:
        launch = run.parent / 'launch.json'
        args = json.loads(launch.read_text()).get('extraArgs', []) if launch.is_file() else []
        dirs = [x.split('=', 1)[1] for x in args if x.startswith('-VeyrAudioTap=')]
        if dirs: tap = Path(dirs[0]) / f'VeyrTap-{a.world_index + 1}-cues.json'
    if tap is not None and tap.is_file():
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'audio')); from content_offset import content_offset
        m, p10, p90, n = content_offset(run, tap, world_index=a.world_index)
        offset, alignment = first['wallSeconds'] + m, 'content'
        print(f'content alignment from {tap}: master minus video {m:+.3f} s (p10 {p10:+.3f}, p90 {p90:+.3f}); clock offset would be {first["wallSeconds"] - audio_start:+.3f}', flush=True)
    else:
        print('WARNING: no audio tap for this run (-VeyrAudioTap or --tap): clock alignment, typically 0.2-0.5 s off', flush=True)
cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', str(silent)]
cmd += (['-ss', f'{offset:.4f}'] if offset >= 0 else ['-itsoffset', f'{-offset:.4f}']) + ['-i', str(audio[0])]
cmd += ['-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', str(a.output)]
subprocess.run(cmd, check=True)
probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_type,codec_name', '-of', 'json', str(a.output)],
                       check=True, capture_output=True, text=True)
(a.output.with_suffix('.json')).write_text(json.dumps({
    'run': str(run), 'audio': str(audio[0]), 'audioOffsetSeconds': offset, 'alignment': alignment, 'sourceId': evidence.get('sourceId'),
    'mode': evidence.get('mode'), 'passed': evidence.get('passed'), 'probe': json.loads(probe.stdout)}, indent=1) + '\n')
print('film', a.output)
