"""Compare the CPU raster of the v3 Actions with the critic's segmented renders of the same clips (masks cached by the critic).
Usage: python3 calibrate.py <critic_dir> <dump_dir> <out.json>"""
import sys, json, numpy as np
sys.path.insert(0, __import__("os").path.dirname(__file__))
import raster as R, critic as C
CD, DD, OUT = sys.argv[1:4]
PAIRS = [("after_idle", "idle_v2", "G"), ("after_roar_r1", "roar_sd_v3", "G"), ("after_bite_r1", "bite_v3", "G"), ("after_collapse_r1", "collapse_v3", "G"),
         ("after_rise_r1", "rise_v3", "G"), ("after_claw_swipe_r1", "claw_swipe_v3", "G"), ("after_land_r1", "land2_v3", "T"), ("air_air_hover_AH1", "air_hover_v3", "T"),
         ("air_air_land_AL1", "air_land_v3", "T"), ("air_air_fire_down_FD1", "air_fire_down_v3", "T"), ("air_takeoff3_TK1", "takeoff3_v3", "K")]
def critic_masks(name, view):
    z = np.load(f"{CD}/masks/{name}_{view}.npz"); sh = tuple(z["shape"])
    m = np.unpackbits(z["m"], axis=-1)[..., :sh[2]].astype(bool); w = np.unpackbits(z["w"], axis=-1)[..., :sh[2]].astype(bool)
    m = np.stack([C.clean(x) for x in m]); return m, w & m, z["gray"].astype(np.float32)
res = {}
for cname, act, grp in PAIRS:
    d = R.load(f"{DD}/d_{act}.npz"); r = {}
    for view in ("front", "left"):
        cm, cw, cg = critic_masks(cname, view)
        mm, mw, mg = R.render(d, grp, view)
        n = min(len(cm), len(mm))
        ious = [C.iou(cm[i], mm[i]) for i in range(n)]
        cs, box = C.steps(cg[:n], cm[:n]); ms, _ = C.steps(mg[:n], mm[:n])
        lo_c = np.array([C.lowest(x) for x in cm[:n]]); lo_m = np.array([C.lowest(x) for x in mm[:n]])
        cy_c = np.array([C.centroid(x)[1] for x in cm[:n]]); cy_m = np.array([C.centroid(x)[1] for x in mm[:n]])
        sp_c = np.array([C.fspan(x)[0] for x in cm[:n]]); sp_m = np.array([C.fspan(x)[0] for x in mm[:n]])
        r[view] = {"frames": [int(len(cm)), int(len(mm))], "iou_mean": round(float(np.mean(ious)), 3), "iou_min": round(float(np.min(ious)), 3),
                   "step_median_critic": round(float(np.median(cs)), 3), "step_median_raster": round(float(np.median(ms)), 3),
                   "step_ratio_critic_over_raster": round(float(np.median(cs) / np.median(ms)), 3), "step_corr": round(float(np.corrcoef(cs, ms)[0, 1]), 3),
                   "saw_critic": round(C.saw(cs), 3), "saw_raster": round(C.saw(ms), 3),
                   "lowest_row_mean_abs_diff_px": round(float(np.abs(lo_c - lo_m).mean()), 2), "centroid_y_mean_abs_diff_px": round(float(np.abs(cy_c - cy_m).mean()), 2),
                   "fspan_mean_abs_diff_px": round(float(np.abs(sp_c - sp_m).mean()), 2)}
    res[cname] = r; print(cname, json.dumps(r), flush=True)
json.dump(res, open(OUT, "w"), indent=1)
