"""Effiziente Frame-Stichproben aus einem Video in EINEM FFmpeg-Lauf.

Nur Vorstufe des Highlight-Modells: Bilder und Zeitangaben beweisen noch
keine Ereignisse. Frame-Zeiten sind nominale fps-Rasterpunkte, keine
framegenauen, originalen PTS.
"""

from __future__ import annotations

import math
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from candidate_windows import CandidateWindow
from frame_sampler import FrameSampleError, SampledFrame


@dataclass(frozen=True)
class FrameCache:
    """Frames desselben Quellvideos – nach Zeitstempel sortiert."""

    source_id: str
    duration_seconds: float
    sample_rate: float
    frames: tuple[SampledFrame, ...]


def extract_frame_cache(
    video_path: str | Path,
    *,
    source_id: str,
    duration_seconds: float,
    sample_rate: float = 2.0,
    max_side: int = 640,
    max_frames: int = 125,
    max_total_bytes: int = 40 * 1024 * 1024,
    timeout_seconds: int = 90,
) -> FrameCache:
    """Extrahiert Bilder fürs gesamte Video in einem FFmpeg-Prozess.

    Die Datei- und RAM-Grenzen sind für Videos bis ca. 60 Sekunden gedacht.
    FFmpeg gibt JPEGs in ein automatisch gelöschtes temporäres Verzeichnis aus.
    Ein explizites Limit stoppt Analyse langer Dateien statt sie abzuschneiden.
    """
    path = Path(video_path)
    if not path.is_file() or path.stat().st_size <= 0:
        raise FrameSampleError("Videodatei fehlt oder ist leer.")
    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError("source_id fehlt.")
    if not isinstance(duration_seconds, (int, float)) or isinstance(duration_seconds, bool) or not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise ValueError("Ungültige Videodauer.")
    if not isinstance(sample_rate, (int, float)) or isinstance(sample_rate, bool) or not math.isfinite(sample_rate) or sample_rate <= 0 or sample_rate > 8:
        raise ValueError("sample_rate muss zwischen 0 und 8 (exkl. 0) sein.")
    if not 128 <= max_side <= 1280:
        raise ValueError("max_side muss zwischen 128 und 1280 liegen.")
    if max_frames < 1 or max_total_bytes < 1 or timeout_seconds <= 0:
        raise ValueError("Ungültige Ressourcenlimits.")

    expected_max = math.ceil(duration_seconds * sample_rate) + 1
    if expected_max > max_frames:
        raise ValueError(
            f"Video benötigt bis zu {expected_max} Frames; Limit ist {max_frames}. "
            "Video kürzen oder Limits bewusst anpassen."
        )
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise FrameSampleError("FFmpeg ist nicht installiert.")

    with tempfile.TemporaryDirectory(prefix="velocut_batch_") as directory:
        target = Path(directory)
        cmd = [
            ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error",
            "-i", str(path.resolve()),
            "-map", "0:v:0", "-an",
            "-vf", (
                f"fps={sample_rate:g},"
                f"scale={max_side}:{max_side}:force_original_aspect_ratio=decrease"
            ),
            "-q:v", "5", "-start_number", "0",
            "-frames:v", str(max_frames),
            str(target / "frame_%05d.jpg"),
        ]
        try:
            completed = subprocess.run(
                cmd, capture_output=True, timeout=timeout_seconds, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise FrameSampleError("Zeitlimit der gebündelten Extraktion überschritten.") from exc
        except OSError as exc:
            raise FrameSampleError("FFmpeg konnte nicht gestartet werden.") from exc

        if completed.returncode != 0:
            error = completed.stderr.decode("utf-8", errors="replace")[:250]
            raise FrameSampleError(f"FFmpeg-Extraktion fehlgeschlagen: {error}")

        images = sorted(target.glob("frame_*.jpg"))
        if not images:
            raise FrameSampleError("FFmpeg hat keine Videobilder erzeugt.")
        if len(images) >= max_frames and expected_max > max_frames - 2:
            # Die Ausgabe könnte durch -frames:v abgeschnitten worden sein.
            # Bei Grenzfällen keinen vollständigen Scan vortäuschen.
            raise FrameSampleError("Frame-Limit erreicht; Vollständigkeit unklar.")

        total_size = 0
        samples: list[SampledFrame] = []
        for index, image in enumerate(images):
            if not re.fullmatch(r"frame_\d{5}\.jpg", image.name):
                raise FrameSampleError("Unerwarteter Bilddateiname.")
            size = image.stat().st_size
            total_size += size
            if size <= 0 or size > 4 * 1024 * 1024 or total_size > max_total_bytes:
                raise FrameSampleError("Maximale Bild-/Speichergröße überschritten.")
            data = image.read_bytes()
            if not (data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9")):
                raise FrameSampleError("Keine gültigen JPEG-Rahmenmarker.")
            samples.append(
                SampledFrame(timestamp_seconds=round(index / sample_rate, 6), jpeg_bytes=data)
            )

    # Nicht stillschweigend behaupten, ein kurzes Video sei ganz gelesen,
    # wenn FFmpeg viel zu wenige Bilder erzeugte.
    if samples[-1].timestamp_seconds < duration_seconds - max(1.0, 2.0 / sample_rate):
        raise FrameSampleError("Videoframes decken das Ende nicht ab.")

    return FrameCache(
        source_id=source_id.strip(), duration_seconds=duration_seconds,
        sample_rate=float(sample_rate), frames=tuple(samples),
    )


def select_cached_frames(
    cache: FrameCache,
    window: CandidateWindow,
    *,
    frame_count: int = 3,
) -> list[SampledFrame]:
    """Nimmt möglichst gleichmäßig verteilte, unterschiedliche Bilder je Fenster."""
    if window.source_id != cache.source_id:
        raise ValueError("Zeitfenster und FrameCache gehören zu anderen Videos.")
    if not 0 <= window.start_seconds < window.end_seconds <= cache.duration_seconds:
        raise ValueError("Zeitfenster liegt außerhalb des Videos.")
    if not 1 <= frame_count <= 8:
        raise ValueError("frame_count muss zwischen 1 und 8 liegen.")

    available = [
        frame for frame in cache.frames
        if window.start_seconds <= frame.timestamp_seconds <= window.end_seconds
    ]
    if not available:
        raise FrameSampleError("Kein gecachtes Bild in diesem Zeitfenster.")
    targets = [
        window.start_seconds + window.duration_seconds * (i + 1) / (frame_count + 1)
        for i in range(frame_count)
    ]
    picked: dict[float, SampledFrame] = {}
    for target in targets:
        options = (frame for frame in available if frame.timestamp_seconds not in picked)
        best = min(options, key=lambda x: abs(x.timestamp_seconds - target), default=None)
        if best is not None:
            picked[best.timestamp_seconds] = best
    return sorted(picked.values(), key=lambda x: x.timestamp_seconds)
