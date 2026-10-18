#!/usr/bin/env python3
"""Repair only root-reviewed whole cloth components 104,541,1935.

Front/rear panels use a smooth hips-dominant thigh blend. The small left knee
hem follows a smooth left thigh/knee blend. No arm/hand influence is permitted.
Reference geometry, all other weights, animations and source files stay intact.
Writes private derivatives and CPU verification receipts; never launches UE.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "Local/CustomuseAssets"
SPEC = importlib.util.spec_from_file_location("veyr_cloth_cpu", ROOT / "tools/unreal/normalize_customuse_glb.py")
CPU = importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(CPU)
COMPONENTS = (104, 541, 1935)


def smooth(value):
    value = np.clip(value, 0, 1)
    return value*value*(3-2*value)


def process(source, output, approval):
    original_bytes = source.read_bytes();g = CPU.GLB(original_bytes);new = CPU.GLB(g.bytes())
    node = g.json["nodes"][g.mesh_node()];parts = g.json["meshes"][node["mesh"]]["primitives"]
    if len(parts) != 1:raise ValueError("Expected the original single primitive, not a highlight")
    primitive = parts[0];attrs = primitive["attributes"];triangles = g.accessor(primitive["indices"]).reshape(-1, 3)
    masks = [json.loads((ASSETS/"cloth-skin-review-v1"/f"component-{cid}-mask.json").read_text()) for cid in COMPONENTS]
    reference = CPU.GLB(ASSETS/"knight-b-idle-01-normalized-v1-rigid-sword-v1-in-place-v1.glb")
    ref_node = reference.json["nodes"][reference.mesh_node()];ref_primitive = reference.json["meshes"][ref_node["mesh"]]["primitives"][0]
    if not np.array_equal(triangles, reference.accessor(ref_primitive["indices"]).reshape(-1, 3)):
        raise ValueError("Topology differs from the visually approved masks")
    if not np.array_equal(g.accessor(attrs["POSITION"]), reference.accessor(ref_primitive["attributes"]["POSITION"])):
        raise ValueError("Reference mesh positions differ")
    skin = g.json["skins"][node["skin"]];names = [g.json["nodes"][i]["name"] for i in skin["joints"]]
    slots = {name:names.index(name) for name in ("Hips", "LeftUpLeg", "RightUpLeg", "LeftLeg")}
    rest = g.skinned_positions();world = g.world_matrices();height = float(np.ptp(rest[:, 1]))
    hip_l = world[skin["joints"][slots["LeftUpLeg"]], :3, 3]
    hip_r = world[skin["joints"][slots["RightUpLeg"]], :3, 3]
    knee = world[skin["joints"][slots["LeftLeg"]], :3, 3]
    old_j, old_w = g.accessor(attrs["JOINTS_0"]), g.accessor(attrs["WEIGHTS_0"])
    joints, weights = new.accessor(attrs["JOINTS_0"]), new.accessor(attrs["WEIGHTS_0"])
    selected = np.zeros(len(rest), bool);components = []
    for mask in masks:
        if mask["componentId"] not in COMPONENTS:raise ValueError("Unapproved component")
        ids = np.array(mask["vertexIndices"]);faces = np.array(mask["triangleIndices"])
        if not np.array_equal(ids, np.unique(triangles[faces])):raise ValueError("Mask vertex/triangle mismatch")
        other = np.ones(len(triangles), bool);other[faces] = False
        if np.intersect1d(ids, np.unique(triangles[other])).size:raise ValueError("Selected surface shares excluded vertices")
        selected[ids] = True;positions = rest[ids]
        if mask["componentId"] in (104, 541):
            fall = smooth((positions[:, 1].max()-positions[:, 1])/(np.ptp(positions[:, 1])*.65))
            thigh_total = .30*fall
            midpoint = (hip_l[0]+hip_r[0])/2
            left = .5+.5*np.tanh((positions[:, 0]-midpoint)/(abs(hip_l[0]-hip_r[0])*.35))
            new_weights = np.column_stack((1-thigh_total, thigh_total*left, thigh_total*(1-left), np.zeros(len(ids))))
            new_joints = [slots["Hips"], slots["LeftUpLeg"], slots["RightUpLeg"], slots["Hips"]]
            method = "Hips70-100percent; smooth height-dependent thighs0-30percent and smooth lateral split"
        else:
            shin = smooth((knee[1]+height*.04-positions[:, 1])/(height*.08))
            new_weights = np.column_stack((np.full(len(ids), .10), .90*(1-shin), .90*shin, np.zeros(len(ids))))
            new_joints = [slots["Hips"], slots["LeftUpLeg"], slots["LeftLeg"], slots["Hips"]]
            method = "Hips10percent; smooth left thigh/knee90percent over an8percent-height transition"
        joints[ids] = new_joints;weights[ids] = new_weights
        components.append({"componentId":mask["componentId"], "vertices":len(ids), "triangles":len(faces), "method":method,
                           "allowedJointNames":[names[i] for i in new_joints[:3]], "faces":faces})
    if not np.array_equal(old_j[~selected], joints[~selected]) or not np.array_equal(old_w[~selected], weights[~selected]):
        raise ValueError("Weights changed outside approved surfaces")
    if not np.allclose(weights.sum(1), 1, atol=1.e-6) or np.any(weights<0):raise ValueError("Invalid weights")
    changed={attrs["JOINTS_0"],attrs["WEIGHTS_0"]}
    if g.json!=new.json:raise ValueError("JSON/animation/geometry declarations changed")
    for i in range(len(g.json["accessors"])):
        if i not in changed and not np.array_equal(g.accessor(i),new.accessor(i)):raise ValueError("Non-weight accessor changed")
    rest_error=float(np.linalg.norm(rest-new.skinned_positions(),axis=1).max())
    if rest_error>2.e-6:raise ValueError("Reference surface changed")
    clip=g.json["animations"][0];duration=max(float(g.accessor(s["input"]).max()) for s in clip["samplers"])
    times=sorted(set(np.linspace(0,duration,17).tolist()+[1/30,min(2.5,duration)]));checks=[]
    for component in components:
        faces=triangles[component.pop("faces")];edges=np.unique(np.sort(np.concatenate([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]),axis=1),axis=0)
        lengths=np.linalg.norm(rest[edges[:,0]]-rest[edges[:,1]],axis=1);component["edges"]=edges;component["lengths"]=lengths
    for t in times:
        before=g.skinned_positions(0,t);after=new.skinned_positions(0,t)
        delta=float(np.linalg.norm(before[~selected]-after[~selected],axis=1).max())
        if delta!=0:raise ValueError("World skin changed outside approved cloth")
        row={"seconds":t,"outsideMaskWorldDelta":delta,"components":[]}
        for c in components:
            edges,lengths=c["edges"],c["lengths"];old_len=np.linalg.norm(before[edges[:,0]]-before[edges[:,1]],axis=1);new_len=np.linalg.norm(after[edges[:,0]]-after[edges[:,1]],axis=1);valid=lengths>height*(.1/244)
            row["components"].append({"componentId":c["componentId"],"maxEdgeStretchBefore":float((old_len[valid]/lengths[valid]).max()),"maxEdgeStretchAfter":float((new_len[valid]/lengths[valid]).max()),"strongOutlierEdgesBefore":int(np.sum(valid&(old_len>3*lengths)&(old_len>height*5/244))),"strongOutlierEdgesAfter":int(np.sum(valid&(new_len>3*lengths)&(new_len>height*5/244)))})
        checks.append(row)
    for c in components:c.pop("edges");c.pop("lengths")
    payload=new.bytes()
    report={"status":"APPROVED_MASK_SKIN_REPAIR_CPU_VERIFIED_NATIVE_QA_PENDING","approvalReference":approval,
            "source":source.name,"sourceSHA256":hashlib.sha256(original_bytes).hexdigest(),"derivative":output.name,
            "derivativeSHA256":hashlib.sha256(payload).hexdigest(),"components":components,"restShapeMaxDelta":rest_error,
            "outsideMaskWeightsAndWorldSkinUnchanged":True,"geometryAnimationAndOtherAccessorsUnchanged":True,
            "armHandInfluenceInsideMask":0,"selectedVertices":int(selected.sum()),"checks":checks,"nativeAccepted":False}
    if source.read_bytes()!=original_bytes:raise ValueError("Source changed during repair")
    with os.fdopen(os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as f:f.write(payload)
    with os.fdopen(os.open(output.with_suffix('.cloth.json'),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps({"file":output.name,"maxStretchBefore":max(c["maxEdgeStretchBefore"] for r in checks for c in r["components"]),"maxStretchAfter":max(c["maxEdgeStretchAfter"] for r in checks for c in r["components"]),"remainingStrongOutliers":max(sum(c["strongOutlierEdgesAfter"] for c in r["components"]) for r in checks)}),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,nargs='+',required=True);p.add_argument('--approval-ref',required=True);p.add_argument('--version',default='v1');a=p.parse_args()
    if not a.version.isalnum():p.error('Use an alphanumeric version')
    for source in a.source:
        source=source.resolve();output=ASSETS/(source.stem+'-cloth-'+a.version+'.glb')
        if not source.is_relative_to(ASSETS.resolve()) or output.exists() or output.with_suffix('.cloth.json').exists():raise ValueError('Use private sources and fresh outputs')
        process(source,output,a.approval_ref)


if __name__=='__main__':main()
