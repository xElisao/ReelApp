# Phase 13: Timeline-Fix 1 – visuelle Schnitt-Zeitleiste

**Stand:** 08.11.2026. Nur geschütztes Staging:
`feature/velocut-2-video-analysis`. Produktive `main`-App unverändert.

## Motivation

Die manuellen Sekundenfelder aus Editor-Fix 1 funktionieren und wurden mit
einem echten, ca. 6,46 Sekunden langen Reel getestet. Nutzer möchten jetzt
eine **Bild-Zeitleiste mit verschiebbaren Anfangs-/Endpunkten**, damit
keine Sekundenwerte mehr manuell getippt werden müssen.

## Neue Oberfläche

Unter jedem einzeln abspielbaren Highlight befindet sich:
**„✂️ Szene X – Zeitleiste und Schnittpunkte“**.

- Der Button **„🎞️ Vorschaubilder für Szene X laden (ohne KI)“**
  erstellt einen Filmstreifen aus **sieben kleinen Bildern des Originalvideos**
  (Originalzeitpunkte unter jedem Bild).
- Der angezeigte Bereich liegt **vier Sekunden vor** und **vier Sekunden
  nach** dem KI-Vorschlag, begrenzt durch Anfang/Ende des Originalvideos.
  So lässt sich der vorgeschlagene Shot anpassen, ohne durch einen
  60-Sekunden-Schieber millimeterkleine 3-Sekunden-Bereiche zu ziehen.
- Direkt unter dem Filmstreifen: ein **Bereichs-Schieberegler mit zwei
  Griffen** für Start und Ende, in Schritten von **0,01 Sekunden**.
  Der Abschnitt wird sofort als Zeit und Dauer angezeigt.
- Original-KI-Zeitpunkte, die mehr als zwei Nachkommastellen enthalten,
  bleiben bei noch nicht betätigtem Schieber **präzise erhalten**.
  Das verhindert unnötiges Rendern oder minimale Verschiebungen.
- Vor dem Laden des Filmstreifens funktionieren die bisherigen exakten
  Sekundeneingabefelder als Fallback. Falls lokale Thumbnail-Erzeugung
  fehlschlägt, bleibt der Editor nutzbar.
- Reel-Export und manuelle Reihenfolge, Background Blur und optionaler
  Originalton bleiben unverändert. **Eine geschnittene Szene wird erst
  beim Reel-Export gerendert**; der Einzelplayer darüber zeigt weiterhin
  den KI-Ausgangsclip.

## Technik

Neue Datei: `timeline_frames.py`.

- FFmpeg extrahiert auf ausdrücklichen Button-Klick kleine Bilder aus
  den temporär hochgeladenen Originaldateien, kein OpenAI-Aufruf.
- Pillow setzt die Frames zu einem einzigen JPEG-Filmstreifen zusammen.
  **Maximal sieben Frames (je 150×84 px)** plus Zeitzeile, Ausgabe
  maximal 800 kB.
- Temporäre Originaldateien werden nach der Erzeugung geschlossen.
  Der Session-Speicher erhält **nur den JPEG-Streifen und seine
  Zeitgrenzen**, keine zusätzliche Kopie der Originalvideos.
  Die Streamlit-Upload-Komponente hält hochgeladene Dateien während
  der Nutzung eventuell weiterhin im Speicher.
- Zeitbereich wird anhand echter Video-Metadaten per ffprobe begrenzt.
- Vor dem Laden des Storyboards werden die Uploads per SHA-256 mit den
  Dateien der KI-Vorschau verglichen. Stale Filmstreifen und Slider-State
  werden beim Laden eines neuen Vorschau-Berichts entfernt.
- Bisheriger `manual_editor.py` validiert **weiterhin beim Export**
  Mindest-/Maximaldauer, Überlappungen und harte Schnitte innerhalb
  eines manuell gesetzten Ausschnitts. Eine Erkennung sämtlicher
  Blenden oder fehlerfreier framegenauer Grenzen wird nicht behauptet.

## Automatische Tests

`tests/test_timeline_frames.py` testet:

- korrekte Begrenzung an Beginn/Ende eines kurzen Originalvideos;
- zeitlich sortierte Frame-Proben in der sichtbaren Zeitleiste;
- Beibehaltung alter KI-Zeitpunkte trotz visueller 0,01-s-Rundung;
- absichtlich verlängerten/kürzeren Clip nach Slider-Eingabe;
- Ablehnung ungültiger Zeitwerte und fehlendem FFmpeg;
- **echte lokale FFmpeg-Frame-Erzeugung** mit 8-s-Rot/Grün-Montage
  (erstes Bild rot, letztes grün) und 2-s-Kurzvideo nahe Dateiende.

Im CI werden `timeline_frames.py` und `staging_app.py` kompiliert,
Unit-Tests mit FFmpeg durchgeführt und die Staging-Abhängigkeiten
unter Python 3.12/3.13 installiert.

## Manueller Test ohne neue KI-Kosten

1. Geschützte Streamlit-App neu starten und Versionslabel
   **`Timeline-Fix 1 | 2026-11-08`** prüfen.
2. 32-s-Landschaftsvideo und zugehörige gespeicherte
   Ersatz-JSON im Bereich **„Szenen-Vorschau ohne neue KI-Analyse“**
   verwenden; **nicht** den Analyse-Button klicken.
3. Zwei gültige Szenen anzeigen lassen.
4. Unter Szene 1 den Bereich „✂️ ... Zeitleiste“ aufklappen und
   **„🎞️ Vorschaubilder ... laden“** klicken.
5. Die sieben mit Sekundenangaben beschrifteten Frames sollten
   um die Gebirgsstraßen-Szene erscheinen.
6. Den rechten Griff des Schiebereglers von **13,50 s auf
   14,00 s** ziehen. Den linken bei 10,50 s lassen.
7. Reel wie zuvor aus Szene 1 und 2 erstellen, wahlweise
   manuell umgeordnete Reihenfolge, anschließend das MP4
   auf korrekte Laufzeit und Bildfolge prüfen.
8. Es darf **keine OpenAI-Analyse** ausgelöst werden.

**Browser-Praxistest steht noch aus.**
