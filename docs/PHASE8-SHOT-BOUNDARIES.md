# Shot-Fix 1: Bildwechsel innerhalb von KI-Highlights vermeiden

**Feedback aus realem Test, 07.11.2026.** Nutzer beobachtete in
Szene 3 (22,50–25,50s) des 32-s-Landschaftstestvideos einen Sprung von
Landschaft zu Motorradvideo. Die Montage enthielt harte Schnitte bei
ungefähr 8, 18 und 24 Sekunden. Der Vorschlag (7,50–10,50s) kann
ebenfalls den Schnitt bei 8 Sekunden überqueren, ist aber vom Nutzer
noch nicht visuell bestätigt.

## Vorgehen

- `shot_boundaries.py`: FFmpeg erkennt auffällige Änderungen im
  Videobild mit dem Szenenwechsel-Score `scene > 0.18` nach lokaler
  Verkleinerung auf 320 Pixel Breite. Es fallen **keine zusätzlichen
  OpenAI-Aufrufe** für diese Erkennung an.
- In der **neuen Analyse mit Detailmodus** werden 3-Sekunden-Fenster,
  die einen erkannten harten Schnitt **deutlich innerhalb** des
  Fensters enthalten, vor der KI-Detailanfrage ausgelassen. Keine
  fehlerhafte Übernahme der Beschreibungen zwischen zwei Aufnahmen.
  Die Zahl ausgelassener Fenster erscheint im Bericht.
- **Alte Analyse-JSONs** können weiterhin im Preview-Labor verwendet
  werden. Das Originalvideo wird auf harte Schnitte geprüft;
  Vorschläge, die einen nachweisbaren harten Schnitt in der Mitte
  enthalten, werden **nicht als MP4-Vorschau gerendert**.
  Die restlichen Clips bleiben verfügbar und es wird ein Hinweis
  angezeigt. Die Analyse wird nicht erneut kostenpflichtig gestartet.

## Bewusste Grenzen

Die FFmpeg-Heuristik findet harte Cuts, aber nicht garantiert
alle Blenden, Schwenks oder sehr schnelle Bildwechsel.
Bei schnellem Kameraschwenk kann sie eine falsche Schnittgrenze
vermuten; bei subtilen Cuts kann sie einen übersehen.
Die Videoausgabe kann weiterhin unpassende Inhalte enthalten.
Coarse-Fenster können Cuts umfassen, weil sie nur der groben
inhaltlichen Orientierung dienen. Die Fein-KI-Analyse wird bei
erkannten Cuts vorsichtiger.

## Verifikation

Im vorhandenen 32-Sekunden-Testvideo liefert die lokale
FFmpeg-Filterkette bei Schwelle `0.18` die erwarteten Zeitpunkte
`8`, `18` und `24` Sekunden.
`tests/test_shot_boundaries.py` enthält reale synthetische
Video-Cuts (bei installiertem FFmpeg) und reine Zeitfenstertests.
`tests/test_preview_clips.py` sichert das Auslassen alter
Mischclips ab; `tests/test_adaptive_refinement.py` stellt sicher,
dass erkannte Mischfenster keine Detail-KI-Aufrufe bekommen.

Die alte Produktions-App auf `main` ist unverändert.
