#!/usr/bin/env python3
"""Check actual replay evidence. This does not grade visual quality or combat feel."""
import argparse
import json
from pathlib import Path


def check(path, enabled):
    data = json.loads(path.read_text())
    rows = data.get("samples", []) + data.get("events", []) + [data.get("latest", {})]
    rows = [row for row in rows if "fightFeel" in row]
    if not rows:
        return {"instrumentation": False}
    effects = [row["fightFeel"] for row in rows]
    metrics = {
        "instrumentation": True,
        "expectedMode": all(row["enabled"] == enabled for row in effects),
        "amplitudeBound": all(0 <= row["lastShakeDegrees"] <= 1.651 for row in effects),
        "trailBound": all(0 <= row["visibleTrailSegments"] <= 24 for row in effects),
        "validClock": all(abs(row["timeDilation"] - 1) < .001 or abs(row["timeDilation"] - .05) < .001 for row in effects),
        "contactOnlyStops": all(row["fightFeel"]["hitStopEvents"] <= row.get("swordContacts", 0) + row.get("hitsTaken", 0) for row in rows),
        "finalClockRestored": abs(data.get("latest", {}).get("fightFeel", {}).get("timeDilation", 0) - 1) < .001,
        "completedEvidence": data.get("finalWrite", False) and data.get("finished", False),
    }
    counters = ["shakeEvents", "hitStopEvents", "hitFlashEvents", "flinchEvents", "trailSamples"]
    for key in counters:
        peak = max(row[key] for row in effects)
        metrics[key + ("Observed" if enabled else "Disabled")] = peak > 0 if enabled else peak == 0
    if enabled:
        metrics["stopDurationBound"] = all(row["lastHitStopSeconds"] == 0 or .049 <= row["lastHitStopSeconds"] <= .121 for row in effects)
    return metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = {"before": check(args.before, False), "after": check(args.after, True),
              "qualityVerdict": "unproven: requires blind video critique and owner playtest"}
    result["engineeringPassed"] = all(all(result[k].values()) for k in ("before", "after"))
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["engineeringPassed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
