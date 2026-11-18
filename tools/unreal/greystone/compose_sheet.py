#!/usr/bin/env python3
"""Lay out a skin-sheet run's frames in one PNG, the owner's pick first, for a by-eye decision. No engine.

usage: compose_sheet.py <Local/greystone/skin-sheet-*> [--owner Local/knight-candidates/greystone-owner-pick-20261118.png]
Writes <run>/sheet.png. Rows: front views, side views; columns: owner pick, then each subject. Labels are file names
only; nothing is scored.
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument('run', type=Path)
p.add_argument('--owner', type=Path, default=ROOT / 'Local/knight-candidates/greystone-owner-pick-20261118.png',
               help='the owner pick (it lives in the main checkout Local/; pass that path from a worktree)')
p.add_argument('--cell', type=int, default=512)
a = p.parse_args()
run = a.run.resolve()
frames = json.loads((run / 'frames.json').read_text())['frames']
subjects = list(dict.fromkeys(f['subject'] for f in frames))
cell = a.cell
sheet = Image.new('RGB', (cell * (len(subjects) + 1), cell * 2 + 24), (24, 24, 24))
draw = ImageDraw.Draw(sheet)


def put(image, column, row):
    image = image.convert('RGB')
    image.thumbnail((cell, cell))
    sheet.paste(image, (column * cell + (cell - image.width) // 2, 24 + row * cell + (cell - image.height) // 2))


if a.owner.is_file():
    put(Image.open(a.owner), 0, 0)
draw.text((6, 4), 'owner pick', fill=(230, 230, 230))
for column, subject in enumerate(subjects, start=1):
    draw.text((column * cell + 6, 4), subject, fill=(230, 230, 230))
    for frame in frames:
        if frame['subject'] == subject:
            put(Image.open(run / frame['file']), column, 0 if frame['view'] == 'front' else 1)
sheet.save(run / 'sheet.png')
print(run / 'sheet.png')
