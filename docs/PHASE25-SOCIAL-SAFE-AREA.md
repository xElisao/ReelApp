# Phase 25 – Instagram/TikTok-Schutzbereich für Text und Logo

**Datum:** 24.11.2026; ausschließlich geschützte Branch
`feature/velocut-2-video-analysis` / Streamlit-Test-App.
**Produktives `main`, Checkout und Kundendaten unverändert.**

## Ziel

In Instagram Reels und TikTok liegen App-Bedienelemente
oben, unten und rechts über dem eigentlichen 9:16-Video.
Titel, Handlungsaufforderung (CTA) und Markenlogo
sollen deshalb optional in einem vorsichtig gewählten
zentralen Bereich angeordnet werden.

Die konkrete App-Oberfläche hängt von Gerät, Plattform,
Beschriftungslänge und Anzeigenformat ab. **Kein Versprechen,
dass ein und dieselbe Position in jeder Ansicht garantiert
frei bleibt.** Die fertige MP4 vor Veröffentlichung auf dem
Zielgerät / in der Plattformvorschau prüfen.

## Quellen und konservativer Bereich

**Meta / Instagram Reels (Ads Guide, Stand Nov. 2026):**
ungefähr **14 % oben**, **35 % unten** und **6 % an
beiden Seiten** frei von wichtigen Texten und Logos lassen.

**TikTok (Auction In-Feed Ads, Juni 2026):** Safe-Zone-
Dateien sind abhängig von Hochkant-/Querformat,
Zeilenzahl der Anzeige und Zusatzformaten. Bei 9:16
Kopfzeile, unterer Beschriftungsbereich und rechte
Aktionsleiste beachten. Die offizielle Hilfe erklärt,
dass die Live-Ansicht je nach Gerät anders aussehen kann.

Für unsere Laborgröße **540 × 960** wird bewusst
ein konservativer **gemeinsamer Korridor** verwendet:

| Kante | Koordinate in Export |
|---|---:|
| Links | x = 60 |
| Rechts | x = 390 (rechts 150 px freihalten) |
| Oben | y = 145 |
| Unten | y = 615 (unten 345 px freihalten) |

Die zusätzliche rechte Freifläche ist absichtlich
**größer** als Metas Seitenempfehlung, da dort
Interaktionssymbole und Werbung erscheinen können.
Für andere TikTok-Captionlängen und Platzierungen
ist das eine **Vorsichtsmaßnahme**, keine garantierte
Norm-/Plattformzertifizierung.

Offizielle Hinweise:
- Meta Instagram Reels Ad Specifications:
  https://en-gb.facebook.com/business/ads-guide/update/video/instagram-reels
- TikTok Auction In-Feed Ads, Safe Zone und
  Download-Dateien:
  https://ads.tiktok.com/resources/help/article/tiktok-auction-in-feed-ads?lang=en-GB

## Benutzeroberfläche

Neuer Schalter bei der Erstellung des Test-Reels:

**`📱 Instagram & TikTok (optional)` →
`Texte und Logo vor App-Schaltflächen schützen`**

- Voreinstellung **ein** (künftige neue Reels damit
  vorsichtiger angeordnet).
- Wer die bisherigen exakten Layoutpositionen möchte,
  kann den Haken **ausschalten**.
- Auch bei **Logo ohne Text** wird das Logo in den
  sicheren Bereich geschoben.
- Der Schalter ist in der **Reel-Cache-Signatur**.
  Beim Ein-/Ausschalten darf keine alte Video-Vorschau
  als aktuelle MP4 erscheinen.
- Neue Downloadnamen bei aktivem Schutzmodus enthalten
  `_social`; weder neue OpenAI-Anfragen noch
  zusätzliche KI-Kosten.
- Versionskennung:
  **`Social-Schutzbereich 1 | 2026-11-24`**.

## FFmpeg-Rendering und Sicherheit

In `reel_export.py`:
- `safe_area_mode` strikt auf `"off"` und
  `"social"` eingeschränkt, Standard `"off"`
  für bestehende Python-Aufrufer (**Abwärtskompatibilität**).
- Bei ausgeschaltetem Schutz bleiben Klassisch/
  Modern und die alte Logo-Position unverändert.
- Bei aktivem Schutz:
  - PNG-Logo innerhalb des Bereichs auf **x=72, y=152**
    (auf maximal 144×88 Pixel normalisiert).
  - Titel unterhalb des Logos:
    Klassisch **y=272**, Modern **y=285**;
    textbezogene Pixelbreiten werden mit derselben
    installierten DejaVu-Schrift via Pillow gemessen,
    dann in Zeilen von höchstens **280 Pixel** umgebrochen.
  - CTA am mittleren unteren Rand:
    Klassisch **y=600−text_h**, Modern **y=595−text_h**,
    ohne UI-kritischen unteren Rand.
  - Schriftgrößen 27 bzw. 26 Pixel, Rahmenbreite 10,
    Zeilenabstand 5. Klassisch im zentralen Korridor
    zentriert, Modern linksbündig bei x=72.
  - Bei mehr als 7 Zeilen wird mit verständlicher
    Meldung abgebrochen, statt unsichtbaren Text zu
    erzeugen. Sämtliche Benutzertexte bleiben wie
    zuvor validiert in temporären UTF-8-Textdateien;
    keine Nutzereingabe direkt in FFmpeg-Filtercode.
- Titel/CTA werden nur innerhalb ihrer bisherigen
  jeweils etwa 2 Sekunden angezeigt. Das Logo bleibt
  während des gesamten Reels sichtbar.
- Farbe, Audio, Übergänge, MP4-Laufzeit sowie
  übrige Videoverarbeitung bleiben unverändert.

## Test und Abnahme

Neue Datei `tests/test_reel_social_safe_area.py`:

1. Nur `"off"` / `"social"` werden vor FFmpeg
   zugelassen, keine Filter-Injection über den Parameter.
2. Ohne Schutz entspricht der Graph genau dem
   vorherigen Verhalten.
3. Textumbruch mit echter Font-Pixelmessung,
   beide Vorlagen und alle festen Schutzpositionen.
4. **Echte synthetische MP4-Exports** mit
   Farbe + Titel + CTA + Logo + 0,5-s-Fade,
   mit/ohne Audio, Klassisch und Modern.
   Exakte Videolänge/Bildanzahl, Positionierung und
   reservierte Bereiche werden kontrolliert.

**CI erfolgreich:** **188 von 188 Tests** (184 bestehende +
vier neue Social-Schutzbereich-Tests). GitHub-Actions-
Push-/PR-Läufe auf Commit `d55d410d` erfolgreich,
insbesondere `unit-tests` mit echten FFmpeg-Exports
für Klassisch/Modern, Markenfarbe und Logo.
Staging-Abhängigkeiten Python 3.12/3.13 ebenfalls grün.
Der nachfolgende Testpositions-Fix `9ab31ec5`
ändert ausschließlich die Prüfstelle im Testbild.

## Browser-Abnahme noch offen

- [x] Schutzbereich im FFmpeg-Export und sichere Platzierung
- [x] Schalter in Test-App, Default ein, Cache-Signatur
- [x] Automatisierte Tests angelegt
- [x] GitHub CI: 188/188 Tests und Python 3.12/3.13 grün
- [ ] **Echter Nutzer-MP4-Test:** Geschützte Streamlit-App
      rebooten; oben `Social-Schutzbereich 1 | 2026-11-24`
      prüfen. Bestehende zwei Landschaftsclips mit
      gespeichertem Vorschau-JSON ohne neue KI laden,
      Modern, Blau `#245582`, Titel
      `Bergstraßen entdecken`, Schlusszeile
      `Mehr entdecken`, DEMO-PNG, 0,5-s-Fade,
      Schalter für den Schutzbereich **ein**.
      Exportierte MP4 im Chat bereitstellen.
      Wir prüfen Bildpositionen und die **132 Frames**.
- [ ] **Browser-Cache-Test:** Nach erfolgreichem
      Social-Export nur den Schutzbereich **ausschalten**,
      **ohne** neu zu exportieren. Alte Vorschau
      muss verschwinden.
- [ ] Auf mindestens einem echten Instagram- und
      TikTok-Gerät mit unterschiedlichen Captions
      und Anzeigenformaten ansehen; umfassende
      Produktions-/Verkaufsfreigabe steht weiter aus.

**F2-02 Brand Kit bleibt offen.** Auch dieser
Teilschritt ist kein öffentlicher Launch.
