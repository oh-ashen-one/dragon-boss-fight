"""Hash the final private Blender assets and source-preservation evidence."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=ROOT/'Local/Blender/polish-20261025';REF=Path('/Users/midir/veyr-review-fable-20261021/tools/asset-review/.asset-cache/review')
NAMES=['Dragon_FlyHover_Blender_polish_v1','Dragon_Takeoff_Blender_polish_v2','Dragon_Land_Blender_polish_v3','RunTwoHand_Blender_polish_v2','GripToTwoHand_Blender_polish_v2','GripToOneHand_Blender_polish_v2','Roll_Blender_polish_v2','RollAttack_Blender_polish_v2']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
locked=json.loads((ROOT/'tools/art/integration/owner-approvals-20261025.json').read_text())['clips'];checks=[]
for c in locked:
 actual=sha(REF/c['file']);checks.append({'file':c['file'],'expected':c['sha256'],'actual':actual,'unchanged':actual==c['sha256']})
assert all(x['unchanged'] for x in checks),'Approved original hash changed'
clips=[]
for name in NAMES:
 row=json.loads((OUT/(name+'.json')).read_text());row.pop('bake',None);row['sha256']=sha(Path(row['file']));row['blendSHA256']=sha(Path(row['blend']));row['ownerApproved']=False;row['ownerRequestedRevision']=True
 row['runtimeKeys']=[row['key']];row['loop']=row['key'] in ['FlightHoverAlternate','RunTwoHand']
 row['authoring']='Actual Blender 5.2 native FK/IK/control keyframes through isolated MCP port9891; editable packed .blend'
 if name.startswith('Dragon_FlyHover'):row['runtimeKeys']=['FlightActive','FlightHoverAlternate']
 if not name.startswith('Dragon_'):row['weapon_file']='BoatGreatsword_OneHand_v4.glb'
 if row['key']=='RunTwoHand':row['nominal_speed_cm_per_second']=460.4147;row['root_policy']='in-place, unchanged approved Tripo run stride and timing'
 elif row['key']=='Roll':row['root_policy']='existing manual .78-second roll travel; body motion preserved except right-arm aiming'
 elif row['key']=='RollAttack':row['root_policy']='exact revised Roll prefix0-.78; existing root extraction after.78; original slash restored from.98';row['damage_windows']=[[1.03,1.27]]
 elif name.startswith('Dragon_'):row['root_policy']='preserve authored altitude; horizontal actor travel remains runtime-owned'
 else:row['root_policy']='in-place'
 if row['key']=='FlightRecovery':row['impact_seconds']=25/30
 views=['front','side','three_quarter' if name.startswith('Dragon_') else 'threequarter'];row['reviewFilms']={v:str(OUT/'fullspeed'/name/(v+'.mp4')) for v in views}
 clips.append(row)
crit=ROOT/'Local/Critique-Polish-20261025/critique-final.json'
report={'date':'2026-10-25','branch':'codex/veyr-combat-arena-polish-20261025','status':'Independent Blender critic ready for native validation; not native/owner acceptance','blender':'5.2.0 LTS','owner':'codex-veyr-polish-20261025','clips':clips,'approvedOriginalsVerifiedUnchanged':checks,'exactPoseAudit':str(OUT/'candidate-audit.json'),'flightSurfaceJoinAudit':str(OUT/'flight-mesh-seams.json'),'independentCritique':str(crit),'importantContracts':['Every new Knight clip uses intact BoatGreatsword_OneHand_v4.glb; Grip_v6 cutaway shaft must not be substituted.','Preserve added PolishHoverBreath morph and hash-distinct delta variants. Old fixed eight-target assumption is obsolete.','Map both FlightActive and FlightHoverAlternate to the revised hover so the new takeoff/land joins remain exact.','Discard local Rollv1, RunTwoHandv1 and earlier transition drafts; only listed clips are final candidates.']}
(OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'manifest':str(OUT/'manifest.json'),'clips':len(clips),'originalHashesVerified':len(checks)},indent=2))
