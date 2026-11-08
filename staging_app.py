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
from preview_clips import PreviewError, pick_suggestions, render_report_previews
from reel_export import ReelExportError, ReelSegment, render_test_reel
from staging_preflight import VideoPreflightError, inspect_videos


LAB_BUILD = "Reel-Design 1 | 2026-11-08"


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


if st.button("🔍 Video prüfen (ohne KI-Kosten)"):
    if not uploads:
        st.error("Bitte zuerst das neue Testvideo hochladen.")
    else:
        try:
            with tempfile.TemporaryDirectory(prefix="velocut_preflight_") as directory:
                video_paths = _write_uploaded_videos(uploads, directory)
                infos = inspect_videos(video_paths)
            st.success("Technische Prüfung bestanden. Noch keine KI-Analyse gestartet.")
            for info in infos:
                st.caption(
                    f"{info.source_id}: {info.duration_seconds:.1f} Sekunden, "
                    f"{info.width} × {info.height} Pixel"
                )
        except VideoPreflightError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(
                "Technische Video-Prüfung fehlgeschlagen "
                f"({type(exc).__name__}). Es wurde keine KI-Analyse gestartet."
            )


def _remember_previews(clips, report_bytes: bytes) -> None:
    """Keep only compressed short clips, never original uploaded videos."""
    identifier = hashlib.sha256(report_bytes).hexdigest()[:16]
    st.session_state["velocut_preview_id"] = identifier
    # Ein alter Export darf nach neuen Vorschaudaten nicht abrufbar bleiben.
    st.session_state.pop("velocut_reel_bytes", None)
    st.session_state.pop("velocut_reel_signature", None)
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
        if result.get("cut_crossing_windows_ignored"):
            st.caption(
                f"Schnittprüfung: {result['cut_crossing_windows_ignored']} "
                "Zeitfenster mit Bildwechsel ausgelassen."
            )
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
        state = {"stage": "Video lokal prüfen", "api_started": False}

        def record_stage(label: str) -> None:
            state["stage"] = label

        with st.spinner("Video wird geprüft und danach nur bei gültigen Daten analysiert ..."):
            try:
                from openai import OpenAI

                preview_warning = None
                with tempfile.TemporaryDirectory(prefix="velocut_staging_") as directory:
                    paths = _write_uploaded_videos(uploads, directory)

                    # Die technischen Grenzen müssen VOR den OpenAI-Aufrufen
                    # überprüft werden, damit keine vermeidbaren Kosten entstehen.
                    infos = inspect_videos(paths)
                    st.caption(
                        "Technisch geprüft: " +
                        ", ".join(
                            f"{item.source_id}: {item.duration_seconds:.1f}s"
                            for item in infos
                        )
                    )

                    state["api_started"] = True
                    report = analyze_files(
                        OpenAI(api_key=api_key, timeout=60.0, max_retries=1),
                        paths,
                        instruction=instruction,
                        category_override=options[category_label],
                        refine=refine,
                        progress=record_stage,
                    )
                    # Den bereits kostenpflichtig erstellten Report unbedingt
                    # vor einem möglichen lokalen Vorschaufehler sichern.
                    history = st.session_state.get("velocut_lab_history", [])
                    history.append({
                        "build": LAB_BUILD,
                        "instruction": instruction,
                        "category": category_label,
                        "refined": refine,
                        "report": report,
                    })
                    st.session_state["velocut_lab_history"] = history[-4:]
                    st.success("Analyse abgeschlossen; Ergebnis ist gespeichert.")

                    if preview_after_analysis:
                        state["stage"] = "Lokale Video-Vorschau"
                        try:
                            clips = render_report_previews(paths, report)
                            expected_preview_count = min(len(pick_suggestions(report)), 3)
                            dropped = expected_preview_count - len(clips)
                            if dropped:
                                st.warning(
                                    f"{dropped} Vorschlag/Vorschläge wegen erkannter "
                                    "harter Bildwechsel mitten im Clip ausgelassen. "
                                    "Die vorhandenen KI-Szenenbeschreibungen werden "
                                    "nicht eigenmächtig auf andere Zeiträume übertragen."
                                )
                            report_bytes = json.dumps(
                                report, sort_keys=True, ensure_ascii=False
                            ).encode("utf-8")
                            _remember_previews(clips, report_bytes)
                        except Exception as exc:
                            # Fehler beim kostenfreien lokalen Rendering
                            # dürfen niemals die Analyseergebnisse verstecken.
                            preview_warning = (
                                "Die KI-Analyse wurde gespeichert, aber "
                                "die lokale Video-Vorschau konnte nicht "
                                f"erstellt werden ({type(exc).__name__})."
                            )
                    else:
                        st.session_state.pop("velocut_preview_clips", None)
                        st.session_state.pop("velocut_preview_id", None)
                        st.session_state.pop("velocut_reel_bytes", None)
                        st.session_state.pop("velocut_reel_signature", None)

                if preview_warning:
                    st.warning(preview_warning)
            except VideoPreflightError as exc:
                st.error("Video-Prüfung: " + str(exc))
                st.info("Es wurden keine OpenAI-Anfragen gestartet.")
            except ValueError as exc:
                reason = str(exc)
                # Nur bekannte, selbst formulierte Limits sicher anzeigen.
                known = (
                    "Prototyp-Limit:",
                    "Zu viele Zeitfenster:",
                    "Video benötigt bis zu ",
                    "Video benötigt",
                    "Nutzeranweisung ist zu lang",
                )
                safe_reason = (
                    reason if reason.startswith(known)
                    else "Bitte die technische Video-Prüfung und den Analyseabschnitt kontrollieren."
                )
                st.error(
                    f"Fehler im Schritt „{state['stage']}“ (ValueError). "
                    f"{safe_reason}"
                )
                if state["api_started"]:
                    st.warning(
                        "Möglicherweise wurden bereits API-Anfragen berechnet. "
                        "Bitte vorerst keine neue Analyse starten."
                    )
            except Exception as exc:
                st.error(
                    f"Fehler im Schritt „{state['stage']}“ "
                    f"({type(exc).__name__}). "
                    "Bitte die Fehlermeldung oder die geschützten Serverlogs prüfen."
                )
                if state["api_started"]:
                    st.warning(
                        "Möglicherweise wurden bereits API-Anfragen berechnet. "
                        "Bitte vorerst keine neue Analyse starten."
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
                skipped = min(len(pick_suggestions(report)), 3) - len(clips)
                if skipped:
                    st.warning(
                        f"{skipped} Vorschlag/Vorschläge wegen erkannter "
                        "harter Bildwechsel mitten im Clip ausgelassen. "
                        "Dafür wird keine neue KI-Analyse benötigt."
                    )
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
    selected_for_reel = []
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
        include_in_reel = st.checkbox(
            f"Szene {index} ins Test-Reel aufnehmen",
            value=True,
            key=f"velocut_reel_clip_{preview_identifier}_{index}",
        )
        if include_in_reel:
            selected_for_reel.append((index, clip))
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

    st.divider()
    st.subheader("🎬 Test-Reel als MP4 erstellen")
    st.caption(
        "Aus 2 bis 3 ausgewählten Vorschauclips entsteht ein gemeinsames "
        "9:16-Hochkantvideo (540 × 960 Pixel). Die ursprünglichen Bilder "
        "bleiben vollständig sichtbar. Ein weichgezeichneter Hintergrund "
        "ersetzt standardmäßig die schwarzen Balken. "
        "Dieser Testexport ist OHNE Ton, Musik, Titel und Übergangseffekte. "
        "Es werden keine neuen OpenAI-Anfragen gesendet."
    )
    reel_order = st.radio(
        "Reihenfolge der Clips im Reel",
        ["Chronologisch", "KI-Rangfolge"],
        horizontal=True,
        key=f"velocut_reel_order_{preview_identifier}",
    )
    reel_background_label = st.radio(
        "Darstellung im Hochformat",
        ["Unscharfer Hintergrund (empfohlen)", "Schwarze Balken (klassisch)"],
        horizontal=True,
        key=f"velocut_reel_background_{preview_identifier}",
        help=(
            "Das Originalbild bleibt in beiden Varianten vollständig sichtbar. "
            "Bei unscharfem Hintergrund wird der freie Raum mit einer "
            "weichgezeichneten Version der Aufnahme gefüllt."
        ),
    )
    reel_background_mode = (
        "blur" if reel_background_label.startswith("Unscharfer") else "black"
    )
    if reel_order == "Chronologisch":
        selected_for_reel.sort(
            key=lambda pair: (
                pair[1]["source_id"], pair[1]["start_seconds"], pair[0]
            )
        )

    selected_numbers = [index for index, _ in selected_for_reel]
    reel_signature = hashlib.sha256(
        json.dumps(
            [preview_identifier, reel_order, reel_background_mode, selected_numbers],
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()
    if len(selected_for_reel) < 2:
        st.info("Für das Test-Reel bitte mindestens zwei Szenen auswählen.")
    else:
        estimated_seconds = sum(
            clip["end_seconds"] - clip["start_seconds"]
            for _, clip in selected_for_reel
        )
        st.caption(
            f"Gewählt: {len(selected_for_reel)} Clips, "
            f"zusammen ungefähr {estimated_seconds:.1f} Sekunden."
        )
    if st.button(
        "🎬 Ausgewählte Clips zu einem Reel verbinden",
        disabled=len(selected_for_reel) < 2,
        key=f"velocut_reel_render_{preview_identifier}",
    ):
        with st.spinner("Die Vorschauclips werden lokal zu einem MP4 zusammengesetzt ..."):
            try:
                segments = [
                    ReelSegment(
                        source_id=clip["source_id"],
                        start_seconds=clip["start_seconds"],
                        end_seconds=clip["end_seconds"],
                        mp4_bytes=clip["mp4_bytes"],
                    )
                    for _, clip in selected_for_reel
                ]
                output = render_test_reel(
                    segments, background_mode=reel_background_mode
                )
                st.session_state["velocut_reel_bytes"] = output
                st.session_state["velocut_reel_signature"] = reel_signature
                st.success(
                    "Test-Reel erstellt. Du kannst es unten ansehen und herunterladen."
                )
            except ReelExportError as exc:
                st.error(f"Reel-Export nicht möglich: {exc}")
            except Exception as exc:
                st.error(
                    "Reel-Export fehlgeschlagen "
                    f"({type(exc).__name__}). Bitte geschützte Serverlogs prüfen."
                )

    if (
        st.session_state.get("velocut_reel_signature") == reel_signature
        and st.session_state.get("velocut_reel_bytes")
    ):
        reel_bytes = st.session_state["velocut_reel_bytes"]
        st.video(reel_bytes, format="video/mp4")
        st.download_button(
            "⬇️ Test-Reel als MP4 herunterladen",
            data=reel_bytes,
            file_name=f"velocut_test_reel_9x16_{reel_background_mode}.mp4",
            mime="video/mp4",
            key=f"velocut_reel_download_{preview_identifier}",
        )
