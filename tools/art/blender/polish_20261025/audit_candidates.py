"""Read-only exported candidate audit. Authoring happens only inside Blender MCP."""
import sys,json,math,hashlib
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'tools/art/integration'))
from normalize_approved import GLB
OUT=ROOT/'Local/Blender/polish-20261025';REF=Path('/Users/midir/veyr-review-fable-20261021/tools/asset-review/.asset-cache/review')
NAMES=['Dragon_FlyHover_Blender_polish_v1','Dragon_Takeoff_Blender_polish_v2','Dragon_Land_Blender_polish_v3','RunTwoHand_Blender_polish_v2','GripToTwoHand_Blender_polish_v2','GripToOneHand_Blender_polish_v2','Roll_Blender_polish_v2','RollAttack_Blender_polish_v2']
g={n:GLB(OUT/(n+'.glb')) for n in NAMES}
def difference(a,b,times,names,bt=None):
 maxerr=0;maxpos=0;worst=None
 for t in times:
  aw,_=a.sample(float(t));bw,_=b.sample(float(t if bt is None else bt(t)))
  for n in names:
   x=aw[a.names[n]];y=bw[b.names[n]];e=float(abs(x-y).max());p=float(np.linalg.norm(x[:3,3]-y[:3,3]))
   if e>maxerr:maxerr=e;worst=(float(t),n)
   maxpos=max(p,maxpos)
 return {'maxMatrixDifference':maxerr,'maxPositionDifferenceRigUnits':maxpos,'worst':worst}
def limb_audit(x):
 rows=[]
 for t in np.linspace(0,min(.78,x.duration()),118):
  w,_=x.sample(float(t));pts=[w[x.names[n],:3,3] for n in ['RightArm','RightForeArm','RightHand']];rows.append([float(t),float(np.linalg.norm(pts[1]-pts[0])),float(np.linalg.norm(pts[2]-pts[1]))])
 return {'upperLengthRange':[min(x[1] for x in rows),max(x[1] for x in rows)],'forearmLengthRange':[min(x[2] for x in rows),max(x[2] for x in rows)]}
roll=g[NAMES[-2]];attack=g[NAMES[-1]];old=GLB(REF/'RollAttack_Blender_v1.glb');excluded={n for n in old.skin_names() if n.startswith(('RightArm','RightForeArm','RightHand'))}
report={'scope':'Exported transforms and finalgeometry, not visual acceptance','clips':[]}
report['rollBodyPreservation']=difference(roll,old,np.linspace(0,.78,118),[n for n in old.skin_names() if n not in excluded])
report['rollAttackPrefix']=difference(roll,attack,np.linspace(0,.78,118),roll.skin_names()+['ReviewWeaponSocket'])
report['rollAttackAfterJoin']=difference(attack,old,np.linspace(.98,2.2,62),old.skin_names()+['ReviewWeaponSocket'])
report['finalRightArm']=limb_audit(roll);report['sourceRightArm']=limb_audit(old)
run=g['RunTwoHand_Blender_polish_v2'];oldrun=GLB(REF/'RunOneHand_Blender_tripo_r2.glb')
report['runLowerBodyPreservation']=difference(run,oldrun,np.linspace(0,run.duration(),95),[n for n in oldrun.skin_names() if not any(x in n for x in ['Arm','Hand'])])
for a,ta,b,tb in [('Dragon_Takeoff_Blender_polish_v2',1.5,'Dragon_FlyHover_Blender_polish_v1',0),('Dragon_FlyHover_Blender_polish_v1',2,'Dragon_Land_Blender_polish_v3',0)]:report[a+'->'+b]=difference(g[a],g[b],[ta],g[a].skin_names(),lambda _:tb)
for n,x in g.items():
 row=json.loads((OUT/(n+'.json')).read_text());row['measuredExportDuration']=x.duration();row['boneCount']=len(x.skin_names());row['sha256']=x.sha
 if 'bake'in row:row['bake']['scope']='Pre-restoration generic solver diagnostic; not final pose acceptance'
 report['clips'].append(row)
(OUT/'candidate-audit.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='clips'},indent=2))
# Explicit endpoint and palm checks use the actual exported meshes/curves.
for clip,start,end in [('GripToTwoHand_Blender_polish_v2','IdleOneHand_Blender_v2r4.glb','IdleTwoHand_Blender_v2r4.glb'),('GripToOneHand_Blender_polish_v2','IdleTwoHand_Blender_v2r4.glb','IdleOneHand_Blender_v2r4.glb')]:
 for t,filename in [(0,start),(.5,end)]:
  ref=GLB(REF/filename);report[clip+('Start' if t==0 else 'End')]=difference(g[clip],ref,[t],ref.skin_names()+['ReviewWeaponSocket'],lambda _:0)
def palm_relative(x,ref,hand,times):
 rw,_=ref.sample(0);expected=np.linalg.inv(rw[ref.names['ReviewWeaponSocket']])@rw[ref.names[hand]];err=0
 for t in times:
  w,_=x.sample(float(t));rel=np.linalg.inv(w[x.names['ReviewWeaponSocket']])@w[x.names[hand]];err=max(err,float(abs(rel-expected).max()))
 return err
report['runLeftPalmSocketRelativeError']=palm_relative(run,GLB(REF/'IdleTwoHand_Blender_v2r4.glb'),'LeftHand',np.linspace(0,run.duration(),95))
report['runRightPalmSocketRelativeError']=palm_relative(run,GLB(REF/'IdleTwoHand_Blender_v2r4.glb'),'RightHand',np.linspace(0,run.duration(),95))
report['rollRightPalmSocketRelativeError']=palm_relative(roll,GLB(REF/'IdleOneHand_Blender_v2r4.glb'),'RightHand',np.linspace(0,.78,118))
weapon=GLB(REF/'BoatGreatsword_OneHand_v4.glb');v=weapon.accessor(weapon.g['meshes'][0]['primitives'][0]['attributes']['POSITION']);v=np.c_[v,np.ones(len(v))];floor=1e9
for t in np.linspace(0,.78,118):
 w,_=roll.sample(float(t));points=(w[roll.names['ReviewWeaponSocket']]@v.T).T;floor=min(floor,float(points[:,1].min()))
report['rollSwordMinimumGroundHeightRigUnits']=floor
(OUT/'candidate-audit.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if 'Palm'in k or 'MinimumGround'in k or k.startswith('Grip')},indent=2))
