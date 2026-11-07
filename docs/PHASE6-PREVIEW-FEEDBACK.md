# VeloCut 2.0 – Szenenvorschau und menschliches Feedback

Status: **Entwicklungsbranch**, \`staging_app.py\` mit Versionsanzeige
\`Preview-Lab 1 | 2026-11-07\`. Kein Merge in \`main\`.

## Was jetzt möglich ist

- Die KI-Analyse liefert nach wie vor Zeitfenster mit Beschreibungen und Scores.
- \`preview_clips.py\` schneidet aus den *ursprünglichen* lokalen Videos
  **bis zu drei kurze MP4-Vorschauen** (H.264, höchstens 10 Sekunden je Clip).
- Alte JSON-Analyseberichte können **ohne weiteren OpenAI-Aufruf** erneut
  verwendet werden. Die Test-App benötigt dazu die passenden Originalvideos,
  die in derselben Reihenfolge erneut hochgeladen werden müssen.
- Der Nutzer spielt die Szenen ab und bewertet jede davon als
  \`Gut\`, \`Nicht gut\` oder \`Noch nicht bewertet\`.
- Das Feedback wird als separate JSON-Datei exportiert.
  Das ist für spätere Vergleiche und Verbesserung des Rankers vorgesehen.

## Bedienung in Streamlit Cloud

1. Die Test-App auf dem Branch \`feature/velocut-2-video-analysis\`
   neu starten und sicherstellen, dass \`Preview-Lab 1\` angezeigt wird.
2. Das **gleiche Originalvideo** hochladen, das beim früheren Test
   als \`video-1\` verwendet wurde.
3. Nach unten zu **Szenen-Vorschau ohne neue KI-Analyse** scrollen.
4. **Vorhandenes Analyseergebnis** auswählen (\`.json\` oder \`.txt\`).
5. Bestätigen, dass das hochgeladene Originalvideo wirklich zur
   Analyse gehört. Bestehende Berichte enthalten noch keine
   verifizierbaren Video-Prüfsummen.
6. Auf **Vorschau aus gespeichertem Ergebnis erstellen** klicken.
   **Nicht** auf den roten KI-Analyse-Button klicken:
   Die gespeicherte JSON-Datei reicht aus.
7. Video-Clips abspielen, jede Szene bewerten und auf
   **Meine Szenenbewertungen herunterladen** klicken.
8. Die Feedback-JSON-Datei kann zur weiteren Auswertung geteilt werden.
   Keine privaten Originalvideos auf GitHub hochladen.

## Neue Analysen

Der neue Haken **Abspielbare Vorschau nach der Analyse erstellen**
ist standardmäßig aktiv. Nach der **kostenpflichtigen** KI-Analyse
werden die ausgewählten MP4-Clips automatisch lokal gerendert.
Für das Rendern selbst werden keine weiteren OpenAI-API-Aufrufe ausgeführt.

## Sicherheits- und technische Grenzen

- Temporär hochgeladene Originalvideos und MP4-Dateien werden am Ende
  des jeweiligen Verarbeitungsdurchlaufs vom Dateisystem entfernt.
  Die verkleinerten Vorschau-Bytes bleiben im Arbeitsspeicher der
  aktiven Streamlit-Sitzung und sind nach Sitzungsende nicht garantiert verfügbar.
- Nutzereingaben aus JSON-Berichten werden hinsichtlich Zeitfenstern,
  Video-Zuordnung, Datenform und Clipsize validiert. Ohne eindeutige
  Quellvideo-Prüfsumme wird die Herkunft alter JSON-Berichte jedoch **nicht
  automatisch** bestätigt: Der Nutzer muss dasselbe Video auswählen.
- Maximal drei Vorschauclips pro Ergebnis, jeweils höchstens 10 Sekunden.
  Maximale Größe eines Vorschau-MP4: 10 MB.
- Videopreviews sind **kein** fertig montiertes Reel und keine Garantie
  für exakte framegenaue Schnittpunkte.
- In der Staging-App dürfen maximal drei Originalvideos von je 60 s/
  80 MB und insgesamt 160 MB hochgeladen werden.
- Die bestehende produktive Streamlit-App auf \`main\` und Stripe
  bleiben unverändert. Passwortschutz des KI-Labors ist nur für
  kontrollierte Staging-Tests geeignet, nicht für öffentliches Kundendeployment.

## Technische Validierung

Die GitHub-Workflow-Tests führen zusätzlich zu den Mock-Tests
einen synthetisch erzeugten vier Sekunden langen FFmpeg-Testclip
durch die Vorschau-Pipeline. Es ist **kein** Nutzer-Testvideo im Repo.
Die wirkliche Vorschauqualität und Passung zum Nutzerziel muss
anschließend menschlich bewertet werden.
