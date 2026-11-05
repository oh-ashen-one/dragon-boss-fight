"""Round-4 targets (docs/dragon-critique-round4-20261030.md) with the round-4 critic's definitions, on masks / gray frames
(CPU raster or segmented renders alike). Pixel numbers are in the 960x540 review frame."""
import numpy as np
import critic as C

def area_change(m, a, b):
    """per-frame relative silhouette-area change |A[i+1]-A[i]|/A[i] for steps a..b-1; returns (max, step)"""
    A = m.sum((1, 2)).astype(float); r = np.abs(np.diff(A)) / np.maximum(A[:-1], 1)
    k = a + int(np.argmax(r[a:b])); return float(r[k]), k
def halves_f0(m):
    """round-4 critic roar halves: about the FRAME-0 mask centre column; ratios to frame 0; span = full width ratio"""
    ys, xs = np.where(m[0]); cx0 = xs.mean(); l0, r0 = xs.min(), xs.max()
    L, R, S = [], [], []
    for x in m:
        cols = np.where(x.any(0))[0]; L.append((cx0 - cols.min()) / (cx0 - l0)); R.append((cols.max() - cx0) / (r0 - cx0)); S.append((cols.max() - cols.min()) / (r0 - l0))
    return np.array(L), np.array(R), np.array(S)
def dominant_period(d, pmax=20.0):
    """period (frames) of the strongest component of a per-frame-change series within the tremor band (period 2..pmax;
    slower breath / envelope drift excluded, as the critic's 3.7 -> 9.6 frame reading)"""
    x = np.asarray(d, float) - np.mean(d); F = np.abs(np.fft.rfft(x * np.hanning(len(x)))); fr = np.fft.rfftfreq(len(x))
    band = np.where(fr >= 1.0 / pmax)[0]; k = band[int(np.argmax(F[band]))]; return float(1.0 / fr[k])
def zone_area(m, zone=None):
    """round-4 critic bite near-wing proxy: mask area in the upper-left quadrant about the frame-0 mask centroid, / frame 0"""
    if zone is None:
        ys, xs = np.where(m[0]); zone = (int(xs.mean()), int(ys.mean()))
    a = np.array([x[:zone[1], :zone[0]].sum() for x in m], float); return a / a[0], zone
