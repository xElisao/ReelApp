"""Offline-Tests der bildgestützten Zeitleiste, ohne OpenAI-API."""

from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from timeline_frames import (
    THUMB_COUNT, TimelineError, render_storyboard,
    selected_slider_interval, storyboard_timestamps, timeline_bounds,
)


class TimelineHelperTests(unittest.TestCase):
    def test_landscape_clip_window_near_ai_proposal(self):
        self.assertEqual(timeline_bounds(10.5, 13.5, 32), (6.5, 17.5))
        self.assertEqual(timeline_bounds(19.5, 22.5, 32), (15.5, 26.5))

    def test_window_never_passes_actual_video_start_or_end(self):
        self.assertEqual(timeline_bounds(0.5, 3.5, 8), (0.0, 7.5))
        self.assertEqual(timeline_bounds(5.0, 7.5, 8), (1.0, 8.0))

    def test_frame_times_are_sorted_inside_range(self):
        times = storyboard_timestamps(6.5, 17.5)
        self.assertEqual(len(times), THUMB_COUNT)
        self.assertEqual(times, tuple(sorted(times)))
        self.assertGreater(times[0], 6.5)
        self.assertLess(times[-1], 17.5)

    def test_subframe_ai_timestamp_is_not_changed_merely_by_slider_rounding(self):
        self.assertEqual(
            selected_slider_interval(
                (4.38, 7.38), (4.376033, 7.376033)
            ),
            (4.376033, 7.376033),
        )

    def test_intentional_trim_is_kept(self):
        self.assertEqual(
            selected_slider_interval(
                (10.5, 14.0), (10.5, 13.5)
            ),
            (10.5, 14.0),
        )

    def test_rejects_nonfinite_or_invalid_ranges(self):
        for args in [
            (0, 3, 0), (-1, 3, 10), (3, 2, 10),
            (0, 5, 4), (0, 3, 61),
            (float("nan"), 3, 10),
            (True, 3, 10),
        ]:
            with self.subTest(args=args), self.assertRaises(TimelineError):
                timeline_bounds(*args)
        with self.assertRaises(TimelineError):
            storyboard_timestamps(5, 5)
        with self.assertRaises(TimelineError):
            storyboard_timestamps(0, 4, count=12)
        with self.assertRaises(TimelineError):
            selected_slider_interval(
                (0, float("nan")), (0, 2)
            )

    def test_invalid_video_file_is_rejected(self):
        with self.assertRaisesRegex(TimelineError, "nicht verfügbar"):
            render_storyboard(
                Path("/unavailable/test.mp4"),
                low=0, high=5, duration_seconds=5,
            )

    @patch("timeline_frames.shutil.which", return_value=None)
    def test_missing_ffmpeg_is_reported(self, _):
        with tempfile.TemporaryDirectory() as directory:
            dummy = Path(directory) / "file.mp4"
            dummy.write_bytes(b"just bytes")
            with self.assertRaisesRegex(TimelineError, "FFmpeg"):
                render_storyboard(dummy, low=0, high=2, duration_seconds=2)


class TimelineFFmpegTests(unittest.TestCase):
    @unittest.skipUnless(
        shutil.which("ffmpeg") and shutil.which("ffprobe"),
        "FFmpeg/ffprobe fehlt",
    )
    def test_original_video_creates_seven_labeled_frames_in_correct_order(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "colors.mp4"
            command = [
                shutil.which("ffmpeg"), "-hide_banner", "-nostdin",
                "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=c=red:s=160x90:r=24:d=4",
                "-f", "lavfi", "-i", "color=c=green:s=160x90:r=24:d=4",
                "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
                "-map", "[v]", "-c:v", "mpeg4", "-q:v", "4",
                str(path),
            ]
            done = subprocess.run(
                command, capture_output=True, timeout=30, check=False,
            )
            self.assertEqual(done.returncode, 0, done.stderr)

            image_bytes = render_storyboard(
                path, low=0.0, high=8.0, duration_seconds=8.0
            )
            self.assertLess(len(image_bytes), 800_000)
            with Image.open(io.BytesIO(image_bytes)) as sheet:
                sheet.load()
                self.assertEqual(sheet.size, (THUMB_COUNT * 150, 107))
                left = sheet.getpixel((75, 40))
                right = sheet.getpixel((6 * 150 + 75, 40))
                # Red is on the left, green on the right.  Image colors
                # are from extracted source frames, not placeholders.
                self.assertGreater(left[0], left[1] + 80)
                self.assertGreater(right[1], right[0] + 45)

    @unittest.skipUnless(
        shutil.which("ffmpeg"), "FFmpeg fehlt"
    )
    def test_storyboard_stays_in_bounds_near_video_end(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "short.mp4"
            command = [
                shutil.which("ffmpeg"), "-hide_banner", "-nostdin",
                "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=24:d=2",
                "-c:v", "mpeg4", "-an", str(path),
            ]
            done = subprocess.run(
                command, capture_output=True, timeout=30, check=False,
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            low, high = timeline_bounds(0.25, 1.75, 2.0)
            jpeg = render_storyboard(
                path, low=low, high=high, duration_seconds=2.0
            )
            self.assertTrue(jpeg.startswith(b"\xff\xd8"))


if __name__ == "__main__":
    unittest.main()
