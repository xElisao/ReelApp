# Phase 22 – PNG-Firmenlogo im Reel (Logo-Overlay 1)

**Stand:** 15.11.2026, geschützte Branch `feature/velocut-2-video-analysis`.
**Produktive Live-App und `main` unverändert.** Markenname bleibt vorläufig intern VeloCut.
**Status:** implementiert, 176 Tests/CI erfolgreich; visueller Nutzer-Browser-Test bestanden, dabei **ein fehlendes Schlussframe erkannt**. Exportfix CI-bestätigt, **Browser-Nachtest der korrigierten Version steht noch aus**.

## Ziel und Bedienung

Unterhalb von `✍️ Texteinblendungen (optional)` im Staging-Reel-Export
gibt es jetzt `🏷️ Firmenlogo (optional)` und den Upload
`Eigenes Logo als PNG hochladen`.

- **Ohne Logo**: bestehender Export vollständig unverändert.
- **Mit Logo**: statisches, gerne transparentes PNG wird
  **oben rechts über alle Szenen** eingeblendet.
- Bis **2 MB** und maximal **2048×2048 Pixel**, nur **ein Frame**;
  kein SVG/GIF/JPG/APNG.
- Nach Verarbeitung maximal **144×88 Pixel** im 540×960-Testvideo,
  32 px Abstand nach rechts und 48 px nach oben. Das Logo
  wird nicht verzerrt; allseits transparente Ränder werden beschnitten.
- Funktioniert zusätzlich zu Einstiegs-/CTA-Text und
  harten/weichen Schnitten (0,25/0,5/1 s) sowie vorhandenem
  Originalton.
- Es entstehen keine neuen KI-Aufrufe; der hochgeladene
  Logo-Inhalt wird **nicht** an OpenAI geschickt.
- Upload lokal im geschützten Streamlit-Prozess, lokal in eine
  temporäre Datei umcodiert und nur im fertigen MP4 eingebrannt;
  die Datei wird nach dem FFmpeg-Aufruf über das temporäre
  Verzeichnis gelöscht. Keine dauerhafte Logo-Bibliothek.
- Logo-PNG-Änderung ist Teil der **Reel-Cache-Signatur**.
  Vorherige Videovorschau / Download werden nach Änderung
  erst nach erneuter Rendering-Aktion wieder eingeblendet.

## Technische Sicherheitsdetails

In `reel_export.py`:
- `normalize_logo_png()` prüft Bytes, Dateikopf,
  Bildformat, Abmessung und Anzahl der Frames **vor FFmpeg**.
- Pillow öffnet das Bild, wandelt es in `RGBA` um,
  beschneidet Alpha-Ränder, skaliert mit Lanczos und
  **kodiert ein neues PNG ohne Originalmetadaten**.
- Ein vollständig transparentes Logo wird als Fehler gemeldet.
- Keine Dateinamen oder Filterparameter aus Nutzereingaben.
  Eingabe und lokale Bilddatei heißen fest `brand_logo.png`
  im separaten Server-Tempordner.
- FFmpeg erhält `-loop 1 -framerate 24 -i` mit diesem
  bereinigten Logo als zusätzlichen Eingang. Das Overlay
  wird **nach** allen Überblendungen und Texteinblendungen
  hinzugefügt: `overlay=x=W-w-32:y=48:shortest=0:format=auto`,
  gefolgt von `format=yuv420p,settb=AVTB,fps=24`.
  Gleichzeitig begrenzt FFmpeg den *gesamten Output* mit `-t`
  auf die erwartete Reel-Dauer. **Warum:** `shortest=1` bei
  Endlos-Logo-Input schnitt das letzte 24-fps-Frame ab (131
  statt 132 Frames bei 5,5 s). `shortest=0` + `-t`
  bewahrt die vollständige berechnete Laufzeit. Das Logo
  bleibt während Übergängen sichtbar und der Loop läuft
  nicht unendlich.
- Ungültige Bilddateien stoppen den Export vor jedem
  FFmpeg-Aufruf. Fehlerdaten/Originalmetadaten werden
  nicht ins UI übernommen.

## Tests / Nachweise

Neues `tests/test_reel_logo_overlay.py` mit **4 Tests**:

1. Transparenz bleibt erhalten, sichtbare Pixel bleiben
   nach proportionalem Resizing erhalten; versteckte
   PNG-Textmetadaten werden nach dem Re-Encode entfernt.
2. Manipulierte/leere/übergroße/falsche Dateien und
   komplett unsichtbare Logos werden vor FFmpeg abgewiesen.
3. Gemockte FFmpeg-Kommandozeile verweist ausschließlich
   auf fest benannte bereinigte PNG-Datei und feste
   Koordinaten; kein beliebiger Nutzerpfad.
4. **Echtes** FFmpeg produziert MP4 mit Logo + Titel +
   CTA sowohl bei hartem Schnitt als auch bei
   0,5-s-Überblendung mit Originalton. Frame-Pixeltests
   prüfen das Logo am Anfang, **während des Übergangs**
   und am Ende. Erwartete Länge 6,0 bzw. 5,5 Sekunden,
   540×960, Audio-Modus korrekt.

**GitHub Actions:** CI auf PR und Push nach Integration
des Tests **176/176 erfolgreich**, inklusive
Abhängigkeitsprüfung für Python 3.12 und 3.13.
Kein API-Konto, keine KI-Kosten für Tests.

## Verbleibende Aufgaben

- [x] PNG-Logo-Validierung inkl. Sicherheit & Re-Encode
- [x] Logo im Export aus Originalclips über alle Szenen
- [x] Text-/Fade-/Audio-Kompatibilität mit echten FFmpeg-Testvideos
- [x] Alte Reel-Signatur wird bei Logo-Wechsel ungültig
      (Code implementiert)
- [x] **Erster echter Benutzer-Browser-Test mit Testlogo**
      (15.11.2026): geschützte App `Logo-Overlay 1`,
      zwei Landschaftsclips aus gespeichertem Ergebnis
      **ohne neue KI-Analyse**; 0,5-s-Fade, Titel,
      Schlusszeile und transparentes Demo-Logo im MP4.
      Upload `velocut_test_reel_9x16_blur_mute_fade_050cs_text_logo (1).mp4`.
      Unabhängiges `ffprobe`: H.264, 540×960, 24 fps, **131 Frames**,
      **5,458333 s**, 281.697 B, stumm, vollständige Dekodierung.
      Visuell geprüft auf 15 Frames (0,3 bis 5,4 s):
      Logo durchgehend rechts oben; Titel zu Beginn gut lesbar;
      0,5-s-Fade zeigt beide Landschaften gemeinsam um
      2,65–2,9 s; `Mehr entdecken` ab etwa 3,7 s.
      Keine groben visuellen Fehler. **Ein Schlussframe
      fehlte jedoch gegenüber dem erwarteten 5,5-s-Reel**
      (132 Frames); daher ist dieser Browser-Build **nicht
      vollständig abgenommen**.
- [x] **Bugfix für ein fehlendes Schlussframe in GitHub
      implementiert und CI-getestet** (15.11.2026):
      in `reel_export.py` `overlay shortest=0` plus `-t`,
      Regressionstests erwarten **exakt 144 Frames / 6,0 s**
      bei Cut und **132 Frames / 5,5 s** bei 0,5-s-Fade,
      jeweils mit Logo+Text und optionalem Audio.
      **176/176 Tests grün**, Staging Python 3.12/3.13 grün.
      Versionslabel **`Logo-Frame-Fix 1 | 2026-11-15`**.
- [x] **Browser-Nachtest des korrigierten Exports bestanden (15.11.2026):**
      Der Nutzer hat nach Neustart und Label `Logo-Frame-Fix 1`
      die Datei `velocut_test_reel_9x16_blur_mute_fade_050cs_text_logo (2).mp4`
      aus der Staging-App hochgeladen. Unabhängige Medienprüfung:
      **5,500000 Sekunden, exakt 132 Frames, 24 fps, H.264, 540 × 960**,
      **282.696 Bytes**, nur Video ohne Audiospur. Vollständiges
      FFmpeg-Dekodieren ohne Fehler bestätigt.
      Frame-Stichproben bei 0,30 / 1,00 / 1,80 / 2,20 / 2,50 /
      2,65 / 2,75 / 2,90 / 3,10 / 3,70 / 4,20 / 4,80 /
      5,20 / 5,45 s zeigen das DEMO-Logo durchgehend rechts oben,
      Einstiegstitel zu Beginn, saubere 0,5-s-Überblendung von
      Bergstraße zu Bergtal bei ~2,5–3,0 s und die Schlusszeile
      ab ca. 3,5 s bis zum vollständigen letzten Bild. Kein
      sichtbarer Beschnitt; vorher fehlendes Schlussframe ist
      **im realen Benutzerexport wieder enthalten**.
      Die Teilfunktion **PNG-Logo + Text + Fade ist praxisbestätigt**.
      Weitere Logo-Formate/Markenfarben und der manuelle Logo-Wechsel-
      Cachetest stehen noch aus.
- [x] **Browser-Cache-Test für Logoentfernung bestanden (15.11.2026):**
      Nutzer hat nach dem erfolgreichen MP4-Export **nur das
      DEMO-Logo entfernt**, ohne einen neuen Export zu starten,
      und mit „ja“ bestätigt, dass die bisherige Videovorschau
      wie erwartet verschwunden ist. Der Download verwendet
      dieselbe Export-Signatur-Bedingung, wurde nicht separat
      bestätigt. **Logo ersetzen** statt entfernen ist noch kein
      eigenständiger manueller Test.
- [ ] Visuelle Prüfung auf anderen Bildern/Logoformaten,
      später Layoutoptionen, Farben, größere Exportauflösung.
- [ ] Marken-/Logo-Nutzungsrechte und Kundendatenschutz
      vor kommerziellem Launch klären.
- [ ] Logo-Persistenz in Nutzerkonto erst nach
      sicherer Authentifizierung/Datenschutzsystem.

**Wichtig:** Auch mit Logo-Overlay bleibt F2-02
als *vollständiges Brand Kit* offen: Markenfarben,
Schriftwahl, Templates und produktionsreifes Hosting
fehlen weiterhin.
