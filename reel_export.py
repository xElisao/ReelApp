"""Erster lokaler MP4-Reel-Export aus bereits geprüften Vorschauclips.

Die Clips bleiben temporär und in der aktuellen Streamlit-Sitzung.
Hochkantformat (540x960), mit schwarzen Rändern statt ungewolltem Zuschnitt.
Diese Laborversion exportiert bewusst OHNE Ton und ohne Musikrechte-/Audio-Mix.
Es wird weder das Originalvideo noch die OpenAI-API erneut benötigt.
"""

from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


MAX_SEGMENTS = 3
MAX_SEGMENT_SECONDS = 10.0
MAX_REEL_SECONDS = 30.0
MAX_SEGMENT_BYTES = 10 * 1024 * 1024
MAX_REEL_BYTES = 40 * 1024 * 1024


class ReelExportError(RuntimeError):
    """Ungültige Reel-Auswahl oder lokaler FFmpeg-Fehler."""


@dataclass(frozen=True)
class ReelSegment:
    source_id: str
    start_seconds: float
    end_seconds: float
    mp4_bytes: bytes

    @property
    def duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds


def validate_reel_segments(segments: Sequence[ReelSegment]) -> float:
    """Prüft Zeitlimits, echte MP4-Dateien und doppelte/überlappende Auswahl."""
    if not 2 <= len(segments) <= MAX_SEGMENTS:
        raise ReelExportError("Bitte 2 bis 3 Vorschauclips für das Test-Reel auswählen.")

    total = 0.0
    intervals: dict[str, list[tuple[float, float]]] = {}
    for segment in segments:
        if not isinstance(segment, ReelSegment):
            raise ReelExportError("Ungültige Vorschau-Auswahl.")
        if not isinstance(segment.source_id, str) or not segment.source_id.strip():
            raise ReelExportError("Dem Clip fehlt die Video-Quelle.")
        start, end = segment.start_seconds, segment.end_seconds
        if (
            not isinstance(start, (int, float)) or isinstance(start, bool)
            or not isinstance(end, (int, float)) or isinstance(end, bool)
            or not math.isfinite(start) or not math.isfinite(end)
            or start < 0 or end <= start
        ):
            raise ReelExportError("Ungültige Clip-Zeitangaben.")
        duration = end - start
        if duration > MAX_SEGMENT_SECONDS + 1e-6:
            raise ReelExportError("Ein Clip ist länger als 10 Sekunden.")
        if (
            not isinstance(segment.mp4_bytes, bytes)
            or not 8 <= len(segment.mp4_bytes) <= MAX_SEGMENT_BYTES
            or segment.mp4_bytes[4:8] != b"ftyp"
        ):
            raise ReelExportError("Ein Vorschauclip ist kein gültiger MP4-Container.")
        total += duration
        intervals.setdefault(segment.source_id, []).append((start, end))

    if total > MAX_REEL_SECONDS + 1e-6:
        raise ReelExportError("Das Test-Reel darf maximal 30 Sekunden lang sein.")
    for spans in intervals.values():
        ordered = sorted(spans)
        for earlier, later in zip(ordered, ordered[1:]):
            if later[0] < earlier[1] - 1e-6:
                raise ReelExportError(
                    "Zwei Clips überlappen im Originalvideo. "
                    "Bitte einen davon abwählen."
                )
    return total


def render_test_reel(
    segments: Sequence[ReelSegment],
    *,
    timeout_seconds: int = 100,
) -> bytes:
    """Fügt bis zu drei kurze Clips mit normalisierter Hochkant-Leinwand zusammen.

    Jedes Segment wird auf 540x960 / 24fps / SAR=1 normalisiert; unterschiedliche
    Originalauflösungen und Seitenverhältnisse sind damit zulässig.
    Das Ergebnis hat keine Audiospur (expliziter MVP-Umfang).
    """
    validate_reel_segments(segments)
    if timeout_seconds <= 0:
        raise ReelExportError("Ungültiges Render-Zeitlimit.")
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise ReelExportError("FFmpeg fehlt auf dem Testserver.")

    with tempfile.TemporaryDirectory(prefix="velocut_reel_") as directory:
        target = Path(directory)
        cmd = [ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error", "-y"]
        graph = []
        for index, segment in enumerate(segments):
            clip_path = target / f"clip_{index:02d}.mp4"
            clip_path.write_bytes(segment.mp4_bytes)
            cmd.extend(["-i", str(clip_path)])
            graph.append(
                f"[{index}:v:0]"
                "fps=24,"
                "scale=540:960:force_original_aspect_ratio=decrease:"
                "force_divisible_by=2,"
                "pad=540:960:(ow-iw)/2:(oh-ih)/2:color=black,"
                "setsar=1,format=yuv420p,setpts=PTS-STARTPTS"
                f"[v{index}]"
            )
        graph.append(
            "".join(f"[v{i}]" for i in range(len(segments)))
            + f"concat=n={len(segments)}:v=1:a=0[video]"
        )
        destination = target / "velocut_test_reel.mp4"
        cmd.extend([
            "-filter_complex", ";".join(graph),
            "-map", "[video]", "-an",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
            "-pix_fmt", "yuv420p", "-threads", "2",
            "-movflags", "+faststart", str(destination),
        ])
        try:
            result = subprocess.run(
                cmd, capture_output=True, check=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise ReelExportError("Zeitlimit beim Zusammenfügen überschritten.") from exc
        except OSError as exc:
            raise ReelExportError("FFmpeg konnte das Reel nicht erstellen.") from exc

        if result.returncode != 0 or not destination.is_file():
            # Potenziell sensible Dateipfade/Metadaten nicht in die UI übernehmen.
            raise ReelExportError(
                "Die Vorschauclips konnten nicht zu einem MP4-Reel kombiniert werden."
            )
        size = destination.stat().st_size
        if not 8 <= size <= MAX_REEL_BYTES:
            raise ReelExportError("Das erstellte Reel überschreitet das Größenlimit.")
        output = destination.read_bytes()
        if output[4:8] != b"ftyp":
            raise ReelExportError("FFmpeg hat keinen gültigen MP4-Container ausgegeben.")
        return output
