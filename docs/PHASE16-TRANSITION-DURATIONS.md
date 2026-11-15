# Phase 16 – Transition-Fix 3: Überblendungsdauer auswählen

**Stand:** 13.11.2026, nur geschützte Staging-App auf
`feature/velocut-2-video-analysis`. `main` bleibt unverändert.

## Nutzerziel

Die vorher starre 0,5-Sekunden-Überblendung soll flexibel werden.

Im Bereich **„🎬 Test-Reel als MP4 erstellen“** gibt es weiterhin
die Auswahl **„Direkter Schnitt (Standard)“** oder **„Weiche Überblendung“**.
Nach Auswahl der weichen Überblendung erscheint
**„Dauer der weichen Überblendung“** mit drei Möglichkeiten:

- **0,25 Sekunden**: zügiger Szenenübergang,
- **0,50 Sekunden**: bisheriger Standard,
- **1,00 Sekunde**: langsamer, deutlicher Übergang.

Beim direkten Schnitt gibt es keine Dauer-Auswahl; das alte Verhalten
bleibt vollständig erhalten.

## Technisches Verhalten

- `reel_export.py` akzeptiert `fade_duration_seconds` zusätzlich zu
  `transition_mode`, Standardwert ist **0,5 Sekunden**, damit bestehende
  Aufrufer weiter funktionieren.
- Nur `0.25`, `0.5` und `1.0` sind zugelassen. Andere Zahlen
  (`nan`, `inf`, `True`, Strings usw.) werden **vor FFmpeg** abgelehnt.
- Der ausgewählte Wert steuert beide FFmpeg-Filter:
  `xfade=transition=fade:duration=...` für Bild und
  `acrossfade=d=...` bei aktivierter Originalton-Ausgabe.
- Die zweite Überblendung in einem Reel mit **drei** Szenen
  berücksichtigt die verkürzte Laufzeit des ersten Übergangs.
- Alle Szenen müssen mindestens **doppelt so lang wie die gewählte
  Überblendung** sein, damit auch eine mittlere Szene zwei
  Übergänge tragen kann: also mindestens 0,50 / 1,00 / 2,00 Sekunden.
- Das MP4-Reel wird durch zeitliches Überlagern kürzer:

  `Reelzeit = Summe der Szenendauern - Überblendungsdauer × (Szenenanzahl - 1)`

  Bei zwei Szenen à 3 Sekunden sind das 5,75 / 5,50 / 5,00 Sekunden.
- Die voraussichtliche Laufzeit wird in der Benutzeroberfläche
  für die gewählte Dauer **vor dem Rendern** angezeigt.
- Die Einstellung fließt in die Export-Signatur ein: Wenn man die
  Dauer ändert, wird ein vorheriges Reel nicht fälschlich als aktuell
  angezeigt. Der MP4-Dateiname enthält die Übergangszeit
  (`_fade_025cs`, `_fade_050cs`, `_fade_100cs`).
- Das FFmpeg-7-CFR-Fix `settb=AVTB,fps=24` aus
  **Transition-Fix 2** bleibt in beiden Hintergründen aktiv.
- Die Funktionen zur visuellen Zeitleiste, der isolierten
  Schnittvorschau und der Shot-Cut-Prüfung bleiben unverändert.
- Keine neuen OpenAI-Aufrufe und keine zusätzlichen KI-Kosten.

## Tests

`tests/test_reel_transitions.py` prüft weiterhin alle alten
Übergangs-/Audio-/Hintergrundtests und zusätzlich:

- korrekte Formeldauer für zwei und drei Szenen bei allen drei Optionen;
- den Standard von 0,50 Sekunden für bisherige Aufrufer;
- Whitelist und ungültige Zahlen vor FFmpeg;
- unterschiedliche Mindest-Szenendauern;
- exakte `xfade`-Offsets und `acrossfade`-Dauern für zwei
  Übergänge bei einem Dreiszenen-Reel;
- echte FFmpeg-Exporte der drei Überblendungszeiten mit visueller
  Farbmischung und Originalton/Silence-Fallback;
- echte Dreiszenen-Reels bei 0,25 und 1,00 Sekunden.

## Manueller Browser-Test – noch offen

1. Geschützte Streamlit-Test-App neu starten. Versionslabel
   **`Transition-Fix 3 | 2026-11-13`** prüfen.
2. Bekannte 32-s-Landschaftsdatei und gespeicherte
   `velocut_32s_ersatz_vorschau.json` ohne neue KI-Analyse importieren.
3. Im Reel-Exportbereich auf **„Weiche Überblendung“** schalten.
   Es erscheint **„Dauer der weichen Überblendung“** mit drei Auswahlwerten.
4. Beide unveränderten 3-s-Szenen wählen, chronologische Reihenfolge,
   Blur, ohne Ton. Beginnen mit **1,00 Sekunde**.
   Erwartete Laufzeit: **5,00 Sekunden**.
5. MP4 exportieren, abspielen, Datei hochladen und die
   Überblendung visuell prüfen.
6. Danach kann die Dauer auf 0,25 Sekunden geändert werden, sodass
   die alte MP4 nicht als aktueller Export sichtbar bleibt.
   Neuer Export sollte rund 5,75 Sekunden lang sein.

**Automatische CI-Prüfung und Browser-Nutzertest getrennt dokumentieren;
eine erfolgreiche CI ersetzt keinen Browser-Praxistest.**
