"""Nutzerzielabhängige, nachvollziehbare Vorauswahl von Video-Zeitfenstern.

Keine exakten finalen Schnitte. Unbelegte Wünsche erzeugen KEINEN Ersatzclip.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from content_understanding import SceneObservation, detected_categories
from highlight_models import CONTENT_NICHES
from user_goals import EditingGoal


STYLE_TAGS = {
    "action": frozenset({"cornering", "overtaking", "wheelie", "sports", "exercise"}),
    "scenic": frozenset({"scenery", "mountains", "forest", "water", "sunset", "city"}),
    "emotional": frozenset({"reaction", "gesture", "people", "sunset"}),
    "informative": frozenset({"product", "gesture", "food"}),
    "balanced": frozenset(),
}


@dataclass(frozen=True)
class RankedScene:
    observation: SceneObservation
    score: float
    matched_tags: tuple[str, ...]
    explanation: str


@dataclass(frozen=True)
class RankingResult:
    ranked_scenes: tuple[RankedScene, ...]
    detected_categories: tuple[str, ...]
    notice: str | None = None


def _overlaps(left: SceneObservation, right: SceneObservation) -> bool:
    a, b = left.window, right.window
    return (
        a.source_id == b.source_id
        and a.start_seconds < b.end_seconds
        and b.start_seconds < a.end_seconds
    )


def rank_for_goal(
    observations: Sequence[SceneObservation],
    goal: EditingGoal,
    *,
    category_override: str | None = None,
    max_results: int = 5,
) -> RankingResult:
    """Priorisiert echte Beobachtungen, vermeidet überlappende Zeitfenster."""
    if category_override is not None and category_override not in CONTENT_NICHES:
        raise ValueError("Nicht unterstützte Nutzer-Kategorie.")
    if max_results < 1:
        raise ValueError("max_results muss >= 1 sein.")

    categories = detected_categories(observations)
    uncertainty_notice = (
        "Ein Teil des Nutzerwunsches kann anhand einzelner Bilder nicht "
        "sicher geprüft werden: " + ", ".join(goal.uncheckable_requests)
        if goal.uncheckable_requests else None
    )
    # Nicht jede schwierige Formulierung darf das gesamte Ergebnis blockieren.
    # Falls kein überprüfbares Motiv übrig bleibt, jedoch keine scheinbar
    # passende allgemeine Szene als Treffer ausgeben.
    if goal.uncheckable_requests and not (goal.focus_tags or goal.required_tags):
        return RankingResult(
            (), categories,
            uncertainty_notice + ". Keine überprüfbaren Bildmotive aus "
            "dieser Anweisung abgeleitet.",
        )
    observed_tags = set().union(*(set(obs.visual_tags) for obs in observations))
    missing = set(goal.required_tags) - observed_tags
    if missing:
        return RankingResult(
            (), categories,
            "Ausdrücklich gewünschte Ereignisse/Motive in den Stichproben "
            "nicht nachgewiesen: " + ", ".join(sorted(missing))
            + (". " + uncertainty_notice if uncertainty_notice else ""),
        )

    candidates: list[RankedScene] = []
    for obs in observations:
        if category_override and category_override not in obs.categories:
            continue
        tags = set(obs.visual_tags)
        if tags.intersection(goal.excluded_tags):
            continue
        if not set(goal.required_tags).issubset(tags):
            continue
        matched = tuple(sorted(tags.intersection(goal.focus_tags)))
        # Wenn ein Fokus vorgegeben ist, werden fehlende Treffer nicht
        # als Treffer ausgegeben – auch bei hoher generischer Qualität nicht.
        if goal.focus_tags and not matched and not goal.required_tags:
            continue
        match_fraction = len(matched) / max(1, len(goal.focus_tags))
        style_match = bool(tags.intersection(STYLE_TAGS[goal.style]))
        quality = 0.65 * obs.impact + 0.35 * obs.technical_quality
        score = 20 * quality + 25 * match_fraction + (10 if style_match else 0)
        if goal.focus_tags:
            score = min(100.0, score * 0.75)  # Kein blindes Überbewerten.
        score = round(min(100.0, score), 2)
        explanation = (
            f"Bildbeleg: {obs.evidence}. "
            + (
                "Passende Merkmale: " + ", ".join(matched)
                if matched
                else "Allgemeine visuelle Qualität"
            )
        )
        candidates.append(RankedScene(obs, score, matched, explanation))

    candidates.sort(
        key=lambda item: (
            -item.score,
            item.observation.window.source_id,
            item.observation.window.start_seconds,
        )
    )
    chosen: list[RankedScene] = []
    for item in candidates:
        if any(_overlaps(item.observation, other.observation) for other in chosen):
            continue
        chosen.append(item)
        if len(chosen) >= max_results:
            break
    if chosen:
        return RankingResult(tuple(chosen), categories, uncertainty_notice)

    message = (
        "Keine ausreichend passend belegten Szenen gefunden. "
        "Nutzerwunsch ändern, andere Bilder untersuchen oder eine genauere "
        "Analyse durchführen; keine Ersatz-Highlights erfunden."
    )
    if uncertainty_notice:
        message += " " + uncertainty_notice
    return RankingResult((), categories, message)
