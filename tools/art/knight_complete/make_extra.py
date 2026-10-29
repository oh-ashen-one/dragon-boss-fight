import json, shutil, sys
from pathlib import Path
R = Path(sys.argv[1]); run = Path(sys.argv[2])
dst = R / "serve/ingame"; dst.mkdir(parents=True, exist_ok=True)
items = []
for f in sorted(run.glob("frame-*-lockon_*.png")):
    shutil.copy2(f, dst / f.name)
    label = f.stem.split("lockon_", 1)[1].replace("_", " ")
    items.append({"image": "ingame/" + f.name, "caption": "Packaged Shipping build, lockon replay: " + label})
fab = json.loads((R / "data/runstop-fab.json").read_text())["summary"]
old = json.loads((R / "data/runstop-tripo.json").read_text())["summary"]
def line(s, name):
    return ("%s: max point gap %.0f cm (median %.0f), clip peak %.0f cm/s; blend 0.10 s peak %.0f cm/s, over clip peak in %d/24 phases; "
            "0.20 s %d/24; 0.30 s %d/24 (peak %.0f)") % (name, s["maxPointGapCm"]["max"], s["maxPointGapCm"]["median"], s["clipPeakReferenceCmS"],
            s["blend0.10PeakSpeedCmS"]["max"], s["blend0.10PeakSpeedCmS"]["phasesOverClipPeak"], s["blend0.20PeakSpeedCmS"]["phasesOverClipPeak"],
            s["blend0.30PeakSpeedCmS"]["phasesOverClipPeak"], s["blend0.30PeakSpeedCmS"]["max"])
extra = {"intro": "Engine checks: packaged Shipping lockon replay passed (10 locomotion trials sampled their clips, max facing error under 2 degrees, directional stagger lab 5/5). "
                  "Frame rate in these runs was about 16 fps because other sessions held the GPU near 100%; screenshots are evidence of clip selection, not of performance.",
         "sections": [
             {"title": "RunStop join measurement (24 run phases, joints plus sword tip, game cm)",
              "items": [{"caption": line(fab, "Fab run (current) to RunStop")}, {"caption": line(old, "Earlier Blender run (RunStop authored from it) to RunStop")}]},
             {"title": "Packaged game, lock-on and stagger lab screenshots", "items": items}]}
(R / "extra.json").write_text(json.dumps(extra, indent=1) + "\n")
print(len(items), "screenshots")
