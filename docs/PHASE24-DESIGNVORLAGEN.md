# Phase 24 – Designvorlagen „Klassisch“ und „Modern“

**Stand:** 24.11.2026, Branch `feature/velocut-2-video-analysis`.
Nur geschützte Staging-Test-App; produktives `main`,
Stripe-Checkout und Kundendaten **nicht verändert**.

## Nutzen und Oberfläche

Im Bereich `✍️ Texteinblendungen (optional)` erscheint bei
eingeschalteten Texteinblendungen unter Titel/Schlusszeile
die Auswahl **`Designvorlage für Titel und Schlusszeile`**:

- **Klassisch (wie bisher)** – Standardeinstellung,
  genau das bestehende mittige Layout:
  30 px Schrift, 16 Zeichen pro Zeile beim Umbruch,
  16 px Textbox-Rand, 6 px Zeilenabstand,
  Text horizontal zentriert; Titel y=150,
  Schlusszeile y=H−185−Texthöhe.
- **Modern (linksbündig)** – festes zweites Layout:
  28 px Schrift, 14 Zeichen pro Zeile,
  12 px Textbox-Rand, 7 px Zeilenabstand,
  x=44, Titel y=210, Schlusszeile y=H−235−Texthöhe.
  Kürzerer Zeilenumbruch schützt breite Texte
  vor seitlichem Beschnitt.
- **Kein neues KI-Rendering:** beide Layouts werden mit
  bestehenden Clips per FFmpeg lokal in die fertige MP4
  eingebrannt, ohne neue OpenAI-Anfrage.
- Die bereits bestehende optional gewählte Firmenfarbe
  färbt in beiden Layouts die Textflächen, bei gut lesbarer
  automatisch schwarzer oder weißer Schrift.
- Transparente Logos (oben rechts), Originalton,
  Hintergrundvarianten, direkte Schnitte und weiche
  Überblendungen werden unverändert verarbeitet.
- Die Designvorlage gehört zur **Reel-Cache-Signatur**.
  Wird von Klassisch auf Modern gewechselt, verschwindet
  das zuvor exportierte MP4 aus Vorschau und Download,
  bis neu gerendert wurde.
- Bei Modern erhalten Downloads ein `_modern`-Suffix.
  Klassisch hat weiterhin die bisherigen Dateinamen.
- Die UI-Versionskennung lautet
  `Designvorlagen 1 | 2026-11-24`.

## Sicherheit, Kompatibilität und Limitierung

In `reel_export.py` ist `design_template="classic"`
der unveränderte Standard für ältere Aufrufer.
Eine **strenge Auswahl** `{"classic", "modern"}` verhindert
beliebige Nutzereingaben im FFmpeg-Filtergraphen.
Der Test rendert nur aus validierten, festen
Schriftgrößen, Positionen, Umbruchbreiten und Rändern.
Nutzertitel und CTA werden wie bisher vor FFmpeg
normalisiert und in temporären UTF-8-Textdateien
abgelegt (`expansion=none`). Es gibt keine neuen
Pfade in Benutzereingaben.

Dies sind zunächst **zwei Layouts für Textflächen**,
keine umfangreiche Vorlagenbibliothek für Videoästhetik,
Szenenauswahl, animierte Elemente oder Schriftarten.

## Testplan und Abnahme

Neue Datei `tests/test_reel_design_templates.py`:

1. Schadhafte/unbekannte Vorlagenwerte werden vor FFmpeg
   abgewiesen (`None`, Injection-ähnliche Zeichenfolgen usw.).
2. Das klassische Layout hat weiterhin die bisherigen
   Graphparameter und ist die Standardwahl.
3. Das moderne Layout verwendet feste linksbündige
   Koordinaten und kürzere Zeilen; Benutzertext taucht
   nicht direkt im Filtergraphen auf.
4. **Echte synthetische MP4s:** Klassisch mit Cut und
   Modern mit Fade, beide mit Titel/CTA, Markenfarbe
   und transparentem Firmenlogo. Modern zusätzlich
   mit Originalton. Dauer, Frame-Anzahl, Auflösung,
   Audiospuren sowie konkrete Pixelpositionen werden
   unabhängig geprüft.

**CI-Status: erfolgreich** – **184/184 automatische Tests grün**,
darunter die vier neuen Designvorlagen-Tests mit echtem
FFmpeg-Rendering und Farb-/Logo-Pixelprüfung.
GitHub-Actions Push-Lauf `45424555567` auf Commit
`7fdb81b1`: `unit-tests` erfolgreich, ebenso
die Staging-Abhängigkeitsprüfungen unter
Python 3.12 und 3.13.

## Noch offen

- [x] Designvorlagen mit sicherer Validierung im MP4-Export
- [x] Auswahlschalter in Streamlit und Cache-Signatur
- [x] Automatisierte Prüffälle hinzugefügt
- [x] GitHub-CI inklusive realem FFmpeg-Abnahmetest: 184 Tests grün
- [ ] **Echter Nutzer-Browser-Praxistest:** geschützte
      Streamlit-Test-App rebooten, Build-Label
      `Designvorlagen 1 | 2026-11-24` prüfen.
      Die bekannten 2 Landschaftsszenen mit
      gespeicherter Vorschau **ohne neue KI** laden;
      Titel/CTA und optional Blau `#245582` plus
      DEMO-Logo aktivieren, 0,5-s-Fade auswählen,
      **Modern (linksbündig)** als Designvorlage wählen,
      MP4 rendern und im Chat hochladen.
      Visuelle Differenz und vollständige Laufzeit
      unabhängig kontrollieren.
- [ ] **Browser-Cache-Test:** nach dem Modern-Export
      nur zur Designvorlage `Klassisch` wechseln,
      ohne erneut zu rendern. Die alte Vorschau
      darf nicht mehr als aktuell angezeigt werden.
- [ ] Weitere Layouts/Schriftarten, unterschiedliche
      Quellbilder, umfassende Social-Safe-Area-Tests,
      barrierearme Vorlagen und Freigabe vor Verkauf.

**Wichtig:** F2-02 Brand Kit bleibt als Gesamtpunkt
**offen**. Zwei sichere Textdesigns alleine machen
die Anwendung nicht automatisch verkaufsfertig.
