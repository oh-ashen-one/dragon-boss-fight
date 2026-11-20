#!/usr/bin/env python3
"""Build the courtyard ambience (mix pass 6) from CC0 Freesound candidates collected by freesound_candidates.py.

    python3 tools/audio/prepare_courtyard_ambience.py <candidates dir> [--content Unreal/Veyr/Content]

Writes, as the game's bed format (24 kHz mono, 16-bit little-endian PCM, seamless loops with an equal-power crossfade):
  Audio/Courtyard20261119/Ambience.pcm  night air: a low wind (high-passed at 60 Hz, low-passed at 1.2 kHz) under night insects (-12 dB),
                                         60 s, RMS -24 dBFS: the bed under everything (replaces the cathedral room tone)
  Audio/Courtyard20261119/Brazier.pcm   a fire crackle loop, RMS -28 dBFS (its crackles peak about 20 dB over it): played from each brazier, attenuated by distance
Sources and their licences go to Data/dragon/audio_sources.json ("ambience").
"""
import argparse, json, subprocess
from pathlib import Path
import numpy as np
from scipy.signal import butter, sosfilt

SR = 24000
SOURCES = {'wind': ('AmbWind', '397091'), 'night': ('AmbNight', '805466'), 'brazier': ('AmbBrazier', '813328')}


def decode(path):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-ac', '1', '-ar', str(SR), '-f', 's16le', '-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype='<i2').astype(np.float64) / 32768


def loop(x, seconds, fade=1.0):
    """A seamless loop of the given length: the source chained with equal-power crossfades, its end crossfaded into its start."""
    n, f = int(seconds * SR), int(fade * SR); w = np.linspace(0, np.pi / 2, f)
    y = x.copy()
    while len(y) < n + f:
        y = np.concatenate([y[:-f], y[-f:] * np.cos(w) + x[:f] * np.sin(w), x[f:]])
    out = y[:n].copy(); out[:f] = y[:f] * np.sin(w) + y[n:n + f] * np.cos(w)
    return out


def rms_db(x): return 10 * np.log10((x ** 2).mean() + 1e-12)


def to_rms(x, db): return x * 10 ** ((db - rms_db(x)) / 20)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('candidates', type=Path); ap.add_argument('--content', type=Path, default=Path(__file__).resolve().parents[2] / 'Unreal/Veyr/Content')
    a = ap.parse_args()
    ledger = json.loads((a.candidates / 'candidates.json').read_text())
    pick = {}
    for role, (cue, sid) in SOURCES.items():
        c = next(c for c in ledger[cue] if c['id'] == sid); assert c['license'] == 'CC0-1.0', c
        pick[role] = c
    wind = decode(a.candidates / pick['wind']['file'])
    wind = sosfilt(butter(2, 60, 'high', fs=SR, output='sos'), wind); wind = sosfilt(butter(2, 1200, 'low', fs=SR, output='sos'), wind)
    night = decode(a.candidates / pick['night']['file'])
    bed = to_rms(loop(wind, 61.0), -24) + to_rms(loop(night[:int(58 * SR)], 61.0), -36)
    bed = to_rms(bed, -24)
    fire = decode(a.candidates / pick['brazier']['file'])
    fire = to_rms(loop(fire, 35.0, .5), -28)
    out = a.content / 'Audio/Courtyard20261119'; out.mkdir(parents=True, exist_ok=True)
    for name, x in (('Ambience', bed), ('Brazier', fire)):
        assert np.abs(x).max() < .99, f'{name} would clip'
        (out / f'{name}.pcm').write_bytes((np.clip(x, -1, 1) * 32767).astype('<i2').tobytes())
        print(f'{name}.pcm {len(x) / SR:.1f} s RMS {rms_db(x):.1f} dBFS peak {20 * np.log10(np.abs(x).max()):.1f} dBFS')
    print(json.dumps({r: {k: pick[r][k] for k in ('id', 'title', 'author', 'page', 'license', 'sha256')} for r in pick}, indent=1))


if __name__ == '__main__':
    main()
