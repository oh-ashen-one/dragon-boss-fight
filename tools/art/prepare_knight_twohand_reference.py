#!/usr/bin/env python3
"""Extract the two owner-selected reference segments for private local review."""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

EXPECTED = '689fbf1cc5055d4270cfcca77bd84ba65b28a4761fb5b680674f0a5a22e37066'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('gif', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if hashlib.sha256(args.gif.read_bytes()).hexdigest() != EXPECTED:
        raise ValueError('Reference differs from the owner-supplied two-hand GIF')
    with Image.open(args.gif) as source:
        if source.n_frames != 686:
            raise ValueError('Unexpected reference length')
        for name, start, end in [('sweep', 0, 194), ('thrust', 340, 686)]:
            output = args.output / name
            output.mkdir(parents=True, exist_ok=True)
            indices = range(start, end, 2)
            for frame, original in enumerate(indices):
                source.seek(original)
                if source.info.get('duration') != 20:
                    raise ValueError('Unexpected source frame timing')
                source.convert('RGB').save(output / f'frame-{frame:03}.jpg', quality=92)
            (output / 'manifest.json').write_text(json.dumps({
                'sourceSha256': EXPECTED,
                'sourceStartSeconds': start * .02,
                'secondsPerFrame': .04,
                'frameCount': len(indices),
                'sourceAsset': 'd7965ok-b28aa032-999c-41e8-9825-33113292d5a7.gif',
            }, indent=2) + '\n')
            print(f'{name}: {len(indices)} frames, starting at {start*.02:.2f}s')


if __name__ == '__main__':
    main()
