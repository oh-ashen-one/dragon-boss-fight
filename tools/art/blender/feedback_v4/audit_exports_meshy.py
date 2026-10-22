"""COPY (meshy/tripo A/B) of audit_exports.py: generic in-place LOOP case for retargeted clips (--glb-name, --loop-job).
Shared checks/thresholds unchanged. Derived from audit_exports_walk.py with an added walk_two (WalkTwoHand_Blender_v5, in-place loop) case.
Shared checks/thresholds unchanged; the walk case adds loop-closure, in-place root, narrow-stance and two-palm checks.

Check the owner's specific motion corrections against exported playback (feedback v4).

Runs outside Blender (system python with numpy/scipy). Reads the DELIVERED GLB names
(<Review>_Blender_v<revision>.glb) from --glb-dir and each <job>-report.json from --report-dir.
Writes only --out. Defaults come from common.params() (v4 export dir / v4 output dir).
Thresholds and checks are identical to feedback_v3/audit_exports.py.

Example (re-audit the delivered v3 GLBs without touching v3 folders):
  python3 tools/art/blender/feedback_v4/audit_exports.py --revision 3 \
    --glb-dir tools/asset-review/.asset-cache/review --report-dir Local/Blender/feedback-v3-20261021 \
    --out Local/Blender/feedback-v4-20261021/dryrun-v3-export-audit.json
"""
from pathlib import Path
import argparse,importlib.util,json,hashlib,sys
import numpy as np
from scipy.spatial.transform import Rotation
HERE=Path(__file__).resolve().parent
_cs=importlib.util.spec_from_file_location('veyr_v4_common',HERE/'common.py');cm=importlib.util.module_from_spec(_cs);_cs.loader.exec_module(cm)
ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('--glb-dir');ap.add_argument('--report-dir');ap.add_argument('--revision');ap.add_argument('--approved-dir');ap.add_argument('--out')
ap.add_argument('--jobs',default='walk_two');ap.add_argument("--walk-glb",default="WalkTwoHand_Blender_v5.glb");ap.add_argument("--glb-name");ap.add_argument("--loop-job",action="store_true")
a=ap.parse_args();ARGS=a
P=cm.params({'revision':a.revision,'approved_dir':a.approved_dir})
def _p(v,default):
 v=Path(v).expanduser() if v else default;return (v if v.is_absolute() else cm.REPO/v).resolve()
GLB_DIR=_p(a.glb_dir,P['export_dir']);REPORT_DIR=_p(a.report_dir,P['out']);OUT=cm.check_writable(_p(a.out,P['out']/'export-audit.json'))
REPO=cm.REPO
spec=importlib.util.spec_from_file_location('eval',REPO/'tools/unreal/normalize_customuse_glb.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
rows=[]
for job in a.jobs.split(','):
 glb=GLB_DIR/(ARGS.glb_name if ARGS.glb_name else ARGS.walk_glb if job=="walk_two" else cm.review_name(job,P['revision'])+'.glb');g=m.GLB(glb);ns={n.get('name'):i for i,n in enumerate(g.json['nodes'])};r=json.loads((REPORT_DIR/(job+'-report.json')).read_text());dur=max(float(g.accessor(s['input']).max()) for s in g.json['animations'][0]['samplers']);first=g.world_matrices(0,0);last=g.world_matrices(0,dur)
 root_delta=last[ns['Hips'],:3,3]-first[ns['Hips'],:3,3];foot_gap=100.;torso_turn=0.;palm=0.;leftwrist=0.;left_elbow_above_hip=100.;lengtherr=0.;jointstep=0.;hand_path=[];local_hand_path=[];knee_gap=100.
 socket=ns['ReviewWeaponSocket'];contact={s:np.linalg.solve(first[ns[s+'Hand']],first[socket]@np.array([0,-.075 if s=='Right' else -.255,0,1])) for s in ('Left','Right')}
 segments=[(ns[s+a],ns[s+b]) for s in ('Left','Right') for a,b in [('Arm','ForeArm'),('ForeArm','Hand'),('UpLeg','Leg'),('Leg','Foot')]];lengths={(a,b):np.linalg.norm(first[a,:3,3]-first[b,:3,3]) for a,b in segments}
 def rot(w,n):
  a=w[ns[n],:3,:3];return Rotation.from_matrix(a/np.linalg.norm(a,axis=0))
 neutral=rot(first,'LeftForeArm').inv()*rot(first,'LeftHand')
 for t in np.linspace(0,dur,round(dur*120)+1):
  w=g.world_matrices(0,float(t));assert np.isfinite(w).all();hand_path.append(w[ns['LeftHand'],:3,3]-w[ns['Spine2'],:3,3]);local_hand_path.append((np.linalg.inv(w[ns['Spine2']])@w[ns['LeftHand']])[:3,3]);knee_gap=min(knee_gap,float(w[ns['LeftLeg'],0,3]-w[ns['RightLeg'],0,3]))
  foot_gap=min(foot_gap,float(w[ns['LeftFoot'],0,3]-w[ns['RightFoot'],0,3]))
  torso_turn=max(torso_turn,float(np.rad2deg((rot(first,'Spine2').inv()*rot(w,'Spine2')).magnitude())))
  left_elbow_above_hip=min(left_elbow_above_hip,float(w[ns['LeftForeArm'],1,3]-w[ns['Hips'],1,3]))
  for a,b in segments:lengtherr=max(lengtherr,abs(float(np.linalg.norm(w[a,:3,3]-w[b,:3,3]))-lengths[a,b]))
  for side in (('Left','Right') if job in ('guard_two','walk_two') else ('Right',)):
   point=w[socket]@np.array([0,-.075 if side=='Right' else -.255,0,1]);palm=max(palm,float(np.linalg.norm((w[ns[side+'Hand']]@contact[side]-point)[:3])))
  if job in ('heal','heavy'):leftwrist=max(leftwrist,float(np.rad2deg((neutral.inv()*(rot(w,'LeftForeArm').inv()*rot(w,'LeftHand'))).magnitude())))
 for channel in g.json['animations'][0]['channels']:
  if channel['target']['path']=='rotation':
   qs=Rotation.from_quat(g.accessor(g.json['animations'][0]['samplers'][channel['sampler']]['output']));jointstep=max(jointstep,float(np.rad2deg((qs[:-1].inv()*qs[1:]).magnitude()).max()))
 expectedroot=None if ARGS.loop_job else {'backpedal':np.array([0,0,-.36]),'strafe_left':np.array([1.,0,0]),'strafe_right':np.array([-1.,0,0])}.get(job)
 row={'job':job,'glb':str(glb),'sha256':hashlib.sha256(glb.read_bytes()).hexdigest(),'reportSHA256':r.get('sha256'),'duration':dur,'nativeIKError':r['nativeIKError'],'maxLimbLengthChange':lengtherr,'maxHeldPalmDrift':palm,'minimumLeftRightFootGap':foot_gap,'maxTorsoTurnDegrees':torso_turn,'rootDelta':root_delta.tolist(),'leftWristDeviationDegrees':leftwrist,'minimumLeftElbowAboveHip':left_elbow_above_hip,'freeHandRelativeMotionExtent':float(np.linalg.norm(np.ptp(np.array(hand_path),axis=0))),'maxExportJointStepDegrees':jointstep,'ownerApproved':False}
 row['minimumKneeGap']=knee_gap
 row['freeHandChestLocalMotionExtent']=float(np.linalg.norm(np.ptp(np.array(local_hand_path),axis=0)))
 checked=['Hips','Head','LeftHand','RightHand','LeftFoot','RightFoot']
 refname='IdleTwoHand_Blender_v1.glb' if job in ('guard_two','walk_two') else 'IdleOneHand_Blender_v1.glb'
 reference=m.GLB(P['approved_dir']/refname);rn={n.get('name'):i for i,n in enumerate(reference.json['nodes'])};rw=reference.world_matrices(0,0)
 row['approvedIdleStartPositionError']=max(float(np.linalg.norm(first[ns[n],:3,3]-rw[rn[n],:3,3])) for n in checked)
 row['translatedIdleEndPositionError']=max(float(np.linalg.norm(last[ns[n],:3,3]-root_delta-first[ns[n],:3,3])) for n in checked)
 row['pass']=abs(dur-r['duration'])<1e-5 and r['nativeIKError']<.001 and lengtherr<.002 and palm<.003 and jointstep<35
 if expectedroot is not None:row['pass'] &= knee_gap>.10 and foot_gap>.20 and torso_turn>1.0 and torso_turn<20 and np.linalg.norm(root_delta-expectedroot)<1e-4
 if job in ('heal','heavy'):row['pass'] &= leftwrist<1.
 if job=='heal':row['pass'] &= left_elbow_above_hip>.09
 if job=='heavy':row['pass'] &= row['freeHandChestLocalMotionExtent']>.12
 if job not in ('guard_two','walk_two') and not ARGS.loop_job:row['pass'] &= row['approvedIdleStartPositionError']<1e-4
 if job not in ('guard_two','walk_two') and not ARGS.loop_job:row['pass'] &= row['translatedIdleEndPositionError']<1e-4
 if ARGS.loop_job:
  row['loopClosureMaxJointError']=float(max(np.linalg.norm(first[i,:3,3]-last[i,:3,3]) for i in range(len(first))))
  dt=1/150.;a0=g.world_matrices(0,0.);a1=g.world_matrices(0,dt);b0=g.world_matrices(0,dur-dt)
  row['loopVelocityJumpUnitsPerS']=float(max(np.linalg.norm((a1[i,:3,3]-a0[i,:3,3])-(last[i,:3,3]-b0[i,:3,3])) for i in range(len(first)))/dt)
  row['pass'] &= row['loopClosureMaxJointError']<1e-4 and float(np.linalg.norm(root_delta))<1e-4 and row['loopVelocityJumpUnitsPerS']<1.0 and foot_gap>0.
 if job=='walk_two':
  # Seamless in-place loop: last sample == first (all joints), velocity continuity across the seam,
  # narrow stance (ankles about hip width, never crossing), torso counter-rotation present but bounded.
  row['loopClosureMaxJointError']=float(max(np.linalg.norm(first[i,:3,3]-last[i,:3,3]) for i in range(len(first))))
  dt=1/150.;a0=g.world_matrices(0,0.);a1=g.world_matrices(0,dt);b0=g.world_matrices(0,dur-dt)
  row['loopVelocityJumpUnitsPerS']=float(max(np.linalg.norm((a1[i,:3,3]-a0[i,:3,3])-(last[i,:3,3]-b0[i,:3,3])) for i in range(len(first)))/dt)
  gaps=[];hipw=[]
  for t in np.linspace(0,dur,round(dur*120)+1):
   w=g.world_matrices(0,float(t));gaps.append(float(w[ns['LeftFoot'],0,3]-w[ns['RightFoot'],0,3]));hipw.append(float(w[ns['LeftUpLeg'],0,3]-w[ns['RightUpLeg'],0,3]))
  row['ankleLateralGap']=[min(gaps),float(np.mean(gaps)),max(gaps)];row['hipJointWidth']=[min(hipw),max(hipw)]
  row['previewLoop']=True;row['rootMotion']=r.get('rootMotion')
  row['pass'] &= row['loopClosureMaxJointError']<1e-4 and row['loopVelocityJumpUnitsPerS']<.2 and float(np.linalg.norm(root_delta))<1e-4
  row['pass'] &= .08<min(gaps) and max(gaps)<1.5*max(hipw) and knee_gap>.05 and 1.<torso_turn<20.
 if job=='guard_two':
  raised=g.world_matrices(0,.3);held=g.world_matrices(0,.4)
  row['rightHandRaise']=float(raised[ns['RightHand'],1,3]-first[ns['RightHand'],1,3])
  row['faceCoverReadySeconds']=.3
  row['holdPoseError']=max(float(np.linalg.norm(last[ns[n],:3,3]-held[ns[n],:3,3])) for n in checked)
  row['pass'] &= row['rightHandRaise']>.14 and row['holdPoseError']<.001
 if job.startswith('strafe'):
  extras=[n.get('extras',{}).get('veyrBlink') for n in g.json['nodes'] if n.get('extras',{}).get('veyrBlink')]
  row['visibilityMetadata']=json.loads(extras[0]) if extras else None
  row['pass'] &= bool(extras) and abs(dur-.7)<1e-5
 row['pass']=bool(row['pass']);rows.append(row)
OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows,indent=2));sys.exit(0 if all(r['pass'] for r in rows) else 1)
