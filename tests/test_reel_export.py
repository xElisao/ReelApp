"""Offline-Tests für 9:16-Test-Reels: stumm oder mit Originalton."""

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

    @patch("reel_export.subprocess.run")
    def test_only_known_background_modes_allowed(self, run):
        with self.assertRaisesRegex(ReelExportError, "Hintergrundmodus"):
            render_test_reel([
                segment("video-1", 0, 2),
                segment("video-2", 0, 2),
            ], background_mode="arbitrary_ffmpeg_expression")
        run.assert_not_called()

    @patch("reel_export.subprocess.run")
    def test_audio_mode_is_explicitly_whitelisted(self, run):
        with self.assertRaisesRegex(ReelExportError, "Tonmodus"):
            render_test_reel([
                segment("video-1", 0, 2),
                segment("video-2", 0, 2),
            ], audio_mode="automatically_guess_audio")
        run.assert_not_called()

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

            # Die breite rote 16:9-Aufnahme liegt scharf in der Mitte.
            # Der neue Standard füllt die obere linke Ecke ebenfalls mit
            # roten Bilddaten statt mit einem schwarzen Balken.
            def sample_corner(file_path):
                cmd = [
                    shutil.which("ffmpeg"), "-hide_banner", "-nostdin",
                    "-loglevel", "error", "-ss", "0.5",
                    "-i", str(file_path), "-frames:v", "1",
                    "-vf", "crop=2:2:0:0,format=rgb24",
                    "-f", "rawvideo", "pipe:1",
                ]
                process = subprocess.run(
                    cmd, capture_output=True, timeout=20, check=False,
                )
                self.assertEqual(process.returncode, 0, process.stderr)
                self.assertGreaterEqual(len(process.stdout), 3)
                return tuple(process.stdout[:3])

            blurred_corner = sample_corner(output_path)
            self.assertGreater(blurred_corner[0], 80, blurred_corner)
            self.assertGreater(
                blurred_corner[0], blurred_corner[1] + 60, blurred_corner
            )

            # Bisherige schwarze Balken bleiben bewusst optional.
            letterboxed = render_test_reel([
                segment("video-1", 0, 1.5, samples[0]),
                segment("video-2", 0, 1.5, samples[1]),
            ], background_mode="black")
            old_path = folder / "letterbox.mp4"
            old_path.write_bytes(letterboxed)
            black_corner = sample_corner(old_path)
            self.assertTrue(all(channel < 25 for channel in black_corner), black_corner)


class ReelAudioFFmpegTests(unittest.TestCase):
    @unittest.skipUnless(
        shutil.which("ffmpeg") and shutil.which("ffprobe"),
        "FFmpeg/ffprobe nicht installiert",
    )
    def test_original_audio_can_be_enabled_and_silent_clips_remain_in_place(self):
        """Ein tonhaltiger Clip + ein stummer Clip dürfen nicht verrutschen."""
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            first = folder / "with_audio.mp4"
            second = folder / "without_audio.mp4"
            commands = [
                [
                    shutil.which("ffmpeg"), "-hide_banner", "-nostdin",
                    "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=red:s=160x90:r=24:d=1.5",
                    "-f", "lavfi", "-i",
                    "sine=frequency=450:sample_rate=48000:duration=1.5",
                    "-t", "1.5", "-c:v", "mpeg4", "-q:v", "4",
                    "-c:a", "aac", "-b:a", "96k", str(first),
                ],
                [
                    shutil.which("ffmpeg"), "-hide_banner", "-nostdin",
                    "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=green:s=90x160:r=24:d=1.5",
                    "-t", "1.5", "-an", "-c:v", "mpeg4",
                    "-q:v", "4", str(second),
                ],
            ]
            for cmd in commands:
                generated = subprocess.run(
                    cmd, capture_output=True, timeout=30, check=False,
                )
                self.assertEqual(generated.returncode, 0, generated.stderr)

            clips = [
                segment("video-1", 0, 1.5, first.read_bytes()),
                segment("video-2", 0, 1.5, second.read_bytes()),
            ]
            with_sound = folder / "reel_with_sound.mp4"
            with_sound.write_bytes(render_test_reel(clips, audio_mode="original"))
            silent = folder / "reel_silent.mp4"
            silent.write_bytes(render_test_reel(clips))  # default mute

            def inspect(path):
                probe = subprocess.run(
                    [
                        shutil.which("ffprobe"), "-v", "error",
                        "-show_entries", "stream=codec_type,codec_name:"
                        "format=duration", "-of", "json", str(path),
                    ],
                    capture_output=True, text=True, timeout=20, check=False,
                )
                self.assertEqual(probe.returncode, 0, probe.stderr)
                return json.loads(probe.stdout)

            soundtrack = inspect(with_sound)
            silent_track = inspect(silent)
            self.assertEqual(
                [x["codec_type"] for x in soundtrack["streams"]],
                ["video", "audio"],
            )
            self.assertEqual(
                next(x for x in soundtrack["streams"]
                     if x["codec_type"] == "audio")["codec_name"],
                "aac",
            )
            self.assertAlmostEqual(
                float(soundtrack["format"]["duration"]), 3.0, delta=0.15
            )
            self.assertFalse(
                any(x["codec_type"] == "audio"
                    for x in silent_track["streams"])
            )

            # Beim ersten Abschnitt muss ein Sinuston vorhanden sein,
            # beim zweiten Abschnitt keine hörbaren Originaldaten.
            def max_amplitude_at(timestamp):
                decoded = subprocess.run(
                    [
                        shutil.which("ffmpeg"), "-hide_banner", "-nostdin",
                        "-loglevel", "error",
                        "-ss", str(timestamp), "-i", str(with_sound),
                        "-t", "0.15", "-vn", "-ar", "48000", "-ac", "1",
                        "-f", "s16le", "pipe:1",
                    ],
                    capture_output=True, timeout=20, check=False,
                )
                self.assertEqual(decoded.returncode, 0, decoded.stderr)
                from array import array
                values = array("h")
                values.frombytes(decoded.stdout)
                self.assertTrue(values)
                return max(abs(value) for value in values)

            self.assertGreater(max_amplitude_at(0.6), 800)
            self.assertLess(max_amplitude_at(2.1), 100)

    @unittest.skipUnless(
        shutil.which("ffmpeg") and shutil.which("ffprobe"),
        "FFmpeg/ffprobe nicht installiert",
    )
    def test_original_audio_mode_with_only_silent_clips_is_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            path = folder / "silent.mp4"
            made = subprocess.run(
                [
                    shutil.which("ffmpeg"), "-hide_banner", "-nostdin",
                    "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=24:d=1",
                    "-c:v", "mpeg4", "-an", str(path),
                ],
                capture_output=True, timeout=30, check=False,
            )
            self.assertEqual(made.returncode, 0, made.stderr)
            data = path.read_bytes()
            output = render_test_reel([
                segment("video-1", 0, 1, data),
                segment("video-2", 0, 1, data),
            ], audio_mode="original", background_mode="black")
            result = folder / "both_silent.mp4"
            result.write_bytes(output)
            probe = subprocess.run(
                [
                    shutil.which("ffprobe"), "-v", "error",
                    "-select_streams", "a", "-show_entries", "stream=codec_name",
                    "-of", "csv=p=0", str(result),
                ],
                capture_output=True, text=True, timeout=20, check=False,
            )
            self.assertEqual(probe.returncode, 0, probe.stderr)
            self.assertIn("aac", probe.stdout)


if __name__ == "__main__":
    unittest.main()
