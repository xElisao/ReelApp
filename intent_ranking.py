"""Nutzerzielabhängige, nachvollziehbare Vorauswahl von Video-Zeitfenstern.

Keine exakten finalen Schnitte. Unbelegte Wünsche erzeugen KEINEN Ersatzclip.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from content_understanding import SceneObservation, detected_categories
from highlight_models import CONTENT_NICHES
from user_goals import EditingGoal
from candidate_windows import CandidateWindow
from visual_diversity import ShotFingerprint, likely_same_camera_view


STYLE_TAGS = {
    "action": frozenset({"cornering", "overtaking", "wheelie", "sports", "exercise"}),
    "scenic": frozenset({"scenery", "mountains", "forest", "water", "sunset", "city"}),
    "emotional": frozenset({"reaction", "gesture", "people", "sunset"}),
    "informative": frozenset({"product", "gesture", "food"}),
    "balanced": frozenset(),
}

# Gültige sichtbare Landschaftsmerkmale. 'scenery' kann durch Berge,
# Wälder, Wasser etc. belegt sein; 'mountains' bleibt ein eigener Fokus.
FOCUS_EVIDENCE = {
    "scenery": frozenset({"scenery", "mountains", "forest", "water", "sunset", "city"}),
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
    repeated_views_suppressed: int = 0


def _prominence_for_focus(obs: SceneObservation, tag: str) -> float | None:
    """Get a visual-focus estimate, including derived scenery markers."""
    candidates = FOCUS_EVIDENCE.get(tag, frozenset({tag}))
    known = [obs.prominence_for(candidate) for candidate in candidates]
    available = [value for value in known if value is not None]
    return max(available) if available else None


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
    scene_fingerprints: Mapping[CandidateWindow, ShotFingerprint] | None = None,
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
        matched = tuple(sorted(
            tag for tag in goal.focus_tags
            if tags.intersection(FOCUS_EVIDENCE.get(tag, frozenset({tag})))
        ))
        # Wenn ein Fokus vorgegeben ist, werden fehlende Treffer nicht
        # als Treffer ausgegeben – auch bei hoher generischer Qualität nicht.
        if goal.focus_tags and not matched and not goal.required_tags:
            continue
        match_fraction = len(matched) / max(1, len(goal.focus_tags))
        style_match = bool(tags.intersection(STYLE_TAGS[goal.style]))
        quality = 0.65 * obs.impact + 0.35 * obs.technical_quality
        score = 20 * quality + 25 * match_fraction + (10 if style_match else 0)
        # Sichtbare Motive sind nicht zwangsläufig der Bildmittelpunkt.
        # Nur vorhandene Dominanz-Schätzungen beeinflussen die Feinbewertung.
        focus_values = [
            _prominence_for_focus(obs, tag) for tag in matched
        ]
        known_focus = [value for value in focus_values if value is not None]
        if known_focus:
            score += 14 * (sum(known_focus) / len(known_focus)) / 5
        secondary = tuple(sorted(tags.intersection(goal.deemphasized_tags)))
        secondary_details = []
        for tag in secondary:
            p = obs.prominence_for(tag)
            if p is None:
                # Bis das Modell Dominanzwerte liefert, neutraler Fallback.
                score -= 9
                secondary_details.append(f"{tag} (Dominanz unbekannt)")
            else:
                # Bei 5/5: merkliche Abwertung; bei 0/5 nur kleine Abwertung.
                score -= 4 + 20 * (p / 5)
                secondary_details.append(f"{tag} (Bilddominanz ca. {p:g}/5)")
        if goal.focus_tags:
            score *= 0.75  # Vorläufige Gewichtung, kein Qualitätsversprechen.
        score = round(max(0.0, min(100.0, score)), 2)
        explanation = (
            f"Bildbeleg: {obs.evidence}. "
            + (
                "Passende Merkmale: " + ", ".join(matched)
                if matched
                else "Allgemeine visuelle Qualität"
            )
            + (
                ". Nebenmotiv (geringer gewichtet): " + ", ".join(secondary_details)
                if secondary_details else ""
            )
            + (
                ". Geschätzte Bilddominanz des Hauptmotivs: "
                + f"{sum(known_focus)/len(known_focus):.1f}/5"
                if known_focus else ""
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
    suppressed = 0
    for item in candidates:
        if any(_overlaps(item.observation, other.observation) for other in chosen):
            continue
        # Eine Landschaft aus derselben Kameraperspektive nicht mehrfach
        # präsentieren; Action-Ereignisse dagegen dürfen sich wiederholen.
        if goal.style == "scenic" and scene_fingerprints is not None:
            current = scene_fingerprints.get(item.observation.window, ())
            if current and any(
                item.observation.window.source_id == other.observation.window.source_id
                and likely_same_camera_view(
                    current, scene_fingerprints.get(other.observation.window, ())
                )
                for other in chosen
            ):
                suppressed += 1
                continue
        chosen.append(item)
        if len(chosen) >= max_results:
            break
    if chosen:
        notices = [uncertainty_notice] if uncertainty_notice else []
        if suppressed:
            notices.append(
                f"{suppressed} weitere Zeitfenster wegen wahrscheinlich gleicher "
                "Kameraansicht zurückgestellt; für Landschaften werden "
                "unterschiedliche Ansichten bevorzugt."
            )
        observed_focus = {
            tag for item in chosen for tag in item.matched_tags
        }
        absent_focus = set(goal.focus_tags) - observed_focus
        if absent_focus:
            notices.append(
                "Ein Teil der gewünschten Bildmotive wurde in diesen "
                "Vorschlägen nicht belegt: " + ", ".join(sorted(absent_focus)) + "."
            )
        return RankingResult(
            tuple(chosen), categories, " ".join(notices) if notices else None,
            repeated_views_suppressed=suppressed,
        )

    message = (
        "Keine ausreichend passend belegten Szenen gefunden. "
        "Nutzerwunsch ändern, andere Bilder untersuchen oder eine genauere "
        "Analyse durchführen; keine Ersatz-Highlights erfunden."
    )
    if uncertainty_notice:
        message += " " + uncertainty_notice
    return RankingResult((), categories, message)
