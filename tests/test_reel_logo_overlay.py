"""Tests für PNG-Logos im Reel-Export, inklusive echtem FFmpeg-Rendering."""

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
from PIL.PngImagePlugin import PngInfo

from reel_export import (
    LOGO_RENDER_HEIGHT, LOGO_RENDER_WIDTH, MAX_LOGO_BYTES,
    ReelExportError, ReelSegment, normalize_logo_png, render_test_reel,
)

FAKE_MP4 = bytes((0, 0, 0, 24)) + b"ftypisom0000"


def make_logo(*, metadata: bool = False) -> bytes:
    image = Image.new("RGBA", (200, 120), (0, 0, 0, 0))
    ImageDraw.Draw(image).ellipse((20, 10, 180, 110), fill=(255, 255, 0, 255))
    data = io.BytesIO()
    info = PngInfo()
    if metadata:
        info.add_text("Comment", "PRIVATE TEST METADATA - MUST BE REMOVED")
    image.save(data, format="PNG", pnginfo=info)
    return data.getvalue()


def make_clip(directory: Path, name: str, color: str, *, audio: bool = False) -> bytes:
    path = directory / f"{name}.mp4"
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
    else:
        command.append("-an")
    command.extend(["-c:v", "mpeg4", "-q:v", "4"])
    if audio:
        command.extend(["-c:a", "aac", "-b:a", "96k"])
    command.append(str(path))
    result = subprocess.run(command, capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise AssertionError(result.stderr.decode(errors="replace"))
    return path.read_bytes()


def video_info(path: Path) -> dict:
    result = subprocess.run([
        shutil.which("ffprobe"), "-v", "error",
        "-show_entries", "stream=codec_type,width,height,nb_frames:format=duration",
        "-of", "json", str(path),
    ], capture_output=True, text=True, timeout=20, check=False)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


def pixel_at(path: Path, second: float, x: int, y: int) -> tuple[int, int, int]:
    result = subprocess.run([
        shutil.which("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel", "error",
        "-ss", f"{second:.3f}", "-i", str(path), "-frames:v", "1",
        "-vf", f"crop=2:2:{x}:{y},format=rgb24", "-f", "rawvideo", "pipe:1",
    ], capture_output=True, timeout=25, check=False)
    if result.returncode or len(result.stdout) < 3:
        raise AssertionError(result.stderr.decode(errors="replace"))
    return tuple(result.stdout[:3])


class LogoValidationTests(unittest.TestCase):
    def test_png_is_cropped_resized_and_metadata_removed(self):
        untrusted = make_logo(metadata=True)
        self.assertIn(b"PRIVATE TEST METADATA", untrusted)
        sanitized = normalize_logo_png(untrusted)
        self.assertNotIn(b"PRIVATE TEST METADATA", sanitized)
        with Image.open(io.BytesIO(sanitized)) as img:
            self.assertEqual(img.format, "PNG")
            self.assertEqual(img.mode, "RGBA")
            self.assertLessEqual(img.width, LOGO_RENDER_WIDTH)
            self.assertLessEqual(img.height, LOGO_RENDER_HEIGHT)
            self.assertGreater(img.getchannel("A").getextrema()[1], 0)
            self.assertEqual(img.getchannel("A").getpixel((0, 0)), 0)
        self.assertIsNone(normalize_logo_png(None))

    def test_bad_or_large_files_and_invisible_logo_are_rejected_before_ffmpeg(self):
        png = make_logo()
        too_wide = Image.new("RGBA", (2049, 10), "red")
        oversized_png = io.BytesIO()
        too_wide.save(oversized_png, format="PNG")
        invisible_png = io.BytesIO()
        Image.new("RGBA", (100, 100), (0, 0, 0, 0)).save(invisible_png, "PNG")
        bad_values = [
            b"", b"not png", None, "not bytes", b"\x89PNG\r\n\x1a\ncorrupt",
            b"\x89PNG\r\n\x1a\n" + b"X" * MAX_LOGO_BYTES,
            oversized_png.getvalue(), invisible_png.getvalue(),
        ]
        for raw in bad_values:
            if raw is None:
                continue  # None explicitly means no logo, never an invalid upload.
            with self.subTest(raw=repr(raw)[:36]):
                with self.assertRaises(ReelExportError):
                    normalize_logo_png(raw)

        clips = [
            ReelSegment("a", 0, 3, FAKE_MP4),
            ReelSegment("b", 0, 3, FAKE_MP4),
        ]
        for bad in (b"invalid", oversized_png.getvalue(), "bad"):
            with self.subTest(bad=repr(bad)[:24]):
                with patch("reel_export.subprocess.run") as execute:
                    with self.assertRaises(ReelExportError):
                        render_test_reel(clips, logo_png_bytes=bad)
                    execute.assert_not_called()

    def test_logo_filter_uses_only_sanitized_temp_png_and_fixed_placement(self):
        clips = [
            ReelSegment("a", 0, 3, FAKE_MP4),
            ReelSegment("b", 0, 3, FAKE_MP4),
        ]
        captured = {}
        def fake_execute(cmd, *, capture_output, check, timeout):
            graph = cmd[cmd.index("-filter_complex") + 1]
            inputs = [cmd[i + 1] for i, arg in enumerate(cmd) if arg == "-i"]
            logo_path = Path(inputs[-1])
            captured["graph"] = graph
            captured["map"] = cmd[cmd.index("-map") + 1]
            captured["path"] = logo_path.name
            captured["logo"] = logo_path.read_bytes()
            Path(cmd[-1]).write_bytes(FAKE_MP4)
            return subprocess.CompletedProcess(cmd, 0, b"", b"")
        with (
            patch("reel_export.shutil.which", return_value="/usr/bin/ffmpeg"),
            patch("reel_export.subprocess.run", side_effect=fake_execute),
        ):
            result = render_test_reel(
                clips, logo_png_bytes=make_logo(metadata=True)
            )
        self.assertEqual(result, FAKE_MP4)
        self.assertEqual(captured["map"], "[video_logo]")
        self.assertEqual(captured["path"], "brand_logo.png")
        self.assertIn("overlay=x=W-w-32:y=48:shortest=1:format=auto", captured["graph"])
        self.assertIn("[video][2:v:0]overlay=", captured["graph"])
        self.assertNotIn(b"PRIVATE TEST METADATA", captured["logo"])


@unittest.skipUnless(
    shutil.which("ffmpeg") and shutil.which("ffprobe"),
    "FFmpeg und ffprobe erforderlich",
)
class LogoRealVideoTests(unittest.TestCase):
    def test_real_logo_always_visible_with_text_fade_audio_and_correct_length(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            clips = [
                ReelSegment("a", 0, 3, make_clip(folder, "one", "red", audio=True)),
                ReelSegment("b", 0, 3, make_clip(folder, "two", "blue")),
            ]
            for mode, audio_mode in (("cut", "mute"), ("fade", "original")):
                with self.subTest(mode=mode, audio=audio_mode):
                    output = folder / f"output_{mode}.mp4"
                    output.write_bytes(render_test_reel(
                        clips,
                        logo_png_bytes=make_logo(),
                        title_text="Traumhafte Bergstraßen",
                        cta_text="Mehr entdecken",
                        transition_mode=mode, fade_duration_seconds=0.5,
                        audio_mode=audio_mode,
                    ))
                    info = video_info(output)
                    expected = 5.5 if mode == "fade" else 6.0
                    self.assertAlmostEqual(
                        float(info["format"]["duration"]), expected, delta=0.08
                    )
                    self.assertEqual(
                        (info["streams"][0]["width"], info["streams"][0]["height"]),
                        (540, 960),
                    )
                    self.assertEqual(
                        [stream["codec_type"] for stream in info["streams"]],
                        ["video", "audio"] if audio_mode == "original" else ["video"],
                    )
                    for timestamp in (0.4, expected / 2.0, expected - 0.4):
                        # Opaque yellow logo: red + green high, blue low.
                        red, green, blue = pixel_at(output, timestamp, 430, 90)
                        self.assertGreater(red, 160, (timestamp, red, green, blue))
                        self.assertGreater(green, 140, (timestamp, red, green, blue))
                        self.assertLess(blue, 100, (timestamp, red, green, blue))


if __name__ == "__main__":
    unittest.main()
