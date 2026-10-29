#!/usr/bin/env python3
"""Encode the native blendproof video into per-sequence MP4s (H.264, 30 fps real time) with a data overlay.

Input: an Evidence/native-blendproof-* folder produced by
  tools/unreal/run_native.py --mode blendproof --video-fps 15
Output: <unreal-run>/blendproof-media/*.mp4 plus *.encode.json receipts.

Timing is the native capture timing (actual pixel-callback wall time) as tools/unreal/encode_video.py preserves it;
the final file is that variable-rate video resampled to constant 30 fps (a held frame stays held, nothing is
interpolated). The burned-in subtitle shows, for the nearest recorded game frame: sequence, phase, clip, blend alpha,
sword-to-hand excess and the worst planted-foot travel of the last frame. No frame is generated or altered.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def srt_time(seconds):
    ms = int(round(max(0.0, seconds) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def load_jsonl(path):
    rows = []
    for line in path.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def frame_text(row):
    if row is None:
        return "setup / transit"
    slide = 0.0
    for key in ("toeTravelCm", "ankleTravelCm"):
        for index, planted in enumerate(row["toePlanted" if key == "toeTravelCm" else "anklePlanted"]):
            if planted:
                slide = max(slide, row[key][index])
    blend = f"blend {row['blendFrom']}->{row['clip']} a={row['blendAlpha']:.2f}" if row["blending"] else f"clip {row['clip']}"
    hidden = "  [blink hidden]" if row["blinkHidden"] else ""
    return (f"{row['sequence']}  {row['phase']}  t={row['t']:.2f}s\\N{blend}{hidden}\\N"
            f"sword-hand excess {row['swordExcessCm']:.2f} cm  hand-space err {row['swordHandSpaceErrorCm']:.2f} cm  "
            f"planted foot travel {slide:.2f} cm/frame")


def encode(manifest_rows, frames, evidence_rows, out_dir, name, ffmpeg, skip_overlay):
    """frames: native 'frame' records already filtered; manifest_rows: world_start/world_end context."""
    video_dir = out_dir.parent / "native-video"
    sub = video_dir / f"frames-{name}.jsonl"
    start_row = next(r for r in manifest_rows if r.get("type") == "world_start")
    last_wall = frames[-1]["wallSeconds"]
    nxt = [r["wallSeconds"] for r in manifest_rows if r.get("type") == "frame" and r["wallSeconds"] > last_wall]
    end_wall = min(nxt) if nxt else last_wall + 1.0 / max(1, start_row.get("requestedFPS", 15))
    rows = [start_row] + frames + [{"type": "world_end", "wallSeconds": end_wall, "worldIndex": start_row.get("worldIndex", 0), "reason": "sequence window"}]
    sub.write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows))
    vfr = out_dir / f"{name}-native-vfr.mp4"
    final = out_dir / f"{name}.mp4"
    for path in (vfr, vfr.with_suffix(".encode.json"), video_dir / f"{vfr.stem}.ffconcat", final):
        if path.exists():
            path.unlink()
    result = subprocess.run([sys.executable, str(HERE / "encode_video.py"), str(sub), "--output", str(vfr)], capture_output=True, text=True)
    if result.returncode:
        raise SystemExit(f"encode_video failed for {name}: {result.stdout}\n{result.stderr}")
    srt = out_dir / f"{name}.srt"
    first_wall = frames[0]["wallSeconds"]
    times = [(r["t"], r) for r in evidence_rows]
    lines = []
    for i, frame in enumerate(frames):
        begin = frame["wallSeconds"] - first_wall
        finish = (frames[i + 1]["wallSeconds"] if i + 1 < len(frames) else end_wall) - first_wall
        game_t = frame.get("requestedGameSeconds", 0.0)
        best = min(times, key=lambda item: abs(item[0] - game_t))[1] if times else None
        if best is not None and abs(best["t"] - game_t) > 0.6:
            best = None
        lines += [str(i + 1), f"{srt_time(begin)} --> {srt_time(max(finish, begin + 0.001))}", frame_text(best), ""]
    srt.write_text("\n".join(lines))
    video_filter = "fps=30" if skip_overlay else (
        "subtitles=" + srt.name + ":original_size=1280x720:force_style='FontName=Menlo,FontSize=9,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        "BorderStyle=3,Outline=1,Shadow=0,Alignment=5,MarginL=10,MarginV=8',fps=30")
    command = [ffmpeg, "-hide_banner", "-nostdin", "-y", "-i", vfr.name, "-vf", video_filter, "-an", "-c:v", "libx264", "-preset", "medium",
               "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", "-movflags", "+faststart", final.name]
    result = subprocess.run(command, cwd=out_dir, capture_output=True, text=True)
    if result.returncode:
        raise SystemExit(f"ffmpeg failed for {name}: {result.stderr[-2000:]}")
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name,width,height,r_frame_rate,nb_frames,duration",
                            "-of", "json", str(final)], capture_output=True, text=True, check=True)
    receipt = {"name": name, "nativeFrames": len(frames), "firstWallSeconds": first_wall, "endWallSeconds": end_wall,
               "expectedRealSeconds": end_wall - first_wall, "probe": json.loads(probe.stdout)["streams"][0],
               "vfrSource": vfr.name, "overlay": not skip_overlay}
    final.with_suffix(".encode.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", type=Path, help="Evidence/native-blendproof-* folder")
    parser.add_argument("--no-overlay", action="store_true")
    parser.add_argument("--delete-frames", action="store_true", help="remove native-video PNGs after every MP4 verified")
    parser.add_argument("--margin", type=float, default=0.25, help="game seconds of context around each sequence")
    args = parser.parse_args()
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not shutil.which("ffprobe"):
        parser.error("ffmpeg and ffprobe are required")
    run = args.run.resolve()
    unreal_runs = sorted(run.glob("unreal-blendproof-*"))
    if len(unreal_runs) != 1:
        parser.error("expected exactly one unreal-blendproof-* folder inside the run")
    unreal_run = unreal_runs[0]
    evidence = json.loads((unreal_run / "evidence.json").read_text())
    proof = evidence["blendProof"]
    manifest = unreal_run / "native-video" / "frames.jsonl"
    if not manifest.is_file():
        parser.error("no native-video/frames.jsonl; run with --video-fps 15")
    rows = load_jsonl(manifest)
    frames = [r for r in rows if r.get("type") == "frame"]
    evidence_rows = load_jsonl(unreal_run / proof["framesFile"])
    out_dir = unreal_run / "blendproof-media"
    out_dir.mkdir(exist_ok=True)
    receipts = []
    for seq in proof["sequences"]:
        lo, hi = seq["gameStartSeconds"] - args.margin, seq["gameEndSeconds"] + args.margin
        picked = [f for f in frames if lo <= f.get("requestedGameSeconds", -1) <= hi]
        if len(picked) < 2:
            print(f"skip {seq['name']}: only {len(picked)} native frames in window", file=sys.stderr)
            continue
        name = f"{seq['index']:02d}-{seq['name']}"
        sequence_rows = [r for r in evidence_rows if r["seq"] == seq["index"]]
        receipts.append(encode(rows, picked, sequence_rows, out_dir, name, ffmpeg, args.no_overlay))
        print("encoded", name, len(picked), "native frames", flush=True)
    receipts.append(encode(rows, frames, evidence_rows, out_dir, "00-blendproof-all", ffmpeg, args.no_overlay))
    (out_dir / "media-receipt.json").write_text(json.dumps(receipts, indent=2) + "\n")
    if args.delete_frames:
        for png in (unreal_run / "native-video").glob("frame-*.png"):
            png.unlink()
    print(json.dumps({"mediaDirectory": str(out_dir), "videos": [r["name"] for r in receipts]}, indent=2))


if __name__ == "__main__":
    main()
