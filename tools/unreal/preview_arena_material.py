"""Apply a reversible arena material/light preview to this task's current PIE world."""
def run():
    import unreal
    worlds=unreal.EditorLevelLibrary.get_pie_worlds(False)
    if len(worlds)!=1:raise RuntimeError('One owned PIE world is required')
    world=worlds[0]
    arenas=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.VeyrArena)
    if len(arenas)!=1:raise RuntimeError('Expected one Veyr arena')
    material=unreal.load_asset('/Game/Veyr/Materials/M_CathedralStone_v3')
    if not isinstance(material,unreal.Material):raise RuntimeError('Authored stone material missing')
    arena=arenas[0]
    changed=[]
    for component in arena.get_components_by_class(unreal.InstancedStaticMeshComponent):
        if 'Rock' in component.get_name() or 'Backdrop' in component.get_name(): continue
        old=component.get_material(0)
        if not isinstance(old,unreal.MaterialInstanceDynamic):continue
        color=old.get_vector_parameter_value('Color')
        roughness=old.get_scalar_parameter_value('Roughness')
        new=component.create_dynamic_material_instance(0,material)
        new.set_vector_parameter_value('Color',color)
        new.set_scalar_parameter_value('Roughness',roughness)
        name=component.get_name()
        if 'Bronze' in name:new.set_scalar_parameter_value('Metallic',.7)
        if 'Ember' in name:new.set_scalar_parameter_value('Emission',2.)
        changed.append(name)
    for light in arena.get_components_by_class(unreal.DirectionalLightComponent):
        moon='SoftMoon' in light.get_name()
        light.set_intensity(3.4 if moon else 2.4)
        light.set_specular_scale(.75 if moon else .6)
    for light in arena.get_components_by_class(unreal.SkyLightComponent):light.set_intensity(.7)
    unreal.log('VEYR_ARENA_MATERIAL_PREVIEW '+repr(changed))
    return changed
