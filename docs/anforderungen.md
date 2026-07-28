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
| **1 Testdaten einspielen** | Daten in MySQL und PostgreSQL, Postgres- und File-Connector testen | gut | **vollständig verifiziert.** PG nach PG und PG nach MySQL (je `fm_gebaeude` 25, `k_plz` 34.172), File nach PG mit `hso_students` 5.052 Zeilen, wo `COPY` keine einzige schaffte. Alle 6 Sources und 2 Destinations angelegt | abgeschlossen |
| **2 Facility Management** | PG-Tabellen `inst`, `geb`, `stamm`, daraus eine denormalisierte Raum-Tabelle in MySQL | Sync gut, Joins nur über dbt oder View | **umgesetzt und verifiziert.** Airbyte bringt die drei Rohtabellen nach `dest-postgres`, dbt baut daraus `fm_raeume` (1.244 Räume, 52.009 m²), Airbyte reicht das Ergebnis nach MySQL weiter. Vier dbt-Tests grün. Befund: die Gebäudenummern liegen in zwei Formaten vor, ohne Normalisierung trifft der Join 0 von 1.244 Zeilen | abgeschlossen, siehe [dbt.md](dbt.md) |
| **3 Bilder als BLOB** | über 1.000 Bilder per API in BYTEA/Blob, später als Datei exportieren | **nicht geeignet** für den Transport, BYTEA geht verloren | **durchgeführt.** 1.100 Bilder geladen (8.015 kB) und wieder exportiert, alle 1.100 Dateien byte-identisch. Der Airbyte-Sync nach MySQL meldet Erfolg, lässt die Bildspalte aber in allen 1.100 Zeilen leer | abgeschlossen, Befund in [testszenarien.md](testszenarien.md) |
| **4 Mapping Studenten/Personal** | Random-Daten, Account-Generator, in neue Tabellen schreiben | über dbt oder Custom-Code | **umgesetzt und verifiziert.** Die Anonymisierung hatte alle Namensfelder geleert, ohne Namen erzeugte der Generator nichts. [`fill_random_names.py`](../scripts/mapping/fill_random_names.py) füllt sie deterministisch, [`generate_accounts.py`](../scripts/mapping/generate_accounts.py) vergibt daraus 5.922 eindeutige Accounts inklusive Kollisionszähler. Schritt 3 über zwei Sichten ([`create_account_views.py`](../scripts/mapping/create_account_views.py)) nach `dest-postgres`: `hso_student_accounts` 5.052 Zeilen, `hso_personal_accounts` 870, alle mit `user_id` und E-Mail. Befund am Rande: die Sichten heißen absichtlich nicht wie ihre Quelltabellen, denn `hso_students` liegt schon aus dem File-Connector im Ziel, und zwei Connections auf denselben Stream verdoppeln die Tabelle (Zeile 27 in [ergebnisse.md](ergebnisse.md)) | abgeschlossen |
| **5 IdM-System** | `hso_personal` und `hso_students` nach `hso_user` (MySQL), Sync bei Änderung, Bild-Verknüpfung | gut, Incremental mit Dedup | **umgesetzt und verifiziert.** View `hso_user` (5.922 Zeilen) nach MySQL, Incremental mit Dedup über Cursor `updatedat` und Primärschlüssel `user_id`. Änderungstest bestanden, Deduplizierung greift, ab dem dritten Lauf werden nur noch Deltas gelesen (1 Zeile statt 5.922). Bild-Verknüpfung ergänzt, alle 5.922 Zeilen tragen ein `image_id`. Befunde: die Zieltabelle führt keinen Primärschlüssel, und eine geänderte View-Logik sieht der Cursor nicht | abgeschlossen |
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

Angelegt werden sie von [`setup_objects.py`](../scripts/airbyte/setup_objects.py) und
[`setup_connections.py`](../scripts/airbyte/setup_connections.py) über die Public API,
idempotent.

**Sechs Sources:** `HSO Source PostgreSQL` (Postgres, User-Defined-Cursor),
`HSO Transform PostgreSQL` (die Ziel-DB als Quelle, für `fm_raeume` in Szenario 2),
`HSO CSV hso_students`, `HSO CSV k_plz`, `HSO CSV fm_gebaeude`, `HSO CSV fm_inst`
(die vier letzten über den File-Connector, Provider `local`, Pfad `/local/*.csv`).

**Zwei Destinations:** `HSO Dest PostgreSQL` (Port 5434), `HSO Dest MySQL` (Port 3306,
SSL aus, `allowPublicKeyRetrieval=true`, `raw_data_schema=destdb`).

**Acht Connections**, alle erfolgreich gesynct und in der Ziel-DB verifiziert:

| Connection | Modus | Ergebnis |
|---|---|---|
| `HSO PG nach PG (Full Refresh)` | Full Refresh, Overwrite | `fm_gebaeude` 25, `k_plz` 34.172 |
| `HSO PG nach MySQL (Full Refresh)` | Full Refresh, Overwrite | `fm_gebaeude` 25, `k_plz` 34.172 |
| `HSO CSV hso_students nach PG` | Full Refresh, Overwrite | 5.052 Zeilen aus der zunächst als defekt eingeschätzten CSV |
| `HSO FM nach PG` | Full Refresh, Overwrite | `fm_stamm` 1.244, `fm_inst` 2.083 (Rohtabellen für dbt) |
| `HSO Accounts nach PG` | Full Refresh, Overwrite | `hso_student_accounts` 5.052, `hso_personal_accounts` 870 |
| `HSO Bilder nach MySQL` | Full Refresh, Overwrite | 1.100 Zeilen, Bildspalte leer (Befund 1) |
| `HSO IdM hso_user nach MySQL` | Incremental, Append + Deduped | 5.922 Zeilen, 5.922 verschiedene `user_id` |
| `HSO fm_raeume nach MySQL` | Full Refresh, Overwrite | 1.244 Zeilen, das dbt-Ergebnis aus Szenario 2 |

**Zusatzdienst:** `hso_postgrest` (PostgREST) auf `dest-postgres`, REST-API unter
`http://localhost:3000`.
