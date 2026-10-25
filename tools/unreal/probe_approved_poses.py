"""Native deterministic sampling proof for all imported clips and mesh transitions.

Runs in the owned editor using transient native game actors. This is an asset
sampling check, not a gameplay/playability or aesthetic acceptance claim.
"""
from pathlib import Path
import json,math
import unreal
ROOT=Path(__file__).resolve().parents[2]

def transform_data(t):
 return {'translation':[t.translation.x,t.translation.y,t.translation.z],
         'rotation':[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w],
         'scale':[t.scale3d.x,t.scale3d.y,t.scale3d.z]}

def run(plan):
 character=plan['character'];definition_path=f"/Game/Characters/Customuse/{character}/{plan['version']}/DA_{character}"
 definition=unreal.load_asset(definition_path)
 if not isinstance(definition,unreal.VeyrVisualDefinition):raise RuntimeError('Missing native definition')
 cls=unreal.VeyrKnight if character=='KnightB' else unreal.VeyrDragon
 actor=unreal.EditorLevelLibrary.spawn_actor_from_class(cls,unreal.Vector(0,0,0),unreal.Rotator(),True)
 if not actor:raise RuntimeError('Could not create transient native sampling actor')
 receipt={'character':character,'definition':definition_path,'samples':[],'transitions':[],'failures':[]}
 out=ROOT/'Local/CustomuseImports'/('native-pose-proof-'+character+'-'+plan['version']+'.json')
 try:
  actor.set_actor_tick_enabled(False);actor.set_is_temporarily_hidden_in_editor(True)
  presentation=actor.get_editor_property('imported_presentation')
  if not presentation.set_visual_definition(definition,False):raise RuntimeError(str(presentation.get_editor_property('last_error')))
  clips=definition.get_editor_property('clips');names=list(clips)
  all_morphs=[str(x) for x in definition.get_imported_morph_target_names()]
  def snapshot():
   return ({str(b):transform_data(v) for b,v in presentation.get_evaluated_local_pose().items()},
           {m:presentation.get_anim_instance().get_curve_value(m) for m in all_morphs})
  def difference(a,b):
   if set(a[0])!=set(b[0]):return float('inf')
   error=max(abs(x-y) for key in a[0] for field in ('translation','rotation','scale') for x,y in zip(a[0][key][field],b[0][key][field]))
   return max(error,max((abs(a[1][key]-b[1][key]) for key in all_morphs),default=0.))
  for name,clip in clips.items():
   end=clip.end_seconds if clip.end_seconds>=0 else clip.sequence.get_play_length();duration=end-clip.start_seconds
   morphs=[str(x) for x in definition.get_imported_morph_target_names(name)]
   for phase in [0.,.17,.37,.63,.83,.999]:
    t=duration*phase
    if not presentation.sample_clip_time(name,t):
     receipt['failures'].append({'clip':str(name),'time':t,'error':str(presentation.get_editor_property('last_error'))});continue
    pose={str(b):transform_data(v) for b,v in presentation.get_evaluated_local_pose().items()}
    instance=presentation.get_anim_instance()
    curves={m:instance.get_curve_value(m) for m in morphs}
    receipt['samples'].append({'clip':str(name),'time':t,'sequenceSeconds':float(presentation.get_editor_property('current_sequence_seconds')),'mesh':presentation.get_skeletal_mesh_asset().get_path_name(),'pose':pose,'morphCurves':curves})
   # All mesh variants must permit a frozen-source blend without resetting animation.
   other=names[(names.index(name)+1)%len(names)]
   if not presentation.sample_clip_time(name,duration*.4) or not presentation.begin_transition():
    receipt['failures'].append({'clip':str(name),'error':'Cannot capture native transition source'});continue
   frozen_source=snapshot()
   for alpha in [0.,.5,1.]:
    good=presentation.sample_clip_time_blended(other,.1,alpha)
    receipt['transitions'].append({'from':str(name),'to':str(other),'alpha':alpha,'passed':bool(good)})
    if not good:receipt['failures'].append({'clip':str(name),'to':str(other),'error':str(presentation.get_editor_property('last_error'))})
    elif alpha==0.:
     error=difference(frozen_source,snapshot());receipt['transitions'][-1]['endpointError']=error
     if error>.0001:receipt['failures'].append({'clip':str(name),'to':str(other),'error':'Frozen-source endpoint mismatch','value':error})
    elif alpha==1.:
     blended=snapshot();presentation.sample_clip_time(other,.1);error=difference(blended,snapshot());receipt['transitions'][-1]['endpointError']=error
     if error>.0001:receipt['failures'].append({'clip':str(name),'to':str(other),'error':'Destination endpoint mismatch','value':error})
  receipt['successfulPoseEvaluations']=presentation.get_editor_property('successful_pose_evaluations')
  receipt['failedRequests']=presentation.get_editor_property('failed_requests')
 finally:
  unreal.EditorLevelLibrary.destroy_actor(actor)
  receipt['passed']=not receipt['failures']
  out.write_text(json.dumps(receipt,indent=2)+'\n')
 if receipt['failures']:raise RuntimeError('Native pose/transition checks failed; inspect '+str(out))
 return {'definition':definition_path,'report':str(out),'passed':True,'samples':len(receipt['samples'])}
