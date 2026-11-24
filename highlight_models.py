"""Validierbare Highlight-Kandidaten und Schnittpläne für VeloCut 2.0.

Die Qualität eines Kandidaten wird später durch Videoanalyse ermittelt.
Dieses Modul verhindert ungültige/erfundene Schnittzeitstempel; es erkennt
selbst keine Highlights.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields
from typing import Mapping, Sequence


CONTENT_NICHES = frozenset({
    "motorcycle_action",
    "fitness",
    "travel_outdoor",
    "general",
})

# Vorläufige Startgewichte, mit manuell annotierten Videos zu evaluieren.
SCORE_WEIGHTS = {
    "relevance": 0.35,
    "impact": 0.35,
    "technical_quality": 0.20,
    "variety": 0.10,
}


def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


@dataclass(frozen=True)
class HighlightScores:
    relevance: float
    impact: float
    technical_quality: float
    variety: float

    def __post_init__(self) -> None:
        for item in fields(self):
            value = getattr(self, item.name)
            if not _finite_number(value) or not 0 <= value <= 5:
                raise ValueError(f"{item.name} muss zwischen 0 und 5 liegen.")

    @property
    def total_out_of_100(self) -> float:
        """Gewichteter Entwicklungswert; kein kalibrierter KI-Sicherheitswert."""
        return round(
            sum(getattr(self, key) * weight for key, weight in SCORE_WEIGHTS.items()) * 20,
            2,
        )


@dataclass(frozen=True)
class HighlightCandidate:
    source_id: str
    start_seconds: float
    end_seconds: float
    category: str
    summary: str
    reason: str
    scores: HighlightScores
    confidence: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ValueError("source_id darf nicht leer sein.")
        if self.category not in CONTENT_NICHES:
            raise ValueError(f"Unbekannte Content-Nische: {self.category!r}")
        if not isinstance(self.summary, str) or not self.summary.strip():
            raise ValueError("summary darf nicht leer sein.")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason darf nicht leer sein.")
        if not isinstance(self.scores, HighlightScores):
            raise TypeError("scores muss ein HighlightScores-Objekt sein.")
        if not (_finite_number(self.start_seconds) and _finite_number(self.end_seconds)):
            raise ValueError("Zeitstempel müssen endliche Zahlen sein.")
        if self.start_seconds < 0 or self.end_seconds <= self.start_seconds:
            raise ValueError("Zeitfenster muss bei >= 0 beginnen und eine positive Dauer haben.")
        if self.confidence is not None and (
            not _finite_number(self.confidence) or not 0 <= self.confidence <= 1
        ):
            raise ValueError("confidence muss zwischen 0 und 1 liegen.")

    @property
    def duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds


def validate_candidate(
    candidate: HighlightCandidate,
    source_durations: Mapping[str, float],
) -> None:
    """Prüft, ob der Highlight-Zeitraum tatsächlich im Quellvideo liegt."""
    if candidate.source_id not in source_durations:
        raise ValueError(f"Unbekannte Quellvideo-ID: {candidate.source_id!r}")
    duration = source_durations[candidate.source_id]
    if not _finite_number(duration) or duration <= 0:
        raise ValueError("Quellvideo-Dauer ist ungültig.")
    if candidate.end_seconds > duration:
        raise ValueError(
            f"Highlight endet bei {candidate.end_seconds}s, Video bei {duration}s."
        )


def validate_cut_plan(
    candidates: Sequence[HighlightCandidate],
    source_durations: Mapping[str, float],
    *,
    target_duration_seconds: float,
) -> None:
    """Prüft ein Schnittplan-Budget und Überlappungen innerhalb derselben Quelle.

    Die Ziellänge ist eine Obergrenze, keine Vorgabe zum Erfinden zusätzlicher Szenen.
    """
    if not _finite_number(target_duration_seconds) or target_duration_seconds <= 0:
        raise ValueError("target_duration_seconds muss eine positive Zahl sein.")
    if not candidates:
        raise ValueError("Schnittplan ist leer.")

    total = 0.0
    by_source: dict[str, list[HighlightCandidate]] = {}
    for candidate in candidates:
        validate_candidate(candidate, source_durations)
        total += candidate.duration_seconds
        by_source.setdefault(candidate.source_id, []).append(candidate)

    if total > target_duration_seconds + 1e-6:
        raise ValueError(
            f"Schnittplan ist {total:.2f}s lang, Zielmaximum {target_duration_seconds:.2f}s."
        )

    for source_id, items in by_source.items():
        ordered = sorted(items, key=lambda c: c.start_seconds)
        for previous, current in zip(ordered, ordered[1:]):
            if current.start_seconds < previous.end_seconds:
                raise ValueError(f"Überlappende Ausschnitte in Video {source_id!r}.")
