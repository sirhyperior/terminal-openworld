"""Benchmark failures retain raw evidence without claiming incomplete passes."""

import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ascii3d.player import Player
from tools.benchmark import EXTRA_SCENARIOS, SCENARIOS, TERRAIN_SCENARIOS, resolve_camera
from tools import benchmark_pair


class CameraPreflightTests(unittest.TestCase):
    def test_every_current_scenario_has_a_clear_shared_collision_pose(self):
        from ascii3d.world import build_world

        world = build_world()
        for name, camera in {**SCENARIOS, **EXTRA_SCENARIOS, **TERRAIN_SCENARIOS}.items():
            with self.subTest(scene=name):
                position = resolve_camera(world, name, camera, natural=name in TERRAIN_SCENARIOS)
                self.assertFalse(world.collides(position["x"], position["y"], position["z"]))

    def test_only_unraised_natural_cameras_follow_circular_support(self):
        world = Mock()
        world.surface_height.return_value = 3.2
        world.walk_support.return_value = (3.3, 5)
        world.collides.return_value = False
        natural = resolve_camera(world, "hill", {"x": 2, "y": 3}, natural=True)
        self.assertEqual(natural["z"], 3.3)
        world.walk_support.assert_called_once_with(2, 3, 3.2)
        world.walk_support.reset_mock()
        self.assertEqual(resolve_camera(world, "roof", {"x": 2, "y": 3, "z": 7}, natural=True)["z"], 7)
        self.assertEqual(resolve_camera(world, "castle", {"x": 2, "y": 3})["z"], Player().z)
        world.walk_support.assert_not_called()
        self.assertEqual(TERRAIN_SCENARIOS["stair_walk"]["y"], 41.5)

    def test_invalid_explicit_camera_is_rejected_instead_of_moved(self):
        world = Mock()
        world.collides.return_value = True
        with self.assertRaisesRegex(ValueError, "wall.*2, 3, 5"):
            resolve_camera(world, "wall", {"x": 2, "y": 3, "z": 5}, natural=True)
        world.surface_height.assert_not_called()
        world.walk_support.assert_not_called()


class PairReportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "ascii3d").mkdir()
        self.source = b"# frozen source\n"
        (self.root / "ascii3d" / "world.py").write_bytes(self.source)
        self.args = SimpleNamespace(before_source=self.root, save=self.root / "report.json", frames=4,
                                    width=120, height=40, audio=False, before_elevated_audio=True)
        self.scenes = {"first": {"x": 2, "y": 3}, "second": {"x": 4, "y": 3}}
        self.terrain = {"hill": {"x": 6, "y": 3}}
        self.prepared = []

    def state(self, label):
        world = SimpleNamespace(width=20, depth=20, height=10,
                                surface_height=lambda x, y: 1.2,
                                walk_support=lambda x, y, z: (1.25, 5),
                                collides=lambda x, y, z: False)
        return {"label": label, "world": world, "engine": {"player": SimpleNamespace(Player=Player)},
                "startup": {}, "renderer": SimpleNamespace(scenery=SimpleNamespace(stats={}))}

    def prepare(self, state, name, camera):
        self.prepared.append((state["label"], name, camera))
        state["timings"] = []

    def run_pair(self, frame, *, before=None, after=None, audio_factory=None):
        with patch.object(benchmark_pair, "SCENARIOS", self.scenes), \
                patch.object(benchmark_pair, "EXTRA_SCENARIOS", {}), \
                patch.object(benchmark_pair, "TERRAIN_SCENARIOS", self.terrain), \
                patch("sys.stdout", io.StringIO()):
            keywords = {"audio_factory": audio_factory} if audio_factory is not None else {}
            return benchmark_pair.run(self.args, before=before or self.state("before"),
                                      after=after or self.state("after"),
                                      prepare_scene=self.prepare, run_frame=frame, **keywords)

    @staticmethod
    def frame(state, name, audio, width, height, *, measured):
        if measured:
            state["timings"].append(10.0)

    def saved(self):
        return json.loads(self.args.save.read_text(encoding="utf-8"))

    def test_mid_scene_exception_keeps_prior_scene_and_partial_samples_with_source_hashes(self):
        def frame(state, name, audio, width, height, *, measured):
            if name == "second" and measured and state["label"] == "after" and state["timings"]:
                raise OSError("device disappeared")
            self.frame(state, name, audio, width, height, measured=measured)

        report = self.run_pair(frame)
        self.assertEqual(report, self.saved())
        self.assertEqual(report["status"], "incomplete")
        self.assertFalse(report["complete"] or report["passed"])
        self.assertEqual(report["before_hashes"][str(Path("ascii3d") / "world.py")],
                         hashlib.sha256(self.source).hexdigest())
        self.assertTrue(report["after_hashes"])
        first, second = report["scenarios"]["first"], report["scenarios"]["second"]
        self.assertEqual(first["status"], "complete")
        self.assertTrue(first["passed"])
        self.assertEqual(first["before"]["sample_count"], 4)
        self.assertEqual(second["status"], "incomplete")
        self.assertFalse(second["passed"])
        self.assertEqual(second["before"]["samples_ms"], [10.0])
        self.assertEqual(second["after"]["samples_ms"], [10.0])
        self.assertEqual(report["errors"][0], {"type": "OSError", "message": "device disappeared",
                                             "phase": "measurement", "scene": "second", "variant": "after"})
        self.assertEqual(report["new_scenarios"]["hill"]["status"], "pending")

    def test_completed_reports_apply_both_unchanged_gates_and_do_not_invent_terrain_comparisons(self):
        def frame(state, name, audio, width, height, *, measured):
            if measured:
                values = [10.0] * 4 if state["label"] == "before" else [10.0, 10.0, 10.0, 12.0]
                state["timings"].append(values[len(state["timings"])])

        report = self.run_pair(frame)
        self.assertTrue(report["complete"])
        self.assertFalse(report["passed"])
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["threshold_percent"], 15.0)
        self.assertEqual(report["scenarios"]["first"]["mean_change_percent"], 5.0)
        self.assertEqual(report["scenarios"]["first"]["p95_change_percent"], 20.0)
        self.assertFalse(report["scenarios"]["first"]["passed"])
        self.assertIsNone(report["new_scenarios"]["hill"]["passed"])
        self.assertEqual(report["new_scenarios"]["hill"]["camera"]["z"], 1.25)

    def test_complete_equal_measurements_pass_and_existing_report_is_never_overwritten(self):
        report = self.run_pair(self.frame)
        self.assertEqual((report["complete"], report["passed"], report["status"]), (True, True, "passed"))
        original = self.args.save.read_bytes()
        self.prepared.clear()
        with self.assertRaises(FileExistsError):
            self.run_pair(self.frame)
        self.assertEqual(self.args.save.read_bytes(), original)
        self.assertEqual(self.prepared, [])

    def test_preflight_rejects_late_camera_before_audio_or_any_timed_work(self):
        after = self.state("after")
        after["world"].collides = lambda x, y, z: x == 6
        audio = Mock()
        frame = Mock()
        self.args.audio = True
        report = self.run_pair(frame, after=after, audio_factory=audio)
        audio.assert_not_called()
        frame.assert_not_called()
        self.assertEqual(self.prepared, [])
        self.assertEqual(report["errors"][0]["phase"], "preflight")
        self.assertEqual(report["new_scenarios"]["hill"]["status"], "invalid_camera")
        self.assertFalse(report["complete"] or report["passed"])

    def test_audio_cleanup_error_keeps_measurements_and_last_health(self):
        audio = SimpleNamespace(available=True, blocks_rendered=20, underruns=0,
                                max_write_gap_ms=12.5, recoveries=0, error="")
        context = Mock()
        context.__enter__ = Mock(return_value=audio)
        context.__exit__ = Mock(side_effect=OSError("cleanup failed"))
        self.args.audio = True
        report = self.run_pair(self.frame, audio_factory=lambda **kwargs: context)
        self.assertEqual(report["audio_health"]["buffers"], 20)
        self.assertEqual(report["audio_health"]["max_write_gap_ms"], 12.5)
        self.assertEqual(report["scenarios"]["second"]["status"], "complete")
        self.assertEqual(report["errors"][0]["phase"], "audio_cleanup")
        self.assertFalse(report["complete"] or report["passed"])
        self.assertEqual(report, self.saved())

    def test_normal_audio_close_preserves_measured_availability_and_final_counters(self):
        audio = SimpleNamespace(available=True, blocks_rendered=20, underruns=0,
                                max_write_gap_ms=12.5, recoveries=0, error="")
        context = Mock()
        context.__enter__ = Mock(return_value=audio)

        def close(*args):
            audio.available = False
            audio.blocks_rendered = 21

        context.__exit__ = Mock(side_effect=close)
        self.args.audio = True
        report = self.run_pair(self.frame, audio_factory=lambda **kwargs: context)
        self.assertTrue(report["passed"])
        self.assertTrue(report["audio_health"]["available"])
        self.assertEqual(report["audio_health"]["buffers"], 21)
        self.assertFalse(report["audio_health_after_cleanup"]["available"])

    def test_unavailable_device_never_falls_back_to_an_accepted_silent_run(self):
        audio = SimpleNamespace(available=False, blocks_rendered=0, underruns=0,
                                max_write_gap_ms=0, recoveries=0, error="no output")
        context = Mock()
        context.__enter__ = Mock(return_value=audio)
        context.__exit__ = Mock()
        self.args.audio = True
        frame = Mock()
        report = self.run_pair(frame, audio_factory=lambda **kwargs: context)
        frame.assert_not_called()
        context.__exit__.assert_called_once()
        self.assertIn("audio_health", report["failed"])
        self.assertEqual(report["audio_health"]["error"], "no output")
        self.assertFalse(report["complete"] or report["passed"])


if __name__ == "__main__":
    unittest.main()
