"""blender -b --factory-startup Dragon_Idle_v2r_v2.blend --python dump_stance.py -- <out.npz> : idle_v2 frame-0 channels = the shared stance"""
import bpy, sys, numpy as np
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import lib_anim as L
out = sys.argv[sys.argv.index("--") + 1]
A = bpy.data.objects["Armature"]; act = A.animation_data.action; assert act.name == "idle_v2"
ch = L.read_channels(act, [0])
bones = [b for b in ch if "q" in ch[b]]
np.savez(out, bones=np.array(bones), q=np.array([ch[b]["q"][0] for b in bones]), l=np.array([ch[b]["l"][0] if "l" in ch[b] else np.zeros(3) for b in bones]))
print("STANCE_DUMP", out, len(bones))
