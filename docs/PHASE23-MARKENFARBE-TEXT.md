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

**Automatische Gesamt-Tests:** 176 bestehende + 4 neue.
CI-Status wird nach dem GitHub-Lauf gesondert bestätigt.

## Noch ausstehend

- [x] Optionaler Farbpicker, Default-Aus, Cache-Invalidierung im Code
- [x] Strenge HEX-Validierung und automatische schwarz/weiß-Schrift
- [x] Neue automatisierte Testfälle geschrieben
- [ ] GitHub-CI-Lauf für diese neuen Testfälle abschließend prüfen
- [ ] **Realer Benutzer-Praxistest:** Staging-App über
      Reboot neu starten, Label `Markenfarbe 1 | 2026-11-15`
      prüfen. Bekannte 2 Landschaftsclips ohne neue KI-Analyse
      laden; Titel `Bergstraßen entdecken`, CTA
      `Mehr entdecken`, 0,5-s-Fade, DEMO-Logo falls gewünscht.
      `Firmenfarbe für die Textflächen verwenden` einschalten,
      z. B. `#245582` (Blau) wählen, MP4 exportieren und
      hier im Chat hochladen. Unabhängig Video und Farben prüfen.
- [ ] **Browser-Cache-Test** nach Farbwechsel ohne Neu-Export.
- [ ] Weitere Designoptionen (Fonts, Templates, Layouts,
      Social-Safe-Areas) und kommerzieller Plattform-Check.

**Wichtig:** Teilfunktion Markenfarbe, nicht das gesamte F2-02
Brand Kit. Produktive Verkaufsreife steht weiterhin aus.
