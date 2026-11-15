"""Offline-Regressionstests der Content- und Intent-Pipeline."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from candidate_windows import CandidateWindow
from content_understanding import (
    ContentUnderstandingError, SceneObservation, detected_categories, observe_window,
)
from frame_sampler import SampledFrame
from intent_ranking import rank_for_goal
from user_goals import EditingGoal, GoalParsingError, understand_user_goal
from video_probe import VideoMetadata


def _client_response(data: dict):
    client = Mock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(
            content=json.dumps(data, ensure_ascii=False)
        ))]
    )
    return client


def _scene(start, end, cats, tags, *, impact=4.0):
    return SceneObservation(
        window=CandidateWindow("v1", start, end),
        categories=tuple(cats), visual_tags=tuple(tags),
        summary="Beobachtete Testszene",
        evidence="Bilder zeigen die benannten Objekte",
        impact=impact, technical_quality=4.0,
    )


class ContentTests(unittest.TestCase):
    def setUp(self):
        self.video = VideoMetadata(
            source_id="v1", path="/tmp/video.mp4", duration_seconds=10,
            width=1920, height=1080, fps=30, has_audio=False, video_codec="h264",
        )

    def test_vision_uses_real_frames_and_multiple_categories(self):
        client = _client_response({
            "categories": ["motorcycle_action", "travel_outdoor"],
            "visual_tags": ["motorcycle", "mountains", "scenery"],
            "summary": "Motorrad auf einer Bergstraße",
            "evidence": "Motorrad und Bergkulisse sichtbar",
            "impact": 4,
            "technical_quality": 5,
        })
        scene = observe_window(
            client, self.video, CandidateWindow("v1", 0, 8),
            frames=[SampledFrame(2, b"\xff\xd8testjpeg\xff\xd9")],
        )
        self.assertEqual(scene.categories, ("motorcycle_action", "travel_outdoor"))
        self.assertIn("mountains", scene.visual_tags)
        items = client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
        self.assertTrue(any(i.get("type") == "image_url" for i in items))

    def test_hallucinated_unknown_tag_is_rejected(self):
        client = _client_response({
            "categories": ["general"], "visual_tags": ["magical_unicorn"],
            "summary": "Unbekannt", "evidence": "Kein Beleg",
            "impact": 2, "technical_quality": 4,
        })
        with self.assertRaises(ContentUnderstandingError):
            observe_window(
                client, self.video, CandidateWindow("v1", 0, 8),
                frames=[SampledFrame(2, b"frame")],
            )

    def test_prominence_from_real_frames_is_retained(self):
        client = _client_response({
            "categories": ["motorcycle_action", "travel_outdoor"],
            "visual_tags": ["motorcycle", "scenery", "mountains"],
            "summary": "Kleine Motorräder vor Bergpanorama",
            "evidence": "Berge füllen den Hintergrund, kleine Motorräder vorne",
            "impact": 4, "technical_quality": 5,
            "prominence": {"motorcycle": 1, "scenery": 5, "mountains": 4},
        })
        scene = observe_window(
            client, self.video, CandidateWindow("v1", 0, 8),
            frames=[SampledFrame(2, b"jpeg")],
        )
        self.assertEqual(scene.prominence_for("motorcycle"), 1)
        self.assertEqual(scene.prominence_for("scenery"), 5)

    def test_invalid_prominence_is_not_silently_trusted(self):
        client = _client_response({
            "categories": ["travel_outdoor"], "visual_tags": ["scenery"],
            "summary": "Landschaft", "evidence": "Sichtbare Hügel",
            "impact": 4, "technical_quality": 4,
            "prominence": {"motorcycle": 5},
        })
        with self.assertRaises(ContentUnderstandingError):
            observe_window(
                client, self.video, CandidateWindow("v1", 0, 8),
                frames=[SampledFrame(2, b"jpeg")],
            )

    def test_auto_detected_categories_ordered_by_frequency(self):
        scenes = [
            _scene(0, 3, ("motorcycle_action", "travel_outdoor"), ("motorcycle",)),
            _scene(4, 7, ("travel_outdoor",), ("mountains",)),
        ]
        self.assertEqual(detected_categories(scenes)[0], "travel_outdoor")


class GoalTests(unittest.TestCase):
    def test_plain_language_goal(self):
        client = _client_response({
            "style": "action", "focus_tags": ["cornering"],
            "required_tags": [], "excluded_tags": [],
            "uncheckable_requests": [],
        })
        goal = understand_user_goal(client, "Zeig die dynamischen Kurven")
        self.assertEqual(goal.focus_tags, ("cornering",))
        self.assertEqual(goal.original_instruction, "Zeig die dynamischen Kurven")

    def test_explicit_wheelie_is_required(self):
        client = _client_response({
            "style": "action", "focus_tags": ["wheelie"],
            "required_tags": ["wheelie"], "excluded_tags": [],
            "uncheckable_requests": [],
        })
        goal = understand_user_goal(client, "Zeig den Wheelie")
        self.assertEqual(goal.required_tags, ("wheelie",))

    def test_uploaded_motorrad_prompt_is_not_lost_as_uncheckable(self):
        """Regression: reale erste Staging-Auswertung markierte alles als ungeprüft."""
        instruction = (
            "Erkenne die interessantesten Motorrad-Durchfahrten und "
            "dynamischen Kurven. Bevorzuge Momente, in denen die "
            "Motorräder gut sichtbar sind."
        )
        client = _client_response({
            "style": "action", "focus_tags": [],
            "required_tags": [], "excluded_tags": [],
            "uncheckable_requests": [
                "interessanteste Motorrad-Durchfahrten",
                "dynamische Kurven",
                "Motorräder gut sichtbar",
            ],
        })
        goal = understand_user_goal(client, instruction)
        self.assertIn("motorcycle", goal.focus_tags)
        self.assertIn("cornering", goal.focus_tags)
        self.assertEqual(goal.original_instruction, instruction)
        action_scene = _scene(
            0, 3, ("motorcycle_action",), ("motorcycle", "cornering"),
        )
        result = rank_for_goal([action_scene], goal)
        self.assertEqual(len(result.ranked_scenes), 1)
        self.assertIn("nicht sicher", result.notice)

    def test_negative_motorcycle_words_do_not_become_positive_focus(self):
        client = _client_response({
            "style": "scenic", "focus_tags": [],
            "required_tags": [], "excluded_tags": ["motorcycle"],
            "uncheckable_requests": ["sonstige Wünsche"],
        })
        goal = understand_user_goal(
            client, "Bitte ohne Motorräder, nur die Landschaft."
        )
        self.assertNotIn("motorcycle", goal.focus_tags)
        self.assertIn("scenery", goal.focus_tags)

    def test_landscape_request_background_motorcycles_not_hard_excluded(self):
        """Regression: echtes JSON aus dem zweiten Streamlit-Praxistest."""
        instruction = (
            "Zeige die schönsten Berglandschaften, beeindruckende Aussichten "
            "und die landschaftlich attraktivsten Momente. Die Motorräder "
            "sollen dabei nicht im Mittelpunkt stehen."
        )
        client = _client_response({
            "style": "scenic",
            "focus_tags": ["scenery", "mountains"],
            "required_tags": [],
            "excluded_tags": ["motorcycle"],
            "uncheckable_requests": [],
        })
        goal = understand_user_goal(client, instruction)
        self.assertEqual(goal.focus_tags, ("scenery", "mountains"))
        self.assertNotIn("motorcycle", goal.excluded_tags)
        self.assertIn("motorcycle", goal.deemphasized_tags)
        scenery_with_motorcycle = _scene(
            0, 3, ("motorcycle_action", "travel_outdoor"),
            ("motorcycle", "mountains", "scenery"),
        )
        result = rank_for_goal([scenery_with_motorcycle], goal)
        self.assertEqual(len(result.ranked_scenes), 1)
        self.assertIn("Nebenmotiv", result.ranked_scenes[0].explanation)

    def test_explicit_without_motorcycles_keeps_hard_exclusion(self):
        client = _client_response({
            "style": "scenic",
            "focus_tags": ["scenery"],
            "required_tags": [],
            "excluded_tags": ["motorcycle"],
            "deemphasized_tags": [],
            "uncheckable_requests": [],
        })
        goal = understand_user_goal(
            client, "Bitte nur die Berge und keine Motorräder zeigen."
        )
        self.assertEqual(goal.excluded_tags, ("motorcycle",))
        self.assertEqual(goal.deemphasized_tags, ())
        scene = _scene(
            0, 3, ("travel_outdoor",), ("mountains", "motorcycle"),
        )
        self.assertEqual(rank_for_goal([scene], goal).ranked_scenes, ())

    def test_model_can_emit_soft_background_field(self):
        client = _client_response({
            "style": "scenic",
            "focus_tags": ["scenery", "mountains"],
            "required_tags": [],
            "excluded_tags": [],
            "deemphasized_tags": ["motorcycle"],
            "uncheckable_requests": [],
        })
        goal = understand_user_goal(
            client, "Landschaften bevorzugen, Motorrad nur als Nebenmotiv."
        )
        self.assertEqual(goal.deemphasized_tags, ("motorcycle",))

    def test_scenic_focus_accepts_visible_forests_not_invented_mountains(self):
        goal = EditingGoal(
            "Schöne Landschaften",
            style="scenic",
            focus_tags=("scenery",),
        )
        forest = _scene(0, 3, ("travel_outdoor",), ("forest",))
        ranked = rank_for_goal([forest], goal)
        self.assertEqual(len(ranked.ranked_scenes), 1)
        self.assertIn("scenery", ranked.ranked_scenes[0].matched_tags)
        mountains_only = rank_for_goal(
            [forest], EditingGoal("Berge", style="scenic", focus_tags=("mountains",)),
        )
        self.assertEqual(mountains_only.ranked_scenes, ())

    def test_empty_goal_is_balanced_without_api(self):
        client = Mock()
        goal = understand_user_goal(client, "")
        self.assertEqual(goal.style, "balanced")
        client.chat.completions.create.assert_not_called()

    def test_invalid_tags_refused(self):
        client = _client_response({
            "style": "action", "focus_tags": ["unsupported"],
            "required_tags": [], "excluded_tags": [],
            "uncheckable_requests": [],
        })
        with self.assertRaises(GoalParsingError):
            understand_user_goal(client, "Das nicht unterstützte Ding")


class RankingTests(unittest.TestCase):
    def setUp(self):
        self.action = _scene(
            0, 3, ("motorcycle_action",), ("motorcycle", "cornering"), impact=4,
        )
        self.scenic = _scene(
            4, 7, ("travel_outdoor", "motorcycle_action"),
            ("scenery", "mountains", "motorcycle"), impact=4,
        )
        self.scenes = [self.action, self.scenic]

    def test_same_video_two_different_goals(self):
        action = rank_for_goal(
            self.scenes,
            EditingGoal("Zeig Kurven", style="action", focus_tags=("cornering",)),
        )
        scenic = rank_for_goal(
            self.scenes,
            EditingGoal("Zeig Berge", style="scenic", focus_tags=("mountains",)),
        )
        self.assertEqual(action.ranked_scenes[0].observation, self.action)
        self.assertEqual(scenic.ranked_scenes[0].observation, self.scenic)

    def test_composition_changes_scenic_ranking_not_just_tag_presence(self):
        def scene(start, scenic_strength, motorcycle_strength):
            return SceneObservation(
                window=CandidateWindow("v1", start, start + 3),
                categories=("travel_outdoor", "motorcycle_action"),
                visual_tags=("motorcycle", "scenery", "mountains"),
                summary="Bergpanorama mit Motorrädern",
                evidence="Berge und Motorräder sichtbar",
                impact=4, technical_quality=4,
                prominence=(
                    ("motorcycle", motorcycle_strength),
                    ("scenery", scenic_strength),
                    ("mountains", scenic_strength),
                ),
            )
        motorcycle_central = scene(0, 1, 5)
        landscape_central = scene(4, 5, 1)
        result = rank_for_goal(
            [motorcycle_central, landscape_central],
            EditingGoal(
                "Landschaft im Mittelpunkt, Motorräder als Nebenmotiv",
                style="scenic", focus_tags=("scenery", "mountains"),
                deemphasized_tags=("motorcycle",),
            ),
        )
        self.assertEqual(len(result.ranked_scenes), 2)
        self.assertEqual(result.ranked_scenes[0].observation, landscape_central)
        self.assertGreater(
            result.ranked_scenes[0].score, result.ranked_scenes[1].score
        )
        self.assertIn("Bilddominanz", result.ranked_scenes[0].explanation)

    def test_missing_wheelie_is_not_invented(self):
        result = rank_for_goal(
            self.scenes,
            EditingGoal("Zeig den Wheelie", required_tags=("wheelie",)),
        )
        self.assertFalse(result.ranked_scenes)
        self.assertIn("wheelie", result.notice)

    def test_partial_uncheckable_request_still_finds_visible_target(self):
        result = rank_for_goal(
            self.scenes,
            EditingGoal(
                "Kurven bei Motorengeräuschen",
                style="action",
                focus_tags=("cornering",),
                uncheckable_requests=("Motorengeräusche",),
            ),
        )
        self.assertEqual(len(result.ranked_scenes), 1)
        self.assertEqual(result.ranked_scenes[0].observation, self.action)
        self.assertIn("Motorengeräusche", result.notice)

    def test_unknown_uncheckable_request_does_not_fake_match(self):
        result = rank_for_goal(
            self.scenes,
            EditingGoal("Spezialereignis", uncheckable_requests=("Spezialereignis",)),
        )
        self.assertFalse(result.ranked_scenes)
        self.assertIn("Spezialereignis", result.notice)

    def test_user_category_override_is_respected(self):
        result = rank_for_goal(
            self.scenes, EditingGoal(""), category_override="travel_outdoor",
        )
        self.assertEqual(len(result.ranked_scenes), 1)
        self.assertEqual(result.ranked_scenes[0].observation, self.scenic)

    def test_exclusion(self):
        result = rank_for_goal(
            self.scenes,
            EditingGoal("Ohne Berge", excluded_tags=("mountains",)),
        )
        self.assertEqual(len(result.ranked_scenes), 1)
        self.assertEqual(result.ranked_scenes[0].observation, self.action)

    def test_overlapping_windows_not_recommended_together(self):
        other = _scene(
            2, 5, ("motorcycle_action",), ("cornering",), impact=5,
        )
        result = rank_for_goal(
            [self.action, other], EditingGoal(""),
        )
        self.assertEqual(len(result.ranked_scenes), 1)

    def test_no_fitting_goal_returns_notice(self):
        result = rank_for_goal(
            self.scenes,
            EditingGoal("Sonnenuntergang", focus_tags=("sunset",)),
        )
        self.assertFalse(result.ranked_scenes)
        self.assertIn("Keine ausreichend", result.notice)


if __name__ == "__main__":
    unittest.main()
