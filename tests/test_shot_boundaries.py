"""Offline-Regression: echte harte Bildschnitte von Videoframes finden."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from shot_boundaries import crosses_hard_cut, detect_hard_cuts


class ClipBoundaryTests(unittest.TestCase):
    def test_inside_cut_rejected_and_boundary_cut_allowed(self):
        cuts = (8.0, 18.0, 24.0)
        self.assertTrue(crosses_hard_cut(7.5, 10.5, cuts))
        self.assertTrue(crosses_hard_cut(22.5, 25.5, cuts))
        self.assertFalse(crosses_hard_cut(10.5, 13.5, cuts))
        self.assertFalse(crosses_hard_cut(19.5, 22.5, cuts))
        self.assertFalse(crosses_hard_cut(8.0, 11.0, cuts))
        self.assertFalse(crosses_hard_cut(21.0, 24.0, cuts))

    def test_invalid_intervals_are_rejected(self):
        with self.assertRaises(ValueError):
            crosses_hard_cut(10.5, 10.5, ())
        with self.assertRaises(ValueError):
            crosses_hard_cut(-1, 3, ())


class FFmpegShotBoundaryTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg unavailable")
    def test_synthetic_red_blue_green_cuts(self):
        with tempfile.TemporaryDirectory() as directory:
            video_path = Path(directory) / "three_shots.mp4"
            command = [
                shutil.which("ffmpeg"), "-hide_banner", "-nostdin",
                "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=c=red:s=320x180:r=10:d=2",
                "-f", "lavfi", "-i", "color=c=blue:s=320x180:r=10:d=2",
                "-f", "lavfi", "-i", "color=c=green:s=320x180:r=10:d=2",
                "-filter_complex",
                "[0:v][1:v][2:v]concat=n=3:v=1:a=0,format=yuv420p[v]",
                "-map", "[v]", "-c:v", "mpeg4", "-q:v", "4",
                str(video_path),
            ]
            output = subprocess.run(
                command, capture_output=True, check=False, timeout=30,
            )
            self.assertEqual(output.returncode, 0, output.stderr.decode(
                "utf-8", errors="replace"
            ))
            cuts = detect_hard_cuts(video_path, duration_seconds=6)
            self.assertTrue(any(abs(cut - 2) <= 0.12 for cut in cuts), cuts)
            self.assertTrue(any(abs(cut - 4) <= 0.12 for cut in cuts), cuts)
            self.assertFalse(crosses_hard_cut(0, 1.9, cuts))
            self.assertTrue(crosses_hard_cut(1.5, 2.5, cuts))


if __name__ == "__main__":
    unittest.main()
