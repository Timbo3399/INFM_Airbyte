# Bewertung: Airbyte als Talend-Ersatz

Abschließende Einschätzung aus der Evaluation. Deliverable aus dem Betreuer-Feedback
vom 09.06.2026 (siehe [betreuer-feedback-2026-06-09.md](betreuer-feedback-2026-06-09.md)):
Vor- und Nachteile plus Aufwandsabschätzung.

Grundlage sind die Anforderungen aus dem Kickoff ([anforderungen.md](anforderungen.md)),
die durchgeführten Szenarien ([testszenarien.md](testszenarien.md)) und die Messreihen
zu den Sync-Strategien ([call-notes-2026-06-16.md](call-notes-2026-06-16.md)).

---

## 1. Wo Airbyte überzeugt

**Kostenmodell.** Die self-hosted Edition Core ist kostenlos und ohne Volumengrenze.
Alle 600+ Connectoren sind enthalten, auch Change Data Capture und Schema-Propagation.
Bezahlt wird nur für Managed Hosting und Komfort, nicht für Funktionalität. Für eine
Hochschul-IT, die ohnehin on-premise betreibt, ist das der passende Zuschnitt.

**Reproduzierbarkeit, mit einer Einschränkung.** Der Stack lässt sich per Skript
aufsetzen, bei uns in unter 20 Minuten, plattformunabhängig über je ein PowerShell- und
ein Bash-Skript. Für die Datenbanken gilt das von Anfang an.

Für Airbyte selbst galt es zunächst nicht. Die Konfiguration, also Sources, Destinations
und Connections, liegt im kind-Cluster und ist nach `abctl local uninstall` verloren.
Uns ist das einmal passiert, und alle sieben Objekte mussten von Hand neu angelegt
werden. Airbyte bringt dafür keine Export- oder Backup-Funktion mit.

Lösbar ist es über die Public API: [`scripts/airbyte_setup_objects.py`](../scripts/airbyte_setup_objects.py)
legt die Objekte idempotent an, siehe [airbyte_api.md](airbyte_api.md#4-objekte-per-skript-anlegen).
Für einen Produktivbetrieb heißt das aber: die Airbyte-Konfiguration gehört als Code
versioniert, per API-Skript oder über den Terraform-Provider. Wer sich auf die UI
verlässt, hat seinen Stand nur im Cluster liegen.

**Datenbankanbindung.** PostgreSQL und MySQL funktionieren als Quelle und als Ziel
ohne Sonderbehandlung. Wir haben dieselben Daten parallel in beide Ziele gespiegelt und
in der Ziel-DB verifiziert.

**Monitoring.** Job-Historie, Attempt-Verlauf, Logs pro Sync mit Filter nach Komponente
und Log-Level. Aus den Logs lassen sich die Phasendauern einzeln auslesen, was unsere
Performance-Messungen überhaupt erst möglich gemacht hat. Benachrichtigung über Webhook
ist in der self-hosted Variante vorhanden.

**Inkrementelle Syncs.** Cursor-basiertes Incremental funktioniert zuverlässig und
braucht keine zusätzliche WAL-Konfiguration. Es spart Laufzeit, weil weniger Daten bewegt
werden. Schneller pro Datensatz ist es nicht: bei gleichen 100.000 Sätzen liegen
Full Refresh (38,08 s) und Incremental/Append (39,42 s) gleichauf.

---

## 2. Wo Airbyte nicht reicht

**Keine freie Code-Ausführung.** Das ist die größte Lücke gegenüber Talend und betrifft
Anforderung A7. Airbyte führt keine eigenen Skripte innerhalb eines Syncs aus. Wer
Feldlogik braucht, hat drei Wege: einen eigenen Connector bauen, nachgelagert mit dbt in
SQL transformieren, oder wie wir die Daten vor Airbyte aufbereiten. Talend erlaubt
Mapping-Code direkt im Job. Wer von dort migriert, muss jedes nicht-triviale Mapping neu
konzipieren, nicht nur portieren.

**ELT statt ETL.** Airbyte transportiert Rohdaten und transformiert nicht unterwegs. In
unserem Projekt hat sich das konkret gezeigt: der SQL-Init lud null von fünf Tabellen,
weil die Quell-CSVs eingebettete Header-Zeilen, NUL-Bytes, unquotierte Kommas und
doppelt kodierte Umlaute enthielten. Wir haben sieben eigene Python-Loader gebraucht,
um die Daten überhaupt in die Quell-DB zu bekommen. Diese Arbeit kann Airbyte nicht
übernehmen.

**Kein Informix-Connector.** Für Informix gibt es in der Open-Source-Variante keinen
Connector (A2). Da Informix in der Hochschul-Landschaft vorkommt, ist das eine harte
Einschränkung. Möglich wäre ein eigener Connector über das Python-CDK oder ein
vorgeschaltetes Skript, das nach PostgreSQL schreibt. Beides ist Zusatzaufwand.

**Kein XML.** Der File-Connector deckt CSV, JSON, Excel, Parquet und Feather ab, aber
kein XML (A3). Für SOAP-Antworten und XML-Dateien braucht es Vorverarbeitung.

**BLOBs gehen still verloren.** Das ist unser deutlichster Einzelbefund. Beim Sync von
1.100 Bildern aus einer PostgreSQL-BYTEA-Spalte nach MySQL meldet Airbyte Erfolg,
überträgt 16,5 MB und legt 1.100 Zeilen im Ziel an. Die Bildspalte ist danach in allen
1.100 Zeilen leer. Die Rohtabelle enthält die Daten noch, verloren gehen sie erst beim
Aufbau der Zieltabelle, und die Zielspalte ist `TEXT` statt eines Binärtyps.
`_airbyte_meta` verzeichnet dabei keinen einzigen verworfenen Wert.

Für die Bewertung ist weniger der fehlende BLOB-Support das Problem als die Art des
Scheiterns. Ein Job, der abbricht, fällt auf. Ein Job, der mit korrekter Zeilenzahl
Erfolg meldet und dabei den Inhalt fallen lässt, fällt erst auf, wenn jemand in die
Spalte schaut. Wer Airbyte für Binärdaten einsetzen will, braucht eigene Prüfungen im
Ziel, nicht nur die Job-Historie.

**Cursor-Syncs übersehen geänderte Logik.** Ein Incremental-Sync über einen Zeitstempel
bemerkt nur, was den Zeitstempel anfasst. Als wir die Ableitungslogik einer View
änderten und damit den Inhalt aller 5.922 Zeilen, übertrug der nächste Sync genau eine
Zeile. Kein Fehler, keine Warnung, im Ziel standen weiter die alten Werte. Nach jeder
Änderung an Mappings oder Views braucht es deshalb bewusst einen Full Refresh oder ein
Anfassen der Cursor-Spalte. Bei Talend, wo die Transformation im Job steckt, stellt sich
diese Frage nicht.

**Keine Daten-API.** Airbyte stellt selbst keine REST-Schnittstelle auf die Zieldaten
bereit (A6). Wir haben das mit PostgREST als zusätzlichem Dienst gelöst. Das
funktioniert, ist aber eine weitere Komponente im Betrieb.

**Keine Verkettung von Connections.** „B startet, wenn A fertig ist" gibt es nicht
nativ. Jede Connection hat nur ihren eigenen Zeitplan. Abhängigkeiten muss man per
Skript über die API oder mit einem Orchestrator abbilden.

**Custom Mappings sind kostenpflichtig.** Feldumbenennung, Hashing und Zeilenfilter in
der Connection-UI gibt es erst ab der Plus-Edition, nicht in Core.

**Erheblicher Overhead pro Sync.** Unsere Messreihen zeigen eine Grunddauer von etwa
27 Sekunden, unabhängig von der Datenmenge. Selbst bei 10 geänderten Datensätzen läuft
ein Sync knapp eine halbe Minute. Bis rund 20.000 geänderten Sätzen bleibt die
Gesamtdauer nahezu gleich. Für häufige Syncs kleiner Deltas ist das ineffizient, und
Intervalle unter 15 Minuten gibt es ohnehin erst in den Paid-Tiers.

**Deduplizierung kostet spürbar.** Bei 75.000 Datensätzen braucht Incremental/Append
39,67 s, derselbe Lauf mit Deduped 82,47 s. Wer wie in Szenario 5 einen Primärschlüssel
sauber halten muss, zahlt dafür etwa das Doppelte an Laufzeit.

**Constraints der Quelle kommen nicht mit.** Die Zieltabelle, die der Destination-Connector
anlegt, übernimmt den Primärschlüssel der Quelle nicht. Bei `fm_stamm` ist es uns zuerst
aufgefallen: unser Loader verwirft eine PK-Dublette und schreibt 1.244 Zeilen, der
File-Connector überträgt alle 1.245.

In Szenario 5 haben wir es dann direkt nachgesehen. `hso_user` in MySQL wird mit
`user_id` als Primärschlüssel und Modus *Append + Deduped* synchronisiert. In der
Zieltabelle steht danach trotzdem kein Primärschlüssel und kein eindeutiger Index,
`SHOW KEYS` meldet für jeden Index `Non_unique = 1`. Der von Airbyte angelegte
`dedup_idx` liegt auf `(_airbyte_extracted_at, user_id, updatedat)` und ist ebenfalls
nicht eindeutig. Die 5.922 eindeutigen `user_id` im Ziel sind also allein das Ergebnis
der Dedup-Logik im Sync, nicht einer Datenbank-Bedingung.

Praktisch heißt das: fällt der Sync-Modus versehentlich auf Append zurück oder greift die
Deduplizierung nicht, nimmt die Zieltabelle die Duplikate widerspruchslos an. Wer bisher
darauf vertraut, dass die Ziel-DB unsaubere Daten ablehnt, muss diese Absicherung bei
einer Migration selbst nachrüsten, etwa über nachgelagerte Constraints oder Tests.

---

## 3. Aufwand

### Einführung

| Posten | Einschätzung |
|---|---|
| Installation und Testumgebung | gering, einmalig automatisierbar. Unser Setup läuft skriptgesteuert in unter 20 Minuten |
| Einarbeitung in die Betriebsform | **hoch und unterschätzt.** Airbyte Community läuft über `abctl` in einem kind-Kubernetes-Cluster. Für die Fehlersuche sind `kubectl`-Kenntnisse nötig |
| Undokumentierte Hürden | wir haben vier Stolperfallen gefunden und gelöst, die in der offiziellen Doku nicht stehen. Ohne Kubernetes-Verständnis ist keine davon auffindbar, weil die UI nur „Pending" anzeigt |
| Connections einrichten | gering pro Tabelle, UI-geführt. Sync-Modus und Cursor müssen bewusst gewählt werden |
| Datenaufbereitung | **der größte Posten.** Für unsere zehn Quelltabellen waren sieben eigene Loader nötig |

### Laufender Betrieb

Der Betrieb selbst ist günstiger als bei Talend, weil Scheduling, Retry-Logik,
Logging und Job-Historie mitgeliefert werden. Die bisherigen Eigenbau-Skripte für
Job-Ausführung und Logging fallen weg. Dafür kommt der Betrieb eines
Kubernetes-Clusters hinzu.

### Migration von Talend

Der Aufwand hängt fast vollständig daran, wie viel Logik in den bestehenden Jobs steckt.
Reines Spiegeln von Tabellen ist schnell nachgebaut. Jobs mit Feldlogik, Fallunterscheidungen
oder Berechnungen müssen als dbt-Modelle oder als vorgeschaltete Skripte neu entstehen.
Eine belastbare Schätzung dafür setzt eine Inventur der bestehenden Talend-Jobs voraus,
die wir nicht hatten.

---

## 4. Empfehlung

Airbyte ist für den Anteil geeignet, der aus Replikation zwischen Datenbanken und
dateibasierten Quellen besteht. Dort spart es Eigenbau und bringt Monitoring mit.

Airbyte ist kein direkter Talend-Ersatz für Jobs mit eigener Transformationslogik. Diese
Fälle brauchen eine zweite Komponente, realistisch dbt. Die Entscheidung ist also nicht
„Airbyte statt Talend", sondern ob die Hochschul-IT bereit ist, das Modell auf
Extraktion mit Airbyte plus Transformation in SQL umzustellen.

Zwei Punkte sollten vor einer Entscheidung geklärt werden: ob Informix zwingend
angebunden werden muss, und wie viele der bestehenden Jobs echte Transformationslogik
enthalten.

---

## 5. Ausblick

Was aus dieser Evaluation heraus als nächstes sinnvoll wäre:

- **Informix und SOAP** über das Python-CDK anbinden und prüfen, ob ein eigener
  Connector wartbar bleibt. Alternativ ein vorgeschaltetes Skript in die Quell-DB.
- **dbt anbinden** und ein bestehendes Talend-Mapping exemplarisch als dbt-Modell
  nachbauen. Damit wird der Migrationsaufwand erstmals messbar statt geschätzt.
- **Sync-Modus pro Tabelle festlegen.** Nach unseren Messungen lohnt Incremental erst
  ab einer relevanten Änderungsmenge. Bei kleinen Tabellen ist Full Refresh
  einfacher und nicht langsamer.
- **Connection-Verkettung** über die Airbyte-API skripten, sofern Reihenfolgen nötig
  sind. Ein Orchestrator wäre für diese Größenordnung überdimensioniert.
- **Eigener Connector über den Connector Builder** für eine freie REST-API, um den
  Low-Code-Weg zu bewerten.
- **Betriebsfragen klären**, die wir lokal nicht beantworten konnten: Backup und
  Wiederherstellung des Airbyte-Zustands, Rechte- und Rollenkonzept, Verhalten bei
  Schema-Änderungen in Produktivquellen.
