"""Offline-Tests für die zweite, dichtere Analyse."""

import unittest
from unittest.mock import patch

from adaptive_refinement import fine_windows, refine_for_goal
from candidate_windows import CandidateWindow
from content_understanding import SceneObservation
from user_goals import EditingGoal
from video_probe import VideoMetadata


def _scene(start, end, tags, categories=("motorcycle_action",), impact=3):
    return SceneObservation(
        window=CandidateWindow("v1", start, end),
        categories=tuple(categories),
        visual_tags=tuple(tags),
        summary="Testszene",
        evidence="Relevante sichtbare Objekte",
        impact=impact,
        technical_quality=4,
    )


class FineWindowsTests(unittest.TestCase):
    def test_covers_both_ends_without_gaps(self):
        windows = fine_windows(CandidateWindow("v1", 2.0, 10.0))
        self.assertEqual(windows[0].start_seconds, 2)
        self.assertEqual(windows[-1].end_seconds, 10)
        self.assertEqual(len(windows), 5)
        for previous, current in zip(windows, windows[1:]):
            self.assertLessEqual(current.start_seconds, previous.end_seconds)
            self.assertGreaterEqual(current.start_seconds, 2)

    def test_short_scene_stays_short(self):
        windows = fine_windows(CandidateWindow("v1", 0.0, 1.2))
        self.assertEqual(len(windows), 1)
        self.assertAlmostEqual(windows[0].end_seconds, 1.2)

    def test_invalid_stride_is_rejected(self):
        with self.assertRaises(ValueError):
            fine_windows(CandidateWindow("v1", 0, 8), window_seconds=2, stride_seconds=3)


class RefineTests(unittest.TestCase):
    def setUp(self):
        self.metadata = {
            "v1": VideoMetadata(
                "v1", "/sample/video.mp4", 12.0, 1920, 1080, 30,
                False, "h264"
            )
        }
        self.coarse = [
            _scene(0, 8, ("motorcycle",), impact=4),
            _scene(4, 12, ("motorcycle", "scenery"), impact=3),
        ]

    @patch("adaptive_refinement.observe_window")
    def test_detail_pass_finds_curve_not_seen_coarsely(self, observe):
        def fake_observe(_client, _metadata, window, *, model):
            tags = ("motorcycle", "cornering") if window.start_seconds <= 3 else ("scenery",)
            return _scene(window.start_seconds, window.end_seconds, tags)
        observe.side_effect = fake_observe
        result = refine_for_goal(
            object(), self.metadata, self.coarse,
            EditingGoal("Zeig Kurven", style="action", focus_tags=("cornering",)),
        )
        self.assertGreater(result.inspected_windows, 0)
        self.assertGreater(len(result.scenes), 0)
        self.assertIn("cornering", result.scenes[0].observation.visual_tags)

    @patch("adaptive_refinement.observe_window")
    def test_same_video_different_goals(self, observe):
        def fake_observe(_client, _metadata, window, *, model):
            tags = ("motorcycle", "cornering") if window.start_seconds < 4 else ("scenery", "mountains")
            return _scene(window.start_seconds, window.end_seconds, tags)
        observe.side_effect = fake_observe
        action = refine_for_goal(
            object(), self.metadata, self.coarse,
            EditingGoal("Kurven", style="action", focus_tags=("cornering",)),
        )
        scenic = refine_for_goal(
            object(), self.metadata, self.coarse,
            EditingGoal("Berglandschaften", style="scenic", focus_tags=("mountains",)),
        )
        self.assertNotEqual(
            action.scenes[0].observation.window.start_seconds,
            scenic.scenes[0].observation.window.start_seconds,
        )

    @patch("adaptive_refinement.observe_window")
    def test_missing_required_event_not_faked(self, observe):
        observe.side_effect = lambda _client, _metadata, window, *, model: _scene(
            window.start_seconds, window.end_seconds, ("motorcycle",)
        )
        result = refine_for_goal(
            object(), self.metadata, self.coarse,
            EditingGoal("Zeig einen Wheelie", required_tags=("wheelie",)),
        )
        self.assertEqual(result.scenes, ())
        self.assertIn("wheelie", result.notice)

    @patch("adaptive_refinement.observe_window")
    def test_unsearched_coarse_windows_disclosed(self, observe):
        observe.side_effect = lambda _client, _metadata, window, *, model: _scene(
            window.start_seconds, window.end_seconds, ("motorcycle",)
        )
        scenes = [
            _scene(0, 4, ("motorcycle",)),
            _scene(4, 8, ("motorcycle",)),
            _scene(8, 12, ("motorcycle",)),
        ]
        result = refine_for_goal(
            object(), self.metadata, scenes,
            EditingGoal("", style="balanced"), max_coarse_windows=2,
        )
        self.assertFalse(result.inspected_all_coarse_windows)
        self.assertIn("beschränkt", result.notice)

    @patch("adaptive_refinement.observe_window")
    def test_budget_raises_before_any_model_call(self, observe):
        with self.assertRaisesRegex(ValueError, "Budget"):
            refine_for_goal(
                object(), self.metadata, self.coarse, EditingGoal(""),
                max_fine_windows=3,
            )
        observe.assert_not_called()

    def test_bad_metadata_rejected(self):
        with self.assertRaisesRegex(ValueError, "ohne Video-Metadaten"):
            refine_for_goal(
                object(), {}, self.coarse, EditingGoal(""),
            )


if __name__ == "__main__":
    unittest.main()
