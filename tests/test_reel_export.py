"""Tests für den kostenlosen, stummen 9:16-Test-Reel-Export."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reel_export import ReelExportError, ReelSegment, render_test_reel, validate_reel_segments


FAKE_MP4 = b"\x00\x00\x00\x18ftypisom0000"


def segment(source, start, end, data=FAKE_MP4):
    return ReelSegment(source, start, end, data)


class ReelExportValidationTests(unittest.TestCase):
    def test_two_distinct_clips_can_be_combined(self):
        self.assertEqual(
            validate_reel_segments([
                segment("video-1", 10.5, 13.5),
                segment("video-1", 19.5, 22.5),
            ]),
            6.0,
        )

    def test_requires_two_to_three_clips(self):
        with self.assertRaisesRegex(ReelExportError, "2 bis 3"):
            validate_reel_segments([segment("video-1", 0, 3)])
        with self.assertRaisesRegex(ReelExportError, "2 bis 3"):
            validate_reel_segments([segment("video-1", i * 3, i * 3 + 2)
                                    for i in range(4)])

    def test_rejects_same_source_overlap(self):
        with self.assertRaisesRegex(ReelExportError, "überlappen"):
            validate_reel_segments([
                segment("video-1", 0, 3),
                segment("video-1", 2.5, 5.5),
            ])

    def test_two_sources_can_share_timestamps(self):
        self.assertAlmostEqual(validate_reel_segments([
            segment("video-1", 0, 3),
            segment("video-2", 0, 3),
        ]), 6.0)

    def test_rejects_nan_bool_and_negative_intervals(self):
        bad_intervals = [
            (float("nan"), 3), (0, float("inf")), (True, 3),
            (-1, 2), (4, 4), (5, 2), (0, 12),
        ]
        for start, end in bad_intervals:
            with self.subTest(start=start, end=end), self.assertRaises(ReelExportError):
                validate_reel_segments([
                    segment("video-1", start, end),
                    segment("video-2", 0, 2),
                ])

    def test_rejects_bogus_mp4_and_oversize(self):
        for content in (b"", b"not a video", b"x" * (10 * 1024 * 1024 + 1)):
            with self.subTest(length=len(content)), self.assertRaises(ReelExportError):
                validate_reel_segments([
                    segment("video-1", 0, 2, content),
                    segment("video-2", 0, 2),
                ])

    @patch("reel_export.shutil.which", return_value=None)
    def test_missing_ffmpeg_is_reported_without_openai(self, _):
        with self.assertRaisesRegex(ReelExportError, "FFmpeg"):
            render_test_reel([
                segment("video-1", 0, 2),
                segment("video-2", 0, 2),
            ])

    @patch("reel_export.subprocess.run")
    def test_invalid_timeout_fails_before_ffmpeg(self, run):
        with self.assertRaisesRegex(ReelExportError, "Zeitlimit"):
            render_test_reel([
                segment("video-1", 0, 2),
                segment("video-2", 0, 2),
            ], timeout_seconds=0)
        run.assert_not_called()


class ReelExportFFmpegTests(unittest.TestCase):
    @unittest.skipUnless(
        shutil.which("ffmpeg") and shutil.which("ffprobe"),
        "FFmpeg/ffprobe nicht installiert",
    )
    def test_actual_video_contains_two_clips_in_vertical_mp4_without_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            samples = []
            for i, (color, size, seconds) in enumerate([
                ("red", "160x90", 1.5),
                ("green", "90x160", 1.5),
            ]):
                source = folder / f"source_{i}.mp4"
                command = [
                    shutil.which("ffmpeg"), "-hide_banner", "-nostdin",
                    "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i",
                    f"color=c={color}:s={size}:r=24:d={seconds}",
                    "-an", "-c:v", "mpeg4", "-q:v", "4", str(source),
                ]
                completed = subprocess.run(
                    command, capture_output=True, timeout=30, check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                samples.append(source.read_bytes())

            output = render_test_reel([
                segment("video-1", 0, 1.5, samples[0]),
                segment("video-2", 0, 1.5, samples[1]),
            ])
            self.assertTrue(output[4:8] == b"ftyp")
            output_path = folder / "final.mp4"
            output_path.write_bytes(output)

            inspected = subprocess.run(
                [
                    shutil.which("ffprobe"), "-v", "error",
                    "-show_entries",
                    "stream=codec_type,codec_name,width,height:"
                    "format=duration",
                    "-of", "json", str(output_path),
                ],
                capture_output=True, text=True, timeout=20, check=False,
            )
            self.assertEqual(inspected.returncode, 0, inspected.stderr)
            data = json.loads(inspected.stdout)
            videos = [x for x in data["streams"] if x["codec_type"] == "video"]
            audios = [x for x in data["streams"] if x["codec_type"] == "audio"]
            self.assertEqual(len(videos), 1)
            self.assertEqual(len(audios), 0)
            self.assertEqual(videos[0]["codec_name"], "h264")
            self.assertEqual((videos[0]["width"], videos[0]["height"]), (540, 960))
            self.assertAlmostEqual(float(data["format"]["duration"]), 3.0, delta=0.15)


if __name__ == "__main__":
    unittest.main()
