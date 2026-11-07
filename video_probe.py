"""Technische Videoprüfung für VeloCut 2.0.

Benötigt das ausführbare Programm ffprobe (Teil von FFmpeg).
Dieses Modul analysiert noch keine Bildinhalte und führt keinen Videoschnitt aus.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path


class VideoProbeError(RuntimeError):
    """Videometadaten konnten nicht zuverlässig gelesen werden."""


@dataclass(frozen=True)
class VideoMetadata:
    source_id: str
    path: str
    duration_seconds: float
    width: int
    height: int
    fps: float | None
    has_audio: bool
    video_codec: str | None


def _positive_float(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) and result > 0 else None


def _fps(value: object) -> float | None:
    if not isinstance(value, str) or not value or value in {"0/0", "N/A"}:
        return None
    try:
        result = float(Fraction(value))
    except (ValueError, ZeroDivisionError):
        return None
    return result if math.isfinite(result) and result > 0 else None


def probe_video(
    video_path: str | Path,
    *,
    source_id: str,
    timeout_seconds: int = 30,
) -> VideoMetadata:
    """Liest Metadaten eines lokalen Videos mit ffprobe.

    source_id ist eine vom Aufrufer vergebene eindeutige ID und sollte nicht
    nur aus dem Originaldateinamen bestehen (Kollisionen bei Uploads).
    """
    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError("source_id darf nicht leer sein.")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds muss positiv sein.")

    path = Path(video_path)
    if not path.is_file():
        raise VideoProbeError("Die Videodatei existiert nicht.")
    if path.stat().st_size == 0:
        raise VideoProbeError("Die Videodatei ist leer.")

    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        raise VideoProbeError("ffprobe fehlt. Bitte FFmpeg auf dem Server installieren.")

    cmd = [
        ffprobe,
        "-v", "error",
        "-show_entries",
        "format=duration:stream=codec_type,codec_name,width,height,avg_frame_rate,duration",
        "-of", "json",
        str(path),
    ]
    try:
        completed = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_seconds, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise VideoProbeError("Die Videoprüfung hat das Zeitlimit überschritten.") from exc
    except OSError as exc:
        raise VideoProbeError("ffprobe konnte nicht ausgeführt werden.") from exc

    if completed.returncode != 0:
        raise VideoProbeError(
            f"ffprobe meldet einen Fehler: {(completed.stderr or '').strip()[:300]}"
        )

    try:
        payload = json.loads(completed.stdout)
    except (TypeError, ValueError) as exc:
        raise VideoProbeError("ffprobe lieferte kein gültiges JSON.") from exc

    if not isinstance(payload, dict):
        raise VideoProbeError("Unerwartete Metadatenstruktur.")
    streams = payload.get("streams", [])
    if not isinstance(streams, list):
        raise VideoProbeError("Unerwartete Stream-Metadaten.")
    videos = [s for s in streams if isinstance(s, dict) and s.get("codec_type") == "video"]
    if not videos:
        raise VideoProbeError("Keine Videospur gefunden.")

    video = videos[0]
    duration = _positive_float((payload.get("format") or {}).get("duration"))
    if duration is None:
        duration = _positive_float(video.get("duration"))
    if duration is None:
        raise VideoProbeError("Keine gültige Videodauer gefunden.")

    try:
        width, height = int(video.get("width", 0)), int(video.get("height", 0))
    except (ValueError, TypeError, OverflowError) as exc:
        raise VideoProbeError("Ungültige Videoauflösung.") from exc
    if width <= 0 or height <= 0:
        raise VideoProbeError("Videoauflösung fehlt oder ist ungültig.")

    codec = video.get("codec_name")
    return VideoMetadata(
        source_id=source_id.strip(),
        path=str(path.resolve()),
        duration_seconds=duration,
        width=width,
        height=height,
        fps=_fps(video.get("avg_frame_rate")),
        has_audio=any(
            isinstance(s, dict) and s.get("codec_type") == "audio" for s in streams
        ),
        video_codec=codec if isinstance(codec, str) else None,
    )
