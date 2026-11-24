"""Kostenlose lokale Vorprüfung von Testvideos vor jedem KI-Aufruf.

Keine OpenAI-Verbindung, keine Frame-Analyse. Die ermittelten
Zeitfenster prüfen nur technische Grenzwerte der Staging-Version.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from candidate_windows import generate_candidate_windows
from video_probe import VideoMetadata, probe_video

MAX_DURATION_SECONDS = 60
MAX_TOTAL_COARSE_WINDOWS = 24


class VideoPreflightError(ValueError):
    """Nutzerfreundlicher und sicherer Fehler vor dem Start kostenpflichtiger KI."""


def inspect_videos(paths: Sequence[Path]) -> tuple[VideoMetadata, ...]:
    if not 1 <= len(paths) <= 3:
        raise VideoPreflightError("Bitte 1 bis 3 Testvideos wählen.")

    metadata = tuple(
        probe_video(path, source_id=f"video-{index}")
        for index, path in enumerate(paths, 1)
    )
    for item in metadata:
        if item.duration_seconds > MAX_DURATION_SECONDS:
            raise VideoPreflightError(
                f"{item.source_id} ist {item.duration_seconds:.1f} Sekunden lang. "
                "Die Testversion erlaubt maximal 60 Sekunden je Video."
            )
    count = 0
    for item in metadata:
        windows = generate_candidate_windows(
            item.source_id,
            item.duration_seconds,
            window_seconds=8,
            stride_seconds=6,
            max_windows=12,
        )
        count += len(windows)
    if count > MAX_TOTAL_COARSE_WINDOWS:
        raise VideoPreflightError(
            "Die Videos erzeugen zu viele Analysefenster (höchstens 24 insgesamt)."
        )
    return metadata
