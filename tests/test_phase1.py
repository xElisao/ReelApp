"""Regressionstests ohne echte Videos/API-Aufrufe.

Ausführen: python -m unittest discover -s tests -v
"""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from highlight_models import (
    HighlightCandidate,
    HighlightScores,
    validate_candidate,
    validate_cut_plan,
)
from video_probe import VideoProbeError, probe_video


def make_candidate(start=1.0, end=3.0, source_id="video-1"):
    return HighlightCandidate(
        source_id=source_id,
        start_seconds=start,
        end_seconds=end,
        category="general",
        summary="Interessante Passage",
        reason="Sichtbare Handlung",
        scores=HighlightScores(4, 5, 3, 2),
        confidence=0.8,
    )


class HighlightModelTests(unittest.TestCase):
    def test_score_computation(self):
        self.assertEqual(HighlightScores(5, 5, 5, 5).total_out_of_100, 100)
        self.assertEqual(HighlightScores(0, 0, 0, 0).total_out_of_100, 0)

    def test_bad_timestamp_rejected(self):
        for start, end in [(-1, 2), (3, 3), (4, 1), (float("nan"), 2)]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                make_candidate(start, end)

    def test_unknown_source_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unbekannte"):
            validate_candidate(make_candidate(), {"other": 10})

    def test_end_beyond_video_rejected(self):
        with self.assertRaisesRegex(ValueError, "endet"):
            validate_candidate(make_candidate(end=11), {"video-1": 10})

    def test_overlapping_clips_rejected(self):
        with self.assertRaisesRegex(ValueError, "Überlappende"):
            validate_cut_plan(
                [make_candidate(0, 3), make_candidate(2, 5)],
                {"video-1": 10},
                target_duration_seconds=15,
            )

    def test_budget_rejected(self):
        with self.assertRaisesRegex(ValueError, "Zielmaximum"):
            validate_cut_plan(
                [make_candidate(0, 4), make_candidate(4, 7)],
                {"video-1": 10},
                target_duration_seconds=6,
            )

    def test_valid_plan(self):
        validate_cut_plan(
            [make_candidate(0, 2), make_candidate(4, 6)],
            {"video-1": 10},
            target_duration_seconds=5,
        )

    def test_empty_plan_rejected(self):
        with self.assertRaises(ValueError):
            validate_cut_plan([], {"video-1": 10}, target_duration_seconds=15)


class VideoProbeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.file = Path(self.directory.name) / "test.mp4"
        self.file.write_bytes(b"dummy input (ffprobe mocked)")

    def tearDown(self):
        self.directory.cleanup()

    @patch("video_probe.shutil.which", return_value="/usr/bin/ffprobe")
    @patch("video_probe.subprocess.run")
    def test_valid_metadata(self, mocked_run, _mocked_which):
        mocked_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout=json.dumps({
                "format": {"duration": "15.5"},
                "streams": [
                    {"codec_type": "video", "width": 1920, "height": 1080,
                     "avg_frame_rate": "30000/1001", "codec_name": "h264"},
                    {"codec_type": "audio", "codec_name": "aac"},
                ],
            }),
            stderr="",
        )
        result = probe_video(self.file, source_id="video-1")
        self.assertEqual(result.duration_seconds, 15.5)
        self.assertEqual((result.width, result.height), (1920, 1080))
        self.assertTrue(result.has_audio)
        self.assertAlmostEqual(result.fps, 29.97, places=2)

    @patch("video_probe.shutil.which", return_value="/usr/bin/ffprobe")
    @patch("video_probe.subprocess.run")
    def test_missing_video_stream_rejected(self, mocked_run, _mocked_which):
        mocked_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"streams": [], "format": {"duration": "8"}}', stderr=""
        )
        with self.assertRaisesRegex(VideoProbeError, "Videospur"):
            probe_video(self.file, source_id="video-1")

    @patch("video_probe.shutil.which", return_value=None)
    def test_ffprobe_missing(self, _mocked_which):
        with self.assertRaisesRegex(VideoProbeError, "FFmpeg"):
            probe_video(self.file, source_id="video-1")

    def test_nonexistent_file(self):
        with self.assertRaisesRegex(VideoProbeError, "existiert nicht"):
            probe_video(self.file.with_name("does-not-exist.mp4"), source_id="video-1")


if __name__ == "__main__":
    unittest.main()
