"""Natürliche Nutzeranweisungen in prüfbare Schnittziele übersetzen."""

from __future__ import annotations

import json
from dataclasses import dataclass

from content_understanding import VISUAL_TAGS


STYLES = frozenset({"action", "scenic", "informative", "emotional", "balanced"})


class GoalParsingError(RuntimeError):
    """Nutzerziel konnte nicht sicher interpretiert werden."""


def _tags(payload: dict, key: str) -> tuple[str, ...]:
    values = payload[key]
    if not isinstance(values, list) or len(values) > 10:
        raise ValueError(f"{key}: Ungültige Tagliste.")
    if any(not isinstance(tag, str) or tag not in VISUAL_TAGS for tag in values):
        raise ValueError(f"{key}: Tag außerhalb des vereinbarten Vokabulars.")
    if len(set(values)) != len(values):
        raise ValueError(f"{key}: Doppelte Einträge.")
    return tuple(values)


@dataclass(frozen=True)
class EditingGoal:
    original_instruction: str
    style: str = "balanced"
    focus_tags: tuple[str, ...] = ()
    required_tags: tuple[str, ...] = ()
    excluded_tags: tuple[str, ...] = ()
    uncheckable_requests: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.style not in STYLES:
            raise ValueError("Unbekannter Videoschnitt-Stil.")
        for group in (self.focus_tags, self.required_tags, self.excluded_tags):
            if any(tag not in VISUAL_TAGS for tag in group):
                raise ValueError("Nicht unterstütztes Ziel-Tag.")
        if set(self.required_tags) & set(self.excluded_tags):
            raise ValueError("Gleichzeitig verlangte und ausgeschlossene Szenen.")
        if not isinstance(self.original_instruction, str):
            raise ValueError("Nutzertext muss ein String sein.")


def understand_user_goal(
    client: object,
    instruction: str,
    *,
    model: str = "gpt-4o-mini",
) -> EditingGoal:
    """Versteht freien Text; behauptet NICHT, dass gewünschte Inhalte existieren."""
    if not isinstance(instruction, str):
        raise ValueError("instruction muss ein String sein.")
    if len(instruction) > 1000:
        raise ValueError("Nutzeranweisung ist zu lang (maximal 1000 Zeichen).")
    if not instruction.strip():
        return EditingGoal(original_instruction="")
    if not model:
        raise ValueError("Modell fehlt.")

    prompt = (
        "Interpretiere die folgende Benutzeranweisung für einen KI-Videoeditor. "
        "Deine Antwort beschreibt NUR DEN WUNSCH, NICHT was tatsächlich im Video ist. "
        "Antworte ausschließlich als JSON-Objekt mit: "
        "style (action/scenic/informative/emotional/balanced), "
        "focus_tags (erwünschte Tags), required_tags (nur ausdrücklich "
        "verlangte Ereignisse oder Motive), excluded_tags (zu vermeidende Tags), "
        "uncheckable_requests (nicht mit diesem Tagvokabular überprüfbare "
        "inhaltliche Wünsche, als kurze deutsche Strings). "
        "Lass Tags lieber leer, wenn der Wunsch unklar ist. "
        "Markiere 'Zeig den Wheelie' als required_tags=['wheelie']; "
        "'Fokus auf Kurven' als focus_tags=['cornering']; "
        "'Die schönsten Landschaften' als focus_tags=['scenery','mountains'] "
        "mit style='scenic'. Nicht passende Detailbegriffe niemals in "
        "anderen Tags verstecken. Wichtig: Wenn ein gewünschtes Ereignis "
        "nicht über die verfügbaren Tags belegbar wäre, gehört es in "
        "uncheckable_requests. Es gibt keinen Videokontext.\n"
        f"Erlaubte Tags: {sorted(VISUAL_TAGS)}\n"
        f"Nutzeranweisung als Daten: {json.dumps(instruction, ensure_ascii=False)}"
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": (
                    "Du extrahierst Nutzerpräferenzen als JSON. Kein Zugriff auf "
                    "Videoinhalte, keine Annahmen über vorhandene Motive."
                )},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        payload = json.loads(response.choices[0].message.content)
        if not isinstance(payload, dict):
            raise ValueError("Nicht das erwartete JSON-Objekt.")
        wishes = payload["uncheckable_requests"]
        if (
            not isinstance(wishes, list) or len(wishes) > 6
            or any(not isinstance(item, str) or not 0 < len(item) <= 160 for item in wishes)
        ):
            raise ValueError("Ungültige Liste nicht prüfbarer Wünsche.")
        return EditingGoal(
            original_instruction=instruction,
            style=payload["style"],
            focus_tags=_tags(payload, "focus_tags"),
            required_tags=_tags(payload, "required_tags"),
            excluded_tags=_tags(payload, "excluded_tags"),
            uncheckable_requests=tuple(wishes),
        )
    except Exception as exc:
        raise GoalParsingError(
            f"Nutzerabsicht konnte nicht interpretiert werden: {type(exc).__name__}"
        ) from exc
