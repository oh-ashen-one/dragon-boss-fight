import bpy,json,math
from pathlib import Path
from mathutils import Vector,Matrix
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'Local/AttackSources20261101/KevinIglesias/Retarget'
bpy.ops.wm.open_mainfile(filepath=str(BASE/'Exports/Kevin_Heavy_M_v1.blend'),load_ui=False)
rig=bpy.data.objects['Knight_Comparison'];s=bpy.context.scene
inverse=rig.data.bones['LeftHand'].matrix_local.inverted()
points={n:inverse@rig.data.bones['LeftHand'+n].head_local for n in ['Index','Pinky','Middle']}
longitudinal=points['Middle'].normalized();blade=(points['Index']-points['Pinky']).normalized();across=(longitudinal-blade*longitudinal.dot(blade)).normalized();palm=(points['Index']+points['Pinky'])*.5-across*.010
records=[]
for frame in [0,12,24,36,48]:
 s.frame_set(frame);bpy.context.view_layer.update();world={n:rig.matrix_world@rig.pose.bones[n].matrix for n in ['LeftArm','LeftForeArm','LeftHand','RightHand','WeaponSocket']}
 shoulder=world['LeftArm'].translation;elbow=world['LeftForeArm'].translation;wrist=world['LeftHand'].translation;socket=world['WeaponSocket'];actual=world['LeftHand']@palm
 records.append({'frame':frame,'palmLocal':list(palm),'armLengths':[(elbow-shoulder).length,(wrist-elbow).length],
 'leftWrist':list(wrist),'leftPalm':list(actual),'rightWrist':list(world['RightHand'].translation),'socket':list(socket.translation),'socketScale':list(socket.to_scale()),'palmInSocket':list(socket.inverted()@actual),
 'reachByAxis':{str(axis):[(off,(socket@Vector(tuple(off if k==axis else 0 for k in range(3)))-world['LeftHand'].to_3x3()@palm-shoulder).length) for off in [-.28,-.18,-.08,0,.18]] for axis in range(3)}})
p=BASE/'grip-geometry-debug.json';assert not p.exists();p.write_text(json.dumps(records,indent=2)+'\n');print('GRIP_GEOMETRY_INSPECTED')
