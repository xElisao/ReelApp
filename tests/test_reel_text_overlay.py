"""Titel-/CTA-Einblendungen: Sicherheit, Graph und echte MP4-Ausgabe ohne KI."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reel_export import (
    MAX_OVERLAY_CHARACTERS, OVERLAY_FONT_PATH,
    ReelExportError, ReelSegment, normalize_overlay_text, render_test_reel,
)

FAKE_MP4 = b"\x00\x00\x00\x18ftypisom0000"


def part(source: str, data: bytes = FAKE_MP4) -> ReelSegment:
    return ReelSegment(source, 0, 3.0, data)


def make_synthetic_clip(directory: Path, color: str, *, audio: bool = False) -> bytes:
    target = directory / f"{color}.mp4"
    command = [
        shutil.which("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel",
        "error", "-y", "-f", "lavfi", "-i",
        f"color=c={color}:s=160x90:r=24:d=3",
    ]
    if audio:
        command += [
            "-f", "lavfi", "-i",
            "sine=frequency=440:sample_rate=48000:duration=3",
        ]
    command += ["-c:v", "mpeg4", "-q:v", "4"]
    if audio:
        command += ["-c:a", "aac", "-b:a", "96k"]
    else:
        command += ["-an"]
    command.append(str(target))
    result = subprocess.run(
        command, capture_output=True, check=False, timeout=30,
    )
    if result.returncode:
        raise AssertionError(result.stderr.decode(errors="replace"))
    return target.read_bytes()


def video_info(target: Path) -> dict:
    command = [
        shutil.which("ffprobe"), "-v", "error",
        "-show_entries", "stream=codec_type,width,height:format=duration",
        "-of", "json", str(target),
    ]
    result = subprocess.run(
        command, text=True, capture_output=True, check=False, timeout=20,
    )
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


def light_pixels(target: Path, seconds: float, y_start: int) -> int:
    """Weißanteile im angegebenen Bildbereich real aus dem MP4 auslesen."""
    cmd = [
        shutil.which("ffmpeg"), "-hide_banner", "-nostdin",
        "-loglevel", "error", "-ss", f"{seconds:.3f}", "-i",
        str(target), "-frames:v", "1",
        "-vf", f"crop=540:200:0:{y_start},format=rgb24",
        "-f", "rawvideo", "pipe:1",
    ]
    result = subprocess.run(
        cmd, capture_output=True, check=False, timeout=30,
    )
    if result.returncode or len(result.stdout) < 540 * 200 * 3:
        raise AssertionError(result.stderr.decode(errors="replace"))
    pixels = result.stdout
    return sum(
        pixels[i] > 195 and pixels[i + 1] > 195 and pixels[i + 2] > 195
        for i in range(0, len(pixels), 3)
    )


class TextOverlayValidationTests(unittest.TestCase):
    def test_unicode_printable_symbols_and_empty_text(self):
        self.assertEqual(normalize_overlay_text("  Café: 100% & Spaß  "), "Café: 100% & Spaß")
        self.assertEqual(normalize_overlay_text(""), "")
        self.assertEqual(MAX_OVERLAY_CHARACTERS, 56)

    def test_invalid_text_rejected_before_subprocess(self):
        clips = [part("one"), part("two")]
        invalid = [None, False, 123, "x" * 57, "A\nB", "A\rB", "A\x00B", "A\u202eB"]
        for text in invalid:
            with self.subTest(text=repr(text)):
                with patch("reel_export.subprocess.run") as execute:
                    with self.assertRaises(ReelExportError):
                        render_test_reel(clips, title_text=text)
                    execute.assert_not_called()

    def test_filter_uses_temp_utf8_files_never_raw_user_text(self):
        with tempfile.TemporaryDirectory() as directory:
            dummy_font = Path(directory) / "test-font.ttf"
            dummy_font.write_bytes(b"not used by mocked ffmpeg")
            captured: dict[str, object] = {}

            def fake_execute(command, *, capture_output, check, timeout):
                graph = command[command.index("-filter_complex") + 1]
                folder = Path(command[-1]).parent
                captured["graph"] = graph
                captured["mapping"] = command[command.index("-map") + 1]
                captured["title"] = (folder / "overlay_title.txt").read_text(
                    encoding="utf-8"
                )
                captured["cta"] = (folder / "overlay_cta.txt").read_text(
                    encoding="utf-8"
                )
                Path(command[-1]).write_bytes(FAKE_MP4)
                return subprocess.CompletedProcess(command, 0, b"", b"")

            with (
                patch("reel_export.OVERLAY_FONT_PATH", dummy_font),
                patch("reel_export.shutil.which", return_value="/usr/bin/ffmpeg"),
                patch("reel_export.subprocess.run", side_effect=fake_execute),
            ):
                output = render_test_reel(
                    [part("one"), part("two")],
                    transition_mode="fade",
                    title_text="Café: 100% %{pts} & Räder",
                    cta_text="Jetzt ansehen: 'Schön'!",
                )
            self.assertEqual(output, FAKE_MP4)
            graph = captured["graph"]
            self.assertEqual(captured["mapping"], "[reel_cta]")
            self.assertIn("drawtext=", graph)
            self.assertEqual(graph.count("drawtext="), 2)
            self.assertIn("expansion=none", graph)
            self.assertIn("enable='lt(t,2.000000)'", graph)
            self.assertIn("enable='gte(t,3.500000)'", graph)
            self.assertNotIn("Café", graph)
            self.assertNotIn("%{pts}", graph)
            self.assertNotIn("Schön", graph)
            self.assertIn("Café: 100%", captured["title"])
            self.assertIn("%{pts}", captured["title"])
            self.assertIn("Schön", captured["cta"])

    def test_without_text_keeps_existing_video_mapping_and_no_font_dependency(self):
        captured = []
        def fake_execute(command, *, capture_output, check, timeout):
            captured.append(command)
            Path(command[-1]).write_bytes(FAKE_MP4)
            return subprocess.CompletedProcess(command, 0, b"", b"")
        with (
            patch("reel_export.shutil.which", return_value="/usr/bin/ffmpeg"),
            patch("reel_export.subprocess.run", side_effect=fake_execute),
        ):
            result = render_test_reel([part("one"), part("two")])
        self.assertEqual(result, FAKE_MP4)
        command = captured[0]
        self.assertEqual(command[command.index("-map") + 1], "[video]")
        self.assertNotIn(
            "drawtext=", command[command.index("-filter_complex") + 1]
        )


@unittest.skipUnless(
    shutil.which("ffmpeg") and shutil.which("ffprobe") and OVERLAY_FONT_PATH.is_file(),
    "FFmpeg, ffprobe und DejaVu-Bold-Schriftart nötig",
)
class TextOverlayFFmpegTests(unittest.TestCase):
    def test_real_mp4_title_cta_both_visible_only_at_right_times(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            clips = [
                part("one", make_synthetic_clip(folder, "red", audio=True)),
                part("two", make_synthetic_clip(folder, "blue")),
            ]
            for mode, fade_seconds, audio_mode in [
                ("cut", 0.5, "mute"),
                ("fade", 0.25, "original"),
                ("fade", 1.0, "mute"),
            ]:
                with self.subTest(mode=mode, fade=fade_seconds, audio=audio_mode):
                    output = folder / f"text_{mode}_{fade_seconds}.mp4"
                    output.write_bytes(render_test_reel(
                        clips, transition_mode=mode,
                        fade_duration_seconds=fade_seconds,
                        background_mode="blur",
                        audio_mode=audio_mode,
                        title_text="Helles Loft: 90 m²",
                        cta_text="Jetzt anfragen! 100%",
                    ))
                    info = video_info(output)
                    expected = 6.0 if mode == "cut" else 6.0 - fade_seconds
                    self.assertAlmostEqual(
                        float(info["format"]["duration"]), expected, delta=0.10
                    )
                    self.assertEqual(
                        [x["codec_type"] for x in info["streams"]],
                        ["video", "audio"] if audio_mode == "original" else ["video"],
                    )
                    self.assertEqual(
                        (info["streams"][0]["width"], info["streams"][0]["height"]),
                        (540, 960),
                    )
                    # On red/blue synthetic backgrounds white appears only
                    # as user-entered title or CTA, and never at the wrong time.
                    self.assertGreater(light_pixels(output, 0.8, 120), 70)
                    self.assertLess(light_pixels(output, expected - 0.7, 120), 20)
                    self.assertLess(light_pixels(output, 0.8, 590), 20)
                    self.assertGreater(
                        light_pixels(output, expected - 0.7, 590), 70
                    )


if __name__ == "__main__":
    unittest.main()
