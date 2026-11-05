"""Read existing Blender actions/rest rigs without saving or changing a source file."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy


def matrix(value):
    return [[float(x) for x in row] for row in value]


def inspect(path):
    if path.suffix.lower() == '.blend':
        bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False)
    elif path.suffix.lower() == '.glb':
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(path))
    else:
        raise ValueError('Expected a Blender scene or GLB')
    rigs = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    result = {"source": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
              "fps": bpy.context.scene.render.fps / bpy.context.scene.render.fps_base,
              "sceneRange": [bpy.context.scene.frame_start, bpy.context.scene.frame_end],
              "linkedLibraries": len(bpy.data.libraries), "rigs": []}
    for rig in rigs:
        action = rig.animation_data.action if rig.animation_data else None
        bones = {bone.name: {"parent": bone.parent.name if bone.parent else None,
                             "rest": matrix(bone.matrix_local)} for bone in rig.data.bones}
        meshes = [o for o in bpy.data.objects if o.type == "MESH" and
                  any(m.type == "ARMATURE" and m.object == rig for m in o.modifiers)]
        result["rigs"].append({"name": rig.name, "world": matrix(rig.matrix_world),
                               "boneCount": len(bones), "bones": bones,
                               "restHash": hashlib.sha256(json.dumps(bones, sort_keys=True).encode()).hexdigest(),
                               "action": action.name if action else None,
                               "actionRange": list(action.frame_range) if action else None,
                               "meshes": [{"name": o.name, "vertices": len(o.data.vertices),
                                           "world": matrix(o.matrix_world)} for o in meshes]})
    result["actions"] = [{"name": a.name, "range": list(a.frame_range)} for a in bpy.data.actions]
    return result


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("sources", type=Path, nargs="+")
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
if args.output.exists():
    raise RuntimeError("Refusing to overwrite an inspection report")
rows = [inspect(p.resolve()) for p in args.sources]
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(rows, indent=2) + "\n")
for row in rows:
    print(json.dumps({"file": Path(row["source"]).name, "fps": row["fps"],
                      "linkedLibraries": row["linkedLibraries"],
                      "rigs": [{k: r[k] for k in ["name", "boneCount", "action", "actionRange", "restHash"]}
                               for r in row["rigs"]]}))
