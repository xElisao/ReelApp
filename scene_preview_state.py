"""Sitzungsstatus für die einzeln gerenderten Schnittvorschauen.

Ein geänderter Start-/End-Regler muss alte MP4-Inhalte sofort ungültig
machen. Die ursprünglichen KI-Vorschauclips bleiben davon unberührt.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import MutableMapping


class PreviewStateError(ValueError):
    """Eine ungültige Szenen-Signatur oder MP4-Vorschau wurde übergeben."""


def scene_signature(
    preview_id: str, scene_number: int, source_id: str,
    start_seconds: float, end_seconds: float,
) -> str:
    """Identität des gegenwärtig ausgewählten Schnitts."""
    if (
        not isinstance(preview_id, str) or not preview_id
        or not isinstance(scene_number, int) or isinstance(scene_number, bool)
        or scene_number < 1 or scene_number > 3
        or not isinstance(source_id, str) or not source_id
        or not all(
            isinstance(v, (int, float))
            and not isinstance(v, bool) and math.isfinite(v)
            for v in (start_seconds, end_seconds)
        )
        or start_seconds < 0 or end_seconds <= start_seconds
    ):
        raise PreviewStateError("Ungültige Szene für die Schnittvorschau.")
    return hashlib.sha256(
        json.dumps([
            preview_id, scene_number, source_id,
            round(start_seconds, 6), round(end_seconds, 6),
        ]).encode("utf-8")
    ).hexdigest()


def expire_scene_preview(session_state: MutableMapping, key: str) -> None:
    """Bei einer Regleränderung den alten Playerzustand sofort entfernen."""
    if session_state.pop(key, None) is not None:
        session_state[f"{key}_outdated"] = True


def read_current_scene_preview(
    session_state: MutableMapping, key: str, signature: str, *,
    uploads_match: bool,
) -> dict | None:
    """Nur MP4 der derzeitigen Auswahl zurückgeben, nie eine veraltete."""
    saved = session_state.get(key)
    if saved is None:
        return None
    if not isinstance(saved, dict) or (
        saved.get("signature") != signature
        or not uploads_match
    ):
        expire_scene_preview(session_state, key)
        return None
    return saved


def store_scene_preview(
    session_state: MutableMapping, key: str, signature: str, mp4_bytes: bytes,
) -> None:
    """Neuen Player nur nach erfolgreichem Rendern freischalten."""
    if (
        not isinstance(signature, str) or len(signature) != 64
        or not isinstance(mp4_bytes, bytes)
        or len(mp4_bytes) < 8 or mp4_bytes[4:8] != b"ftyp"
    ):
        raise PreviewStateError("Ungültige MP4-Schnittvorschau.")
    session_state[key] = {
        "signature": signature,
        "mp4_bytes": mp4_bytes,
    }
    session_state.pop(f"{key}_outdated", None)
