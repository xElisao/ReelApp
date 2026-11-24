"""Zwei vorgegebene, sichere Text-Layouts inklusive echtem FFmpeg-Export."""

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
    DESIGN_TEMPLATES, ReelExportError, ReelSegment, render_test_reel,
)

FAKE_MP4 = bytes((0, 0, 0, 24)) + b"ftypisom0000"


def stub_segments() -> list[ReelSegment]:
    return [
        ReelSegment("first", 0, 3, FAKE_MP4),
        ReelSegment("second", 0, 3, FAKE_MP4),
    ]


def make_clip(folder: Path, name: str, color: str, *, audio: bool = False) -> bytes:
    path = folder / f"{name}.mp4"
    command = [
        shutil.which("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel",
        "error", "-y", "-f", "lavfi", "-i",
        f"color=c={color}:s=160x90:r=24:d=3",
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
    command.append(str(path))
    result = subprocess.run(command, capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise AssertionError(result.stderr.decode(errors="replace"))
    return path.read_bytes()


def make_logo() -> bytes:
    image = Image.new("RGBA", (180, 100), (0, 0, 0, 0))
    ImageDraw.Draw(image).ellipse((18, 12, 162, 88), fill=(255, 255, 0, 255))
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


def pixel_at(path: Path, second: float, x: int, y: int) -> tuple[int, int, int]:
    result = subprocess.run([
        shutil.which("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel",
        "error", "-ss", f"{second:.3f}", "-i", str(path),
        "-frames:v", "1", "-vf",
        f"crop=2:2:{x}:{y},format=rgb24", "-f", "rawvideo", "pipe:1",
    ], capture_output=True, timeout=25, check=False)
    if result.returncode or len(result.stdout) < 3:
        raise AssertionError(result.stderr.decode(errors="replace"))
    return tuple(result.stdout[:3])


class DesignValidationTests(unittest.TestCase):
    def test_only_fixed_templates_are_allowed_before_ffmpeg(self):
        self.assertEqual(DESIGN_TEMPLATES, frozenset({"classic", "modern"}))
        for invalid in (None, False, 123, "Modern", "default", "",
                        "modern:enable=1", "classic;drawtext", [], {}):
            with self.subTest(invalid=repr(invalid)):
                with patch("reel_export.subprocess.run") as execute:
                    with self.assertRaises(ReelExportError):
                        render_test_reel(stub_segments(), design_template=invalid)
                    execute.assert_not_called()

    def test_classic_layout_preserves_existing_ffmpeg_parameters(self):
        captured: list[str] = []

        def fake_render(command, *, capture_output, check, timeout):
            graph = command[command.index("-filter_complex") + 1]
            captured.append(graph)
            Path(command[-1]).write_bytes(FAKE_MP4)
            return subprocess.CompletedProcess(command, 0, b"", b"")

        with (
            patch("reel_export.shutil.which", return_value="/usr/bin/ffmpeg"),
            patch("reel_export.subprocess.run", side_effect=fake_render),
        ):
            render_test_reel(
                stub_segments(), title_text="Wunderschönes Haus",
                cta_text="Mehr ansehen",
            )
            render_test_reel(
                stub_segments(), title_text="Wunderschönes Haus",
                cta_text="Mehr ansehen", design_template="classic",
            )
        self.assertEqual(len(captured), 2)
        for graph in captured:
            self.assertIn("fontsize=30:fontcolor=white:", graph)
            self.assertIn("boxcolor=black@0.65:boxborderw=16:", graph)
            self.assertIn("line_spacing=6:x=(w-text_w)/2:y=150:", graph)
            self.assertIn("line_spacing=6:x=(w-text_w)/2:y=h-185-text_h:", graph)
            self.assertEqual(graph.count("drawtext="), 2)

    def test_modern_uses_fixed_left_alignment_and_wrapped_utf8_text(self):
        captured: dict[str, object] = {}

        def fake_render(command, *, capture_output, check, timeout):
            graph = command[command.index("-filter_complex") + 1]
            folder = Path(command[-1]).parent
            captured["graph"] = graph
            captured["title"] = (folder / "overlay_title.txt").read_text("utf-8")
            captured["mapping"] = command[command.index("-map") + 1]
            Path(command[-1]).write_bytes(FAKE_MP4)
            return subprocess.CompletedProcess(command, 0, b"", b"")

        with (
            patch("reel_export.shutil.which", return_value="/usr/bin/ffmpeg"),
            patch("reel_export.subprocess.run", side_effect=fake_render),
        ):
            render_test_reel(
                stub_segments(), title_text="Berghütte mit Ausblick",
                cta_text="Jetzt ansehen", design_template="modern",
                brand_color="#245582",
            )
        graph = captured["graph"]
        self.assertEqual(captured["mapping"], "[reel_cta]")
        self.assertEqual(graph.count("drawtext="), 2)
        self.assertEqual(graph.count("fontsize=28:fontcolor=white:"), 2)
        self.assertEqual(graph.count("boxcolor=0x245582:boxborderw=12:"), 2)
        self.assertIn("line_spacing=7:x=44:y=210:", graph)
        self.assertIn("line_spacing=7:x=44:y=h-235-text_h:", graph)
        self.assertIn("\\n", repr(captured["title"]))
        self.assertNotIn("Berghütte", graph)


@unittest.skipUnless(
    shutil.which("ffmpeg") and shutil.which("ffprobe"),
    "FFmpeg und ffprobe benötigt",
)
class DesignTemplateFFmpegTests(unittest.TestCase):
    def test_real_mp4_classic_and_modern_with_fade_brand_and_logo(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            clips = [
                ReelSegment("first", 0, 3, make_clip(folder, "one", "red", audio=True)),
                ReelSegment("second", 0, 3, make_clip(folder, "two", "blue")),
            ]
            for design, transition, audio in (
                ("classic", "cut", "mute"),
                ("modern", "fade", "original"),
            ):
                with self.subTest(design=design):
                    target = folder / f"reel_{design}.mp4"
                    target.write_bytes(render_test_reel(
                        clips, transition_mode=transition,
                        fade_duration_seconds=0.5, audio_mode=audio,
                        title_text="Berghütte am See",
                        cta_text="Mehr entdecken",
                        brand_color="#F0C020",
                        logo_png_bytes=make_logo(),
                        design_template=design,
                    ))
                    result = subprocess.run([
                        shutil.which("ffprobe"), "-v", "error", "-show_entries",
                        "stream=codec_type,width,height,nb_frames:format=duration",
                        "-of", "json", str(target),
                    ], text=True, capture_output=True, timeout=20, check=False)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    info = json.loads(result.stdout)
                    expected = 6.0 if transition == "cut" else 5.5
                    self.assertAlmostEqual(float(info["format"]["duration"]), expected, delta=0.00001)
                    self.assertEqual(int(info["streams"][0]["nb_frames"]), round(24 * expected))
                    self.assertEqual(
                        (info["streams"][0]["width"], info["streams"][0]["height"]),
                        (540, 960),
                    )
                    self.assertEqual(
                        [stream["codec_type"] for stream in info["streams"]],
                        ["video", "audio"] if audio == "original" else ["video"],
                    )
                    # Gelbe Textfläche bei je eigenem Layout, nicht an gleicher Stelle.
                    if design == "modern":
                        r, g, b = pixel_at(target, 0.6, 50, 205)
                        self.assertGreater(r, 170, (r, g, b))
                        self.assertGreater(g, 115, (r, g, b))
                        self.assertLess(b, 120, (r, g, b))
                        # Modern-Titel liegt deutlich tiefer als klassisch.
                        r, g, b = pixel_at(target, 0.6, 50, 155)
                        self.assertGreater(r, g, (r, g, b))
                    else:
                        r, g, b = pixel_at(target, 0.6, 270, 155)
                        self.assertGreater(r, 170, (r, g, b))
                        self.assertGreater(g, 115, (r, g, b))
                        self.assertLess(b, 120, (r, g, b))
                    # PNG-Logo bleibt bis kurz vor Schluss sichtbar.
                    r, g, b = pixel_at(target, expected - 0.3, 450, 90)
                    self.assertGreater(r, 150, (r, g, b))
                    self.assertGreater(g, 140, (r, g, b))
                    self.assertLess(b, 115, (r, g, b))


if __name__ == "__main__":
    unittest.main()
