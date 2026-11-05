#!/usr/bin/env python3
"""Encode matched three-view source studies, with no text burned into video."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT/'Local/AttackSources20261105/ACCADMale1'
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--weapon-pair-directory', type=Path)
a = p.parse_args()
output = a.output.resolve()
assert output.is_dir()
variants = [
    ('before', 'Reference3Inspection', 'ACCAD_StandToRun_v3reference', list(range(24, 91))),
    ('footpaths', 'ContactFitInspection', 'ACCAD_StandToRun_v4contacts', list(range(67))),
    ('after', 'SupportFitInspection', 'ACCAD_StandToRun_v5support', list(range(0, 265, 4)))]
if a.weapon_pair_directory:
    folder = a.weapon_pair_directory.resolve(strict=True).relative_to(BASE).as_posix()
    variants = [('weapon-before', folder, 'ACCAD_StandToRun_v5support', list(range(0, 265, 4))),
                ('weapon-after', folder, 'ACCAD_StandToRunTwoHand_v6weapon', list(range(0, 265, 4)))]
baseline = json.loads((BASE/variants[0][1]/(variants[0][2]+'.json')).read_text())
reports = []
for label, folder, clip, frames in variants:
    metadata = json.loads((BASE/folder/(clip+'.json')).read_text())
    assert metadata['viewOrthoScales'] == baseline['viewOrthoScales']
    assert metadata['groundHeightSourceUnits'] == baseline['groundHeightSourceUnits'] == 0
    assert metadata['reviewFPS'] == 30 and len(frames) == 67
    files = [BASE/folder/'Evidence'/clip/f'{view}_{frame:04d}.png'
             for view in ['front', 'side', 'threequarter'] for frame in frames]
    assert all(f.is_file() for f in files)
    work = BASE/('encode-start-'+label)
    assert not work.exists()
    work.mkdir()
    movie = output/('accad-start-'+label+'.mp4')
    assert not movie.exists()
    try:
        for i, source in enumerate(files):
            os.link(source, work/f'frame-{i:06d}.png')
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-n',
            '-framerate', '30', '-i', str(work/'frame-%06d.png'), '-c:v', 'libx264', '-threads', '2',
            '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p', '-map_metadata', '-1',
            '-an', '-movflags', '+faststart', str(movie)], check=True)
        probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries',
            'stream=nb_frames,avg_frame_rate:format=duration', '-of', 'json', str(movie)], text=True))
        assert int(probe['streams'][0]['nb_frames']) == len(files) == 201
        assert abs(float(probe['format']['duration'])-6.7) < .001
        reports.append({'variant': label, 'movie': movie.name, 'movieSHA256': hashlib.sha256(movie.read_bytes()).hexdigest(),
            'frameSequenceSHA256': hashlib.sha256(''.join(hashlib.sha256(f.read_bytes()).hexdigest() for f in files).encode()).hexdigest(),
            'frames': len(files), 'fps': 30, 'durationSeconds': 6.7, 'views': ['front', 'side', 'threequarter'],
            'sourceReview': str((BASE/folder).relative_to(ROOT)), 'sourceFramesPerView': frames,
            'matchedCameraAndFloor': True, 'editorialTextBurnedIn': False})
    finally:
        shutil.rmtree(work)
report = {'scope': 'Matched full source motion over the same captured interval; source study, not native integration or quality acceptance',
          'sourceLicense': 'CC BY 3.0', 'attribution': 'Open Motion Project by ACCAD/The Ohio State University. Retargeted and corrected for Veyr.',
          'licenseURL': 'https://creativecommons.org/licenses/by/3.0/', 'movies': reports}
if a.weapon_pair_directory:
    report['additionalSourceLicense'] = 'Adobe Mixamo project incorporation; no raw-library redistribution'
report_name = 'accad-weapon-start-review-movies.json' if a.weapon_pair_directory else 'accad-start-review-movies.json'
(ROOT/'docs/master-goal-20261103'/report_name).write_text(json.dumps(report, indent=2)+'\n')
print('Verified matched source-study films', len(reports), flush=True)
