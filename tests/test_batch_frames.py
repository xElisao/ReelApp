"""Tests für einmalige FFmpeg-Extraktion und wiederverwendbaren FrameCache."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from batch_frames import FrameCache, extract_frame_cache, select_cached_frames
from candidate_windows import CandidateWindow
from frame_sampler import FrameSampleError, SampledFrame


def fake_cache():
    return FrameCache(
        source_id="v1", duration_seconds=10, sample_rate=2,
        frames=tuple(
            SampledFrame(i / 2, b"\xff\xd8data\xff\xd9")
            for i in range(20)
        ),
    )


class SelectCachedFramesTests(unittest.TestCase):
    def test_even_distribution_inside_window_without_duplicates(self):
        selected = select_cached_frames(
            fake_cache(), CandidateWindow("v1", 2, 6), frame_count=5
        )
        self.assertEqual(len(selected), 5)
        times = [x.timestamp_seconds for x in selected]
        self.assertEqual(times, sorted(times))
        self.assertEqual(len(set(times)), 5)
        self.assertTrue(all(2 <= time <= 6 for time in times))

    def test_fewer_available_frames_than_requested(self):
        result = select_cached_frames(
            fake_cache(), CandidateWindow("v1", 0, 0.5),
            frame_count=8,
        )
        self.assertEqual(len(result), 2)

    def test_rejects_wrong_source(self):
        with self.assertRaises(ValueError):
            select_cached_frames(fake_cache(), CandidateWindow("other", 1, 2))

    def test_missing_frames_are_reported(self):
        cache = FrameCache("v1", 10, 2, (SampledFrame(0, b"jpeg"),))
        with self.assertRaises(FrameSampleError):
            select_cached_frames(cache, CandidateWindow("v1", 3, 5))


class BatchExtractionTests(unittest.TestCase):
    def test_duration_budget_checked_before_ffmpeg(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "existing.mp4"
            path.write_bytes(b"dummy")
            with self.assertRaisesRegex(ValueError, "Limit"):
                extract_frame_cache(
                    path, source_id="v1", duration_seconds=120,
                    sample_rate=2, max_frames=125,
                )

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg is not available")
    def test_real_short_generated_video(self):
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "synthetic.mp4"
            produced = subprocess.run(
                [
                    shutil.which("ffmpeg"), "-hide_banner", "-nostdin",
                    "-loglevel", "error",
                    "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=25",
                    "-t", "3", "-an", "-c:v", "mpeg4",
                    str(video),
                ],
                check=False, capture_output=True, timeout=30,
            )
            if produced.returncode != 0:
                self.fail(f"FFmpeg test video generation failed: {produced.stderr!r}")
            cache = extract_frame_cache(
                video, source_id="synthetic", duration_seconds=3.0,
                timeout_seconds=30,
            )
            self.assertGreaterEqual(len(cache.frames), 5)
            self.assertLessEqual(len(cache.frames), 7)
            for frame in cache.frames:
                self.assertTrue(frame.jpeg_bytes.startswith(b"\xff\xd8"))
                self.assertTrue(frame.jpeg_bytes.endswith(b"\xff\xd9"))
            selected = select_cached_frames(
                cache, CandidateWindow("synthetic", 0, 3), frame_count=3,
            )
            self.assertEqual(len(selected), 3)


if __name__ == "__main__":
    unittest.main()
