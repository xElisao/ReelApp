# Phase 22 – PNG-Firmenlogo im Reel (Logo-Overlay 1)

**Stand:** 15.11.2026, geschützte Branch `feature/velocut-2-video-analysis`.
**Produktive Live-App und `main` unverändert.** Markenname bleibt vorläufig intern VeloCut.
**Status:** implementiert, 176 Tests/CI erfolgreich; **Nutzer-Browser-Praxistest noch offen**.

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
  hinzugefügt: `overlay=x=W-w-32:y=48:shortest=1:format=auto`,
  gefolgt von `format=yuv420p,settb=AVTB,fps=24`.
  Logo ist damit auch während Übergängen sichtbar.
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
- [ ] **Echter Benutzer-Browser-Test mit Testlogo**:
      Staging App rebooten, `Logo-Overlay 1 | 2026-11-15`
      prüfen, bekanntes 32-s-Landschaftsvideo und
      gespeichertem Ergebnis ohne KI laden.
      Demo-PNG hochladen, Titel und CTA nach Wunsch
      belassen, Fade 0,5 s auswählen, MP4 exportieren,
      zur Bildprüfung in Chat hochladen.
- [ ] **Browser-Cache-Test**: Logo entfernen oder wechseln,
      alte MP4-Vorschau muss ohne Export verschwinden.
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
