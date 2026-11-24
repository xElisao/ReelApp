"""Social-Schutzbereich: Validierung, pixelbasierter Textumbruch und echte MP4s."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageFont

from reel_export import (
    OVERLAY_FONT_PATH, SAFE_AREA_MODES, ReelExportError,
    ReelSegment, SOCIAL_SAFE_LEFT, SOCIAL_SAFE_RIGHT,
    SOCIAL_SAFE_TOP, SOCIAL_SAFE_BOTTOM,
    _wrap_social_text, render_test_reel,
)

FAKE_MP4 = bytes((0, 0, 0, 24)) + b"ftypisom0000"


def fake_segments():
    return [
        ReelSegment("one", 0, 3, FAKE_MP4),
        ReelSegment("two", 0, 3, FAKE_MP4),
    ]


def make_clip(folder, name, color, audio=False):
    target = folder / f"{name}.mp4"
    command = [
        shutil.which("ffmpeg"), "-hide_banner", "-nostdin",
        "-loglevel", "error", "-y", "-f", "lavfi",
        "-i", f"color=c={color}:s=160x90:r=24:d=3",
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
    done = subprocess.run(command, capture_output=True, timeout=30, check=False)
    if done.returncode:
        raise AssertionError(done.stderr.decode(errors="replace"))
    return target.read_bytes()


def make_logo():
    image = Image.new("RGBA", (120, 80), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((10, 10, 110, 70), fill=(255, 255, 0, 255))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def pixel_at(path, second, x, y):
    done = subprocess.run([
        shutil.which("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel",
        "error", "-ss", f"{second:.3f}", "-i", str(path),
        "-frames:v", "1", "-vf",
        f"crop=2:2:{x}:{y},format=rgb24", "-f", "rawvideo", "pipe:1",
    ], capture_output=True, timeout=25, check=False)
    if done.returncode or len(done.stdout) < 3:
        raise AssertionError(done.stderr.decode(errors="replace"))
    return tuple(done.stdout[:3])


class SafeAreaValidationTests(unittest.TestCase):
    def test_safe_mode_only_accepts_fixed_values_before_ffmpeg(self):
        self.assertEqual(SAFE_AREA_MODES, frozenset({"off", "social"}))
        for value in (None, False, True, 42, "Social", "instagram",
                      "social:enable=1", "", [], {}):
            with self.subTest(value=repr(value)):
                with patch("reel_export.subprocess.run") as mocked:
                    with self.assertRaises(ReelExportError):
                        render_test_reel(fake_segments(), safe_area_mode=value)
                    mocked.assert_not_called()

    def test_off_keeps_previous_graph_and_logo_position(self):
        graphs = []
        def fake_run(command, *, capture_output, check, timeout):
            graphs.append(command[command.index("-filter_complex") + 1])
            Path(command[-1]).write_bytes(FAKE_MP4)
            return subprocess.CompletedProcess(command, 0, b"", b"")
        with (
            patch("reel_export.shutil.which", return_value="/usr/bin/ffmpeg"),
            patch("reel_export.subprocess.run", side_effect=fake_run),
        ):
            render_test_reel(fake_segments(), title_text="Bergblick",
                             cta_text="Mehr entdecken", logo_png_bytes=make_logo())
            render_test_reel(fake_segments(), title_text="Bergblick",
                             cta_text="Mehr entdecken", logo_png_bytes=make_logo(),
                             safe_area_mode="off")
        self.assertEqual(graphs[0], graphs[1])
        self.assertIn("boxborderw=16:line_spacing=6:x=(w-text_w)/2:y=150", graphs[0])
        self.assertIn("overlay=x=W-w-32:y=48", graphs[0])

    def test_social_wraps_wide_text_to_pixel_limit_and_uses_fixed_positions(self):
        font = ImageFont.truetype(str(OVERLAY_FONT_PATH), 27)
        for text in ("W" * 56, "Traumhafte Bergstraßen entdecken",
                     "SuperlangeununterbrocheneWortkette", "Café – Blicke"):
            lines = _wrap_social_text(text, 27)
            self.assertLessEqual(len(lines), 7)
            for line in lines:
                self.assertLessEqual(font.getlength(line), 280)
        self.assertEqual(
            (SOCIAL_SAFE_LEFT, SOCIAL_SAFE_RIGHT, SOCIAL_SAFE_TOP, SOCIAL_SAFE_BOTTOM),
            (60, 390, 145, 615),
        )
        graph = []
        def fake_run(command, *, capture_output, check, timeout):
            graph.append(command[command.index("-filter_complex") + 1])
            Path(command[-1]).write_bytes(FAKE_MP4)
            return subprocess.CompletedProcess(command, 0, b"", b"")
        with (
            patch("reel_export.shutil.which", return_value="/usr/bin/ffmpeg"),
            patch("reel_export.subprocess.run", side_effect=fake_run),
        ):
            for design in ("classic", "modern"):
                render_test_reel(
                    fake_segments(), title_text="Bergstraßen entdecken",
                    cta_text="Mehr entdecken", logo_png_bytes=make_logo(),
                    design_template=design, safe_area_mode="social",
                    brand_color="#245582",
                )
        self.assertEqual(len(graph), 2)
        for rendered in graph:
            self.assertIn("overlay=x=72:y=152", rendered)
            self.assertEqual(rendered.count("drawtext="), 2)
            self.assertEqual(rendered.count("boxcolor=0x245582"), 2)
            self.assertNotIn("Bergstraßen entdecken", rendered)
            self.assertNotIn("y=h-185-text_h", rendered)
        self.assertIn("x=(450-text_w)/2:y=272", graph[0])
        self.assertIn("x=72:y=285", graph[1])
        self.assertIn("y=600-text_h", graph[0])
        self.assertIn("y=595-text_h", graph[1])


@unittest.skipUnless(
    shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg erforderlich",
)
class SafeAreaFFmpegTests(unittest.TestCase):
    def test_real_social_mp4_logo_text_colors_fade_and_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            clips = [
                ReelSegment("one", 0, 3, make_clip(folder, "red", "red", True)),
                ReelSegment("two", 0, 3, make_clip(folder, "blue", "blue")),
            ]
            for design, audio_mode in (("classic", "mute"), ("modern", "original")):
                with self.subTest(design=design):
                    target = folder / f"social_{design}.mp4"
                    target.write_bytes(render_test_reel(
                        clips, transition_mode="fade", fade_duration_seconds=0.5,
                        audio_mode=audio_mode, title_text="Bergstraßen entdecken",
                        cta_text="Mehr entdecken", logo_png_bytes=make_logo(),
                        brand_color="#245582", design_template=design,
                        safe_area_mode="social",
                    ))
                    probe = subprocess.run([
                        shutil.which("ffprobe"), "-v", "error",
                        "-show_entries",
                        "stream=codec_type,width,height,nb_frames:format=duration",
                        "-of", "json", str(target),
                    ], capture_output=True, text=True, timeout=20, check=False)
                    self.assertEqual(probe.returncode, 0, probe.stderr)
                    meta = json.loads(probe.stdout)
                    self.assertAlmostEqual(float(meta["format"]["duration"]), 5.5, delta=0.00001)
                    self.assertEqual(int(meta["streams"][0]["nb_frames"]), 132)
                    self.assertEqual(
                        (meta["streams"][0]["width"], meta["streams"][0]["height"]),
                        (540, 960),
                    )
                    self.assertEqual(
                        [item["codec_type"] for item in meta["streams"]],
                        ["video"] if audio_mode == "mute" else ["video", "audio"],
                    )
                    for time in (0.6, 2.75, 5.45):
                        rgb = pixel_at(target, time, 120, 190)
                        self.assertGreater(rgb[0], 165, rgb)
                        self.assertGreater(rgb[1], 160, rgb)
                        self.assertLess(rgb[2], 100, rgb)
                    # Kein Logo in der bisherigen oberen rechten Position.
                    rgb = pixel_at(target, 0.6, 450, 85)
                    self.assertGreater(rgb[0], rgb[1], rgb)
                    # Blauer Titel innerhalb der sicheren Fläche.
                    rgb = pixel_at(target, 0.6, 72, 280 if design == "classic" else 292)
                    self.assertLess(rgb[0], 85, rgb)
                    self.assertGreater(rgb[2], rgb[0], rgb)
                    # Untere 35% enthalten nur die rote/blaue Videoszene.
                    rgb = pixel_at(target, 5.3, 120, 760)
                    self.assertGreater(rgb[2], rgb[0], rgb)


if __name__ == "__main__":
    unittest.main()
