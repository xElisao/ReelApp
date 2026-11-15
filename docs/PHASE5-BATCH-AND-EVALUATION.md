# VeloCut 2.0 – Batch-Extraktion und messbare Highlight-Qualität

**Status:** Entwicklungsbranch `feature/velocut-2-video-analysis`, noch nicht in der produktiven Streamlit-App.

## Neu programmiert

1. `batch_frames.py`: Alle Standbilder eines Quellvideos werden **einmal pro Upload** mit FFmpeg extrahiert (Standard: 2 Bilder/Sekunde, größte Bildseite 640 Pixel). Das System prüft Speicher-/Frame-/Laufzeitlimits; die temporären JPEG-Dateien werden automatisch entfernt.
2. `prototype_intent.py`: Grobscan und optionale Detailprüfung verwenden nun denselben FrameCache, statt für jedes Zeitfenster neue FFmpeg-Prozesse zu starten.
3. `adaptive_refinement.py`: Nach dem Grobscan wählt die Detailprüfung aus dem Cache mehr Bildbeispiele pro 3-Sekunden-Fenster.
4. `evaluate_recommendations.py`: Verifiziert Vorschläge gegen manuell markierte Referenzzeitfenster. Ausgabe: zeitliche IoU, Precision@K, Recall@K, F1@K. Treffer werden **eins-zu-eins** zugeordnet.
5. Offline-Tests: `tests/test_batch_frames.py` inkl. synthetischem FFmpeg-Testclip und `tests/test_evaluation.py`.

## Lokal reproduzieren

```bash
python -m pip install -r requirements-prototype.txt
python -m unittest discover -s tests -v
# Einen OpenAI API-Key nur lokal als Umgebungsvariable setzen.
python prototype_intent.py video.mp4 --instruction "Zeige die besten Kurven" --refine --output result_action.json
python prototype_intent.py video.mp4 --instruction "Zeige die schönsten Landschaften" --refine --output result_scenic.json
```

Für jede Nutzervorgabe Referenzpassagen **selbst** markieren. Als Vorlage dient `evaluation/annotations.example.json`. Die Quellvideo-ID von `video-1` entspricht dem ersten übergebenen Video und muss mit dem Ergebnis übereinstimmen.

```bash
python evaluate_recommendations.py --annotations evaluation/annotations.example.json --results result_action.json --stage refined --top-k 5
python evaluate_recommendations.py --annotations evaluation/annotations.example.json --results result_action.json --stage coarse --top-k 5
```

Die Beispieldaten sind fiktiv; nur eigene Annotationen ergeben eine sinnvolle Qualitätseinschätzung.

## Reale Video-Extraktionsmessung (lokale Testumgebung)

Drei vom Nutzer bereitgestellte Motorradclips wurden nicht in GitHub hochgeladen.
Mit dem gewählten FFmpeg-Verfahren bei 2 Bildern/Sekunde entstanden:

| Clip | Zeit | Bilder | Extraktionszeit |
|---|---:|---:|---:|
| 15059932…mp4 | 13,38s | 27 | 1,51s |
| 15127630…mp4 | 6,00s | 12 | 0,57s |
| 15900856…mp4 | 9,38s | 19 | 2,86s |

Insgesamt 58/58 JPEGs. Zeitangaben gelten **nur** für dieses Testsystem und beweisen nicht die KI-Erkennungsqualität. Die Bild-Zeitangaben beruhen aktuell auf dem nominalen FPS-Abtastraster und sind noch **keine framegenauen Quell-PTS**.

## Offene Punkte

- Für kurze Ereignisse sind 2 Bilder/Sekunde eventuell zu wenig, eine ereignisgesteuerte zusätzliche Bewegungsauswertung bleibt offen.
- Für die externen Modellaufrufe fehlt weiterhin ein freigegebener API-Testlauf mit den realen Videoclips und eine Messung der Kosten/Fehlerquote.
- Manuelle Referenzannotations-Sätze je Content-Nische fehlen.
- Ein erkanntes Zeitfenster ist nicht automatisch der fertige Schnitt. Exakte Kanten, Ton und Übergänge fehlen noch.
- Streamlit/Stripe/öffentliche Live-App auf `main` wurden **nicht** geändert.
- Standbilder werden in der API-Auswertung an einen externen KI-Dienst gesendet. Verarbeite dafür nur berechtigtes Material; keine API-Schlüssel oder privaten Videos ins öffentliche Repository laden.

## Arbeitsreihenfolge ab hier

1. Gegen reale (autorisierte) Videos und **zwei unterschiedliche Ziel-Anweisungen** testen.
2. Precision@K/Recall@K, Fehlklassifikationen, Kosten und Latenz protokollieren.
3. Gezielte Verbesserung kurzer Bewegungsereignisse und präzisere Zeitstempel.
4. Schnittplan-Auswahl und gerenderte Vorschau aus nachgewiesenen Highlights entwickeln.
