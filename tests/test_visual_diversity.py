"""Tests für visuell doppelte Landschaftsszenen und unterschiedliche Action-Momente."""

import unittest
from io import BytesIO

from PIL import Image, ImageDraw

from batch_frames import FrameCache
from candidate_windows import CandidateWindow
from content_understanding import SceneObservation
from frame_sampler import SampledFrame
from intent_ranking import rank_for_goal
from user_goals import EditingGoal
from visual_diversity import (
    VisualDiversityError, fingerprint_jpeg, fingerprint_window,
    likely_same_camera_view,
)


def _jpeg(background_variant=0, motorbike_offset=0):
    """Ein synthetisches Berg/Brückenbild mit kleinem bewegtem Fahrzeug."""
    image = Image.new("RGB", (240, 144), (25, 75, 55))
    draw = ImageDraw.Draw(image)
    if background_variant == 0:
        draw.polygon([(0, 40), (70, 5), (130, 60), (240, 15), (240, 85), (0, 90)],
                     fill=(135, 150, 145))
        draw.polygon([(0, 95), (240, 80), (240, 130), (0, 140)], fill=(95, 100, 96))
        draw.line([(0, 100), (240, 85)], fill=(230, 220, 200), width=5)
    else:
        draw.polygon([(0, 10), (240, 12), (220, 130), (0, 120)], fill=(20, 35, 90))
        for i in range(10):
            x = i * 25 + 5
            draw.rectangle((x, i % 2 * 10, x + 6, 140), fill=(215, 180, 40))
    x = 70 + motorbike_offset
    draw.ellipse((x, 100, x + 6, 106), fill=(220, 30, 20))
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=86)
    return buffer.getvalue()


def _scene(start, *, source_id="video-1", action=False):
    return SceneObservation(
        window=CandidateWindow(source_id, start, start + 3),
        categories=("travel_outdoor", "motorcycle_action"),
        visual_tags=("motorcycle", "cornering", "scenery"),
        summary="Brücke in bewaldetem Tal mit Motorrad",
        evidence="Bäume, Straße und Fahrzeuge erkennbar",
        impact=4, technical_quality=4,
        prominence=(("motorcycle", 4), ("scenery", 5)),
    )


class SimilarViewTests(unittest.TestCase):
    def test_moving_motorcycles_same_background_is_one_view(self):
        a = tuple(fingerprint_jpeg(_jpeg(0, offset)) for offset in (0, 5, 10))
        b = tuple(fingerprint_jpeg(_jpeg(0, offset)) for offset in (15, 20, 25))
        self.assertTrue(likely_same_camera_view(a, b))

    def test_visually_different_background_is_not_same(self):
        a = tuple(fingerprint_jpeg(_jpeg(0, offset)) for offset in (0, 5, 10))
        b = tuple(fingerprint_jpeg(_jpeg(1, offset)) for offset in (0, 5, 10))
        self.assertFalse(likely_same_camera_view(a, b))

    def test_insufficient_samples_not_fake_duplicate(self):
        fp = fingerprint_jpeg(_jpeg())
        self.assertFalse(likely_same_camera_view((fp,), (fp,)))

    def test_invalid_jpeg_does_not_fake_duplicate(self):
        with self.assertRaises(VisualDiversityError):
            fingerprint_jpeg(b"not a jpeg")

    def test_scenic_ranking_only_one_similar_view(self):
        first = _scene(0)
        second = _scene(4)
        signature_a = tuple(fingerprint_jpeg(_jpeg(0, i)) for i in (0, 5, 10))
        signature_b = tuple(fingerprint_jpeg(_jpeg(0, i)) for i in (15, 20, 25))
        result = rank_for_goal(
            [first, second],
            EditingGoal("Landschaften, Berge", style="scenic",
                        focus_tags=("scenery", "mountains"),
                        deemphasized_tags=("motorcycle",)),
            scene_fingerprints={
                first.window: signature_a, second.window: signature_b,
            },
        )
        self.assertEqual(len(result.ranked_scenes), 1)
        self.assertEqual(result.repeated_views_suppressed, 1)
        self.assertIn("gleicher Kameraansicht", result.notice)
        self.assertIn("mountains", result.notice)

    def test_action_repeated_view_but_different_moments_allowed(self):
        first = _scene(0)
        second = _scene(4)
        fp = tuple(fingerprint_jpeg(_jpeg(0, i)) for i in (0, 5, 10))
        result = rank_for_goal(
            [first, second],
            EditingGoal("Motorräder in Kurven",
                        style="action", focus_tags=("cornering",)),
            scene_fingerprints={first.window: fp, second.window: fp},
        )
        self.assertEqual(len(result.ranked_scenes), 2)
        self.assertEqual(result.repeated_views_suppressed, 0)

    def test_other_source_not_collapsed_without_evidence(self):
        first = _scene(0, source_id="video-1")
        second = _scene(0, source_id="video-2")
        fp = tuple(fingerprint_jpeg(_jpeg(0, i)) for i in (0, 5, 10))
        result = rank_for_goal(
            [first, second], EditingGoal("Landschaften", style="scenic",
                                         focus_tags=("scenery",)),
            scene_fingerprints={first.window: fp, second.window: fp},
        )
        self.assertEqual(len(result.ranked_scenes), 2)

    def test_window_sampling_reuses_existing_jpeg_frames(self):
        frames = tuple(
            SampledFrame(timestamp_seconds=0.5 * i, jpeg_bytes=_jpeg(0, i * 2))
            for i in range(12)
        )
        cache = FrameCache("video-1", duration_seconds=6, sample_rate=2, frames=frames)
        result = fingerprint_window(cache, CandidateWindow("video-1", 0, 3))
        self.assertEqual(len(result), 3)


if __name__ == "__main__":
    unittest.main()
