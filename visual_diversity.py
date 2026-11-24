"""Unterschiedliche Kameraansichten anhand vorhandener Videobilder abschätzen.

Lokale, konservative Bildähnlichkeit (dHash + aHash), KEINE KI-API.
Schätzung: kleine bewegte Objekte ändern die Kameraansicht nicht unbedingt.
Fehlende/ungültige Bilder dürfen nie zur Behauptung 'gleiches Bild' führen.
"""

from __future__ import annotations

from io import BytesIO
from typing import Sequence

from PIL import Image, UnidentifiedImageError

from batch_frames import FrameCache, select_cached_frames
from candidate_windows import CandidateWindow


# (64-bit difference hash, 64-bit average hash)
FrameFingerprint = tuple[int, int]
ShotFingerprint = tuple[FrameFingerprint, ...]


class VisualDiversityError(RuntimeError):
    """Vorgesehene Thumbnail-Analyse aus tatsächlichen Videoframes fehlgeschlagen."""


def fingerprint_jpeg(jpeg_bytes: bytes) -> FrameFingerprint:
    """Kleine robuste Schwarzweiß-Signatur für bereits extrahierte JPEGs."""
    if not isinstance(jpeg_bytes, bytes) or not jpeg_bytes:
        raise VisualDiversityError("Leeres oder ungültiges Thumbnail.")
    try:
        with Image.open(BytesIO(jpeg_bytes)) as image:
            if image.format != "JPEG":
                raise VisualDiversityError("Erwartet wird ein JPEG-Videoframe.")
            gray = image.convert("L")
            wide = list(gray.resize((9, 8), Image.Resampling.BILINEAR).getdata())
            small = list(gray.resize((8, 8), Image.Resampling.BILINEAR).getdata())
    except (OSError, ValueError, UnidentifiedImageError) as exc:
        raise VisualDiversityError("Thumbnail konnte nicht eingelesen werden.") from exc

    difference = 0
    for row in range(8):
        for col in range(8):
            difference = (difference << 1) | int(
                wide[row * 9 + col] > wide[row * 9 + col + 1]
            )
    average = sum(small) / 64
    average_hash = 0
    for value in small:
        average_hash = (average_hash << 1) | int(value > average)
    return difference, average_hash


def fingerprint_window(cache: FrameCache, window: CandidateWindow) -> ShotFingerprint:
    """Verwendet drei gleichmäßig verteilte vorhandene JPEG-Frames je Fenster."""
    samples = select_cached_frames(cache, window, frame_count=3)
    return tuple(fingerprint_jpeg(frame.jpeg_bytes) for frame in samples)


def _looks_same(left: FrameFingerprint, right: FrameFingerprint) -> bool:
    return (
        (left[0] ^ right[0]).bit_count() <= 9
        and (left[1] ^ right[1]).bit_count() <= 12
    )


def likely_same_camera_view(left: Sequence[FrameFingerprint], right: Sequence[FrameFingerprint]) -> bool:
    """Mehrheitsabgleich in BEIDEN Fenstern, nicht bloß ein Zufallstreffer.

    Ohne mindestens zwei Stichproben pro Fenster keine sichere Schätzung.
    Der Algorithmus ist bewusst konservativ, keine echte Shot-Boundary-Erkennung.
    """
    if len(left) < 2 or len(right) < 2:
        return False
    for samples, others in ((left, right), (right, left)):
        matched = sum(
            any(_looks_same(sample, comparison) for comparison in others)
            for sample in samples
        )
        if matched * 3 < 2 * len(samples):
            return False
    return True
