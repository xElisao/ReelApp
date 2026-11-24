# Phase 20 – Wettbewerbs- und Produktlückenmatrix (Desk Research)

**Stand: 15.11.2026**. Öffentliche Anbieterinformationen, keine bezahlten
Testkonten, keine unabhängigen Produkt-Benchmarks. Angaben auf Pricing-
und Produktseiten können wechseln und sind kein Garantie-Nachweis.
**Keine Ansprache von Betrieben, keine Kundendaten verarbeitet.**

## Leitfrage

Welche Funktionen sollte das interne **VeloCut-2.0-Labor**
für ein erstes bezahlbares Produkt ausbauen, wenn allgemeine
KI-Clip-Editoren und branchenspezifische Immobilienvideo-Tools
bereits konkurrieren?

## I. Konkurrenz im Überblick (Quellen direkt vom Anbieter)

| Anbieter / Typ | Dokumentierte Funktionen / Segment | Preisanker zum Recherchezeitpunkt |
|---|---|---|
| OpusClip / allgemeiner KI-Clip-Editor | Automatische Auswahl aus Video, AI-Reframe, Captions, visuelle/akustische Clip-Erkennung in bezahlten Tarifen, Video-/Timeline-Editing, Brand Templates | Starter 15 USD/Monat; Pro 29 USD/Monat (bei Monatsabrechnung; Preise regional und je Abrechnung abweichend) |
| Submagic / allgemeiner & Immobilien-Editor | Auto Captions, Hook Title, B-Roll, Übergänge, Auto-Edit, Immobilien-Workflows, 1080p im Starter-Tarif | Starter 19 €/Monat; Pro 39 €/Monat; Business 69 €/Monat (monatliche Euro-Preise laut Seite; Produktseite teils unterschiedliche Währung/Varianten) |
| Reel-E / Immobilien aus Fotos | Immobilienfoto-Upload → Videos in 9:16, 16:9, 1:1 mit Branding, Listing-Website, Stimme, Videoeditor. Laut Dokumentation **keine** eigenen Video-/Drohnenclips als Input | Essential 59 USD/Monat bei Monatszahlung bzw. 44 USD/Monat bei Jahreszahlung |
| AutoReel / Immobilien aus Fotos | Automatisierte Videos aus Immobilienfotos, Photo-Edits/Staging, Vorlagen und jährliche Video-Kontingente | Essential ab etwa 30 USD/Monat, Jahreslaufzeit; Preise und jährliche Credits prüfen |
| Kadapt / Immobilien aus Fotos | Listingfotos → Skript, Logo, Reel, Voiceover, Planung; AI Motion optional mit generiertem Bildinhalt | Starter 14,99 USD/Monat; Solo 49 USD/Monat |
| VideoMotion / Immobilien aus gefilmten Rundgängen | Vorhandene Walkthrough-Videoaufnahmen, Raumerkennung, Geschwindigkeitsbearbeitung, 1080p, Branding, hoch/quer | Preis hier nicht belastbar ermittelt |
| Shorty / allgemeiner Prompt-Editor, Immobilien-Workflow | Rohclips **und** Fotos, Anweisung per Text, MP4, spezielle Vorlagen für Immobilientouren | Ab 19 USD/Monat laut Anbieter |
| Reslate / Immobilien-Profiproduktion | Rohfilmmaterial (einschließlich Kamera-Metadaten), automatische Bewertung und Vorbereitung für DaVinci/Final Cut | Preis hier nicht belastbar ermittelt |

Primärquellen:
- https://www.opus.pro/pricing
- https://www.submagic.co/de/preisgestaltung
- https://www.submagic.co/solutions/real-estate
- https://www.reel-e.ai/docs/billing/plans
- https://www.reel-e.ai/pricing
- https://www.autoreelapp.com/pricing
- https://kadapt.com/real-estate/
- https://www.videomotion.studio/
- https://shortyedit.com/real-estate
- https://reslate.ai/

**Wichtige Korrektur unserer bisherigen Produktthese:** Die Nische
„Immobilien-Reels aus schon gefilmtem Rohmaterial“ ist **nicht**
unbesetzt. Neben Foto-zu-Video-Diensten gibt es mindestens
VideoMotion, Shorty und Submagic mit entsprechenden Angeboten.
**Nicht** mit „einzige Lösung für Immobilienrohdaten“ werben.
Auch visuelle KI-Clip-Erkennung an sich ist bei OpusClip beworben.

## II. Funktions-Lückenmatrix für VeloCut (Stand Labor)

Legende: **✅ vorhanden/getestet**, **⚠️ teilweise oder nur Labor**,
**❌ fehlt**. Spalten zeigen keine unabhängige Bewertung der Konkurrenz.

| Anforderung / Nutzen | VeloCut heute | Markt-/Konkurrenzsignal | Empfehlung |
|---|---|---|---|
| Visuelle KI-Analyse *tatsächlicher Frames* und Wunschtext | ✅ als Labor | OpusClip bewirbt visuelle Clip-Erkennung; viele Tools nutzen Prompts | Behalten, aber nicht als Exklusivmerkmal |
| Shot-Grenzen, schonende Auswahl, manuelle Timeline | ✅ in Labor; auf bis zu 3 Clips begrenzt | Allgemeine Editoren bieten Timeline; Schutz vor unsauberen Cuts ist nützlich | Kernqualität messen und ausbauen |
| Vorschau und Feinschnitt **ohne neue KI-Analyse** | ✅ in Labor | Wettbewerber haben Re-Editing, Abrechnung/Cache oft nicht transparent | Vorteil als nachprüfbares Kosten-/Kontrollversprechen ausbauen |
| Fertiges Reel statt Rohclip-Montage | ❌ Titel/CTA/Branding fehlen | Wettbewerber liefern Branding, Texte und Abschlusskarten | **Prio 1** für erste publish-ready Demo |
| Branchenspezifische, überprüfbare Story-Reihenfolge | ⚠️ Wunsch + Ranking, aber kein vollständiger Branchen-Storyplan | Kadapt/Reel-E und Prompt-Editoren bieten schon Pläne | **Prio 1**, als einfacher Ablauf statt Feature-Claim |
| 1080×1920 & FPS/Audio-QA | ❌ Labor exportiert 540×960, 24 fps | 1080p ist etablierter Mindestwert | **Verkaufsblocker**, nach Demo als Technikgate |
| 9:16 Motiv-Autoframing | ⚠️ Blur/letterbox, kein Tracking | OpusClip/Submagic/VideoMotion bearbeiten Hochkant | **Prio 2**, an Objektgenauigkeit prüfen |
| Untertitel bei gesprochenem Inhalt | ❌ | Standard bei OpusClip/Submagic | **Prio 2**, für stumme Objektvideos nicht zwingend |
| Mehrere Varianten aus derselben Analyse | ⚠️ manuelle Änderungen möglich, aber kein Variantenknopf | Verschiedene Ausgabevarianten bei Spezialisten | **Prio 2**, wenn Kundenstil klar ist |
| Echte Fotos zusätzlich zu Video-Uploads | ❌ | Viele Immobilienlösungen starten sogar ausschließlich aus Fotos | Später anhand vorhandener Kundendaten entscheiden |
| Direkte Social-Posts / Scheduler | ❌ | Schon etabliert bei OpusClip/Submagic | **Nicht MVP**, Download reicht |
| Benutzerkonten, Isolation, Löschung, Datenschutzhinweise | ❌ nur geschütztes Labor; alte E-Mail-only-Live-App | Für zahlende Kunden Mindestvoraussetzung | **Vor Kunden-Uploads zwingend** |
| Hosting und gleichzeitige Jobs | ❌ nur Laborexporte auf Community Cloud | Verkaufs- und Datenschutzrisiko | **Vor Kunden-Uploads zwingend** |
| Günstige, transparente Nutzung pro Projekt | ⚠️ Wiederverwendung lokaler Clips | Konkurrenz mit Credits/Minuten/Videos | Feature nach **echter Kostenmessung** auspreisen |

## III. Positionierungskandidat

> **„Aus echten Aufnahmen in wenigen Schritten ein fertiges
> Immobilien- oder Unterkunfts-Reel, mit kontrollierbarer KI-Auswahl –
> und ohne erneute KI-Analyse bei jedem Feinschnitt.“**

Nicht beanspruchen: einzigartige KI-Videobearbeitung, garantierte
Leads/Buchungen oder „viral“, unrealistische Ein-Klick-Automation,
faktische Richtigkeit von KI-generierten Immobilienattributen.

**Möglicher Differenzierungstest:**
- Originale, echte Videos werden verwendet statt Eigenschaften
  in generierten Innenräumen zu verändern (solange keine generative
  Videoerzeugung hinzugefügt wird).
- Anstatt nur ein abstraktes Video zu erzeugen, bekommt der Nutzer
  eine verständliche Auswahl, klare Einstiegs-/Highlight-/Schlussstruktur,
  manuell korrigierbare Schnittgrenzen und mehrere Ausgaben aus
  derselben Analyse.
- Branchenspezifische Vorlagen mit sichtbarer Faktengrenze:
  Titel/Texte aus **Nutzerangaben**, keine erfundenen Größen,
  Ausstattungsmerkmale oder Preisangaben.

Diese Punkte sind **Positionierungshypothesen** und müssen technisch
und am späteren Kundenergebnis überprüft werden.

## IV. Entwicklungsempfehlung / Reihenfolge

1. **Demo-Funktion 1: Text-/CTA-Overlay für Reels**
   - Lokaler FFmpeg-Overlay auf 540×960-Labor-Export,
     später 1080×1920.
   - Ein-/ausblendbare optionale Textfelder (Titel, Schlusszeile,
     optionale Fakten), begrenzte Eingabelänge, Schriftart lizenzierbar.
   - Safe-Zones für Social-UI, gute Lesbarkeit, korrektes Escaping
     aller Texte; keine Shell-Kommandos aus Benutzereingaben.
   - Keine neue KI-Analyse für Textänderung.
   - Drei Testfälle: Video ohne Titel; mit Titel/CTA;
     Titel mit Umlauten/Sonderzeichen; neue Signatur bei Textwechsel.
2. **Demo-Funktion 2: Story-Vorlage mit 3 Schritten**
   - „Einstieg – Hauptmerkmal – Abschluss“ und Nutzerpräferenzen;
     nur bereits geprüfte Clips neu ordnen, keine erfundenen Fakten.
   - Für Immobilien- und Unterkunftsbeispiel.
3. **Abnahme Demo:** zwei fiktive Branchenreels aus
   eigenem oder eindeutig lizenziertem Material,
   keine personenbeziehbaren Kundendaten auf Community Cloud.
4. **Vor zahlenden Kunden:** sichere Anmeldung, Dateispeicherung,
   Löschung/Hosting, 1080p, Nutzungsquoten, Belastbarkeit,
   Recht/Checkout, Markenfreigabe.
5. **Kundennachweis später:** 5–10 freiwillige Pilotnutzer auf
   datenschutzkonformer Infrastruktur. Nicht im Laborexperiment
   als Verkaufsreife missverstehen.

## V. Checklistenstatus

- [x] Anbieter recherchiert, aktuelle Produktseiten und Preise
      geprüft; Grenzen und Anbieterwerbung kenntlich gemacht.
- [x] Feature-Lücken gegen **aktuelle Laborfunktionen** verglichen.
- [x] Zwei Branchenideen (Immobilie/Unterkunft) differenziert.
- [x] In Demo 1 Texteinblendungen technisch ergänzen (**Text-Overlay 1**, 15.11.2026; 172 Tests, auch echte FFmpeg-MP4-Tests; **Browser-Praxistest noch offen**).
- [ ] In Demo 2 Branchenstory erstellen.
- [ ] Beide Demos von Anfang bis Ende mit echten, rechtmäßig
      nutzbaren Testvideos abnehmen.
- [ ] Kundennachweis nach Datenschutz-/Hostingfreigabe.

**Nächster Schritt:** Geschützte Streamlit-App neu starten und die implementierte
**Titel-/Schlusszeilen-Einblendung** mit der gespeicherten Landschaftsszenen-Vorschau
ohne neuen KI-Aufruf im Browser testen. Details:
[PHASE21-REEL-TITEL-CTA.md](PHASE21-REEL-TITEL-CTA.md).
