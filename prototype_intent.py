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
from typing import Callable

from adaptive_refinement import refine_for_goal
from batch_frames import extract_frame_cache, select_cached_frames
from candidate_windows import generate_candidate_windows
from content_understanding import observe_window
from highlight_models import CONTENT_NICHES
from intent_ranking import rank_for_goal
from user_goals import understand_user_goal
from video_probe import probe_video
from frame_sampler import FrameSampleError
from visual_diversity import VisualDiversityError, fingerprint_window


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
    refine: bool = False,
    progress: Callable[[str], None] | None = None,
) -> dict:
    """Führt alle Prototyp-Schritte mit strikten Kosten-/Dauerlimits aus."""
    def stage(label: str) -> None:
        if progress is not None:
            progress(label)

    stage("Technische Video-Prüfung")
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

    stage("Videobilder extrahieren")
    # Ein FFmpeg-Durchlauf pro Video statt erneuter Extraktion für jedes
    # grobe und detaillierte Zeitfenster. Maximal 60 s x 2 FPS = ca. 120 Frames.
    caches = {
        item.source_id: extract_frame_cache(
            item.path, source_id=item.source_id,
            duration_seconds=item.duration_seconds,
        )
        for item in metadata
    }

    # Nutzerwunsch unabhängig vom Videoinhalt interpretieren, anschließend
    # visuell prüfen. Kein Wunsch darf einen Bildbeleg ersetzen.
    stage("Nutzerwunsch verstehen")
    goal = understand_user_goal(client, instruction, model=model)
    stage("Grobe Bildanalyse")
    observations = [
        observe_window(
            client, item, window, model=model,
            frames=select_cached_frames(caches[item.source_id], window, frame_count=3),
        )
        for item, window in windows
    ]
    fingerprints = {}
    for obs in observations:
        try:
            fingerprints[obs.window] = fingerprint_window(
                caches[obs.window.source_id], obs.window
            )
        except (VisualDiversityError, FrameSampleError):
            # Bildvergleich unbekannt: keine zwei unbewiesenen Bilder gleichsetzen.
            continue
    result = rank_for_goal(
        observations, goal,
        category_override=category_override,
        max_results=max_results,
        scene_fingerprints=fingerprints if fingerprints else None,
    )
    if refine:
        stage("Detaillierte Bildanalyse")
    refinement = (
        refine_for_goal(
            client, {item.source_id: item for item in metadata},
            observations, goal,
            category_override=category_override,
            model=model,
            max_results=max_results,
            frame_caches=caches,
        )
        if refine else None
    )
    stage("Analysebericht erstellen")
    def observation_record(obs):
        return {
            "source_id": obs.window.source_id,
            "start_seconds": obs.window.start_seconds,
            "end_seconds": obs.window.end_seconds,
            "categories": list(obs.categories),
            "visual_tags": list(obs.visual_tags),
            "prominence": dict(obs.prominence),
            "summary": obs.summary,
            "evidence": obs.evidence,
            "impact": obs.impact,
            "technical_quality": obs.technical_quality,
        }

    output = {
        "mode": "cached_static_frame_visual_observations_no_audio",
        "video_count": len(metadata),
        "analyzed_windows": len(windows),
        "extracted_frame_counts": {
            source_id: len(cache.frames) for source_id, cache in caches.items()
        },
        "goal": asdict(goal),
        "detected_categories": list(result.detected_categories),
        "category_override": category_override,
        "notice": result.notice,
        "repeated_views_suppressed": result.repeated_views_suppressed,
        # Diagnosedaten: alle tatsächlich gesehenen Szenen, auch verworfene.
        # Damit lässt sich die Filterentscheidung ohne weitere API-Kosten prüfen.
        "observed_windows": [
            observation_record(obs) for obs in observations
        ],
        "recommendations": [
            {
                "source_id": ranked.observation.window.source_id,
                "start_seconds": ranked.observation.window.start_seconds,
                "end_seconds": ranked.observation.window.end_seconds,
                "categories": list(ranked.observation.categories),
                "visual_tags": list(ranked.observation.visual_tags),
                "prominence": dict(ranked.observation.prominence),
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
    if refinement is not None:
        output["refinement"] = {
            "level": "denser_static_frame_windows",
            "inspected_windows": refinement.inspected_windows,
            "selected_coarse_windows": refinement.selected_coarse_windows,
            "inspected_all_coarse_windows": refinement.inspected_all_coarse_windows,
            "observed_windows": [
                observation_record(obs) for obs in refinement.observed_windows
            ],
            "notice": refinement.notice,
            "repeated_views_suppressed": refinement.repeated_views_suppressed,
            "suggestions": [
                {
                    "source_id": scene.observation.window.source_id,
                    "start_seconds": scene.observation.window.start_seconds,
                    "end_seconds": scene.observation.window.end_seconds,
                    "summary": scene.observation.summary,
                    "reason": scene.explanation,
                    "visual_tags": list(scene.observation.visual_tags),
                    "prominence": dict(scene.observation.prominence),
                    "score": scene.score,
                }
                for scene in refinement.scenes
            ],
            "warning": (
                "Auch die engeren Zeitfenster sind keine exakten Schnittgrenzen. "
                "Kurze Ereignisse können zwischen gesampelten Standbildern liegen."
            ),
        }
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="VeloCut 2.0 – automatische Video-Einordnung")
    parser.add_argument("videos", type=Path, nargs="+", help="1 bis 3 Videos, je bis zu 60s")
    parser.add_argument("--instruction", default="", help="Freier Wunsch, z. B. 'Zeig die Kurven'")
    parser.add_argument(
        "--category", choices=["auto", *sorted(CONTENT_NICHES)],
        default="auto", help="Auto-Erkennung oder bewusste Kategorie-Vorgabe",
    )
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--refine", action="store_true", help="Detailanalyse für ausgewählte grobe Zeitfenster")
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
        refine=args.refine,
    )
    serialized = json.dumps(output, indent=2, ensure_ascii=False)
    if args.output is None:
        print(serialized)
    else:
        args.output.write_text(serialized + "\n", encoding="utf-8")
        print(f"Ergebnis gespeichert: {args.output}")


if __name__ == "__main__":
    main()
