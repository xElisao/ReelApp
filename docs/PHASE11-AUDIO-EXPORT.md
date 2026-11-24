# Phase 11: Originalton optional im Test-Reel (Audio-Export 1)

**Stand:** 08.11.2026. Ausschließlich geschütztes Staging auf
`feature/velocut-2-video-analysis`. Kein Merge nach `main`.

## Ziel und Umfang

Der Nutzer möchte **erst die technischen Grundfunktionen des Video-Tools
fertigstellen** und danach eine strukturierte Datenschutz-/Rechtsprüfung
für den öffentlichen Betrieb durchführen. Die rechtliche Freigabe wird
dadurch **nicht** vorweggenommen.

Das Feature ist bewusst klein und reversibel:

- Im Reel-Export kann zwischen **„Ohne Ton (Standard)“** und
  **„Originalton übernehmen“** gewechselt werden.
- Wenn Originalton gewählt wurde, wird nur die Tonspur aus den
  **bereits lokal erstellten Vorschau-MP4s** verwendet. Keine
  zusätzlichen OpenAI-Aufrufe, kein Transkript, keine Sprecheranalyse
  und keine Musikbibliothek.
- Clips ohne Audio werden durch stille Abschnitte gleicher Länge
  aufgefüllt, damit nachfolgender Ton synchron bleibt.
- Ton wird mit FFmpeg auf Stereo/48 kHz normalisiert und als AAC im
  MP4 mit dem Video der beiden bis drei ausgewählten Clips verbunden.
- Die bisherigen Bildschirmformate `blur` und `black` funktionieren
  unverändert.
- Der Streamlit-Exportschlüssel berücksichtigt jetzt auch `audio_mode`.
  Beim Wechsel zwischen stumm und Originalton erscheint deshalb keine
  irrtümlich gecachte Version der anderen Option.

## Technische Grenzen

- Es gibt **keine Lautstärken-Normalisierung, Musik-Einblendung,
  Audio-Ducking, Sprachuntertitel oder Übergangseffekte**.
- Ausgangston und -musik können Rechte Dritter oder private Gespräche
  enthalten; der originale Ton wird ungefiltert übernommen. UI weist
  ausdrücklich darauf hin, nur eigene oder freigegebene Tests zu nutzen.
- Die Option ist ein technischer Prototyp, **keine
  datenschutzrechtliche/urheberrechtliche Freigabe**.
- Die vorhandene Zugriffssperre des Staging-Labors bleibt erhalten.
  Datenschutz durch Gestaltung (keine unnötige Audioanalyse,
  Standard stumm) ist bereits jetzt sinnvoll, die abschließende
  Dokumentation und Prüfung ist ein separates Freigabethema.

## Technische Prüfungen

`tests/test_reel_export.py` simuliert echte Medien durch FFmpeg:

1. Ein Clip mit 450-Hz-Testton und ein zweiter Clip ohne Audio.
   Prüfung auf AAC-Spur, Audiowellen im ersten und Stille im zweiten
   Segment und korrekte Gesamtvideodauer.
2. Dieselben Clips im unveränderten Default **ohne Audio-Spur**.
3. Zwei vollständig stumme Clips bei aktivierter Originaltonoption
   ergeben trotzdem einen funktionsfähigen MP4-Export.
4. Nicht erlaubte Audio-Moduswerte werden vor FFmpeg zurückgewiesen.
5. Bereits vorhandene Tests bleiben für Bildgestaltung und Grenzwerte
   bestehen. Kein API-Zugriff in Tests.

## Manuelle Prüfung

**Wichtig:** Der bisherige 32-s-Landschaftstest kann selbst stumm
sein. Die Einstellung „Originalton“ erzeugt keinen Ton aus einer
stummen Aufnahme. Daher zuerst nur prüfen, ob die Option funktioniert;
für hörbaren Audio-Test später ein eigenes kurzes Video **mit hörbarem
Originalton** und passenden Szenen verwenden.

1. Staging neu starten und Versionslabel
   `Audio-Export 1 | 2026-11-08` prüfen.
2. 32-s-Landschafts-Testclip und gespeicherte Ersatz-JSON im
   *kostenlosen* Vorschau-Bereich erneut laden.
3. Zwei gültige Szenen im Reel-Export auswählen.
4. Bei „Ton im fertigen Reel“ zwischen „Ohne Ton (Standard)“ und
   „Originalton übernehmen“ wechseln, Reel jeweils erneut erstellen.
5. Prüfen, dass die zweite Option die korrekte Datei herunterlädt und
   Bild/Spielbarkeit erhalten bleiben.

## Noch vor einer öffentlichen Freigabe

Gesonderter Prüf- und Freigabeblock: Datenfluss- und Hostinginventar,
Empfänger/Auftragsverarbeitung, rechtliche Grundlage für Videos mit
Dritten, Veröffentlichung/Urheberrechte, Transparenz,
Speicher- und Löschkonzept, Betroffenenrechte, Zugriffssicherheit,
Datenschutzerklärung/Nutzungsbedingungen. Diese Punkte sollen nicht
einer laufenden öffentlichen Verarbeitung ungeprüfter Personendaten
nachgelagert werden; hier entwickeln wir auf der geschützten Testinstanz.
