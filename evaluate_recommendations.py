"""Evaluation echter Highlight-Vorschläge gegen menschlich markierte Zeitbereiche.

Eine Übereinstimmung wird über zeitliche Intersection-over-Union (IoU)
gezählt. Ein Vorschlag kann höchstens eine Referenz abdecken und umgekehrt.
Dies misst Zeitfenster-Treffer, nicht automatisch dramaturgische Schnittqualität.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


class EvaluationError(ValueError):
    pass


def _interval(item: Any) -> tuple[str, float, float]:
    if not isinstance(item, dict):
        raise EvaluationError("Zeitfenster muss ein JSON-Objekt sein.")
    source = item.get("source_id")
    start = item.get("start_seconds")
    end = item.get("end_seconds")
    if not isinstance(source, str) or not source.strip():
        raise EvaluationError("source_id fehlt.")
    if any(
        isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)
        for x in (start, end)
    ):
        raise EvaluationError("Zeitstempel müssen endliche Zahlen sein.")
    if start < 0 or end <= start:
        raise EvaluationError("Ungültiges Zeitfenster.")
    return source, float(start), float(end)


def temporal_iou(a: dict, b: dict) -> float:
    source_a, start_a, end_a = _interval(a)
    source_b, start_b, end_b = _interval(b)
    if source_a != source_b:
        return 0.0
    intersection = max(0.0, min(end_a, end_b) - max(start_a, start_b))
    if intersection <= 0:
        return 0.0
    union = (end_a - start_a) + (end_b - start_b) - intersection
    return intersection / union


def compare_predictions(
    reference_highlights: list[dict],
    predictions: list[dict],
    *,
    min_iou: float = 0.30,
    max_predictions: int = 5,
) -> dict:
    """Greedy Matching nach höchster IoU, ohne doppelte Trefferwertung."""
    if not 0 < min_iou <= 1:
        raise EvaluationError("min_iou muss > 0 und <= 1 sein.")
    if not 1 <= max_predictions <= 100:
        raise EvaluationError("max_predictions muss 1 bis 100 sein.")
    if not isinstance(reference_highlights, list) or not reference_highlights:
        raise EvaluationError("Mindestens ein menschlich markiertes Highlight erforderlich.")
    if not isinstance(predictions, list):
        raise EvaluationError("Vorhersagen müssen eine Liste sein.")
    for item in reference_highlights:
        _interval(item)
    for item in predictions:
        _interval(item)

    selected = predictions[:max_predictions]
    pairs = [
        (temporal_iou(pred, truth), pred_index, reference_index)
        for pred_index, pred in enumerate(selected)
        for reference_index, truth in enumerate(reference_highlights)
    ]
    pairs.sort(reverse=True)
    used_predictions: set[int] = set()
    used_references: set[int] = set()
    matches = []
    for iou, pred_index, reference_index in pairs:
        if iou < min_iou:
            break
        if pred_index in used_predictions or reference_index in used_references:
            continue
        used_predictions.add(pred_index)
        used_references.add(reference_index)
        matches.append({
            "prediction_index": pred_index,
            "reference_index": reference_index,
            "iou": round(iou, 4),
        })

    hits = len(matches)
    precision = hits / len(selected) if selected else 0.0
    recall = hits / len(reference_highlights)
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    return {
        "reference_count": len(reference_highlights),
        "prediction_count": len(selected),
        "matched_count": hits,
        "precision_at_k": round(precision, 4),
        "recall_at_k": round(recall, 4),
        "f1_at_k": round(f1, 4),
        "mean_matched_iou": round(
            sum(match["iou"] for match in matches) / hits, 4
        ) if hits else 0.0,
        "min_iou": min_iou,
        "max_predictions": max_predictions,
        "matches": matches,
        "missed_reference_indices": [
            index for index in range(len(reference_highlights))
            if index not in used_references
        ],
        "note": (
            "Zeitliche Überdeckung auf menschlichen Referenzfenstern. "
            "Beweist weder sichere Ereigniserkennung noch die Qualität eines "
            "fertig geschnittenen Reels. Ergebnisse nur mit demselben "
            "Testdatensatz und derselben IoU-Schwelle vergleichen."
        ),
    }


def load_and_compare(
    annotations: dict, analysis: dict, *, stage: str = "refined",
    min_iou: float = 0.3, max_predictions: int = 5,
) -> dict:
    if not isinstance(annotations, dict) or not isinstance(analysis, dict):
        raise EvaluationError("Ein JSON-Objekt pro Eingabedatei erforderlich.")
    ground_truth = annotations.get("reference_highlights")
    if stage == "refined":
        refined = analysis.get("refinement")
        if not isinstance(refined, dict):
            raise EvaluationError("Keine Detailanalyse vorhanden. --refine beim Prototyp aktivieren.")
        predictions = refined.get("suggestions")
    elif stage == "coarse":
        predictions = analysis.get("recommendations")
    else:
        raise EvaluationError("Stufe muss refined oder coarse sein.")
    report = compare_predictions(
        ground_truth, predictions, min_iou=min_iou,
        max_predictions=max_predictions,
    )
    report["stage"] = stage
    report["goal_name"] = annotations.get("goal_name", "")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="VeloCut: Highlight-Treffer objektiv vergleichen")
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--stage", choices=["refined", "coarse"], default="refined")
    parser.add_argument("--min-iou", type=float, default=0.30)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    annotations = json.loads(args.annotations.read_text(encoding="utf-8"))
    analysis = json.loads(args.results.read_text(encoding="utf-8"))
    report = load_and_compare(
        annotations, analysis, stage=args.stage,
        min_iou=args.min_iou, max_predictions=args.top_k,
    )
    formatted = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(formatted + "\n", encoding="utf-8")
        print(f"Auswertung geschrieben: {args.output}")
    else:
        print(formatted)


if __name__ == "__main__":
    main()
