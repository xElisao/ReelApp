# VeloCut 2.0 – Zweite visuelle Analyse und reale Extraktionsmessung

Stand: 2026-11-07. Entwicklungsbranch, **nicht** Produktivsystem.

## Umgesetzt
- `adaptive_refinement.py`: Bereits erkannte Grobfenster werden in kleinere
  Fenster (3 Sekunden Länge, 1,5 Sekunden Schrittweite) aufgeteilt.
- Die Reihenfolge der Detailanalyse berücksichtigt den Nutzerwunsch.
- Wenn ein gefragtes Ereignis im Grobscan nicht erkannt wird, werden begrenzt
  auch unpassende Grobfenster genauer untersucht, statt das Ereignis als sicher
  abwesend auszugeben.
- Überlappungen, API-Aufruf-Budgets und teilweise untersuchte Videos werden
  transparent behandelt; fehlerhafte Szenen werden nicht als Treffer ausgegeben.
- `prototype_intent.py` unterstützt `--refine`; die neue Phase bleibt optional.
- `tests/test_adaptive_refinement.py` ergänzt Regressionstests für Grenzen,
  verschiedene Nutzerziele, fehlende Pflichtmotive, Budgetlimits.

## Kommando

```bash
python prototype_intent.py video.mp4 --instruction "Zeige die besten Kurven" --refine --output kurven.json
python prototype_intent.py video.mp4 --instruction "Zeige die schönsten Berge" --refine --output berge.json
```

Voraussetzungen: Python, FFmpeg/FFprobe, installierte Python-Abhängigkeiten,
OpenAI-API-Key in lokaler Umgebungsvariable (niemals im Repository speichern).

## Reale lokale Extraktionsmessung ohne KI-API

Drei private Beispielvideos wurden **nicht** in GitHub hochgeladen.
Offline wurden mit einem FFmpeg-Prozess je Originalvideo Bilder mit
2 Bildern/Sekunde und maximal 640 Pixel Kantenlänge extrahiert:

| Videodatei | Dauer | Bilder | Extraktionszeit |
|---|---:|---:|---:|
| 15059932…mp4 | 13,38 s | 27 | 1,52 s |
| 15127630…mp4 | 6,00 s | 12 | 0,60 s |
| 15900856…mp4 | 9,38 s | 19 | 2,87 s |

**Insgesamt 58/58 Bilder erfolgreich**, auf diesem Prüfgerät in ungefähr
5 Sekunden Gesamtzeit. Andere Hardware und Uploadauflösungen können abweichen.

Ein separater Versuch, viele Einzelbilder über wiederholte unabhängige
FFmpeg-Aufrufe zu extrahieren, lief in ein Zeitlimit. Die **gebündelte**
Extraktion muss daher als nächster Schritt in den Prototyp integriert werden.

**Wichtig:** Dies testet nur die technische Bilderzeugung. Keine dieser
Messungen liefert eine KI-Highlight-Erkennungsquote, eine validierte
Schnittqualität oder eine API-Kostenmessung.

## Noch offen

1. Batch-Extraktion statt separatem FFmpeg-Prozess pro Bild in den
   Analyseablauf integrieren.
2. Freigegebenen echten Testclip über den OpenAI-API-Prototyp auswerten,
   mit zwei unterschiedlichen Nutzeranweisungen.
3. Genaue Referenzereignisse manuell markieren und Trefferquote, Fehler,
   Kosten und Latenzen messen.
4. Auf Basis der Ergebnisse die Auswahl/Schneidegrenzen iterieren.
5. Streamlit und Stripe erst nach gesonderter Prüfung anfassen.
