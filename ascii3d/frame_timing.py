"""Bounded gameplay timing samples serialized after terminal restoration."""

from collections import deque
import json
import math
from statistics import mean
import sys


MAX_RECORDED_FRAMES = 3600
METRICS = ("interval_ms", "input_ms", "audio_ms", "simulation_ms", "render_ms",
           "draw_ms", "encode_ms", "write_flush_ms", "output_bytes", "work_ms",
           "cap_requested_ms", "cap_actual_ms")


def milliseconds(seconds):
    return round(seconds * 1000, 6)


class FrameTiming:
    def __init__(self, path, settings):
        self.path = path
        self.settings = settings
        self.frames = deque(maxlen=MAX_RECORDED_FRAMES)
        self.total = 0
        self.start = None

    def begin(self, now):
        if self.frames:
            self.frames[-1]["interval_ms"] = milliseconds(now - self.start)
        self.start = now

    def record(self, **frame):
        frame["interval_ms"] = None
        self.frames.append(frame)
        self.total += 1
        return frame

    def write(self, status):
        summary = {}
        for metric in METRICS:
            values = sorted(frame[metric] for frame in self.frames if frame.get(metric) is not None)
            summary[metric] = {"count": len(values), "mean": round(mean(values), 6) if values else None,
                               "p95": values[math.ceil(len(values) * 0.95) - 1] if values else None}
        report = {
            "version": 1,
            "python": sys.version.split()[0],
            "platform": sys.platform,
            "settings": self.settings,
            "exit_status": status,
            "frames_completed": self.total,
            "frames_retained": len(self.frames),
            "measurement": {"interval_ms": "frame start to next frame start, when observed",
                            "input_ms": "input, terminal sizing and mouse capture",
                            "audio_ms": "soundscape, audio controls and interface event dispatch",
                            "simulation_ms": "game simulation and its audio event dispatch",
                            "draw_ms": "terminal encoding, write and flush",
                            "gpu_stats": "GPU query stages and fallback rays when available",
                            "summary": "nearest-rank p95 of the retained frames"},
            "summary": summary,
            "frames": list(self.frames),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("x", encoding="utf-8") as destination:
            json.dump(report, destination, indent=2)
            destination.write("\n")
