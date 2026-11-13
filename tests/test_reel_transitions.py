"""Tests für harte Schnitte und variabel lange Überblendungen ohne KI."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from array import array
from pathlib import Path
from unittest.mock import patch
from subprocess import CompletedProcess

from reel_export import (
    FADE_SECONDS, FADE_DURATIONS, ReelExportError, ReelSegment,
    expected_reel_duration, render_test_reel,
)

FAKE_MP4 = b"\x00\x00\x00\x18ftypisom0000"


def part(source_id, start, end, data=FAKE_MP4):
    return ReelSegment(source_id, start, end, data)


def generate_clip(folder: Path, index: int, color: str, *,
                  duration: float = 1.5, audio_hz: int | None = None) -> bytes:
    target = folder / f"clip_{index}.mp4"
    ffmpeg = shutil.which("ffmpeg")
    command = [
        ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i",
        f"color=c={color}:s=160x90:r=24:d={duration}",
    ]
    if audio_hz:
        command.extend([
            "-f", "lavfi", "-i",
            f"sine=frequency={audio_hz}:sample_rate=48000:duration={duration}",
        ])
    else:
        command.extend(["-an"])
    command.extend(["-c:v", "mpeg4", "-q:v", "4"])
    if audio_hz:
        command.extend(["-c:a", "aac", "-b:a", "96k"])
    command.append(str(target))
    result = subprocess.run(command, capture_output=True, timeout=30, check=False)
    if result.returncode != 0:
        raise AssertionError(result.stderr.decode("utf-8", errors="replace"))
    return target.read_bytes()


def inspect_mp4(path: Path) -> dict:
    result = subprocess.run([
        shutil.which("ffprobe"), "-v", "error",
        "-show_entries",
        "stream=codec_type,codec_name,width,height:format=duration",
        "-of", "json", str(path),
    ], capture_output=True, text=True, timeout=20, check=False)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


def sample_center_pixel(path: Path, timestamp: float) -> tuple[int, int, int]:
    result = subprocess.run([
        shutil.which("ffmpeg"), "-hide_banner", "-nostdin",
        "-loglevel", "error", "-ss", str(timestamp), "-i", str(path),
        "-frames:v", "1",
        "-vf", "crop=2:2:269:479,format=rgb24",
        "-f", "rawvideo", "pipe:1",
    ], capture_output=True, timeout=30, check=False)
    if result.returncode or len(result.stdout) < 3:
        raise AssertionError(result.stderr.decode("utf-8", errors="replace"))
    return tuple(result.stdout[:3])


def audio_peak(path: Path, timestamp: float) -> int:
    result = subprocess.run([
        shutil.which("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel",
        "error", "-ss", str(timestamp), "-i", str(path),
        "-t", "0.15", "-vn", "-ar", "48000", "-ac", "1",
        "-f", "s16le", "pipe:1",
    ], capture_output=True, timeout=20, check=False)
    if result.returncode:
        raise AssertionError(result.stderr.decode("utf-8", errors="replace"))
    samples = array("h")
    samples.frombytes(result.stdout)
    if not samples:
        raise AssertionError("Keine Audio-Beispiele extrahiert")
    return max(abs(item) for item in samples)


class TransitionValidationTests(unittest.TestCase):
    def test_two_and_three_scene_output_lengths(self):
        two = [part("video-1", 0, 3), part("video-2", 0, 3)]
        self.assertAlmostEqual(expected_reel_duration(two), 6.0)
        self.assertAlmostEqual(
            expected_reel_duration(two, transition_mode="fade"), 5.5
        )
        three = two + [part("video-3", 0, 3)]
        self.assertAlmostEqual(
            expected_reel_duration(three, transition_mode="fade"), 8.0
        )
        self.assertAlmostEqual(FADE_SECONDS, 0.5)

    def test_duration_options_apply_to_two_and_three_clips(self):
        self.assertEqual(FADE_DURATIONS, frozenset({0.25, 0.5, 1.0}))
        two = [part("video-1", 0, 3), part("video-2", 0, 3)]
        three = two + [part("video-3", 0, 3)]
        for fade_seconds in (0.25, 0.5, 1.0):
            with self.subTest(fade_seconds=fade_seconds):
                self.assertAlmostEqual(
                    expected_reel_duration(
                        two, transition_mode="fade",
                        fade_duration_seconds=fade_seconds,
                    ),
                    6 - fade_seconds,
                )
                self.assertAlmostEqual(
                    expected_reel_duration(
                        three, transition_mode="fade",
                        fade_duration_seconds=fade_seconds,
                    ),
                    9 - 2 * fade_seconds,
                )
        # Existing callers without a duration retain the old 0.5-s default.
        self.assertAlmostEqual(
            expected_reel_duration(two, transition_mode="fade"), 5.5
        )

    def test_duration_is_whitelisted_even_for_cut_mode(self):
        two = [part("video-1", 0, 3), part("video-2", 0, 3)]
        for bad in (-1, 0, 0.1, 0.6, 1.5, True, float("nan"), float("inf"), "1"):
            with self.subTest(bad=bad):
                with patch("reel_export.subprocess.run") as run:
                    with self.assertRaisesRegex(ReelExportError, "Überblendungsdauer"):
                        render_test_reel(
                            two, transition_mode="fade",
                            fade_duration_seconds=bad,
                        )
                    run.assert_not_called()

    def test_minimum_scene_length_changes_with_fade_duration(self):
        shorter = [part("video-1", 0, 0.75), part("video-2", 0, 3)]
        self.assertAlmostEqual(
            expected_reel_duration(
                shorter, transition_mode="fade",
                fade_duration_seconds=0.25,
            ), 3.5
        )
        with self.assertRaisesRegex(ReelExportError, "1,00 Sekunden"):
            expected_reel_duration(
                shorter, transition_mode="fade",
                fade_duration_seconds=0.5,
            )
        with self.assertRaisesRegex(ReelExportError, "2,00 Sekunden"):
            expected_reel_duration(
                [part("video-1", 0, 1.5), part("video-2", 0, 3)],
                transition_mode="fade",
                fade_duration_seconds=1.0,
            )

    def test_duration_passed_exactly_to_video_and_audio_filter_graph(self):
        scenes = [
            part("video-1", 0, 3),
            part("video-2", 0, 3),
            part("video-3", 0, 3),
        ]
        for duration in (0.25, 0.5, 1.0):
            with self.subTest(duration=duration):
                captured = []
                def fake_ffmpeg(cmd, *, capture_output, check, timeout):
                    captured.append(cmd)
                    Path(cmd[-1]).write_bytes(FAKE_MP4)
                    return CompletedProcess(cmd, 0, b"", b"")
                with (
                    patch("reel_export.shutil.which", return_value="/usr/bin/ffmpeg"),
                    patch("reel_export._clip_has_audio", return_value=False),
                    patch("reel_export.subprocess.run", side_effect=fake_ffmpeg),
                ):
                    render_test_reel(
                        scenes, transition_mode="fade",
                        fade_duration_seconds=duration,
                        audio_mode="original",
                    )
                graph = captured[0][captured[0].index("-filter_complex") + 1]
                self.assertIn(
                    f"xfade=transition=fade:duration={duration:.6f}:"
                    f"offset={3-duration:.6f}", graph,
                )
                self.assertIn(
                    f"xfade=transition=fade:duration={duration:.6f}:"
                    f"offset={6-2*duration:.6f}", graph,
                )
                self.assertEqual(
                    graph.count(f"acrossfade=d={duration:.6f}:"), 2
                )

    def test_xfade_receives_explicit_constant_frame_rate_after_overlay(self):
        """Regression: FFmpeg 7 refuses xfade when upstream overlay reports 1/0 FPS.

        On some FFmpeg versions 'overlay' does not preserve CFR metadata,
        even though the clip was normalized with fps=24 earlier in the graph.
        The final fps filter must be AFTER overlay, trim and settb.
        """
        scenes = [
            part("video-1", 10.5, 13.5),
            part("video-1", 19.5, 22.5),
        ]
        for background in ("blur", "black"):
            with self.subTest(background=background):
                captured = []

                def fake_ffmpeg(cmd, *, capture_output, check, timeout):
                    captured.append(cmd)
                    Path(cmd[-1]).write_bytes(FAKE_MP4)
                    return CompletedProcess(cmd, 0, b"", b"")

                with (
                    patch("reel_export.shutil.which", return_value="/usr/bin/ffmpeg"),
                    patch("reel_export.subprocess.run", side_effect=fake_ffmpeg),
                ):
                    result = render_test_reel(
                        scenes, transition_mode="fade",
                        background_mode=background,
                    )
                self.assertEqual(result, FAKE_MP4)
                self.assertEqual(len(captured), 1)
                cmd = captured[0]
                graph = cmd[cmd.index("-filter_complex") + 1]
                self.assertIn("settb=AVTB,fps=24[v0]", graph)
                self.assertIn("settb=AVTB,fps=24[v1]", graph)
                self.assertIn(
                    "xfade=transition=fade:duration=0.500000:offset=2.500000",
                    graph,
                )

    def test_bad_transition_is_rejected_before_ffmpeg(self):
        segments = [part("video-1", 0, 2), part("video-2", 0, 2)]
        with patch("reel_export.subprocess.run") as run:
            with self.assertRaisesRegex(ReelExportError, "Übergangsmodus"):
                render_test_reel(
                    segments, transition_mode="arbitrary_expression"
                )
        run.assert_not_called()

    def test_too_short_scenes_cannot_be_blended_but_direct_cuts_allowed(self):
        short = [part("video-1", 0, 0.75), part("video-2", 0, 3)]
        self.assertAlmostEqual(expected_reel_duration(short), 3.75)
        with self.assertRaisesRegex(ReelExportError, "mindestens 1,00"):
            expected_reel_duration(short, transition_mode="fade")
        with self.assertRaisesRegex(ReelExportError, "mindestens 1,00"):
            render_test_reel(short, transition_mode="fade")

    def test_three_scene_middle_too_short_is_blocked(self):
        clips = [
            part("video-1", 0, 2), part("video-2", 0, 0.5),
            part("video-3", 0, 2),
        ]
        with self.assertRaisesRegex(ReelExportError, "mindestens 1,00"):
            expected_reel_duration(clips, transition_mode="fade")


@unittest.skipUnless(
    shutil.which("ffmpeg") and shutil.which("ffprobe"),
    "FFmpeg und ffprobe nötig",
)
class TransitionFFmpegTests(unittest.TestCase):
    def test_two_clips_fade_visibly_and_keep_blurred_canvas(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            red = generate_clip(folder, 0, "red")
            green = generate_clip(folder, 1, "green")
            segments = [
                part("video-1", 0, 1.5, red),
                part("video-2", 0, 1.5, green),
            ]
            faded = folder / "fade.mp4"
            faded.write_bytes(
                render_test_reel(segments, transition_mode="fade")
            )
            info = inspect_mp4(faded)
            self.assertAlmostEqual(float(info["format"]["duration"]), 2.5, delta=0.15)
            video_streams = [s for s in info["streams"] if s["codec_type"] == "video"]
            self.assertEqual(len(video_streams), 1)
            self.assertEqual(video_streams[0]["codec_name"], "h264")
            self.assertEqual(
                (video_streams[0]["width"], video_streams[0]["height"]),
                (540, 960),
            )
            self.assertFalse(
                any(s["codec_type"] == "audio" for s in info["streams"])
            )
            early = sample_center_pixel(faded, 0.4)
            middle = sample_center_pixel(faded, 1.25)
            late = sample_center_pixel(faded, 2.0)
            self.assertGreater(early[0], early[1] + 80, early)
            self.assertGreater(late[1], late[0] + 50, late)
            # At the center of the 0.5 s fade, both colors are present.
            self.assertGreater(middle[0], 40, middle)
            self.assertGreater(middle[1], 20, middle)

            hard_cut = folder / "hard_cut.mp4"
            hard_cut.write_bytes(render_test_reel(segments))
            self.assertAlmostEqual(
                float(inspect_mp4(hard_cut)["format"]["duration"]), 3.0,
                delta=0.15,
            )
            hard_middle = sample_center_pixel(hard_cut, 1.25)
            self.assertGreater(hard_middle[0], hard_middle[1] + 80)

    def test_three_clips_with_black_padding_have_correct_sequence_and_length(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            colors = ("red", "green", "blue")
            media = [
                generate_clip(folder, i, color) for i, color in enumerate(colors)
            ]
            segments = [
                part(f"video-{i+1}", 0, 1.5, media[i])
                for i in range(3)
            ]
            result = folder / "three.mp4"
            result.write_bytes(
                render_test_reel(
                    segments, transition_mode="fade",
                    background_mode="black",
                )
            )
            self.assertAlmostEqual(
                float(inspect_mp4(result)["format"]["duration"]), 3.5,
                delta=0.15,
            )
            first = sample_center_pixel(result, 0.4)
            second = sample_center_pixel(result, 1.75)
            third = sample_center_pixel(result, 3.1)
            self.assertGreater(first[0], first[1] + 80, first)
            self.assertGreater(second[1], second[0] + 40, second)
            self.assertGreater(third[2], third[0] + 80, third)

    def test_audio_crossfade_keeps_tone_and_silence_aligned(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            tone = generate_clip(folder, 0, "red", audio_hz=440)
            quiet = generate_clip(folder, 1, "green")
            segments = [
                part("video-1", 0, 1.5, tone),
                part("video-2", 0, 1.5, quiet),
            ]
            result = folder / "with_audio_fade.mp4"
            result.write_bytes(
                render_test_reel(
                    segments, transition_mode="fade", audio_mode="original",
                )
            )
            meta = inspect_mp4(result)
            self.assertAlmostEqual(
                float(meta["format"]["duration"]), 2.5, delta=0.15,
            )
            self.assertEqual(
                [s["codec_type"] for s in meta["streams"]],
                ["video", "audio"],
            )
            self.assertGreater(audio_peak(result, 0.4), 800)
            self.assertLess(audio_peak(result, 2.0), 100)

    def test_real_three_durations_video_and_audio_within_24fps(self):
        """Test with real FFmpeg, not just a mocked filter expression."""
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            red = generate_clip(folder, 0, "red", duration=3, audio_hz=440)
            green = generate_clip(folder, 1, "green", duration=3)
            blue = generate_clip(folder, 2, "blue", duration=3)
            two = [
                part("video-1", 0, 3, red),
                part("video-2", 0, 3, green),
            ]
            three = two + [part("video-3", 0, 3, blue)]
            for duration in (0.25, 0.5, 1.0):
                with self.subTest(duration=duration):
                    target = folder / f"fade_{int(duration * 100)}.mp4"
                    target.write_bytes(render_test_reel(
                        two, transition_mode="fade",
                        fade_duration_seconds=duration,
                        audio_mode="original",
                    ))
                    info = inspect_mp4(target)
                    self.assertAlmostEqual(
                        float(info["format"]["duration"]),
                        6 - duration, delta=0.08,
                    )
                    self.assertEqual(
                        [item["codec_type"] for item in info["streams"]],
                        ["video", "audio"],
                    )
                    start = sample_center_pixel(target, 0.5)
                    mix = sample_center_pixel(target, 3-duration/2)
                    end = sample_center_pixel(target, 5-duration)
                    self.assertGreater(start[0], start[1] + 80, start)
                    self.assertGreater(mix[0], 30, mix)
                    self.assertGreater(mix[1], 20, mix)
                    self.assertGreater(end[1], end[0] + 50, end)
                    self.assertGreater(audio_peak(target, 0.5), 600)
                    self.assertLess(audio_peak(target, 5-duration), 100)

            # Three scenes need two successive fades, including 1-second
            # transitions in a black letterbox layout.
            for duration in (0.25, 1.0):
                with self.subTest(three_scene_duration=duration):
                    target = folder / f"three_{int(duration * 100)}.mp4"
                    target.write_bytes(render_test_reel(
                        three, transition_mode="fade",
                        fade_duration_seconds=duration,
                        background_mode="black",
                    ))
                    info = inspect_mp4(target)
                    self.assertAlmostEqual(
                        float(info["format"]["duration"]),
                        9 - 2*duration, delta=0.08,
                    )
                    self.assertGreater(
                        sample_center_pixel(target, 0.5)[0], 80
                    )
                    self.assertGreater(
                        sample_center_pixel(target, 4.5-duration)[1], 50
                    )
                    self.assertGreater(
                        sample_center_pixel(
                            target, 8-2*duration
                        )[2], 80
                    )

    def test_two_silent_clips_with_original_audio_mode_fade_safely(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            first = generate_clip(folder, 0, "red")
            second = generate_clip(folder, 1, "blue")
            output = folder / "silent_audio.mp4"
            output.write_bytes(
                render_test_reel(
                    [
                        part("video-1", 0, 1.5, first),
                        part("video-2", 0, 1.5, second),
                    ],
                    audio_mode="original",
                    transition_mode="fade",
                    background_mode="black",
                )
            )
            info = inspect_mp4(output)
            self.assertAlmostEqual(float(info["format"]["duration"]), 2.5, delta=0.15)
            self.assertTrue(
                any(stream["codec_type"] == "audio" for stream in info["streams"])
            )
            self.assertLess(audio_peak(output, 1.0), 100)


if __name__ == "__main__":
    unittest.main()
