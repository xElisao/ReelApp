"""Offline-Tests: keine echten API-Aufrufe, keine Videodateien erforderlich."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from candidate_windows import CandidateWindow, generate_candidate_windows
from frame_sampler import FrameSampleError, SampledFrame, sample_window_frames
from highlight_analyzer import HighlightAnalysisError, analyze_video, evaluate_window
from video_probe import VideoMetadata


class WindowTests(unittest.TestCase):
    def test_short_video_one_window(self):
        windows = generate_candidate_windows("v1", 3)
        self.assertEqual([(w.start_seconds, w.end_seconds) for w in windows], [(0, 3)])

    def test_entire_timeline_covered(self):
        windows = generate_candidate_windows("v1", 60)
        self.assertEqual(windows[0].start_seconds, 0)
        self.assertEqual(windows[-1].end_seconds, 60)
        self.assertLessEqual(len(windows), 12)
        for earlier, later in zip(windows, windows[1:]):
            self.assertLessEqual(later.start_seconds, earlier.end_seconds)

    def test_too_many_windows_is_error(self):
        with self.assertRaisesRegex(ValueError, "Zu viele"):
            generate_candidate_windows("v1", 1000)

    def test_invalid_stride(self):
        with self.assertRaises(ValueError):
            generate_candidate_windows("v1", 20, window_seconds=3, stride_seconds=4)


class FrameSamplerTests(unittest.TestCase):
    @patch("frame_sampler.shutil.which", return_value="/usr/bin/ffmpeg")
    @patch("frame_sampler.subprocess.run")
    def test_extracts_three_jpegs_at_known_times(self, mocked_run, _):
        mocked_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=b"\xff\xd8dummy\xff\xd9", stderr=b""
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.mp4"
            path.write_bytes(b"mock")
            result = sample_window_frames(path, CandidateWindow("v1", 2, 10))
        self.assertEqual(len(result), 3)
        self.assertEqual([f.timestamp_seconds for f in result], [4, 6, 8])
        self.assertEqual(mocked_run.call_count, 3)

    @patch("frame_sampler.shutil.which", return_value=None)
    def test_missing_ffmpeg_fails(self, _):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.mp4"
            path.write_bytes(b"mock")
            with self.assertRaises(FrameSampleError):
                sample_window_frames(path, CandidateWindow("v1", 0, 2))


class AnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.metadata = VideoMetadata(
            source_id="v1", path="/fake/video.mp4",
            duration_seconds=20.0, width=1920, height=1080, fps=30.0,
            has_audio=True, video_codec="h264",
        )
        self.client = Mock()
        self.client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
                "summary": "Aussicht auf ein Tal",
                "reason": "Interessante Bildkomposition",
                "scores": {
                    "relevance": 5, "impact": 4,
                    "technical_quality": 4, "variety": 3,
                },
            })))]
        )

    def test_real_frame_payload_included(self):
        result = evaluate_window(
            self.client, self.metadata,
            CandidateWindow("v1", 2, 10), niche="travel_outdoor",
            frames=[SampledFrame(4, b"fake-jpeg")],
        )
        self.assertEqual(result.start_seconds, 2)
        self.assertEqual(result.end_seconds, 10)
        self.assertEqual(result.summary, "Aussicht auf ein Tal")
        self.assertEqual(result.scores.variety, 3)
        call = self.client.chat.completions.create.call_args
        content = call.kwargs["messages"][1]["content"]
        self.assertTrue(any(item.get("type") == "image_url" for item in content))

    def test_bad_json_fails_not_falls_back(self):
        self.client.chat.completions.create.return_value.choices[0].message.content = "oops"
        with self.assertRaises(HighlightAnalysisError):
            evaluate_window(
                self.client, self.metadata, CandidateWindow("v1", 2, 10),
                niche="general", frames=[SampledFrame(5, b"img")]
            )

    def test_unknown_niche_fails(self):
        with self.assertRaises(ValueError):
            evaluate_window(
                self.client, self.metadata, CandidateWindow("v1", 2, 10),
                niche="not-a-niche", frames=[SampledFrame(5, b"img")]
            )

    def test_long_video_rejected_before_api(self):
        big = VideoMetadata(
            source_id="v1", path="/fake/video.mp4",
            duration_seconds=120, width=1920, height=1080, fps=30,
            has_audio=False, video_codec="h264",
        )
        with self.assertRaisesRegex(ValueError, "maximal"):
            analyze_video(self.client, big, niche="general")
        self.client.chat.completions.create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
