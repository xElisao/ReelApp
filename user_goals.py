"""Natürliche Nutzeranweisungen in prüfbare Schnittziele übersetzen."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from content_understanding import VISUAL_TAGS


STYLES = frozenset({"action", "scenic", "informative", "emotional", "balanced"})

# Kleine, bewusst konservative Wortliste für klar sichtbare Nutzerpräferenzen.
# Das ist KEINE Erkennung von Videoereignissen – nur eine Absicherung gegen
# die fehlerhafte Einstufung gewöhnlicher Nutzerwörter als "nicht prüfbar".
_VISIBLE_FOCUS_PATTERNS = (
    (r"\bmotorr(?:ad|äder|aeder)\w*", "motorcycle"),
    (r"\bkurv\w*", "cornering"),
    (r"\blandschaft\w*|\bpanorama\w*|\baussicht\w*", "scenery"),
    (r"\bberge?\b|\bbergpanorama\w*", "mountains"),
    (r"\bsonnenuntergang\w*", "sunset"),
    (r"\bfitness\b|\bworkout\w*|\bgym\b", "fitness"),
    (r"\btrainings?\b|\bübung\w*", "exercise"),
)


def _recover_obvious_visual_focus(
    instruction: str, excluded_tags: tuple[str, ...],
) -> tuple[str, ...]:
    """Gängige positive Motive als Fokustags erhalten, falls das Modell versagt.

    Die Wörter werden NUR als Präferenzen interpretiert. Es wird niemals
    behauptet, dass die entsprechenden Szenen im Video vorhanden sind.
    """
    result: list[str] = []
    text = instruction.casefold()
    for pattern, tag in _VISIBLE_FOCUS_PATTERNS:
        if tag in excluded_tags:
            continue
        for match in re.finditer(pattern, text):
            prefix = text[max(0, match.start() - 45):match.start()]
            # Häufige Negationsformen: "keine Kurven", "ohne Motorräder".
            negated = re.search(
                r"\b(?:kein\w*|ohne|nicht|vermeid\w*|no)\s+(?:\w+\s+){0,2}$",
                prefix,
            )
            if not negated and tag not in result:
                result.append(tag)
                break
    return tuple(result)


def _soften_background_requests(
    instruction: str,
    excluded: tuple[str, ...],
    deemphasized: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """'Nicht im Mittelpunkt' ist keine Verbotsanweisung.

    Nur eindeutig erkennbare Begriffe in derselben Satzhälfte umdeuten.
    'Ohne X' und 'keine X' bleiben harte Ausschlüsse.
    """
    excluded_set = set(excluded)
    reduced = list(deemphasized)
    text = instruction.casefold()
    markers = (
        "nicht im mittelpunkt", "nicht im vordergrund",
        "nur im hintergrund", "eher im hintergrund",
    )
    for sentence in re.split(r"[.!?;]", text):
        if not any(marker in sentence for marker in markers):
            continue
        for pattern, tag in _VISIBLE_FOCUS_PATTERNS:
            for mention in re.finditer(pattern, sentence):
                before = sentence[max(0, mention.start() - 35):mention.start()]
                # Ein klarer Ausschluss hat stets Vorrang.
                if re.search(
                    r"\b(?:ohne|kein\w*|niemals)\s+(?:\w+\s+){0,2}$",
                    before,
                ):
                    continue
                if tag in excluded_set:
                    excluded_set.remove(tag)
                if tag not in reduced:
                    reduced.append(tag)
    return tuple(t for t in excluded if t in excluded_set), tuple(reduced)


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
    deemphasized_tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.style not in STYLES:
            raise ValueError("Unbekannter Videoschnitt-Stil.")
        for group in (
            self.focus_tags, self.required_tags,
            self.excluded_tags, self.deemphasized_tags,
        ):
            if any(tag not in VISUAL_TAGS for tag in group):
                raise ValueError("Nicht unterstütztes Ziel-Tag.")
        if set(self.required_tags) & set(self.excluded_tags):
            raise ValueError("Gleichzeitig verlangte und ausgeschlossene Szenen.")
        if set(self.deemphasized_tags) & (set(self.required_tags) | set(self.excluded_tags)):
            raise ValueError("Widerspruch zwischen weicher und harter Motivvorgabe.")
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
        "verlangte Ereignisse oder Motive), excluded_tags (vollständig "
        "auszuschließende Motive: nur bei 'keine', 'ohne', 'niemals'), "
        "deemphasized_tags (Motive, die sichtbar bleiben dürfen, aber "
        "nicht im Mittelpunkt stehen sollen), "
        "uncheckable_requests (nicht mit diesem Tagvokabular überprüfbare "
        "inhaltliche Wünsche, als kurze deutsche Strings). "
        "Nenne bei erkennbaren Motiven immer passende focus_tags; sie "
        "beschreiben Nutzerpräferenzen und behaupten NICHT, dass das Video "
        "diese Motive enthält. Ordne normale Wörter und Umschreibungen "
        "passenden sichtbaren Tags zu. "
        "Setze uncheckable_requests NUR für den Aspekt eines Wunsches, "
        "der an statischen Bildern nicht prüfbar ist, etwa Motorengeräusch, "
        "Geschwindigkeit oder eine exakte Bewegung zwischen zwei Bildern. "
        "Nicht ganze Anweisungen pauschal als ungeprüft markieren, wenn "
        "Motorräder, Kurven oder Landschaften sichtbar sein können. "
        "Beispiel: 'Zeige schöne Berglandschaften, die Motorräder sollen "
        "nicht im Mittelpunkt stehen' -> focus_tags=['scenery','mountains'], "
        "deemphasized_tags=['motorcycle'], excluded_tags=[]. "
        "Nicht im Mittelpunkt bedeutet NIEMALS kompletter Ausschluss. "
        "Beispiel: 'Interessante Motorrad-Durchfahrten und dynamische Kurven, "
        "Motorräder gut sichtbar' -> style='action', "
        "focus_tags=['motorcycle','cornering'], required_tags=[], "
        "uncheckable_requests=['exakter zeitlicher Ablauf der Durchfahrt']. "
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
        focus_tags = _tags(payload, "focus_tags")
        required_tags = _tags(payload, "required_tags")
        excluded_tags = _tags(payload, "excluded_tags")
        deemphasized_tags = _tags(
            {"deemphasized_tags": payload.get("deemphasized_tags", [])},
            "deemphasized_tags",
        )
        excluded_tags, deemphasized_tags = _soften_background_requests(
            instruction, excluded_tags, deemphasized_tags,
        )
        # Weiche Nebenmotive nicht versehentlich positiv hervorheben.
        focus_tags = tuple(t for t in focus_tags if t not in deemphasized_tags)
        # Nur falls das Modell offensichtliche sichtbare Motive als
        # ungeprüft einstuft: deren Bedeutung als weiches Ziel retten.
        # Ausschlüsse und ausdrücklich verlangte Ereignisse werden nie verändert.
        if not focus_tags and not required_tags:
            focus_tags = _recover_obvious_visual_focus(instruction, excluded_tags)

        return EditingGoal(
            original_instruction=instruction,
            style=payload["style"],
            focus_tags=focus_tags,
            required_tags=required_tags,
            excluded_tags=excluded_tags,
            uncheckable_requests=tuple(wishes),
            deemphasized_tags=deemphasized_tags,
        )
    except Exception as exc:
        raise GoalParsingError(
            f"Nutzerabsicht konnte nicht interpretiert werden: {type(exc).__name__}"
        ) from exc
