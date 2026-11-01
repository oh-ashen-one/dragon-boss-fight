#!/usr/bin/env python3
"""Anonymize native contact sequences. Mapping stays outside the critic directory."""
import argparse
import json
import math
from pathlib import Path
import secrets

from PIL import Image
from encode_video import read_capture


def prepare(before, after, directory, mapping_file):
    directory, mapping_file = directory.resolve(), mapping_file.resolve()
    if mapping_file.is_relative_to(directory):
        raise ValueError("Blind mapping must stay outside the review directory")
    if directory.exists() or mapping_file.exists():
        raise ValueError("Refusing to overwrite a review or mapping")
    versions = ["before", "after"]
    secrets.SystemRandom().shuffle(versions)
    mapping = dict(zip(["A", "B"], versions))
    inputs = {"before": before.resolve(), "after": after.resolve()}
    data_by_version = {key: json.loads(path.read_text()) for key, path in inputs.items()}
    chosen = {"before": [], "after": []}
    for event_name, action in [("leg_contact", "LightAttack"), ("leg_contact", "HeavyAttack"), ("head_contact", "HeavyAttack")]:
        candidates = {key: [e for e in data["events"] if e["event"] == event_name and e["action"] == action]
                      for key, data in data_by_version.items()}
        def matching_cost(pair):
            a, b = pair
            pa = [x - y for x, y in zip(a["playerFeet"], a["bossPosition"])]
            pb = [x - y for x, y in zip(b["playerFeet"], b["bossPosition"])]
            dot = max(-1, min(1, sum(x * y for x, y in zip(a["playerForward"], b["playerForward"]))))
            return (a["dragonState"] != b["dragonState"], math.dist(pa, pb) + 100 * math.acos(dot))
        pairs = [(a, b) for a in candidates["before"] for b in candidates["after"]]
        if not pairs:
            raise ValueError("Both replays must contain each required contact action")
        a, b = min(pairs, key=matching_cost)
        chosen["before"].append(a)
        chosen["after"].append(b)
    directory.mkdir(parents=True)
    manifest = {
        "scope": "Corresponding native actions under the same adaptive policy, not an identical prerecorded trajectory. No generated or interpolated frames. Sheets resize only; details preserve full resolution.",
        "selection": "Closest actor-relative position/facing pair within each shared contact action, prioritizing matching dragon state, chosen without inspecting pixels. Full videos retain all contacts.",
        "sequences": [], "matchingDiagnostics": [],
    }
    events_by_label = {}
    for label, version in mapping.items():
        evidence = inputs[version]
        data = json.loads(evidence.read_text())
        if not (data.get("finalWrite") and data.get("finished") and data.get("passed")):
            raise ValueError("Review requires completed, passing replay evidence")
        source = evidence.parent / "native-video"
        _, frames, _, _, _ = read_capture(source / "frames.jsonl")
        if data.get("sourceId") != frames[0]["sourceId"]:
            raise ValueError("Replay and captured frames identify different builds")
        if len(frames) < 20:
            raise ValueError("Insufficient native captured frames")
        events = chosen[version]
        events_by_label[label] = events
        for number, event in enumerate(events, 1):
            index = min(range(len(frames)), key=lambda i: abs(frames[i]["requestedGameSeconds"] - event["seconds"]))
            if index < 4 or index + 12 > len(frames):
                raise ValueError("A contact lacks its complete review window")
            selected = frames[index - 4:index + 12]
            sheet = Image.new("RGB", (1920, 1080))
            for cell, frame in enumerate(selected):
                with Image.open(source / frame["file"]) as image:
                    sheet.paste(image.convert("RGB").resize((480, 270), Image.Resampling.LANCZOS),
                                ((cell % 4) * 480, (cell // 4) * 270))
            name = f"{label}-contact-{number}.jpg"
            sheet.save(directory / name, quality=90)
            row = {
                "label": label, "sheet": name,
                "action": ["light leg", "heavy leg", "heavy head"][number - 1],
                "order": "4 columns, row-major",
                "relativePixelSeconds": [round(f["wallSeconds"] - frames[index]["wallSeconds"], 4) for f in selected],
                "zero": "closest capture to logged contact; uncertainty up to one captured interval",
            }
            if number >= 2:
                detail = f"{label}-contact-{number}-detail.jpg"
                with Image.open(source / frames[index + 1]["file"]) as image:
                    image.convert("RGB").save(directory / detail, quality=93)
                row["fullResolutionDetail"] = detail
            manifest["sequences"].append(row)
    for number, (a, b) in enumerate(zip(events_by_label["A"], events_by_label["B"]), 1):
        relative_a = [x - y for x, y in zip(a["playerFeet"], a["bossPosition"])]
        relative_b = [x - y for x, y in zip(b["playerFeet"], b["bossPosition"])]
        dot = max(-1, min(1, sum(x * y for x, y in zip(a["playerForward"], b["playerForward"]))))
        manifest["matchingDiagnostics"].append({
            "contact": number, "relativeActorPositionDifferenceCm": round(math.dist(relative_a, relative_b), 2),
            "playerFacingDifferenceDegrees": round(math.degrees(math.acos(dot)), 2),
            "sameKnightAction": a["action"] == b["action"], "sameDragonState": a["dragonState"] == b["dragonState"],
            "bossWorldPositionDifferenceCm": round(math.dist(a["bossPosition"], b["bossPosition"]), 2),
            "dragonStateSecondsDifference": round(abs(a["stateElapsed"] - b["stateElapsed"]), 4),
        })
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    mapping_file.parent.mkdir(parents=True, exist_ok=True)
    mapping_file.write_text(json.dumps(mapping, indent=2) + "\n")
    print(json.dumps({"images": len(list(directory.glob("*.jpg"))),
                      "matchingDiagnostics": manifest["matchingDiagnostics"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.before, args.after, args.directory, args.mapping)
