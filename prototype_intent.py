"""Visuelle VeloCut-2.0-Pipeline als CLI – ohne Änderung an Streamlit/Stripe.

Beispiel:
  python prototype_intent.py motorrad.mp4 --instruction "Zeig die besten Kurven"
  python prototype_intent.py a.mp4 b.mp4 --instruction "Schöne Landschaften"

Die Dateien verlassen diesen Rechner nur insofern, als verkleinerte
Standbilder zur Analyse an den OpenAI-Dienst übertragen werden.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

from candidate_windows import generate_candidate_windows
from content_understanding import observe_window
from highlight_models import CONTENT_NICHES
from intent_ranking import rank_for_goal
from user_goals import understand_user_goal
from video_probe import probe_video


MAX_VIDEOS = 3
MAX_VIDEO_SECONDS = 60
MAX_TOTAL_WINDOWS = 24


def analyze_files(
    client: object,
    video_paths: list[Path],
    *,
    instruction: str,
    category_override: str | None = None,
    model: str = "gpt-4o-mini",
    max_results: int = 5,
) -> dict:
    """Führt alle Prototyp-Schritte mit strikten Kosten-/Dauerlimits aus."""
    if not 1 <= len(video_paths) <= MAX_VIDEOS:
        raise ValueError(f"Bitte 1 bis {MAX_VIDEOS} Videos wählen.")
    if category_override is not None and category_override not in CONTENT_NICHES:
        raise ValueError("Unbekannte Nutzer-Kategorie.")
    if not 1 <= max_results <= 10:
        raise ValueError("max_results muss zwischen 1 und 10 liegen.")

    metadata = [
        probe_video(path, source_id=f"video-{index + 1}")
        for index, path in enumerate(video_paths)
    ]
    if any(item.duration_seconds > MAX_VIDEO_SECONDS for item in metadata):
        raise ValueError(f"Prototyp-Limit: maximal {MAX_VIDEO_SECONDS}s je Video.")

    windows = [
        (item, window)
        for item in metadata
        for window in generate_candidate_windows(
            item.source_id, item.duration_seconds,
            window_seconds=8, stride_seconds=6, max_windows=12,
        )
    ]
    if len(windows) > MAX_TOTAL_WINDOWS:
        raise ValueError("Zu viele Zeitfenster für den Prototyp. Videos kürzen.")

    # Nutzerwunsch unabhängig vom Videoinhalt interpretieren, anschließend
    # visuell prüfen. Kein Wunsch darf einen Bildbeleg ersetzen.
    goal = understand_user_goal(client, instruction, model=model)
    observations = [
        observe_window(client, item, window, model=model)
        for item, window in windows
    ]
    result = rank_for_goal(
        observations, goal,
        category_override=category_override,
        max_results=max_results,
    )
    return {
        "mode": "static_frame_visual_observations_no_audio",
        "video_count": len(metadata),
        "analyzed_windows": len(windows),
        "goal": asdict(goal),
        "detected_categories": list(result.detected_categories),
        "category_override": category_override,
        "notice": result.notice,
        "recommendations": [
            {
                "source_id": ranked.observation.window.source_id,
                "start_seconds": ranked.observation.window.start_seconds,
                "end_seconds": ranked.observation.window.end_seconds,
                "categories": list(ranked.observation.categories),
                "visual_tags": list(ranked.observation.visual_tags),
                "summary": ranked.observation.summary,
                "reason": ranked.explanation,
                "score": ranked.score,
                "matched_goal_tags": list(ranked.matched_tags),
            }
            for ranked in result.ranked_scenes
        ],
        "warning": (
            "Dies sind grobe Zeitfenster, keine exakten Highlight-Grenzen. "
            "Nur extrahierte Standbilder werden analysiert, kein Ton und "
            "keine Bewegungen zwischen Einzelbildern. "
            "Bei fehlenden Treffern kann dichteres Sampling helfen."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="VeloCut 2.0 – automatische Video-Einordnung")
    parser.add_argument("videos", type=Path, nargs="+", help="1 bis 3 Videos, je bis zu 60s")
    parser.add_argument("--instruction", default="", help="Freier Wunsch, z. B. 'Zeig die Kurven'")
    parser.add_argument(
        "--category", choices=["auto", *sorted(CONTENT_NICHES)],
        default="auto", help="Auto-Erkennung oder bewusste Kategorie-Vorgabe",
    )
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--output", type=Path, help="Optional JSON-Ergebnis speichern")
    args = parser.parse_args()
    if not os.environ.get("OPENAI_API_KEY"):
        parser.error("OPENAI_API_KEY fehlt in der lokalen Umgebung.")
    from openai import OpenAI

    output = analyze_files(
        OpenAI(), args.videos,
        instruction=args.instruction,
        category_override=None if args.category == "auto" else args.category,
        model=args.model,
    )
    serialized = json.dumps(output, indent=2, ensure_ascii=False)
    if args.output is None:
        print(serialized)
    else:
        args.output.write_text(serialized + "\n", encoding="utf-8")
        print(f"Ergebnis gespeichert: {args.output}")


if __name__ == "__main__":
    main()
