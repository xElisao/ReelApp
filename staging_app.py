"""Separate, passwortgeschützte VeloCut-2.0-Testoberfläche.

NICHT die produktive app.py; kein Stripe-Login und keine öffentliche Paywall.
Die Anwendung muss separat bereitgestellt werden. Ohne konfigurierte
STAGING_ACCESS_PASSWORD und OPENAI_API_KEY startet kein Testzugang.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import tempfile
from pathlib import Path

import streamlit as st

from prototype_intent import analyze_files
from preview_clips import PreviewError, render_report_previews


LAB_BUILD = "Diversity-Fix 1 | 2026-11-07"


st.set_page_config(
    page_title="VeloCut 2.0 | KI-Labor",
    page_icon="🎬",
    layout="wide",
)


def _secret(key: str) -> str:
    """Keine Secrets, Fehlermeldungen oder Default-Keys ins UI ausgeben."""
    try:
        value = st.secrets.get(key, "")
    except (KeyError, FileNotFoundError):
        return ""
    return value if isinstance(value, str) else ""


def _authenticated(password: str, expected: str) -> bool:
    """Timing-robuster Vergleich, ohne Klartextkennwort irgendwo zu loggen."""
    return hmac.compare_digest(
        hashlib.sha256(password.encode("utf-8")).digest(),
        hashlib.sha256(expected.encode("utf-8")).digest(),
    )


st.title("🎬 VeloCut 2.0 – KI-Labor")
st.caption("Separater Testbereich für echte Video-Inhaltsanalyse und Nutzerwünsche.")
st.caption(f"Testversion: {LAB_BUILD}")

access_password = _secret("STAGING_ACCESS_PASSWORD")
api_key = _secret("OPENAI_API_KEY")

if len(access_password) < 16:
    st.error(
        "Testbereich gesperrt: Es fehlt ein starkes "
        "STAGING_ACCESS_PASSWORD (mindestens 16 Zeichen) in den App-Secrets."
    )
    st.stop()

if not st.session_state.get("velocut_lab_authenticated", False):
    st.info("Dieser Entwicklungsbereich ist passwortgeschützt und nicht öffentlich freigeschaltet.")
    entered = st.text_input("Entwickler-Zugangspasswort", type="password")
    if st.button("Testbereich öffnen"):
        if _authenticated(entered, access_password):
            st.session_state["velocut_lab_authenticated"] = True
            st.rerun()
        else:
            st.error("Zugang verweigert.")
    st.stop()

if st.sidebar.button("Abmelden"):
    st.session_state.clear()
    st.rerun()

if not api_key:
    st.error("OPENAI_API_KEY ist für diese Testinstanz noch nicht konfiguriert.")
    st.stop()

st.info(
    "Entwicklungsversion: Es werden derzeit nur Einzelbilder, keine durchgehenden "
    "Bewegungen oder Tonspuren analysiert. Zeitfenster sind noch keine exakten Schnitte."
)
st.warning(
    "Nur Videos verwenden, deren Verarbeitung durch den externen KI-Anbieter "
    "erlaubt ist. Beim Start werden verkleinerte Bilder an die OpenAI-API gesendet. "
    "Jede Auswertung verursacht möglicherweise API-Kosten."
)

uploads = st.file_uploader(
    "1 bis 3 Testvideos hochladen (je maximal 60 Sekunden)",
    type=["mp4", "mov", "m4v", "avi"],
    accept_multiple_files=True,
)
instruction = st.text_area(
    "Was soll das Reel zeigen?",
    value="Zeige die spannendsten Momente",
    help="Beispiele: Zeig die besten Kurven; Zeig schöne Bergpanoramen",
)
options = {
    "Automatisch bestimmen": None,
    "Motorrad / Action": "motorcycle_action",
    "Fitness": "fitness",
    "Reise / Outdoor": "travel_outdoor",
    "Allgemein": "general",
}
category_label = st.selectbox(
    "Erkannte Kategorie bei Bedarf überschreiben", list(options)
)
refine = st.checkbox("Interessante Stellen genauer untersuchen", value=True)
preview_after_analysis = st.checkbox(
    "Abspielbare Vorschau nach der Analyse erstellen",
    value=True,
    help="Kurze MP4-Vorschauen werden lokal erstellt. Dafür fallen keine "
         "zusätzlichen KI-API-Aufrufe an.",
)


def _write_uploaded_videos(uploaded, directory: str) -> list[Path]:
    if not uploaded or len(uploaded) > 3:
        raise ValueError("Bitte 1 bis 3 Originalvideos hochladen.")
    if (
        any(item.size > 80 * 1024 * 1024 for item in uploaded)
        or sum(item.size for item in uploaded) > 160 * 1024 * 1024
    ):
        raise ValueError("Maximal 80 MB pro Video und 160 MB insgesamt.")
    result = []
    for index, item in enumerate(uploaded, 1):
        suffix = Path(item.name).suffix.lower()
        if suffix not in {".mp4", ".mov", ".m4v", ".avi"}:
            raise ValueError("Nicht erlaubtes Upload-Format.")
        path = Path(directory) / f"video_{index}{suffix}"
        path.write_bytes(item.getbuffer())
        result.append(path)
    return result


def _remember_previews(clips, report_bytes: bytes) -> None:
    """Keep only compressed short clips, never original uploaded videos."""
    identifier = hashlib.sha256(report_bytes).hexdigest()[:16]
    st.session_state["velocut_preview_id"] = identifier
    st.session_state["velocut_preview_clips"] = [
        {
            "source_id": clip.source_id,
            "start_seconds": clip.start_seconds,
            "end_seconds": clip.end_seconds,
            "score": clip.score,
            "summary": clip.summary,
            "mp4_bytes": clip.mp4_bytes,
            "similar_view_as": clip.similar_view_as,
        }
        for clip in clips
    ]


def _display(report: dict, *, show_refined: bool, download_key: str) -> None:
    st.subheader("Ergebnis dieser Analyse")
    st.caption(
        "Erkannt: " + (", ".join(report.get("detected_categories", [])) or "Unklar")
    )
    # Sichtbar machen, wie der freie Nutzerwunsch verstanden wurde.
    goal = report.get("goal") or {}
    tag_names = {
        "motorcycle": "Motorräder", "cornering": "Kurven",
        "scenery": "Landschaften", "mountains": "Berge",
        "sunset": "Sonnenuntergang", "fitness": "Fitness",
        "exercise": "Übungen", "vehicles": "Fahrzeuge",
        "wheelie": "Wheelie",
    }
    focus = goal.get("focus_tags") or []
    if focus:
        st.markdown(
            "**Verstandenes Ziel:** " +
            ", ".join(tag_names.get(tag, tag) for tag in focus)
        )
    elif goal.get("uncheckable_requests"):
        st.caption("Keine sicher aus Bildern prüfbare Zielvorgabe abgeleitet.")
    less_important = goal.get("deemphasized_tags") or []
    excluded = goal.get("excluded_tags") or []
    if less_important:
        st.caption(
            "Nur Nebenmotiv (nicht verboten): " +
            ", ".join(tag_names.get(tag, tag) for tag in less_important)
        )
    if excluded:
        st.caption(
            "Ausgeschlossen: " +
            ", ".join(tag_names.get(tag, tag) for tag in excluded)
        )
    result = report.get("refinement") if show_refined and "refinement" in report else None
    if result:
        st.caption(f"Detailprüfung: {result['inspected_windows']} weitere Zeitfenster")
        if result.get("notice"):
            st.info(result["notice"])
        rows = result.get("suggestions", [])
    else:
        if report.get("notice"):
            st.info(str(report["notice"]))
        rows = report.get("recommendations", [])

    if not rows:
        st.warning(
            "Keine passend nachgewiesenen Szenen. Bitte einen anderen Wunsch "
            "ausprobieren oder eine genauere Analyse durchführen."
        )
    else:
        for index, item in enumerate(rows, 1):
            st.markdown(
                f"**{index}. {item['summary']}** · "
                f"{item['source_id']} · "
                f"{item['start_seconds']:.2f}–{item['end_seconds']:.2f}s · "
                f"Bewertung {item['score']:.1f}/100"
            )
            st.caption(item["reason"])
    st.download_button(
        "JSON-Ergebnis herunterladen",
        data=json.dumps(report, indent=2, ensure_ascii=False).encode("utf-8"),
        file_name="velocut_analysis.json",
        mime="application/json",
        key=f"download_{download_key}",
    )


if st.button("🤖 Inhalt und Wunsch analysieren", type="primary"):
    if not uploads or len(uploads) > 3:
        st.error("Bitte 1 bis 3 Videos hochladen.")
    elif len(instruction) > 1000:
        st.error("Nutzerwunsch ist zu lang (max. 1000 Zeichen).")
    elif any(item.size > 80 * 1024 * 1024 for item in uploads) or sum(item.size for item in uploads) > 160 * 1024 * 1024:
        st.error("Maximal 80 MB pro Video und 160 MB insgesamt für die Testinstanz.")
    else:
        with st.spinner("Video-Inhalte werden analysiert – externe API-Aufrufe laufen ..."):
            try:
                # Import erst hier: Wenn Secrets fehlen, keine API initialisieren.
                from openai import OpenAI

                preview_warning = None
                with tempfile.TemporaryDirectory(prefix="velocut_staging_") as directory:
                    paths = _write_uploaded_videos(uploads, directory)
                    report = analyze_files(
                        OpenAI(api_key=api_key, timeout=60.0, max_retries=1),
                        paths,
                        instruction=instruction,
                        category_override=options[category_label],
                        refine=refine,
                    )
                    if preview_after_analysis:
                        try:
                            clips = render_report_previews(paths, report)
                            report_bytes = json.dumps(
                                report, sort_keys=True, ensure_ascii=False
                            ).encode("utf-8")
                            _remember_previews(clips, report_bytes)
                        except PreviewError:
                            preview_warning = (
                                "Die KI-Analyse war erfolgreich, aber die "
                                "Video-Vorschau konnte nicht gerendert werden."
                            )
                    else:
                        st.session_state.pop("velocut_preview_clips", None)
                        st.session_state.pop("velocut_preview_id", None)

                history = st.session_state.get("velocut_lab_history", [])
                history.append({
                    "build": LAB_BUILD,
                    "instruction": instruction,
                    "category": category_label,
                    "refined": refine,
                    "report": report,
                })
                st.session_state["velocut_lab_history"] = history[-4:]
                st.success("Analyse abgeschlossen. Prüfe die Ergebnisse unten.")
                if preview_warning:
                    st.warning(preview_warning)
            except Exception as exc:
                # Keine internen Fehlermeldungen mit möglichen Pfaden/Details veröffentlichen.
                st.error(
                    "Die Analyse konnte nicht abgeschlossen werden "
                    f"({type(exc).__name__}). Prüfe Upload, Limits und "
                    "Serverlogs der geschützten Testinstanz."
                )

history = st.session_state.get("velocut_lab_history", [])
if history:
    st.divider()
    st.subheader("Analysen vergleichen")
    st.caption(
        "Die letzten bis zu vier Auswertungen bleiben nur innerhalb dieser "
        "Streamlit-Sitzung zum Vergleich sichtbar."
    )
    for index, entry in enumerate(reversed(history)):
        caption = f"{entry['instruction'] or '(ohne Vorgabe)'} · {entry['category']}"
        with st.expander(caption, expanded=(index == 0)):
            if entry.get("build") != LAB_BUILD:
                st.warning(
                    "Dies ist ein gespeichertes Ergebnis einer früheren "
                    "Testversion. Bitte die Analyse neu starten, um die "
                    "korrigierte Wunsch-Erkennung zu prüfen."
                )
            _display(
                entry["report"], show_refined=entry["refined"],
                download_key=str(index),
            )


st.divider()
st.subheader("🎞️ Szenen-Vorschau ohne neue KI-Analyse")
st.caption(
    "Du hast schon eine JSON-Auswertung? Lade dasselbe Originalvideo oben "
    "noch einmal hoch und wähle hier die gespeicherte JSON-Datei. "
    "Die Vorschau verwendet ausschließlich FFmpeg, keine OpenAI-API."
)
saved_report = st.file_uploader(
    "Vorhandenes Analyseergebnis hochladen (.json oder .txt)",
    type=["json", "txt"],
    key="velocut_import_report",
)
same_video_confirmed = st.checkbox(
    "Ich verwende genau dieselben Originalvideos wie bei der Analyse "
    "(bei mehreren Dateien in derselben Reihenfolge).",
    key="velocut_same_video_confirmed",
)

if st.button("🎞️ Vorschau aus gespeichertem Ergebnis erstellen", type="secondary"):
    if not uploads:
        st.error("Bitte zuerst das zugehörige Originalvideo oben hochladen.")
    elif saved_report is None:
        st.error("Bitte das gespeicherte JSON-Analyseergebnis auswählen.")
    elif not same_video_confirmed:
        st.error("Bitte bestätigen, dass die Originalvideos zur Analyse gehören.")
    elif saved_report.size > 1024 * 1024:
        st.error("Die JSON-Datei darf maximal 1 MB groß sein.")
    else:
        with st.spinner("Aus den bereits erkannten Zeiten werden kurze MP4-Clips erstellt ..."):
            try:
                report_bytes = saved_report.getvalue()
                report = json.loads(report_bytes.decode("utf-8-sig"))
                if not isinstance(report, dict) or not report.get("mode"):
                    raise PreviewError("Dies ist kein VeloCut-Analysebericht.")
                with tempfile.TemporaryDirectory(prefix="velocut_preview_") as directory:
                    paths = _write_uploaded_videos(uploads, directory)
                    clips = render_report_previews(paths, report)
                _remember_previews(clips, report_bytes)
                if clips:
                    st.success(
                        f"{len(clips)} Vorschauclip(s) erstellt. "
                        "Du kannst sie jetzt direkt ansehen und bewerten."
                    )
                else:
                    st.warning("Die JSON-Analyse enthält keine ausgewählten Highlights.")
            except (ValueError, PreviewError, UnicodeError, json.JSONDecodeError) as exc:
                st.error(
                    f"Vorschau nicht möglich: {exc}"
                )
            except Exception as exc:
                st.error(
                    "Die Vorschau konnte nicht erstellt werden "
                    f"({type(exc).__name__}). Bitte Streamlit-Protokolle prüfen."
                )

clips_to_show = st.session_state.get("velocut_preview_clips", [])
preview_identifier = st.session_state.get("velocut_preview_id", "")
if clips_to_show:
    st.subheader("Deine abspielbaren Highlight-Vorschläge")
    st.caption(
        "Die Vorschau zeigt genau die ausgewählten Zeitfenster, noch "
        "keine finalen Schnitte. Bewertungen bleiben in dieser Sitzung."
    )
    grades = []
    for index, clip in enumerate(clips_to_show, 1):
        st.markdown(
            f"**Szene {index}: {clip['summary']}**  "
            f"({clip['source_id']}, "
            f"{clip['start_seconds']:.2f}–{clip['end_seconds']:.2f}s)"
        )
        st.video(clip["mp4_bytes"], format="video/mp4")
        if clip.get("similar_view_as") is not None:
            st.info(
                f"Vermutlich dieselbe Kameraperspektive wie Szene "
                f"{clip['similar_view_as']}. Für ein Landschafts-Reel "
                "könnte diese Ansicht eine Wiederholung sein. "
                "Bei Action kann es trotzdem ein eigener guter Moment sein."
            )
        grade = st.radio(
            f"Wie gut passt Szene {index} zu deinem Wunsch?",
            ["Noch nicht bewertet", "Gut", "Nicht gut"],
            horizontal=True,
            key=f"velocut_grade_{preview_identifier}_{index}",
        )
        grades.append({
            "source_id": clip["source_id"],
            "start_seconds": clip["start_seconds"],
            "end_seconds": clip["end_seconds"],
            "ai_score": clip["score"],
            "user_rating": grade,
            "similar_view_as": clip.get("similar_view_as"),
        })
    feedback = {
        "report_sha256_prefix": preview_identifier,
        "rating_type": "human_review_of_ai_previews",
        "ratings": grades,
        "note": "Subjektive Benutzerbewertung. Kein Beweis für korrekte KI-Erkennung.",
    }
    st.download_button(
        "Meine Szenenbewertungen herunterladen (JSON)",
        data=json.dumps(feedback, ensure_ascii=False, indent=2).encode("utf-8"),
        file_name="velocut_szenen_feedback.json",
        mime="application/json",
        key="velocut_feedback_download",
    )
