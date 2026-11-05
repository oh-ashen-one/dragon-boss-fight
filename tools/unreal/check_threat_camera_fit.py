"""Read-only camera-fit geometry check against recorded gameplay. Not runtime QA."""
import json,math
from pathlib import Path
root=Path(__file__).resolve().parents[2]
def project(foot,head,arm,fov,yaw):
 aspect=16/9;half=math.atan(math.tan(math.radians(fov/2))/aspect);pitch=max(-5,min(25,math.degrees(half)-math.degrees(math.atan2(90,arm))-3.5));p,y=map(math.radians,[pitch,yaw]);cp,sp,cy,sy=math.cos(p),math.sin(p),math.cos(y),math.sin(y);fw=[cp*cy,cp*sy,sp];rr=[-sy,cy,0];up=[-sp*cy,-sp*sy,cp];pivot=max(170,90+arm*sp-12*cp);side=42+138*max(0,min(1,(pitch-15)/53));camera=[foot[i]+(pivot if i==2 else 0)-arm*fw[i]+side*rr[i]+12*up[i] for i in range(3)];points=[]
 for point in [foot,head,[foot[0],foot[1],foot[2]+244]]:
  v=[a-b for a,b in zip(point,camera)];z=sum(a*b for a,b in zip(v,fw))
  if z<=1:return None
  points.append([.5+.5*sum(a*b for a,b in zip(v,rr))/(z*math.tan(math.radians(fov/2))),.5-.5*sum(a*b for a,b in zip(v,up))/(z*math.tan(half))])
 return pitch,points
rows=[]
for stamp in ['20261105T025323Z','20261105T030339Z']:
 p=next((root/'Evidence'/('native-victory-'+stamp)).glob('unreal-*/evidence.json'));d=json.loads(p.read_text());selected=[]
 for s in d['samples']:
  if s['dragonMove']!='FlyAway' or s['dragonState'] not in ['Windup','Active','Recovery'] or not s['lockedOn']:continue
  choices=[]
  for arm in range(560,1601,80):
   for fov in [72,78,84,90,94]:
    value=project(s['playerFeet'],s['headPosition'],arm,fov,s['camera']['yaw'])
    if not value:continue
    pitch,points=value
    if all(.06<=x<=.94 and .06<=y<=.94 for x,y in points):
     cost=((arm-560)/560)**2+.7*((fov-72)/22)**2;choices.append((cost,arm,fov,pitch))
  selected.append({'seconds':s['seconds'],'state':s['dragonState'],'fit':min(choices) if choices else None})
 rows.append({'run':str(p.parent.parent.relative_to(root)),'samples':selected});print(stamp,'feasible',sum(x['fit'] is not None for x in selected),'/',len(selected),'windup',[(x['fit'][1:3] if x['fit'] else None) for x in selected if x['state']=='Windup'])
(root/'docs/master-goal-20261103/threat-framing-offline-fit.json').write_text(json.dumps({'scope':'Candidate geometry on recorded points, not collision-aware runtime or quality evidence','armBoundsCm':[560,1600],'fovBoundsDegrees':[72,94],'rows':rows},indent=2)+'\n')
