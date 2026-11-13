# VeloCut – Master-Checkliste bis zum ersten zahlenden Kunden

**Stand: 13. November 2026.** Gilt für den geschützten Entwicklungszweig
`feature/velocut-2-video-analysis`. Keine automatischen Änderungen an
`main` oder bestehenden Zahlungseinrichtungen.

## Produktthese

**Nicht** ein allgemeiner Videoeditor mit möglichst vielen Effekten.
**Sondern:** Aus Rohvideo in wenigen Schritten ein veröffentlichungsfertiges
Social-Media-Reel, mit nachvollziehbarer KI-Szenenauswahl und Feinschnitt
**ohne wiederholte KI-Kosten**.

**Arbeitshypothese für die erste Zielgruppe:** kleine Ferienunterkünfte,
Tourismusbetriebe und Hotels in der DACH-Region. Die Hypothese vor
großem Featureaufwand mit 10 Gesprächen und 5 Praxispiloten prüfen.
Spätere Segmente: Immobilien, lokale Dienstleister, Agenturen.

## Baseline / bereits bestätigt

- [x] Kostenpflichtige, inhaltlich-visuelle KI-Szenenanalyse (geschütztes Labor)
- [x] Shot-Grenzen-Prüfung, Auswahl und Ranking
- [x] Visuelle Timeline, manuelles Anpassen und Vorschau ohne neue KI-Kosten
- [x] 9:16-MP4-Export H.264 mit Blur- oder schwarzem Hintergrund
- [x] 2–3 Szenen, harte Schnitte oder 0,25/0,50/1,00-s-Crossfade
- [x] Optionaler Originalton und stummer Standardexport
- [x] Automatisierte Tests (167) sowie reale Nutzer-MP4-Exports aller drei Blenden

**Bisherige Laborgrenzen:** max. 3 Uploads, max. 60 Sekunden je Quellvideo,
max. 80 MB je Datei / 160 MB gesamt, Vorschau-/Reel-Export
540×960, max. 3 Szenen und 30 Sekunden Reel. Das ist **kein**
vollständiger kommerzieller Editor.

**Bestehendes `app.py` ist NICHT das neue Labor:** Enthält eine alte
14,99-€-Einmal-/„unbegrenzt“-Paywall mit einem
E-Mail-only-Pro-Login und lokaler SQLite-Datenbank.
Diesen Zahlungs- und Anmeldepfad nicht ungeprüft in den Verkauf übernehmen.

## Phase 0 – Entscheidungen und Risikosperren (vor externem Bezahlen)

- [ ] **P0-01 Marke/Name (Recherche begonnen 13.11.2026; Rechtsfreigabe ausständig):** Aktives Open-Source-KI-Videoschnittprojekt
  `open-ribbi/velocut` mit nahezu identischem Namen prüfen. Identische
  Schreibweise bedeutet noch nicht nachgewiesene Markenverletzung;
  Recherche in österreichischem Markenregister, TMview, EUIPO,
  Domains/Handelsnamen, ggf. juristische Freigabe oder neues Branding.
  **Abnahme:** eindeutiger Name mit dokumentierter Recherche; vor
  Logo, Anzeigen, Domainkauf, Markenanmeldung.
  **Recherchenotiz 13.11.2026:** Identische Produktbezeichnung bei
  `open-ribbi/velocut` bestätigt. Vorläufige Bewertung: hohe
  praktische Verwechslungsgefahr; juristische Bewertung offen.
  Amtliche Registerzugänge geprüft, aber keine abgeschlossene
  Suchabfrage zu identischen/ähnlichen Marken. Noch **nicht abhaken**.
  Arbeitsdokument: [PHASE17-NAME-MARKENRECHERCHE.md](PHASE17-NAME-MARKENRECHERCHE.md).

- [ ] **P0-02 Zahlungsrisiko:** Altes einmaliges „unbegrenztes“ Angebot
  (14,99 €) und E-Mail-only-Login nicht als neue Verkaufsbasis verwenden.
  Vor weiteren echten Zahlungen aktuellen Checkout, Altbestellungen,
  Leistungsversprechen und Verpflichtungen prüfen.
  **Abnahme:** klare Altbestands-/Migrationsentscheidung, keine
  unauthentifizierte fremde Kontenfreischaltung.
- [ ] **P0-03 Marktgespräche:** 10 reale Gespräche mit der Startnische.
  Typische Rohvideos, Post-Häufigkeit, vorhandene Tools, Schmerz,
  Zahlungsbereitschaft, Datenschutzbedenken erfragen.
  **Abnahme:** mindestens fünf passende Pilotkandidaten und
  klare Top-3-Aufgaben; kein vorab unterstellter Product-Market-Fit.
- [ ] **P0-04 Hosting-Entscheidung:** Keine kommerzielle Verarbeitung
  personenbezogener Videos auf Streamlit **Community Cloud**; die
  Community-Cloud-Bedingungen untersagen personenbezogene Inhalte für
  kommerzielle Zwecke. Bezahltes Hosting mit passendem AVV/DPA,
  bevorzugt EU-Region wählen; Streamlit kann als Oberfläche zunächst
  weiterlaufen. **Abnahme:** Vertrags-/Datenschutzcheck und
  belastbarer Staging-/Produktionsbetrieb.
- [ ] **P0-05 Echte Kosten ermitteln:** OpenAI-Analyse je
  Quellvideominute, CPU/GPU-Renderzeit, Speichervolumen, Versand,
  Zahlungsgebühren und Support durch 20 Testjobs messen.
  **Abnahme:** Kosten pro zahlendem Nutzer/Export nachvollziehbar.

## Phase 1 – Unverzichtbare Technik für Fremdkunden (Verkaufsblocker)

- [ ] **T1-01 Ein Produkt:** KI-Labor und bisherige Live-App zu einem
  einheitlichen, getesteten Endnutzerablauf zusammenführen; kein
  paralleles „Legacy gegen 2.0“ für Käufer.
  **Abnahme:** Upload → Wunsch → Vorschläge → Feinschnitt → Export
  ohne JSON-Zwischenschritt oder Entwicklerpasswort.
- [ ] **T1-02 Sichere Konten:** individuelle Identitäten via
  passwortloser E-Mail-Link/OAuth und serverseitige Berechtigungsprüfung;
  niemals allein durch Angabe einer fremden Bezahl-E-Mail einloggen.
  **Abnahme:** zwei Testkonten können gegenseitig keine Videos,
  Rechnungen oder Exporte sehen.
- [ ] **T1-03 Sichere Videoablage:** private und isolierte Speicherung,
  Zugriffstoken, Größenlimits, temporäre Files, automatische Löschung,
  manueller Löschknopf und robuste Fehlerbereinigung.
  Keine sensiblen Videometadaten in Logs.
  **Abnahme:** Löschung funktioniert end-to-end und bleibt nach
  Prozessabbruch wirksam; kein öffentlicher Downloadlink.
- [ ] **T1-04 Belastbare Jobs:** Hintergrundverarbeitung/Jobqueue,
  Fortschritt, Retry, Abbruch, Timeout, verständliche Fehler.
  Gleichzeitig laufende Exporte begrenzen. **Abnahme:** Test mit
  fünf parallelen Kundenjobs ohne Datenvermischung/Absturz.
- [ ] **T1-05 Nutzungsbegrenzung:** erfasst analysierte Videominuten
  und Renderjobs, Kostenbudget, Rate-Limits, Missbrauchsschutz;
  keine „unbegrenzte KI“ ohne kalkulierte Fair-Use-Regel.
  **Abnahme:** hartes Monatsbudget und freundliche Fehlermeldung.
- [ ] **T1-06 Verkaufstaugliche Qualität:** Testexport mit 1080×1920
  (je nach Quelle und Kosten), H.264/AAC, 24/30 fps, klare
  Dateigrößen, Tonpegel, Safe Zones, sauberes MP4.
  **Abnahme:** Reels auf iOS/Android und TikTok/Instagram/YouTube
  manuell überprüft; 540×960 darf als Vorschau bleiben.
- [ ] **T1-07 Realistische Rohvideos:** Eingabegrenzen auf einen für
  die Startnische brauchbaren Wert erhöhen (Hypothese: 3–5 Minuten
  je Projekt, nach Lasttest), mehr als zwei Szenen unterstützen,
  variable Reel-Länge. **Abnahme:** 20–30 verschiedene echte
  Testvideos, quer/hochkant, wechselnde FPS/Audio/Codec,
  ohne stille Bild-/Tonverluste.
- [ ] **T1-08 Support & Zuverlässigkeit:** Statusseite,
  Testmonitoring, Fehlerkennungen ohne personenbezogene Daten,
  Support-E-Mail, Recovery-Playbook, Rechnungs-/Zugangsprobleme.
  **Abnahme:** Fehler reproduzierbar und ohne Kunden-Upload
  erneut prüfbar, sofern technisch möglich.

## Phase 2 – Was Kunden tatsächlich posten können (MVP-Differenzierung)

- [ ] **F2-01 Story-Modi:** „Ferienunterkunft präsentieren“,
  „Tourismus-Highlight“, „Produkt zeigen“: Ziel,
  gewünschte Länge, Tonalität. KI empfiehlt Hook → Highlights →
  Schlussbild; behauptet keine erfundenen Eigenschaften.
  **Abnahme:** Laien erhalten eine plausible Reihenfolge und
  können sie ohne neue Analyse ändern.
- [ ] **F2-02 Titel/CTA/Brand Kit:** sichere Text-Ebenen, Logo,
  Farben, Schrift, Einstieg und Abspann, Social-Safe-Areas.
  **Abnahme:** tatsächlich veröffentlichbares Reel ohne
  Weiterbearbeitung in anderer Software.
- [ ] **F2-03 Untertitel optional:** Spracherkennung,
  Zeitmarken und leicht korrigierbare Captions, mindestens
  Deutsch und Englisch; Kosten transparent und
  abhängig von Nutzerbedarf. **Abnahme:** gut lesbare
  Untertitel und Korrektur vor Export.
- [ ] **F2-04 Drei Varianten aus einmaliger KI-Analyse:**
  „ruhig“, „schnell“, „informativ“, mit gespeicherter
  Analyse. **Abnahme:** keine erneute Vision-Abrechnung
  beim Wechsel zwischen Varianten.
- [ ] **F2-05 Smart Reframe:** optional statt Blur, Fokus auf
  Personen/Objekte bei 9:16; Fallback auf Vollbild/Blur,
  manuelle Korrektur. **Abnahme:** Hauptmotiv wird bei
  Kamerabewegungen nicht abgeschnitten.
- [ ] **F2-06 Erklärbare KI-Auswahl:** kurzer Grund für
  jedes Highlight („ruhige Kamerafahrt“, „schöner Einstieg“),
  einfache Alternativclips; **kein** unbelegtes Versprechen
  „viral garantiert“.

## Phase 3 – Recht, Verkauf & Betrieb (vor öffentlichem Launch)

- [ ] **R3-01 Unternehmen/Steuern:** passende österreichische
  Gewerbeberechtigung, SVS/Finanzamt, Rechnungen, mögliche
  Kleinunternehmerregelung, B2B/B2C, EU-OSS klären.
  55.000-€-Grenze der AT-Kleinunternehmerregelung und
  10.000-€-EU-Grenze für bestimmte elektronische B2C-Umsätze
  sind **unterschiedliche Regeln**, keine pauschale Befreiung.
  **Abnahme:** Steuerberatung bestätigt konkretes Modell.
- [ ] **R3-02 Datenschutz-Map:** Prozesse und Datenflüsse
  (Video-Uploads, Standbilder, KI-Anfragen, Accounts, Zahlung,
  Support, Logs), Rollen Verantwortlicher/Auftragsverarbeiter,
  Auftragsverarbeitungsverträge, Drittlandtransfers,
  Löschfristen, Auskunft/Löschung, Vorfallverfahren,
  Datenschutzinformationen, TOMs.
  **Abnahme:** Dokumentation, technische Löschung und
  anwendbare AVVs vor Fremdkunden-Uploads. OpenAI-API:
  Daten standardmäßig nicht fürs Training, Logs abhängig
  von Endpunkt/Vertrag gewöhnlich bis zu 30 Tage.
- [ ] **R3-03 Nutzer- und Urheberrechte:** AGB/Nutzungsrechte,
  Zusicherung für eigene Videos/Personen/Musik/Logos,
  Lösch-/Meldeverfahren, Lizenz für Fonts/Templates/Sounds,
  klare Haftungs- und Supportregelung.
  **Abnahme:** nur nachweislich lizenzierte Assets werden
  eingebaut. Keine Musikbibliothek ohne nötige Rechte.
- [ ] **R3-04 Verbraucherschutz:** Österreichisches Impressum,
  Leistungsbeschreibung, transparente Endpreise, AGB,
  Widerrufs-/Rücktrittsinformation, digitale
  Dienstleistungen/Downloads korrekt unterscheiden,
  Checkout-Bestätigung, Abo-Kündigung, Gewährleistung;
  neuer elektronischer Widerrufsbutton nach FAGG §13a
  seit **01.10.2026** in Österreich (für anwendbare
  B2C-Fernabsatzabschlüsse), in Deutschland seit 19.06.2026.
  Prüfen, wer bei einem Merchant-of-Record-Vertrieb der
  Endkunden-Vertragspartner ist und welcher Pfad die
  Pflicht konkret erfüllt. **Abnahme:** fachkundige Prüfung.
- [ ] **R3-05 KI-Regeln:** AI-Act-Pflichten anhand der
  tatsächlichen Funktionen und Rollen dokumentieren;
  bei bloß unterstützenden Standard-Edits i.d.R.
  keine automatische Deepfake-Pflicht unterstellen.
  Wenn synthetische/deepfakeähnliche Inhalte hinzukommen,
  Art. 50 erneut prüfen. KI-Einsatz transparent erklären.
- [ ] **R3-06 Softwarelizenzen:** FFmpeg-Build/Libx264 (GPL/LGPL),
  Fonts, OSS-Abhängigkeiten und Drittanbieter-APIs prüfen,
  Lizenzhinweise/Compliance dokumentieren.
  Hosted SaaS und verteiltes Binary getrennt bewerten.
- [ ] **R3-07 Barrierefreiheit & Cookies:** zugängliche
  Web-Oberfläche/Checkout; European Accessibility Act/
  österreichische Umsetzung inklusive möglicher
  Kleinstunternehmen-Ausnahmen klären. Keine unnötigen
  Tracking-Cookies ohne passende Rechtsgrundlage/Einwilligung.
- [ ] **R3-08 Checkout & Preise:** Start mit eigener Landingpage,
  Zahlungsabwicklung **Paddle oder Lemon Squeezy (MoR)** prüfen
  oder Stripe plus eigenständige Steuer-/Compliance-Prozesse.
  Abos/verbrauchsbasierte Kontingente statt einmalig
  unbegrenzter KI-Nutzung. **Preis-Hypothese:** Solo 19–29 €/Monat,
  Business 49–79 €/Monat; **erst nach Kostenmessung und
  Pilotinterviews festlegen**. Jahresrabatt später.
- [ ] **R3-09 Marke/Vertriebskanäle:** eigene Domain/Landingpage
  und Web-App als Hauptprodukt; persönliche DACH-Demos,
  Tourismusnetzwerke, Partneragenturen, YouTube-Shorts,
  Instagram-Demos. Nicht zuerst in App-Stores investieren.

## Phase 4 – Piloten und Verkauf (Go-/No-Go-Tore)

- [ ] **G4-01 Landingpage-Demo:** 30–60-s-Echt-Demo
  „Rohvideo → 3 publizierbare Reels“ ohne erfundene
  Leistungsversprechen; klarer Nutzen, Preis und Kontakt.
- [ ] **G4-02 Pilotgruppe:** 5–10 echte Nutzer (sichere,
  vertragskonforme Umgebung), jeweils min. 3 Projekte.
  Beobachten, wo Nutzer stocken und wie lange sie bis zum
  ersten publizierbaren Reel brauchen.
- [ ] **G4-03 Qualitäts-/Sicherheitsgate:** Erfolgsrate,
  Jobkosten, 5-Paralleljobs-Test, Audio/Bild-Synchronität,
  Supportabläufe, Löschtest, Rechte/Checkout-Rechtsprüfung;
  alle P0/T1/R3 Verkaufsblocker geschlossen.
- [ ] **G4-04 Zahlungsbereitschaft:** mindestens 3–5
  unabhängige Pilotbetriebe testen einen realen
  Preis bzw. verbindliche bezahlte Pilotvereinbarung
  (keine private personenbezogene Videoverarbeitung auf
  Community Cloud). Dokumentierter Kaufgrund.
- [ ] **G4-05 Soft Launch:** begrenzte zahlende Nutzer,
  kontingentierte KI-Minuten, Status-/Supportkanal,
  wöchentliche KPIs (Upload→Export, Kosten/Export,
  Aktivierung, Wiederkehrrate, Reklamationen).

## Nicht vor dem ersten Verkauf

- [ ] **Später:** direkte TikTok-/Instagram-Veröffentlichung
  (API-Freigaben/Berechtigungen), automatische Postingplanung,
  Voice-Over-Generator, Avatar-/Deepfake-Funktionen,
  riesige Musikkataloge, vollwertige Desktop-App.
  Erst nach belegter Kundennachfrage.

## Offizielle Referenzen / überprüfte Recherche

- Streamlit Community Cloud Nutzungsbedingungen:
  https://streamlit.io/terms-of-use
- Gleichnamiges Open-Source-Produkt:
  https://github.com/open-ribbi/velocut
- Österreichisches Patentamt Markenrecherche:
  https://www.patentamt.at/recherche/marken
- WKO Gewerbeanmeldung:
  https://www.wko.at/gruendung/gewerbeanmeldung
- WKO E-Commerce-Informationspflichten:
  https://www.wko.at/internetrecht/informationspflichten-nach-dem-e-commerce-gesetz--dem-unte
- WKO FAGG Widerrufsbutton ab 01.10.2026:
  https://www.wko.at/internetrecht/e-commerce-widerrufsbutton-webshop
- WKO Digitale Dienste Widerruf:
  https://www.wko.at/internetrecht/ruecktrittsrecht-bei-dienstleistungen-im-internet
- Österreichische USt EU OSS:
  https://www.usp.gv.at/themen/steuern-finanzen/umsatzsteuer-ueberblick/weitere-informationen-zur-umsatzsteuer/umsaetze-mit-auslandsbezug/Umsatzsteuer-One-Stop-Shop.html
- USP EU 10.000-€-Elektronikleistungen:
  https://www.usp.gv.at/themen/steuern-finanzen/umsatzsteuer-ueberblick/weitere-informationen-zur-umsatzsteuer/umsaetze-mit-auslandsbezug/grenzueberschreitende-dienstleistungen/elektronisch-erbrachte-dienstleistungen_telekommunikations_rundfunk--und-fernsehdienstleistungen.html
- Datenschutzbehörde (AT) Auftragsverarbeiterpflichten:
  https://dsb.gv.at/rechte-pflichten/ihre-pflichten-als-auftragsverarbeiterin
- OpenAI API data retention:
  https://developers.openai.com/api/docs/guides/your-data
- AI Act konsolidiert 2026, Art. 50:
  https://eur-lex.europa.eu/eli/reg/2024/1689
- FFmpeg Software-Lizenzen:
  https://www.ffmpeg.org/legal.html
- Paddle MoR:
  https://developer.paddle.com/get-started/how-paddle-works/
- Lemon Squeezy MoR:
  https://docs.lemonsqueezy.com/help/payments/sales-tax-vat
- EU Barrierefreiheit:
  https://europa.eu/youreurope/business/selling-in-eu/selling-goods-services/accessibility/index_en.htm

## Nächster Arbeitsschritt (genau einer je Gespräch)

**P0-01** zuerst: Namens-/Marken-Konflikt und Folgen für Branding
prüfen, zwei bis drei alternative Produktnamen sammeln und für
den ausgewählten Namen die professionelle Register-/Rechtsprüfung
als klaren Go-/No-Go-Schritt vorbereiten.
