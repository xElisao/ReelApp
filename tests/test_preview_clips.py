"""Offline-Tests der Clip-Vorschau; keine OpenAI-API-Aufrufe."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from preview_clips import (
    MAX_PREVIEWS,
    PreviewError,
    pick_suggestions,
    render_report_previews,
)
from video_probe import VideoMetadata


def _metadata(path="/test/sample.mp4", duration=9.376033):
    return VideoMetadata(
        source_id="video-1", path=path, duration_seconds=duration,
        width=1920, height=1080, fps=30, has_audio=False,
        video_codec="h264",
    )


def _report(suggestions):
    return {
        "video_count": 1,
        "refinement": {"suggestions": suggestions},
    }


def _suggestion(start=4.376033, end=7.376033):
    return {
        "source_id": "video-1",
        "start_seconds": start,
        "end_seconds": end,
        "summary": "Motorräder im Bergpanorama",
        "score": 72.38,
    }


class PreviewSelectionTests(unittest.TestCase):
    def test_prefers_fine_suggestions(self):
        report = {
            "video_count": 1,
            "recommendations": [_suggestion(0, 8)],
            "refinement": {"suggestions": [_suggestion()]},
        }
        self.assertEqual(pick_suggestions(report)[0]["start_seconds"], 4.376033)

    def test_limits_preview_count(self):
        selections = [_suggestion(i, i + 1) for i in range(8)]
        self.assertEqual(len(pick_suggestions(_report(selections))), MAX_PREVIEWS)

    def test_bad_refinement_rejected(self):
        with self.assertRaises(PreviewError):
            pick_suggestions({"refinement": {"suggestions": "broken"}})

    @patch("preview_clips.probe_video")
    @patch("preview_clips._render_mp4", return_value=b"preview")
    def test_replays_existing_report_without_ai(self, render, probe):
        probe.return_value = _metadata()
        clips = render_report_previews(
            [Path("/test/sample.mp4")],
            _report([_suggestion()]),
        )
        self.assertEqual(len(clips), 1)
        self.assertEqual(clips[0].start_seconds, 4.376033)
        self.assertEqual(clips[0].mp4_bytes, b"preview")
        render.assert_called_once()

    @patch("preview_clips.fingerprint_window")
    @patch("preview_clips.extract_frame_cache")
    @patch("preview_clips.probe_video")
    @patch("preview_clips._render_mp4", return_value=b"mp4 bytes")
    def test_saved_scenic_json_marks_same_camera_view_without_ai(
        self, render, probe, extract, fingerprint,
    ):
        probe.return_value = _metadata()
        extract.return_value = object()
        fingerprint.return_value = ((123, 456), (123, 456), (123, 456))
        report = _report([_suggestion(0, 3), _suggestion(4.376033, 7.376033)])
        report["goal"] = {"style": "scenic", "focus_tags": ["scenery"]}
        clips = render_report_previews([Path("/test/sample.mp4")], report)
        self.assertEqual(len(clips), 2)
        self.assertIsNone(clips[0].similar_view_as)
        self.assertEqual(clips[1].similar_view_as, 1)
        self.assertEqual(render.call_count, 2)
        self.assertEqual(extract.call_count, 1)

    @patch("preview_clips.fingerprint_window")
    @patch("preview_clips.extract_frame_cache")
    @patch("preview_clips.probe_video")
    @patch("preview_clips._render_mp4", return_value=b"mp4 bytes")
    def test_saved_action_json_keeps_distinct_moments(
        self, render, probe, extract, fingerprint,
    ):
        probe.return_value = _metadata()
        report = _report([_suggestion(0, 3), _suggestion(4.376033, 7.376033)])
        report["goal"] = {"style": "action", "focus_tags": ["motorcycle"]}
        clips = render_report_previews([Path("/test/sample.mp4")], report)
        self.assertEqual(len(clips), 2)
        self.assertIsNone(clips[1].similar_view_as)
        extract.assert_not_called()
        fingerprint.assert_not_called()

    @patch("preview_clips.detect_hard_cuts", return_value=(8.0, 18.0, 24.0))
    @patch("preview_clips.probe_video")
    @patch("preview_clips._render_mp4", return_value=b"preview")
    def test_old_report_skips_mixed_motorrad_clip_without_ai(
        self, render, probe, detect,
    ):
        probe.return_value = _metadata(duration=32.0)
        report = _report([
            _suggestion(10.5, 13.5),
            _suggestion(19.5, 22.5),
            _suggestion(22.5, 25.5),
        ])
        clips = render_report_previews([Path("/test/sample.mp4")], report)
        self.assertEqual(len(clips), 2)
        self.assertEqual(render.call_count, 2)
        self.assertEqual([c.start_seconds for c in clips], [10.5, 19.5])
        detect.assert_called_once()

    @patch("preview_clips.detect_hard_cuts", return_value=(8.0, 18.0, 24.0))
    @patch("preview_clips.probe_video")
    @patch("preview_clips._render_mp4", return_value=b"preview")
    def test_shot_start_on_cut_allowed(self, render, probe, detect):
        probe.return_value = _metadata(duration=32.0)
        report = _report([_suggestion(8.0, 11.0)])
        clips = render_report_previews([Path("/test/sample.mp4")], report)
        self.assertEqual(len(clips), 1)
        render.assert_called_once()

    @patch("preview_clips.probe_video")
    @patch("preview_clips._render_mp4")
    def test_wrong_video_length_is_rejected(self, render, probe):
        probe.return_value = _metadata(duration=5)
        with self.assertRaisesRegex(PreviewError, "außerhalb"):
            render_report_previews(
                [Path("/test/sample.mp4")], _report([_suggestion()])
            )
        render.assert_not_called()

    @patch("preview_clips.probe_video")
    @patch("preview_clips._render_mp4")
    def test_report_video_count_mismatch_rejected(self, render, probe):
        with self.assertRaisesRegex(PreviewError, "Anzahl"):
            render_report_previews(
                [Path("/test/sample.mp4")],
                {"video_count": 2, "recommendations": []},
            )
        render.assert_not_called()
        probe.assert_not_called()

    @patch("preview_clips.probe_video")
    @patch("preview_clips._render_mp4")
    def test_long_clip_rejected(self, render, probe):
        probe.return_value = _metadata(duration=50)
        with self.assertRaisesRegex(PreviewError, "länger"):
            render_report_previews(
                [Path("/test/sample.mp4")],
                _report([_suggestion(0, 30)]),
            )
        render.assert_not_called()

    @patch("preview_clips.probe_video")
    @patch("preview_clips._render_mp4")
    def test_unknown_source_rejected(self, render, probe):
        probe.return_value = _metadata()
        item = _suggestion()
        item["source_id"] = "../../server"
        with self.assertRaisesRegex(PreviewError, "unbekannt"):
            render_report_previews(
                [Path("/test/sample.mp4")], _report([item])
            )
        render.assert_not_called()

    @patch("preview_clips.probe_video")
    @patch("preview_clips._render_mp4")
    def test_nan_and_boolean_times_rejected(self, render, probe):
        probe.return_value = _metadata()
        for start in (float("nan"), True, "3.0"):
            with self.subTest(start=start), self.assertRaises(PreviewError):
                render_report_previews(
                    [Path("/test/sample.mp4")],
                    _report([_suggestion(start, 3)]),
                )
        render.assert_not_called()


class ActualFFmpegPreviewTests(unittest.TestCase):
    @unittest.skipUnless(
        shutil.which("ffmpeg") and shutil.which("ffprobe"),
        "FFmpeg/ffprobe not installed",
    )
    def test_render_synthetic_video_without_openai(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "generated.mp4"
            result = subprocess.run(
                [
                    shutil.which("ffmpeg"), "-hide_banner", "-nostdin",
                    "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=25",
                    "-t", "4", "-an", "-c:v", "mpeg4", str(source),
                ],
                capture_output=True, timeout=30, check=False,
            )
            if result.returncode != 0:
                self.fail(f"FFmpeg source fixture failed: {result.stderr!r}")
            report = _report([_suggestion(0.5, 2.5)])
            clips = render_report_previews([source], report)
            self.assertEqual(len(clips), 1)
            self.assertTrue(clips[0].mp4_bytes)
            self.assertLessEqual(len(clips[0].mp4_bytes), 10 * 1024 * 1024)
            # MP4 magic: ftyp box in file header.
            self.assertEqual(clips[0].mp4_bytes[4:8], b"ftyp")


if __name__ == "__main__":
    unittest.main()
