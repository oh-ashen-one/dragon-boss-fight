#!/usr/bin/env python3
"""Measure capture gaps, including actual contact windows. Never infer visual quality."""
import argparse
import json
from pathlib import Path
import statistics


def intervals(rows):
    gaps = [b["wallSeconds"] - a["wallSeconds"] for a, b in zip(rows, rows[1:])]
    if not gaps or any(gap <= 0 for gap in gaps):
        raise ValueError("Need strictly ordered captured frames")
    ordered = sorted(gaps)
    return {"frames": len(rows), "fps": 1 / statistics.mean(gaps),
            "medianGapMs": statistics.median(gaps) * 1000,
            "p95GapMs": ordered[min(len(ordered) - 1, int(len(ordered) * .95))] * 1000,
            "maximumGapMs": max(gaps) * 1000}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.evidence.read_text())
    manifest = args.evidence.parent / "native-video/frames.jsonl"
    records = [json.loads(line) for line in manifest.read_text().splitlines() if line.strip()]
    frames = [row for row in records if row.get("type") == "frame"]
    contacts = []
    for event in data.get("events", []):
        if event.get("event") not in {"leg_contact", "head_contact", "body_contact", "damage_received"}:
            continue
        nearest = min(frames, key=lambda row: abs(row["requestedGameSeconds"] - event["seconds"]))
        around = [row for row in frames if abs(row["wallSeconds"] - nearest["wallSeconds"]) < .3]
        metric = intervals(around)
        metric.update(event=event["event"], gameSeconds=event["seconds"],
                      estimatedWallSeconds=nearest["wallSeconds"])
        contacts.append(metric)
    result = {"overall": intervals(frames), "contacts": contacts,
              "sourceId": data.get("sourceId"),
              "failedFrames": sum(row.get("type") == "failed_frame" for row in records),
              "qualityAccepted": False,
              "scope": "Pixel callback timing, not scene motion or render performance. Contact wall time is the nearest capture request to the game's event."}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
