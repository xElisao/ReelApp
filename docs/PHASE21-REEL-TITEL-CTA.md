# Phase 21 – Texteinblendungen: Titel und Schlusszeile (Text-Overlay 1)

**Stand:** 15.11.2026; **nur** branch `feature/velocut-2-video-analysis`;
produktiv laufendes `main` und alter Checkout **nicht geändert**.

## Nutzen

Zum ersten Mal kann der Nutzer ein fertiges Reel lokal mit
einem **Einblendungstitel** am Anfang und einer optionalen
**Schlusszeile / Handlungsaufforderung** am Ende versehen.
Beispiel Immobilien-Reel:
- Titel: `Moderne Wohnung mit Bergblick`
- Schlusszeile: `Jetzt Besichtigung vereinbaren`

Das ist ein erster, bewusst kleiner Schritt Richtung
veröffentlichungsfertige Videos – **noch kein** vollständiges Brand Kit,
kein Untertitel-Editor, keine Musikbibliothek.

## UX / Ablauf

In der Staging-App unter `🎬 Test-Reel als MP4 erstellen` erscheint
der neue Abschnitt **`✍️ Texteinblendungen (optional)`**.
- Checkbox **`Titel und Schlusszeile einblenden`** ist zunächst aus;
  bestehendes Verhalten bleibt identisch.
- Nach Aktivierung erscheinen zwei frei editierbare Textfelder
  `Titel am Anfang` und `Schlusszeile am Ende`, jeweils bis
  zu **56 Unicode-Zeichen**.
- **Es reicht eines** der beiden Felder. Bei beiden leer
  erfolgt ein normaler Export ohne Titel.
- Einblendungen mit semitransparentem dunklen Hintergrund
  und weißer Schrift in vertikalen Social-Safe-Zones:
  Titel im oberen Bereich, Schlusszeile oberhalb des unteren
  Social-UI-Bereichs.
- Maximal **2 Sekunden** pro Einblendung, bei sehr kurzen Reels
  automatisch kürzer; Text wird nach allen Szenenschnitten und
  Überblendungen eingefügt, nicht in einzelnen Rohclips.
- Neues Download-Suffix `_text.mp4`, wenn mindestens ein Text
  nicht leer ist.
- Der Nutzer darf **keine Eigenschaften erfinden**; Texte sind
  bewusst vom Nutzer einzugeben und nicht von der KI generiert.

## Technik / Sicherheit

- `render_test_reel(..., title_text="", cta_text="")`: sichere
  rückwärtskompatible optionalen Parameter.
- `normalize_overlay_text` erlaubt nur druckbare Unicode-Zeichen,
  normalisiert nach NFC und begrenzt Länge auf 56; Nullbytes,
  Zeilenumbruch, Steuerzeichen und bidi-Steuerungen werden abgewiesen.
- FFmpeg-Textfilter liest Inhalte **ausschließlich aus temporären,
  nicht nutzerbenannten UTF-8-Dateien** `overlay_title.txt` und
  `overlay_cta.txt`. Raw-Text ist *niemals* Teil des Filtergraphen
  oder Shell-Kommandos. Filter `expansion=none` verhindert
  Makro-/Expressions-Auswertung von `%{...}`, und FFmpeg erhält
  weiterhin eine Argumentliste statt einer Shell-Zeichenkette.
- 16-Zeichen-Wrapping pro Zeile hilft gegen überbreite Einblendungen.
  Die reale visuelle Qualität langer Wörter wird im Browser geprüft;
  für endgültige Produktausgabe brauchen wir belastbares
  pixelbasiertes Layout/Safe-Zones über alle Formate.
- Systemschrift DejaVu Sans Bold über `fonts-dejavu-core` in
  `packages.txt`; keine Schriftdateien werden in das Projekt
  oder an Endkunden kopiert. Lizenzprüfung vor öffentlichem Launch.
- Fehlende Schriftart führt zu kontrollierter Fehlermeldung;
  Export ohne Text funktioniert weiterhin.
- Titel / Schlusszeile zählen zusammen mit anderen Exportparametern
  zur Reel-Cache-Signatur. Änderung an einem Feld blendet das alte
  MP4 aus und erfordert einen neuen manuellen Export.
- Alle bestehenden `cut`/`fade`-Übergänge mit variabler Dauer
  und Originalton bleiben erhalten. Keine neue OpenAI-Analyse.

## Tests / Status

- CI auf Branch nach Integration: **172 Tests erfolgreich**,
  inkl. 5 neuer Testfälle in `tests/test_reel_text_overlay.py`.
- Reale FFmpeg-MP4-Tests für `cut`, `fade` 0,25 s + Originalton
  und `fade` 1,0 s, jeweils Titel / CTA sichtbar nur
  an den vorgesehenen Zeitpunkten;
  Laufzeit und 540×960 Auflösung unverändert.
- Validierung von Umlauten, `%{pts}`, Doppelpunkten, Steuerzeichen
  und Länge, keine Nutzereingabe als FFmpeg-Filterausdruck.
- Systempakete im Staging bei Deployment prüfen
  (die Linux-CI-Tests hatten DejaVu installiert).
- **Browser-Praxistest des echten Streamlit-Exports am 15.11.2026 bestanden:**
  Nutzer hat `velocut_test_reel_9x16_blur_mute_cut_text.mp4`
  hochgeladen. Unabhängig per `ffprobe` geprüft: **6,000 Sekunden**, 
  **H.264**, **540×960**, **24 fps**, **144 Frames**, **keine Tonspur**.
  Unabhängig extrahierte Frames bei 0,25 / 0,9 / 1,85 Sekunden zeigen
  sichtbar `Bergstraßen entdecken` in zwei Zeilen mit dunkler Fläche;
  bei 2,15 / 2,9 Sekunden nicht mehr. Bei 3,1 / 3,9 Sekunden
  noch keine Schlusszeile; bei 4,15 / 4,65 / 5,25 / 5,85 Sekunden
  sichtbar `Mehr entdecken`. Szenenwechsel am 3,0-s-Schnitt:
  Bergstraße zu grünem Gebirgstal, ohne augenfälligen Bildfehler.
  Auf dem Bild sind beide Texte gut lesbar, kontrastreich und
  ohne sichtbaren Beschnitt.
  **Wichtig:** Dieses reale Benutzer-MP4 ist ein **direkter Schnitt**
  (`_cut_text.mp4`), *kein* echter Text-plus-Fade-Browser-Test.
  Text+Fade ist über FFmpeg-CI bereits getestet, echtes Benutzer-MP4
  für die Kombination steht noch aus. MP4 lokal geprüft, nicht
  als sensibles Testmaterial ins Repository kopiert.

- **Zweiter echter Nutzer-Browser-Praxistest am 15.11.2026 bestanden:
  Titel + CTA + weiche Überblendung 0,50 s.**
  Nutzer hat `velocut_test_reel_9x16_blur_mute_fade_050cs_text.mp4`
  hochgeladen. Per `ffprobe` unabhängig bestätigt:
  **5,500 Sekunden**, **280.336 Bytes**, **H.264**, **540×960**,
  **24 fps**, **132 Frames**, **nur Videospur ohne Ton**.
  Die Datei lässt sich vollständig und fehlerfrei dekodieren
  (`ffmpeg -f null -`, Rückgabewert 0).
  Stichprobenframes aus dem **echten Nutzer-Export** zeigen
  den Einstiegstitel `Bergstraßen entdecken` bei 0,4 / 1,0 /
  1,8 s und nicht mehr bei 2,15 s. Die Überlagerung beider
  Landschaften ist sichtbar ungefähr zwischen 2,5 und 3,0 s,
  insbesondere bei 2,65 / 2,75 / 2,9 s, und endet in der
  grünen Tallandschaft ohne sichtbaren harten Schnitt.
  `Mehr entdecken` steht bei 3,8 / 4,0 / 4,3 / 4,8 / 5,2 s
  gut lesbar über der Landschaft. Die Laufzeit stimmt exakt
  mit 2×3,0 s minus 0,5 s Überlappung überein.
  Keine visuellen Beschnitte der Textflächen erkennbar.
  **Damit ist die Browser-Praxisabnahme der Kombination
  Fade + Titel + CTA abgeschlossen.**
  MP4 ist **nicht** im GitHub-Repository abgelegt.

## Nächster manueller Schritt (einzeln testen)

1. Geschützte Streamlit-Test-App über **Reboot** neu starten.
2. Versionslabel `Text-Overlay 1 | 2026-11-15` prüfen.
3. Erst dann vorhandenes 32-s-Landschaftsvideo samt gespeichertem
   `velocut_32s_ersatz_vorschau.json` **ohne KI** laden.
4. Bei Reel-Export **Texteinblendungen einschalten**,
   als Titel z. B. `Bergstraßen entdecken`,
   als Schlusszeile `Mehr entdecken`; Übergang 0,50 s,
   unscharfer Hintergrund, ohne Ton.
5. Exportieren, MP4 hochladen, reale Originalframes prüfen und
   getrennt den Test ohne Text bestätigen.
6. Manuell einen Titel ändern: älteres MP4 darf bis zum nächsten
   erneuten Export nicht als aktuell angezeigt werden.

**Stand der Praxisabnahme:** Titel, CTA, direkter Schnitt **und**
0,5-s-Fade jeweils per echtem Nutzer-MP4 unabhängig bestätigt.
Offen bleiben Stale-Cache-Prüfung nach Textänderung,
Tests ohne Text sowie weitere Brand-Kit-Funktionen.

**Wichtig:** Staging ist weiterhin keine für Fremdkunden
freigegebene kommerzielle Anwendung.
