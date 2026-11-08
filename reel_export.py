"""Erster lokaler MP4-Reel-Export aus bereits geprüften Vorschauclips.

Die Clips bleiben temporär und in der aktuellen Streamlit-Sitzung.
Hochkantformat (540x960), standardmäßig mit weichgezeichnetem Bildhintergrund.
Das vollständige Quellbild bleibt in der Mitte sichtbar; optionale schwarze Balken.
Diese Laborversion exportiert standardmäßig OHNE Ton; vorhandener Originalton
kann beim Export ausdrücklich aktiviert werden. Keine Sprachanalyse/Musikmischung.
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
BACKGROUND_MODES = frozenset({"blur", "black"})
AUDIO_MODES = frozenset({"mute", "original"})
TRANSITION_MODES = frozenset({"cut", "fade"})
FADE_SECONDS = 0.5
MIN_FADE_CLIP_SECONDS = 1.0


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


def expected_reel_duration(
    segments: Sequence[ReelSegment], *,
    transition_mode: str = "cut",
) -> float:
    """Reellaufzeit mit ggf. überlappenden Szenenübergängen berechnen.

    Weiche Übergänge überlagern 0,5 Sekunden der angrenzenden Clips;
    sie fügen KEINE künstliche zusätzliche Zeit ein.
    """
    total = validate_reel_segments(segments)
    if transition_mode not in TRANSITION_MODES:
        raise ReelExportError("Unbekannter Übergangsmodus.")
    if transition_mode == "fade":
        if any(
            segment.duration_seconds < MIN_FADE_CLIP_SECONDS - 1e-6
            for segment in segments
        ):
            raise ReelExportError(
                "Für eine weiche Überblendung muss jede Szene "
                "mindestens 1,00 Sekunden lang sein. "
                "Bitte die Szene verlängern oder direkten Schnitt wählen."
            )
        total -= FADE_SECONDS * (len(segments) - 1)
    return total


def _clip_has_audio(path: Path, *, timeout_seconds: int = 12) -> bool:
    """Prüfe die lokale Vorschau auf Audio, ohne Mediendaten nach außen zu senden."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        raise ReelExportError("FFprobe fehlt auf dem Testserver.")
    try:
        result = subprocess.run(
            [
                ffprobe, "-v", "error", "-select_streams", "a:0",
                "-show_entries", "stream=index", "-of", "csv=p=0",
                str(path),
            ],
            capture_output=True, timeout=timeout_seconds, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReelExportError("Die Tonspur konnte nicht geprüft werden.") from exc
    if result.returncode != 0:
        raise ReelExportError("Die Tonspur konnte nicht geprüft werden.")
    return bool(result.stdout.strip())


def render_test_reel(
    segments: Sequence[ReelSegment],
    *,
    background_mode: str = "blur",
    audio_mode: str = "mute",
    transition_mode: str = "cut",
    timeout_seconds: int = 100,
) -> bytes:
    """Fügt bis zu drei kurze Clips mit normalisierter Hochkant-Leinwand zusammen.

    Jedes Segment wird auf 540x960 / 24fps / SAR=1 normalisiert; unterschiedliche
    Originalauflösungen und Seitenverhältnisse sind damit zulässig.
    Audio: standardmäßig stumm. Bei "original" wird die schon in der
    Vorschau vorhandene Tonspur übernommen; stumme Clips erhalten an
    gleicher Position lokal erzeugte Stille für einen stabilen Export.
    Es erfolgen weder Sprachanalyse noch zusätzliche OpenAI-Aufrufe.
    "blur" erhält das Originalmotiv mittig und füllt freie Flächen mit
    weichgezeichnetem Bildmaterial, "black" bietet den alten Letterbox-Modus.
    "cut" verbindet direkt; "fade" überblendet je 0,5 Sekunden visuell
    per xfade und bei Originalton synchron per acrossfade.
    """
    expected_reel_duration(segments, transition_mode=transition_mode)
    if background_mode not in BACKGROUND_MODES:
        raise ReelExportError("Unbekannter Hintergrundmodus.")
    if audio_mode not in AUDIO_MODES:
        raise ReelExportError("Unbekannter Tonmodus.")
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
            if audio_mode == "original":
                segment_duration = f"{segment.duration_seconds:.6f}"
                if _clip_has_audio(clip_path):
                    # Einheitliches Format für die FFmpeg-Verkettung.
                    # apad/atrim hält Audio exakt auf der Videolänge;
                    # sehr kurze Tonspuren bleiben sonst nicht synchron.
                    graph.append(
                        f"[{index}:a:0]"
                        "aresample=48000,"
                        "aformat=sample_fmts=fltp:sample_rates=48000:"
                        "channel_layouts=stereo,"
                        "asetpts=PTS-STARTPTS,apad,"
                        f"atrim=duration={segment_duration}"
                        f"[a{index}]"
                    )
                else:
                    # Gemischte Auswahl aus Clips mit und ohne Ton:
                    # die stummen Teile dürfen nicht verschoben werden.
                    graph.append(
                        "anullsrc=r=48000:cl=stereo,"
                        f"atrim=duration={segment_duration},"
                        "aformat=sample_fmts=fltp:sample_rates=48000:"
                        "channel_layouts=stereo,"
                        f"asetpts=PTS-STARTPTS[a{index}]"
                    )
            if background_mode == "blur":
                # Eine einzige Videoquelle wird in Hintergrund und Vordergrund
                # geteilt. Das Hintergrundbild füllt 9:16 aus (Crop nur HINTER
                # dem Motiv); das scharfe Motiv selbst bleibt vollständig.
                graph.extend([
                    f"[{index}:v:0]fps=24,setsar=1,split=2[bg{index}][fg{index}]",
                    f"[bg{index}]"
                    "scale=540:960:force_original_aspect_ratio=increase,"
                    "crop=540:960,"
                    "boxblur=luma_radius=18:luma_power=2:"
                    "chroma_radius=9:chroma_power=2,"
                    "eq=brightness=-0.055:saturation=0.9"
                    f"[blur{index}]",
                    f"[fg{index}]"
                    "scale=540:960:force_original_aspect_ratio=decrease:"
                    "force_divisible_by=2,setsar=1"
                    f"[sharp{index}]",
                    f"[blur{index}][sharp{index}]"
                    "overlay=(W-w)/2:(H-h)/2:shortest=1,"
                    "setsar=1,format=yuv420p,setpts=PTS-STARTPTS,"
                    f"trim=duration={segment.duration_seconds:.6f},settb=AVTB"
                    f"[v{index}]",
                ])
            else:
                graph.append(
                    f"[{index}:v:0]"
                    "fps=24,"
                    "scale=540:960:force_original_aspect_ratio=decrease:"
                    "force_divisible_by=2,"
                    "pad=540:960:(ow-iw)/2:(oh-ih)/2:color=black,"
                    "setsar=1,format=yuv420p,setpts=PTS-STARTPTS,"
                    f"trim=duration={segment.duration_seconds:.6f},settb=AVTB"
                    f"[v{index}]"
                )
        if transition_mode == "fade":
            # Video- und Tonspuren überlappen jeweils FADE_SECONDS.
            # Alle Videos haben dieselbe Canvas, 24 fps und AVTB.
            # Die zweite xfade-Position bezieht sich auf die bereits
            # um vorherige Blenden verkürzte Ergebnis-Zeitleiste.
            current_video = "v0"
            prefix_duration = segments[0].duration_seconds
            for index in range(1, len(segments)):
                offset = (
                    prefix_duration - FADE_SECONDS * index
                )
                next_video = (
                    "video" if index == len(segments) - 1
                    else f"vf{index}"
                )
                graph.append(
                    f"[{current_video}][v{index}]"
                    f"xfade=transition=fade:duration={FADE_SECONDS:.6f}:"
                    f"offset={offset:.6f}[{next_video}]"
                )
                current_video = next_video
                prefix_duration += segments[index].duration_seconds

            if audio_mode == "original":
                current_audio = "a0"
                for index in range(1, len(segments)):
                    next_audio = (
                        "audio" if index == len(segments) - 1
                        else f"af{index}"
                    )
                    graph.append(
                        f"[{current_audio}][a{index}]"
                        f"acrossfade=d={FADE_SECONDS:.6f}:"
                        f"c1=tri:c2=tri[{next_audio}]"
                    )
                    current_audio = next_audio
        elif audio_mode == "original":
            graph.append(
                "".join(
                    f"[v{i}][a{i}]" for i in range(len(segments))
                ) + f"concat=n={len(segments)}:v=1:a=1[video][audio]"
            )
        else:
            graph.append(
                "".join(f"[v{i}]" for i in range(len(segments)))
                + f"concat=n={len(segments)}:v=1:a=0[video]"
            )
        destination = target / "velocut_test_reel.mp4"
        cmd.extend([
            "-filter_complex", ";".join(graph),
            "-map", "[video]",
        ])
        if audio_mode == "original":
            cmd.extend([
                "-map", "[audio]", "-c:a", "aac", "-b:a", "128k",
                "-ar", "48000",
            ])
        else:
            cmd.append("-an")
        cmd.extend([
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
