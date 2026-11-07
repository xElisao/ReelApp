# VeloCut 2.0: Erster visueller Highlight-Prototyp

Der Code liegt **ausschließlich auf dem Entwicklungsbranch**, nicht auf \`main\`.
Die laufende Streamlit-App und der Stripe-Webhook sind nicht verändert.

## Was neu ist

- \`candidate_windows.py\`: Überlappende 8-Sekunden-Fenster mit 6 Sekunden Abstand,
  einschließlich des Video-Endes. Keine echte Szenenwechsel-Erkennung.
- \`frame_sampler.py\`: FFmpeg extrahiert 3 JPEG-Bilder je Fenster.
- \`highlight_analyzer.py\`: OpenAI Vision erhält die **echten extrahierten Bilder**
  und liefert eine begründete Bewertung, je nach Nische.
- \`prototype_analyze.py\`: Eigenständiger manueller CLI-Test und optionaler JSON-Export.
- \`tests/test_visual_prototype.py\`: Tests mit simulierten FFmpeg-/API-Antworten.

## Einschränkungen

- **Noch kein Videoschnitt und keine Streamlit-Integration.**
- Statische Videoframes zeigen keine Bewegung zwischen den Bildern.
- Ton, gesprochene Sprache und Musik werden noch nicht analysiert.
- Es wird über das gesamte Video gesampelt, aber kurze Ereignisse können verpasst werden.
- Zeitstempel beziehen sich auf **Zeitfenster**, noch nicht auf exakte Highlights innerhalb dieser Fenster.
- Die "variety"-Bewertung ist derzeit absichtlich neutral (3/5), bis
  Quellvideo-übergreifendes Ranking vorhanden ist.
- Bilder werden zur Analyse an den konfigurierten OpenAI-API-Dienst gesendet.
  Nur Material verarbeiten, das für diese Datenübertragung freigegeben ist.
- \`gpt-4o-mini\` ist hier der erste vergleichbare Basis-Anbieter und nicht
  automatisch die endgültige Modellwahl. Modelle/Preise/Qualität messen.
- Prototyp-Limit: maximal **60 Sekunden pro Video** und maximal 12 Zeitfenster.
  Dies verhindert unbemerkte Teilanalysen und begrenzt API-Ausgaben.
- **Kein stummer Fallback** bei Fehlern: Fehler sollen sichtbar sein.

## Testen

Python >= 3.10 und FFmpeg/ffprobe im PATH:

\`\`\`bash
python -m pip install -r requirements-prototype.txt
python -m unittest discover -s tests -v
export OPENAI_API_KEY="DEIN_SCHLUESSEL_NUR_LOKAL"
python prototype_analyze.py beispiel.mp4 --niche travel_outdoor --output highlights.json
\`\`\`

Unter Windows den Key über die Umgebungsvariablen/Powershell setzen.
**API-Schlüssel und Videos niemals in GitHub committen.**

Das Script analysiert ein echtes Video und zeigt Zeitfenster mit Beschreibungen
und Bewertungen. Das ist der nächste notwendige Praxistest, aber noch kein
automatisch geschnittenes fertiges Reel.

## Weiterer Pfad

1. Automatisierte Regressionstests und mit realen Testclips validieren.
2. Menschlich annotierte Highlights mit Top-K-Vorschlägen vergleichen.
3. Zweite Videoanalyse via Gemini (direktes Video mit Audio) evaluieren.
4. Bei schnellen Szenen adaptives dichteres Sampling und präzisere Zeitgrenzen.
5. Globales Ranking + Schnittplan + Vorschau, erst danach Integration in Streamlit.

Aktuelle Dokumentation:
- https://developers.openai.com/api/docs/guides/images-vision
- https://ai.google.dev/gemini-api/docs/video-understanding
