#!/usr/bin/env python3
"""One PNG per cue: waveform and spectrogram of every cut variant, for looking at head, peak, tail and noise floor.
  ~/.cache/earshot/venv/bin/python tools/audio/qc_sheet.py Unreal/Veyr/Content/Audio/Recorded20261118 OUT_DIR [Cue ...]
"""
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

RATE = 24000
folder, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
files = sorted(folder.glob('*_*.pcm'))
cues = sorted({f.name.rsplit('_', 1)[0] for f in files})
if len(sys.argv) > 3:
    cues = [c for c in cues if c in sys.argv[3:]]
for cue in cues:
    items = sorted(folder.glob(cue + '_*[0-9].pcm'), key=lambda f: int(''.join(ch for ch in f.stem.rsplit('_', 1)[1] if ch.isdigit())))
    fig, axes = plt.subplots(len(items), 2, figsize=(11, 1.25 * len(items) + 0.4), squeeze=False)
    for row, f in zip(axes, items):
        x = np.frombuffer(f.read_bytes(), dtype='<i2') / 32768
        t = np.arange(len(x)) / RATE
        row[0].plot(t, x, lw=0.4, color='#222')
        row[0].set_ylim(-1, 1)
        row[0].set_xlim(0, max(t[-1], 0.5))
        row[0].set_ylabel(f.stem.rsplit('_', 1)[1], rotation=0, labelpad=8)
        row[0].tick_params(labelsize=6)
        row[1].specgram(x, NFFT=512, Fs=RATE, noverlap=384, cmap='magma', vmin=-110, vmax=-30)
        row[1].set_xlim(0, max(t[-1], 0.5))
        row[1].tick_params(labelsize=6)
    fig.suptitle(cue, fontsize=8, y=0.995)
    fig.tight_layout(pad=0.3)
    fig.savefig(out / (cue + '.png'), dpi=70)
    plt.close(fig)
    print(out / (cue + '.png'))
