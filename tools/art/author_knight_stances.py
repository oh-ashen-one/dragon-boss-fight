#!/usr/bin/env python3
"""Original one/two-hand stance candidates on the preserved Customuse v012 body.

Only reviewed weapon component196 triangles are removed. All original body
attributes, weights, bind nodes/materials and source files are preserved.
Accepted Roll animation is copied exactly. New poses use actual-length limb
IK, bounded wrist swing, planted/support foot targets and measured palm frames.
No Unreal, Blender, network, paid generation or asset publication is performed.

Run from the checkout, supplying an explicit immutable weapon file:
  python3 tools/art/author_knight_stances.py --weapon Local/.../BoatGreatsword_v4.glb \
      --output Local/art-pass-20261019/knight/fresh-candidate \
      --clips IdleOneHand IdleTwoHand LightAttackOneHand HeavyAttackOneHand \
              LightAttackTwoHand HeavyAttackTwoHand GuardOneHand GuardTwoHand \
              HealOneHand RollBoat

NumPy, SciPy, Pillow and the existing repository GLB authoring helpers are used.
Outputs remain private, exclusive-created and never overwrite prior evidence.
Every run saves the exact generator source and rejects failed QA in its manifest.
CPU geometry/kinematic checks do not constitute native visual acceptance.
"""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from author_knight_actions import sample, build
from inspect_weapon_topology import topology
from author_knight_hold import CPU, rotation, quaternion, align, unit

SOURCE_SNAPSHOT=Path(__file__).read_bytes()
SOURCE_SHA256=hashlib.sha256(SOURCE_SNAPSHOT).hexdigest()
ROOT=Path(__file__).resolve().parents[2]
ASSETS=ROOT/'Local/CustomuseAssets'
OUT=ROOT/'Local/art-pass-20261019/knight'
G=np.array([[0.,0,1],[-1.,0,0],[0,1.,0]]) # glTF XYZ -> gameplay forward/right/up
S=np.array([[1.,0,0],[0,0,1],[0,1.,0]]) # glTF local -> imported UE local


def local_input(value):
    """Resolve preserved project-private inputs after moving a checkout."""
    path=Path(value);candidate=path if path.is_absolute() else ROOT/path
    if candidate.is_file():return candidate.resolve()
    if 'Local' in path.parts:
        candidate=ROOT.joinpath(*path.parts[path.parts.index('Local'):])
        if candidate.is_file():return candidate.resolve()
    raise ValueError('Required preserved input is missing: '+str(value))


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ease(x):x=float(np.clip(x,0,1));return x*x*(3-2*x)
def angle(R):return math.degrees(math.acos(float(np.clip((np.trace(R)-1)/2,-1,1))))
def yaw(degrees):
    a=math.radians(degrees);c,s=math.cos(a),math.sin(a)
    return G.T@np.array([[c,-s,0],[s,c,0],[0,0,1.]])@G


def no_weapon(g,mask):
    out=CPU.GLB(g.bytes());node=g.json['nodes'][g.mesh_node()];p=g.json['meshes'][node['mesh']]['primitives'][0]
    if len(g.json['meshes'][node['mesh']]['primitives'])!=1:raise ValueError('Expected canonical single primitive')
    indices=g.accessor(p['indices']).reshape(-1,3).copy();selected=np.array(mask['triangleIndices']);vertices=np.array(mask['vertexIndices'])
    if mask['componentId']!=196 or not np.array_equal(np.unique(indices[selected]),vertices):raise ValueError('Reviewed sword mask mismatch')
    keep=np.ones(len(indices),bool);keep[selected]=False
    if np.intersect1d(vertices,np.unique(indices[keep])).size:raise ValueError('Weapon shares body vertices')
    data=np.asarray(indices[keep].ravel(),dtype='<u4');out.binary.extend(b'\0'*(-len(out.binary)%4));offset=len(out.binary);out.binary.extend(data.tobytes())
    vi=len(out.json['bufferViews']);out.json['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':data.nbytes,'target':34963})
    ai=len(out.json['accessors']);out.json['accessors'].append({'bufferView':vi,'componentType':5125,'count':len(data),'type':'SCALAR'})
    out.json['meshes'][node['mesh']]['primitives'][0]['indices']=ai;out.json['buffers'][0]['byteLength']=len(out.binary)
    if out.binary[:len(g.binary)]!=g.binary:raise ValueError('Original body/animation bytes changed')
    return out,indices[keep]


class Rig:
    def __init__(self,g,idle,mask,weapon_path=None,weapon_shift_cm=(0.,0.,0.)):
        self.g=g;self.names={n.get('name'):i for i,n in enumerate(g.json['nodes'])};self.rest=g.world_matrices();self.base=sample(idle,1.5)
        self.factor=244/np.ptp(g.skinned_positions()[:,1]);self.mask=mask;self.scale=np.array([n.get('scale',[1,1,1]) for n in g.json['nodes']])
        self.order=[]
        def visit(i):
            if i in self.order:return
            if i in g.parents:visit(g.parents[i])
            self.order.append(i)
        for i in range(len(g.json['nodes'])):visit(i)
        # The provider idle carries25/13/22-degree spine offsets and unequal
        # clavicle poses. Start the new upper body from the actual bind anatomy,
        # retaining the already-grounded hips/legs, then author deliberate motion.
        for name in ['Spine','Spine1','Spine2','Neck','Head','RightShoulder','LeftShoulder']:
            index=self.names[name];self.base[(index,'rotation')]=np.array(g.json['nodes'][index].get('rotation',[0,0,0,1]),dtype=float)
        self.baseW=self.world(self.base);self.hips=self.names['Hips']
        self.chains={side:[self.names[side+n] for n in ['Arm','ForeArm','Hand']] for side in ['Right','Left']}
        self.legs={side:[self.names[side+n] for n in ['UpLeg','Leg','Foot']] for side in ['Right','Left']}
        n=g.json['nodes'][g.mesh_node()];self.p=g.json['meshes'][n['mesh']]['primitives'][0]
        self.J=g.accessor(self.p['attributes']['JOINTS_0']).copy();self.weights=g.accessor(self.p['attributes']['WEIGHTS_0']).copy();self.skin=g.json['skins'][n['skin']]['joints'];P=g.skinned_positions()
        self.grip={};self.frames={};self.palm_axes={}
        for side in ['Right','Left']:
            hand=self.chains[side][2];inverse=np.linalg.inv(self.rest[hand])
            points={part:(inverse@np.r_[self.rest[self.names[side+'Hand'+part],:3,3],1])[:3] for part in ['Index','Pinky','Middle']}
            longitudinal=unit(points['Middle']);blade=unit(points['Index']-points['Pinky'])
            across=unit(longitudinal-blade*np.dot(longitudinal,blade))
            self.grip[side]=(points['Index']+points['Pinky'])*.5-across*.010
            self.frames[side]=np.column_stack([across,np.cross(across,blade),blade])
            if side=='Left':self.frames[side]=self.frames[side]@np.diag([-1.,-1.,1.])
            self.palm_axes[hand]=longitudinal
        self.fingers=[]
        for side in ['Right','Left']:
            pending=list(g.json['nodes'][self.chains[side][2]].get('children',[]))
            while pending:
                i=pending.pop();self.fingers.append(i);pending.extend(g.json['nodes'][i].get('children',[]))
        original_faces=g.accessor(self.p['indices']).reshape(-1,3)
        components,_,_=topology(g.accessor(self.p['attributes']['POSITION']),original_faces,0.)
        # These exact disconnected hands were identified during the earlier
        # source topology review; do not confuse stray hand-weighted cloth with hands.
        self.hand_faces={side:original_faces[components[cid]] for side,cid in [('Right',207),('Left',1646)]}
        self.hand_vertices={side:np.unique(faces) for side,faces in self.hand_faces.items()}
        self.weapon_path=local_input(weapon_path) if weapon_path else ROOT/'Local/art-pass-20261019/tripo/BoatGreatsword_v4.glb'
        weapon=CPU.GLB(self.weapon_path);wp=weapon.json['meshes'][0]['primitives'][0]
        self.weapon_vertices=weapon.accessor(wp['attributes']['POSITION']).copy()@S.T*(100/self.factor)
        self.weapon_faces=weapon.accessor(wp['indices']).reshape(-1,3).copy()
        self.weapon_trial_shift_cm=np.asarray(weapon_shift_cm,dtype=float);self.weapon_vertices+=self.weapon_trial_shift_cm/self.factor
        self.weapon_tip_cm=self.weapon_vertices[np.argmax(self.weapon_vertices[:,2])]*self.factor
        grip_receipt=self.weapon_path.with_suffix('.grip.json');self.weapon_base_cm=np.array([0.,0.,float(np.min(self.weapon_vertices[:,2])*self.factor)])
        if grip_receipt.exists():
            metadata=json.loads(grip_receipt.read_text())
            if metadata.get('outputSHA256')!=sha(self.weapon_path):raise ValueError('Weapon grip receipt hash mismatch')
            self.weapon_tip_cm=np.array(metadata['bladeTipUECm'])+self.weapon_trial_shift_cm;self.weapon_base_cm=np.array(metadata['bladeBaseUECm'])+self.weapon_trial_shift_cm
        self.fixed_stance=None;self.fixed_stance_metrics=None;self.metrics=[];self.soft=False;self.correction=np.zeros(4);self.previous_elbows={};self.previous_upper_rotations={};self.elbow_delta_degrees=12.

    def world(self,pose):
        W=np.zeros((len(self.g.json['nodes']),4,4))
        for i in self.order:
            node=self.g.json['nodes'][i];q=pose.get((i,'rotation'),node.get('rotation',[0,0,0,1]));t=pose.get((i,'translation'),node.get('translation',[0,0,0]));local=np.eye(4);local[:3,:3]=rotation(q)@np.diag(pose.get((i,'scale'),self.scale[i]));local[:3,3]=t
            W[i]=W[self.g.parents[i]]@local if i in self.g.parents else local
        return W

    def set_world_rotation(self,pose,node,R,W=None):
        W=self.world(pose) if W is None else W;parent=self.g.parents.get(node);pose[(node,'rotation')]=quaternion(W[parent,:3,:3].T@R if parent is not None else R)

    def limb(self,pose,chain,target,desired,pole,limit=None):
        W=self.world(pose);upper,fore,end=chain;shoulder=W[upper,:3,3];L1=np.linalg.norm(W[fore,:3,3]-shoulder);L2=np.linalg.norm(W[end,:3,3]-W[fore,:3,3]);delta=target-shoulder;d=np.linalg.norm(delta)
        requested=d;minimum=math.sqrt(L1*L1+L2*L2-2*L1*L2*math.cos(math.radians(25 if limit is not None else 5)))
        maximum=math.sqrt(L1*L1+L2*L2-2*L1*L2*math.cos(math.radians(165 if limit is not None else 175)))
        if limit is not None:maximum=min(maximum,.97*(L1+L2))
        clamped=float(np.clip(d,minimum,maximum))
        if abs(d-clamped)>1e-5 and not self.soft:raise ValueError('Unreachable '+self.g.json['nodes'][end]['name']+f' {d*self.factor:.2f}/{(L1+L2)*self.factor:.2f}cm')
        d=clamped;target=shoulder+unit(delta)*d
        direction=unit(delta);along=(L1*L1-L2*L2+d*d)/(2*d);height=math.sqrt(max(0,L1*L1-along*along));pole=unit(pole-direction*np.dot(pole,direction))
        continuous=False
        if limit is not None and end in self.previous_elbows:
            projected=self.previous_elbows[end]-(shoulder+direction*along);projected-=direction*np.dot(projected,direction)
            if np.linalg.norm(projected)>1e-9:pole=unit(projected);continuous=True
        other=np.cross(direction,pole)
        ref_hand=rotation(self.g.json['nodes'][end].get('rotation',[0,0,0,1]));ref_fore=rotation(self.g.json['nodes'][fore].get('rotation',[0,0,0,1]));end_t=np.array(self.g.json['nodes'][end]['translation']);fore_t=np.array(self.g.json['nodes'][fore]['translation']);best=None
        # Search a bounded anatomical elbow hemisphere around the explicit pole.
        ideal=target-desired@self.palm_axes[end]*L2-(shoulder+direction*along) if limit is not None else np.zeros(3)
        preferred=math.degrees(math.atan2(np.dot(ideal,other),np.dot(ideal,pole)))
        theta_choice=float(np.clip(preferred,-self.elbow_delta_degrees,self.elbow_delta_degrees)) if continuous else float(np.clip(preferred,-85,85))
        for theta in ([0.] if limit is None else [theta_choice]):
            a=math.radians(theta);elbow=shoulder+direction*along+height*(pole*math.cos(a)+other*math.sin(a))
            if limit is None:
                upperR=align(self.baseW[fore,:3,3]-self.baseW[upper,:3,3],elbow-shoulder)@self.baseW[upper,:3,:3]
                foreR=align(self.baseW[end,:3,3]-self.baseW[fore,:3,3],target-elbow)@self.baseW[fore,:3,:3]
            else:
                hint=desired@ref_hand.T;foreR=align(hint@end_t,target-elbow)@hint
                hint=self.previous_upper_rotations.get(upper,self.baseW[upper,:3,:3]);upperR=align(hint@fore_t,elbow-shoulder)@hint
            wrist=foreR.T@desired;wrist_angle=angle(ref_hand.T@wrist)
            bend=math.degrees(math.acos(float(np.clip(unit(target-elbow)@(desired@self.palm_axes[end]),-1,1)))) if limit is not None else wrist_angle
            dq=quaternion(ref_hand.T@wrist);axis=self.palm_axes.get(end,unit(end_t));twist=math.degrees(2*math.atan2(float(dq[:3]@axis),abs(float(dq[3]))));score=bend+abs(theta)*.01
            if best is None or score<best[0]:best=(score,elbow,upperR,foreR,wrist,wrist_angle,theta,bend,twist)
        _,elbow,upperR,foreR,wrist,wrist_angle,theta,bend,twist=best
        if limit is not None and (bend>limit+.10 or abs(twist)>30) and not self.soft:raise ValueError(self.g.json['nodes'][end]['name']+f' wrist bend{bend:.2f} twist{twist:.2f} exceeds{limit:.0f}/30deg')
        self.set_world_rotation(pose,upper,upperR,W);pose[(fore,'rotation')]=quaternion(upperR.T@foreR);pose[(end,'rotation')]=quaternion(wrist)
        elbow_angle=math.degrees(math.acos(float(np.clip(np.dot(shoulder-elbow,target-elbow)/(L1*L2),-1,1))))
        return {'end':self.g.json['nodes'][end]['name'],'wristFromReferenceDegrees':wrist_angle,'wristBendDegrees':bend,'wristTwistDegrees':twist,'elbowInteriorDegrees':elbow_angle,'poleSweepDegrees':theta,'reachClampCm':abs(requested-clamped)*self.factor,'target':target.tolist()}

    def weapon_frame(self,direction):
        blade=unit(direction);x=unit(np.cross([0,0,1.],blade));y=np.cross(blade,x)
        return G.T@np.column_stack([x,y,blade])

    def arms(self,pose,grip_game,direction,two,roll=0.):
        a=math.radians(roll);axial=np.array([[math.cos(a),-math.sin(a),0],[math.sin(a),math.cos(a),0],[0,0,1.]])
        weapon=self.weapon_frame(direction)@(np.diag([-1.,-1.,1.]) if two else np.eye(3))@axial;grip=G.T@np.asarray(grip_game)/self.factor;metrics=[]
        for side in ['Right','Left']:
            if side=='Right' or two:
                center=grip if side=='Right' else grip-weapon[:,2]*(28/self.factor)
                desired=weapon@self.frames[side].T;target=center-desired@self.grip[side]
            else:
                # Free hand beside the pelvis, distinctly outside the torso.
                shoulder=self.world(pose)[self.chains[side][0],:3,3]
                target=shoulder+G.T@np.array([8.,-18.,-55.])/self.factor
                desired=self.baseW[self.chains[side][2],:3,:3]
            pole=G.T@np.array([.5,1 if side=='Right' else -1,-.4])
            if side=='Left' and not two:pole=G.T@np.array([.1,-.25,-1.])
            m=self.limb(pose,self.chains[side],target,desired,pole,35. if side=='Right' or two else None)
            if side=='Left' and not two:
                pose[(self.chains[side][2],'rotation')]=rotation_quat=self.g.json['nodes'][self.chains[side][2]].get('rotation',[0,0,0,1])
                pose[(self.chains[side][2],'rotation')]=np.array(rotation_quat,dtype=float);m['wristFromReferenceDegrees']=0.;m['wristBendDegrees']=22.;m['wristTwistDegrees']=0.
            metrics.append(m)
        for node in self.fingers:pose[(node,'rotation')]=unit(self.g.json['nodes'][node].get('rotation',[0,0,0,1]))
        return metrics

    def pose(self,time,duration,two,kind):
        pose={k:v.copy() for k,v in self.base.items()};phase=time/duration;breath=math.sin(phase*2*math.pi)
        grip=np.array([58.,15.,180.] if two else [30.,78.,155.]);direction=np.array([.15,.42,.895] if two else [.12,.32,.94]);hipyaw=0.;chestyaw=0.;step=0.;lift=0.;rootforward=0.;dip=0.
        if kind in ('Light','Heavy'):
            heavy=kind=='Heavy'
            if two:
                controls=[(0,grip,direction,0,0,0,0),(.24 if not heavy else .30,[52,28,198] if not heavy else [50,30,215],[.12,.70,.70] if not heavy else [.10,.85,.52],-8,-10,12,7),(.511111 if not heavy else .533333,[65,6,195] if not heavy else [65,8,210],[.75,-.25,-.61] if not heavy else [.72,-.15,-.68],10,15,12,0),(.68,[65,6,195] if not heavy else [65,8,210],[.75,-.25,-.61] if not heavy else [.72,-.15,-.68],14,16,12,0),(.88,grip,direction,5,5,5,6),(1,grip,direction,0,0,0,0)]
            else:
                controls=[(0,grip,direction,0,0,0,0),(.25,[40,75,182] if not heavy else [42,75,195],[.05,.4,.916] if not heavy else [.05,.4,.916],-9,-11,12,7),(.50,[60,55,195] if not heavy else [62,50,205],[.78,-.32,-.53] if not heavy else [.78,-.30,-.55],10,15,12,0),(.66,[65,35,180] if not heavy else [65,35,190],[.78,-.4,-.48] if not heavy else [.78,-.4,-.48],16,17,12,0),(.86,grip,direction,5,6,5,6),(1,grip,direction,0,0,0,0)]
            for a,b in zip(controls,controls[1:]):
                if a[0]-1e-9<=phase<=b[0]+1e-9:
                    u=ease((phase-a[0])/(b[0]-a[0]));grip=(1-u)*np.array(a[1])+u*np.array(b[1]);direction=unit((1-u)*np.array(a[2])+u*np.array(b[2]));hipyaw=(1-u)*a[3]+u*b[3];chestyaw=(1-u)*a[4]+u*b[4];step=(1-u)*a[5]+u*b[5];lift=(1-u)*a[6]+u*b[6];break
            rootforward=4*math.sin(math.pi*phase)**2;dip=3.5*math.sin(math.pi*phase)**2
        else:
            hipyaw=1.2*breath;chestyaw=-.8*breath;dip=-1.2*breath
            grip=grip+np.array([.6*breath,.8*breath,1.0*breath])
        if kind=='Guard':
            hipyaw=.4*breath;chestyaw=-.3*breath;dip=4.-.4*breath;step=6.;grip+=np.array([0.,0.,-4.])
            if not two:direction=unit([.18,.32,.93])
        if kind in ('Light','Heavy'):hipyaw=-hipyaw;chestyaw=-chestyaw
        hips=self.hips;pose[(hips,'translation')]=self.base[(hips,'translation')]+G.T@np.array([rootforward,1.0*breath if kind=='Idle' else 0,-dip])/self.factor
        self.set_world_rotation(pose,hips,yaw(hipyaw)@self.baseW[hips,:3,:3])
        for name,share in [('Spine',.2),('Spine1',.35),('Spine2',.45)]:
            i=self.names[name];W=self.world(pose);self.set_world_rotation(pose,i,yaw(chestyaw*share)@W[i,:3,:3],W)
        # Scapular protraction provides anatomical reach without stretching
        # arm bones or forcing wrist bend around the wide breastplate.
        protraction=(32. if two else 14.)+(8.*math.sin(math.pi*phase)**2 if kind in ('Light','Heavy') else 1.2*breath)
        for side,sign in [('Right',-1),('Left',1)]:
            node=self.names[side+'Shoulder'];W=self.world(pose);self.set_world_rotation(pose,node,yaw(sign*protraction)@W[node,:3,:3],W)
        # Actual left-foot step with a fixed support right foot; endpoints return
        # to the original grounded stance, not a translated gameplay actor.
        for side in ['Right','Left']:
            foot=self.legs[side][2];target=self.baseW[foot,:3,3].copy()
            if side=='Left':target+=G.T@np.array([step,0,lift])/self.factor
            footR=yaw(hipyaw*.20)@self.baseW[foot,:3,:3]
            self.limb(pose,self.legs[side],target,footR,G.T@np.array([1.,.1 if side=='Right' else -.1,0]))
        if self.fixed_stance is not None:
            for node in self.fixed_stance:pose[(node,'rotation')]=self.fixed_stance[node].copy()
            world=self.world(pose);hand=self.chains['Right'][2];actual_grip=world[hand,:3,3]+world[hand,:3,:3]@self.grip['Right'];frame=world[hand,:3,:3]@self.frames['Right']
            metrics=copy.deepcopy(self.fixed_stance_metrics)
            for metric in metrics:metric['target']=world[self.names[metric['end']],:3,3].tolist()
            return pose,{'seconds':time,'rightGripGameCm':(G@actual_grip*self.factor).tolist(),'bladeDirectionGame':(G@frame[:,2]).tolist(),'hipYawDegrees':hipyaw,'chestYawDegrees':chestyaw,'leftStepCm':step,'leftLiftCm':lift,'limbs':metrics,'authoring':'One anatomical hold carried by a periodic breathing torso; no per-frame arm IK'}
        original={k:v.copy() for k,v in pose.items()}
        def residual(x):
            candidate={k:v.copy() for k,v in original.items()};self.soft=True
            metrics=self.arms(candidate,grip+x[:3],direction,two,float(x[3]));self.soft=False
            return np.r_[[max(0.,m['wristBendDegrees']-27.)*8 for m in metrics],
                         [m['reachClampCm']*1000 for m in metrics],[max(0.,abs(m['wristTwistDegrees'])-25)*8 for m in metrics],x[:3]*.03,x[3]*.002]
        # Small measured path adjustments and grip-axis roll are solved instead
        # of dumping unreachable orientation into a bent wrist. +Z never flips.
        minimum_forward=(48.+28.*max(0.,unit(direction)[0])) if two else (45. if abs(grip[1])<40 else 35.)
        low=np.array([max(-15.,minimum_forward-grip[0]),-15.,-15.,-100.]);high=np.array([15.,15.,15.,100.])
        if np.any(low>=high):raise ValueError('Grip path cannot clear the torso within its authoring bounds')
        initial=np.clip(self.correction.copy(),low+1e-6,high-1e-6)
        result=least_squares(residual,initial,bounds=(low,high),
                             max_nfev=80,ftol=1e-5,xtol=1e-5,gtol=1e-5,diff_step=1e-3)
        def valid_correction(x):
            candidate={k:v.copy() for k,v in original.items()};self.soft=True
            ms=self.arms(candidate,grip+x[:3],direction,two,float(x[3]));self.soft=False
            return all(m['wristBendDegrees']<=34. and abs(m['wristTwistDegrees'])<=28. and m['reachClampCm']<=.001 for m in ms)
        if not valid_correction(result.x):
            options=[result]
            for seed_roll in [-90.,90.,-45.,45.]:
                seed=np.clip(np.r_[initial[:3],seed_roll],low+1e-6,high-1e-6)
                trial=least_squares(residual,seed,bounds=(low,high),max_nfev=80,ftol=1e-5,xtol=1e-5,gtol=1e-5,diff_step=1e-3);options.append(trial)
                if valid_correction(trial.x):break
            feasible=[option for option in options if valid_correction(option.x)]
            result=min(feasible or options,key=lambda option:float(np.linalg.norm(residual(option.x))))
        self.correction=result.x;grip=grip+result.x[:3]
        metrics=self.arms(pose,grip,direction,two,float(result.x[3]))
        return pose,{'seconds':time,'rightGripGameCm':grip.tolist(),'bladeDirectionGame':unit(direction).tolist(),'hipYawDegrees':hipyaw,'chestYawDegrees':chestyaw,'leftStepCm':step,'leftLiftCm':lift,'gripPathCorrectionCm':self.correction[:3].tolist(),'weaponAxialRollCorrectionDegrees':float(self.correction[3]),'limbs':metrics}




class WeightStanceRig(Rig):
 def __init__(self,*args,**kwargs):
  super().__init__(*args,**kwargs);self.frames['Left']=self.frames['Left']@np.diag([-1.,-1.,1.]);self.context=(0.,4.,False,'Idle')
 def upgrade_body(self,pose):
  time,duration,two,kind=self.context;phase=time/duration;attack=kind in ('Light','Heavy');heavy=kind=='Heavy' or (kind=='Light' and duration>.8);pulse=math.sin(math.pi*phase) if attack else 0.;pulse2=pulse*pulse
  if not attack and not two:return
  old=self.world(pose);hip=self.hips;rootdelta=np.array([(4. if heavy else 2.)*pulse2,0.,-(6. if two else 0.)-(8. if heavy else 5.)*pulse])
  if attack:
   controls=[(0,0),(.25,8),(.5,-6),(.68,-8),(1,0)]
   for l,r in zip(controls,controls[1:]):
    if l[0]<=phase<=r[0]+1e-9:rootdelta[1]=(1-ease((phase-l[0])/(r[0]-l[0])))*l[1]+ease((phase-l[0])/(r[0]-l[0]))*r[1];break
  pose[(hip,'translation')]+=G.T@rootdelta/self.factor
  strength=(1.35 if heavy else 1.25) if attack else 1.
  def heading(matrix):
   game=G@matrix@G.T;return math.degrees(math.atan2(game[1,0],game[0,0]))
  hipyaw=heading(old[hip,:3,:3]@self.baseW[hip,:3,:3].T);spine=self.names['Spine2'];totalyaw=heading(old[spine,:3,:3]@self.baseW[spine,:3,:3].T);chestyaw=totalyaw-hipyaw
  W=self.world(pose);self.set_world_rotation(pose,hip,yaw((strength-1)*hipyaw)@W[hip,:3,:3],W)
  for name,share in [('Spine',.2),('Spine1',.35),('Spine2',.45)]:
   n=self.names[name];W=self.world(pose);self.set_world_rotation(pose,n,yaw((strength-1)*chestyaw*share)@W[n,:3,:3],W)
  pitch=4. if two else 0.
  if attack:
   curve=[(0,pitch),(.25,-3.),(.5,13. if heavy else 10.),(.68,16. if heavy else 12.),(1,pitch)]
   for l,r in zip(curve,curve[1:]):
    if l[0]<=phase<=r[0]+1e-9:q=ease((phase-l[0])/(r[0]-l[0]));pitch=(1-q)*l[1]+q*r[1];break
  if attack and two:pitch=0.
  body_right=-G.T@np.array([-math.sin(math.radians(totalyaw*strength)),math.cos(math.radians(totalyaw*strength)),0.])
  for name,share in [('Spine',.2),('Spine1',.35),('Spine2',.45)]:
   n=self.names[name];W=self.world(pose);R=Rotation.from_rotvec(body_right*math.radians(pitch*share)).as_matrix();self.set_world_rotation(pose,n,R@W[n,:3,:3],W)
  spread=10.*(1. if two else pulse)
  for side,sign in [('Right',1),('Left',-1)]:
   foot=self.legs[side][2];delta=G@(old[foot,:3,3]-self.baseW[foot,:3,3])*self.factor
   if side=='Left':delta[0]=(12. if two else 0.)+delta[0]*((20./12. if two else 30./12.) if attack else 1.);delta[2]*=1.3 if attack else 1.
   if two:delta[1]+=sign*spread
   elif side=='Left' and attack:delta[1]-=20.*min(1.,max(0.,float((G@(old[foot,:3,3]-self.baseW[foot,:3,3]))[0]*self.factor/12.)))
   target=self.baseW[foot,:3,3]+G.T@delta/self.factor;rotation=yaw(sign*12.*(1. if two else pulse))@old[foot,:3,:3]
   self.limb(pose,self.legs[side],target,rotation,G.T@np.array([1.,sign*.25,0.]))
 def arms(self,pose,grip_game,direction,two,roll=0.):
  before=self.world(pose);self.upgrade_body(pose);after=self.world(pose);time,duration,_,kind=self.context;phase=time/duration;attack=kind in ('Light','Heavy');pulse2=math.sin(math.pi*phase)**2 if attack else 0.;grip_game=np.asarray(grip_game,dtype=float).copy();direction=np.asarray(direction,dtype=float).copy()
  if two:
   if attack:
    grip_game+=np.array([10.+12.*pulse2,0.,-18.-20.*pulse2])
    if direction[2]<0:direction[2]=max(direction[2],-.40 if kind=='Heavy' else -.38);direction=unit(direction)
   else:
    nodes=[self.chains[x][0] for x in ['Right','Left']];shift=G@np.mean(after[nodes,:3,3]-before[nodes,:3,3],axis=0)*self.factor;grip_game+=shift+np.array([10.,0.,-12.])
  elif attack:
   node=self.chains['Right'][0];grip_game+=G@(after[node,:3,3]-before[node,:3,3])*self.factor
  metrics=super().arms(pose,grip_game,direction,two,roll)
  if attack and not two:
   shoulder=self.world(pose)[self.chains['Left'][0],:3,3];target=shoulder+G.T@np.array([8.-20.*pulse2,-18.-15.*pulse2,-55.+12.*pulse2])/self.factor
   metric=self.limb(pose,self.chains['Left'],target,self.baseW[self.chains['Left'][2],:3,:3],G.T@np.array([.1,-.25,-1.]))
   pose[(self.chains['Left'][2],'rotation')]=np.array(self.g.json['nodes'][self.chains['Left'][2]].get('rotation',[0,0,0,1]),float);metric['wristFromReferenceDegrees']=0.;metric['wristBendDegrees']=22.;metric['wristTwistDegrees']=0.;metrics[-1]=metric
  return metrics
 def pose(self,time,duration,two,kind):
  self.context=(time,duration,two,kind);held=self.fixed_stance is not None;p,m=super().pose(time,duration,two,kind)
  if held:self.upgrade_body(p)
  W=self.world(p);h=self.chains['Right'][2];m['rightGripGameCm']=(G@(W[h,:3,3]+W[h,:3,:3]@self.grip['Right'])*self.factor).tolist();m['profile']='v2_unflipped_left_palm_wide_loaded_stance';return p,m


def sequence(rig,duration,two,kind):
    from author_knight_actions import blend
    if kind in ('Idle','Guard'):
        rig.fixed_stance=None;rig.correction=np.zeros(4);baseline,baseline_metrics=rig.pose(0.,duration,two,kind)
        nodes=[i for name,i in rig.names.items() if name.startswith(('RightShoulder','RightArm','RightForeArm','RightHand','LeftShoulder','LeftArm','LeftForeArm','LeftHand'))]
        rig.fixed_stance={i:baseline[(i,'rotation')].copy() for i in nodes};rig.fixed_stance_metrics=baseline_metrics['limbs']
        times=np.linspace(0,duration,round(duration*60)+1);poses=[];metrics=[]
        for t in times:
            p,m=rig.pose(float(t),duration,two,kind);poses.append(p);metrics.append(m)
        poses[-1]=copy.deepcopy(poses[0]);rig.fixed_stance=None;rig.fixed_stance_metrics=None
        return poses,times,metrics
    impact=(.46/.90 if kind=='Light' else .64/1.20) if two else .5
    phases=[0,.24 if two and kind=='Light' else .30 if two else .25,impact,.68 if two else .66,1.]
    keyposes=[];keymetrics=[];rig.correction=np.zeros(4);rig.previous_elbows={};rig.previous_upper_rotations={}
    for phase in phases:
        p,m=rig.pose(phase*duration,duration,two,kind);keyposes.append(p);keymetrics.append(m)
    times=np.unique(np.r_[np.linspace(0,duration,round(duration*60)+1),impact*duration]);poses=[];metrics=[]
    if two:
        phases.insert(-1,.86)
        keyposes.insert(-1,copy.deepcopy(keyposes[1]));keymetrics.insert(-1,copy.deepcopy(keymetrics[1]))
    keyworld=[rig.world(p) for p in keyposes];previous_adjustment=np.zeros(4)
    for t in times:
        phase=float(t/duration);i=max(0,min(len(phases)-2,int(np.searchsorted(phases,phase,side='right')-1)));u=ease((phase-phases[i])/(phases[i+1]-phases[i]));pose=blend(keyposes[i],keyposes[i+1],u)
        # Interpolate already constrained joint rotations, not a discontinuous
        # sequence of independent IK optima. Replant support feet after blending.
        for side in ['Right','Left']:
            foot=rig.legs[side][2];W=rig.world(pose);target=(1-u)*keyworld[i][foot,:3,3]+u*keyworld[i+1][foot,:3,3]
            rig.limb(pose,rig.legs[side],target,W[foot,:3,:3],G.T@np.array([1.,.1 if side=='Right' else -.1,0]))
        right=rig.chains['Right'][2];limbs=[]
        if poses:
            previousW=rig.world(poses[-1]);rig.previous_elbows={rig.chains[side][2]:previousW[rig.chains[side][1],:3,3].copy() for side in ['Right','Left']};rig.previous_upper_rotations={rig.chains[side][0]:previousW[rig.chains[side][0],:3,:3].copy() for side in ['Right','Left']}
        else:rig.previous_elbows={};rig.previous_upper_rotations={}
        if two or kind=='Heavy':
            grip_a=keyworld[i][right,:3,3]+keyworld[i][right,:3,:3]@rig.grip['Right']
            grip_b=keyworld[i+1][right,:3,3]+keyworld[i+1][right,:3,:3]@rig.grip['Right']
            grip=(1-u)*grip_a+u*grip_b
            desired_right=rotation(CPU.slerp(quaternion(keyworld[i][right,:3,:3]),quaternion(keyworld[i+1][right,:3,:3]),u))
            if two:
                blade_game=G@(desired_right@rig.frames['Right'][:,2]);grip_game=G@grip*rig.factor
                forward=max(0.,blade_game[0]);lower_clearance=48.+8.*min(1.,forward/.6)
                grip_game[0]=max(grip_game[0],lower_clearance+28.*forward);grip_game[1]+=4.*min(1.,forward/.6);grip=G.T@grip_game/rig.factor
            target_right=grip-desired_right@rig.grip['Right']
            original={k:v.copy() for k,v in pose.items()}
            def apply_frame(candidate,delta,soft):
                adjusted=Rotation.from_rotvec((desired_right@rig.frames['Right'][:,2])*math.radians(delta[3])).as_matrix()@desired_right
                center=grip+G.T@delta[:3]/rig.factor;frame=adjusted@rig.frames['Right'];rig.soft=soft
                ms=[rig.limb(candidate,rig.chains['Right'],center-adjusted@rig.grip['Right'],adjusted,G.T@np.array([.5,1.,-.4]),35.)]
                if two:
                    leftR=frame@rig.frames['Left'].T;leftcenter=center-frame[:,2]*(28/rig.factor)
                    ms.append(rig.limb(candidate,rig.chains['Left'],leftcenter-leftR@rig.grip['Left'],leftR,G.T@np.array([.5,-1.,-.4]),35.))
                rig.soft=False
                return ms
            def fit(delta):
                candidate={k:v.copy() for k,v in original.items()};ms=apply_frame(candidate,delta,True)
                return np.r_[[max(0.,m['wristBendDegrees']-29.)*8 for m in ms],[max(0.,abs(m['wristTwistDegrees'])-25.)*8 for m in ms],[m['reachClampCm']*1000 for m in ms],delta[:3]*.02,delta[3]*.002]
            lower=np.maximum([0. if two else -15.,-15.,-15.,-40.],previous_adjustment-[4.,4.,4.,8.]);upper=np.minimum([20.,15.,15.,40.],previous_adjustment+[4.,4.,4.,8.])
            adjustment=least_squares(fit,np.clip(previous_adjustment,lower+1e-7,upper-1e-7),bounds=(lower,upper),max_nfev=80,ftol=1e-5,xtol=1e-5,gtol=1e-5,diff_step=1e-3).x
            previous_adjustment=adjustment
            try:limbs.extend(apply_frame(pose,adjustment,False))
            except ValueError as exc:raise ValueError(f'{kind} two={two} t={t}: {exc}') from exc
        W=rig.world(pose);frame=W[right,:3,:3]@rig.frames['Right'];grip=W[right,:3,3]+W[right,:3,:3]@rig.grip['Right']
        for side in ['Right','Left']:
            W=rig.world(pose);hand=rig.chains[side][2];local=W[rig.g.parents[hand],:3,:3].T@W[hand,:3,:3];degrees=angle(rotation(rig.g.json['nodes'][hand]['rotation']).T@local)
            bend=math.degrees(math.acos(float(np.clip(unit(W[hand,:3,3]-W[rig.chains[side][1],:3,3])@(W[hand,:3,:3]@rig.palm_axes[hand]),-1,1))))
            if bend>35.10:raise ValueError(f'Interpolated {side} wrist bend exceeds bound at{t}: {bend}')
            limbs.append({'end':side+'Hand','wristFromReferenceDegrees':degrees,'wristBendDegrees':bend})
        metrics.append({'seconds':float(t),'rightGripGameCm':(G@grip*rig.factor).tolist(),'bladeDirectionGame':(G@frame[:,2]).tolist(),'limbs':limbs,'authoring':'smooth anatomical key poses plus exact foot/second-grip IK'})
        poses.append(pose)
    if isinstance(rig,WeightStanceRig) and not two:
        # Recovery is a lifted step, never a planted foot sliding backward.
        for pose,time in zip(poses,times):
            phase=float(time/duration)
            if phase>.66:
                world=rig.world(pose);foot=rig.legs['Left'][2];target=world[foot,:3,3]+G.T@np.array([0.,0.,8.*math.sin(math.pi*(phase-.66)/.34)])/rig.factor
                rig.limb(pose,rig.legs['Left'],target,world[foot,:3,:3],G.T@np.array([1.,-.25,0.]))
    rig.previous_elbows={};rig.previous_upper_rotations={}
    return poses,times,metrics


def roll_boat(rig,source):
    """Replace only the right limb rotations; retain every other original track."""
    if [n.get('name') for n in source.json['nodes']]!=[n.get('name') for n in rig.g.json['nodes']]:
        raise ValueError('Roll skeleton differs from canonical rig')
    duration=max(float(source.accessor(s['input']).max()) for s in source.json['animations'][0]['samplers'])
    if not .5<=duration<=1.2:raise ValueError('Unexpected accepted roll duration')
    times=np.linspace(0,duration,round(duration*60)+1);poses=[];rows=[];correction=np.zeros(4)
    upper,fore,hand=rig.chains['Right'];rig.previous_elbows={};rig.previous_upper_rotations={};rig.elbow_delta_degrees=18.
    for time in times:
        pose=sample(source,float(time));world=rig.world(pose);shoulder=G@world[upper,:3,3]*rig.factor
        lateral_weight=ease(time/.10)*(1-ease((time-.55)/(duration-.55)))
        tuck=ease((time-.27)/.05)*(1-ease((time-.46)/.04));carry_yaw=math.radians(30+30*tuck)
        lateral=np.array([-math.sin(carry_yaw),math.cos(carry_yaw),0.])
        direction=unit((1-lateral_weight)*np.array([.12,.32,.94])+lateral_weight*lateral)
        frame=rig.weapon_frame(direction);grip=shoulder+np.array([30.+15.*lateral_weight,45.,-30.*(1-lateral_weight)])
        grip[2]=max(50.,grip[2]);original=copy.deepcopy(pose)
        if poses:
            previous=rig.world(poses[-1]);rig.previous_elbows={hand:previous[fore,:3,3]};rig.previous_upper_rotations={upper:previous[upper,:3,:3]}
        def apply(candidate,delta,soft):
            axial=Rotation.from_rotvec(np.array([0.,0.,math.radians(delta[3])])).as_matrix()
            weapon=frame@axial;desired=weapon@rig.frames['Right'].T
            center=G.T@(grip+delta[:3])/rig.factor;target=center-desired@rig.grip['Right'];rig.soft=soft
            metric=rig.limb(candidate,[upper,fore,hand],target,desired,G.T@np.array([.5,1.,-.4]),45.)
            rig.soft=False
            return metric
        def residual(delta):
            metric=apply(copy.deepcopy(original),delta,True)
            return np.r_[max(0.,metric['wristBendDegrees']-29.)*8,max(0.,abs(metric['wristTwistDegrees'])-25.)*8,metric['reachClampCm']*1000,delta[:3]*.025,delta[3]*.002]
        low=np.array([-25.,max(-25.,(55.-grip[1])*tuck),max(-20.,50.-grip[2]),-720.]);high=np.array([25.,35.,25.,720.])
        fit=least_squares(residual,np.clip(correction,low+1e-7,high-1e-7),bounds=(low,high),max_nfev=120,diff_step=1e-3,ftol=1e-5,xtol=1e-5,gtol=1e-5)
        correction=fit.x;metric=apply(pose,correction,False);poses.append(pose)
        rows.append({'seconds':float(time),'rightLimb':metric,'palmGameCm':(grip+correction[:3]).tolist(),'weaponAxialRollDegrees':float(correction[3])})
    rig.previous_elbows={};rig.previous_upper_rotations={};rig.elbow_delta_degrees=12.
    unarmed,_=no_weapon(source,rig.mask);result=build(unarmed,poses,times,'RollBoat')
    original_animation=copy.deepcopy(unarmed.json['animations'][0]);new_animation=result.json['animations'][0];changed={upper,fore,hand}
    channels={(c['target']['node'],c['target']['path']):c for c in new_animation['channels']}
    for channel in original_animation['channels']:
        key=(channel['target']['node'],channel['target']['path'])
        if key[0] in changed and key[1]=='rotation':
            sampler=new_animation['samplers'][channels[key]['sampler']]
            channel['sampler']=len(original_animation['samplers']);original_animation['samplers'].append(copy.deepcopy(sampler))
    original_animation['name']='RollBoat';result.json['animations']=[original_animation]
    def track_digest(g):
        digest=hashlib.sha256();animation=g.json['animations'][0]
        for channel in animation['channels']:
            if channel['target']['node'] in changed and channel['target']['path']=='rotation':continue
            sampler=animation['samplers'][channel['sampler']]
            digest.update(json.dumps({'target':channel['target'],'interpolation':sampler.get('interpolation','LINEAR')},sort_keys=True).encode())
            digest.update(g.accessor(sampler['input']).tobytes());digest.update(g.accessor(sampler['output']).tobytes())
        return digest.hexdigest()
    original_digest=track_digest(source);output_digest=track_digest(result)
    if original_digest!=output_digest or result.binary[:len(source.binary)]!=source.binary:
        raise ValueError('Accepted non-right roll tracks or original binary changed')
    right_descendants=set(changed);pending=list(source.json['nodes'][hand].get('children',[]))
    while pending:
        node=pending.pop();right_descendants.add(node);pending.extend(source.json['nodes'][node].get('children',[]))
    untouched=[i for i in rig.skin if i not in right_descendants];right_indices=sorted(right_descendants)
    maximum_unchanged=0.;maximum_step=0.;previous=None
    for time in times:
        before=source.world_matrices(0,float(time));after=result.world_matrices(0,float(time))
        maximum_unchanged=max(maximum_unchanged,float(np.max(np.abs(before[untouched]-after[untouched]))))
        current=after[right_indices,:3,:3]
        if previous is not None:maximum_step=max(maximum_step,float(np.degrees(np.arccos(np.clip((np.sum(current*previous,axis=(1,2))-1)/2,-1,1))).max()))
        previous=current
    if maximum_unchanged>1e-10:raise ValueError('Accepted non-right roll world transforms changed')
    proof={'originalSourceSHA256':hashlib.sha256(source.bytes()).hexdigest(),'unchangedTrackSHA256':original_digest,'outputUnchangedTrackSHA256':output_digest,'onlyReplacedRotationNodes':[source.json['nodes'][n]['name'] for n in sorted(changed)],'originalBinaryPrefixPreserved':True,'maximumUnchangedWorldMatrixError':maximum_unchanged,'durationUnchangedSeconds':duration,'maximumRightWristBendDegrees':max(r['rightLimb']['wristBendDegrees'] for r in rows),'maximumRightWristTwistDegrees':max(abs(r['rightLimb']['wristTwistDegrees']) for r in rows),'maximumRightJointStepDegrees':maximum_step,'permittedTransientRightWristBendDegrees':45.,'notes':'Root, hips, torso, head, legs, left arm, right clavicle and all finger LOCAL tracks remain original. Inherited left-arm defects are not corrected by this scoped candidate.'}
    return result,times,rows,proof


def remaining_carry(rig,source,kind,donor):
    """Preserve body tracks; change only the explicitly scoped arm rotations."""
    if [n.get('name') for n in source.json['nodes']]!=[n.get('name') for n in rig.g.json['nodes']]:raise ValueError('Carry skeleton differs')
    duration=max(float(source.accessor(s['input']).max()) for s in source.json['animations'][0]['samplers'])
    times=np.linspace(0,duration,round(duration*60)+1)
    if kind=='Death':times=np.unique(np.r_[times,.3].astype('<f4')).astype(float)
    prefixes=['RightShoulder','RightArm','RightForeArm','RightHand']
    if kind=='Stagger':prefixes+=['LeftShoulder','LeftArm','LeftForeArm','LeftHand']
    changed={i for name,i in rig.names.items() if name.startswith(tuple(prefixes))};poses=[];hand=rig.names['RightHand'];extra={}
    if kind=='Death':
        raw_path=ASSETS/'knight-b-death-01-normalized-v1-rigid-sword-v1-in-place-v1-cloth-v1.glb';raw=CPU.GLB(raw_path)
        if raw.json['nodes']!=source.json['nodes']:raise ValueError('Natural death arm reference differs')
        opening={};finger_nodes=[]
        for label,fan in [('Index',.10),('Middle',0.),('Ring',-.05),('Pinky',-.10),('Thumb',.6)]:
            node=rig.names['RightHand'+label];chain=[node]
            while source.json['nodes'][node].get('children'):
                node=source.json['nodes'][node]['children'][0];chain.append(node)
            direction=rig.rest[hand,:3,:3]@unit(rig.palm_axes[hand]+fan*rig.frames['Right'][:,2]);last_rotation=None
            for node in chain:
                world=rig.world(opening);children=source.json['nodes'][node].get('children',[])
                if children:desired=align(world[node,:3,:3]@np.array(source.json['nodes'][children[0]]['translation']),direction)@world[node,:3,:3]
                elif last_rotation is not None:desired=last_rotation
                else:continue
                rig.set_world_rotation(opening,node,desired,world);reference=np.array(source.json['nodes'][node].get('rotation',[0,0,0,1]))
                degrees=angle(rotation(reference).T@rotation(opening[(node,'rotation')]))
                opening[(node,'rotation')]=CPU.slerp(reference,opening[(node,'rotation')],min(1.,(30. if label=='Thumb' else 45.)/max(degrees,1e-6)))
                last_rotation=rig.world(opening)[node,:3,:3];finger_nodes.append(node)
        extra={'runtimeReleaseRequired':True,'releaseSeconds':.30,'fingerReleaseSeconds':[.24,.44],'rightArmReturnToNaturalProviderSeconds':[.30,.70],'naturalArmSource':str(raw_path),'naturalArmSourceSHA256':sha(raw_path)}
    for time in times:
        pose=sample(source,float(time))
        if kind=='Death':
            natural=sample(raw,float(.1+time));weight=ease((time-.3)/.4);open_weight=ease((time-.24)/.20)
            for node in changed:
                target=natural[(node,'rotation')]
                if node==hand:target=np.array(source.json['nodes'][node].get('rotation',[0,0,0,1]))
                pose[(node,'rotation')]=CPU.slerp(donor[(node,'rotation')],opening[(node,'rotation')],open_weight) if node in finger_nodes else CPU.slerp(donor[(node,'rotation')],target,weight)
        else:
            for node in changed:pose[(node,'rotation')]=donor[(node,'rotation')].copy()
        poses.append(pose)
    unarmed,_=no_weapon(source,rig.mask);result=build(unarmed,poses,times,kind+'Boat');original_animation=copy.deepcopy(source.json['animations'][0]);new_animation=result.json['animations'][0]
    channels={(c['target']['node'],c['target']['path']):c for c in new_animation['channels']}
    for channel in original_animation['channels']:
        key=(channel['target']['node'],channel['target']['path'])
        if key[0] in changed and key[1]=='rotation':
            sampler=new_animation['samplers'][channels[key]['sampler']];channel['sampler']=len(original_animation['samplers']);original_animation['samplers'].append(copy.deepcopy(sampler))
    original_animation['name']=kind+'Boat';result.json['animations']=[original_animation]
    def digest_tracks(g):
        digest=hashlib.sha256();animation=g.json['animations'][0]
        for channel in animation['channels']:
            if channel['target']['node'] in changed and channel['target']['path']=='rotation':continue
            sampler=animation['samplers'][channel['sampler']];digest.update(json.dumps({'target':channel['target'],'interpolation':sampler.get('interpolation','LINEAR')},sort_keys=True).encode());digest.update(g.accessor(sampler['input']).tobytes());digest.update(g.accessor(sampler['output']).tobytes())
        return digest.hexdigest()
    before_digest=digest_tracks(source);after_digest=digest_tracks(result)
    if before_digest!=after_digest or result.binary[:len(source.binary)]!=source.binary:raise ValueError('Untouched carry tracks changed')
    untouched=[i for i in rig.skin if i not in changed];maximum_unchanged=0.;maximum_step=0.;previous=None;maximum_wrist=0.;maximum_twist=0.
    for time in times:
        before=source.world_matrices(0,float(time));after=result.world_matrices(0,float(time));maximum_unchanged=max(maximum_unchanged,float(np.max(np.abs(before[untouched]-after[untouched]))))
        current=after[sorted(changed),:3,:3]
        if previous is not None:maximum_step=max(maximum_step,float(np.degrees(np.arccos(np.clip((np.sum(current*previous,axis=(1,2))-1)/2,-1,1))).max()))
        previous=current
        for side in (['Right','Left'] if kind=='Stagger' else ['Right']):
            _,fore,end=rig.chains[side];bend=math.degrees(math.acos(float(np.clip(unit(after[end,:3,3]-after[fore,:3,3])@(after[end,:3,:3]@rig.palm_axes[end]),-1,1))));maximum_wrist=max(maximum_wrist,bend)
            local=after[rig.g.parents[end],:3,:3].T@after[end,:3,:3];reference=rotation(rig.g.json['nodes'][end]['rotation']);dq=quaternion(reference.T@local);maximum_twist=max(maximum_twist,abs(math.degrees(2*math.atan2(float(dq[:3]@rig.palm_axes[end]),abs(float(dq[3]))))))
    if maximum_unchanged>1e-10:raise ValueError('Source body world transforms changed')
    proof={'sourceSHA256':hashlib.sha256(source.bytes()).hexdigest(),'unchangedTrackSHA256':before_digest,'outputUnchangedTrackSHA256':after_digest,'maximumUnchangedWorldMatrixError':maximum_unchanged,'changedRotationNodes':[rig.g.json['nodes'][n]['name'] for n in sorted(changed)],'originalBinaryPrefixPreserved':True,'durationUnchangedSeconds':duration,'maximumChangedJointStepDegrees':maximum_step,'maximumCorrectedWristBendDegrees':maximum_wrist,'maximumCorrectedWristTwistDegrees':maximum_twist,**extra}
    if kind=='Death':
        world=result.world_matrices(0,.3);frame=world[hand,:3,:3]@rig.frames['Right'];grip=world[hand,:3,3]+world[hand,:3,:3]@rig.grip['Right'];proof['releaseGripFloorFrameCm']=(G@grip*rig.factor).tolist();proof['releaseWeaponActorRotationXYZW']=quaternion(G@frame).tolist()
    return result,times,proof


def audit_death_drop(rig,result,body_faces):
    """Match the agreed native component path; flat floor/body audit only."""
    hand=rig.names['RightHand'];world=result.world_matrices(0,.3);start_rotation=G@(world[hand,:3,:3]@rig.frames['Right']);start_position=G@(world[hand,:3,3]+world[hand,:3,:3]@rig.grip['Right'])*rig.factor
    end_rotation=np.array([[0.,0,1],[1.,0,0],[0,1.,0]]);vertices=rig.weapon_vertices*rig.factor;end_position=np.array([70.,250.,3.-(vertices@end_rotation.T)[:,2].min()]);rows=[]
    nodes={hand};pending=list(result.json['nodes'][hand].get('children',[]))
    while pending:
        node=pending.pop();nodes.add(node);pending.extend(result.json['nodes'][node].get('children',[]))
    slots=[i for i,n in enumerate(rig.skin) if n in nodes];hand_mask=np.all((np.where(np.isin(rig.J,slots),rig.weights,0).sum(1)>.5)[body_faces],axis=1)
    for time in np.linspace(.3,1.05,46):
        phase=float(np.clip((time-.3)/.72,0,1));rot=rotation(CPU.slerp(quaternion(start_rotation),quaternion(end_rotation),ease(phase)));origin=(1-phase)*start_position+phase*end_position+np.array([0.,0.,65.*math.sin(math.pi*phase)])
        wood=(vertices@rot.T+origin)@G/rig.factor;body=result.skinned_positions(0,float(time));world=result.world_matrices(0,float(time));grip=world[hand,:3,3]+world[hand,:3,:3]@rig.grip['Right']
        def release_contact(i,j,points):return time<=.44 and hand_mask[i] and np.max(np.linalg.norm(points-grip,axis=1))*rig.factor<=11.5
        hits=intersecting_triangle_pairs(body,body_faces,wood,rig.weapon_faces,64,release_contact)
        rows.append({'seconds':float(time),'intersectionPairs':len(hits),'minimumFloorCm':float(wood[:,1].min()*rig.factor)})
    return {'releaseSeconds':.3,'fallDurationSeconds':.72,'restForwardRightCm':[70.,250.],'upwardArcCm':65.,'rotation':'MakeFromZY(actorForward,worldUp); smoothstep quaternionSLERP','translation':'Linear phase plus65*sin(pi*phase)worldUp','finalFloorGapCm':3.,'scope':'Actual boat vs unchanged animated body and flat floor; native arena obstacles not audited','releaseGripFloorFrameCm':start_position.tolist(),'restGripFloorFrameCm':end_position.tolist(),'totalIntersectionPairs':sum(r['intersectionPairs'] for r in rows),'minimumFloorCm':min(r['minimumFloorCm'] for r in rows),'samples':rows}


def carry_heal(rig,source,donor):
    """Keep source body/head timing; route a left palm flask outside the armor."""
    if [n.get('name') for n in source.json['nodes']]!=[n.get('name') for n in rig.g.json['nodes']]:
        raise ValueError('Heal skeleton differs from canonical rig')
    duration=max(float(source.accessor(s['input']).max()) for s in source.json['animations'][0]['samplers'])
    if abs(duration-1.25)>1e-5:raise ValueError('Expected the accepted1.25s healing timing')
    times=np.linspace(0,duration,round(duration*60)+1);poses=[];rows=[];correction=np.zeros(4);previous_frame=None
    upper,fore,hand=rig.chains['Left'];head=rig.names['Head'];mouth_vertex=26616
    if rig.weights[mouth_vertex][rig.J[mouth_vertex]==rig.skin.index(head)].sum()<.8:
        raise ValueError('Reviewed helmet-front drinking landmark no longer belongs to Head')
    mouth_local=(np.linalg.inv(rig.rest[head])@np.r_[rig.g.skinned_positions()[mouth_vertex],1])[:3]
    length=24.;spout=rig.grip['Left']+rig.frames['Left'][:,2]*length/rig.factor
    right_nodes=[rig.names['RightShoulder']]+[i for name,i in rig.names.items() if name.startswith(('RightArm','RightForeArm','RightHand'))]
    start=np.array([10.,-60.,145.]);start_axis=unit([.15,0.,.989]);drink_offset=unit([20.,-8.,-10.])*length
    rig.previous_elbows={};rig.previous_upper_rotations={}
    for time in times:
        pose=sample(source,float(time));world=rig.world(pose)
        mouth=G@(world[head,:3,:3]@mouth_local+world[head,:3,3])*rig.factor;drink=mouth+drink_offset;contact_axis=-unit(drink_offset)
        controls=[(0.,start,start_axis),(.12,start,start_axis),(.28,np.array([50.,-55.,165.]),start_axis),(.5,drink,contact_axis),(.88,drink,contact_axis),(1.03,np.array([50.,-55.,165.]),start_axis),(duration,start,start_axis)]
        for before,after in zip(controls,controls[1:]):
            if before[0]-1e-9<=time<=after[0]+1e-9:
                weight=ease((time-before[0])/(after[0]-before[0]));target=(1-weight)*before[1]+weight*after[1];direction=unit((1-weight)*before[2]+weight*after[2]);break
        contact=ease((time-.28)/.22)*(1-ease((time-.88)/.15));new_axis=G.T@direction
        # Parallel transport avoids a heading singularity as the bottle passes
        # upright while tilting toward the helmet-front drinking landmark.
        frame=rig.weapon_frame(direction) if previous_frame is None else align(previous_frame[:,2],new_axis)@previous_frame
        previous_frame=frame.copy();original=copy.deepcopy(pose)
        if poses:
            previous=rig.world(poses[-1]);rig.previous_elbows={hand:previous[fore,:3,3]};rig.previous_upper_rotations={upper:previous[upper,:3,:3]}
        def apply(candidate,delta,soft):
            axial=Rotation.from_rotvec(np.array([0.,0.,math.radians(delta[3])])).as_matrix();desired=frame@axial@rig.frames['Left'].T
            center=G.T@(target+(1-contact)*delta[:3])/rig.factor;wrist=center-desired@rig.grip['Left'];rig.soft=soft
            metric=rig.limb(candidate,[upper,fore,hand],wrist,desired,G.T@np.array([.5,-1.,-.4]),35.);rig.soft=False
            return metric
        def residual(delta):
            metric=apply(copy.deepcopy(original),delta,True)
            return np.r_[max(0.,metric['wristBendDegrees']-29.)*8,max(0.,abs(metric['wristTwistDegrees'])-25.)*8,metric['reachClampCm']*1000,delta[:3]*.02,delta[3]*.001]
        lower=np.array([-12.,-12.,-12.,-720.]);upper_bound=np.array([12.,12.,12.,720.])
        fit=least_squares(residual,np.clip(correction,lower+1e-7,upper_bound-1e-7),bounds=(lower,upper_bound),max_nfev=100,ftol=1e-5,xtol=1e-5,gtol=1e-5)
        correction=fit.x;metric=apply(pose,correction,False)
        for node in right_nodes:pose[(node,'rotation')]=donor[(node,'rotation')].copy()
        for node in rig.fingers:
            if rig.g.json['nodes'][node]['name'].startswith('Left'):pose[(node,'rotation')]=np.array(rig.g.json['nodes'][node].get('rotation',[0,0,0,1]),float)
        poses.append(pose);rows.append({'seconds':float(time),'leftLimb':metric,'palmGameCm':(target+(1-contact)*correction[:3]).tolist(),'contactWeight':contact})
    rig.previous_elbows={};rig.previous_upper_rotations={}
    unarmed,_=no_weapon(source,rig.mask);result=build(unarmed,poses,times,'HealOneHand')
    changed=set(right_nodes+[i for name,i in rig.names.items() if name.startswith(('LeftArm','LeftForeArm','LeftHand'))])
    original_animation=copy.deepcopy(unarmed.json['animations'][0]);new_animation=result.json['animations'][0]
    channels={(c['target']['node'],c['target']['path']):c for c in new_animation['channels']}
    for channel in original_animation['channels']:
        key=(channel['target']['node'],channel['target']['path'])
        if key[0] in changed and key[1]=='rotation':
            sampler=new_animation['samplers'][channels[key]['sampler']];channel['sampler']=len(original_animation['samplers']);original_animation['samplers'].append(copy.deepcopy(sampler))
    original_animation['name']='HealOneHand';result.json['animations']=[original_animation]
    def body_digest(g):
        digest=hashlib.sha256();animation=g.json['animations'][0]
        for channel in animation['channels']:
            if channel['target']['node'] in changed and channel['target']['path']=='rotation':continue
            sampler=animation['samplers'][channel['sampler']]
            digest.update(json.dumps({'target':channel['target'],'interpolation':sampler.get('interpolation','LINEAR')},sort_keys=True).encode());digest.update(g.accessor(sampler['input']).tobytes());digest.update(g.accessor(sampler['output']).tobytes())
        return digest.hexdigest()
    before_digest=body_digest(source);after_digest=body_digest(result)
    if before_digest!=after_digest or result.binary[:len(source.binary)]!=source.binary:raise ValueError('Heal changed original body tracks or binary prefix')
    untouched=[i for i in rig.skin if i not in changed];maximum_unchanged=0.
    for time in times:
        before=source.world_matrices(0,float(time));after=result.world_matrices(0,float(time));maximum_unchanged=max(maximum_unchanged,float(np.max(np.abs(before[untouched]-after[untouched]))))
    if maximum_unchanged>1e-10:raise ValueError('Heal changed source body/head world transforms')
    world=result.world_matrices(0,.85);contact_error=float(np.linalg.norm(world[hand,:3,:3]@spout+world[hand,:3,3]-(world[head,:3,:3]@mouth_local+world[head,:3,3]))*rig.factor)
    if contact_error>.05:raise ValueError('Flask spout does not meet measured drinking target')
    proof={'sourceSHA256':hashlib.sha256(source.bytes()).hexdigest(),'unchangedBodyTrackSHA256':before_digest,'outputUnchangedBodyTrackSHA256':after_digest,'maximumUnchangedBodyMatrixError':maximum_unchanged,'changedRotationNodes':[rig.g.json['nodes'][n]['name'] for n in sorted(changed)],'originalBinaryPrefixPreserved':True,'durationSeconds':duration,'contactSeconds':.85,'flaskTargets':{'bone':'LeftHand','flask_grip':{'translation_cm':(S@rig.grip['Left']*100).tolist()},'flask_spout':{'translation_cm':(S@spout*100).tolist()},'lengthWorldCm':length,'measuredHelmetFrontVertex':mouth_vertex,'mouthTargetHeadLocalGLTF':mouth_local.tolist(),'contactErrorCm':contact_error},'leftGesturePolicy':'Original1.25s left-hand drinking gesture retained; both arm poses corrected, left lift/return rerouted outside armor. Source body/head/legs remain byte-identical.','samples':rows}
    return result,times,proof


def point_triangle_minimum(points,triangles):
    a=triangles[:,0];ab=triangles[:,1]-a;ac=triangles[:,2]-a;n=np.cross(ab,ac);n2=(n*n).sum(1)
    good=n2>1e-16;a=a[good];ab=ab[good];ac=ac[good];n=n[good];n2=n2[good]
    minimum=1.e10
    for p in points:
        ap=p-a;signed=(ap*n).sum(1);projection=ap-n*(signed/n2)[:,None]
        d00=(ab*ab).sum(1);d01=(ab*ac).sum(1);d11=(ac*ac).sum(1);d20=(projection*ab).sum(1);d21=(projection*ac).sum(1);den=d00*d11-d01*d01
        v=(d11*d20-d01*d21)/np.maximum(den,1e-16);w=(d00*d21-d01*d20)/np.maximum(den,1e-16)
        dist=np.where((v>=0)&(w>=0)&(v+w<=1),signed*signed/n2,np.inf)
        for start,end in [(a,a+ab),(a,a+ac),(a+ab,a+ac)]:
            edge=end-start;u=np.clip(((p-start)*edge).sum(1)/np.maximum((edge*edge).sum(1),1e-16),0,1);dist=np.minimum(dist,((p-start-u[:,None]*edge)**2).sum(1))
        minimum=min(minimum,float(dist.min()))
    return math.sqrt(minimum)



def intersecting_triangle_pairs(P,F,Q,H,limit=64,allow_contact=None):
    """Bounded BVH broad phase plus exact noncoplanar triangle edge tests."""
    A=P[F];B=Q[H]
    def tree(tris,ids):
        lo=tris[ids].min((0,1));hi=tris[ids].max((0,1))
        if len(ids)<=12:return lo,hi,ids,None
        center=tris[ids].mean(1);axis=int(np.argmax(hi-lo));order=ids[np.argsort(center[:,axis])];middle=len(order)//2
        return lo,hi,None,(tree(tris,order[:middle]),tree(tris,order[middle:]))
    stack=[(tree(A,np.arange(len(A))),tree(B,np.arange(len(B))))];hits=[]
    def edge_points(first,second):
        e1=second[1]-second[0];e2=second[2]-second[0];points=[]
        for start,end in zip(first,np.roll(first,-1,axis=0)):
            d=end-start;p=np.cross(d,e2);det=float(e1@p)
            if abs(det)<1e-12:continue
            t=start-second[0];u=float(t@p)/det;q=np.cross(t,e1);v=float(d@q)/det;along=float(e2@q)/det
            if -1e-7<=u<=1+1e-7 and -1e-7<=v and u+v<=1+1e-7 and 1e-7<along<1-1e-7:points.append(start+along*d)
        return points
    while stack and len(hits)<limit:
        a,b=stack.pop()
        if np.any(a[1]<b[0]-1e-8) or np.any(b[1]<a[0]-1e-8):continue
        if a[3] is not None:
            stack.extend((child,b) for child in a[3]);continue
        if b[3] is not None:
            stack.extend((a,child) for child in b[3]);continue
        for i in a[2]:
            lo=A[i].min(0);hi=A[i].max(0)
            for j in b[2]:
                if np.any(hi<B[j].min(0)) or np.any(B[j].max(0)<lo):continue
                points=edge_points(A[i],B[j])+edge_points(B[j],A[i])
                if points:
                    if allow_contact is not None and allow_contact(int(i),int(j),np.asarray(points)):continue
                    hits.append([int(i),int(j)])
                    if len(hits)>=limit:return hits
    return hits

def validate_clip(rig,result,times,metrics,body_faces,name,geometry_samples=17):
    core_names=['Hips','Spine','Spine1','Spine2','Neck','Head'];slots=[rig.skin.index(rig.names[n]) for n in core_names]
    core_weight=np.where(np.isin(rig.J,slots),rig.weights,0).sum(1);torso=body_faces[np.min(core_weight[body_faces],axis=1)>.45]
    if len(torso)<100:raise ValueError('Torso surface mask is insufficient')
    hands={side:ids[::max(1,len(ids)//120)] for side,ids in rig.hand_vertices.items()}
    grip_nodes=set()
    for side in ['Right','Left']:
        pending=[rig.chains[side][2]]
        while pending:
            n=pending.pop();grip_nodes.add(n);pending.extend(rig.g.json['nodes'][n].get('children',[]))
    grip_slots=[i for i,n in enumerate(rig.skin) if n in grip_nodes]
    grip_surfaces=np.where(np.isin(rig.J,grip_slots),rig.weights,0).sum(1)>.5
    contact_influence={};hand_contact_influence={}
    for side in ['Right','Left']:
        nodes={rig.chains[side][1],rig.chains[side][2]};pending=list(rig.g.json['nodes'][rig.chains[side][2]].get('children',[]))
        while pending:
            node=pending.pop();nodes.add(node);pending.extend(rig.g.json['nodes'][node].get('children',[]))
        slots=[i for i,n in enumerate(rig.skin) if n in nodes]
        dominant=np.where(np.isin(rig.J,slots),rig.weights,0).sum(1)>.5
        contact_influence[side]=np.all(dominant[body_faces],axis=1)
        hand_slots=[i for i,n in enumerate(rig.skin) if n in nodes and n!=rig.chains[side][1]]
        handdominant=np.where(np.isin(rig.J,hand_slots),rig.weights,0).sum(1)>.5
        hand_contact_influence[side]=np.all(handdominant[body_faces],axis=1)

    edges=[(p,n) for n,p in rig.g.parents.items() if p in rig.skin and n in rig.skin];lengths=np.array([np.linalg.norm(rig.rest[n,:3,3]-rig.rest[p,:3,3]) for p,n in edges]);rows=[];weapon_hits=0;minimum_weapon_floor=1e10;max_length=0.;max_wrist=0.;max_bend=0.;max_twist=0.;previous=None;max_step=0.;max_step_at=None;min_clearance=1e10;grip_error=0.
    for t in times:
        W=result.world_matrices(0,float(t));cur=np.array([np.linalg.norm(W[n,:3,3]-W[p,:3,3]) for p,n in edges]);max_length=max(max_length,float(np.abs(cur-lengths).max()*rig.factor))
        for side in ['Right','Left']:
            node=rig.chains[side][2];local=W[rig.g.parents[node],:3,:3].T@W[node,:3,:3];ref=rotation(rig.g.json['nodes'][node]['rotation']);max_wrist=max(max_wrist,angle(ref.T@local));palm=rig.palm_axes[node];fore=rig.chains[side][1];bend=math.degrees(math.acos(float(np.clip(unit(W[node,:3,3]-W[fore,:3,3])@(W[node,:3,:3]@palm),-1,1))));dq=quaternion(ref.T@local);twist=abs(math.degrees(2*math.atan2(float(dq[:3]@palm),abs(float(dq[3])))));max_bend=max(max_bend,bend);max_twist=max(max_twist,twist)
        rotations=W[rig.skin,:3,:3]
        if previous is not None:
            steps=np.degrees(np.arccos(np.clip((np.sum(rotations*previous,axis=(1,2))-1)/2,-1,1)));peak=int(np.argmax(steps))
            if steps[peak]>max_step:max_step=float(steps[peak]);max_step_at={'seconds':float(t),'bone':rig.g.json['nodes'][rig.skin[peak]]['name']}
        previous=rotations
    for t in np.linspace(0,float(times[-1]),geometry_samples):
        W=result.world_matrices(0,float(t));P=result.skinned_positions(0,float(t));row={'seconds':float(t),'handTorsoSurfaceClearanceCm':{}}
        for side,ids in hands.items():
            clearance=point_triangle_minimum(P[ids],P[torso])*rig.factor;min_clearance=min(min_clearance,clearance);row['handTorsoSurfaceClearanceCm'][side]=clearance
        hand=rig.chains['Right'][2];weapon=W[hand,:3,:3]@rig.frames['Right'];grip=W[hand,:3,3]+W[hand,:3,:3]@rig.grip['Right'];tip=grip+weapon@(rig.weapon_tip_cm/rig.factor);blade_base=grip+weapon@(rig.weapon_base_cm/rig.factor)
        row['gripGameCm']=(G@grip*rig.factor).tolist();row['tipGameCm']=(G@tip*rig.factor).tolist();row['actualBladeBaseGameCm']=(G@blade_base*rig.factor).tolist();row['actualTipFloorCm']=float(tip[1]*rig.factor)
        wood=rig.weapon_vertices@weapon.T+grip
        allowed=np.zeros(len(body_faces),dtype=bool);centers={}
        for side in (['Right','Left'] if 'TwoHand' in name else ['Right']):
            node=rig.chains[side][2];center=W[node,:3,3]+W[node,:3,:3]@rig.grip[side];centers[side]=center
            distance=np.max(np.linalg.norm(P[body_faces]-center,axis=2),axis=1)*rig.factor
            allowed|=((distance<=11.5)&hand_contact_influence[side])|((distance<=8.)&contact_influence[side])
        tested=np.flatnonzero(~allowed)
        def permitted_contact(i,j,points):
            original=int(tested[i])
            for side,center in centers.items():
                radius=11.5 if hand_contact_influence[side][original] else 8. if contact_influence[side][original] else 0.
                if radius and np.max(np.linalg.norm(points-center,axis=1))*rig.factor<=radius:return True
            return False
        hits=intersecting_triangle_pairs(P,body_faces[tested],wood,rig.weapon_faces,allow_contact=permitted_contact)
        weapon_hits+=len(hits);minimum_weapon_floor=min(minimum_weapon_floor,float(wood[:,1].min()*rig.factor))
        row['actualBoatNonHandBodyIntersectionPairs']=len(hits);row['actualBoatMinimumFloorCm']=float(wood[:,1].min()*rig.factor)

        if 'TwoHand' in name:
            left=rig.chains['Left'][2];left_grip=W[left,:3,3]+W[left,:3,:3]@rig.grip['Left'];error=float(np.linalg.norm(left_grip-(grip-weapon[:,2]*(28/rig.factor)))*rig.factor);grip_error=max(grip_error,error);row['secondGripErrorCm']=error
        rows.append(row)
    report={'actualBoatNonHandBodyIntersectionPairs':weapon_hits,'actualBoatMinimumFloorCm':minimum_weapon_floor,'actualBoatSHA256':sha(rig.weapon_path),'inMemoryWeaponTrialShiftCm':rig.weapon_trial_shift_cm.tolist(),'weaponCollisionScope':'Actual boat triangles vs body. Exact intersection points may contact active grip hand surfaces within11.5cm (measured source fist), or hand/forearm seam within8cm. Free hand, far forearm, head and torso remain tested','permittedGripHandRadiusCm':11.5,'permittedForearmSeamRadiusCm':8.,'maximumWristFromReferenceDegrees':max_wrist,'maximumPhysicalWristBendDegrees':max_bend,'maximumAxialWristTwistDegrees':max_twist,'physicalWristBendLimitDegrees':35.,'axialWristTwistLimitDegrees':30.,'maximumBoneLengthErrorCm':max_length,'maximumWorldJointStepDegreesAt60Hz':max_step,'maximumJointStepAt':max_step_at,'minimumSampledHandTorsoSurfaceClearanceCm':min_clearance,'maximumSecondGripErrorCm':grip_error,'clearanceScope':f'Actual skinned torso triangles vs up to~120 sampled surface vertices from exact hand components207/1646 at{geometry_samples}poses; not a full-volume self-collision proof','geometrySampleCount':geometry_samples,'minimumClearancePose':min(rows,key=lambda r:min(r['handTorsoSurfaceClearanceCm'].values())),'samples':rows}
    if name.startswith(('Idle','Guard')):
        beginning=result.world_matrices(0,0.);ending=result.world_matrices(0,float(times[-1]))
        report['loopSeamMaximumPositionCm']=float(np.linalg.norm(beginning[:,:3,3]-ending[:,:3,3],axis=1).max()*rig.factor)
        report['loopSeamMaximumAngleDegrees']=float(np.degrees(np.arccos(np.clip((np.sum(beginning[:,:3,:3]*ending[:,:3,:3],axis=(1,2))-1)/2,-1,1))).max())
    report['passed']=not (weapon_hits or minimum_weapon_floor<0 or max_bend>35.1 or max_twist>30.1 or max_length>.01 or grip_error>1.0 or min_clearance<2.5 or max_step>25. or report.get('loopSeamMaximumPositionCm',0)>.01 or report.get('loopSeamMaximumAngleDegrees',0)>.01)
    return report


def render_review(rig,result,time,path,title):
    from PIL import Image,ImageDraw,ImageFont
    P=result.skinned_positions(0,time)*rig.factor;n=result.json['nodes'][result.mesh_node()];p=result.json['meshes'][n['mesh']]['primitives'][0];faces=result.accessor(p['indices']).reshape(-1,3);hand_faces=np.all(np.isin(faces,np.r_[rig.hand_vertices['Right'],rig.hand_vertices['Left']]),axis=1)
    image=Image.new('RGB',(1400,850),(237,240,243));draw=ImageDraw.Draw(image);font=ImageFont.load_default(size=18)
    draw.text((18,15),title,fill=(25,35,45),font=font);draw.text((18,40),'Actual body and normalized Tripo boat geometry; flat diagnostic colors; blue = left grip. Native review pending.',fill=(55,65,75),font=ImageFont.load_default(size=14))
    W=result.world_matrices(0,time);hand=rig.chains['Right'][2];frame=W[hand,:3,:3]@rig.frames['Right'];grip=W[hand,:3,3]+W[hand,:3,:3]@rig.grip['Right'];line=np.array([grip-frame[:,2]*(28/rig.factor),grip,grip+frame@(rig.weapon_tip_cm/rig.factor)])*rig.factor
    wood=rig.weapon_vertices@(W[hand,:3,:3]@rig.frames['Right']).T+grip;wood*=rig.factor
    wood_faces=rig.weapon_faces+len(P);wood_mask=np.r_[np.zeros(len(faces),bool),np.ones(len(wood_faces),bool)]
    P=np.vstack([P,wood]);faces=np.vstack([faces,wood_faces]);hand_faces=np.r_[hand_faces,np.zeros(len(wood_faces),bool)]
    light=unit([.4,.8,.5]);norm=np.cross(P[faces[:,1]]-P[faces[:,0]],P[faces[:,2]]-P[faces[:,0]]);shade=.35+.65*abs(norm@light)/np.maximum(np.linalg.norm(norm,axis=1),1e-12)
    low=min(-10,float(P[np.unique(faces),1].min())-5,float(line[:,1].min())-5);high=max(260,float(line[:,1].max())+5);scale=min(2.5,700/(high-low),630/max(float(np.ptp(P[:,0])),float(np.ptp(P[:,2])),1.))
    for panel,(label,axis,depthsign) in enumerate([('FRONT',0,1),('SIDE',2,-1)]):
        u=P[:,axis];depths=P[:,2] if axis==0 else -P[:,0];center=(u.min()+u.max())*.5;uv=np.c_[340+(u-center)*scale,25+(high-P[:,1])*scale];rgb=np.full((750,680,3),[237,240,243],np.uint8);z=np.full((750,680),-np.inf)
        for fi,f in enumerate(faces):
            tr=uv[f];xmin=max(0,int(np.floor(tr[:,0].min())));xmax=min(679,int(np.ceil(tr[:,0].max())));ymin=max(0,int(np.floor(tr[:,1].min())));ymax=min(749,int(np.ceil(tr[:,1].max())));x0,y0=tr[0];x1,y1=tr[1];x2,y2=tr[2];den=(y1-y2)*(x0-x2)+(x2-x1)*(y0-y2)
            if abs(den)<1e-9 or xmin>xmax or ymin>ymax:continue
            X,Y=np.meshgrid(np.arange(xmin,xmax+1)+.5,np.arange(ymin,ymax+1)+.5);a=((y1-y2)*(X-x2)+(x2-x1)*(Y-y2))/den;b=((y2-y0)*(X-x2)+(x0-x2)*(Y-y2))/den;c=1-a-b;d=a*depths[f[0]]+b*depths[f[1]]+c*depths[f[2]];patch=z[ymin:ymax+1,xmin:xmax+1];mask=(a>=0)&(b>=0)&(c>=0)&(d>patch);rgb[ymin:ymax+1,xmin:xmax+1][mask]=np.array([110,74,43] if wood_mask[fi] else [180,104,80] if hand_faces[fi] else [165,175,186])*shade[fi];patch[mask]=d[mask]
        panel_image=Image.fromarray(rgb);pd=ImageDraw.Draw(panel_image);points=[(340+(v[axis]-center)*scale,25+(high-v[1])*scale) for v in line];pd.line(points,fill=(222,120,20),width=4);pd.ellipse((points[0][0]-5,points[0][1]-5,points[0][0]+5,points[0][1]+5),fill=(40,120,220));pd.text((12,5),label,fill=(30,40,50),font=font);pd.line((0,25+high*scale,679,25+high*scale),fill=(110,115,120));image.paste(panel_image,(10+panel*700,80))
    image.save(path);os.chmod(path,0o600)

def write(path,data):
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as f:f.write(data)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=OUT/'candidate-v1');parser.add_argument('--clips',nargs='*',choices=['IdleOneHand','IdleTwoHand','LightAttackOneHand','HeavyAttackOneHand','LightAttackTwoHand','HeavyAttackTwoHand','HealOneHand','RollBoat','GuardOneHand','GuardTwoHand','JumpBoat','StaggerBoat','DeathBoat']);parser.add_argument('--weapon',type=Path,required=True);parser.add_argument('--weapon-shift-cm',type=float,nargs=3,default=[0.,0.,0.]);parser.add_argument('--stance-version',type=int,choices=[1,2],default=1);args=parser.parse_args();dest=args.output.resolve()
    if not dest.is_relative_to(OUT.resolve()) or dest.exists():raise ValueError('Use fresh owned output directory')
    receipt=ROOT/'Local/CustomuseImports/20261018T235418Z-840a3151.json';imported=json.loads(receipt.read_text())
    if not imported.get('success') or '/KnightB/v012/' not in imported.get('definition',''):raise ValueError('Active v012 import receipt missing')
    plan=json.loads((ASSETS/'import-knight-v012.json').read_text());source=local_input(imported['sourceFile']);g=CPU.GLB(source)
    if sha(source)!=imported['sourceSHA256']:raise ValueError('Active rig source hash mismatch')
    sources={c['name']:local_input(c['file']) for c in plan['clips']};mask=json.loads((ASSETS/'weapon-topology-v1/candidate-mask.json').read_text());rig=(WeightStanceRig if args.stance_version==2 else Rig)(g,CPU.GLB(sources['Idle']),mask,args.weapon,args.weapon_shift_cm)
    if args.stance_version==2 and args.clips and any(c in args.clips for c in ['HealOneHand','RollBoat','JumpBoat','StaggerBoat','DeathBoat']):raise ValueError('Version2 applies to stance/attack/guard only; retain reviewed auxiliary clips')
    unarmed,body_faces=no_weapon(g,mask);dest.mkdir(parents=True,mode=0o700)
    write(dest/'generator-source.py',SOURCE_SNAPSHOT)
    body=CPU.GLB(unarmed.bytes());body.json.pop('animations',None);write(dest/'KnightBody.glb',body.bytes())
    roll=CPU.GLB(sources['Roll']);roll_body,_=no_weapon(roll,mask)
    if roll_body.json['animations']!=roll.json['animations'] or roll_body.binary[:len(roll.binary)]!=roll.binary:raise ValueError('Accepted Roll changed')
    write(dest/'Roll.glb',roll_body.bytes())
    outputs=[]
    for two,kind,duration in [(False,'Idle',4.),(True,'Idle',4.),(False,'Light',.66),(False,'Heavy',.90),(True,'Light',.90),(True,'Heavy',1.20),(False,'Guard',4.),(True,'Guard',4.)]:
        name=(kind if kind in ('Idle','Guard') else kind+'Attack')+('TwoHand' if two else 'OneHand')
        if args.clips and name not in args.clips:continue
        rig.correction=np.zeros(4)
        if args.stance_version==2 and two and kind=='Light':
            # Same cleared two-hand sweep, shorter anticipation and contact at.46.
            poses,source_times,metrics=sequence(rig,1.2,True,'Heavy')
            times=np.interp(source_times/1.2,[0.,.3,.64/1.2,.68,.86,1.],[0.,.24,.46/.9,.68,.86,1.])*.9
            for metric,time in zip(metrics,times):metric['seconds']=float(time)
        else:poses,times,metrics=sequence(rig,duration,two,'Light' if kind=='Heavy' and not two else kind)
        result=build(unarmed,poses,times,name);qa=validate_clip(rig,result,times,metrics,body_faces,name);path=dest/(name+'.glb');write(path,result.bytes());render_review(rig,result,duration*.5,dest/(name+'-review.png'),name+' midpoint');row={'name':name,'runtimeName':name.replace('OneHand','') if not two else name,'contactSeconds':None if kind in ('Idle','Guard') else ((.46 if kind=='Light' else .64) if two else (.33 if kind=='Light' else .45)),'activeWindowSeconds':None if kind in ('Idle','Guard') else ([.34,.60] if two and kind=='Light' else [.48,.81] if two else [.25,.43] if kind=='Light' else [.34,.59]),'authoringNote':'One-hand heavy intentionally uses the cleared whole-body diagonal cut with longer timing' if kind=='Heavy' and not two else 'Original constrained stance/motion','file':str(path),'sha256':sha(path),'durationSeconds':duration,'loop':kind in ('Idle','Guard'),'qa':qa,'maximumWristDegrees':max(m['wristFromReferenceDegrees'] for r in metrics for m in r['limbs']),'samples':metrics};outputs.append(row);write(dest/(name+'.json'),(json.dumps(row,indent=2)+'\n').encode());print(name,'ready' if qa['passed'] else 'REJECTED',json.dumps({k:v for k,v in qa.items() if k not in ['samples','minimumClearancePose']}),flush=True)
        if not qa['passed']:
            bad=max(qa['samples'],key=lambda r:r['actualBoatNonHandBodyIntersectionPairs'])
            render_review(rig,result,bad['seconds'],dest/(name+'-rejected.png'),name+' rejected at '+str(bad['seconds']))
    if args.clips and 'HealOneHand' in args.clips:
        rig.previous_elbows={};rig.previous_upper_rotations={};rig.correction=np.zeros(4)
        donor,_=rig.pose(0.,4.,False,'Idle');result,times,proof=carry_heal(rig,CPU.GLB(sources['Heal']),donor)
        qa=validate_clip(rig,result,times,[],body_faces,'HealOneHand',geometry_samples=len(times));path=dest/'HealOneHand.glb';write(path,result.bytes());render_review(rig,result,.65,dest/'HealOneHand-review.png','Heal: original left flask gesture + corrected right carry')
        row={'name':'HealOneHand','runtimeName':'Heal','contactSeconds':.85,'file':str(path),'sha256':sha(path),'durationSeconds':float(times[-1]),'loop':False,'qa':qa,'preservationProof':proof};outputs.append(row);write(dest/'HealOneHand.json',(json.dumps(row,indent=2)+'\n').encode());print('HealOneHand','ready' if qa['passed'] else 'REJECTED',json.dumps({k:v for k,v in qa.items() if k not in ['samples','minimumClearancePose']}),flush=True)
    if args.clips and 'RollBoat' in args.clips:
        result,times,metrics,proof=roll_boat(rig,CPU.GLB(sources['Roll']));diagnostics=validate_clip(rig,result,times,[],body_faces,'RollBoat',geometry_samples=2*len(times)-1)
        scoped=diagnostics['actualBoatNonHandBodyIntersectionPairs']==0 and diagnostics['actualBoatMinimumFloorCm']>=0 and proof['maximumRightWristBendDegrees']<=45.1 and proof['maximumRightWristTwistDegrees']<=30.1 and proof['maximumRightJointStepDegrees']<=30.
        qa={'passed':scoped,'scope':'Right carry and boat only; original body and left arm tracks explicitly preserved','preservationProof':proof,'fullBodyDiagnosticsIncludingInheritedDefects':diagnostics}
        path=dest/'RollBoat.glb';write(path,result.bytes());render_review(rig,result,.3,dest/'RollBoat-review.png','RollBoat: unchanged body/timing; scoped right carry')
        row={'name':'RollBoat','runtimeName':'Roll','file':str(path),'sha256':sha(path),'durationSeconds':float(times[-1]),'loop':False,'qa':qa,'samples':metrics};outputs.append(row);write(dest/'RollBoat.json',(json.dumps(row,indent=2)+'\n').encode());print('RollBoat','ready' if scoped else 'REJECTED',json.dumps(proof),flush=True)
    for kind in ['Jump','Stagger','Death']:
        name=kind+'Boat'
        if not args.clips or name not in args.clips:continue
        rig.previous_elbows={};rig.previous_upper_rotations={};rig.correction=np.zeros(4);donor,_=rig.pose(0.,4.,False,'Idle')
        result,times,proof=remaining_carry(rig,CPU.GLB(sources[kind]),kind,donor)
        held_times=np.linspace(0,.3,19) if kind=='Death' else times
        diagnostics=validate_clip(rig,result,held_times,[],body_faces,name,geometry_samples=len(held_times))
        scoped=diagnostics['actualBoatNonHandBodyIntersectionPairs']==0 and diagnostics['actualBoatMinimumFloorCm']>=0 and proof['maximumCorrectedWristBendDegrees']<=35.1 and proof['maximumCorrectedWristTwistDegrees']<=30.1
        drop=audit_death_drop(rig,result,body_faces) if kind=='Death' else None
        if drop:scoped=scoped and drop['totalIntersectionPairs']==0 and drop['minimumFloorCm']>=0
        if kind!='Death':scoped=scoped and diagnostics['minimumSampledHandTorsoSurfaceClearanceCm']>=2.5
        qa={'passed':bool(scoped),'scope':'Changed arms/weapon only; source body tracks preserved','preservationProof':proof,'fullBodyDiagnosticsIncludingInheritedMotion':diagnostics,'runtimeDeathDropAudit':drop}
        path=dest/(name+'.glb');write(path,result.bytes());render_review(rig,result,.3 if kind=='Death' else float(times[-1])*.5,dest/(name+'-review.png'),name+' scoped carry; original body preserved')
        row={'name':name,'runtimeName':kind,'file':str(path),'sha256':sha(path),'durationSeconds':float(times[-1]),'loop':False,'qa':qa};outputs.append(row);write(dest/(name+'.json'),(json.dumps(row,indent=2)+'\n').encode());print(name,'ready' if scoped else 'REJECTED',json.dumps(proof),flush=True)
    manifest={'stanceVersion':args.stance_version,'status':'OFFLINE_CANDIDATES_NATIVE_VISUAL_REVIEW_REQUIRED' if all(c['qa']['passed'] for c in outputs) else 'REJECTED_NATIVE_IMPORT_BLOCKED','sourceScriptSHA256':SOURCE_SHA256,'sourceSnapshot':str(dest/'generator-source.py'),'selectedClips':args.clips,'weaponFile':str(rig.weapon_path),'weaponSHA256':sha(rig.weapon_path),'weaponInMemoryShiftCm':rig.weapon_trial_shift_cm.tolist(),'sourceImportReceipt':str(receipt),'sourceRigSHA256':sha(source),'acceptedRollSourceSHA256':sha(sources['Roll']),'preservedOriginalRollCopy':{'file':str(dest/'Roll.glb'),'animationAndOriginalBinaryUnchanged':True},'removedWeaponComponent':196,'removedTriangles':len(mask['triangleIndices']),'allOriginalBodyAttributesWeightsBindNodesPreserved':True,'worldCmPerSourceUnit':rig.factor,'weaponConvention':{'bladeAxis':'+Z','guardAxis':'+X','rightGripCm':[0,0,0],'leftGripCm':[0,0,-28],'actualBladeBaseUECm':rig.weapon_base_cm.tolist(),'actualBladeTipUECm':rig.weapon_tip_cm.tolist(),'weaponFinalWorldScale':[1,1,1]},'rightGripImportedBoneLocal':{'translationCm':(S@rig.grip['Right']*100).tolist(),'rotationQuaternionXYZW':quaternion(S@rig.frames['Right']).tolist()},'leftGripImportedBoneLocal':{'translationCm':(S@rig.grip['Left']*100).tolist(),'rotationQuaternionXYZW':quaternion(S@rig.frames['Left']).tolist()},'clips':outputs,'nativeAccepted':False}
    write(dest/'manifest.json',(json.dumps(manifest,indent=2)+'\n').encode());print(dest/'manifest.json',flush=True)
    if not all(c['qa']['passed'] for c in outputs):raise SystemExit(2)


if __name__=='__main__':main()
