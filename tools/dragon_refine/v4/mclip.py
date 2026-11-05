"""Quick iteration probe: raster one dumped Action and print the round-2 metrics that apply.
python3 mclip.py <dump.npz> <G|T|K> [beat=a:b] [loop=1] [sheet=out.png] [every=4] [series=1]"""
import sys, json, numpy as np, cv2, os
sys.path.insert(0, os.path.dirname(__file__))
import raster as R, metrics_v4 as MV, critic as C
dump, grp = sys.argv[1], sys.argv[2]
opt = dict(a.split("=", 1) for a in sys.argv[3:])
d = R.load(dump)
mf, wf, gf = R.render(d, grp, "front"); mf = np.stack([C.clean(x) for x in mf])
if opt.get("front_only"): ml, wl, gl = mf, wf, gf
else:
    ml, wl, gl = R.render(d, grp, "left"); ml = np.stack([C.clean(x) for x in ml])
BH = C.BH_PX[grp]
def rnd(o):
    if isinstance(o, dict): return {k: rnd(v) for k, v in o.items()}
    if isinstance(o, (float, np.floating)): return round(float(o), 3)
    return o
if "beat" in opt:
    a, b = map(int, opt["beat"].split(":")); print("BEAT", json.dumps(rnd(MV.beat(mf, wf, BH, (a, b), P=int(opt.get("P", 26))))))
if opt.get("loop"):
    print("LOOP", json.dumps(rnd(MV.loop(gf, mf, gl, ml, mf, P=int(opt.get("P", 26))))))
sf, sl = MV.series(mf, wf), MV.series(ml, wl)
if opt.get("series"):
    e = int(opt.get("every", 4))
    for k in ("top", "body_cy", "fspan", "lowest"): print(" front", k, np.round(sf[k][::e]).astype(int).tolist())
    for k in ("lowest", "cy"): print(" left", k, np.round(sl[k][::e]).astype(int).tolist())
    df, _ = C.steps(gf, mf); dl, _ = C.steps(gl, ml)
    print(" steps front", np.round(df[::e], 2).tolist()); print(" steps left", np.round(dl[::e], 2).tolist()); print(" saw", round(C.saw(df), 3), round(C.saw(dl), 3))
if "sheet" in opt:
    e = int(opt.get("every", 4)); idx = list(range(0, len(gf), e))[:24]
    rows = [np.concatenate([np.concatenate([g[i] for i in idx[r:r + 6]] + [np.zeros_like(g[0])] * (6 - len(idx[r:r + 6])), 1) for g in (gf, gl)], 0) for r in range(0, len(idx), 6)]
    img = np.concatenate(rows, 0).astype(np.uint8)
    cv2.imwrite(opt["sheet"], cv2.resize(img, None, fx=0.33, fy=0.33, interpolation=cv2.INTER_AREA))
