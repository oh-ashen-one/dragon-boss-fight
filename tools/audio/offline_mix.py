#!/usr/bin/env python3
"""Offline mixer: re-render a fight's mix from one recorded tap event log with changed gains, no engine needed.

    ~/.cache/earshot/venv/bin/python tools/audio/offline_mix.py <VeyrTap-N-cues.json> [--content Unreal/Veyr/Content]
        [--gains Landing:2/Slam:-1] [--trim DB] [--music DB] [--bed-offset DB] [--limiter DBFS] [--out mix.wav] [--verify] [--solve]

The tap (-VeyrAudioTap=<dir>) logs every voice the game starts: cue, variant, pitch, level (already including the kind gain and the
master trim), distance attenuation, pan, start time, mix kind, and the per-play tilt; and from mix pass 5 on it writes the beds (music
+ ambience at their live gains) to <stem>-beds.wav. This script loads the same samples the game loads (same order, head trim, wing
high-pass), renders each item exactly as the tap does (linear resampling, equal-power pan, the tap's engine offset), scales every item
by (new kind gain / logged kind gain) x (new trim / logged trim), adds the beds (scaled by the trim ratio, the music offset and the
measured real-engine bed offset), applies the master limiter model, and measures the targets with the blind critic's methods.

--verify   render with the logged gains and compare with the tap's own wav (loudness, per-kind peaks) and item by item (peak of each item).
--solve    iterate the per-kind gains until the median peaks of the event kinds sit on the target ladder, then print the table.
"""
import argparse, json, math, re, subprocess, sys, tempfile, wave
from pathlib import Path
import numpy as np
from scipy.signal import butter, sosfilt, lfilter

CUES = ['Swing', 'HeavySwing', 'Contact', 'Guard', 'Impact', 'Breath', 'Fire', 'Heal', 'Exposed', 'Death', 'Victory', 'Roll', 'Blink', 'Footstep', 'Wing',
        'Roar', 'Break', 'PlayerPain', 'DragonGrowl', 'DragonPain', 'ArmorHit', 'DragonStep', 'DragonSwing', 'Bite', 'Debris', 'DragonBreathIn',
        'DragonBreathOut', 'DragonGrowlLow', 'DragonSnort']
KINDS = ['Other', 'Landing', 'Slam', 'ClawTail', 'BodyFall', 'HeadHit', 'HeavyHit', 'FireIgnition', 'LightHit', 'Hurt', 'WalkStep', 'KnightStep', 'Wing',
         'FireSustain', 'Presence']
EVENT_KIND = {'dragonLanding': 'Landing', 'dragonStomp': 'Slam', 'clawTailImpact': 'ClawTail', 'bodyFall': 'BodyFall', 'weaponHead': 'HeadHit',
              'weaponHeavy': 'HeavyHit', 'fireIgnition': 'FireIgnition', 'weaponLight': 'LightHit', 'hurt': 'Hurt', 'dragonFootfall': 'WalkStep',
              'knightStep': 'KnightStep'}
# Target order, loudest first, as median full-band peak relative to the landing (dB). Neighbours 1.2 dB apart: 13.2 dB top to bottom.
LADDER = ['Landing', 'Slam', 'ClawTail', 'BodyFall', 'HeadHit', 'HeavyHit', 'FireIgnition', 'LightHit', 'Hurt', 'WalkStep', 'KnightStep']
SR_IN, SR = 24000, 48000


def biquad_hp(f, rate):
    w = 2 * math.pi * f / rate; c = math.cos(w); s = math.sin(w); al = s / (2 * .7071); a0 = 1 + al
    return np.array([(1 + c) / 2 / a0, -(1 + c) / a0, (1 + c) / 2 / a0]), np.array([1, -2 * c / a0, (1 - al) / a0])


def load_pcm(path):
    return np.frombuffer(Path(path).read_bytes(), dtype='<i2').astype(np.float64)


def prep(cue, s):
    """The game's AddVariant: wing high-pass (float32 on int16 values, clamped), head trim."""
    if cue == 'Wing':
        b, a = biquad_hp(450., SR_IN)
        s = np.clip(lfilter(b, a, lfilter(b, a, s)), -32767, 32767).astype(np.int16).astype(np.float64)
    peak0 = max(1e-4, np.abs(s).max() / 32768)
    idx = np.nonzero(np.abs(s) / 32768 >= .04 * peak0)[0]
    first = int(idx[0]) if len(idx) else 0
    cut = min(max(first - int(.002 * SR_IN), 0), int(.025 * SR_IN))
    return s[cut:]


TARGET_DB = {'Swing': -10, 'HeavySwing': -8, 'Contact': -5, 'Guard': -6, 'ArmorHit': -5, 'Impact': -5, 'DragonStep': -6, 'DragonSwing': -7, 'Bite': -7,
             'Breath': -15, 'Fire': -11, 'Wing': -15, 'Roll': -16, 'Footstep': -9, 'Blink': -15, 'Break': -9, 'Debris': -12, 'Exposed': -5, 'Death': -8,
             'Heal': -15, 'Victory': -10, 'DragonBreathIn': -22, 'DragonBreathOut': -22, 'DragonGrowlLow': -14, 'DragonSnort': -18, 'Roar': -8,
             'DragonGrowl': -11, 'DragonPain': -11, 'PlayerPain': -8}


def variant_gain(cue, s):
    """AddVariant's per-variant gain (RMS to the cue's target on the recorded master, capped so the variant peaks at .9 at volume 1)."""
    x = s / 32768; peak = max(1e-4, np.abs(x).max()); g = x[np.abs(x) > .01]
    rms = math.sqrt((g ** 2).mean()) if len(g) else 1e-4; mdb = 20 * math.log10(max(rms, 1e-5)); t = TARGET_DB.get(cue, 0)
    gain = 10 ** ((t - mdb) / 20) / (.65 * .355) if t < 0 else 1 / (.65 * .355)
    return min(gain, .9 / (peak * .65 * .355))


def as_pass5(d, banks):
    """A pass 4 log played through the pass 5 level rule: volume x variant gain x jitter x makeup, no solo ceiling, no peak budget, the
    weapon layers at class volume 1 (pass 4 scaled them by .65/.75/.85). Jitter is recovered where the logged level is within +-2 dB of
    the uncapped level, else taken as 1."""
    W = {'LightHit': .65, 'HeavyHit': .75, 'HeadHit': .85}
    for it in d['items']:
        if it['cue'] not in banks or it['variant'] >= len(banks[it['cue']]): continue
        g = variant_gain(it['cue'], banks[it['cue']][it['variant']]); mk = 10 ** (-1.5 / 20)
        un = min(it['volume'], 1.5) * g * mk; r = it['level'] / un if un > 0 else 1
        jit = r if .79 <= r <= 1.26 else 1.0
        vol = it['volume'] / W[it['kind']] if it['kind'] in W and it['cue'] in ('Contact', 'Guard', 'ArmorHit', 'Impact', 'Exposed', 'DragonStep', 'Break') else it['volume']
        it['level'] = min(vol, 1.5) * g * mk * jit


def load_banks(content):
    content = Path(content); d = content / 'Audio/Recorded20261118'; banks = {}
    for cue in CUES:
        if cue in ('Roar', 'DragonGrowl', 'DragonPain', 'PlayerPain'):
            f = content / ('Audio/Fish20261102/PlayerPain.pcm' if cue == 'PlayerPain' else f'Audio/DragonLibrary20261103/{cue}.pcm')
            banks[cue] = [prep(cue, load_pcm(f))] if f.exists() else []
            continue
        rec, gen = [], []
        for f in d.glob(f'{cue}_*.pcm'):
            tail = f.stem.rsplit('_', 1)[1]
            if tail.startswith('g'): gen.append((int(tail[1:] or 0), f))
            else: rec.append((int(tail or 0), f))
        files = [f for _, f in sorted(rec)] + [f for _, f in sorted(gen)]
        banks[cue] = [prep(cue, load_pcm(f)) for f in files[:16]]
    return banks


def tilt(s, fc, k):
    a = 1 - math.exp(-2 * math.pi * fc / SR_IN)
    lp = lfilter([a], [1, -(1 - a)], s)
    return np.clip(lp + k * (s - lp), -32767, 32767).astype(np.int16).astype(np.float64)


NARROW = {'Landing', 'Slam', 'BodyFall', 'WalkStep'}
NARROW_BY = 1.0  # --narrow: model of mix pass 5's half-way-to-the-view-axis placement on a log recorded without it (pan x 0.5)


def render_item(it, banks, offset_db):
    pcm = banks[it['cue']][it['variant']]
    if it.get('tiltK', -1) >= 0: pcm = tilt(pcm, it['tiltFc'], it['tiltK'])
    pitch = it['pitch']
    frames = int(len(pcm) / SR_IN / max(.5, pitch) * SR)
    src = np.arange(frames) * pitch * SR_IN / SR
    i0 = src.astype(np.int64); keep = i0 + 1 < len(pcm); src, i0 = src[keep], i0[keep]
    f = src - i0
    x = (pcm[i0] * (1 - f) + pcm[i0 + 1] * f) / 32768
    amp = it['level'] * MASTER * EFFECTS * it['attenuation'] * 10 ** (offset_db / 20)
    pan = it['pan'] * (NARROW_BY if it.get('kind') in NARROW and it.get('place', 4) else 1.0)
    ang = (pan + 1) * math.pi * .25
    return x * amp * math.cos(ang), x * amp * math.sin(ang)


def limiter(mix, ceiling_db, look=240, release_ms=140.):
    c = 10 ** (ceiling_db / 20); p = np.abs(mix).max(1)
    g = np.where(p > c, c / np.maximum(p, 1e-12), 1.0)
    from scipy.ndimage import minimum_filter1d
    gm = minimum_filter1d(g, size=look + 1, origin=-(look // 2))  # min over [i, i+look]
    a = 1 - math.exp(-1 / (release_ms * .001 * SR)); r = 1.0; out = np.empty_like(gm)
    for i in range(len(gm)):  # down at once, up slowly
        v = gm[i]; r = v if v < r else r + (v - r) * a; out[i] = r
    cs = np.cumsum(np.concatenate([[0], out])); n = np.arange(len(out))
    lo = np.maximum(0, n - look); gain = (cs[n + 1] - cs[lo]) / (n + 1 - lo)
    return mix * gain[:, None]


EVENT_CUES = {'dragonLanding': None, 'dragonStomp': None, 'bodyFall': {'Exposed', 'Impact', 'Debris'}, 'clawTailImpact': None,
              'weaponHead': {'Contact', 'Guard', 'ArmorHit', 'Impact', 'Exposed', 'DragonStep', 'Break'},
              'weaponHeavy': {'Contact', 'Guard', 'ArmorHit', 'Impact', 'Exposed', 'DragonStep'}, 'weaponLight': {'Contact', 'Guard', 'ArmorHit', 'Impact'},
              'fireIgnition': {'Debris', 'Break', 'Impact', 'Breath', 'Fire'}, 'hurt': {'ArmorHit', 'Impact', 'PlayerPain'},
              'dragonFootfall': {'DragonStep', 'Impact'}, 'knightStep': {'Footstep'}}


def infer_kinds(d):
    """Taps before mix pass 5 carry no kind per item: the latest event within 0.13 s before the item whose layer set has the item's cue."""
    if all('kind' in it for it in d['items']): return
    ev = sorted(d['events'], key=lambda e: e['t'])
    for it in d['items']:
        k = 'Other'
        for e in reversed(ev):
            if e['t'] > it['t'] + 1e-4: continue
            if it['t'] - e['t'] > .13: break
            cs = EVENT_CUES.get(e['kind'], set())
            if e['kind'] in EVENT_KIND and (cs is None or it['cue'] in cs):
                if cs is None and it['cue'] not in {'DragonStep', 'Impact', 'Exposed', 'Break', 'Debris'}: continue
                k = EVENT_KIND[e['kind']]; break
        if k == 'Other':
            if it['cue'] in ('DragonBreathIn', 'DragonBreathOut', 'DragonGrowlLow', 'DragonSnort'): k = 'Presence'
            elif it['cue'] == 'Fire': k = 'FireSustain'
            elif it['cue'] == 'Wing': k = 'Wing'
            elif it['cue'] == 'Footstep': k = 'KnightStep'
        it['kind'] = k; it['kindGain'] = 1.0; it['trim'] = 1.0


def mix_from(d, banks, beds, gains_db, trim_db, music_db, bed_offset_db, offset_db, limit_db, per_item=False):
    n = int(d['seconds'] * SR) + SR
    fx = np.zeros((n, 2)); peaks = []
    tr_new = 10 ** (trim_db / 20) if trim_db is not None else None
    for it in d['items']:
        if it['cue'] not in banks or it['variant'] >= len(banks[it['cue']]): peaks.append(None); continue
        L, R = render_item(it, banks, offset_db)
        k = it.get('kind', 'Other'); scale = 1.0
        if gains_db is not None:  # kind gain plus an optional layer gain "Kind.Cue"; the logged kindGain is the total the game applied
            scale *= 10 ** ((gains_db.get(k, 0.0) + gains_db.get(k + '.' + it['cue'], 0.0)) / 20) / it.get('kindGain', 1.0)
        if tr_new is not None: scale *= tr_new / it.get('trim', 1.0)
        a = int(it['t'] * SR); b = min(n, a + len(L))
        fx[a:b, 0] += L[:b - a] * scale; fx[a:b, 1] += R[:b - a] * scale
        if per_item: peaks.append(20 * math.log10(max(np.abs(L).max(), np.abs(R).max(), 1e-9)))
    out = fx.copy()
    if beds is not None:
        m = min(len(beds), n)
        bs = 10 ** (bed_offset_db / 20) * (10 ** (music_db / 20) if music_db else 1.0)
        if tr_new is not None: bs *= tr_new / (10 ** (d.get('masterTrimDb', 0) / 20))
        out[:m] += beds[:m] * bs
    if limit_db is not None: out = limiter(out, limit_db)
    return out, fx, peaks


def rdwav(p):
    w = wave.open(str(p)); sr = w.getframerate()
    return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).reshape(-1, w.getnchannels()).astype(float) / 32768, sr


def wrwav(p, x):
    w = wave.open(str(p), 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((np.clip(x, -1, 1) * 32767).astype('<i2').tobytes()); w.close()


def loudness(x):
    t = Path(tempfile.mkdtemp()) / 'l.wav'; wrwav(t, x)
    r = subprocess.run(['ffmpeg', '-nostats', '-i', str(t), '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True)
    txt = r.stderr.split('Summary:')[-1]
    g = lambda pat: float(re.search(pat, txt).group(1)) if re.search(pat, txt) else None
    return {'lufs': g(r'I:\s+(-?[\d.]+) LUFS'), 'lra': g(r'LRA:\s+(-?[\d.]+) LU'), 'tp': g(r'Peak:\s+(-?[\d.]+) dBFS')}


BANDS = ((20, 200), (200, 2000), (2000, 8000))


def bands(seg):
    sp = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) ** 2; f = np.fft.rfftfreq(len(seg), 1 / SR)
    return np.array([10 * np.log10(sp[(f >= lo) & (f < hi)].sum() + 1e-12) for lo, hi in BANDS])


def measure(x, events, lag=0.0):
    """rank_kinds.py (median full-band and 2-8 kHz peak in 0.25 s, mono mean) and analyze_mix.py (band rise against 15 x 33 ms before)."""
    mono = x.mean(1); hi = sosfilt(butter(4, [2000, 8000], btype='band', fs=SR, output='sos'), mono)
    lo = sosfilt(butter(4, 200, btype='low', fs=SR, output='sos'), mono)
    N = int(.033 * SR); rows = {}
    for e in events:
        i = int((e['t'] + (lag(e['t']) if callable(lag) else lag)) * SR)
        if i < 16 * N or i + int(.3 * SR) > len(mono): continue
        n = int(.25 * SR)
        full = 20 * np.log10(np.abs(mono[i:i + n]).max() + 1e-9); high = 20 * np.log10(np.abs(hi[i:i + n]).max() + 1e-9)
        low = 20 * np.log10(np.abs(lo[i:i + n]).max() + 1e-9)
        rise = bands(mono[i:i + N]) - np.median([bands(mono[i - k * N:i - (k - 1) * N]) for k in range(1, 16)], axis=0)
        seg = mono[i:i + int(.15 * SR)]; s = np.log10(np.abs(np.fft.rfft(seg * np.hanning(len(seg)), 2048)) ** 2 + 1e-12)
        rows.setdefault(e['kind'], []).append(dict(t=e['t'], full=full, high=high, low=low, rise=rise, spec=s - s.mean()))
    return rows


def summary(x, d, lag=0.0, quiet=False):
    rows = measure(x, d['events'], lag); res = {'kinds': {}}
    res.update(loudness(x)); res['samplePeak'] = float(20 * np.log10(np.abs(x).max() + 1e-9))
    res['fullScale'] = int((np.abs(x) >= .999).sum())
    res['rMinusL'] = float(10 * np.log10((x[:, 1] ** 2).mean() / max((x[:, 0] ** 2).mean(), 1e-12)))
    n4 = int(.4 * SR); k4 = len(x) // n4; blk = 10 * np.log10((x[:k4 * n4].mean(1).reshape(k4, n4) ** 2).mean(1) + 1e-12); blk = blk[blk > -90]  # trailing silence out
    res['quietP10'] = float(np.percentile(blk, 10)); res['under45'] = float((blk < -45).mean())
    for k, v in rows.items():
        sp = [r['spec'] for r in v]; ts = [r['t'] for r in v]
        cors = [float(np.corrcoef(a, b)[0, 1]) for a, b, t1, t2 in zip(sp, sp[1:], ts, ts[1:]) if t2 - t1 < 3.0]
        res['kinds'][k] = dict(n=len(v), full=float(np.median([r['full'] for r in v])), high=float(np.median([r['high'] for r in v])),
                               low=float(np.median([r['low'] for r in v])), rise=np.median([r['rise'] for r in v], axis=0).round(1).tolist(),
                               corr=(float(np.median(cors)), sum(c >= .8 for c in cors), len(cors)) if cors else None)
    # fire sustained while the flame shows: median 200 Hz-8 kHz level over the flame against the 0.5 s before the ignition
    L = lag if callable(lag) else (lambda t: lag)
    ig = [e['t'] + L(e['t']) for e in d['events'] if e['kind'] == 'fireIgnition']; en = [e['t'] + L(e['t']) for e in d['events'] if e['kind'] == 'fireEnd']
    mono = x.mean(1); bp = sosfilt(butter(4, [200, 8000], btype='band', fs=SR, output='sos'), mono); sus = []
    for t0 in ig:
        t1 = min([t for t in en if t > t0 + .2] or [t0 + 1.5])
        a0, a1 = int((t0 + .25) * SR), int(t1 * SR); p0 = int((t0 - .5) * SR)
        if p0 < 0 or a1 <= a0: continue
        w = int(.05 * SR); lv = [10 * np.log10((bp[i:i + w] ** 2).mean() + 1e-12) for i in range(a0, a1 - w, w)]
        sus.append(float(np.median(lv) - 10 * np.log10((bp[p0:int(t0 * SR)] ** 2).mean() + 1e-12)) if lv else None)
    res['fireSustainDb'] = sus
    if not quiet: report(res)
    return res


def check(res, pass2_light=13.0):
    """Every target of the brief, PASS/FAIL, on one measured result."""
    K = res['kinds']; out = []; m = {k: K[ev]['full'] for ev, k in EVENT_KIND.items() if ev in K}
    def chk(name, ok, val): out.append((name, bool(ok), val))
    chk('integrated -24 +-1.5 LUFS', -25.5 <= res['lufs'] <= -22.5, res['lufs']); chk('true peak <= -1.5 dBTP', res['tp'] <= -1.5, res['tp'])
    chk('full-scale samples 0', res['fullScale'] == 0, res['fullScale']); chk('R-L within 1 dB', abs(res['rMinusL']) <= 1, round(res['rMinusL'], 2))
    lad = [k for k in LADDER if k in m]
    bad = [(a, b, round(m[a] - m[b], 1)) for a, b in zip(lad, lad[1:]) if m[a] < m[b] - 1.0]
    chk('order (neighbours tie within 1 dB)', not bad, bad or [(k, round(m[k], 1)) for k in lad])
    chk('span >= 12 dB', m[lad[0]] - m[lad[-1]] >= 12 if lad else False, round(max(m.values()) - min(m.values()), 1) if m else None)
    if 'Slam' in m and 'WalkStep' in m: chk('slam >= walking step + 8', m['Slam'] - m['WalkStep'] >= 8, round(m['Slam'] - m['WalkStep'], 1))
    if 'Landing' in m: chk('landing the biggest', all(m['Landing'] >= v for k, v in m.items() if k != 'Landing'), round(m['Landing'] - max(v for k, v in m.items() if k != 'Landing'), 1))
    if 'weaponLight' in K:
        rel = K['weaponLight']['high'] - res['lufs']; chk(f'light 2-8k over programme within 2 dB of pass 2 ({pass2_light:+.1f})', abs(rel - pass2_light) <= 2, round(rel, 1))
        chk('light high-band rise >= 10', K['weaponLight']['rise'][2] >= 10, K['weaponLight']['rise'])
    for ev in ('weaponHead', 'weaponHeavy'):
        if ev in K: chk(f'{ev} rise >= 10 in all bands', min(K[ev]['rise']) >= 10, K[ev]['rise'])
    if 'fireIgnition' in K:
        chk('fire ignition rise >= 8 mid and high', min(K['fireIgnition']['rise'][1:]) >= 8, K['fireIgnition']['rise'])
        chk('fire sustained (flame level over pre-ignition >= +3 dB)', all(v is not None and v >= 3 for v in res['fireSustainDb']) if res['fireSustainDb'] else False, res['fireSustainDb'])
    if 'wingBeat' in K and 'dragonFootfall' in K:
        chk('wing low band <= walking step low - 6', K['wingBeat']['low'] <= K['dragonFootfall']['low'] - 6, round(K['wingBeat']['low'] - K['dragonFootfall']['low'], 1))
    if 'dragonStomp' in K and K['dragonStomp']['corr']:
        c = K['dragonStomp']['corr']; chk('stomp neighbours spectral corr < 0.8 for most pairs', c[1] < c[2] / 2, f'{c[2] - c[1]}/{c[2]} under 0.8, median {c[0]:.2f}')
    chk('loudness range >= 7 LU', res['lra'] >= 7, res['lra'])
    if 'quietP10' in res:  # mix pass 6 (critic S6: 11 % of the film under -45 dBFS): the bed holds the quiet moments at -38..-34 dBFS
        chk('quiet moments (400 ms RMS, 10th percentile) -38..-34 dBFS, under 2 % below -45', -38 <= res['quietP10'] <= -34 and res['under45'] < .02, f"{res['quietP10']:.1f} dBFS, {100 * res['under45']:.0f}% under -45")
    for n, ok, v in out: print(f"  {'PASS' if ok else 'FAIL'}  {n}: {v}")
    return out


def report(res):
    print(f"LUFS {res['lufs']}  LRA {res['lra']}  true peak {res['tp']} dBTP  sample peak {res['samplePeak']:.1f}  full-scale {res['fullScale']}  R-L {res['rMinusL']:+.2f} dB")
    order = sorted(res['kinds'].items(), key=lambda kv: -kv[1]['full'])
    for k, v in order:
        c = v['corr']; cs = f"corr med {c[0]:.2f} {c[1]}/{c[2]}>=.8" if c else ''
        print(f"  {k:15} n={v['n']:3} full {v['full']:6.1f}  2-8k {v['high']:6.1f}  <200 {v['low']:6.1f}  rise {v['rise']}  {cs}")


def find_lag(real, tap):
    """Recording time minus tap time (s): onset-envelope correlation at 50 ms, as rank_kinds.py, refined to 5 ms."""
    def env(x, h):
        n = int(SR * h); k = len(x) // n; return np.maximum(np.diff(10 * np.log10((x.mean(1)[:k * n].reshape(k, n) ** 2).mean(1) + 1e-10)), 0)
    def best(h, lo, hi):
        dr, dt = env(real, h), env(tap, h); b = (-1, 0)
        for l in range(lo, hi):
            x, y = (dr[l:], dt) if l >= 0 else (dr, dt[-l:]); n = min(len(x), len(y))
            if n < 400: continue
            c = np.corrcoef(x[:n], y[:n])[0, 1]
            if c > b[0]: b = (c, l)
        return b
    c, l = best(.05, -600, 600); c2, l2 = best(.005, l * 10 - 12, l * 10 + 12)
    return l2 * .005, c2


def lag_map(real, tap, block=10.0, search=3.0):
    """Recording time minus tap time as a function of tap time. The master recording loses time when the audio render falls behind
    (under capture load a 106 s fight recorded about 1.7 s short), so one constant lag misplaces late events. Per 10 s block (5 s hop):
    the onset-envelope correlation peak within +-3 s of the global lag at 10 ms; blocks whose peak is weak keep their neighbour's lag."""
    g, _ = find_lag(real, tap); h = .01; n = int(SR * h)
    def env(x):
        k = len(x) // n; return np.maximum(np.diff(10 * np.log10((x.mean(1)[:k * n].reshape(k, n) ** 2).mean(1) + 1e-10)), 0)
    er, et = env(real), env(tap); B = int(block / h); S = int(search / h); ts, ls = [], []
    for c0 in range(0, len(et) - B, B // 2):
        y = et[c0:c0 + B]
        if y.std() == 0: continue
        best = (-1, 0)
        for l in range(int(g / h) - S, int(g / h) + S + 1):
            a0 = c0 + l
            if a0 < 0 or a0 + B > len(er): continue
            x = er[a0:a0 + B]
            if x.std() == 0: continue
            cc = np.corrcoef(x, y)[0, 1]
            if cc > best[0]: best = (cc, l)
        ts.append((c0 + B / 2) * h); ls.append(best[1] * h if best[0] > .3 else np.nan)
    ts, ls = np.array(ts), np.array(ls)
    ok = ~np.isnan(ls)
    if ok.sum() == 0: return (lambda t: g), [(float(g), 0.0)]
    ls = np.interp(ts, ts[ok], ls[ok])
    med = np.array([np.median(ls[max(0, i - 1):i + 2]) for i in range(len(ls))])
    return (lambda t: float(np.interp(t, ts, med))), list(zip(ts.round(1).tolist(), med.round(3).tolist()))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('cues'); ap.add_argument('--content', default=str(Path(__file__).resolve().parents[2] / 'Unreal/Veyr/Content'))
    ap.add_argument('--gains'); ap.add_argument('--trim', type=float); ap.add_argument('--music', type=float, default=0.0)
    ap.add_argument('--bed-offset', type=float, default=-6.0, help='real engine bed level minus the tap bed level (dB): Mac PlatformHeadroomDB -6 on the stereo beds')
    ap.add_argument('--offset', type=float, help="effects engine offset (default: the tap's own tapOffsetDb)")
    ap.add_argument('--limiter', type=float); ap.add_argument('--no-limiter', action='store_true')
    ap.add_argument('--out'); ap.add_argument('--verify', action='store_true'); ap.add_argument('--solve', action='store_true')
    ap.add_argument('--top', type=float, default=-3.0, help='target median peak of the landing (dBFS)'); ap.add_argument('--step', type=float, default=1.2)
    ap.add_argument('--narrow', type=float, default=1.0, help='scale the pan of the dragon ground thuds (0.5 models the pass 5 placement on an older log)')
    ap.add_argument('--as-pass5', action='store_true', help='play a pass 4 log through the pass 5 level rule (no ceiling, no budget)')
    ap.add_argument('--measure', help='a real recording (wav, 48 kHz stereo) of this log: measure it against every target instead of rendering')
    ap.add_argument('--lag', type=float, help='with --measure: recording time minus tap time (s); default: a local lag map from the tap mix')
    ap.add_argument('--calibrate', help='the real master recording of this log: shift the effects and bed offsets by the median per-kind peak difference (real minus offline) first')
    ap.add_argument('--clamp', type=float, default=6.0, help='--solve moves no kind gain more than this from where it started (dB)')
    ap.add_argument('--json'); ap.add_argument('--ladder', help='explicit targets, e.g. Landing:-2.5/Slam:-3.3/... (dBFS median peak)')
    a = ap.parse_args()
    d = json.loads(Path(a.cues).read_text()); global MASTER, EFFECTS
    MASTER, EFFECTS = d.get('masterVolume', .65), d.get('effectsVolume', 1.0)
    global NARROW_BY; NARROW_BY = a.narrow
    banks = load_banks(a.content)
    infer_kinds(d)
    if a.as_pass5: as_pass5(d, banks)
    stem = Path(a.cues).name.replace('-cues.json', '')
    bp = Path(a.cues).with_name(stem + '-beds.wav'); beds = rdwav(bp)[0] if bp.exists() else None
    offset = a.offset if a.offset is not None else d.get('tapOffsetDb', -9)
    limit = None if a.no_limiter else (a.limiter if a.limiter is not None else d.get('limiterDb', -1.5))
    gains = {k: 20 * math.log10(1.0) for k in KINDS} if 'kindGainDb' not in d else dict(d['kindGainDb'])
    if a.gains:
        for part in a.gains.split('/'):
            k, v = part.split(':'); gains[k] = float(v)
    if a.measure:
        x, sr = rdwav(Path(a.measure)); assert sr == SR, 'resample the recording to 48 kHz first'
        if a.lag is not None: lag = a.lag; lm = None
        else:
            lag, lm = lag_map(x, rdwav(Path(a.cues).with_name(stem + '-mix.wav'))[0])
            print('local lag (tap s, recording minus tap s): ' + ' '.join(f'{t:.0f}:{l:+.2f}' for t, l in lm[::2]))
        res = summary(x, d, lag=lag); check(res)
        if a.json: Path(a.json).write_text(json.dumps({'measured': a.measure, 'lag': a.lag, 'result': res}, indent=1, default=str))
        return
    if a.verify:
        out, fx, peaks = mix_from(d, banks, beds, None, None, 0, 0.0, offset, limit, per_item=True)
        diffs = [p - it['peakDb'] for p, it in zip(peaks, d['items']) if p is not None and it['peakDb'] > -90]
        print(f'items: {len(diffs)} rendered; item peak minus tap item peak: median {np.median(diffs):+.3f} dB, max |diff| {np.abs(diffs).max():.3f} dB, '
              f'{sum(abs(x) > .5 for x in diffs)} over 0.5 dB')
        tap = rdwav(Path(a.cues).with_name(stem + '-mix.wav'))[0]
        m = min(len(tap), len(out))
        print('--- tap wav'); rt = summary(tap[:m], d)
        print('--- offline render (logged gains)'); ro = summary(out[:m], d)
        print(f"loudness offline minus tap {ro['lufs'] - rt['lufs']:+.2f} LU; per-kind peak offline minus tap: " +
              ', '.join(f"{k} {ro['kinds'][k]['full'] - rt['kinds'][k]['full']:+.2f}" for k in rt['kinds'] if k in ro['kinds']))
        if beds is None: print('(no beds wav in this tap: the offline render has effects only)')
        return
    trim = a.trim if a.trim is not None else d.get('masterTrimDb', 0.0)
    bed_offset = a.bed_offset
    if a.calibrate:
        real = rdwav(Path(a.calibrate))[0]; tapw = rdwav(Path(a.cues).with_name(stem + '-mix.wav'))[0]
        lag, lm = lag_map(real, tapw); c = float('nan')
        out, fx, _ = mix_from(d, banks, beds, None, None, 0, bed_offset, offset, limit)
        rr = summary(real, d, lag=lag, quiet=True); ro = summary(out, d, quiet=True)
        diffs = {k: rr['kinds'][k]['full'] - ro['kinds'][k]['full'] for k in ro['kinds'] if k in rr['kinds'] and ro['kinds'][k]['n'] >= 2}
        shift = float(np.median(list(diffs.values())))
        print(f'calibration: local lag {lm[0][1]:+.3f} .. {lm[-1][1]:+.3f} s; real minus offline (logged gains): LUFS {rr["lufs"] - ro["lufs"]:+.2f}, per kind ' +
              ', '.join(f'{k} {v:+.1f}' for k, v in diffs.items()) + f'; offsets shifted {shift:+.2f} dB')
        offset += shift; bed_offset += shift
    if a.solve:
        targets = {k: a.top - i * a.step for i, k in enumerate(LADDER)}
        if a.ladder: targets = {k: float(v) for k, v in (p.split(':') for p in a.ladder.split('/'))}
        base = {k: gains.get(k, 0.0) for k in targets}
        for k in targets: gains.setdefault(k, 0.0)
        for it_ in range(8):
            out, fx, _ = mix_from(d, banks, beds, gains, trim, a.music, bed_offset, offset, None)
            res = summary(out, d, quiet=True)
            worst = 0
            for ev, kk in EVENT_KIND.items():
                if ev in res['kinds'] and kk in targets:
                    err = targets[kk] - res['kinds'][ev]['full']; worst = max(worst, abs(err))
                    gains[kk] = float(np.clip(gains[kk] + .85 * err, base[kk] - a.clamp, base[kk] + a.clamp))
            print(f'iteration {it_}: worst error {worst:.2f} dB')
            if worst < .3: break
    out, fx, _ = mix_from(d, banks, beds, gains, trim, a.music, bed_offset, offset, limit)
    res = summary(out, d); check(res)
    print('gains: ' + '/'.join(f'{k}:{v:.1f}' for k, v in gains.items() if abs(v) > .01) + f'  trim {trim:.1f}  music {a.music:.1f}')
    if a.out: wrwav(a.out, out)
    if a.json: Path(a.json).write_text(json.dumps({'gains': gains, 'trim': trim, 'music': a.music, 'result': res}, indent=1))


if __name__ == '__main__':
    main()
