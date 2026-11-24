# Phase 12: Editor-Fix 1 – Szenen manuell schneiden und anordnen

**Stand:** 08.11.2026. Nur geschützte Staging-App auf
`feature/velocut-2-video-analysis`; `main` / produktive App bleibt unverändert.

## Ziel

Nach einem erfolgreichen E2E-Test von Reel-Export 1, Blur-Design 1
und Audio-Export 1 kann der Nutzer die vorgeschlagenen Highlight-Szenen
**manuell kürzen, verlängern und in eigener Reihenfolge anordnen**.

## Oberfläche

- Unter jedem Vorschauclip gibt es einen aufklappbaren Abschnitt
  **„✂️ Szene X kürzen oder verlängern (optional)“** mit numerischen
  Feldern für **Start- und Endzeit im Originalvideo**.
- Zeitwerte sind in Sekunden einstellbar (Schrittweite 0,25 s,
  Anzeige auf drei Nachkommastellen); exakte KI-Start-/Endwerte
  werden als Standard **ohne unbeabsichtigte Rundung** verwendet.
- Im Reel-Export stehen **Chronologisch**, **KI-Rangfolge**
  oder **Manuell** zur Auswahl. Bei „Manuell“ wird für jede
  Reel-Position ein Szenenwahlfeld angezeigt; Duplikate werden
  als Eingabefehler zurückgewiesen.
- Das fertige MP4 wird nur angezeigt, wenn die Cache-Signatur zur
  tatsächlich gewählten Reihenfolge, zu **allen** Schnittpunkten,
  dem Hintergrundmodus und dem Tonmodus passt.
- Bestehende Optionen: 9:16, Blur oder schwarze Balken, Standard
  stumm oder optionaler Originalton. Maximal 2–3 Szenen pro Reel.

## Technische Umsetzung

- `manual_editor.py` prüft zuerst Intervallgrenzen, Mindestlänge
  von 0,25 s, Höchstlänge von 10 s, Gesamtzeit und Überlappungen
  aus derselben Videoquelle.
- **Unveränderte Clips** verwenden die bereits im Session-Speicher
  liegenden MP4-Vorschauen. Kein Originalupload und keine lokale
  Neuberechnung erforderlich.
- Für **geänderte Schnitte** verwendet das Testlabor das exakt
  gleiche hochgeladene Originalvideo (SHA-256-Abgleich der
  Upload-Dateien gegenüber dem Preview-Erstellungszeitpunkt).
  Unser Editor speichert **keine zusätzliche dauerhafte Kopie**
  der Originaldatei. Die Streamlit-Dateiupload-Komponente kann
  hochgeladene Medien jedoch während der Sitzung im Speicher halten;
  für das lokale Bearbeiten wird nur kurz eine temporäre Datei erzeugt.
- Der lokale FFmpeg-Schnittdetektor `shot_boundaries.py` wird
  für geänderte Videos erneut ausgeführt. Wenn der gewählte
  Clip einen erkannten **harten Bildwechsel im Inneren** enthält,
  wird der Export mit verständlicher Fehlermeldung blockiert.
  Bei Fehlern der Schnittprüfung wird kein neuer Clip erstellt.
- Die neu gerenderten Vorschau-MP4s werden an den vorhandenen
  `render_test_reel`-Export übergeben. Bestehende Audio-
  und Hintergrundoptionen bleiben erhalten.
- Der Editor analysiert **keine** neuen Bilder bei OpenAI:
  ausschließlich lokale FFmpeg- und Python-Verarbeitung.
- Hinweis: Die KI-Beschreibung eines Vorschlagclips kann nach
  einer deutlichen manuellen Verschiebung nicht mehr stimmen.
  Harte-Schnitt-Erkennung ist eine Heuristik, keine Garantie für
  weiche Blenden oder alle extrem schnellen Bewegungswechsel.

## Tests und Nachweise

`tests/test_manual_editor.py` prüft:
- Wiederverwendung unveränderter MP4s ohne Originaldateien;
- geänderte Schnitte/Verlängerungen aus einem Originalvideo;
- Ablehnung bei harten Bildwechseln;
- Sperre, wenn die lokale Schnittprüfung scheitert;
- Ablehnung ungültiger Längen, NaN, Bool, Quellen, Überschneidungen
  und Schnitte hinter dem Originalvideo-Ende;
- echte FFmpeg-Montage: Ein 8-s-Video mit rotem und grünem Shot
  wird lokal an neuen Zeiten auf zwei Clips (3,0 s und 2,5 s)
  geschnitten und zu einem ca. 5,5-s-Hochkantvideo exportiert.

GitHub Actions setzt die Offline-Tests unter Python 3.11
mit FFmpeg sowie die Staging-Abhängigkeitschecks unter Python 3.12
und 3.13 um.

## Manueller Test ohne KI-Kosten

1. Geschütztes Labor neu starten und
   **„Editor-Fix 1 | 2026-11-08“** sehen.
2. 32-s-Landschafts-Testclip plus gespeicherte passende
   Ersatz-JSON in den **kostenfreien Vorschau-Bereich** laden.
3. Wieder zwei gültige Vorschauclips erzeugen.
4. Bei Szene 1 „✂️ ...“ öffnen und z.B. nur **Ende von
   13,50 auf 14,00 Sekunden** ändern. Szene 2 unverändert lassen.
   Das liegt voraussichtlich innerhalb des Shots 8–18 s.
5. Beim Reel-Export „Manuell“ wählen und Szene 2 vor Szene 1
   setzen; Ton und Blur nach Wunsch beibehalten.
6. „Ausgewählte Clips zu einem Reel verbinden“ klicken:
   fertiges MP4 mit manuell gekürzter/verlängerter Szene und
   veränderter Reihenfolge prüfen. Dauer wäre mit obigen Zeiten
   voraussichtlich ca. 6,5 Sekunden.
7. Negativtest: keine weitere KI-Analyse, aber einen Ausschnitt
   über einen erkannten harten Cut (z.B. 22,5–25,5 s) einstellen.
   Der neue Export sollte blockiert werden.

**Live-End-to-End-Sichtprüfung steht noch aus.**
