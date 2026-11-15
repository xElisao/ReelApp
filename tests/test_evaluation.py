"""Evaluation-Regressionstests ohne externe API."""

import unittest

from evaluate_recommendations import (
    EvaluationError, compare_predictions, load_and_compare, temporal_iou,
)


def window(start, end, source="video-1"):
    return {
        "source_id": source,
        "start_seconds": start,
        "end_seconds": end,
    }


class EvaluationTests(unittest.TestCase):
    def test_perfect_overlap(self):
        self.assertEqual(temporal_iou(window(1, 5), window(1, 5)), 1.0)

    def test_partial_overlap(self):
        self.assertAlmostEqual(temporal_iou(window(1, 5), window(3, 7)), 2 / 6)

    def test_other_file_never_overlaps(self):
        self.assertEqual(temporal_iou(window(1, 5), window(1, 5, "video-2")), 0)

    def test_two_references_and_two_hits(self):
        result = compare_predictions(
            [window(0, 3), window(5, 8)],
            [window(0, 3), window(5, 8)],
        )
        self.assertEqual(result["matched_count"], 2)
        self.assertEqual(result["precision_at_k"], 1.0)
        self.assertEqual(result["recall_at_k"], 1.0)

    def test_no_double_counting_one_reference(self):
        result = compare_predictions(
            [window(1, 5)], [window(1, 5), window(1.2, 4.8)]
        )
        self.assertEqual(result["matched_count"], 1)
        self.assertEqual(result["precision_at_k"], 0.5)
        self.assertEqual(result["recall_at_k"], 1.0)

    def test_missing_result_is_zero(self):
        result = compare_predictions([window(1, 5)], [])
        self.assertEqual(result["precision_at_k"], 0)
        self.assertEqual(result["recall_at_k"], 0)

    def test_invalid_interval_rejected(self):
        with self.assertRaises(EvaluationError):
            compare_predictions([window(5, 1)], [window(1, 2)])

    def test_requires_real_references(self):
        with self.assertRaises(EvaluationError):
            compare_predictions([], [window(1, 2)])

    def test_coarse_and_refined_separated(self):
        reference = {"goal_name": "Action", "reference_highlights": [window(2, 5)]}
        report = {
            "recommendations": [window(0, 8)],
            "refinement": {"suggestions": [window(2, 5)]},
        }
        coarse = load_and_compare(reference, report, stage="coarse")
        refined = load_and_compare(reference, report, stage="refined")
        self.assertEqual(coarse["matched_count"], 1)  # IoU 3/8 = 0.375
        self.assertGreater(refined["mean_matched_iou"], coarse["mean_matched_iou"])
        self.assertEqual(refined["matched_count"], 1)

    def test_refined_requires_actual_refinement(self):
        with self.assertRaisesRegex(EvaluationError, "Detailanalyse"):
            load_and_compare(
                {"reference_highlights": [window(1, 2)]},
                {"recommendations": []}, stage="refined",
            )


if __name__ == "__main__":
    unittest.main()
