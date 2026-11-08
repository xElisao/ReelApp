# Phase 10: Reel-Design 1 – Weichgezeichneter Hochkant-Hintergrund

**Stand:** 08.11.2026. Nur Staging-Entwicklungsbranch
`feature/velocut-2-video-analysis`; produktive App auf `main` unverändert.

## Anlass

Der erste reale, technisch bestätigte VeloCut-Reel-Export zeigte beide
Landschaftsaufnahmen korrekt, aber mit großen schwarzen Flächen oben und
unten im 9:16-Hochformat. Der Nutzer stimmte der Empfehlung zu,
zunächst einen **unscharfen Hintergrund** zu entwickeln, damit das
vollständige Panorama sichtbar bleibt und die schwarzen Flächen
ansprechender gefüllt werden. Ein automatischer Crop mit
Motiv-Nachverfolgung ist eine spätere Funktion, nicht Teil dieses Fixes.

## Reel-Export

Im Bereich „🎬 Test-Reel als MP4 erstellen“ kann gewählt werden:

- **Unscharfer Hintergrund (empfohlen, Standard):** Originalclip
  mittig in vollständiger Breite und Höhe darstellen, Hintergrund aus
  demselben Videoframe füllen und deutlich weichzeichnen. Der
  Hintergrund wird leicht abgedunkelt/entsättigt, damit das eigentliche
  scharfe Video im Vordergrund bleibt.
- **Schwarze Balken (klassisch):** Bisheriger FFmpeg-Renderpfad,
  gleicher vollständiger Bildinhalt und alte Darstellung.

Die Option wirkt ausschließlich auf das fertig zusammengesetzte,
stumme Test-Reel. Die Einzelvorschauen und KI-Analyse bleiben unverändert.

**Technik:** FFmpeg `split` erzeugt aus derselben Videospur einen
Hintergrund- und Vordergrundzweig. Hintergrund: `scale=increase`,
`crop=540:960`, `boxblur`, leichte Farbkorrektur.
Vordergrund: `scale=decrease`, vollständiges Originalbild.
Beide Zweige werden mittig überlagert, auf 24fps/H.264 und 540×960
vereinheitlicht und die Szenen als MP4 zusammengefügt.

**Keine zusätzlichen KI-Kosten:** Der Export nimmt die bereits
lokal gerenderten MP4-Vorschauclips und nutzt nur FFmpeg.
**Kein Ton** (wie Export 1). Clips weiterhin 2–3, max. 30 Sekunden.

## Caching

Der bestehende Sitzungs-Cache wird beim Erstellen neuer
Vorschauclips gelöscht. Der Signaturschlüssel des MP4-Exports
berücksichtigt zusätzlich zu Bericht, Clipauswahl und Reihenfolge
jetzt auch den Hintergrundmodus. Wechsel zwischen Blur und Schwarz
zeigt deshalb niemals einen Export der falschen Variante.

## Nachweise

`tests/test_reel_export.py` testet weiterhin echte FFmpeg-H.264-MP4s
aus Quer- und Hochformatmaterial und prüft zusätzlich Bildpixel:

- Im Blur-Standard wird die obere Leinwand-Ecke tatsächlich mit
  Video-Farben gefüllt (kein schwarzer Balken).
- Im expliziten Modus `black` bleibt die Ecke schwarz.
- Unbekannte Modi werden **vor** dem Start von FFmpeg zurückgewiesen.

Das Laufverhalten im geschützten Streamlit-Labor und die visuelle
Ästhetik des Nutzervideos müssen zusätzlich manuell beurteilt werden.

## Manueller Test ohne OpenAI

1. Staging neu starten, Versionszeile **Reel-Design 1 | 2026-11-08** prüfen.
2. Wie bisher 32-Sekunden-Landschaftstestvideo und gespeicherte
   `velocut_32s_ersatz_vorschau.json` im kostenlosen
   Vorschau-Labor verwenden. Kein KI-Analyse-Button.
3. Zwei gültige Clips anzeigen lassen, beim Test-Reel
   „Unscharfer Hintergrund (empfohlen)“ belassen.
4. Clips zu einem Reel verbinden, Video direkt abspielen und
   Download begutachten. Die schwarzen Balken sollen nun durch
   weichgezeichnete Versionen der jeweiligen Landschaft ersetzt sein.
