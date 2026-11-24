"""Kostenlose technische Staging-Video-Prüfung ohne OpenAI-API."""

import unittest
from pathlib import Path
from unittest.mock import patch

from staging_preflight import VideoPreflightError, inspect_videos
from video_probe import VideoMetadata


def fake_metadata(source_id="video-1", duration=9.4):
    return VideoMetadata(
        source_id=source_id,
        path="/tmp/example.mp4",
        duration_seconds=duration,
        width=1920, height=1080,
        fps=30.0, has_audio=False, video_codec="h264",
    )


class PreflightTests(unittest.TestCase):
    @patch("staging_preflight.probe_video")
    def test_short_video_reports_duration(self, probe):
        probe.return_value = fake_metadata(duration=9.4)
        result = inspect_videos([Path("source.mp4")])
        self.assertEqual(result[0].duration_seconds, 9.4)
        probe.assert_called_once_with(Path("source.mp4"), source_id="video-1")

    @patch("staging_preflight.probe_video")
    def test_long_video_explains_60_second_limit(self, probe):
        probe.return_value = fake_metadata(duration=85.6)
        with self.assertRaisesRegex(VideoPreflightError, "85.6 Sekunden"):
            inspect_videos([Path("source.mp4")])

    @patch("staging_preflight.probe_video")
    def test_two_videos_keep_correct_source_numbers(self, probe):
        def make_metadata(path, source_id):
            return fake_metadata(source_id=source_id, duration=9.4)
        probe.side_effect = make_metadata
        result = inspect_videos([Path("a.mp4"), Path("b.mp4")])
        self.assertEqual([x.source_id for x in result], ["video-1", "video-2"])

    @patch("staging_preflight.probe_video")
    def test_three_long_videos_exceed_analysis_budget(self, probe):
        def make_metadata(path, source_id):
            return fake_metadata(source_id=source_id, duration=59.8)
        probe.side_effect = make_metadata
        with self.assertRaisesRegex(VideoPreflightError, "24 insgesamt"):
            inspect_videos([Path("1.mp4"), Path("2.mp4"), Path("3.mp4")])

    @patch("staging_preflight.probe_video")
    def test_zero_uploaded_videos_rejected(self, probe):
        with self.assertRaisesRegex(VideoPreflightError, "1 bis 3"):
            inspect_videos([])
        probe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
