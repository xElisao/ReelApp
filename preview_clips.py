"""Lokale MP4-Vorschau aus vorhandenen KI-Zeitfenstern, ohne API-Aufruf.

Nur kurze Ansichts-Clips; kein fertiger Reel-Export. Nutzerdateien werden
temporär verarbeitet. Die Vorschau wird im Streamlit-Session-Speicher gehalten.
"""

from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

from video_probe import VideoMetadata, probe_video
from batch_frames import extract_frame_cache
from candidate_windows import CandidateWindow
from frame_sampler import FrameSampleError
from visual_diversity import (
    VisualDiversityError, fingerprint_window, likely_same_camera_view,
)
from shot_boundaries import ShotDetectionError, crosses_hard_cut, detect_hard_cuts


MAX_PREVIEWS = 3
MAX_CLIP_SECONDS = 10.0
MAX_PREVIEW_BYTES = 10 * 1024 * 1024


class PreviewError(RuntimeError):
    """Ungültige Vorschauanforderung oder FFmpeg-Fehler."""


@dataclass(frozen=True)
class PreviewClip:
    source_id: str
    start_seconds: float
    end_seconds: float
    score: float | None
    summary: str
    mp4_bytes: bytes
    similar_view_as: int | None = None


def _number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def pick_suggestions(report: Mapping[str, Any]) -> list[dict]:
    """Bevorzuge Detailanalyse, falls vorhanden; sonst Grobvorschläge."""
    if not isinstance(report, dict):
        raise PreviewError("Analysebericht ist kein JSON-Objekt.")
    refined = report.get("refinement")
    if refined is not None:
        if not isinstance(refined, dict):
            raise PreviewError("Ungültige Detailanalyse.")
        suggestions = refined.get("suggestions")
    else:
        suggestions = report.get("recommendations")
    if not isinstance(suggestions, list):
        raise PreviewError("Keine gültige Liste mit Highlight-Vorschlägen.")
    if len(suggestions) > 10:
        raise PreviewError("Ungewöhnlich viele Highlight-Vorschläge.")
    if not all(isinstance(x, dict) for x in suggestions):
        raise PreviewError("Ungültige Highlight-Daten.")
    return suggestions[:MAX_PREVIEWS]


def _validate_interval(item: dict, metadata: Mapping[str, VideoMetadata]) -> tuple[str, float, float]:
    source_id = item.get("source_id")
    if not isinstance(source_id, str) or source_id not in metadata:
        raise PreviewError("Highlight verweist auf ein unbekanntes Video.")
    start, end = item.get("start_seconds"), item.get("end_seconds")
    if not (_number(start) and _number(end)):
        raise PreviewError("Ungültige Zeitangaben im Highlight.")
    start, end = float(start), float(end)
    duration = metadata[source_id].duration_seconds
    # Kleine Rundungsfehler im Analyse-JSON tolerieren, aber nie außerhalb lesen.
    if start < 0 or end <= start or end > duration + 0.05:
        raise PreviewError("Highlight liegt außerhalb der tatsächlichen Videolänge.")
    end = min(end, duration)
    if end - start > MAX_CLIP_SECONDS + 1e-6:
        raise PreviewError("Highlight ist länger als das Vorschau-Limit.")
    return source_id, start, end


def _render_mp4(
    video_path: str | Path, start: float, end: float, *,
    timeout_seconds: int = 45,
) -> bytes:
    """MP4/H.264 transkodieren; FFmpeg bekommt eine Argumentliste, keine Shell."""
    executable = shutil.which("ffmpeg")
    if executable is None:
        raise PreviewError("FFmpeg fehlt auf dem Testserver.")
    if not _number(start) or not _number(end) or not 0 <= start < end:
        raise PreviewError("Ungültige Vorschauzeit.")
    if end - start > MAX_CLIP_SECONDS + 1e-6:
        raise PreviewError("Maximale Vorschauzeit überschritten.")
    if timeout_seconds <= 0:
        raise PreviewError("Ungültiges Zeitlimit.")

    with tempfile.TemporaryDirectory(prefix="velocut_clip_") as directory:
        destination = Path(directory) / "preview.mp4"
        # Seek vor -i ist schneller bei hochaufgelösten Quellvideos.
        # Da neu kodiert wird, folgt die Ausgabe nicht nur Keyframes.
        cmd = [
            executable, "-hide_banner", "-nostdin", "-loglevel", "error",
            "-y", "-ss", f"{start:.6f}",
            "-i", str(Path(video_path).resolve()),
            "-t", f"{end - start:.6f}",
            "-map", "0:v:0", "-map", "0:a:0?",
            "-vf", "scale=720:720:force_original_aspect_ratio=decrease:force_divisible_by=2",
            "-r", "24",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "29",
            "-pix_fmt", "yuv420p", "-threads", "2",
            "-c:a", "aac", "-b:a", "96k",
            "-movflags", "+faststart",
            str(destination),
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, timeout=timeout_seconds, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise PreviewError("Zeitlimit beim Erstellen der Vorschau überschritten.") from exc
        except OSError as exc:
            raise PreviewError("FFmpeg konnte die Vorschau nicht erstellen.") from exc
        if result.returncode != 0 or not destination.is_file():
            message = result.stderr.decode("utf-8", errors="replace")[-350:]
            raise PreviewError(f"Vorschau konnte nicht erstellt werden: {message}")
        size = destination.stat().st_size
        if not 0 < size <= MAX_PREVIEW_BYTES:
            raise PreviewError("MP4-Vorschau überschreitet das Größenlimit.")
        return destination.read_bytes()


def render_report_previews(
    video_paths: Sequence[Path],
    report: dict,
    *,
    max_previews: int = MAX_PREVIEWS,
) -> list[PreviewClip]:
    """Rendert höchstens drei vorgeschlagene Szenen aus den lokalen Originalen.

    Der JSON-Bericht allein enthält kein Video. Reihenfolge der Dateien muss
    identisch zur ursprünglichen Analyse sein (video-1, video-2, ...).
    """
    if not 1 <= len(video_paths) <= 3:
        raise PreviewError("Bitte 1 bis 3 Originalvideos erneut hochladen.")
    if not 1 <= max_previews <= MAX_PREVIEWS:
        raise PreviewError("Ungültiges Vorschau-Limit.")
    if not isinstance(report, dict) or type(report.get("video_count")) is not int:
        raise PreviewError("Ungültiger Analysebericht.")
    if report["video_count"] != len(video_paths):
        raise PreviewError("Anzahl der Videos passt nicht zum Analysebericht.")

    metadata: dict[str, VideoMetadata] = {}
    for i, path in enumerate(video_paths):
        source_id = f"video-{i + 1}"
        item = probe_video(path, source_id=source_id)
        if item.duration_seconds > 60.05:
            raise PreviewError("Testvideos dürfen höchstens 60 Sekunden lang sein.")
        metadata[source_id] = item

    selections = pick_suggestions(report)
    # Prüfe auch alte KI-Berichte kostenlos auf Mischclips. Ein Bericht aus
    # vorangegangenen Versionen enthält die Schnittgrenzen noch nicht.
    shot_cuts = {}
    for source_id, source in metadata.items():
        try:
            shot_cuts[source_id] = detect_hard_cuts(
                source.path, duration_seconds=source.duration_seconds,
            )
        except ShotDetectionError:
            shot_cuts[source_id] = ()
    clips: list[PreviewClip] = []
    for item in selections[:max_previews]:
        source_id, start, end = _validate_interval(item, metadata)
        if crosses_hard_cut(start, end, shot_cuts[source_id]):
            # Nicht eigenmächtig trimmen: die alte Szenenbeschreibung könnte
            # sich auf das entfernte Motiv beziehen. Sicherer: überspringen.
            continue
        score = item.get("score")
        if score is not None and (not _number(score) or not 0 <= score <= 100):
            raise PreviewError("Ungültige Vorschau-Bewertung.")
        summary = item.get("summary", "Highlight-Vorschlag")
        if not isinstance(summary, str):
            raise PreviewError("Ungültige Szenenbeschreibung.")
        clips.append(
            PreviewClip(
                source_id=source_id,
                start_seconds=start,
                end_seconds=end,
                score=float(score) if score is not None else None,
                summary=summary[:180],
                mp4_bytes=_render_mp4(metadata[source_id].path, start, end),
            )
        )
    # Auch ältere JSON-Berichte lokal beurteilen, ohne KI neu aufzurufen.
    # Anders als beim neuen Ranking werden Clips NICHT versteckt; der Nutzer
    # soll die Vermutung über dieselbe Kameraperspektive überprüfen können.
    goal = report.get("goal")
    if (
        isinstance(goal, dict) and goal.get("style") == "scenic"
        and len(clips) > 1
    ):
        try:
            caches = {}
            signatures = []
            for clip in clips:
                if clip.source_id not in caches:
                    source = metadata[clip.source_id]
                    caches[clip.source_id] = extract_frame_cache(
                        source.path, source_id=source.source_id,
                        duration_seconds=source.duration_seconds,
                    )
                signatures.append(fingerprint_window(
                    caches[clip.source_id],
                    CandidateWindow(
                        clip.source_id, clip.start_seconds, clip.end_seconds
                    ),
                ))
            for index, clip in enumerate(clips):
                for previous in range(index):
                    if (
                        clip.source_id == clips[previous].source_id
                        and likely_same_camera_view(
                            signatures[index], signatures[previous]
                        )
                    ):
                        clips[index] = replace(
                            clip, similar_view_as=previous + 1
                        )
                        break
        except (FrameSampleError, VisualDiversityError, ValueError, OSError):
            # Ein gescheiterter Bildvergleich ist KEIN Beleg für gleiche
            # oder unterschiedliche Szenen. MP4-Preview bleibt nutzbar.
            pass
    return clips
