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
from manual_editor import (
    ClipEdit, EditorError, prepare_edited_segments,
    render_single_scene_preview, validate_manual_edits, validate_single_edit,
)
from scene_preview_state import (
    expire_scene_preview, read_current_scene_preview,
    scene_signature, store_scene_preview,
)
from timeline_frames import (
    TimelineError, render_storyboard, selected_slider_interval, timeline_bounds,
)
from video_probe import VideoProbeError, probe_video
from reel_export import (
    ReelExportError, ReelSegment, expected_reel_duration, render_test_reel,
)
from staging_preflight import VideoPreflightError, inspect_videos


LAB_BUILD = "Transition-Fix 3 | 2026-11-13"


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


def _uploads_still_match_preview(uploaded) -> bool:
    """Eine lokal gerenderte Vorschau darf nicht aus fremden Uploads stammen."""
    expected = st.session_state.get("velocut_preview_source_hashes")
    return bool(
        uploaded and expected
        and tuple(
            hashlib.sha256(item.getbuffer()).hexdigest()
            for item in uploaded
        ) == tuple(expected)
    )


def _scene_cut_changed(preview_key: str) -> None:
    """Slider- oder Zahlenfeld-Änderung räumt alte Einzelvorschau sofort ab."""
    expire_scene_preview(st.session_state, preview_key)


def _remember_previews(clips, report_bytes: bytes, uploaded) -> None:
    """Nur komprimierte Clips und Upload-Hashwerte, niemals Originaldateien sichern."""
    source_hashes = tuple(
        hashlib.sha256(item.getbuffer()).hexdigest() for item in uploaded
    )
    identifier = hashlib.sha256(
        report_bytes + ("|".join(source_hashes)).encode("ascii")
    ).hexdigest()[:16]
    st.session_state["velocut_preview_id"] = identifier
    st.session_state["velocut_preview_source_hashes"] = source_hashes
    # Alte Filmstreifen zu anderen Uploads nicht unnötig im Speicher halten.
    for key in list(st.session_state):
        if (
            key.startswith("velocut_storyboard_")
            or key.startswith("velocut_timeline_slider_")
            or key.startswith("velocut_scene_cut_preview_")
        ):
            st.session_state.pop(key, None)
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
                            _remember_previews(clips, report_bytes, uploads)
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
                        st.session_state.pop("velocut_preview_source_hashes", None)
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
                _remember_previews(clips, report_bytes, uploads)
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
    edited_ranges = {}
    for index, clip in enumerate(clips_to_show, 1):
        st.markdown(
            f"**Szene {index}: {clip['summary']}**  "
            f"({clip['source_id']}, "
            f"{clip['start_seconds']:.2f}–{clip['end_seconds']:.2f}s)"
        )
        st.caption(
            f"Original-KI-Vorschau · Szene {index} · "
            f"{clip['end_seconds'] - clip['start_seconds']:.2f} Sekunden "
            "(bleibt unverändert)"
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
        with st.expander(f"✂️ Szene {index} – Zeitleiste und Schnittpunkte"):
            scene_preview_key = (
                f"velocut_scene_cut_preview_{preview_identifier}_{index}"
            )
            st.caption(
                f"KI-Vorschlag: {clip['start_seconds']:.2f}–"
                f"{clip['end_seconds']:.2f} Sekunden. "
                "Wähle Start und Ende per Schieberegler (0,01 s Schritte). "
                "Vorschaubilder zeigen den Bereich um die vorgeschlagene Szene. "
                "Die Vorschau oben zeigt den ursprünglichen KI-Ausschnitt. "
                "Darunter kannst du deinen veränderten Ausschnitt einzeln "
                "abspielen, bevor du das Reel exportierst."
            )
            storyboard_key = f"velocut_storyboard_{preview_identifier}_{index}"
            board = st.session_state.get(storyboard_key)
            if board is None and st.button(
                f"🎞️ Vorschaubilder für Szene {index} laden (ohne KI)",
                key=f"velocut_load_storyboard_{preview_identifier}_{index}",
            ):
                old_hashes = st.session_state.get("velocut_preview_source_hashes")
                matching_uploads = (
                    uploads and old_hashes
                    and tuple(
                        hashlib.sha256(item.getbuffer()).hexdigest()
                        for item in uploads
                    ) == tuple(old_hashes)
                )
                if not matching_uploads:
                    st.error(
                        "Bitte dieselben Originalvideos wie bei dieser Vorschau "
                        "hochladen und die Vorschau gegebenenfalls neu erstellen."
                    )
                else:
                    try:
                        with st.spinner(
                            "Sieben kleine Filmframes werden lokal erzeugt ..."
                        ):
                            with tempfile.TemporaryDirectory(
                                prefix="velocut_storyboard_"
                            ) as directory:
                                originals = _write_uploaded_videos(
                                    uploads, directory
                                )
                                source_number = int(
                                    clip["source_id"].removeprefix("video-")
                                )
                                if not 1 <= source_number <= len(originals):
                                    raise TimelineError(
                                        "Quellvideo ist nicht vorhanden."
                                    )
                                source_path = originals[source_number - 1]
                                metadata = probe_video(
                                    source_path, source_id=clip["source_id"]
                                )
                                low, high = timeline_bounds(
                                    clip["start_seconds"], clip["end_seconds"],
                                    metadata.duration_seconds,
                                )
                                image_bytes = render_storyboard(
                                    source_path, low=low, high=high,
                                    duration_seconds=metadata.duration_seconds,
                                )
                        board = {
                            "low": low, "high": high, "jpeg": image_bytes,
                        }
                        st.session_state[storyboard_key] = board
                    except (TimelineError, VideoProbeError, ValueError) as exc:
                        st.warning(f"Zeitleiste nicht verfügbar: {exc}")
                    except Exception as exc:
                        st.warning(
                            "Zeitleiste konnte nicht erstellt werden "
                            f"({type(exc).__name__}). "
                            "Die genaue Sekundeneingabe bleibt möglich."
                        )
            if board is not None:
                st.image(
                    board["jpeg"],
                    caption=(
                        "Filmstreifen aus dem Originalvideo. "
                        "Die Zeitangaben gelten im Originalvideo."
                    ),
                    use_container_width=True,
                )
                initial = (
                    max(board["low"], min(
                        board["high"], round(clip["start_seconds"], 2)
                    )),
                    max(board["low"], min(
                        board["high"], round(clip["end_seconds"], 2)
                    )),
                )
                chosen = st.slider(
                    f"Szene {index}: Anfang und Ende verschieben",
                    min_value=float(board["low"]),
                    max_value=float(board["high"]),
                    value=initial,
                    step=0.01,
                    format="%.2f s",
                    key=f"velocut_timeline_slider_{preview_identifier}_{index}",
                    on_change=_scene_cut_changed,
                    args=(scene_preview_key,),
                    help=(
                        "Ziehe die beiden Griffe unter den Bildern. "
                        "Maximal 10 Sekunden Länge. Harte Bildwechsel "
                        "werden beim Export noch einmal geprüft."
                    ),
                )
                edited_start, edited_end = selected_slider_interval(
                    chosen,
                    (clip["start_seconds"], clip["end_seconds"]),
                )
                st.caption(
                    f"Gewählter Ausschnitt: {edited_start:.2f}–"
                    f"{edited_end:.2f}s "
                    f"({edited_end - edited_start:.2f}s)."
                )
            else:
                st.caption(
                    "Für die Bild-Zeitleiste oben auf „Vorschaubilder laden“ "
                    "klicken. Bis dahin sind die bisherigen Sekundenfelder verfügbar."
                )
                start_col, end_col = st.columns(2)
                edited_start = start_col.number_input(
                    f"Szene {index}: Start (Sekunden)",
                    min_value=0.0, max_value=60.05, step=0.25,
                    value=float(clip["start_seconds"]),
                    format="%.3f",
                    key=f"velocut_edit_start_{preview_identifier}_{index}",
                    on_change=_scene_cut_changed,
                    args=(scene_preview_key,),
                )
                edited_end = end_col.number_input(
                    f"Szene {index}: Ende (Sekunden)",
                    min_value=0.0, max_value=60.05, step=0.25,
                    value=float(clip["end_seconds"]),
                    format="%.3f",
                    key=f"velocut_edit_end_{preview_identifier}_{index}",
                    on_change=_scene_cut_changed,
                    args=(scene_preview_key,),
                )
            edited_ranges[index] = (edited_start, edited_end)
            scene_edit = ClipEdit(
                source_id=clip["source_id"],
                start_seconds=edited_start,
                end_seconds=edited_end,
                suggested_start=clip["start_seconds"],
                suggested_end=clip["end_seconds"],
                mp4_bytes=clip["mp4_bytes"],
            )
            scene_preview_signature = scene_signature(
                preview_identifier, index, clip["source_id"],
                edited_start, edited_end,
            )
            saved_scene_preview = read_current_scene_preview(
                st.session_state, scene_preview_key,
                scene_preview_signature,
                uploads_match=_uploads_still_match_preview(uploads),
            )
            if st.session_state.get(f"{scene_preview_key}_outdated"):
                st.warning(
                    "Die vorherige bearbeitete Schnittvorschau ist nicht "
                    "mehr aktuell und wurde entfernt. Der Videoplayer "
                    "OBERHALB dieses ✂️-Editors zeigt weiterhin den "
                    "ursprünglichen KI-Ausschnitt. Klicke unten auf "
                    "„Bearbeitete Szene als Vorschau erstellen“, um "
                    "den neuen Ausschnitt zu sehen."
                )

            scene_preview_error = None
            try:
                validate_single_edit(scene_edit)
            except EditorError as exc:
                scene_preview_error = str(exc)
                st.warning(f"Einzelvorschau noch nicht möglich: {exc}")
            st.caption(
                "Die Schnittvorschau verwendet nur FFmpeg, ohne KI-Kosten. "
                "Sie zeigt den gewählten Ausschnitt mit vorhandenem "
                "Originalton. Der endgültige Reel-Ton wird weiter unten gewählt."
            )
            if st.button(
                f"▶️ Bearbeitete Szene {index} als Vorschau erstellen",
                key=f"velocut_make_scene_preview_{preview_identifier}_{index}",
                disabled=scene_preview_error is not None,
            ):
                try:
                    if not _uploads_still_match_preview(uploads):
                        raise EditorError(
                            "Bitte dieselben Originalvideos wie bei der "
                            "Vorschauerstellung hochladen. Die Dateien "
                            "wurden entfernt oder ausgetauscht."
                        )
                    with st.spinner(
                        "Der einzelne Ausschnitt wird lokal gerendert ..."
                    ):
                        if scene_edit.changed:
                            with tempfile.TemporaryDirectory(
                                prefix="velocut_single_scene_"
                            ) as directory:
                                originals = _write_uploaded_videos(
                                    uploads, directory
                                )
                                source_id = scene_edit.source_id
                                if not source_id.startswith("video-"):
                                    raise EditorError(
                                        "Ungültige Originalvideo-Quelle."
                                    )
                                try:
                                    source_number = int(source_id[6:])
                                except ValueError as exc:
                                    raise EditorError(
                                        "Ungültige Originalvideo-Quelle."
                                    ) from exc
                                if not 1 <= source_number <= len(originals):
                                    raise EditorError(
                                        "Originalvideo nicht verfügbar."
                                    )
                                single_bytes = render_single_scene_preview(
                                    scene_edit, originals[source_number - 1]
                                )
                        else:
                            single_bytes = render_single_scene_preview(scene_edit)
                    store_scene_preview(
                        st.session_state, scene_preview_key,
                        scene_preview_signature, single_bytes,
                    )
                    saved_scene_preview = st.session_state[scene_preview_key]
                    st.success(
                        "Bearbeitete Szene bereit. "
                        "Sieh dir unten den tatsächlichen Schnitt an."
                    )
                except EditorError as exc:
                    st.error(f"Schnittvorschau nicht möglich: {exc}")
                except Exception as exc:
                    st.error(
                        "Einzelvorschau fehlgeschlagen "
                        f"({type(exc).__name__}). "
                        "Bitte geschützte Serverlogs prüfen."
                    )
            if saved_scene_preview is not None:
                st.markdown(
                    f"**✅ Aktuelle BEARBEITETE Schnittvorschau "
                    f"für Szene {index} · "
                    f"{edited_end - edited_start:.2f} Sekunden**"
                )
                st.video(
                    saved_scene_preview["mp4_bytes"],
                    format="video/mp4",
                )
                st.caption(
                    f"Das ist der bearbeitete Ausschnitt "
                    f"({edited_end - edited_start:.2f} Sekunden). "
                    "Er wird nicht automatisch in das Reel übernommen; "
                    "deine aktuellen Schnittwerte gelten beim Reel-Export."
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

    st.divider()
    st.subheader("🎬 Test-Reel als MP4 erstellen")
    st.caption(
        "Du kannst Szenen oben über ✂️ und die Bild-Zeitleiste kürzen "
        "oder verlängern, sie einzeln abspielen und unten ihre Reihenfolge "
        "festlegen. Geänderte Clips werden beim Reel-Export aus dem "
        "gleichen Originalvideo neu ausgeschnitten. "
        "Die KI-Beschreibungen beziehen sich auf die ursprünglichen Vorschläge. "
        "Aus 2 bis 3 ausgewählten Szenen entsteht ein gemeinsames "
        "9:16-Hochkantvideo (540 × 960 Pixel). Die ursprünglichen Bilder "
        "bleiben vollständig sichtbar. Ein weichgezeichneter Hintergrund "
        "ersetzt standardmäßig die schwarzen Balken. "
        "Ohne Ton ist die Standardeinstellung; vorhandener Originalton "
        "kann beim Export ausdrücklich eingeschaltet werden. "
        "Optional verbinden weiche Überblendungen von 0,25 bis 1 Sekunde "
        "die Szenen. Keine zusätzliche KI-Analyse, Spracherkennung "
        "oder Musikeinblendung."
    )
    reel_order = st.radio(
        "Reihenfolge der Clips im Reel",
        ["Chronologisch", "KI-Rangfolge", "Manuell"],
        horizontal=True,
        key=f"velocut_reel_order_{preview_identifier}",
    )
    reel_transition_label = st.radio(
        "Übergang zwischen den Szenen",
        ["Direkter Schnitt (Standard)", "Weiche Überblendung"],
        horizontal=True,
        key=f"velocut_reel_transition_{preview_identifier}",
        help=(
            "Direkter Schnitt: Szenen wechseln sofort. "
            "Weiche Überblendung: Die letzten Bilder einer Szene "
            "werden mit dem Anfang der nächsten Szene überlagert. "
            "Es sind 0,25, 0,5 oder 1 Sekunde möglich, ohne KI-Kosten."
        ),
    )
    reel_transition_mode = (
        "fade" if reel_transition_label.startswith("Weiche") else "cut"
    )
    reel_fade_duration = 0.5
    if reel_transition_mode == "fade":
        reel_fade_duration = st.selectbox(
            "Dauer der weichen Überblendung",
            options=[0.25, 0.5, 1.0],
            index=1,
            format_func=lambda value: (
                f"{value:.2f}".replace(".", ",") + " Sekunden"
            ),
            key=f"velocut_reel_fade_duration_{preview_identifier}",
            help=(
                "0,25 s = kurzer Übergang, 0,5 s = Standard, "
                "1,0 s = langsamer Übergang. "
                "Jede ausgewählte Szene muss mindestens doppelt "
                "so lang wie die Überblendung sein."
            ),
        )
        st.caption(
            f"Jede Szene muss mindestens {2 * reel_fade_duration:.2f} "
            "Sekunden dauern. Die beiden Szenen überlappen sich beim "
            "Übergang; das Reel wird entsprechend kürzer."
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
    reel_audio_label = st.radio(
        "Ton im fertigen Reel",
        ["Ohne Ton (Standard)", "Originalton übernehmen"],
        horizontal=True,
        key=f"velocut_reel_audio_{preview_identifier}",
        help=(
            "Nur der bereits vorhandene Originalton der ausgewählten Clips "
            "wird übernommen. Es findet keine Sprachanalyse statt. "
            "Clips ohne Ton bleiben still."
        ),
    )
    reel_audio_mode = (
        "original" if reel_audio_label.startswith("Originalton") else "mute"
    )
    if reel_audio_mode == "original":
        st.caption(
            "Hinweis: Der Originalton kann Stimmen, Gespräche oder Musik "
            "enthalten. Diese Testfunktion bitte zunächst nur mit "
            "eigenen oder freigegebenen Aufnahmen verwenden."
        )
    order_valid = True
    if reel_order == "Chronologisch":
        selected_for_reel.sort(
            key=lambda pair: (
                pair[1]["source_id"], edited_ranges[pair[0]][0], pair[0]
            )
        )
    elif reel_order == "Manuell" and selected_for_reel:
        st.caption(
            "Manuelle Reihenfolge: Wähle für jede Position eine andere Szene."
        )
        selectable = [number for number, _ in selected_for_reel]
        choices = []
        order_cols = st.columns(len(selectable))
        for position, column in enumerate(order_cols, 1):
            with column:
                choice = st.selectbox(
                    f"Position {position}",
                    options=selectable,
                    index=position - 1,
                    format_func=lambda number: f"Szene {number}",
                    key=f"velocut_manual_order_{preview_identifier}_{position}",
                )
                choices.append(choice)
        if len(set(choices)) != len(choices):
            order_valid = False
            st.error(
                "Eine Szene wurde mehrfach ausgewählt. "
                "Bitte jede Szene genau einmal in die Reihenfolge setzen."
            )
        else:
            selection_by_number = dict(selected_for_reel)
            selected_for_reel = [
                (number, selection_by_number[number]) for number in choices
            ]

    edits_for_reel = [
        ClipEdit(
            source_id=clip["source_id"],
            start_seconds=edited_ranges[number][0],
            end_seconds=edited_ranges[number][1],
            suggested_start=clip["start_seconds"],
            suggested_end=clip["end_seconds"],
            mp4_bytes=clip["mp4_bytes"],
        )
        for number, clip in selected_for_reel
    ]
    edit_error = None
    if len(edits_for_reel) >= 2:
        try:
            validate_manual_edits(edits_for_reel)
            preview_segments = [
                ReelSegment(
                    source_id=edit.source_id,
                    start_seconds=edit.start_seconds,
                    end_seconds=edit.end_seconds,
                    mp4_bytes=edit.mp4_bytes,
                )
                for edit in edits_for_reel
            ]
            estimated_seconds = expected_reel_duration(
                preview_segments,
                transition_mode=reel_transition_mode,
                fade_duration_seconds=reel_fade_duration,
            )
        except (EditorError, ReelExportError) as exc:
            edit_error = str(exc)
            st.error(f"Schnittauswahl korrigieren: {exc}")

    selected_edits_signature = [
        (
            number, round(edit.start_seconds, 4),
            round(edit.end_seconds, 4),
        )
        for (number, _), edit in zip(selected_for_reel, edits_for_reel)
    ]
    reel_signature = hashlib.sha256(
        json.dumps(
            [
                preview_identifier, reel_order, reel_background_mode,
                reel_audio_mode, reel_transition_mode,
                reel_fade_duration, selected_edits_signature,
            ],
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()
    if len(selected_for_reel) < 2:
        st.info("Für das Test-Reel bitte mindestens zwei Szenen auswählen.")
    elif not edit_error and order_valid:
        st.caption(
            f"Gewählt: {len(selected_for_reel)} Clips, "
            f"Reel mit {reel_transition_label.lower()} "
            f"{f'({reel_fade_duration:.2f} s)' if reel_transition_mode == 'fade' else ''} "
            f"ungefähr {estimated_seconds:.2f} Sekunden lang."
        )
        if any(edit.changed for edit in edits_for_reel):
            st.caption(
                "Geänderte Ausschnitte werden ohne KI-Aufruf aus den "
                "ursprünglichen Uploads neu gerendert. Eine unerkannte "
                "weiche Blende ist weiterhin möglich."
            )

    if st.button(
        "🎬 Ausgewählte Clips zu einem Reel verbinden",
        disabled=(
            len(selected_for_reel) < 2 or not order_valid
            or edit_error is not None
        ),
        key=f"velocut_reel_render_{preview_identifier}",
    ):
        with st.spinner("Die ausgewählten Szenen werden lokal zu einem MP4 zusammengesetzt ..."):
            try:
                if any(edit.changed for edit in edits_for_reel):
                    if not _uploads_still_match_preview(uploads):
                        raise EditorError(
                            "Die Originalvideos wurden seit der Vorschau "
                            "ausgetauscht oder entfernt. Für neue Schnitte "
                            "bitte die Vorschau mit den passenden Uploads "
                            "nochmals erstellen."
                        )
                    with tempfile.TemporaryDirectory(
                        prefix="velocut_edit_"
                    ) as directory:
                        original_paths = _write_uploaded_videos(
                            uploads, directory
                        )
                        segments = prepare_edited_segments(
                            edits_for_reel, original_paths
                        )
                else:
                    segments = prepare_edited_segments(edits_for_reel)
                output = render_test_reel(
                    segments,
                    background_mode=reel_background_mode,
                    audio_mode=reel_audio_mode,
                    transition_mode=reel_transition_mode,
                    fade_duration_seconds=reel_fade_duration,
                )
                st.session_state["velocut_reel_bytes"] = output
                st.session_state["velocut_reel_signature"] = reel_signature
                st.success(
                    "Test-Reel erstellt. Du kannst es unten ansehen und herunterladen."
                )
            except (ReelExportError, EditorError) as exc:
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
            file_name=(
                f"velocut_test_reel_9x16_{reel_background_mode}_"
                f"{reel_audio_mode}_{reel_transition_mode}"
                f"{f'_{int(reel_fade_duration * 100):03d}cs' if reel_transition_mode == 'fade' else ''}.mp4"
            ),
            mime="video/mp4",
            key=f"velocut_reel_download_{preview_identifier}",
        )
