RES=(960,540); FRONT_SCALE=1.2; SIDE_SCALE=1.3; TQ_SCALE=1.15; TARGET_Z=0.40
import bpy, shutil
exec(open("/Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_flight_r2/drender_r2.py").read())
setup(show=("DRAGON_MESH","DRAGON_DEFORM"))
bpy.data.objects["REVIEW_Ground"].scale=(4,4,1)
out = W/"renders"/"hover_v1r2"; shutil.rmtree(out, ignore_errors=True)
n = len(render(range(0, 61), out, res=RES))
print("RES", n, str(out))
