"""Independently sample authored grip targets for an existing native replay.

CPU-only and read-only. Uses a separate native component and unblended assets,
not the gameplay grip-interpolation variables being checked.
"""
import hashlib
import json
import os
from pathlib import Path

import unreal

ROOT=Path(__file__).resolve().parents[2]
assert '-nullrhi' in unreal.SystemLibrary.get_command_line().lower()
assert Path(unreal.Paths.project_dir()).resolve()==ROOT/'Unreal/Veyr'
job_path=Path(os.environ['VEYR_GRIP_REFERENCE_JOB']).resolve()
assert job_path.is_relative_to(ROOT/'Local')
job=json.loads(job_path.read_text());frames_path=Path(job['frames']).resolve();out=Path(job['output']).resolve()
assert frames_path.is_relative_to(ROOT/'Evidence') and out.is_relative_to(ROOT/'Local') and not out.exists()
assert hashlib.sha256(frames_path.read_bytes()).hexdigest()==job['framesSHA256']
frames=[json.loads(l) for l in frames_path.read_text().splitlines()]
requests={(r['clip'],r['clipPhase']) for r in frames if r['blending']}
unreal.EditorLoadingAndSavingUtils.load_map('/Game/Maps/VeyrArena')
definition=unreal.load_asset('/Game/Characters/Customuse/RuntimePolish/DA_Knight')
assert unreal.EditorAssetLibrary.get_metadata_tag(definition,'VeyrPolishSourceDefinition')=='/Game/Characters/Customuse/KnightB/v045turns/DA_KnightB'
actor=unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.VeyrKnight,unreal.Vector(),unreal.Rotator(),True)
assert actor
report={'success':False,'framesSHA256':job['framesSHA256'],'referenceMode':'independent unblended native assets','references':[]}
try:
    actor.set_actor_tick_enabled(False);actor.set_is_temporarily_hidden_in_editor(True)
    p=actor.get_editor_property('imported_presentation');p.set_editor_property('prefer_canonical_mesh',True)
    p.set_editor_property('root_space_blend',False)
    assert p.set_visual_definition(definition,False)
    assert p.get_bone_index('RightHand')>=0 and p.get_bone_index('WeaponSocket')>=0
    clips=definition.get_editor_property('clips')
    for name,phase in sorted(requests):
        c=clips[name];duration=(c.end_seconds if c.end_seconds>=0 else c.sequence.get_play_length())-c.start_seconds
        assert p.sample_clip_time(name,float(phase)*duration),str(p.get_editor_property('last_error'))
        hand=p.get_socket_transform('RightHand');socket=p.get_socket_transform('WeaponSocket')
        report['references'].append({'clip':name,'phase':phase,
            'hand':[hand.translation.x,hand.translation.y,hand.translation.z],
            'handQuaternion':[hand.rotation.x,hand.rotation.y,hand.rotation.z,hand.rotation.w],
            'socket':[socket.translation.x,socket.translation.y,socket.translation.z]})
    report['success']=True
finally:
    unreal.EditorLevelLibrary.destroy_actor(actor)
    out.write_text(json.dumps(report,indent=2)+'\n')
unreal.log('VEYR_GRIP_REFERENCE_PROBE_COMPLETE')
