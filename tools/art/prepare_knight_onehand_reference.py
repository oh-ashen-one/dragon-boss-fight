#!/usr/bin/env python3
"""Extract the owner's one-hand GIF for the synchronized private local review."""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('gif', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    digest = hashlib.sha256(args.gif.read_bytes()).hexdigest()
    expected = '7406671d0795781d5d835928effda4ee5937bec928845a98077e52ced4da685b'
    if digest != expected:
        raise ValueError('Reference differs from the owner-supplied Black Knight GIF')
    with Image.open(args.gif) as source:
        frames = []
        if source.n_frames != 37:
            raise ValueError('Unexpected reference frame count')
        for index in range(source.n_frames):
            source.seek(index)
            if source.info.get('duration') != 50:
                raise ValueError('Reference timeline is not 50 milliseconds per frame')
            frames.append(source.convert('RGB'))
    args.output.mkdir(parents=True, exist_ok=True)
    for index, frame in enumerate(frames):
        frame.save(args.output / f'frame-{index:02}.jpg', quality=94)
    (args.output / 'manifest.json').write_text(json.dumps({
        'sourceSha256': digest, 'frameCount': len(frames), 'secondsPerFrame': .05,
        'source': 'https://cdnb.artstation.com/p/assets/images/images/032/421/303/original/elhuevocosmic-black-knight-gif-2.gif?1606387799',
    }, indent=2) + '\n')
    print(f'Prepared {len(frames)} private reference frames in {args.output}')


if __name__ == '__main__':
    main()
