"""Deterministische, überlappende Zeitfenster für die erste Videoanalyse.

Noch KEINE Erkennung tatsächlicher Szenenwechsel. Mit überlappenden
Zeitfenstern durchsuchen wir auch lange, ungeschnittene Einstellungen.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateWindow:
    source_id: str
    start_seconds: float
    end_seconds: float

    @property
    def duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds


def generate_candidate_windows(
    source_id: str,
    duration_seconds: float,
    *,
    window_seconds: float = 8.0,
    stride_seconds: float = 6.0,
    max_windows: int = 20,
) -> list[CandidateWindow]:
    """Deckt die komplette Videolänge mit begrenzten Fenstern ab.

    Bei zu vielen Fenstern wird bewusst ein Fehler ausgelöst, statt
    den Rest des Videos kommentarlos zu ignorieren.
    """
    if not source_id or not source_id.strip():
        raise ValueError("source_id fehlt")
    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise ValueError("duration_seconds muss positiv und endlich sein")
    if not math.isfinite(window_seconds) or window_seconds <= 0:
        raise ValueError("window_seconds muss positiv und endlich sein")
    if not math.isfinite(stride_seconds) or stride_seconds <= 0:
        raise ValueError("stride_seconds muss positiv und endlich sein")
    if stride_seconds > window_seconds:
        raise ValueError("stride_seconds darf keine Lücken erzeugen")
    if max_windows < 1:
        raise ValueError("max_windows muss mindestens 1 sein")

    actual_window = min(window_seconds, duration_seconds)
    final_start = max(0.0, duration_seconds - actual_window)
    starts: list[float] = []
    position = 0.0

    while position < final_start - 1e-7:
        starts.append(position)
        if len(starts) >= max_windows:
            raise ValueError("Zu viele Zeitfenster: Video aufteilen oder Limits anpassen")
        position += stride_seconds

    if not starts or abs(starts[-1] - final_start) > 1e-7:
        starts.append(final_start)
    if len(starts) > max_windows:
        raise ValueError("Zu viele Zeitfenster: Video aufteilen oder Limits anpassen")

    return [
        CandidateWindow(
            source_id=source_id.strip(),
            start_seconds=round(start, 6),
            end_seconds=round(min(duration_seconds, start + actual_window), 6),
        )
        for start in starts
    ]
