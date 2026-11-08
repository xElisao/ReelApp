# Phase 15: Transition-Fix 1 – Direkter Schnitt oder 0,5-s-Überblendung

**Stand:** 08.11.2026, geschütztes VeloCut-2.0-Staging.
Branch: `feature/velocut-2-video-analysis`, nicht `main`.

## Nutzerfunktion

Im Bereich **„🎬 Test-Reel als MP4 erstellen“** lässt sich
**„Übergang zwischen den Szenen“** auswählen:

- **Direkter Schnitt (Standard):** Die Szenen schließen unmittelbar
  aneinander an; keine überlappenden Frames. Das alte Verhalten bleibt
  als Default erhalten.
- **Weiche Überblendung (0,5 Sekunden):** Das Ende jeder Szene und der
  Beginn der folgenden Szene werden optisch während 0,5 s gemischt.
  Bei aktivierter Originalton-Option gehen auch die Tonspuren per
  0,5-s-Audioüberblendung ineinander über.

Die Szene-Reihenfolge (chronologisch, KI, manuell), schwarzer oder
unscharfer 9:16-Hintergrund und „Ohne Ton“/„Originalton übernehmen“
bleiben unabhängig wählbar.

**Keine zusätzlichen KI-API-Kosten.** Alle Übergänge werden lokal mit
FFmpeg aufgebaut.

## Dauer und Grenzen

Eine Überblendung *verkürzt* das Reel, da zwei benachbarte Clips sich
während des Übergangs überlappen.

`Reeldauer = Summe(Einzelclipdauern) - 0,5 s × (Clipanzahl - 1)`

Beispiele:

- Zwei Szenen à 3,0 s: direkter Schnitt 6,0 s; überblendet ca. 5,5 s.
- Drei Szenen à 3,0 s: direkter Schnitt 9,0 s; überblendet ca. 8,0 s.

Jeder Clip muss für eine weiche Überblendung **mindestens 1 Sekunde**
lang sein. Kürzere Clips sind für einen direkten Schnitt weiterhin
erlaubt (ab 0,25 s laut bestehendem Editor). Die UI meldet die
Bedingung und deaktiviert den Export bei Unterschreitung.

## Implementierung

`reel_export.py`:

- `transition_mode: Literal["cut", "fade"]` (String-Allowlist)
  als neuer optionaler Parameter von `render_test_reel`.
- Alle Clips werden auf 540×960, 24 fps, SAR=1, yuv420p und
  einheitliche Zeitbasis (`settb=AVTB`) normiert.
- `xfade=transition=fade:duration=0.5:offset=…` überlagert
  zwei oder drei Szenen. Der zweite Offset berücksichtigt die
  bereits verkürzte erste Überblendung.
- Bei `audio_mode="original"`: Audio wird wie bisher auf 48 kHz,
  stereo und die nominelle Clip-Länge normalisiert; fehlende
  Originaltonspuren werden mit lokaler Stille aufgefüllt.
  `acrossfade=d=0.5` verbindet die Tonspuren passend zum
  Videoübergang.
- `expected_reel_duration` berechnet die Soll-Laufzeit und prüft
  ungültige Übergänge und zu kurze Szenen **vor** teurer Verarbeitung.
- Unbekannte Übergangsnamen werden nicht in den FFmpeg-Graphen
  eingebaut (Whitelist). Kein Shell-Befehl aus Nutzereingaben.
- Original-KI-Vorschau, Timeline, einzelne bearbeitete Clips und
  die Shot-Cut-Prüfung bleiben unverändert.

`staging_app.py`:

- Neuer Radio-Button mit Standardwert „Direkter Schnitt“.
- Die voraussichtliche Reeldauer passt sich an die Übergangsauswahl
  an (2 Clips: 0,5 s Abzug, 3 Clips: 1,0 s Abzug).
- Die Auswahl fließt in die Export-Signatur ein: Nach Änderung des
  Übergangs ist eine vorherige MP4 nicht mehr als aktuelle sichtbar.
- Der Downloadname enthält `_cut.mp4` oder `_fade.mp4`.

## Tests

`tests/test_reel_transitions.py` prüft ohne KI:

- erwartete Dauer für zwei/drei Clips und Erhalt des Defaults;
- Ablehnung ungültiger Übergänge vor FFmpeg;
- kurze Szenen können nur direkt geschnitten werden;
- **echte FFmpeg-Integration:** rot-grün-Überblendung im 9:16-Blur-Reel,
  überlappende Farbmischung im Zentrum des Übergangs und kürzere
  Laufzeit im Vergleich zum direkten Schnitt;
- **drei** Clips rot-grün-blau in korrekter Reihenfolge,
  mit schwarzem Hintergrund;
- optische Überblendung synchron zu vorhandener Originaltonspur,
  gefolgt von stiller Szene;
- auch Clips ohne Ton lassen sich bei optional aktiviertem
  Originalton sicher überblenden.

Die vorhandenen Reel-, Audio-, Editor-, Zeitleisten- und KI-Pipeline-Tests
bleiben Teil des gleichen GitHub-Actions-Workflows.

## Manueller Test (ausstehend)

1. Streamlit-Test-App neu starten und
   **`Transition-Fix 1 | 2026-11-08`** prüfen.
2. Das bekannte 32-s-Landschaftsvideo und die gespeicherte
   `velocut_32s_ersatz_vorschau.json` **ohne neue KI-Analyse**
   zur Vorschau laden. Zwei Szenen sollten sichtbar sein.
3. Unter „🎬 Test-Reel als MP4 erstellen“ den Übergang
   **„Weiche Überblendung (0,5 Sekunden)“** wählen. Beide Clips
   zunächst unverändert lassen.
4. Chronologische Reihenfolge, Blur, ohne Ton auswählen;
   für 3+3 Sekunden wird eine Laufzeit von **ca. 5,50 s**
   angezeigt.
5. Reel exportieren, MP4 abspielen und hochladen.
   Prüfen, ob um 3 s herum die Bergstraße weich ins Bergtal
   übergeht, bei weiterhin korrektem Blur-Hintergrund.
6. Optional „Direkter Schnitt“ wählen, neu exportieren und
   den sichtbaren Unterschied vergleichen (ca. 6,0 s).
7. Ein Browser-/Nutzer-Praxistest muss nach grüner CI noch
   eigens bestätigt werden.
