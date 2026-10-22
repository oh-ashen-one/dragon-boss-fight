import bpy, shutil
exec(open('/Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_v1/dragon_render.py').read())
setup(show=globals().get('SHOW', ('DRAGON_MESH','DRAGON_DEFORM')))
bpy.data.objects['REVIEW_Ground'].scale=(4,4,1)
out = W/'renders'/PASS
if VIEW == 'front': shutil.rmtree(out, ignore_errors=True)
render(range(0,LAST+1), out, res=globals().get('RES', (480,360)), views=(VIEW,))
