# Call-Notizen & Themensammlung — 16.06.2026

Mitschriften aus dem Call, ausformuliert und thematisch geordnet. Bezieht sich auf
das lokale Airbyte-Setup (`abctl`/kind, Source-PostgreSQL → Ziel-PostgreSQL & MySQL,
Python-Loader für die Source-Befüllung). Siehe auch [architektur.md](architektur.md)
und [airbyte-setup.md](airbyte-setup.md).

---

## 1. Sync-Funktionsweise

### Die Phasen eines Syncs
Ein Airbyte-Sync läuft in festen Phasen ab:

1. **Trigger** — Start per Zeitplan (Cron), manuell oder über die API. Zuerst wird
   `check` an Source- *und* Destination-Connector aufgerufen (stehen beide Verbindungen?).
2. **Read (Extract)** — Der Source-Connector liest die Daten; jeder Datensatz wird zu
   einer `AirbyteRecordMessage` (JSON). Der Sync-Modus bestimmt, *was* gelesen wird.
3. **Transfer (Plattform)** — Airbyte puffert und batcht die Records. Hier findet
   **keine** Transformation statt (ELT-Prinzip: Daten bleiben roh).
4. **Write (Load)** — Der Destination-Connector schreibt zunächst in eine
   **Raw-Tabelle** (`_airbyte_raw_…`) mit JSON-Blob + Metadaten (Ladezeit, Hash).
5. **Typing & Deduping** — Die Raw-Daten werden in die finale, typisierte Tabelle
   überführt; bei Dedup-Modus werden Duplikate über den Primary Key entfernt.
6. **State / Checkpoint** — Bei Incremental wird der Fortschritt (z. B. höchster
   `updatedAt`-Wert) gespeichert, auch zwischendurch.

### Wird immer alles gesynct?
Hängt vom **Sync-Modus** ab:

| Modus | Liest jedes Mal alles? |
|---|---|
| Full Refresh – Overwrite | **Ja** — Ziel wird geleert und komplett neu geladen |
| Full Refresh – Append | **Ja** — alles wird erneut angehängt (Snapshots/Historie) |
| Incremental – Append | **Nein** — nur Sätze neuer als der Cursor |
| Incremental – Append + Dedup | **Nein** — nur Neues, dedupliziert per PK (häufigster Fall) |

### Wenn ein Sync abbricht
- **Transaktionssicher:** kein halb-importierter, kaputter Zustand in der finalen Tabelle.
- **Automatische Retries:** mehrere Attempts pro Job vor „failed".
- **Checkpointing (nur Incremental):** der nächste Lauf macht ab dem letzten Checkpoint
  weiter, nicht von vorn.
- **Full Refresh:** kein Teil-Aufholen — der nächste Lauf macht alles neu (robust, aber teuer).
- Pro Connection konfigurierbar, ob bei wiederholten Fehlern automatisch deaktiviert wird.

### Paketgröße / Batching
- **Airbyte intern:** Records werden gepuffert und in Batches geschrieben; ein „Flush"
  wird durch Buffer-Größe (RAM/Bytes) **oder** Record-Anzahl ausgelöst. Defaults sind
  connector-spezifisch, in der UI normalerweise nicht gesetzt. Bei self-hosted über
  Memory-Limits (`JOB_MAIN_CONTAINER_MEMORY_*`) indirekt beeinflussbar.
- **State-Checkpoint-Intervall:** bestimmt, wie oft der Fortschritt gesichert wird
  (relevant für Wiederaufnahme nach Abbruch).
- **In unseren Skripten:** sichtbare Paketgröße = `page_size` bei `execute_values`.
  `load_k_plz.py` nutzt `page_size=1000`; die übrigen Loader nutzen den Default (100)
  → bei großen Tabellen ggf. angleichen.

---

## 2. Connections

### Connections aneinanderreihen / verketten
Airbyte kann Connections **nicht nativ** verketten („B startet, wenn A fertig ist").
Jede Connection hat nur ihren eigenen Zeitplan oder wird manuell/per API getriggert.
Wege für Reihenfolge/Abhängigkeiten:

| Ansatz | Wann sinnvoll |
|---|---|
| Airbyte-API / `abctl`-Skript | Skript triggert Connection 1, wartet auf „succeeded", triggert dann 2. Für wenige Connections völlig ausreichend. |
| Orchestrator (Airflow, Dagster, Prefect) | Viele Schritte mit echten Abhängigkeiten. Für ein Studienprojekt meist Overkill. |
| dbt nach dem Sync | Wenn die zweite Stufe eine Transformation in der Ziel-DB ist (kein weiterer Sync). |

### Custom Code zum Daten-Manipulieren
Airbyte ist **ELT**, nicht ETL — keine freien Code-Snippets mitten im Sync. Möglichkeiten:

| Möglichkeit | Was geht | Was nicht |
|---|---|---|
| Mappings (Connection-UI) | Felder umbenennen, hashen/verschlüsseln, Zeilen filtern | keine freie Logik / Berechnungen |
| Connector Builder / Low-Code CDK | eigene Quell-Connectoren (Extraktion) | keine Ziel-Transformation |
| dbt (nach dem Load) | beliebige SQL-Transformationen | externes Tool, separat aufzusetzen |

> Unsere Python-Loader (`demojibake`, `normalize`, `generate_account`) sind faktisch
> unsere Custom-Transformation — bewusst **vor** Airbyte, weil die Roh-CSVs unsauber sind.

---

## 3. Eigene Connectoren

### Drei Ebenen (einfach → mächtig)
1. **Connector Builder** (Airbyte-UI, kein Code) — für REST-APIs; direkt in der UI testbar.
2. **Low-Code CDK** (`manifest.yaml`) — deklarativ, versionierbar im Git.
3. **Python CDK** (voller Code) — für Nicht-REST: Datenbanken, SOAP, exotische Formate.

### Aufbau jedes Connectors
Jeder Connector läuft als **Docker-Image** und implementiert vier Kommandos:

| Kommando | Zweck |
|---|---|
| `spec` | Welche Config-Felder braucht der Connector? |
| `check` | Verbindung testen |
| `discover` | Welche Streams/Tabellen + Schema gibt es? |
| `read` | Daten auslesen (als JSON-Stream) |

### Connectoren für APIs
Der Connector Builder reicht für REST-APIs völlig aus. Wichtige Stellen:
Base-URL, Authentication (None/API-Key/Bearer/OAuth2/Basic), Streams (Pfad + Methode),
**Record Selector** (wo im JSON liegen die Daten?), **Pagination**, Schema,
optional **Incremental Sync** über ein Datums-/ID-Feld. Ergebnis als `manifest.yaml`
exportieren und ins Repo legen (z. B. unter `connections/`), damit alle dieselbe
Definition haben.

> Für **Informix** und **SOAP** (offene Quellen) gibt es keine fertigen Connectoren →
> Python CDK oder pragmatisch per eigenem Skript in die Source-DB schreiben.

---

## 4. Monitoring

### Logs
- **Sync-Logs:** 
    - Airbyte-UI → Connection → **Job History** → Sync anklicken → Logs
  (gelesene/geschriebene Zeilen, Fehler, Dauer).
    - Airbyte-UI → Connections → entsprechende Connection anklicken -> Timeline -> auf das Punktemenü rechts neben dem entsprechenden Event klicken -> View Logs (kann auch als .txt Datei gedownloadet werden)
        - Im Header: Attempt wählbar (wenn fehlgeschlagen), Timestamp, Anzahl extracted/geladener records, Job id, Dauer in Sekunden
        - wenn Warning/Fail: Kurzbeschreibung: zum Beispiel: "Failure in source: Checking source connection failed - please review this connection's configuration to prevent future syncs from failing"
        - bietet Suchfunktion, filterbar nach sources (replication-orchestrator, source, destination, platform) und filterbar nach Log levels (info, warn, error, debug, trace)
        - Logfile: enthält weitere nützliche Informationen (zum Beispiel detailliertes Sync summary)
          
          Hier ein beispielhafter Auszug eines erfolgreichen Syncs:

          ```json
          {
            "status" : "completed",
            "recordsSynced" : 1245,
            "bytesSynced" : 363574,
            "startTime" : 1781532526967,
            "endTime" : 1781532557644,
            "totalStats" : {
              "recordsEmitted" : 1245,
              "recordsCommitted" : 1245
              (...)
 
            },
            "streamStats" : [ {
              "streamName" : "fm_stamm"
            } ]
          }
    - Logs über die Airbyte API auszulesen ist aktuell noch nicht möglich (ggf. noch Umwege prüfen)

- **Plattform-Logs:** `kubectl logs -n airbyte-abctl <pod>` (`kubectl get pods -n airbyte-abctl`).
- **DB-Logs:** `docker compose logs source-postgres` / `dest-postgres` (`-f` für live).
- **Unsere Skripte:** aktuell nur `print()` auf die Konsole, kein File-Logging.
  → Möglicher Verbesserungspunkt: `logging` mit Zeitstempel + Logfile.

### Performance-Checks
- **Airbyte:** UI zeigt Dauer, Zeilen, Datenvolumen pro Sync. Größter Hebel:
  **Incremental statt Full Refresh**.
    - Aus den Logs lässt sich die Dauer der einzelnen Phasen rauslesen: 
        - **destinationWriteStartTime, destinationWriteEndTime**: Zeitpunkt des Beginns/Endes beim Schreiben in die Ziel-DB
        - **sourceReadStartTime , sourceReadEndTime**: Zeitpunkt des Starts/Endes beim Lesen aus der Quell-DB
        - **replicationStartTime, replicationEndTime**: Zeitpunkt des Starts/Endes des Syncs insgesamt
        - weitere: 
          **meanSecondsBeforeSourceStateMessageEmitted, maxSecondsBeforeSourceStateMessageEmitted**:
          durchschnittliche/ längste Zeitspanne, die der Airbyte Source-Connector warten musste, bis die Source-DB die Daten geliefert hat
          und ein neues Lesezeichen (State Message) in die Pipeline gesendet werden konnte.
          **meanSecondsBetweenStateMessageEmittedandCommitted, maxSecondsBetweenStateMessageEmittedandCommitted**:
          durchschnittliche/ längste gemessene Zeitspanne, die ein Lesezeichen in der Airbyte-Pipeline verbracht hat.
          (zwischen Source-Connector und Destination-Connector)

- **Skripte:** Laufzeit messen (`time.perf_counter()`); `execute_values` (Batch-Insert)
  ist bereits gesetzt; bei Bedarf `page_size` erhöhen.
- **Ziel-DB:** `EXPLAIN ANALYZE` für langsame Abfragen; Indizes prüfen
  (z. B. Index auf `updatedat` in `load_json.py` für den Cursor).

## Performance pro Sync-Strategie:

Getestet wird mit den Tabellen fm_gebaeude (25 Records) und k_plz (34.172 Records) (Insgesamt = 5.331.779 Bytes ~ 5,33 MB)
TimeBetween = meanSecondsBetweenStateMessageEmittedandCommitted (zwischen Source und Destination)
Es gibt einen relativ großen Overhead vor Start des eigentlichen Streams. (Containerstart, Verbindungsaufbau,..)

Bei **Incremental-Strategien**: Benötigt Cursor mit folgender Eigenschaft: neuerer/aktualisierter Datensatz 
muss immer höheren Cursor-Wert haben als der vorherige.
Daher wird hierfür die Tabelle hso_personal (870 records = 275.756 Byte ~ 0,28 MB) verwendet mit updated_at als Cursor
Hiermit können Simulationsdurchläufe mit nur wenig veränderten Datensätzen simuliert werden (+ Darstellung von Overhead).

| Sync mode | Gesamtdauer Stream (Replication) | Destination Time | Source Read Time | TimeBetween | Durchsatz-Geschwindigkeit | Gesamtdauer |
|---|---|---|---|---|---|---|
| Full refresh/Overwrite | 36,36 s | 36,18 s | 25,1 s | 11 s | 0,14 MB/s | 104 s |
| Full refresh/Append | 48,88 s| 48,4 s | 36,0 s | 17 s | 0,11 MB/s |96 s |
| Full refresh/Overwrite + Deduped | 40,93 s | 29,07 s | 40,57 s | 16 s| 0,13 MB/s| 68 s|
| Incremental/Append + Deduped | 31,26 s | 30,83 s | 20,24 s| 10 s | 0,009 MB/s | 105 s|
| Incremental/Append | 28,96 s | 28,66 s | 17,97 s | 10 s | 0,00014 MB/s | 57 s |

[Hier noch Grafiken einfügen]

Es fällt auf, dass der Overhead überall relativ groß ist, daher ist Incremental im Vergleich zu Full refresh auch relativ langsam
---

## 5. SDK, Marketplace & Ideen

### SDK anschauen / testen
Das Python-CDK ist nur für **Nicht-REST**-Quellen nötig. Für APIs ist der Connector
Builder schneller und ohne lokales Setup. SDK-Einstieg lohnt sich gezielt für
Informix/SOAP.

### Kostet der Marketplace?
**Nein.** Airbyte OSS (unser `abctl`-Setup) und **alle** Connectoren (Certified wie
Community/Marketplace) sind kostenlos. Kostenpflichtig ist nur **Airbyte Cloud**
(nutzungsbasiert). Kosten können höchstens auf Seiten der **Quelle** entstehen
(bezahlte API-Tiers).

### Creative Connections (Demo-Ideen)
Externe Live-Daten als Ergänzung zu den HSO-Daten — ideal: freie APIs **ohne Key**:

| Thema | API | Key nötig? |
|---|---|---|
| Börsen/Finanzen | Frankfurter (EZB-Wechselkurse) | nein |
| Krypto | CoinGecko | nein (rate-limited) |
| Aktien | Alpha Vantage / Finnhub | ja (free tier) |
| Green IT / Energie | Energy-Charts (Fraunhofer ISE) | nein |
| Wetter/Solar | Open-Meteo | nein |
| Strommarkt EU | ENTSO-E / Electricity Maps | ja |

> Empfehlung für eine Demo: Frankfurter (Wechselkurse) **oder** Energy-Charts (Green IT)
> im Connector Builder nachbauen — beide ohne Key, ~10 Min., zeigt externe Daten im Fluss.

---

## 6. Weitere thematisch sinnvolle Punkte (ergänzt)

Diese kamen im Call nicht explizit vor, gehören aber sachlich dazu und sind für die
nächsten Schritte relevant:

- **CDC vs. Cursor:** Wir nutzen bewusst Cursor (`updatedat`) statt CDC/Xmin, um
  zusätzliche WAL-/Replication-Konfiguration zu vermeiden (siehe
  [architektur.md §5](architektur.md)). CDC erkennt auch *Löschungen* — Cursor nicht.
  Für eine vollständige Sync-Strategie-Doku relevant.
- **Schema-Änderungen (Schema Drift):** Wenn sich Quellspalten ändern, kann Airbyte
  pro Connection automatisch propagieren oder den Sync zur Bestätigung anhalten —
  Verhalten sollte bewusst gesetzt werden.
- **Scheduling:** Sync-Intervall pro Connection (Cron) vs. manueller/API-Trigger —
  zusammen mit dem Verkettungs-Thema (Abschnitt 2) zu entscheiden.
- **Idempotenz:** Unsere Loader sind idempotent (`TRUNCATE` + Reload); bei Airbyte
  übernimmt das der Sync-Modus (Overwrite vs. Append+Dedup).
- **Sicherheit:** Secrets nur in `.env` (gegitignored), nicht in `manifest.yaml`
  committen; bei API-Connectoren Keys über Config-Felder, nie hartkodiert.
- **Versionierung der Connectoren:** Builder-Ergebnisse als `manifest.yaml` ins Repo,
  damit das Setup reproduzierbar und im Team gleich ist.

---

## 7. Offene Aufgaben / To-dos

- [ ] **Architektur-Diagramm** als richtiges Bild erstellen (statt ASCII) — Deliverable
      aus dem Prof-Feedback.
- [ ] **Sync-Strategie-Doku** (Modi pro Tabelle, CDC vs. Cursor, Fehlerverhalten) —
      offenes Deliverable.
- [ ] Sync-Modus **pro Tabelle** festlegen (Full Refresh vs. Incremental+Dedup) und in
      `connections/` dokumentieren.
- [ ] Performance messen für die verschiedenen Sync-Modi bei größeren Datensätzen
- [ ] **Informix / SOAP**: Custom-Connector (Python CDK) vs. Skript-in-Postgres entscheiden.
- [ ] **File-Logging** in den Loadern statt `print()` (optional).
- [ ] `page_size` in `load_json.py` und `load_fm_gebaeude.py` angleichen (optional).
- [ ] Optional: Demo-Connector für eine freie API (Frankfurter / Energy-Charts).