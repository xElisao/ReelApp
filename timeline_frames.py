"""Lokaler Storyboard-Streifen für den VeloCut-Schnitt-Editor (keine KI).

Ein kurzer visueller Bereich um den bestehenden Clip dient als Orientierung
für einen Streamlit-Bereichsschieber. Quellvideos bleiben nur temporär auf Disk.
"""

from __future__ import annotations

import io
import math
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, UnidentifiedImageError


THUMB_COUNT = 7
THUMB_WIDTH = 150
THUMB_HEIGHT = 84
LABEL_HEIGHT = 23
MAX_STORYBOARD_BYTES = 800_000
PADDING_SECONDS = 4.0


class TimelineError(RuntimeError):
    """Zeitbereich ist ungültig oder die lokale Vorschau fehlgeschlagen."""


def _finite(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def timeline_bounds(
    suggested_start: float, suggested_end: float,
    duration_seconds: float,
    *, padding_seconds: float = PADDING_SECONDS,
) -> tuple[float, float]:
    """Fenster um den Vorschlag; nie über echte Quelldauer hinaus."""
    if not all(
        _finite(value) for value in (
            suggested_start, suggested_end, duration_seconds, padding_seconds
        )
    ):
        raise TimelineError("Ungültige Zeitangaben für die Zeitleiste.")
    if (
        duration_seconds <= 0 or duration_seconds > 60.05
        or suggested_start < 0 or suggested_end <= suggested_start
        or suggested_end > duration_seconds + 0.05
        or padding_seconds < 0 or padding_seconds > 15
    ):
        raise TimelineError("Der Ausschnitt liegt außerhalb des Originalvideos.")

    low = round(max(0.0, suggested_start - padding_seconds), 2)
    high = round(min(duration_seconds, suggested_end + padding_seconds), 2)
    if high - low < 0.25:
        raise TimelineError("Der verfügbare Zeitbereich ist zu kurz.")
    return low, high


def storyboard_timestamps(low: float, high: float, *, count: int = THUMB_COUNT) -> tuple[float, ...]:
    """Gleichmäßig über den angezeigten Zeitraum verteilte Filmframes."""
    if not _finite(low) or not _finite(high) or low < 0 or high <= low:
        raise TimelineError("Ungültiger Bildbereich.")
    if not 2 <= count <= 9 or high > 60.05:
        raise TimelineError("Ungültige Anzahl oder Dauer der Vorschaubilder.")
    step = (high - low) / count
    return tuple(round(low + (i + 0.5) * step, 3) for i in range(count))


def selected_slider_interval(
    chosen: tuple[float, float],
    original: tuple[float, float],
) -> tuple[float, float]:
    """Behalte exakte KI-Startwerte bei, wenn nur die Anzeige gerundet wurde.

    Der Streamlit-Schieber arbeitet auf 0,01 Sekunden. Alte KI-Zeitwerte
    können mehr Stellen haben. Ohne Nutzeränderung darf daraus kein
    unnötiges erneutes Rendern entstehen.
    """
    if len(chosen) != 2 or len(original) != 2:
        raise TimelineError("Ungültiges Schnittintervall.")
    if not all(_finite(v) for v in (*chosen, *original)):
        raise TimelineError("Ungültige Schnittzeit.")
    return tuple(
        float(initial) if abs(float(slider) - float(initial)) <= 0.00501
        else round(float(slider), 2)
        for slider, initial in zip(chosen, original)
    )


def render_storyboard(
    video_path: str | Path,
    *,
    low: float,
    high: float,
    duration_seconds: float,
    timeout_seconds: int = 10,
) -> bytes:
    """Sieben JPEG-Frames in *einem* Bildstreifen; keine OpenAI-Anfrage.

    FFmpeg-Seek pro Bild, kleine Frames (150×84) und gesamt maximal
    800 KB. Bildstempel sind Zeitpunkte im Originalvideo.
    """
    path = Path(video_path)
    if not path.is_file() or not path.stat().st_size:
        raise TimelineError("Das Originalvideo ist nicht verfügbar.")
    if (
        not _finite(duration_seconds)
        or duration_seconds <= 0 or duration_seconds > 60.05
        or not _finite(low) or not _finite(high)
        or low < 0 or high <= low or high > duration_seconds + 0.05
        or timeout_seconds <= 0
    ):
        raise TimelineError("Ungültiger Zeitbereich für die Vorschaubilder.")

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise TimelineError("FFmpeg fehlt auf dem Testserver.")

    sheet = Image.new(
        "RGB", (THUMB_COUNT * THUMB_WIDTH, THUMB_HEIGHT + LABEL_HEIGHT),
        color=(24, 24, 24),
    )
    painter = ImageDraw.Draw(sheet)
    times = storyboard_timestamps(low, min(high, duration_seconds))
    for i, timestamp in enumerate(times):
        # Das letzte Frame nicht versehentlich nach Videoende suchen.
        timestamp = min(timestamp, max(0.0, duration_seconds - 0.04))
        command = [
            ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error",
            "-ss", f"{timestamp:.3f}", "-i", str(path.resolve()),
            "-frames:v", "1",
            "-vf", (
                "scale=150:84:force_original_aspect_ratio=decrease:"
                "force_divisible_by=2,"
                "pad=150:84:(ow-iw)/2:(oh-ih)/2:color=black,"
                "setsar=1"
            ),
            "-q:v", "7", "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1",
        ]
        try:
            result = subprocess.run(
                command, capture_output=True, timeout=timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise TimelineError("Vorschaubilder konnten nicht erstellt werden.") from exc
        if result.returncode != 0 or not result.stdout:
            raise TimelineError("Ein Bild der Zeitleiste konnte nicht gelesen werden.")
        try:
            with Image.open(io.BytesIO(result.stdout)) as image:
                image.load()
                frame = image.convert("RGB")
                if frame.size != (THUMB_WIDTH, THUMB_HEIGHT):
                    raise TimelineError("Unerwartete Vorschaubildgröße.")
                sheet.paste(frame, (i * THUMB_WIDTH, 0))
        except (OSError, UnidentifiedImageError) as exc:
            raise TimelineError("Ein Vorschaubild ist beschädigt.") from exc
        x = i * THUMB_WIDTH
        painter.text(
            (x + 7, THUMB_HEIGHT + 4),
            f"{timestamp:.2f} s",
            fill=(240, 240, 240),
        )
        if i:
            painter.line([(x, 0), (x, THUMB_HEIGHT)], fill=(230, 230, 230), width=2)

    payload = io.BytesIO()
    sheet.save(payload, format="JPEG", quality=78, optimize=True)
    content = payload.getvalue()
    if not 0 < len(content) <= MAX_STORYBOARD_BYTES:
        raise TimelineError("Der Vorschaustreifen überschreitet das Größenlimit.")
    return content
