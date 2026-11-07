"""Zweistufige visuelle Analyse: interessante 8-s-Fenster genauer untersuchen.

Stufe 1 liefert grobe Beobachtungen. Hier werden höchstens zwei grobe Fenster
in 3-s-Abschnitte mit 1.5-s-Schritten aufgelöst. Es werden *echte* zusätzliche
Videobilder angefordert. Kein Audio, kein Bewegungsmodell, keine Punkt-genauen
Schnittgrenzen und keine Garantie, alle kurzen Ereignisse zu sehen.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

from candidate_windows import CandidateWindow
from content_understanding import SceneObservation, observe_window
from intent_ranking import RankedScene, rank_for_goal
from user_goals import EditingGoal
from video_probe import VideoMetadata


@dataclass(frozen=True)
class RefinedResult:
    scenes: tuple[RankedScene, ...]
    inspected_windows: int
    selected_coarse_windows: int
    inspected_all_coarse_windows: bool
    notice: str | None


def fine_windows(
    coarse: CandidateWindow,
    *,
    window_seconds: float = 3.0,
    stride_seconds: float = 1.5,
) -> list[CandidateWindow]:
    """Erzeugt lückenlose kleinere Fenster INNERHALB eines groben Fensters."""
    if (
        not isinstance(coarse.source_id, str) or not coarse.source_id.strip()
        or not math.isfinite(coarse.start_seconds)
        or not math.isfinite(coarse.end_seconds)
        or coarse.start_seconds < 0
        or coarse.end_seconds <= coarse.start_seconds
    ):
        raise ValueError("Ungültiges grobes Zeitfenster.")
    if not (
        math.isfinite(window_seconds) and window_seconds > 0
        and math.isfinite(stride_seconds) and 0 < stride_seconds <= window_seconds
    ):
        raise ValueError("Ungültige Größe oder Schrittweite.")

    width = min(window_seconds, coarse.duration_seconds)
    final_start = coarse.end_seconds - width
    starts = []
    pos = coarse.start_seconds
    while pos < final_start - 1e-7:
        starts.append(pos)
        pos += stride_seconds
    if not starts or abs(starts[-1] - final_start) > 1e-7:
        starts.append(final_start)
    return [
        CandidateWindow(coarse.source_id, round(start, 6), round(start + width, 6))
        for start in starts
    ]


def refine_for_goal(
    client: object,
    source_metadata: Mapping[str, VideoMetadata],
    coarse_observations: Sequence[SceneObservation],
    goal: EditingGoal,
    *,
    category_override: str | None = None,
    model: str = "gpt-4o-mini",
    max_coarse_windows: int = 2,
    max_fine_windows: int = 12,
    max_results: int = 5,
) -> RefinedResult:
    """Analysiert möglichst passende grobe Fenster in höherer zeitlicher Auflösung.

    Wird im Grobscan kein Nutzer-Fokus entdeckt, werden ersatzweise grobe Fenster
    nach sichtbarer Relevanz/Qualität ausgewählt, um Kurzereignisse nicht sofort
    als abwesend zu behandeln. Ist das Suchbudget erschöpft, wird transparent
    kommuniziert, dass nur ein Teil des Videos dichter untersucht wurde.
    """
    if not 1 <= max_coarse_windows <= 4:
        raise ValueError("max_coarse_windows muss zwischen 1 und 4 liegen.")
    if not 1 <= max_fine_windows <= 24:
        raise ValueError("max_fine_windows muss zwischen 1 und 24 liegen.")
    if not 1 <= max_results <= 10:
        raise ValueError("max_results muss zwischen 1 und 10 liegen.")
    if not coarse_observations:
        return RefinedResult((), 0, 0, True, "Keine groben Szenen vorhanden.")

    for scene in coarse_observations:
        source = source_metadata.get(scene.window.source_id)
        if source is None:
            raise ValueError("Grobe Szene ohne Video-Metadaten.")
        if not 0 <= scene.window.start_seconds < scene.window.end_seconds <= source.duration_seconds:
            raise ValueError("Grobe Szene außerhalb des Videos.")

    coarse_ranking = rank_for_goal(
        coarse_observations, goal, category_override=category_override,
        max_results=max_coarse_windows,
    )
    selected = [item.observation for item in coarse_ranking.ranked_scenes]

    # Bei Null-Treffern wegen striktem Wunsch: nicht behaupten, das Ereignis
    # existiere nicht. Weitere grobe Beobachtungen (auch mit anderer erkannter
    # Kategorie) können an wenigen Frames vorbeigegangen sein.
    if len(selected) < max_coarse_windows:
        remaining = sorted(
            coarse_observations,
            key=lambda obs: (
                -(0.65 * obs.impact + 0.35 * obs.technical_quality),
                obs.window.source_id, obs.window.start_seconds,
            ),
        )
        for item in remaining:
            if item not in selected:
                selected.append(item)
            if len(selected) == max_coarse_windows:
                break

    selected = selected[:max_coarse_windows]
    expanded: list[CandidateWindow] = []
    seen: set[tuple[str, float, float]] = set()
    for observation in selected:
        for window in fine_windows(observation.window):
            key = (window.source_id, window.start_seconds, window.end_seconds)
            if key not in seen:
                seen.add(key)
                expanded.append(window)

    # Don't silently skip windows if configured budget is too small.
    if len(expanded) > max_fine_windows:
        raise ValueError(
            f"{len(expanded)} Detailfenster benötigt, "
            f"Budget erlaubt nur {max_fine_windows}; "
            "bitte grobe Fensterzahl oder Budget anpassen."
        )

    fine_observations = [
        observe_window(
            client, source_metadata[window.source_id], window,
            model=model,
        )
        for window in expanded
    ]
    ranked = rank_for_goal(
        fine_observations, goal, category_override=category_override,
        max_results=max_results,
    )
    complete = len(selected) == len(coarse_observations)
    notice = ranked.notice
    if not complete:
        scope = (
            f"Detailanalyse beschränkt auf {len(selected)} von "
            f"{len(coarse_observations)} groben Zeitfenstern. "
            "Nicht gefundene Ereignisse können in nicht geprüften Fenstern liegen."
        )
        notice = f"{notice} {scope}" if notice else scope
    elif not ranked.ranked_scenes:
        notice = (
            f"{notice or 'Keine Treffer.'} Auch in den Detail-Stichproben "
            "ist eine Abwesenheit nicht sicher nachgewiesen."
        )
    return RefinedResult(
        scenes=ranked.ranked_scenes,
        inspected_windows=len(expanded),
        selected_coarse_windows=len(selected),
        inspected_all_coarse_windows=complete,
        notice=notice,
    )
