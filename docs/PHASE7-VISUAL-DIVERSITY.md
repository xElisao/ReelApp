# Phase 7: Ähnliche Kameraansichten zusammenfassen

**Status:** Staging-Branch, `Diversity-Fix 1 | 2026-11-07`. Produktive
`app.py` auf `main` ist unverändert.

## Erkenntnis aus dem Praxistest

Zwei von der KI für schöne Landschaften ausgewählte Videofenster zeigten
dieselbe statische Kameraperspektive auf eine kurvige Steinbrücke.
Die Motorräder fuhren nur zu unterschiedlichen Zeitpunkten durchs Bild.
Beide Beschreibungen waren plausibel, aber es sind nicht zwei
unterschiedliche Landschaftsbilder.

Im Nutzer-JSON lauteten die Vorschläge:
- 4,376–7,376 s, Score 72,38/100.
- 0,000–3,000 s, Score 68,18/100.

Alle zehn Detailfenster enthielten laut KI lediglich die Tags
`motorcycle`, `cornering` und `scenery`. Obwohl „Berge“ im Nutzerwunsch
vorkam, gab es keinen nachgewiesenen Tag `mountains`.

## Neue Logik

- `visual_diversity.py` bildet pro Zeitfenster **zwei 64-Bit-Bild-Hashes**
  aus jeweils drei aus dem Video bereits extrahierten Standbildern.
  Unterschiedliche Zeitfenster werden nur dann als vermutlich dieselbe
  Kameraperspektive eingestuft, wenn mindestens zwei Drittel der
  Stichproben in *beiden Richtungen* ähnlich sind.
- Bei `style=scenic` vermeidet der Ranking-Algorithmus weitere Vorschläge
  aus sehr wahrscheinlich derselben Ansicht. Die besten Zeitfenster bleiben
  erhalten. Die gewählte Anzahl und ein erklärender Hinweis werden im
  JSON dokumentiert.
- Bei `style=action` darf dieselbe Kameraansicht mehrere zeitlich
  getrennte gute Fahrmomente enthalten.
- Fehlende gewünschte Fokus-Tags (z. B. `mountains`) werden als
  **nicht nachgewiesen** im Hinweis genannt, nicht erfunden.
- Die **alte JSON-Datei** kann weiterhin im Vorschau-Labor wiedergegeben
  werden. Beim Erstellen der Vorschau wird rein lokal geprüft, ob zwei
  Vorschläge vermutlich dieselbe Kameraansicht haben. In diesem Fall
  bleibt das zweite Video abspielbar, wird aber gekennzeichnet.

## Kein zusätzlicher KI-Aufruf für den Bildvergleich

Der Vergleich nutzt Pillow und FFmpeg und vorhandene Originalvideos.
Wird ein **alter Analysebericht** hochgeladen, genügt es, das Originalvideo
wie bisher im Preview-Lab bereitzustellen. Für den lokalen Bildvergleich
fallen **keine OpenAI-API-Gebühren** an.

**Wichtig:** Perzeptuelle Hashes sind keine zuverlässige Kamera-Tracking-
oder Szenenwechsel-Erkennung. Unterschiedliche Bilder können ähnlich
erscheinen, und dasselbe Motiv kann bei Kamerabewegung als verschieden
gelten. Deshalb nennt die UI die Ergebnisse ausdrücklich
„vermutlich dieselbe Kameraperspektive“. Bei fehlenden Bildinformationen
werden Szenen nicht allein aufgrund ähnlicher Textbeschreibungen
zusammengefasst.

## Relevante Tests

`tests/test_visual_diversity.py` testet synthetische
Bilder mit bewegten kleinen Vordergrundobjekten und unterschiedlichen
Hintergründen sowie das Verhalten für Landschaft vs. Action.
`tests/test_preview_clips.py` testet den lokalen
Ähnlichkeitshinweis für alte JSON-Berichte und die Action-Ausnahme.
