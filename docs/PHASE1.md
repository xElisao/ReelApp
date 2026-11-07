# VeloCut 2.0 – Phase 1 (Entwicklungsbranch)

**Zweck:** Schrittweise echte Highlight-Erkennung für Motorrad/Action,
Fitness, Reise/Outdoor und allgemeine Videos aufbauen.

Dieser Branch ist **nicht** die produktive Anwendung. Die bisherige
\`app.py\`, \`database.py\` und \`webhook_server.py\` bleiben zunächst unverändert.

## Bereits angelegte Bausteine

- \`video_probe.py\`: liest Quellvideodauer, Auflösung, FPS, Codec und Audio-Vorhandensein per FFprobe.
  Liest **keine Bilder oder Ereignisse** aus dem Video.
- \`highlight_models.py\`: Datenmodell für Highlight-Kandidaten, Bewertungsdimensionen,
  Prüfung von Zeitstempeln, Quellvideos, Überlappungen und Schnittplan-Budget.
  Erkennt **noch keine Highlights**.
- \`tests/test_phase1.py\`: Unit-Tests ohne API-Schlüssel und ohne echtes Video.

## Voraussetzungen und Test

- Python 3.10+.
- FFmpeg inklusive \`ffprobe\` muss für die spätere Verwendung auf dem System installiert sein
  und im PATH liegen.
- Für die Unit-Tests sind keine zusätzlichen Python-Pakete nötig:

\`\`\`bash
python -m unittest discover -s tests -v
\`\`\`

## Nächster Umsetzungsschritt

1. \`scene_detector.py\` entwickelt Szenen/überlappende Zeitfenster aus echten Videos.
2. \`highlight_analyzer.py\` schickt echte Videoinhalte an einen austauschbaren
   multimodalen Anbieter und erhält begründete Highlight-Kandidaten.
3. \`highlight_ranker.py\` wählt die besten Kandidaten nischenabhängig und
   mit überprüften Zeitstempeln aus.
4. Ein annotierter Testdatensatz mit mindestens 3 Videos je Nische und ein Vergleich
   zu bisherigen Baselines zeigen Trefferquote, False Positives, Kosten und Laufzeit.

**Hinweis:** Zeitstempel/Confidence von KI-Modellen sind nicht von sich aus
vertrauenswürdig. Alle Ergebnisse müssen gegen Quellvideodauern geprüft werden;
Confidence-Werte sind ohne Kalibrierung keine echten Wahrscheinlichkeiten.

## Sicherheitsbaustellen vor einem öffentlichen Verkauf

- Login darf nicht nur auf frei eingebbarer E-Mail-Adresse basieren.
- Stripe-Webhook und Streamlit brauchen eine wirklich gemeinsame Datenbank.
- Uploads/Exports unterschiedlicher Nutzer brauchen separate Arbeitsverzeichnisse.
- Das bestehende \`requirements.txt\` ist unvollständig für den Streamlit-Teil;
  Dependency-Versionen und Deployment-Konfiguration müssen getrennt getestet werden.

Plan: https://github.com/xElisao/ReelApp/issues/1
