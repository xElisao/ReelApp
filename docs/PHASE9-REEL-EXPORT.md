# Phase 9: Reel-Export 1 (geschütztes KI-Labor)

**Stand:** 08.11.2026, nur Entwicklungsbranch
`feature/velocut-2-video-analysis`.
Produktive `app.py` auf `main` bleibt unverändert.

## Warum?

Zuvor erzeugte VeloCut nur kurze, einzeln abspielbare Vorschauclips.
Nach dem erfolgreichen Test zur Vermeidung harter Schnitte hat der Nutzer
ausdrücklich darum gebeten, die Highlights zu **einer herunterladbaren
MP4-Datei zusammenzufügen**.

## Umfang des ersten Export-Prototyps

- Erzeugt ein stummes **Hochkant-MP4 (9:16, 540 × 960 Pixel, H.264)**.
- Aus **2 bis 3 bereits gerenderten Vorschauclips**; maximale Länge
  30 Sekunden, maximal 40 MB Datei.
- Auswahl einzelner Szenen über Checkboxen. Reihenfolge:
  **chronologisch (Standard)** oder **bisherige KI-Rangfolge**.
- Verschiedene Quellauflösungen und Bildseitenverhältnisse werden
  unter Beibehaltung des vollständigen Bildinhalts skaliert und
  gegebenenfalls mit **schwarzen Balken** versehen.
- Erste Version **ohne Ton, Musik, Untertitel, Übergänge oder
  Bildausschnitt-Zoom**. Das wird in der Oberfläche ausdrücklich gesagt.
- Kein OpenAI-Aufruf: FFmpeg verbindet die bereits vorhandenen
  Vorschau-MP4s. Die Originalvideos werden nicht nochmals gelesen.
- Streamlit speichert das exportierte Video ausschließlich in der
  aktuellen Sitzung. Es wird **nur bei identischer Szenenauswahl und
  Reihenfolge** zum Download angeboten; beim Erstellen neuer Vorschauen
  wird ein alter Export aus dem Sitzungsstatus gelöscht.

## Sicherheit / Grenzen

- Nur bereits von `preview_clips.py` erfolgreich gerenderte Clips können
  im Labor gewählt werden. Die vorhandene Shot-Fix-1-Prüfung filtert
  harte Bildwechsel im Einzelclip, soweit lokal erkennbar.
- `reel_export.py` validiert MP4-Containerkopf, Zeiträume,
  maximal 10 s pro Clip, maximale Datei-/Gesamtlänge und
  ungewollt überlappende Ausschnitte derselben Quelle.
- FFmpeg läuft ohne Shell-Zwischenschicht mit festem Zeitlimit und
  temporären Dateien, die nach dem Rendern gelöscht werden.
- Fehlermeldungen geben keine internen Videopfade oder FFmpeg-Logs preis.
- Noch kein finaler kommerzieller Editor: Audio, Verhältnisausschnitte,
  Frame-genaue Übergänge und mehr als drei Szenen sind spätere Themen.

## Testplan

1. Streamlit-Dev-App mit Build `Reel-Export 1 | 2026-11-08` starten.
2. Bestehendes 32-s-Landschaftstestvideo und die gespeicherte
   Ersatz-Analyse-JSON in der **kostenfreien Vorschau** verwenden.
   Das bereits bekannte Szenen-Cut-Filtering lässt zwei Clips übrig.
3. Beide Clips bei „Szene ins Test-Reel aufnehmen“ ausgewählt lassen.
4. Standardreihenfolge „Chronologisch“ beibehalten.
5. „Ausgewählte Clips zu einem Reel verbinden“ anklicken.
6. Ergebnis in der App anschauen und als MP4 herunterladen.
   Visuell prüfen, dass die zwei Einstellungen nacheinander
   abgespielt werden und kein innerer Bildsprung auftritt.

`tests/test_reel_export.py` prüft Validierungsfälle und einen echten
FFmpeg-Export mit Clips unterschiedlicher Seitenverhältnisse (mit
FFmpeg/ffprobe). GitHub CI installiert FFmpeg für Unit-Tests und
prüft die Staging-Python-Dependencies für 3.12 und 3.13.

**Hinweis:** Das Laufverhalten in der geschützten Streamlit-Instanz muss
noch durch den Nutzer bestätigt werden. GitHub Actions können nur die
Offline-Pipeline prüfen.
