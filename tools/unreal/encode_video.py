#!/usr/bin/env python3
"""Encode unchanged native viewport PNGs using their actual capture timestamps.

Input: an ignored native-video/frames.jsonl produced by -VeyrVideoFPS=1..15.
Output: silent VFR H.264, timing/identity receipt and an inspectable ffconcat file.
No image generation, interpolation, fixed-step capture or missing-frame invention.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys


def read_capture(manifest):
    records = []
    for number, line in enumerate(manifest.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"Manifest line {number} is incomplete or invalid: {error}") from error
        if not isinstance(row, dict):
            raise ValueError(f"Manifest line {number} must be an object")
        records.append(row)
    frames = [row for row in records if row.get("type") == "frame"]
    if not 2 <= len(frames) <= 6000:
        raise ValueError("Need 2 through 6000 successfully captured native frames")
    sources = {row.get("sourceId") for row in frames}
    if len(sources) != 1 or not next(iter(sources)):
        raise ValueError("All frames must identify the same nonempty native source ID")
    previous = -math.inf
    dimensions = set()
    filenames = set()
    for row in frames:
        name = row.get("file", "")
        if not re.fullmatch(r"frame-\d{6}\.png", name) or name in filenames:
            raise ValueError("Video manifest contains an unexpected or repeated frame filename")
        filenames.add(name)
        frame = (manifest.parent / name).resolve()
        if frame.parent != manifest.parent or not frame.is_file():
            raise ValueError(f"Missing frame or frame escapes capture directory: {name}")
        with frame.open("rb") as stream:
            header = stream.read(24)
        if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
            raise ValueError(f"Invalid PNG header: {name}")
        width, height = struct.unpack(">II", header[16:24])
        if (width, height) != (row.get("width"), row.get("height")):
            raise ValueError(f"PNG dimensions disagree with native callback: {name}")
        if width < 2 or height < 2 or width % 2 or height % 2:
            raise ValueError("H.264 yuv420p output requires even capture dimensions >=2; recapture without resizing")
        dimensions.add((width, height))
        timestamp = row.get("wallSeconds")
        if not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp) or timestamp < 0 or timestamp <= previous:
            raise ValueError("Capture timestamps must be finite, nonnegative and strictly increasing")
        previous = timestamp
    if len(dimensions) != 1:
        raise ValueError("Capture dimensions changed; encode separate runs instead of silently resizing")
    fps_values = [row["requestedFPS"] for row in records if row.get("type") == "world_start"]
    if not fps_values or any(not isinstance(fps, (int, float)) or not 1 <= fps <= 15 for fps in fps_values):
        raise ValueError("Missing or invalid native requested FPS metadata")
    # The first world_end after the last pixel timestamp gives the observed tail.
    # If a process crashed without one, use one requested interval and label it.
    endings = [row.get("wallSeconds") for row in records if row.get("type") == "world_end"]
    endings = [value for value in endings if isinstance(value, (int, float)) and math.isfinite(value) and value > previous]
    end = min(endings) if endings else previous + 1 / fps_values[-1]
    return records, frames, end, bool(endings), next(iter(dimensions))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, help="Default: gameplay-vfr.mp4 beside the manifest; refuses overwrite")
    parser.add_argument("--ffmpeg", default=shutil.which("ffmpeg"))
    parser.add_argument("--ffprobe", default=shutil.which("ffprobe"))
    args = parser.parse_args()
    if not args.ffmpeg or not args.ffprobe:
        parser.error("Installed ffmpeg and ffprobe are required; this tool installs nothing")
    manifest = args.manifest.resolve()
    output = (args.output or manifest.parent / "gameplay-vfr.mp4").resolve()
    concat = manifest.parent / (output.stem + ".ffconcat")
    receipt = output.with_suffix(".encode.json")
    if any(path.exists() for path in (output, concat, receipt)):
        parser.error("Output, ffconcat or receipt already exists; choose a fresh --output filename")
    try:
        records, frames, end, observed_tail, dimensions = read_capture(manifest)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = ["ffconcat version 1.0"]
    for index, frame in enumerate(frames):
        following = frames[index + 1]["wallSeconds"] if index + 1 < len(frames) else end
        lines += [f"file '{frame['file']}'", "option framerate 1000", f"duration {following - frame['wallSeconds']:.9f}"]
    # The final repeated still establishes the preceding frame's actual hold.
    # There is no generated in-between motion; timestamp precision is 1ms.
    lines += [f"file '{frames[-1]['file']}'", "option framerate 1000"]
    concat.write_text("\n".join(lines) + "\n")
    command = [args.ffmpeg, "-hide_banner", "-nostdin", "-n", "-f", "concat", "-safe", "0", "-i", str(concat),
               "-an", "-c:v", "libx264", "-threads", "2", "-preset", "veryfast", "-crf", "18",
               # Nominal encoder rate avoids advertising the concat demuxer's
               # 1000-Hz timestamp precision as a level-6 video stream. Passing
               # through PTS preserves every actual variable-rate capture.
               "-pix_fmt", "yuv420p", "-bf", "0", "-x264-params", "fps=60/1:force-cfr=0",
               "-fps_mode", "vfr", "-enc_time_base", "1:1000000",
               "-video_track_timescale", "1000000", "-movflags", "+faststart", str(output)]
    result = subprocess.run(command, cwd=manifest.parent)
    if result.returncode:
        return result.returncode
    probe_result = subprocess.run([args.ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=codec_name,level,width,height,nb_frames,duration,avg_frame_rate:format=duration:frame=pts_time",
                                   "-of", "json", str(output)], check=True, capture_output=True, text=True)
    probe = json.loads(probe_result.stdout)
    actual_duration = float(probe["format"]["duration"])
    expected_duration = end - frames[0]["wallSeconds"]
    stream = probe["streams"][0]
    encoded_pts = [float(row["pts_time"]) for row in probe.pop("frames", [])]
    expected_pts = [row["wallSeconds"] - frames[0]["wallSeconds"] for row in frames] + [expected_duration]
    max_pts_error = max((abs(actual - expected) for actual, expected in zip(encoded_pts, expected_pts)), default=math.inf)
    valid = (len(encoded_pts) == len(expected_pts) and max_pts_error <= .002 and
             abs(actual_duration - expected_duration) <= .025 and (stream["width"], stream["height"]) == dimensions)
    report = {
        "sourceId": frames[0]["sourceId"], "manifestSHA256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "videoSHA256": hashlib.sha256(output.read_bytes()).hexdigest(), "nativeFrames": len(frames),
        "requestedFPS": next(row["requestedFPS"] for row in records if row.get("type") == "world_start"),
        "achievedCaptureFPS": (len(frames) - 1) / (frames[-1]["wallSeconds"] - frames[0]["wallSeconds"]),
        "skippedSlots": sum(row.get("slots", 0) for row in records if row.get("type") == "skip"),
        "failedFrames": sum(row.get("type") == "failed_frame" for row in records),
        "pngWriteSeconds": sum(row.get("pngWriteSeconds", 0) for row in frames),
        "firstCapturedWallSeconds": frames[0]["wallSeconds"], "lastCapturedWallSeconds": frames[-1]["wallSeconds"],
        "expectedDurationSeconds": expected_duration, "encodedDurationSeconds": actual_duration,
        "encodedFrameCount": len(encoded_pts), "maximumFrameTimestampErrorSeconds": max_pts_error if math.isfinite(max_pts_error) else None,
        "lastFrameEndObserved": observed_tail, "terminalHoldSeconds": end - frames[-1]["wallSeconds"],
        "silent": True, "timingVerified": valid, "probe": probe,
        "timingPolicy": "Actual monotonic native pixel-callback timestamps; 1ms encoding precision; skipped captures and reload gaps hold the previous frame. No interpolation. Final endpoint is one repeated still.",
        "ffmpegVersion": subprocess.run([args.ffmpeg, "-version"], check=True, capture_output=True, text=True).stdout.splitlines()[0],
    }
    receipt.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"output": str(output), "receipt": str(receipt), "timingVerified": valid}, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    sys.exit(main())
