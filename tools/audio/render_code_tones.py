#!/usr/bin/env python3
"""Render the code-generated cues of VeyrAudio.cpp (BuildSamples) so they can be heard and measured.

A line-for-line Python port of the synthesis in AVeyrAudio::BuildSamples (xorshift noise, same filters, same
envelopes). Writes 24 kHz mono 16-bit <Cue>.pcm files. Used for the audition page (old next to new) and for the
level targets of cues that have no recorded file in the game today.
  python3 tools/audio/render_code_tones.py Local/AudioSources20261118/_code_tones
"""
import math
from pathlib import Path
import sys

RATE = 24000
TAU = 6.283185307179586
CUES = ['Swing', 'HeavySwing', 'Contact', 'Guard', 'Impact', 'Breath', 'Fire', 'Heal', 'Exposed', 'Death', 'Victory']
LENGTHS = [.32, .55, .48, .38, 1.15, 1.45, 2.1, 1.2, .65, 1.6, 2.2]


def tone(f, t):
    return math.sin(TAU * f * t)


def decay(t, r):
    return math.exp(-t * r)


def render(cue, length):
    count = round(length * RATE)
    seed, low, mid, phase = 0xB7471C53, 0.0, 0.0, 0.0
    raw, peak = [], .001
    for i in range(count):
        t = i / RATE
        seed ^= (seed << 13) & 0xFFFFFFFF
        seed ^= seed >> 17
        seed ^= (seed << 5) & 0xFFFFFFFF
        noise = seed / 2147483648.0 - 1.0
        low += .035 * (noise - low)
        mid += .25 * (noise - mid)
        v = 0.0
        if cue in ('Swing', 'HeavySwing'):
            heavy = cue == 'HeavySwing'
            c, w = (.35, .11) if heavy else (.13, .065)
            x = (t - c) / w
            v = (mid - low) * math.exp(-x * x) * 1.7 + tone(1741, t) * .035 * decay(t, 14)
        elif cue == 'Contact':
            v = (math.sin(TAU * (48 * t + 4.5 * (1 - decay(t, 20)))) * decay(t, 10) * .63 + (noise - mid) * decay(t, 100) * .5
                 + low * decay(t, 8) * .7 + tone(851, t) * decay(t, 25) * .06)
        elif cue == 'Guard':
            v = (tone(977, t) + .45 * tone(1543, t) + .2 * tone(2311, t)) * decay(t, 15) * .4 + noise * decay(t, 75) * .15
        elif cue == 'Impact':
            v = (math.sin(TAU * (36 * t + 4.3 * (1 - decay(t, 13)))) * decay(t, 5) * .7 + tone(118, t) * decay(t, 24) * .18
                 + low * decay(t, 3) + (mid - low) * decay(t, 7) * .4)
        elif cue == 'Breath':
            phase += TAU * (45 + 12 * math.sin(t * 2.4) + 2 * tone(11, t)) / RATE
            v = ((math.sin(phase) * .4 + math.sin(phase * 2) * .15 + (mid - low) * 1.2)
                 * min(1.0, t / .22) * min(1.0, (length - t) / .4))
        elif cue == 'Fire':
            v = (low * .9 + (mid - low) * .8) * (.8 + .2 * tone(17, t)) * min(1.0, t / .12) * min(1.0, (length - t) / .4)
        elif cue in ('Heal', 'Exposed', 'Victory'):
            freqs = [329.628, 440, 493.883, 659.255]
            offset = .24 if cue == 'Victory' else .085
            pitch = 1.5 if cue == 'Exposed' else 1.0
            for n in range(4):
                nt = t - n * offset
                if nt >= 0:
                    v += ((tone(freqs[n] * pitch, nt) + .12 * tone(freqs[n] * pitch * 2.003, nt))
                          * (1 - decay(nt, 70)) * decay(nt, 2.5 if cue == 'Victory' else 5.0) * .2)
        elif cue == 'Death':
            v = (math.sin(TAU * (55 * t + 6 * (1 - decay(t, 2)))) * .5 + low * .5) * decay(t, 2.5)
        v *= min(1.0, t / .003) * min(1.0, (length - t) / .05)
        raw.append(v)
        peak = max(peak, abs(v))
    return [max(-.65, min(.65, x / peak * .65)) for x in raw]


if __name__ == '__main__':
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    import struct
    for cue, length in zip(CUES, LENGTHS):
        data = render(cue, length)
        (out / f'{cue}.pcm').write_bytes(struct.pack('<%dh' % len(data), *[int(x * 32767) for x in data]))
        print(cue, len(data) / RATE, 's')
