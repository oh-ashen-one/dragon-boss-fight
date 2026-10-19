"""Stage a native knight/weapon pose in the root-owned fresh PIE world.

No editor launch, asset edits, screenshot capture, gameplay simulation or art
acceptance. Keep this imported module alive between stage()/cleanup() calls.
Root captures the official viewport after stage. Stop PIE for a complete reset.
Do not interact with gameplay controls while actors/components are frozen.

Installed UE5.8 API evidence and native findings:
 BlueprintInternalUseOnly deferred-spawn functions are excluded from Python.
 Use the knight's existing CameraComponent named Combat Camera instead. Its
 bUsePawnControlRotation is false in the constructor; frozen component ticks
 prevent the spring arm from overwriting the staged world transform.
 Controller's current view target must already be this actual knight.
 SceneComponent.h: SetWorldTransform(NewTransform,bSweep,outHit,bTeleport).
 UE5.8 native Transform()/translation/rotation/scale3d assignment is verified
 in import_customuse.py. MakeTransform is a native struct constructor mapping,
 not a MathLibrary Python factory. Camera look rotation uses atan2 and the
 verified Rotator(...).quaternion() conversion. GetComponentBounds has3 outputs.
 Veyr GetBoneTargetWorldTransform is verified to return Transform or None;
 explicit(bool,Transform) tuple adaptation is also handled, never guessed.
"""
import datetime
import json
import math
from pathlib import Path
import uuid

ROOT=Path(__file__).resolve().parents[2]
PROJECT=ROOT/'Unreal/Veyr'
_SESSION=None


def vec(v):
    return [float(v.x),float(v.y),float(v.z)]


def transform_data(t):
    return {'translation':vec(t.translation),'rotation':[float(t.rotation.x),float(t.rotation.y),float(t.rotation.z),float(t.rotation.w)],'scale':vec(t.scale3d)}


def game_state(knight):
    return {'health':float(knight.get_editor_property('health')),'stamina':float(knight.get_editor_property('stamina')),
            'healingCharges':int(knight.get_editor_property('healing_charges')),'action':str(knight.get_editor_property('action')),
            'actionElapsed':float(knight.get_action_elapsed()),'actionDuration':float(knight.get_action_duration()),
            'twoHanded':bool(knight.is_two_handed()),'pawnTransform':transform_data(knight.get_actor_transform())}


def target_transform(presentation,name,unreal):
    result=presentation.get_bone_target_world_transform(name)
    if isinstance(result,unreal.Transform):return result
    if isinstance(result,tuple) and len(result)==2 and result[0] is True and isinstance(result[1],unreal.Transform):return result[1]
    raise RuntimeError('Missing evaluated target '+str(name)+': '+repr(result))


def _world(unreal,expected=None):
    if Path(unreal.Paths.project_dir()).resolve()!=PROJECT.resolve():raise RuntimeError('Wrong owned Veyr project')
    worlds=unreal.EditorLevelLibrary.get_pie_worlds(False)
    if len(worlds)!=1:raise RuntimeError('Expected exactly one root-owned fresh PIE world')
    world=worlds[0]
    if expected is not None and world.get_path_name()!=expected:raise RuntimeError('PIE world differs from requested ownership path')
    return world


def _valid(unreal,obj):
    return obj is not None and unreal.SystemLibrary.is_valid(obj)


def _make_transform(unreal,location,rotation,scale=None):
    transform=unreal.Transform()
    transform.translation=location
    transform.rotation=rotation if isinstance(rotation,unreal.Quat) else rotation.quaternion()
    transform.scale3d=scale if scale is not None else unreal.Vector(1,1,1)
    return transform


def _component_bounds(unreal,component):
    value=unreal.SystemLibrary.get_component_bounds(component)
    if not isinstance(value,tuple) or len(value)!=3:raise RuntimeError('Unexpected native component-bounds out tuple')
    origin,extent,radius=value
    if not all(math.isfinite(x) for x in vec(origin)+vec(extent)+[float(radius)]):raise RuntimeError('Non-finite native bounds')
    return vec(origin),vec(extent)


def stage(definition_path,clip,phase,weapon_path,view='front',expected_world_path=None):
    """Apply/sample actual candidate, equip actual mesh at weapon_grip WORLDscale1.

    view=front|side|grip. Full views frame union of native body+weapon bounds with
    a conservative enclosing sphere; grip view intentionally crops the blade.
    Repeated calls retain the initial restoration snapshot and reuse Combat Camera.
    """
    import unreal
    global _SESSION
    if not definition_path.startswith('/Game/Characters/Customuse/KnightB/'):
        raise ValueError('Use an exact versioned private KnightB definition')
    if not weapon_path.startswith('/Game/ArtPass/Tripo/') or '/SM_' not in weapon_path:
        raise ValueError('Use an exact versioned imported Tripo static mesh')
    if view not in ('front','side','grip') or not math.isfinite(phase) or not 0<=phase<=1:
        raise ValueError('Expected front/side/grip view and finite phase0..1')
    world=_world(unreal,expected_world_path);world_path=world.get_path_name()
    if _SESSION is not None and (_SESSION['worldPath']!=world_path or not _valid(unreal,_SESSION['knight'])):
        # Old PIE objects must not be applied to a new PIE session.
        _SESSION=None
    knights=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.VeyrKnight)
    if len(knights)!=1:raise RuntimeError('Expected exactly one actual VeyrKnight')
    knight=knights[0];controller=unreal.GameplayStatics.get_player_controller(world,0)
    if not controller or controller.get_controlled_pawn()!=knight:raise RuntimeError('Local PIE controller does not possess the intended knight')
    definition=unreal.load_asset(definition_path);weapon_mesh=unreal.load_asset(weapon_path)
    if not isinstance(definition,unreal.VeyrVisualDefinition) or not isinstance(weapon_mesh,unreal.StaticMesh):
        raise RuntimeError('Missing candidate definition or actual imported weapon')
    clips=definition.get_editor_property('clips');keys={str(k):k for k in clips}
    if clip not in keys:raise ValueError('Requested clip is absent from candidate definition')
    target_names={str(k):k for k in definition.get_editor_property('bone_targets')}
    if 'weapon_grip' not in target_names:raise ValueError('Candidate must define measured weapon_grip target')
    presentation=knight.get_editor_property('imported_presentation')
    # BoatWeapon is a private non-Blueprint UPROPERTY. Enumerate the actor's
    # reflected components and match its actual CreateDefaultSubobject name.
    # The C++ member name is NOT the UObject name.
    static_components=list(knight.get_components_by_class(unreal.StaticMeshComponent))
    matches=[component for component in static_components if component.get_name()=='Tripo Timber Greatsword']
    if len(matches)!=1:
        raise RuntimeError('Expected exactly one Tripo Timber Greatsword component; found names: '+
                           repr([component.get_name() for component in static_components]))
    weapon=matches[0]
    if not presentation:raise RuntimeError('Actual knight presentation component missing')
    cameras=[component for component in knight.get_components_by_class(unreal.CameraComponent)
             if component.get_name()=='Combat Camera']
    if len(cameras)!=1:raise RuntimeError('Expected the actual knight Combat Camera component')
    camera_component=cameras[0]
    if controller.get_view_target()!=knight:raise RuntimeError('Fresh PIE view target must already be the actual knight')
    before=game_state(knight)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid.uuid4().hex[:8]
    folder=ROOT/'Local/art-pass-20261019/knight-native-review';folder.mkdir(parents=True,exist_ok=True)
    receipt={'staged':False,'gameplayAcceptance':False,'visualAcceptance':False,'world':world_path,'definition':definition_path,
             'weapon':weapon_path,'weaponComponent':weapon.get_name(),'clip':clip,'phase':float(phase),'view':view,'gameplayBefore':before}
    try:
        if _SESSION is None:
            dragons=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.VeyrDragon)
            actors=[knight]+list(dragons)
            components=[]
            for actor in actors:
                components.extend((c,bool(c.is_component_tick_enabled())) for c in actor.get_components_by_class(unreal.ActorComponent))
            _SESSION={'worldPath':world_path,'knight':knight,'controller':controller,
                      'definition':knight.get_editor_property('customuse_visual_definition'),'presentation':presentation,
                      'clip':str(presentation.get_editor_property('current_clip')),'time':float(presentation.get_editor_property('current_trimmed_seconds')),
                      'actors':[(a,bool(a.is_actor_tick_enabled())) for a in actors],
                      'components':components,'dragons':[(d,bool(d.get_editor_property('hidden'))) for d in dragons],
                      'weapon':weapon,'weaponMesh':weapon.get_editor_property('static_mesh'),'weaponTransform':weapon.get_world_transform(),
                      'weaponVisible':bool(weapon.is_visible()),'weaponHidden':bool(weapon.get_editor_property('hidden_in_game')),
                      'gameplay':before,'cameraComponent':camera_component,
                      'cameraTransform':camera_component.get_world_transform(),
                      'cameraFOV':float(camera_component.get_editor_property('field_of_view')),
                      'cameraAspect':float(camera_component.get_editor_property('aspect_ratio')),
                      'cameraConstrainAspect':bool(camera_component.get_editor_property('constrain_aspect_ratio'))}
        for actor,_ in _SESSION['actors']:actor.set_actor_tick_enabled(False)
        # CharacterMovement ticks independently of its owner. Disable component
        # ticks too, retaining velocity/movement mode and the exact pawn transform.
        for component,_ in _SESSION['components']:component.set_component_tick_enabled(False)
        for dragon,_ in _SESSION['dragons']:dragon.set_actor_hidden_in_game(True)
        if not knight.apply_customuse_visual(definition):raise RuntimeError('Actual knight rejected candidate definition')
        if not presentation.sample_clip_phase(keys[clip],phase):raise RuntimeError('Explicit native pose sample rejected')
        grip=target_transform(presentation,target_names['weapon_grip'],unreal)
        # UE returns false for an unchanged mesh too; verify actual assignment.
        if weapon.get_editor_property('static_mesh')!=weapon_mesh:
            weapon.set_static_mesh(weapon_mesh)
        if weapon.get_editor_property('static_mesh')!=weapon_mesh:raise RuntimeError('BoatWeapon rejected actual static mesh')
        weapon.set_world_transform(_make_transform(unreal,grip.translation,grip.rotation),False,True)
        weapon.set_visibility(True,False);weapon.set_hidden_in_game(False,False)
        actual=weapon.get_world_transform()
        if max(abs(v-1) for v in vec(actual.scale3d))>1e-5:raise RuntimeError('Equipped weapon inherited a nonunit world scale')
        if max(abs(a-b) for a,b in zip(vec(actual.translation),vec(grip.translation)))>1e-3:raise RuntimeError('Weapon origin does not match evaluated grip')
        receipt['targets']={name:transform_data(target_transform(presentation,key,unreal)) for name,key in target_names.items()}
        receipt['weaponWorld']=transform_data(actual)
        body_origin,body_extent=_component_bounds(unreal,presentation);weapon_origin,weapon_extent=_component_bounds(unreal,weapon)
        low=[min(a-b,c-d) for a,b,c,d in zip(body_origin,body_extent,weapon_origin,weapon_extent)]
        high=[max(a+b,c+d) for a,b,c,d in zip(body_origin,body_extent,weapon_origin,weapon_extent)]
        center=[(a+b)/2 for a,b in zip(low,high)];radius=math.sqrt(sum(((b-a)/2)**2 for a,b in zip(low,high)))
        if radius<=0:raise RuntimeError('Native union bounds are empty')
        forward=vec(knight.get_actor_forward_vector());right=vec(knight.get_actor_right_vector())
        direction=forward if view=='front' else right if view=='side' else [a+.55*b for a,b in zip(forward,right)]
        length=math.sqrt(sum(v*v for v in direction));direction=[v/length for v in direction]
        fov=45.;aspect=16/9;vertical_half=math.atan(math.tan(math.radians(fov/2))/aspect)
        if view=='grip':center=vec(grip.translation);radius=72.
        distance=radius/math.sin(vertical_half)*1.12
        camera_location=unreal.Vector(*[v+d*distance for v,d in zip(center,direction)])
        look=unreal.Vector(*center)
        delta=[a-b for a,b in zip(center,vec(camera_location))]
        camera_rotation=unreal.Rotator(pitch=math.degrees(math.atan2(delta[2],math.hypot(delta[0],delta[1]))),
                                      yaw=math.degrees(math.atan2(delta[1],delta[0])),roll=0.)
        transform=_make_transform(unreal,camera_location,camera_rotation)
        camera_component.set_world_transform(transform,False,True)
        camera_component.set_editor_property('field_of_view',fov)
        camera_component.set_editor_property('aspect_ratio',aspect)
        camera_component.set_editor_property('constrain_aspect_ratio',True)
        after=game_state(knight)
        if after!=before:raise RuntimeError('Pose staging changed gameplay state or pawn transform')
        receipt.update(staged=True,gameplayUnchanged=True,gameplayAfter=after,sequenceSeconds=float(presentation.get_editor_property('current_sequence_seconds')),
            camera={'component':camera_component.get_path_name(),'transform':transform_data(camera_component.get_world_transform()),'fovDegrees':fov,'aspect':aspect,
                    'distanceCm':distance,'focus':center,'fullWeaponFramed':view!='grip','unionBoundsCm':[low,high]},
            restore='Stop PIE for a complete reset; cleanup restores Combat Camera transform/FOV/aspect, definition/sample, weapon, ticks and visibility.')
    except Exception as error:
        receipt['error']=str(error)
        if _SESSION is not None:
            try:receipt['cleanupAfterFailure']=cleanup()
            except Exception as restore_error:receipt['cleanupError']=str(restore_error)
        raise
    finally:
        path=folder/(stamp+'-'+view+'.json');path.write_text(json.dumps(receipt,indent=2)+'\n')
        unreal.log('VEYR_KNIGHT_POSE_STAGE_RECEIPT '+str(path))
    return receipt


def cleanup():
    """Restore this module's snapshot only. Stop PIE is the complete reset path."""
    import unreal
    global _SESSION
    if _SESSION is None:return {'restored':False,'reason':'No owned staging snapshot'}
    saved=_SESSION;worlds=unreal.EditorLevelLibrary.get_pie_worlds(False)
    if len(worlds)!=1 or worlds[0].get_path_name()!=saved['worldPath']:
        _SESSION=None;return {'restored':False,'reason':'Original PIE ended; no new-world objects touched'}
    errors=[]
    def attempt(name,call):
        try:call()
        except Exception as error:errors.append(name+': '+str(error))
    controller=saved['controller'];knight=saved['knight'];weapon=saved['weapon'];presentation=saved['presentation']
    camera_component=saved['cameraComponent']
    if _valid(unreal,camera_component):
        attempt('camera transform',lambda:camera_component.set_world_transform(saved['cameraTransform'],False,True))
        attempt('camera FOV',lambda:camera_component.set_editor_property('field_of_view',saved['cameraFOV']))
        attempt('camera aspect',lambda:camera_component.set_editor_property('aspect_ratio',saved['cameraAspect']))
        attempt('camera constrain aspect',lambda:camera_component.set_editor_property('constrain_aspect_ratio',saved['cameraConstrainAspect']))
    if _valid(unreal,knight) and _valid(unreal,saved['definition']):
        def restore_pose():
            if not knight.apply_customuse_visual(saved['definition']):raise RuntimeError('Original definition rejected')
            if saved['clip']!='None' and not presentation.sample_clip_time(saved['clip'],saved['time']):raise RuntimeError('Original sample rejected')
        attempt('definition/sample',restore_pose)
    if _valid(unreal,weapon):
        attempt('weapon mesh',lambda:weapon.set_static_mesh(saved['weaponMesh']))
        attempt('weapon transform',lambda:weapon.set_world_transform(saved['weaponTransform'],False,True))
        attempt('weapon visibility',lambda:weapon.set_visibility(saved['weaponVisible'],False))
        attempt('weapon hidden',lambda:weapon.set_hidden_in_game(saved['weaponHidden'],False))
    for dragon,hidden in saved['dragons']:
        if _valid(unreal,dragon):attempt('dragon visibility',lambda d=dragon,h=hidden:d.set_actor_hidden_in_game(h))
    for component,enabled in saved['components']:
        if _valid(unreal,component):attempt('component tick',lambda c=component,e=enabled:c.set_component_tick_enabled(e))
    for actor,enabled in saved['actors']:
        if _valid(unreal,actor):attempt('actor tick',lambda a=actor,e=enabled:a.set_actor_tick_enabled(e))
    unchanged=game_state(knight)==saved['gameplay'] if _valid(unreal,knight) else False
    _SESSION=None
    return {'restored':not errors,'errors':errors,'gameplayUnchanged':unchanged,'gameplayAcceptance':False,
            'limit':'Restores prior sampled clip/time, not an interrupted blend/layer snapshot. Use fresh PIE and stop PIE for complete reset.'}
