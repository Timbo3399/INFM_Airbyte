# Testszenarien: Campus Next-Gen Data-Hub (SoSe 2026)

Ziel: Evaluierung von Airbyte als ETL-Tool für die Hochschul-IT (Ersatz für Talend).

> **Umsetzungsstand (live verifiziert, Stand 06.06.2026):**
> - **Szenario 1** ist vollständig umgesetzt: PG→PG **und** PG→MySQL (je fm_gebaeude 25 / k_plz 34.172),
>   File→PG `hso_students` **5.052 Zeilen** (defekte CSV, an der `COPY` scheiterte).
> - **Szenario 6a** ist umgesetzt, PostgREST liefert REST auf `destdb` (`GET localhost:3000/k_plz`).
> - **Szenario 2, 3, 4 und 5** sind teilweise umgesetzt oder offen. Stand und Blocker je Szenario stehen unten bzw. in
>   [anforderungen.md](anforderungen.md).

---

## Übersicht der Testdaten

| Datei / Tabelle | Format | Inhalt | Zeilen | In source-postgres |
|-----------------|--------|--------|--------|--------------------|
| `hso_students` | Pipe-CSV | Studierende (anonym.) | 5.052 | `hso_students` (via load_hso_students.py, quote-bewusster Parser) + zusätzlich via File-Connector |
| `fm_gebaeude` | CSV | Gebaeude der Hochschule | 25 | `fm_gebaeude` (via load_fm_gebaeude.py) |
| `fm_inst` | Semikolon-CSV | Institute / Org-Einheiten | ~2.080 | `fm_inst` (via load_fm_inst.py) |
| `fm_stamm` | Excel (.xltx) | Raumstammdaten (Räume) | 1.245 in der Quelle, 1.244 geladen | `fm_stamm` (via ETL-Mapping aus rooms.xltx befüllt, siehe load_fm_stamm.py; eine PK-Dublette wird verworfen) |
| `k_plz` | CSV | PLZ-Verzeichnis Deutschland | ~34.000 | `k_plz` (via load_k_plz.py) |
| `fm_rna.json` | JSON | Raumnutzungsarten | ~380 | `fm_rna` (via load_json.py) |
| `hso_personal.json` | JSON | Personal HSO (anonym.) | ~870 | `hso_personal` (via load_json.py) |
| `k_res*.csv` | Semikolon-CSV | Klassifikations-Lookups | je ~5-20 | `k_res` (8 Dateien konsolidiert via load_lookups.py) |
| `hso_accountgenerator.js` | JavaScript | Account-Name-Logik (HSO-Original, **Referenz**) | entfällt | nicht geladen, portiert nach `generate_accounts.py` |

---

## Airbyte Sync-Modi

> Konzept-Doku: <https://docs.airbyte.com/using-airbyte/core-concepts/sync-modes/>
> **Inkrementelle Modi** brauchen ein **Cursor-Feld** (neue Zeilen erkennen); alle
> **Deduped**-Modi zusätzlich einen **Primary Key** (für die Deduplizierung).

| Modus | Liest | Schreibt | Wann verwenden |
|-------|-------|----------|----------------|
| Full Refresh \| Overwrite | Alles | Ersetzt Ziel komplett | Erster Test, kleine Tabellen |
| Full Refresh \| Append | Alles | Haengt an Ziel an | Historisierung ganzer Snapshots |
| Full Refresh \| Overwrite + Deduped | Alles | Ersetzt + dedupliziert | Frischer Stand ohne Duplikate |
| Incremental \| Append | Nur neue Zeilen | Haengt neue Zeilen an | Wachsende Logs, kein Cursor noetig |
| Incremental \| Append + Deduped | Nur neue Zeilen | Haengt an + dedupliziert | IdM-Sync (Szenario 5), Cursor: `updatedat` |

---

## Szenario 1: Einspielen der Testdaten

**Ziel:** Vertrautmachen mit Airbyte, grundlegende Datenbankanbindungen testen.

**Aufgaben:**
- Bestehende Testdaten (k_res*.csv, k_plz) in MySQL und PostgreSQL laden
- Verschiedene Source-Typen testen: Postgres-Source, File-Connector

**Airbyte-Konfiguration:**

| Parameter | Wert |
|-----------|------|
| Source | `source-postgres` (alle Streams) |
| Destination 1 | `dest-postgres` |
| Destination 2 | `dest-mysql` |
| Sync-Modus | Full Refresh \| Overwrite |

**Prüfung:**
```sql
-- In dest-postgres:
SELECT schemaname, tablename, n_live_tup
FROM pg_stat_user_tables ORDER BY n_live_tup DESC;

-- In dest-mysql:
SHOW TABLES;
SELECT COUNT(*) FROM hso_students;
```

---

## Szenario 2: Facility Management

**Ziel:** PostgreSQL-DB mit FM-Tabellen aufbauen; denormalisierte MySQL-Tabelle für Räume erstellen.

**Teilaufgabe A, PostgreSQL FM-DB:**

Tabellen `fm_inst`, `fm_gebaeude`, `fm_stamm` sind in `source-postgres` vorgeladen.

Nach dem Sync nach `dest-postgres` prüfen:
```sql
-- Raumübersicht (Gebäude + Institut + Raum joined)
SELECT s.geb_nr, s.raumnr, g.geb AS gebaeude_name,
       s.flaeche, s.rna_nr, s.kost_nr
FROM fm_stamm s
JOIN fm_gebaeude g ON s.geb_nr = g.geb_nr
ORDER BY s.geb_nr, s.raumnr;
```

**Teilaufgabe B, MySQL Raumtabelle (denormalisiert):**

In Airbyte eine Transformation konfigurieren, die folgende Tabelle in `dest-mysql` erzeugt:

```sql
CREATE TABLE fm_raeume (
    raum_id      VARCHAR(30) PRIMARY KEY,
    raumnr       VARCHAR(20),
    gebaeude     VARCHAR(60),   -- aus fm_gebaeude.geb
    gebaeude_nr  VARCHAR(10),
    institut     VARCHAR(60),   -- aus fm_inst.dname
    flaeche      DECIMAL(14,2),
    kostenstelle VARCHAR(20)
);
```

> **Hinweis:** Airbyte kann Joins nicht direkt ausführen. Optionen:
> - dbt-Transformation nach dem Sync
> - Custom SQL-View in source-postgres, dann syncen
> - Python/SQL-Skript nach dem Sync

---

## Szenario 3: Testdaten für Bilder generieren

**Ziel:** >1.000 Bilder per API abrufen, als BLOB in DB speichern; danach aus DB exportieren.

**API:** https://picsum.photos/ (liefert zufällige Bilder als JPEG)

**Teilaufgabe A, Bilder in DB laden:** [`scripts/images/load_images.py`](../scripts/images/load_images.py)

```powershell
python scripts/images/load_images.py
```

Legt `hso_images` an (`image_id SERIAL`, `ext_id UNIQUE`, `data BYTEA`) und lädt 1.100 Bilder.

> **Warum Seed-URLs und nicht `/id/<n>`?** Der erste Ansatz über `https://picsum.photos/id/<n>/200/200`
> lieferte für viele IDs 404, wir landeten damit deutlich unter den geforderten 1.000 Bildern.
> `https://picsum.photos/seed/hso<n>/200/200` antwortet dagegen immer mit 200 und ist zusätzlich
> deterministisch: derselbe Seed liefert dasselbe Bild.

**Teilaufgabe B, Bilder aus DB exportieren:** [`scripts/images/export_images.py`](../scripts/images/export_images.py)

```powershell
python scripts/images/export_images.py
```

Schreibt die BLOBs als `<ext_id>.png` nach `data/images/`. Der Dateiname folgt der Aufgabenstellung;
picsum liefert JPEG-Daten, die Endung sagt also nichts über das Format aus.

### Ergebnis des Durchlaufs

`load_images.py` hat 1.100 Bilder geholt, keines übersprungen, zusammen 8.015 kB in
`hso_images`. `export_images.py` hat daraus 1.100 Dateien geschrieben, und alle 1.100
sind byteweise identisch mit dem Inhalt der Datenbank. Der Weg Datei nach BYTEA nach
Datei verliert also nichts.

### Airbyte-Evaluation: BYTEA nach MySQL

Sync `hso_images` von `source-postgres` nach `dest-mysql`, Full Refresh, über
`python scripts/airbyte_run_sync.py "HSO Bilder nach MySQL"`.

Der Job meldet Erfolg: 1.100 Zeilen, 16.508.628 Bytes übertragen, Dauer PT1M. In der
Zieltabelle stehen 1.100 Zeilen. Trotzdem ist **kein einziges Bild angekommen**:

```sql
SELECT COUNT(*), COUNT(data) FROM hso_images;   -- 1100, 0
```

| Spalte | Typ in MySQL | Werte |
|---|---|---|
| `image_id` | bigint | 1.100 |
| `ext_id` | text | 1.100 |
| `data` | **text** (max 65.535) | **0**, alles NULL |

Was dabei auffällt:

**Die Rohdaten sind da.** In `destdb_raw__stream_hso_images` steht das Bild als
Hex-String, beginnend mit `\xffd8ffe1`, also der JPEG-Signatur. Die Rohsätze sind
zwischen 3.927 und 35.647 Bytes groß und liegen damit alle deutlich unter der
TEXT-Grenze. Verloren geht das Bild erst im Typisierungsschritt, der aus der Rohtabelle
die Zieltabelle baut.

**Die Zielspalte ist TEXT, nicht BLOB.** Airbyte bildet BYTEA nicht auf einen
Binärtyp ab. Ein Bild in einer TEXT-Spalte wäre ohnehin nur als Hex oder Base64
speicherbar, hier bleibt die Spalte gleich ganz leer.

**Airbyte meldet nichts.** `_airbyte_meta` enthält `{"changes": []}`, also keinen
Hinweis auf verworfene Werte. Der Sync gilt als erfolgreich, die Zeilenzahl stimmt,
und nur ein Blick in die Spalte zeigt den Verlust. Wer nach dem Sync die Zeilen zählt,
merkt nichts.

**Konsequenz für Szenario 3:** Der Bildtransport funktioniert mit den Python-Skripten,
nicht mit Airbyte. Für BLOBs bräuchte es einen anderen Weg, etwa die Bilder im
Dateisystem oder Objektspeicher zu halten und über Airbyte nur Pfade und Metadaten zu
synchronisieren.

---

## Szenario 4: Mapping von Studenten / Personal

**Ziel:** Anonymisierte Daten mit realistischen Werten befüllen; Account-IDs generieren; in neue Tabellen schreiben.

**Schritt 1, Namen befüllen:** [`scripts/mapping/fill_random_names.py`](../scripts/mapping/fill_random_names.py)

Die Anonymisierung hat die Namensfelder komplett geleert: `firstname` und `surname` sind in
allen 5.052 Zeilen von `hso_students` leer, `vorname` und `nachname` in allen 870 Zeilen von
`hso_personal`. Ohne Namen erzeugt der Account-Generator für keine einzige Zeile eine `user_id`.
Das Skript füllt sie deterministisch aus einem Namenspool, abgeleitet aus `mtknr` bzw. `id`,
sodass ein zweiter Lauf dieselben Namen liefert.

**Schritt 2, Accounts generieren:** [`scripts/mapping/generate_accounts.py`](../scripts/mapping/generate_accounts.py)

Referenz-Artefakt ist `data/js/hso_accountgenerator.js` (HSO-Original aus HISinOne, wird nicht
ausgeführt). Die Spec dort lautet:

```
account = maxLength-8(Vorname[0] + Nachname + (Anzahlaccounts_mit_dem_Schema + 1))
          (Umlaute ersetzen: ä→ae, ö→oe, ü→ue, ß→ss)
```

Der Zähler in der Klammer ist die Kollisionsbehandlung, und die Längenbegrenzung gilt für den
gesamten Namen. Ist `mmusterm` vergeben, folgt also `mmuster2`, ab dem zehnten `mmuste10`.
Über beide Tabellen zusammen ergibt das 5.922 eindeutige Accounts. Geschrieben werden
`user_id` und die daraus abgeleitete Hochschul-E-Mail, dazu wird `updatedat` gesetzt, damit ein
Incremental-Sync über den Cursor die Änderung sieht.

```powershell
python scripts/mapping/fill_random_names.py
python scripts/mapping/generate_accounts.py
```

**Airbyte Custom Transformation:**
In Airbyte kann die Account-Logik als dbt-Modell oder über einen Custom Python Connector implementiert werden.

**Ziel-Tabelle** (`dest-postgres`):
```sql
CREATE TABLE hso_students_mapped (
    mtknr      INTEGER,
    firstname  VARCHAR(100),
    surname    VARCHAR(100),
    user_id    VARCHAR(20),  -- generierter Account, wie in hso_students
    email      VARCHAR(255),
    stg        VARCHAR(20),
    fakult     VARCHAR(100)
);
```

---

## Szenario 5: IdM-System

**Ziel:** `hso_personal` + `hso_students` → gemeinsame `hso_user`-Tabelle in MySQL synchronisieren; bei Änderungen in Quelltabellen automatisch nachziehen.

**Ziel-Tabelle** `hso_user` in `dest-mysql`:
```sql
CREATE TABLE hso_user (
    user_id      VARCHAR(20) PRIMARY KEY,
    nachname     VARCHAR(100),
    vorname      VARCHAR(100),
    email        VARCHAR(255),
    rolle        VARCHAR(50),   -- 'student' oder 'personal'
    status       VARCHAR(20),
    image_id     INTEGER        -- FK zu hso_images (Szenario 3)
);
```

**Sync-Strategie:**
- Airbyte Connection: `source-postgres.hso_students` → `dest-mysql.hso_user` (Incremental | Append+Dedup)
- Cursor-Feld: `updatedat` (in beiden Quelltabellen vorhanden und indiziert)
- Primary Key: `user_id`. Er ist über Studierende und Personal hinweg eindeutig, siehe Szenario 4.
  Tabellenintern eindeutig sind auch `hso_students.mtknr` (5.052 verschiedene Werte) und
  `hso_personal.id` (Primärschlüssel). Als gemeinsamer Schlüssel in `hso_user` taugen sie
  trotzdem nicht: die Nummernkreise stammen aus verschiedenen Systemen (mtknr 153.026 bis
  184.213, id 3 bis 8.542). Sie überschneiden sich derzeit zwar nicht, garantiert ist das
  aber nicht.

> **Aufwand beachten:** Der Dedup-Modus kostet in unseren Messungen etwa das Doppelte an
> Laufzeit gegenüber Incremental/Append ohne Dedup (82,47 s statt 39,67 s bei 75.000 Sätzen,
> siehe [call-notes-2026-06-16.md](call-notes-2026-06-16.md)).

**Änderungs-Test:**
```sql
-- Feld in der Quelle aendern, updatedat mitziehen (sonst sieht der Cursor nichts)
UPDATE hso_students SET studentstatus='AENDERUNGSTEST', updatedat=NOW()
WHERE user_id = 'abauer';

-- Sync starten, danach im Ziel pruefen
```

```powershell
python scripts/airbyte_run_sync.py "HSO IdM hso_user nach MySQL"
```

### Aufbau

Airbyte synchronisiert Streams 1:1, ein UNION zweier Quelltabellen in eine Zieltabelle
ist nicht vorgesehen. Die Zusammenführung passiert deshalb vor Airbyte, in der View
[`sql/source/views/hso_user.sql`](../sql/source/views/hso_user.sql). Airbyte liest sie
wie eine normale Tabelle.

```powershell
python scripts/mapping/create_hso_user_view.py     # View anlegen (5.922 Zeilen)
python scripts/airbyte_setup_objects.py            # Sources + Destinations
python scripts/airbyte_setup_connections.py        # Connections inkl. IdM
```

### Ergebnis

Vier Syncs, alle über die API ausgelöst:

| Job | Anlass | Gelesen | Volumen | Dauer |
|---|---|---:|---:|---|
| 2 | Erstlauf | 5.922 | 1.110.471 B | PT1M |
| 3 | nach der Änderung an `abauer` | 5.922 | 1.110.484 B | PT31S |
| 4 | ohne Änderung | 1 | 197 B | PT31S |

Im Ziel stehen 5.922 Zeilen mit 5.922 verschiedenen `user_id`, davon 5.052 Studierende
und 870 Personal. Der geänderte Status steht nach dem Sync in MySQL, und es ist keine
zweite Zeile für `abauer` entstanden: die Deduplizierung greift.

Drei Beobachtungen dazu:

**Der Cursor ist einschließend.** Job 4 liest ohne jede Änderung eine Zeile statt keiner.
Das ist die Zeile mit dem höchsten `updatedat`. Airbyte filtert mit `>=`, um bei
gleichen Zeitstempeln nichts zu verlieren, und liest die Grenzzeile deshalb jedes Mal
erneut. Harmlos, aber gut zu wissen, wenn man Zeilenzahlen vergleicht.

**Die ersten beiden Läufe lasen alles.** Dass der Erstlauf einem Full Refresh entspricht,
war bekannt. Dass auch Job 3 noch alle 5.922 Zeilen las und erst Job 4 auf die Delta-Menge
umschaltete, haben wir nicht abschließend erklärt. Wer das nachstellt, sollte den dritten
Lauf mitmessen, bevor er aus einer einzelnen Messung Schlüsse zieht.

**Die Rohtabelle wächst mit jedem Lauf.** `destdb_raw__stream_hso_user` enthält nach den
drei erfolgreichen Syncs 11.845 Zeilen (5.922 + 5.922 + 1), die Zieltabelle dagegen
konstant 5.922. Die Deduplizierung passiert also erst beim Aufbau der finalen Tabelle,
der Rohbestand bleibt vollständig liegen und braucht auf Dauer eine Aufräumstrategie.

### Bildverknüpfung

Der zweite Teil von Szenario 5 verknüpft `user_id` mit den Bildern aus Szenario 3. Die
Testbilder haben keinen inhaltlichen Bezug zu Personen, die Zuordnung ist also
willkürlich, aber deterministisch: ein Hash der `user_id` modulo Bildanzahl. Dieselbe
Person bekommt bei jedem Lauf dasselbe Bild. Im Ziel haben alle 5.922 Zeilen ein
`image_id`, verteilt auf 1.095 der 1.100 Bilder.

Dabei ist uns eine Falle aufgefallen, die es wert ist, festgehalten zu werden.

**Eine geänderte View-Definition sieht der Cursor nicht.** Nach dem Umbau der View
hatten alle 5.922 Zeilen einen neuen Wert in `image_id`. Der nächste Incremental-Sync
übertrug trotzdem genau eine Zeile, und im Ziel hatte danach genau eine Zeile ein Bild.
Der Grund ist simpel: `updatedat` hatte sich nicht geändert, und der Cursor schaut nur
dorthin. Inhaltlich hatte sich alles geändert, für Airbyte aber nichts.

Das trifft jede Änderung an der Ableitungslogik, nicht nur diese: neue Spalte, andere
Berechnung, korrigiertes Mapping. Wer das übersieht, hat im Ziel wochenlang alte Werte
stehen, ohne dass ein Sync fehlschlägt. Abhilfe war hier ein Anfassen des Cursors:

```sql
UPDATE hso_students SET updatedat = NOW() WHERE user_id IS NOT NULL;
UPDATE hso_personal SET updatedat = NOW() WHERE COALESCE(user_id,'') <> '';
```

Danach lief der Sync über alle 5.922 Zeilen (1.104.531 Bytes, PT33S) und die
Verknüpfung stand im Ziel. Alternativ hätte ein einmaliger Full Refresh gereicht.

### Der Primärschlüssel steht nur auf dem Papier

`user_id` ist als Primary Key konfiguriert, in der MySQL-Zieltabelle existiert aber weder
ein Primärschlüssel noch ein eindeutiger Index:

```sql
SHOW KEYS FROM hso_user;   -- jeder Index meldet Non_unique = 1
```

Airbyte legt lediglich `dedup_idx` auf `(_airbyte_extracted_at, user_id, updatedat)` an,
ebenfalls nicht eindeutig. Die Eindeutigkeit der 5.922 `user_id` kommt allein aus der
Dedup-Logik des Syncs. Fällt der Modus versehentlich auf Append zurück, nimmt die
Zieltabelle Duplikate widerspruchslos an. Dasselbe Muster hatten wir schon bei `fm_stamm`
(siehe [etl-prozess.md](etl-prozess.md)), hier ist es direkt nachgewiesen.

---

## Szenario 6: Web APIs

**Ziel:** REST-Schnittstellen für Datenzugriff; SOAP-Abfrage von HISinOne.

**6a, REST API via Airbyte:**
Airbyte kann REST-APIs als Source einbinden (HTTP-Source-Connector).

Für das Bereitstellen einer REST-API eignet sich ein separater Dienst:
- **PostgREST**: Generiert automatisch REST-API aus PostgreSQL-Schema
- **bereits in `docker-compose.yml` umgesetzt** (Service `postgrest`/`hso_postgrest`);
  starten mit `docker compose up -d postgrest`, dann z. B. `GET http://localhost:3000/k_plz?limit=5`.
  Die folgende Definition ist dort enthalten:

```yaml
postgrest:
  image: postgrest/postgrest:v12.2.3
  container_name: hso_postgrest
  environment:
    PGRST_DB_URI: postgres://destuser:destpassword@dest-postgres:5432/destdb
    PGRST_DB_SCHEMA: public
    PGRST_DB_ANON_ROLE: destuser
  ports:
    - "3000:3000"
  networks:
    - airbyte_net
```

Dann erreichbar:
- `GET http://localhost:3000/hso_students` → alle Studierenden
- `POST http://localhost:3000/hso_students` → neuen Eintrag anlegen

**6b, SOAP-Webservice (HISinOne):**
- Zugang zu `https://hisinone.hs-offenburg.de/qisserver/services2/` wird separat bereitgestellt
- Airbyte HTTP-Connector konfigurieren mit Security-Header
- Response (XML) in DB schreiben

---

## Bewertungsmatrix

| Szenario | Machbarkeit | Aufwand | Airbyte-Feature |
|----------|-------------|---------|-----------------|
| 1 Testdaten | einfach | niedrig | DB-Connector, File-Connector |
| 2 FM | möglich | mittel | Sync + dbt-Transformation |
| 3 Bilder/BLOB | eingeschränkt | hoch | BYTEA-Handling prüfen |
| 4 Mapping | möglich | mittel | Custom Transformation / dbt |
| 5 IdM Sync | gut | mittel | Incremental + Dedup |
| 6a REST | indirekt | mittel | PostgREST als Zusatzdienst |
| 6b SOAP | komplex | hoch | HTTP-Connector + XML-Parsing |
