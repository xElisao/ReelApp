"""Abrupte Videobildwechsel lokal mit FFmpeg erkennen (ohne OpenAI-API).

Diese Heuristik erkennt harte Schnitte und ist weder eine framegenaue
Szenensegmentierung noch zuverlässig für Blenden, Schwenks oder schnelle Action.
Bei Unsicherheit lieber keine vermeintlich sicheren Schnittgrenzen erfinden.
"""

from __future__ import annotations

import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Sequence


class ShotDetectionError(RuntimeError):
    """Die lokale Erkennung von harten Szenenschnitten ist fehlgeschlagen."""


def detect_hard_cuts(
    video_path: str | Path,
    *,
    duration_seconds: float,
    threshold: float = 0.18,
    timeout_seconds: int = 45,
    max_cuts: int = 80,
) -> tuple[float, ...]:
    """Liest den Szenenwechsel-Score jedes Frames in kleinem Vorschaubildformat.

    FFmpeg select(scene) liefert den Zeitstempel des ersten Frames des
    neuen Bildmotivs. Nur ausreichend deutliche Unterschiede werden erfasst.
    """
    path = Path(video_path)
    if not path.is_file() or path.stat().st_size <= 0:
        raise ShotDetectionError("Videodatei fehlt oder ist leer.")
    if (
        not isinstance(duration_seconds, (int, float))
        or isinstance(duration_seconds, bool)
        or not math.isfinite(duration_seconds)
        or duration_seconds <= 0
    ):
        raise ValueError("Ungültige Videodauer für die Schnittsuche.")
    if not 0.05 <= threshold <= 0.8 or timeout_seconds <= 0 or max_cuts < 1:
        raise ValueError("Ungültige Parameter der Schnittsuche.")
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise ShotDetectionError("FFmpeg ist für die Schnittsuche nicht installiert.")

    command = [
        ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "info",
        "-i", str(path.resolve()),
        "-map", "0:v:0", "-an",
        "-vf", (
            "scale=320:-2,"
            f"select='gt(scene,{threshold:g})',showinfo"
        ),
        "-f", "null", "-",
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise ShotDetectionError("Zeitlimit bei der Schnittsuche überschritten.") from exc
    except OSError as exc:
        raise ShotDetectionError("FFmpeg konnte die Schnittsuche nicht starten.") from exc
    if result.returncode != 0:
        raise ShotDetectionError("Schnittsuche konnte das Video nicht lesen.")

    # Nur showinfo-Zeilen aus der Filterausgabe auswerten, nicht beliebige Logs.
    stamps: list[float] = []
    for line in result.stderr.decode("utf-8", errors="replace").splitlines():
        if "Parsed_showinfo" not in line:
            continue
        match = re.search(r"\bpts_time:\s*([0-9]+(?:\.[0-9]+)?)", line)
        if not match:
            continue
        timestamp = float(match.group(1))
        if 0.1 < timestamp < duration_seconds - 0.1:
            if not stamps or abs(timestamp - stamps[-1]) >= 0.15:
                stamps.append(round(timestamp, 3))
        if len(stamps) > max_cuts:
            raise ShotDetectionError("Zu viele mögliche Schnitte für eine sichere Auswertung.")
    return tuple(stamps)


def crosses_hard_cut(
    start_seconds: float,
    end_seconds: float,
    cuts: Sequence[float],
    *,
    edge_tolerance: float = 0.12,
) -> bool:
    """Nur Schnitte klar *innerhalb* des Zeitfensters machen es unsicher.

    Liegt ein Schnitt direkt am Anfang/Ende, zählt er als erlaubte Clip-Grenze.
    """
    if not (
        math.isfinite(start_seconds) and math.isfinite(end_seconds)
        and 0 <= start_seconds < end_seconds
    ):
        raise ValueError("Ungültiges Zeitfenster.")
    return any(
        math.isfinite(cut)
        and start_seconds + edge_tolerance < cut < end_seconds - edge_tolerance
        for cut in cuts
    )
