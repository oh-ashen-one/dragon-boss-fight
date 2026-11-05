"""Read-only native transition probe; run as PythonScriptCommandlet -nullrhi.

Checks exact endpoints, non-turn regressions and limb lengths. Intermediate
foot paths are diagnostics, not gameplay contact or visible quality acceptance.
"""
import json
import math
from pathlib import Path

import unreal

ROOT=Path(__file__).resolve().parents[2]
assert Path(unreal.Paths.project_dir()).resolve()==ROOT/'Unreal/Veyr'
assert '-nullrhi' in unreal.SystemLibrary.get_command_line().lower()
unreal.EditorLoadingAndSavingUtils.load_map('/Game/Maps/VeyrArena')
definition=unreal.load_asset('/Game/Characters/Customuse/RuntimePolish/DA_Knight')
assert definition
actor=unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.VeyrKnight,unreal.Vector(),unreal.Rotator(),True)
assert actor
out=ROOT/'Local/Fortress20261103/native-turn-root-blend-proof.json'
report={'success':False,'readOnly':True,'qualityAccepted':False,'cases':[]}


def flatten(t):
    return [t.translation.x,t.translation.y,t.translation.z,t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w,
            t.scale3d.x,t.scale3d.y,t.scale3d.z]


def vec(v):return [v.x,v.y,v.z]
def dist(a,b):return math.sqrt(sum((x-y)**2 for x,y in zip(a,b)))


try:
    actor.set_actor_tick_enabled(False)
    actor.set_is_temporarily_hidden_in_editor(True)
    presentation=actor.get_editor_property('imported_presentation')
    presentation.set_editor_property('prefer_canonical_mesh',True)
    assert presentation.set_visual_definition(definition,False)
    clips=definition.get_editor_property('clips')
    def duration(name):
        c=clips[name];return (c.end_seconds if c.end_seconds>=0 else c.sequence.get_play_length())-c.start_seconds
    cases=[('turn_exit','TurnRight180TwoHand',1.,'RunTwoHandPlanted',.55,True),
           ('turn_entry','IdleTwoHand',.3,'TurnRight180TwoHand',.1,True),
           ('run_stop','RunTwoHandPlanted',.55,'RunStopTwoHandSourced',.05,False),
           ('onehand_start','Idle',.3,'RunOneHandPlanted',.55,False),
           ('heavy_exit','HeavyAttackTwoHandSourced',.99,'IdleTwoHand',.2,False)]
    for name,source,source_phase,target,target_phase,is_turn in cases:
        trial={'name':name,'source':source,'target':target,'rootTurnCase':is_turn,'variants':{}}
        source_time=duration(source)*source_phase;target_time=duration(target)*target_phase
        for enabled in [False,True]:
            presentation.set_editor_property('root_space_blend',enabled)
            assert presentation.sample_clip_time(source,source_time)
            initial={str(k):flatten(v) for k,v in presentation.get_evaluated_local_pose().items()}
            assert presentation.begin_transition()
            samples=[]
            for i in range(51):
                alpha=i/50
                assert presentation.sample_clip_time_blended(target,target_time,alpha),str(presentation.get_editor_property('last_error'))
                local={str(k):flatten(v) for k,v in presentation.get_evaluated_local_pose().items()}
                if i==0:
                    error=max(abs(x-y) for k in initial for x,y in zip(initial[k],local[k]))
                    assert error<.0001, 'Frozen endpoint changed'
                world={k:vec(presentation.get_socket_location(k)) for k in local}
                lengths={side+segment:dist(world[side+a],world[side+b])
                         for side in ['Left','Right'] for segment,a,b in [('Thigh','UpLeg','Leg'),('Shin','Leg','Foot')]}
                samples.append({'alpha':alpha,'positions':world,'lengths':lengths})
            final=local
            assert presentation.sample_clip_time(target,target_time)
            exact={str(k):flatten(v) for k,v in presentation.get_evaluated_local_pose().items()}
            assert max(abs(x-y) for k in exact for x,y in zip(exact[k],final[k]))<.0001,'Target endpoint changed'
            stretch=max(max(0.,value-max(samples[0]['lengths'][k],samples[-1]['lengths'][k]),
                            min(samples[0]['lengths'][k],samples[-1]['lengths'][k])-value)
                        for s in samples for k,value in s['lengths'].items())
            assert stretch<.05,'Transition stretched a leg link'
            paths={}
            for bone in ['LeftToeBase','RightToeBase','LeftFoot','RightFoot']:
                a,b=samples[0]['positions'][bone],samples[-1]['positions'][bone]
                deviations=[dist(s['positions'][bone],[x*(1-s['alpha'])+y*s['alpha'] for x,y in zip(a,b)]) for s in samples]
                paths[bone]={'maximumDeviationFromEndpointLineCm':max(deviations),
                             'pathLengthCm':sum(dist(a['positions'][bone],b['positions'][bone]) for a,b in zip(samples,samples[1:]))}
            trial['variants']['rebased' if enabled else 'baseline']={'endpointsExact':True,'maximumLegLengthExcessCm':stretch,
                                                                     'footPaths':paths,'samples':samples}
        if not is_turn:
            a,b=trial['variants']['baseline']['samples'],trial['variants']['rebased']['samples']
            error=max(dist(x['positions'][k],y['positions'][k]) for x,y in zip(a,b) for k in x['positions'] if k!='VeyrRoot')
            trial['nonTurnMaximumWorldPositionDifferenceCm']=error
            assert error<.1,'Non-turn body/helper blend changed'
        report['cases'].append(trial)
    report['success']=True
finally:
    unreal.EditorLevelLibrary.destroy_actor(actor)
    out.write_text(json.dumps(report,indent=2)+'\n')
unreal.log('VEYR_TURN_ROOT_BLEND_PROOF_COMPLETE')
