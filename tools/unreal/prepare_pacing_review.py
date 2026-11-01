#!/usr/bin/env python3
"""Make anonymous, uniformly sampled native timelines for a pacing critic.

This does not replace watching the continuous movies: metadata explicitly says
that the sheets establish order/progress, not continuous-motion quality.
"""
import argparse
import json
from pathlib import Path
import secrets

from PIL import Image
from encode_video import read_capture


def prepare(before, after, directory, mapping_file):
    directory, mapping_file = directory.resolve(), mapping_file.resolve()
    if mapping_file.is_relative_to(directory):
        raise ValueError('Private mapping must be outside the blind directory')
    if directory.exists() or mapping_file.exists():
        raise ValueError('Refusing to overwrite a review')
    versions = [before.resolve(), after.resolve()]
    secrets.SystemRandom().shuffle(versions)
    captures = {label: (path, read_capture(path, world_index=0))
                for label, path in zip(('A', 'B'), versions)}
    source_ids = {rows[1][0]['sourceId'] for _, rows in captures.values()}
    if len(source_ids) != 1:
        raise ValueError('Pacing comparison must use the same build')
    directory.mkdir(parents=True)
    manifest = {'scope': 'Uniform 2-second native frame samples, plus the last frame; '
                'read sheets left-to-right then top-to-bottom. Black cells are padding. '
                'No generated/interpolated frames. Sheets show temporal progress but '
                'cannot establish continuous motion quality or human gameplay feel.',
                'variants': {}}
    for label, (path, (_, frames, end, observed_tail, _)) in captures.items():
        if not observed_tail:
            raise ValueError('Capture lacks an observed world end')
        origin = frames[0]['wallSeconds']
        chosen = []
        target = 0.0
        while target <= frames[-1]['wallSeconds'] - origin:
            chosen.append(min(frames, key=lambda f: abs(f['wallSeconds'] - origin - target)))
            target += 2.0
        if chosen[-1]['file'] != frames[-1]['file']:
            chosen.append(frames[-1])
        pages = []
        for page, start in enumerate(range(0, len(chosen), 16), 1):
            tile_frames = chosen[start:start + 16]
            sheet = Image.new('RGB', (1920, 1080))
            for index, frame in enumerate(tile_frames):
                with Image.open(path.parent / frame['file']) as im:
                    sheet.paste(im.convert('RGB').resize((480, 270), Image.Resampling.LANCZOS),
                                ((index % 4) * 480, (index // 4) * 270))
            name = f'{label}-timeline-{page:02}.jpg'
            sheet.save(directory / name, quality=94)
            pages.append({'file': name, 'tileElapsedSeconds':
                          [round(f['wallSeconds'] - origin, 3) for f in tile_frames]})
        with Image.open(path.parent / frames[-1]['file']) as im:
            im.convert('RGB').save(directory / f'{label}-last.jpg', quality=96)
        manifest['variants'][label] = {'durationSeconds': end - origin, 'sheets': pages,
                                      'lastDetail': f'{label}-last.jpg'}
    (directory / 'sequence.json').write_text(json.dumps(manifest, indent=2) + '\n')
    mapping_file.parent.mkdir(parents=True, exist_ok=True)
    mapping_file.write_text(json.dumps({label: str(path) for label, (path, _) in captures.items()}, indent=2) + '\n')
    print('Anonymous pacing sequences prepared')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--mapping', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.before, args.after, args.directory, args.mapping)
