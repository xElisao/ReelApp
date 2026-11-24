# Phase 14: Preview-Fix 1 – abspielbare Vorschau des bearbeiteten Einzelclips

**Stand:** 08.11.2026. Geschütztes Streamlit-Staging auf
`feature/velocut-2-video-analysis`. Die produktive `main`-App bleibt unverändert.

## Ziel

Der Nutzer kann schon vor dem gesamten 9:16-Reel-Export sehen, ob die
manuell ausgewählte Szene tatsächlich an den neu eingestellten
Start-/Endpunkten geschnitten wurde.

## Oberfläche

1. Im bisherigen ✂️-Expander der Szene auf **„🎞️ Vorschaubilder … laden“**
   klicken und die zwei Slidergriffe anpassen. (Alternativ funktionieren
   die bisherigen Sekundeneingabefelder weiterhin.)
2. Auf **„▶️ Bearbeitete Szene X als Vorschau erstellen“** klicken.
3. Unter dem Button erscheint ein Videoplayer **mit dem wirklich
   ausgeschnittenen Originalausschnitt**, seiner Länge und optional dem
   vorhandenen Originalton. Der Player oberhalb des Editors bleibt als
   Vergleich mit dem ursprünglichen KI-Vorschlag erhalten.
4. Bei späteren Änderungen der Schnittpunkte oder Originaluploads
   wird eine alte Einzelvorschau ausgeblendet. Der Button kann den
   aktuellen Ausschnitt erneut prüfen und rendern.
5. Der Button **startet nie eine OpenAI-/KI-Analyse** und muss nicht
   für jede Szene gedrückt werden. Beim normalen Reel-Export gelten
   weiterhin direkt die aktuell eingestellten Start-/Endpunkte.

## Technik und Sicherheit

- Neue API in `manual_editor.py`:
  `validate_single_edit(edit)`,
  `render_single_scene_preview(edit, original_path=None)`.
- Diese Funktion verwendet denselben lokalen FFmpeg-Schnitt-Helper
  **`_render_checked_edit`** wie
  `prepare_edited_segments` für den endgültigen Export.
  So können Vorschau und Export nicht versehentlich unterschiedliche
  Prüfregeln für harte Bildwechsel bekommen.
- Vor lokalem Rendern der neuen Szene verifiziert `staging_app.py`
  SHA-256 der hochgeladenen Originalvideos gegenüber dem Zeitpunkt
  des ursprünglichen Vorschau-Imports.
- Bei geändertem Schnitt: `ffprobe` prüft echte Dateidauer,
  `detect_hard_cuts` blockiert erkannte harte Szenenwechsel, FFmpeg
  kodiert den Ausschnitt als kurzen H.264-MP4-Clip. Bei ausfallender
  Bildwechselprüfung wird **nicht** ungesichert exportiert.
- Bei unverändertem Schnitt kann der bereits gerenderte MP4-Clip
  ohne zusätzliche FFmpeg-Arbeit abgespielt werden.
- Der Streamlit-Sitzungsspeicher enthält nur den jeweils zuletzt
  gerenderten Szenenclip und eine SHA-256-Signatur über
  Vorschau-ID, Szenennummer und aktuell gewählte Schnittzeiten;
  Originaldateien werden ausschließlich im temporären
  Renderverzeichnis gespeichert und sofort wieder entfernt.
- Bei neuem JSON-/Video-Vorschau-Import werden alle bisherigen
  Szenenclip-Vorschauen gelöscht. Nach einer Zeitänderung wird
  der alte Player ausgeblendet, bevor ein weiterer Klick erfolgt.
- Kein automatisches Starten von Verarbeitung bei Slider-Bewegung,
  keine neuen AI-Kosten.

## Grenzen

- Die Einzelvorschau ist ein leichtes MP4 aus dem **Originalvideo**
  und zeigt **noch nicht** den finalen Blur-/Schwarz-Hochformat-Look.
  Der wird erst beim Reel-Export angewendet.
- Die Vorschau kann **Originalton** enthalten. Für die fertige MP4
  bleibt die separate Tonwahl „Ohne Ton“ / „Originalton übernehmen“
  zuständig.
- Keine sekundengenaue Garantie für unerkannte **weiche** Blenden.
- Das MP4 wird nach Klick neu erstellt, nicht bei jedem Ziehen
  des Reglers in Echtzeit.

## Tests

`tests/test_manual_editor.py`: neue Tests für die ungeänderte
Vorschau (kein FFmpeg), geänderte Zeitspanne, identische Hard-Cut-Regeln,
Fehlschlag der Schnittprüfung, fehlendes Original, nicht zulässige
Längen, fehlende MP4-Kennung, FFmpeg-Fehler und **echte** lokale
FFmpeg-Erzeugung aus einem synthetischen 8-s-Rot/Grün-Video. Dazu
bestehende Offline- und Reel-Integrationstests.

## Manueller Streamlit-Test (noch ausstehend)

1. Geschützte Test-App neu starten. Build:
   **`Preview-Fix 1 | 2026-11-08`**.
2. Das bekannte 32-s-Landschaftsvideo und die dazugehörige
   `velocut_32s_ersatz_vorschau.json` im **kostenfreien**
   Vorschau-Import verwenden, **keine KI-Analyse starten**.
3. Unter Szene 1 die Zeitleiste öffnen und Ende mit rechtem
   Griff von **13,50 auf 14,00 s** verlängern.
4. Unter dem Regler auf
   **„▶️ Bearbeitete Szene 1 als Vorschau erstellen“** klicken.
5. Den zusätzlichen Player abspielen: Die Bergstraße sollte jetzt
   etwa **3,5 Sekunden** laufen.
6. Optional anderen Endpunkt wählen: Ein **alter** Vorschauplayer
   darf nicht als aktuelles Ergebnis sichtbar bleiben.
7. Reel-Export separat durchführen und mit der Einzelvorschau
   vergleichen. Original-Blur-Tonoptionen bleiben unverändert.
