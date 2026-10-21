import bpy,json
from pathlib import Path
from mathutils import Vector
scene=bpy.context.scene
root=Path('/Users/midir/veyr-blender-walk-20261021')
cam=scene.camera
scene.render.resolution_x=640;scene.render.resolution_y=640
for view,xyz in [('front',(0,-3.8,1.3)),('side',(3.8,0,1.3)),('threequarter',(2.4,-3.4,1.5))]:
    for f in [0,30,65,102]:
        scene.frame_set(f)
        travel=bpy.data.objects['Knight_Walk_Rig'].pose.bones['Hips'].matrix.translation.y
        cam.location=Vector(xyz)+Vector((0,travel,0))
        cam.rotation_euler=(Vector((0,travel-.15,.87))-cam.location).to_track_quat('-Z','Y').to_euler()
        cam.data.ortho_scale=1.9
        scene.render.filepath=str(root/f'v3-{view}-{f}.png')
        bpy.ops.render.render(write_still=True)
print('Rendered 12 inspection frames')
