# Phase 23 – Markenfarbe für Titel und Schlusszeile (Markenfarbe 1)

**Stand:** 15.11.2026. Nur Branch `feature/velocut-2-video-analysis` und
geschützte Streamlit-Staging-App; produktives `main`, Checkout und
bestehende Kundendaten **nicht geändert**.

## Was die Funktion kann

Im Exportabschnitt `✍️ Texteinblendungen (optional)` erscheint, **nur
bei aktivierten Textebenen**, eine neue optionale Checkbox:
`Firmenfarbe für die Textflächen verwenden`.

- Standard **aus**: bewährter Export mit **weißer Schrift auf
  halbtransparenter schwarzer Fläche** bleibt identisch.
- Bei Aktivierung: Streamlit-Farbauswahl
  `Markenfarbe für Titel und Schlusszeile` (initial `#245582`).
- Titel und CTA erhalten die **gleiche ausgewählte, deckende
  Volltonfläche**. Die Farbe bleibt die eingegebene HEX-Farbe
  (ohne erzwungenes Dunkeln oder Verfälschen).
- Die Schriftfarbe wird **automatisch schwarz oder weiß**,
  je nachdem welche nach der WCAG-Luminanzformel den größeren
  Kontrast zur Hintergrundfarbe hat. Bei opaker Farbfläche
  ist dieser rechnerisch mindestens 4,5:1, bevor H.264
  die Pixel minimal beeinflusst.
- Firmenlogo, Szenenübergänge, Originalton, Textpositionen,
  Exportdauer und die optionalen 2-s-Einblendungen bleiben
  unverändert.
- Die Markenfarbe gehört zur **Export-Cache-Signatur**. Nach einer
  Farbänderung wird das alte MP4 nicht mehr als aktuelle Vorschau
  angezeigt, bis neu gerendert wird.
- Keine erneute KI-Analyse, keine OpenAI-Kosten und keine
  externe Verarbeitung für die Farbanpassung.
- Dateien mit aktiver Farbe erhalten im Download-Namen
  das Suffix `_brand`.

## Sichere Implementierung

In `reel_export.py`:
- `normalize_brand_color()` akzeptiert ausschließlich
  Strings im Format `#RRGGBB` (6 Hex-Ziffern), gibt
  standardisierte Großschreibung zurück oder bricht mit
  `ReelExportError` **vor Aufruf von FFmpeg** ab.
- `_brand_text_style()` berechnet die linearisierte
  relative Luminanz und daraus Kontrastverhältnisse
  für Schwarz und Weiß; die stärkere Textfarbe wird gewählt.
  Ohne Markenfarbe gilt `black@0.65` mit weißem Text.
- FFmpeg erhält **nur nach erfolgreicher Validierung** ein
  sicheres `boxcolor=0xRRGGBB` und `fontcolor=black/white`,
  keine unbereinigten User-Filterausdrücke.
- Weiterhin `drawtext` mit sicheren temporären UTF-8-Textdateien,
  `expansion=none`, anschließend optionales PNG-Firmenlogo.
- Streamlit-Farbauswahl nur sichtbar, wenn Texte aktiv sind.

## Tests und Abnahme

Neue Datei `tests/test_reel_brand_color.py` mit vier Tests:
1. HEX-Normalisierung, Standardverhalten, Kontrastwahl für
   helle und dunkle Farben.
2. Defekte/manipulierte Nicht-HEX-Werte werden vor FFmpeg
   abgewiesen, einschließlich Filter-Injection-ähnlicher Werte.
3. FFmpeg-Filtergraph zeigt exakt die sichere Farbe und die
   ausgewählte Schrift, an beiden Textfeldern, ohne Farbe
   bleibt der alte Graph identisch.
4. **Echte lokale FFmpeg-MP4-Exports** mit ausgewählten
   Firmenfarben: `cut/mute` mit heller Farbfläche und
   `fade/original` mit dunkler Farbfläche,
   jeweils inklusive Titel, CTA und PNG-Logo.
   Die Video-Pixel werden farblich geprüft; Laufzeiten,
   genaue Frameanzahl, Auflösung und Tonspuren ebenfalls.

**Automatische Gesamt-Tests erfolgreich:** **180/180**
(176 bestehende + 4 neue). GitHub Actions PR-Lauf
`43731455767` auf Commit `c059aee4`: `unit-tests` grün,
inklusive realer FFmpeg-MP4s und Farbpixelprüfung;
Staging-Abhängigkeiten für Python 3.12/3.13 ebenfalls grün.
Kein zusätzlicher KI-Aufruf.

## Noch ausstehend

- [x] Optionaler Farbpicker, Default-Aus, Cache-Invalidierung im Code
- [x] Strenge HEX-Validierung und automatische schwarz/weiß-Schrift
- [x] Neue automatisierte Testfälle geschrieben
- [x] GitHub-CI-Lauf: 180 Tests + Python 3.12/3.13 grün
- [x] **Realer Benutzer-Praxistest 15.11.2026 bestanden:**
      Nutzer hat nach Reboot/Versionsbestätigung `Markenfarbe 1`
      das 32-s-Landschaftsvideo mit gespeichertem JSON ohne
      neue KI analysieren zu lassen erneut geladen, zwei Szenen
      mit 0,5-s-Fade, Titel `Bergstraßen entdecken`, Schlusszeile
      `Mehr entdecken`, DEMO-PNG-Logo und blauem Titel-/CTA-
      Hintergrund `#245582` exportiert und das **echte** MP4
      `velocut_test_reel_9x16_blur_mute_fade_050cs_text_brand_logo.mp4`
      im Chat bereitgestellt. Unabhängig per `ffprobe` bestätigt:
      **5,500000 s, 132 Frames, 24 fps, H.264, 540 × 960,
      281.469 Bytes**, keine Audiospur. Vollständiges Decoding
      mit FFmpeg **ohne Fehler**. An **16 extrahierten Frames**
      bei 0,30 / 0,80 / 1,50 / 1,85 / 2,15 / 2,48 / 2,62 /
      2,75 / 2,90 / 3,10 / 3,45 / 3,65 / 4,00 / 4,80 /
      5,20 / 5,45 s visuell bestätigt: Titel in weißer Schrift
      auf der gewählten blauen Fläche nur am Anfang, CTA auf
      gleicher Fläche am Ende, DEMO-Logo durchgehend rechts oben;
      weiche Überblendung der zwei Landschaften etwa 2,5–3,0 s.
      Kein sichtbarer Text- oder Logo-Beschnitt. Video und
      Titel-/CTA-Farbflächen sind korrekt – **Browser-Abnahme
      der Farb-Teilfunktion bestanden**. Die MP4 selbst wurde
      nicht im GitHub-Repository abgelegt.
- [ ] **Browser-Cache-Test** nach Farbwechsel ohne Neu-Export.
- [ ] Weitere Designoptionen (Fonts, Templates, Layouts,
      Social-Safe-Areas) und kommerzieller Plattform-Check.

**Wichtig:** Teilfunktion Markenfarbe, nicht das gesamte F2-02
Brand Kit. Produktive Verkaufsreife steht weiterhin aus.
