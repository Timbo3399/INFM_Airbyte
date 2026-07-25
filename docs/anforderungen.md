# Anforderungen und Umsetzungsstand

Diese Übersicht fasst alle Anforderungen aus dem Kickoff (`moodle/Kickoff.md`) und den
sechs Szenarien (`moodle/Projektszenarieren.md`, ausführlich in [testszenarien.md](testszenarien.md))
zusammen und bewertet, was Airbyte kann und wie weit wir sind.

Die abschließende Bewertung mit Vor- und Nachteilen, Aufwand und Empfehlung steht in
[bewertung-airbyte.md](bewertung-airbyte.md).

Stand: 2026-07-25.

---

## 1. System-Anforderungen aus dem Kickoff

| # | Anforderung | Airbyte-Fähigkeit | Stand im Projekt |
|---|---|---|---|
| A1 | **Open Source** und aktive Community | Airbyte OSS (MIT/ELv2), sehr aktive Community | **erfüllt**, war unser Auswahlkriterium |
| A2 | **DB-Anbindungen**, mindestens Informix, MySQL, PostgreSQL | Postgres und MySQL als Source und Destination vorhanden. Informix nur Enterprise-/Db2-nah, kein OSS-Connector | **teilweise.** PostgreSQL und MySQL erfüllt, Informix ist eine Lücke |
| A3 | **Datei-basiert**: CSV, Excel, JSON, XML | File-Connector deckt CSV, JSON, Excel, Feather und Parquet ab, XML nicht nativ | **teilweise.** CSV, JSON und Excel erfüllt, XML fehlt |
| A4 | **SOAP- und REST-APIs** abfragen | REST über den Connector-Builder (Low-Code). SOAP nicht nativ, nur als HTTP-POST mit eigenem XML-Parsing | **offen** (Szenario 6b) |
| A5 | **Daten-Mapping und Transformation** über eigenen Code | Transformationen über dbt (SQL) oder eigenen Connector. Kein freies Code-Mapping pro Feld wie in Talend | **teilweise.** Konzept steht, bedeutet aber einen Paradigmenwechsel zu dbt und SQL |
| A6 | **Low-Code REST-API bereitstellen** | Airbyte stellt selbst keine Daten-API bereit, dafür braucht es einen externen Dienst | **erfüllt** über PostgREST (`GET localhost:3000/k_plz` liefert Daten) |
| A7 | **Code-Snippets** ausführen (Python, JS, Groovy, Selenium) | Airbyte führt keine freien Skripte aus, nur dbt-SQL oder einen eigenen Connector über Python- bzw. Low-Code-CDK | **nicht erfüllt.** Das ist die größte Lücke gegenüber Talend und ein zentraler Evaluationsbefund |
| A8 | **Logging und Monitoring** von Jobs | Job-Historie, Status-UI, Logs pro Sync und Attempt, Timeline | **erfüllt** |
| A9 | **Usability, einfache Konfiguration** | Web-UI, Connector-Kataloge, geführte Setups | **erfüllt**, mit abctl-spezifischen Stolpersteinen (siehe [installation-guide.md](installation-guide.md)) |
| A10 | **Integration in die Hochschul-IT** | Läuft on-premise über abctl (kind), Anbindung über API und Terraform möglich | **teilweise.** Lokal evaluiert, die Produktiv-Integration ist offen |

---

## 2. Szenarien-Stand

| Szenario | Inhalt | Eignung von Airbyte | Stand | Nächster Schritt |
|---|---|---|---|---|
| **1 Testdaten einspielen** | Daten in MySQL und PostgreSQL, Postgres- und File-Connector testen | gut | **vollständig verifiziert.** PG nach PG und PG nach MySQL (je `fm_gebaeude` 25, `k_plz` 34.172), File nach PG mit `hso_students` 5.052 Zeilen, wo `COPY` keine einzige schaffte. Alle 5 Sources und 2 Destinations angelegt | abgeschlossen |
| **2 Facility Management** | PG-Tabellen `inst`, `geb`, `stamm`, daraus eine denormalisierte Raum-Tabelle in MySQL | Sync gut, Joins nur über dbt oder View | **teilweise.** `fm_inst`, `fm_gebaeude` und `fm_stamm` sind geladen | View oder dbt-Modell für `fm_raeume`, dann nach MySQL syncen |
| **3 Bilder als BLOB** | über 1.000 Bilder per API in BYTEA/Blob, später als Datei exportieren | eingeschränkt, BYTEA-Handling | **Skripte vorhanden** (`scripts/images/load_images.py`, `export_images.py`, ausgelegt auf über 1.100 Bilder über Seed-URLs) | Durchlauf dokumentieren, BYTEA-Sync nach MySQL prüfen |
| **4 Mapping Studenten/Personal** | Random-Daten, Account-Generator, in neue Tabellen schreiben | über dbt oder Custom-Code | **Schritt 1 und 2 umgesetzt.** Die Anonymisierung hatte alle Namensfelder geleert, ohne Namen erzeugte der Generator nichts. [`fill_random_names.py`](../scripts/mapping/fill_random_names.py) füllt sie deterministisch, [`generate_accounts.py`](../scripts/mapping/generate_accounts.py) vergibt daraus 5.922 eindeutige Accounts inklusive Kollisionszähler | Schritt 3: Zieltabellen für Studierende und Personal in `dest-postgres` anlegen und syncen |
| **5 IdM-System** | `hso_personal` und `hso_students` nach `hso_user` (MySQL), Sync bei Änderung, Bild-Verknüpfung | gut, Incremental mit Dedup | **Vorarbeit erledigt.** Die Incremental-Strategien sind gemessen und verglichen (siehe [call-notes-2026-06-16.md](call-notes-2026-06-16.md)). Der Primärschlüssel `user_id` ist jetzt über alle 5.922 Personen eindeutig belegt | Cursor `updatedat` und Primärschlüssel setzen, Connection für `hso_user` anlegen |
| **6 Web APIs** | 6a REST für Insert und Update, 6b SOAP gegen HISinOne | REST über PostgREST oder Builder, SOAP aufwendig | **6a erfüllt**, PostgREST liefert REST auf `destdb`, per GET verifiziert. **6b offen** | 6a: Schreibzugriff über JWT. 6b: HISinOne-Zugang abwarten |

> Zur Priorisierung: Der Betreuer hat am 09.06.2026 klargestellt, dass die Herangehensweise
> und die dokumentierten Lösungen zählen, nicht das vollständige Lösen aller sechs
> Szenarien. Wir haben deshalb bewusst Tiefe vor Breite gewählt.

---

## 3. Offene Punkte und Fragen an die Betreuer

Am 09.06.2026 beantwortet, Details in [betreuer-feedback-2026-06-09.md](betreuer-feedback-2026-06-09.md):

- **`hso_students.csv`** ist "roh wie beim Export", wir sollten eine eigene Alternative
  finden und dokumentieren. Gelöst über [`load_hso_students.py`](../scripts/load_hso_students.py),
  5.052 Zeilen.
- **`fm_stamm`** ist eine Systemtabelle und selbst über ETL-Mapping aus `rooms.xltx` zu
  füllen. Umgesetzt in [`load_fm_stamm.py`](../scripts/load_fm_stamm.py), 1.244 Zeilen
  aus 1.245 Quellzeilen (eine PK-Dublette wird verworfen).
- **Sync-Strategie:** Der Cursor über `updatedat` genügt. Der Methodenvergleich steht in
  [airbyte-setup.md §5](airbyte-setup.md), die Messreihen und die Bewertung in
  [bewertung-airbyte.md](bewertung-airbyte.md).
- **Szenario-Priorisierung:** siehe Hinweis in Abschnitt 2.

Weiterhin offen, vom Betreuer nicht adressiert:

- **Informix-Anbindung.** Es gibt keinen OSS-Connector. Ist Informix zwingend, oder
  genügen PostgreSQL und MySQL für die Evaluation?
- **Code-Snippet-Ausführung (A7)** ist Airbytes größte Lücke gegenüber Talend. Wie stark
  wiegt dieses Kriterium in der Bewertung?
- **SOAP-Zugang zu HISinOne** (Szenario 6b) soll testweise bereitgestellt werden. Wann?

---

## 4. Angelegte Airbyte-Objekte

**Sources:** `HSO Source PostgreSQL` (Postgres, User-Defined-Cursor), `HSO CSV hso_students`,
`HSO CSV k_plz`, `HSO CSV fm_gebaeude`, `HSO CSV fm_inst` (alle über den File-Connector,
Provider `local`, Pfad `/local/*.csv`).

**Destinations:** `HSO Dest PostgreSQL` (Port 5434), `HSO Dest MySQL` (Port 3306, SSL aus,
`allowPublicKeyRetrieval=true`).

**Connections**, alle erfolgreich gesynct und in der Ziel-DB verifiziert:

| Connection | Modus | Ergebnis |
|---|---|---|
| `HSO Source PostgreSQL` nach `HSO Dest PostgreSQL` | Full Refresh, Overwrite | `fm_gebaeude` 25, `k_plz` 34.172 |
| `HSO Source PostgreSQL` nach `HSO Dest MySQL` | Full Refresh, Overwrite | `fm_gebaeude` 25, `k_plz` 34.172 |
| `HSO CSV hso_students` nach `HSO Dest PostgreSQL` | Full Refresh, Overwrite | 5.052 Zeilen aus der zunächst als defekt eingeschätzten CSV |

**Zusatzdienst:** `hso_postgrest` (PostgREST) auf `dest-postgres`, REST-API unter
`http://localhost:3000`.
