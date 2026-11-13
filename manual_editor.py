"""Manueller Clip-Editor für VeloCut-Test-Reels – vollständig ohne KI.

Nur für Vorschauclips aus einer bereits erfolgreichen Analyse.
Änderungen werden bei Bedarf lokal aus denselben Originaluploads mit FFmpeg
neu gerendert; unveränderte Vorschauen werden ohne Re-Encoding übernommen.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from preview_clips import PreviewError, _render_mp4
from reel_export import ReelExportError, ReelSegment, validate_reel_segments
from shot_boundaries import ShotDetectionError, crosses_hard_cut, detect_hard_cuts
from video_probe import VideoProbeError, probe_video

MIN_EDIT_SECONDS = 0.25
MAX_SOURCE_SECONDS = 60.05


class EditorError(RuntimeError):
    """Nicht zulässiger Schnitt oder lokale Dateiprüfung fehlgeschlagen."""


@dataclass(frozen=True)
class ClipEdit:
    """Ein vom Nutzer gewählter Ausschnitt eines vorhandenen KI-Vorschauclips."""

    source_id: str
    start_seconds: float
    end_seconds: float
    suggested_start: float
    suggested_end: float
    mp4_bytes: bytes

    @property
    def changed(self) -> bool:
        return (
            abs(self.start_seconds - self.suggested_start) > 0.001
            or abs(self.end_seconds - self.suggested_end) > 0.001
        )


def validate_single_edit(item: ClipEdit) -> None:
    """Einzelne Szenen prüfen, auch vor dem isolierten Vorschau-Rendern."""
    if not isinstance(item, ClipEdit):
        raise EditorError("Ungültige Szenenauswahl.")
    vals = (
        item.start_seconds, item.end_seconds,
        item.suggested_start, item.suggested_end,
    )
    if any(
        not isinstance(value, (float, int))
        or isinstance(value, bool) or not math.isfinite(value)
        for value in vals
    ):
        raise EditorError("Die Schnittzeiten müssen gültige Zahlen sein.")
    if (
        item.start_seconds < 0
        or item.end_seconds - item.start_seconds < MIN_EDIT_SECONDS - 1e-6
    ):
        raise EditorError("Eine Szene muss mindestens 0,25 Sekunden lang sein.")
    if item.end_seconds - item.start_seconds > 10.0 + 1e-6:
        raise EditorError("Eine Szene darf höchstens 10 Sekunden lang sein.")
    if item.end_seconds > MAX_SOURCE_SECONDS + 0.05:
        raise EditorError("Der Ausschnitt liegt außerhalb des Originalvideo-Limits.")
    if item.suggested_start < 0 or item.suggested_end <= item.suggested_start:
        raise EditorError("Ungültiger Ausgangsclip.")
    if not isinstance(item.source_id, str) or not item.source_id.strip():
        raise EditorError("Dem Clip fehlt die Originalvideo-Quelle.")
    if (
        not isinstance(item.mp4_bytes, bytes)
        or not 8 <= len(item.mp4_bytes) <= 10 * 1024 * 1024
        or item.mp4_bytes[4:8] != b"ftyp"
    ):
        raise EditorError("Der ursprüngliche Vorschauclip ist kein gültiger MP4-Container.")


def _render_checked_edit(
    edit: ClipEdit, source_path: Path, *,
    duration_seconds: float, shot_cuts: Sequence[float],
) -> bytes:
    """Identische Sicherheit beim Einzel-Preview und beim Reel-Export."""
    if edit.end_seconds > duration_seconds + 0.05:
        raise EditorError(
            "Der manuelle Ausschnitt reicht über das Ende des Originalvideos."
        )
    if crosses_hard_cut(edit.start_seconds, edit.end_seconds, shot_cuts):
        raise EditorError(
            "Der neue Ausschnitt enthält einen erkannten harten "
            "Bildwechsel. Bitte Start oder Ende anpassen."
        )
    try:
        return _render_mp4(
            source_path, edit.start_seconds,
            min(edit.end_seconds, duration_seconds),
        )
    except PreviewError as exc:
        raise EditorError(
            "Der geänderte Videoausschnitt konnte nicht erstellt werden."
        ) from exc


def render_single_scene_preview(
    edit: ClipEdit, original_path: Path | None = None,
) -> bytes:
    """Den tatsächlich geschnittenen Einzelclip lokal abspielbar machen.

    Original-Hashvergleich erfolgt im Streamlit-Aufrufer vor dem Zugriff.
    Ohne Änderung kann die bestehende geprüfte Vorschau direkt verwendet
    werden. Mit Änderung: dieselben Shot-Grenzen wie beim Reel-Export.
    """
    validate_single_edit(edit)
    if not edit.changed:
        return edit.mp4_bytes
    if original_path is None:
        raise EditorError(
            "Für eine neue Schnittvorschau bitte dasselbe Originalvideo hochladen."
        )
    try:
        info = probe_video(original_path, source_id=edit.source_id)
    except (VideoProbeError, ValueError, OSError) as exc:
        raise EditorError("Das Originalvideo konnte nicht geprüft werden.") from exc
    if info.duration_seconds > MAX_SOURCE_SECONDS:
        raise EditorError("Originalvideos dürfen maximal 60 Sekunden lang sein.")
    try:
        shots = detect_hard_cuts(
            info.path, duration_seconds=info.duration_seconds,
        )
    except (ShotDetectionError, ValueError, OSError) as exc:
        raise EditorError(
            "Die Schnittprüfung ist fehlgeschlagen. "
            "Der geänderte Clip wurde nicht exportiert."
        ) from exc
    return _render_checked_edit(
        edit, info.path,
        duration_seconds=info.duration_seconds,
        shot_cuts=shots,
    )


def validate_manual_edits(edits: Sequence[ClipEdit]) -> None:
    """Schnitte und Duplikate vor zeitaufwendiger Bearbeitung prüfen."""
    if not 2 <= len(edits) <= 3:
        raise EditorError("Bitte 2 bis 3 Szenen für das Reel auswählen.")
    segments = []
    for item in edits:
        validate_single_edit(item)
        segments.append(
            ReelSegment(
                source_id=item.source_id,
                start_seconds=item.start_seconds,
                end_seconds=item.end_seconds,
                mp4_bytes=item.mp4_bytes,
            )
        )
    try:
        validate_reel_segments(segments)
    except ReelExportError as exc:
        raise EditorError(str(exc)) from exc


def prepare_edited_segments(
    edits: Sequence[ClipEdit],
    original_paths: Sequence[Path] | None = None,
) -> list[ReelSegment]:
    """Wiederverwendung unveränderter MP4s oder sichere lokale Neuschnitte.

    Der Anrufer muss vor dem Bereitstellen der Originaluploads die Hashwerte
    der Dateien mit dem Vorschauzeitpunkt vergleichen. Die Dateien werden
    nicht dauerhaft gespeichert.
    """
    validate_manual_edits(edits)
    if not any(edit.changed for edit in edits):
        return [
            ReelSegment(e.source_id, e.start_seconds, e.end_seconds, e.mp4_bytes)
            for e in edits
        ]

    if not original_paths or not 1 <= len(original_paths) <= 3:
        raise EditorError(
            "Für geänderte Schnitte bitte dieselben Originalvideos "
            "erneut hochladen."
        )

    metadata = {}
    for i, path in enumerate(original_paths, 1):
        source_id = f"video-{i}"
        try:
            info = probe_video(path, source_id=source_id)
        except (VideoProbeError, ValueError, OSError) as exc:
            raise EditorError("Das Originalvideo konnte nicht geprüft werden.") from exc
        if info.duration_seconds > MAX_SOURCE_SECONDS:
            raise EditorError("Originalvideos dürfen maximal 60 Sekunden lang sein.")
        metadata[source_id] = info

    changed_sources = {e.source_id for e in edits if e.changed}
    for edit in edits:
        if edit.source_id not in metadata:
            raise EditorError("Ein Ausschnitt verweist auf ein unbekanntes Originalvideo.")
        if edit.changed and edit.end_seconds > metadata[edit.source_id].duration_seconds + 0.05:
            raise EditorError(
                "Der manuelle Ausschnitt reicht über das Ende des Originalvideos."
            )

    cuts = {}
    for source_id in changed_sources:
        info = metadata[source_id]
        try:
            cuts[source_id] = detect_hard_cuts(
                info.path, duration_seconds=info.duration_seconds,
            )
        except (ShotDetectionError, ValueError, OSError) as exc:
            # Bei manuellen Änderungen niemals einen Schnitt stillschweigend
            # als sicher behandeln, wenn die Prüfung fehlgeschlagen ist.
            raise EditorError(
                "Die Schnittprüfung ist fehlgeschlagen. "
                "Der geänderte Clip wurde nicht exportiert."
            ) from exc

    rendered = []
    for edit in edits:
        info = metadata[edit.source_id]
        if edit.changed:
            mp4_bytes = _render_checked_edit(
                edit, info.path,
                duration_seconds=info.duration_seconds,
                shot_cuts=cuts[edit.source_id],
            )
        else:
            mp4_bytes = edit.mp4_bytes
        rendered.append(
            ReelSegment(
                edit.source_id,
                edit.start_seconds,
                min(edit.end_seconds, info.duration_seconds),
                mp4_bytes,
            )
        )
    return rendered
