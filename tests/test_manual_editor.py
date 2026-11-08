"""Offline-Tests für manuelle Reel-Schnitte ohne neue KI-Analyse."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from manual_editor import (
    ClipEdit, EditorError, prepare_edited_segments, validate_manual_edits,
)
from reel_export import render_test_reel
from video_probe import VideoMetadata


FAKE_MP4 = b"\x00\x00\x00\x18ftypisom0000"


def edit(start, end, original_start, original_end, *, source="video-1", data=FAKE_MP4):
    return ClipEdit(
        source_id=source,
        start_seconds=start,
        end_seconds=end,
        suggested_start=original_start,
        suggested_end=original_end,
        mp4_bytes=data,
    )


def original_metadata(source_id="video-1", duration=32.0):
    return VideoMetadata(
        source_id=source_id, path="/fake/original.mp4",
        duration_seconds=duration,
        width=1920, height=1080, fps=24.0,
        has_audio=False, video_codec="h264",
    )


class EditorValidationTests(unittest.TestCase):
    def test_original_windows_reused_without_ffmpeg_or_originals(self):
        scenes = [
            edit(10.5, 13.5, 10.5, 13.5),
            edit(19.5, 22.5, 19.5, 22.5),
        ]
        with (
            patch("manual_editor._render_mp4") as render,
            patch("manual_editor.probe_video") as probe,
        ):
            segments = prepare_edited_segments(scenes)
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0].mp4_bytes, FAKE_MP4)
        render.assert_not_called()
        probe.assert_not_called()

    def test_change_shortens_or_extends_fine_window_locally(self):
        scenes = [
            edit(10, 14.5, 10.5, 13.5),
            edit(19.5, 22.5, 19.5, 22.5),
        ]
        with (
            patch("manual_editor.probe_video", return_value=original_metadata()),
            patch("manual_editor.detect_hard_cuts", return_value=(8.0, 18.0, 24.0)),
            patch("manual_editor._render_mp4", return_value=FAKE_MP4) as render,
        ):
            segments = prepare_edited_segments(
                scenes, [Path("/fake/original.mp4")],
            )
        self.assertEqual([(x.start_seconds, x.end_seconds) for x in segments],
                         [(10.0, 14.5), (19.5, 22.5)])
        render.assert_called_once_with("/fake/original.mp4", 10.0, 14.5)

    def test_rejects_new_window_crossing_a_cut_before_render(self):
        scenes = [
            edit(22.5, 25.5, 19.5, 22.5),
            edit(10.5, 13.5, 10.5, 13.5),
        ]
        with (
            patch("manual_editor.probe_video", return_value=original_metadata()),
            patch("manual_editor.detect_hard_cuts", return_value=(8.0, 18.0, 24.0)),
            patch("manual_editor._render_mp4") as render,
        ):
            with self.assertRaisesRegex(EditorError, "harten Bildwechsel"):
                prepare_edited_segments(scenes, [Path("/fake/original.mp4")])
        render.assert_not_called()

    def test_cut_detection_failure_blocks_new_trim(self):
        from shot_boundaries import ShotDetectionError
        scenes = [edit(10, 12, 10.5, 13.5), edit(19.5, 22.5, 19.5, 22.5)]
        with (
            patch("manual_editor.probe_video", return_value=original_metadata()),
            patch("manual_editor.detect_hard_cuts", side_effect=ShotDetectionError()),
            patch("manual_editor._render_mp4") as render,
        ):
            with self.assertRaisesRegex(EditorError, "Schnittprüfung"):
                prepare_edited_segments(scenes, [Path("/fake/original.mp4")])
        render.assert_not_called()

    def test_editor_requires_originals_only_for_changed_scenes(self):
        scenes = [edit(10, 13, 10.5, 13.5), edit(19.5, 22.5, 19.5, 22.5)]
        with self.assertRaisesRegex(EditorError, "Originalvideos"):
            prepare_edited_segments(scenes)

    def test_rejects_edit_past_actual_file_end(self):
        scenes = [edit(7.5, 10.0, 7.0, 9.0), edit(1, 3, 1, 3)]
        with patch("manual_editor.probe_video", return_value=original_metadata(duration=9.0)):
            with self.assertRaisesRegex(EditorError, "Ende des Originalvideos"):
                prepare_edited_segments(scenes, [Path("/fake/original.mp4")])

    def test_rejects_invalid_and_too_long_intervals(self):
        for bad in [
            edit(10, 10.1, 10, 13),
            edit(10, 10, 10, 13),
            edit(-1, 2, 10, 13),
            edit(0, 11, 10, 13),
            edit(float("nan"), 3, 10, 13),
            edit(True, 3, 10, 13),
        ]:
            with self.subTest(bad=bad), self.assertRaises(EditorError):
                validate_manual_edits([
                    bad, edit(19.5, 22.5, 19.5, 22.5),
                ])

    def test_rejects_overlapping_manual_intervals_same_source(self):
        with self.assertRaisesRegex(EditorError, "überlappen"):
            validate_manual_edits([
                edit(10, 14, 10.5, 13.5),
                edit(13.5, 16, 19.5, 22.5),
            ])

    def test_allows_same_timestamps_for_different_sources(self):
        validate_manual_edits([
            edit(2, 5, 2, 5, source="video-1"),
            edit(2, 5, 2, 5, source="video-2"),
        ])

    def test_source_not_present_in_originals_is_rejected(self):
        scenes = [
            edit(3, 5, 3, 6, source="video-2"),
            edit(6, 8, 6, 8),
        ]
        with patch("manual_editor.probe_video", return_value=original_metadata()):
            with self.assertRaisesRegex(EditorError, "unbekanntes Originalvideo"):
                prepare_edited_segments(scenes, [Path("/fake/original.mp4")])


class EditorFFmpegIntegrationTests(unittest.TestCase):
    @unittest.skipUnless(
        shutil.which("ffmpeg") and shutil.which("ffprobe"),
        "FFmpeg und ffprobe werden benötigt",
    )
    def test_real_trim_and_extension_from_same_original_then_export(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "montage.mp4"
            command = [
                shutil.which("ffmpeg"), "-hide_banner", "-nostdin",
                "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=c=red:s=160x90:r=24:d=4",
                "-f", "lavfi", "-i", "color=c=green:s=160x90:r=24:d=4",
                "-filter_complex",
                "[0:v][1:v]concat=n=2:v=1:a=0[v]",
                "-map", "[v]", "-c:v", "mpeg4", "-q:v", "4", str(path),
            ]
            generated = subprocess.run(
                command, capture_output=True, check=False, timeout=30,
            )
            self.assertEqual(generated.returncode, 0, generated.stderr)

            scenes = [
                edit(0.5, 3.5, 1, 2),  # Verlängert, bleibt in Rot
                edit(4.5, 7, 5, 6),  # Verlängert, bleibt in Grün
            ]
            # Echte FFmpeg-Renderer und Schnittprüfung, keine Mocks.
            segments = prepare_edited_segments(scenes, [path])
            self.assertEqual(len(segments), 2)
            self.assertEqual([round(s.end_seconds - s.start_seconds, 1)
                              for s in segments], [3.0, 2.5])
            self.assertTrue(all(s.mp4_bytes[4:8] == b"ftyp" for s in segments))
            final = Path(directory) / "edited.mp4"
            final.write_bytes(render_test_reel(segments, background_mode="blur"))
            probe = subprocess.run(
                [
                    shutil.which("ffprobe"), "-v", "error",
                    "-show_entries", "format=duration:stream=width,height",
                    "-of", "json", str(final),
                ],
                capture_output=True, text=True, timeout=20, check=False,
            )
            self.assertEqual(probe.returncode, 0, probe.stderr)
            result = json.loads(probe.stdout)
            self.assertAlmostEqual(
                float(result["format"]["duration"]), 5.5, delta=0.15
            )
            self.assertEqual(
                (result["streams"][0]["width"], result["streams"][0]["height"]),
                (540, 960),
            )


if __name__ == "__main__":
    unittest.main()
