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

**Reproduzierbarkeit.** Der komplette Stack lässt sich per Skript aufsetzen. Bei uns in
unter 20 Minuten, plattformunabhängig über je ein PowerShell- und ein Bash-Skript.
Damit ist eine Testumgebung jederzeit neu herstellbar, was bei den bisherigen
handgepflegten Talend-Jobs nicht gegeben ist.

**Datenbankanbindung.** PostgreSQL und MySQL funktionieren als Quelle und als Ziel
ohne Sonderbehandlung. Wir haben dieselben Daten parallel in beide Ziele gespiegelt und
in der Ziel-DB verifiziert.

**Monitoring.** Job-Historie, Attempt-Verlauf, Logs pro Sync mit Filter nach Komponente
und Log-Level. Aus den Logs lassen sich die Phasendauern einzeln auslesen, was unsere
Performance-Messungen überhaupt erst möglich gemacht hat. Benachrichtigung über Webhook
ist in der self-hosted Variante vorhanden.

**Inkrementelle Syncs.** Cursor-basiertes Incremental funktioniert zuverlässig und
braucht keine zusätzliche WAL-Konfiguration. Von den gemessenen Strategien hat
Incremental/Append die kürzeste Replikationsdauer.

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

---

## 3. Aufwand

### Einführung

| Posten | Einschätzung |
|---|---|
| Installation und Testumgebung | gering, einmalig automatisierbar. Unser Setup läuft skriptgesteuert in unter 20 Minuten |
| Einarbeitung in die Betriebsform | **hoch und unterschätzt.** Airbyte Community läuft über `abctl` in einem kind-Kubernetes-Cluster. Für die Fehlersuche sind `kubectl`-Kenntnisse nötig |
| Undokumentierte Hürden | wir haben vier Stolperfallen gefunden und gelöst, die in der offiziellen Doku nicht stehen. Ohne Kubernetes-Verständnis ist keine davon auffindbar, weil die UI nur „Pending" anzeigt |
| Connections einrichten | gering pro Tabelle, UI-geführt. Sync-Modus und Cursor müssen bewusst gewählt werden |
| Datenaufbereitung | **der größte Posten.** Für unsere fünf Quelltabellen waren sieben eigene Loader nötig |

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
