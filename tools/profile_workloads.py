"""Profile the paired benchmark's changing yaw and simulation, not fixed poses.

These instrumented counts diagnose costs; they are not acceptance timings.
The text report and source manifest use unused paths, preserving earlier runs.
"""

import argparse
import cProfile
from contextlib import ExitStack
import importlib
import io
import json
from pathlib import Path
import platform
import pstats
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ascii3d.sound import Audio
from tools.benchmark import EXTRA_SCENARIOS, SCENARIOS, TERRAIN_SCENARIOS, resolve_camera
from tools.benchmark_pair import audio_health, frame, hashes, prepare, variant


def main():
    cameras = {**SCENARIOS, **EXTRA_SCENARIOS, **TERRAIN_SCENARIOS}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenes", nargs="+", choices=tuple(cameras))
    parser.add_argument("--frames", type=int, default=60)
    parser.add_argument("--width", type=int, default=120)
    parser.add_argument("--height", type=int, default=40)
    parser.add_argument("--audio", action="store_true")
    parser.add_argument("--save", type=Path, required=True)
    args = parser.parse_args()
    if min(args.frames, args.width, args.height) < 1:
        parser.error("frames, width and height must be positive")
    manifest = args.save.with_suffix(".sources.json")
    if args.save.exists() or manifest.exists():
        parser.error("report and source manifest paths must be unused")
    args.save.parent.mkdir(parents=True, exist_ok=True)
    metadata = {"method": "cProfile of benchmark_pair.frame, five warmups; diagnostic only",
                "python": platform.python_version(), "platform": platform.platform(),
                "frames": args.frames, "width": args.width, "height": args.height,
                "audio": args.audio, "scenes": args.scenes,
                "hashes": hashes(Path(__file__).resolve().parents[1])}
    with manifest.open("x", encoding="utf-8") as destination:
        json.dump(metadata, destination, indent=2)
        destination.write("\n")
    with args.save.open("x", encoding="utf-8") as destination, ExitStack() as stack:
        state = variant({name: importlib.import_module(f"ascii3d.{name}")
                         for name in ("world", "player", "renderer", "combat", "soundscape")},
                        args.width, args.height)
        state["elevated_audio"] = True
        audio = stack.enter_context(Audio(volume=0.25)) if args.audio else None
        if audio is not None and not audio.available:
            raise OSError(audio.error or "Audio output unavailable")
        for name in args.scenes:
            position = resolve_camera(state["world"], name, cameras[name], natural=name in TERRAIN_SCENARIOS)
            prepare(state, name, position)
            for _ in range(5):
                frame(state, name, audio, args.width, args.height, measured=False)
            profile = cProfile.Profile()
            profile.enable()
            for _ in range(args.frames):
                frame(state, name, audio, args.width, args.height, measured=False)
            profile.disable()
            output = io.StringIO()
            stats = pstats.Stats(profile, stream=output).strip_dirs()
            stats.sort_stats("cumulative").print_stats(45)
            stats.sort_stats("tottime").print_stats(15)
            destination.write(name + "\n" + output.getvalue() + "\n")
            destination.flush()
            print(name, flush=True)
        if audio is not None:
            destination.write("Audio before cleanup: " + json.dumps(audio_health(audio)) + "\n")


if __name__ == "__main__":
    main()
