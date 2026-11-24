# VeloCut 2.0 – Erkennen → Nutzerwunsch verstehen → passend auswählen

## Status

**Forschungs-/Entwicklungsprototyp** auf \`feature/velocut-2-video-analysis\`.
Kein Merge auf \`main\`, keine Streamlit-Integration, kein fertiger Reel-Export.

Neu:
1. \`content_understanding.py\`: Multilabel-Kategorien und sichtbare Tags
   je Zeitfenster aus **echten extrahierten Videobildern**. Ohne Audiospur.
2. \`user_goals.py\`: natürliche Beschreibung als Stil, Fokus, zwingend
   gewünschte/ausgeschlossene Motive und nicht prüfbare Wünsche strukturiert.
3. \`intent_ranking.py\`: Szenen werden abhängig vom Ziel priorisiert;
   unbelegte Pflichtmotive, ungeprüfte Anforderungen und Überlappungen
   werden nicht als erfolgreiche Treffer ausgegeben.
4. \`prototype_intent.py\`: Pipeline zur manuellen Ausführung mit 1–3 Videos.

## Lokal testen

Erforderlich: Python 3.10+, FFmpeg/FFprobe und OpenAI-Python-Paket:

\`\`\`bash
python -m pip install -r requirements-prototype.txt
python -m unittest discover -s tests -v
export OPENAI_API_KEY="..."
python prototype_intent.py motorrad.mp4 --instruction "Zeig die schönsten Bergpanoramen" --output scenic.json
python prototype_intent.py motorrad.mp4 --instruction "Zeig interessante Kurven" --output action.json
\`\`\`

Für eine manuelle Vorgabe:
\`\`\`bash
python prototype_intent.py motorrad.mp4 --category travel_outdoor --instruction "Schöne Landschaften"
\`\`\`

Gleicher Video-Input, andere Ziele, andere Reihenfolge/Vorauswahl bei passenden Bildbelegen.
Nicht vorhandene Pflichtmotive (z. B. \`wheelie\`) müssen klar als unbestätigt
gemeldet werden. Ohne ausreichenden visuellen Beleg kein erfundener Ersatz.

**Datenschutz:** API-Schlüssel in Umgebungsvariablen speichern, niemals ins Repo;
Videos niemals in GitHub committen. Die extrahierten Einzelbilder werden an
die externe OpenAI-API gesendet. Nur freigegebenes Material analysieren.

## Grenzen / offene Arbeiten

- Höchstens 3 Dateien, je höchstens 60 Sekunden, insgesamt 24 Fenster.
- Nur drei Einzelbilder aus jedem überlappenden 8-Sekunden-Fenster:
  **kurze Ereignisse und Geschwindigkeiten sind nicht verlässlich erkennbar**.
- Die Wörter werden durch ein Modell in ein begrenztes Tag-Vokabular
  übersetzt; Interpretationsfehler sind möglich.
- Kategorien sind Vorschläge, keine gesicherten Klassifikationen.
- Bei strikten/unprüfbaren Wünschen signalisiert die Pipeline
  Nicht-Erfüllbarkeit, statt unbelegte Szenen zu erfinden.
- Stile/Bewertungsgewichte sind vorläufig, noch nicht empirisch kalibriert.
- Keine exakten Schnittpunkte, Transkription, Tonanalyse, dynamisches
  zweites Sampling, Videoexport, Streamlit-UI, Echtzeitprogress oder Kauf-Login.
- Kein Live-Vergleich mit der Bild-/Audioanalyse oder mit dem alten VeloCut
  aus den drei hochgeladenen Testvideos, solange keine API-Auswertung erfolgt.
- GitHub Unit-Tests nutzen simulierte KI-Antworten und verifizieren
  Logik/Fehlerbehandlung, **nicht die Erkennungsqualität**.

## Nächster Test

Für dasselbe echte Motorrad-Rohvideo die Wünsche
"Kurven/Action" vs. "Landschaft/Berge" vergleichen und manuell annotierte
Highlights als Messlatte nutzen. Falls die entsprechenden Ereignisse in den
wenigen Frame-Stichproben nicht erkennbar sind, adaptives Sampling implementieren.

Plan: https://github.com/xElisao/ReelApp/issues/1
