"""Extraktion einzelner Videobilder per FFmpeg für einen KI-Prototyp."""

from __future__ import annotations

import math
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from candidate_windows import CandidateWindow


class FrameSampleError(RuntimeError):
    pass


@dataclass(frozen=True)
class SampledFrame:
    timestamp_seconds: float
    jpeg_bytes: bytes


def sample_window_frames(
    video_path: str | Path,
    window: CandidateWindow,
    *,
    frame_count: int = 3,
    max_side: int = 640,
    per_frame_timeout: int = 25,
) -> list[SampledFrame]:
    """Entnimmt Frames innerhalb des Fensters, mit Zeitstempeln.

    Bytes bleiben im Speicher; es werden keine Einzelbilder gespeichert.
    """
    if not 1 <= frame_count <= 6:
        raise ValueError("frame_count muss zwischen 1 und 6 liegen")
    if not 128 <= max_side <= 1280:
        raise ValueError("max_side muss zwischen 128 und 1280 liegen")
    if per_frame_timeout <= 0:
        raise ValueError("per_frame_timeout muss positiv sein")
    if not (
        math.isfinite(window.start_seconds)
        and math.isfinite(window.end_seconds)
        and 0 <= window.start_seconds < window.end_seconds
    ):
        raise ValueError("Ungültiges Zeitfenster")

    path = Path(video_path)
    if not path.is_file():
        raise FrameSampleError("Videodatei fehlt")
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise FrameSampleError("FFmpeg fehlt")

    frames: list[SampledFrame] = []
    for i in range(frame_count):
        stamp = window.start_seconds + window.duration_seconds * (i + 1) / (frame_count + 1)
        cmd = [
            ffmpeg, "-hide_banner", "-loglevel", "error",
            "-ss", f"{stamp:.6f}", "-i", str(path.resolve()),
            "-an", "-frames:v", "1",
            "-vf", f"scale={max_side}:{max_side}:force_original_aspect_ratio=decrease",
            "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1",
        ]
        try:
            result = subprocess.run(
                cmd, check=False, capture_output=True, timeout=per_frame_timeout
            )
        except subprocess.TimeoutExpired as exc:
            raise FrameSampleError("Zeitlimit bei der Frame-Extraktion") from exc
        except OSError as exc:
            raise FrameSampleError("FFmpeg konnte nicht gestartet werden") from exc

        if result.returncode != 0 or not result.stdout:
            raise FrameSampleError(
                f"Videobild bei {stamp:.2f}s konnte nicht gelesen werden"
            )
        if len(result.stdout) > 4 * 1024 * 1024:
            raise FrameSampleError("Extrahiertes Bild überschreitet das Größenlimit")
        frames.append(SampledFrame(timestamp_seconds=stamp, jpeg_bytes=result.stdout))
    return frames
