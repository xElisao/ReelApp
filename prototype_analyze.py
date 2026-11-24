"""Manueller Kommandozeilen-Test von VeloCut 2.0 (keine Stripe-/UI-Änderung).

Beispiel:
  export OPENAI_API_KEY='...'
  python prototype_analyze.py video.mp4 --niche travel_outdoor

Bitte Videos nur mit den nötigen Rechten an einen externen KI-Dienst senden.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

from highlight_analyzer import analyze_video
from highlight_models import CONTENT_NICHES
from video_probe import probe_video


def main() -> None:
    parser = argparse.ArgumentParser(description="VeloCut 2.0 – visuelle Highlight-Vorschläge")
    parser.add_argument("video", type=Path, help="Pfad zu einem Testvideo (max. 60s)")
    parser.add_argument("--niche", choices=sorted(CONTENT_NICHES), default="general")
    parser.add_argument("--instruction", default="", help="Optionaler Schnittwunsch")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--output", type=Path, help="Optionaler Pfad für JSON-Ergebnis")
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        parser.error("OPENAI_API_KEY ist nicht gesetzt")
    from openai import OpenAI

    metadata = probe_video(args.video, source_id="video-1")
    candidates = analyze_video(
        OpenAI(), metadata, niche=args.niche,
        user_instruction=args.instruction, model=args.model,
    )
    result = {
        "mode": "sampled_static_frames_no_audio",
        "video_duration_seconds": metadata.duration_seconds,
        "niche": args.niche,
        "candidates_best_first": [
            {**asdict(c), "total_score": c.scores.total_out_of_100}
            for c in candidates
        ],
        "warning": "Vorschläge, noch keine finalen Schnittzeitpunkte.",
    }
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")
        print(f"Ergebnis gespeichert: {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
