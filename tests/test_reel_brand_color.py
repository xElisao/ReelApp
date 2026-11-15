"""Markenfarbige Textflächen: HEX-Sicherheit, Schriftkontrast und echte Videos."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from reel_export import (
    ReelExportError, ReelSegment, _brand_text_style,
    normalize_brand_color, render_test_reel,
)

FAKE_MP4 = bytes((0, 0, 0, 24)) + b"ftypisom0000"


def fake_segments() -> list[ReelSegment]:
    return [
        ReelSegment("clip1", 0.0, 3.0, FAKE_MP4),
        ReelSegment("clip2", 0.0, 3.0, FAKE_MP4),
    ]


def synthetic_clip(folder: Path, name: str, color: str, *, audio: bool = False) -> bytes:
    destination = folder / f"{name}.mp4"
    command = [
        shutil.which("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel", "error",
        "-y", "-f", "lavfi", "-i", f"color=c={color}:s=160x90:r=24:d=3",
    ]
    if audio:
        command.extend([
            "-f", "lavfi", "-i",
            "sine=frequency=440:sample_rate=48000:duration=3",
        ])
    command.extend(["-c:v", "mpeg4", "-q:v", "4"])
    if audio:
        command.extend(["-c:a", "aac", "-b:a", "96k"])
    else:
        command.append("-an")
    command.append(str(destination))
    result = subprocess.run(command, capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise AssertionError(result.stderr.decode(errors="replace"))
    return destination.read_bytes()


def small_logo() -> bytes:
    img = Image.new("RGBA", (120, 80), (0, 0, 0, 0))
    ImageDraw.Draw(img).rectangle((18, 12, 105, 68), fill=(255, 255, 0, 255))
    buffer = io.BytesIO()
    img.save(buffer, "PNG")
    return buffer.getvalue()


def pixel_at(path: Path, second: float, x: int, y: int) -> tuple[int, int, int]:
    result = subprocess.run([
        shutil.which("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel", "error",
        "-ss", f"{second:.3f}", "-i", str(path), "-frames:v", "1",
        "-vf", f"crop=2:2:{x}:{y},format=rgb24", "-f", "rawvideo", "pipe:1",
    ], capture_output=True, timeout=25, check=False)
    if result.returncode or len(result.stdout) < 3:
        raise AssertionError(result.stderr.decode(errors="replace"))
    return tuple(result.stdout[:3])


class BrandColorValidationTests(unittest.TestCase):
    def test_colors_normalized_and_font_selected_for_readability(self):
        self.assertIsNone(normalize_brand_color(None))
        self.assertEqual(normalize_brand_color("#a1B2c3"), "#A1B2C3")
        self.assertEqual(_brand_text_style(None), ("black@0.65", "white"))
        self.assertEqual(_brand_text_style("#000000"), ("0x000000", "white"))
        self.assertEqual(_brand_text_style("#FFFFFF"), ("0xFFFFFF", "black"))
        self.assertEqual(_brand_text_style("#F0C020"), ("0xF0C020", "black"))
        self.assertEqual(_brand_text_style("#173A72"), ("0x173A72", "white"))

    def test_rejects_invalid_color_before_ffmpeg(self):
        invalid = [
            "", "#fff", "#GG8899", "#1234567", "red", "black@0.5",
            "0x112233", "#112233:enable=1", "#ff0000\n", "#fff000;",
            None, False, 123, {}, [],
        ]
        self.assertIsNone(normalize_brand_color(None))
        for value in invalid:
            if value is None:
                continue
            with self.subTest(value=repr(value)):
                with patch("reel_export.subprocess.run") as execute:
                    with self.assertRaises(ReelExportError):
                        render_test_reel(fake_segments(), brand_color=value)
                    execute.assert_not_called()

    def test_drawtext_graph_has_exact_color_and_no_user_expression(self):
        results: list[list[str]] = []

        def fake_run(command, *, capture_output, check, timeout):
            results.append(command)
            Path(command[-1]).write_bytes(FAKE_MP4)
            return subprocess.CompletedProcess(command, 0, b"", b"")

        with (
            patch("reel_export.shutil.which", return_value="/usr/bin/ffmpeg"),
            patch("reel_export.subprocess.run", side_effect=fake_run),
        ):
            for color in (None, "#F0C020", "#173A72"):
                render_test_reel(
                    fake_segments(), title_text="Schönes Haus",
                    cta_text="Jetzt ansehen", brand_color=color,
                )
            render_test_reel(fake_segments(), brand_color="#ABCDEF")
        graphs = [command[command.index("-filter_complex") + 1] for command in results]
        self.assertEqual(len(graphs), 4)
        self.assertIn("fontcolor=white:box=1:boxcolor=black@0.65", graphs[0])
        self.assertIn("fontcolor=black:box=1:boxcolor=0xF0C020", graphs[1])
        self.assertIn("fontcolor=white:box=1:boxcolor=0x173A72", graphs[2])
        self.assertEqual(graphs[1].count("boxcolor=0xF0C020"), 2)
        self.assertNotIn("drawtext=", graphs[3])


@unittest.skipUnless(
    shutil.which("ffmpeg") and shutil.which("ffprobe"),
    "FFmpeg und ffprobe benötigt",
)
class BrandColorFFmpegTests(unittest.TestCase):
    def test_real_mp4_brand_color_with_logo_title_cta_and_fade(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            clips = [
                ReelSegment("a", 0, 3, synthetic_clip(folder, "red", "red", audio=True)),
                ReelSegment("b", 0, 3, synthetic_clip(folder, "blue", "blue")),
            ]
            for transition, color, audio in [
                ("cut", "#F0C020", "mute"),
                ("fade", "#173A72", "original"),
            ]:
                with self.subTest(transition=transition, color=color):
                    destination = folder / f"brand_{transition}.mp4"
                    destination.write_bytes(render_test_reel(
                        clips, transition_mode=transition,
                        fade_duration_seconds=0.5, audio_mode=audio,
                        title_text="Moderne Wohnung",
                        cta_text="Mehr entdecken",
                        logo_png_bytes=small_logo(),
                        brand_color=color,
                    ))
                    probe = subprocess.run([
                        shutil.which("ffprobe"), "-v", "error",
                        "-show_entries",
                        "stream=codec_type,width,height,nb_frames:format=duration",
                        "-of", "json", str(destination),
                    ], text=True, capture_output=True, timeout=20, check=False)
                    self.assertEqual(probe.returncode, 0, probe.stderr)
                    meta = json.loads(probe.stdout)
                    expected = 5.5 if transition == "fade" else 6.0
                    self.assertAlmostEqual(
                        float(meta["format"]["duration"]), expected, delta=0.00001
                    )
                    self.assertEqual(int(meta["streams"][0]["nb_frames"]), round(24 * expected))
                    self.assertEqual(
                        (meta["streams"][0]["width"], meta["streams"][0]["height"]),
                        (540, 960),
                    )
                    self.assertEqual(
                        [s["codec_type"] for s in meta["streams"]],
                        ["video", "audio"] if audio == "original" else ["video"],
                    )
                    red, green, blue = pixel_at(destination, 0.8, 270, 140)
                    if color == "#F0C020":
                        self.assertGreater(red, 170)
                        self.assertGreater(green, 120)
                        self.assertLess(blue, 90)
                    else:
                        self.assertLess(red, 80)
                        self.assertGreater(green, 30)
                        self.assertGreater(blue, 65)
                    # Bei beiden Szenen ist das Logo auch noch am Ende.
                    logo_rgb = pixel_at(destination, expected - 0.3, 450, 90)
                    self.assertGreater(logo_rgb[0], 150)
                    self.assertGreater(logo_rgb[1], 150)
                    self.assertLess(logo_rgb[2], 110)


if __name__ == "__main__":
    unittest.main()
