"""Offline-Checks für das Ausblenden veralteter bearbeiteter Szenen."""

import unittest

from scene_preview_state import (
    PreviewStateError, expire_scene_preview, read_current_scene_preview,
    scene_signature, store_scene_preview,
)


MP4 = b"\x00\x00\x00\x18ftypisom0000"
CACHE_KEY = "velocut_scene_cut_preview_demo_1"


class PreviewInvalidationTests(unittest.TestCase):
    def test_change_of_slider_end_changes_signature(self):
        first = scene_signature("preview", 1, "video-1", 10.5, 14.0)
        second = scene_signature("preview", 1, "video-1", 10.5, 13.75)
        self.assertNotEqual(first, second)

    def test_original_and_edited_preview_have_independent_state(self):
        first = scene_signature("preview", 1, "video-1", 10.5, 14.0)
        state = {"velocut_preview_clips": [{"mp4_bytes": MP4}]}
        store_scene_preview(state, CACHE_KEY, first, MP4)
        self.assertEqual(
            read_current_scene_preview(
                state, CACHE_KEY, first, uploads_match=True
            )["mp4_bytes"], MP4
        )
        expire_scene_preview(state, CACHE_KEY)
        self.assertNotIn(CACHE_KEY, state)
        self.assertTrue(state[f"{CACHE_KEY}_outdated"])
        self.assertEqual(
            state["velocut_preview_clips"][0]["mp4_bytes"], MP4,
        )
        self.assertIsNone(
            read_current_scene_preview(
                state, CACHE_KEY, first, uploads_match=True,
            )
        )

    def test_old_player_is_hidden_if_changed_start_or_end(self):
        old = scene_signature("preview", 1, "video-1", 10.5, 14.0)
        new = scene_signature("preview", 1, "video-1", 10.5, 13.75)
        state = {}
        store_scene_preview(state, CACHE_KEY, old, MP4)
        self.assertIsNone(
            read_current_scene_preview(
                state, CACHE_KEY, new, uploads_match=True
            )
        )
        self.assertNotIn(CACHE_KEY, state)
        self.assertTrue(state[f"{CACHE_KEY}_outdated"])

    def test_reupload_other_video_invalidates_old_preview(self):
        key = scene_signature("preview", 1, "video-1", 10.5, 14)
        state = {}
        store_scene_preview(state, CACHE_KEY, key, MP4)
        self.assertIsNone(
            read_current_scene_preview(
                state, CACHE_KEY, key, uploads_match=False
            )
        )
        self.assertNotIn(CACHE_KEY, state)

    def test_new_preview_after_change_clears_outdated_notice(self):
        old = scene_signature("preview", 1, "video-1", 10.5, 14.0)
        new = scene_signature("preview", 1, "video-1", 10.5, 13.75)
        state = {}
        store_scene_preview(state, CACHE_KEY, old, MP4)
        expire_scene_preview(state, CACHE_KEY)
        store_scene_preview(state, CACHE_KEY, new, MP4)
        self.assertFalse(state.get(f"{CACHE_KEY}_outdated", False))
        self.assertIsNotNone(
            read_current_scene_preview(
                state, CACHE_KEY, new, uploads_match=True
            )
        )

    def test_temporary_invalid_number_inputs_do_not_crash_signature(self):
        state = {}
        signature = scene_signature("preview", 1, "video-1", 14.0, 13.75)
        store_scene_preview(state, CACHE_KEY, signature, MP4)
        self.assertIsNotNone(
            read_current_scene_preview(
                state, CACHE_KEY, signature, uploads_match=True
            )
        )
        # validate_single_edit rejects the invalid cut before rendering.

    def test_invalid_numbers_and_corrupt_mp4_are_rejected(self):
        with self.assertRaises(PreviewStateError):
            scene_signature("preview", 1, "video-1", 10.5, float("nan"))
        with self.assertRaises(PreviewStateError):
            scene_signature("preview", 0, "video-1", 10.5, 14)
        with self.assertRaises(PreviewStateError):
            store_scene_preview({}, CACHE_KEY, "bad", MP4)
        with self.assertRaises(PreviewStateError):
            store_scene_preview({}, CACHE_KEY, "a" * 64, b"not-mp4")


if __name__ == "__main__":
    unittest.main()
