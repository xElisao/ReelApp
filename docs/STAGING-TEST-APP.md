# VeloCut 2.0 – separater Testbereich (Streamlit)

Die Entwicklungsanwendung verwendet `staging_app.py`. **Nicht**
`app.py` aus der Live-Anwendung ersetzen. Der Entwicklungsbranch ist
`feature/velocut-2-video-analysis`.

## Sicherer Start in einer separaten Streamlit-App

1. Im Streamlit-Dashboard **eine zweite, neue App** aus dem Repository
   `xElisao/ReelApp` anlegen.
2. Den Branch `feature/velocut-2-video-analysis` auswählen.
3. Als Main File **`staging_app.py`** angeben.
4. Python **3.11** als App-Python-Version wählen, sofern auswählbar.
5. In **dieser neuen App** unter Secrets diese beiden Werte hinterlegen:

```toml
STAGING_ACCESS_PASSWORD = "EIN_STARKES_UNABHAENGIGES_PASSWORT_MINDESTENS_16_ZEICHEN"
OPENAI_API_KEY = "DEIN_OPENAI_API_KEY_NUR_IN_DEN_SECRETS"
```

Die Werte oben sind nur Platzhalter! **Keine Secrets in das GitHub-Repository,
keine Secrets in den Chat und nicht in commitbare Dateien kopieren.**

6. Das Staging-URL nicht öffentlich bewerben oder teilen. Das Passwort
   nicht identisch mit anderen Kontopasswörtern wählen.
7. Autorisiertes Video (max. 60s, max. 80 MB) hochladen,
   Zieltext eingeben, optional feineren Scan aktivieren und testen.

Die Staging-App startet **nicht**, solange das starke Zugangspasswort
oder der API-Key fehlen. OpenAI-Aufrufe kosten je nach ausgewähltem Modell
und Anzahl Bilder Geld. Für die erste Prüfung einen kurzen Testclip verwenden.

## Wozu das Testlabor dient

- Mehrere Szenenkategorien aus echten Videobildern schätzen.
- Beliebige Wünsche in Schnittziele umwandeln und passende Zeitfenster
  als begründete Vorschläge anzeigen.
- Ergebnisse als JSON exportieren.
- Dasselbe Video mit zwei verschiedenen Nutzerzielen testen.
- Eine spätere manuell annotierte Referenz mittels
  `evaluate_recommendations.py` mit JSON vergleichen.

## Wichtig: noch keine fertige KI-Videoschnitt-App

- Es werden nur Videobilder zur Analyse an OpenAI geschickt,
  **kein Audio**.
- Die Bilder sind ein Stichprobenraster; kurze Ereignisse können fehlen.
- Zeitangaben sind Video-Zeitfenster, keine präzisen Schnittmarken.
- Keine KI-Erkennungsqualität garantiert oder mit echtem Modell gemessen.
- Die Staging-App enthält keinen produktiven Stripe-Flow oder
  Kunden-Login. Das Testpasswort ist ein Entwicklungsschutz, kein
  vollständiges Produkt-Authentifizierungssystem.
- Bei extern öffentlich zugänglichen URLs bleibt auch mit Passwort
  Restrisiko; niemals Kundenvideos ohne Zustimmung testen.
- Die bestehende App auf `main` wurde nicht verändert.

## Vor dem Produktiveinsatz

Modellqualität und API-Kosten messen, Videoschnitt exakt implementieren,
und Benutzerzugang, Datenspeicherung, Nutzerausgaben, Hosting und
Stripe-Webhooks separat absichern.
