# Abschlussbericht: Campus Next-Gen Data-Hub

**Evaluation von Airbyte als ETL-/Integrationswerkzeug (Ablösung von Talend)**

| | |
|---|---|
| Modul | INF-M Modul Projekte SoSe '26 |
| Gruppe | Airbyte |
| Bearbeiter | Lahres Timo <tlahres@stud.hs-offenburg.de> <br>Bräutigam Rebecca <rbraeuti@stud.hs-offenburg.de> <br> Horst Isabella <ihorst@stud.hs-offenburg.de> |
| Stand | 25.07.2026 |
| GitHub | <https://github.com/Timbo3399/INFM_Airbyte> |

> **Verhältnis zum Zwischenbericht.** Der [Zwischenbericht](zwischenbericht.md) vom
> 07.06.2026 bleibt als Abgabe unverändert stehen und beschreibt den Aufbau der
> Umgebung. Dieses Dokument ist das Gegenstück: es beantwortet die Evaluationsfrage.
> Wo der Zwischenbericht noch Vermutungen enthält, gilt der hier beschriebene Stand.

---

## Inhaltsverzeichnis

1. [Antwort auf die Evaluationsfrage](#1-antwort-auf-die-evaluationsfrage)
2. [Was wir gebaut haben](#2-was-wir-gebaut-haben)
3. [Stand der Szenarien](#3-stand-der-szenarien)
4. [Die tragenden Befunde](#4-die-tragenden-befunde)
5. [Anforderungen aus dem Kickoff](#5-anforderungen-aus-dem-kickoff)
6. [Aufwand](#6-aufwand)
7. [Empfehlung](#7-empfehlung)
8. [Was offen bleibt](#8-was-offen-bleibt)
9. [Nachvollziehen und nachrechnen](#9-nachvollziehen-und-nachrechnen)

---

## 1. Antwort auf die Evaluationsfrage

Airbyte kann Talend an der Hochschule Offenburg teilweise ersetzen. Die Trennlinie
verläuft nicht zwischen Werkzeugen, sondern zwischen Aufgabenarten.

Für **Replikation zwischen Datenbanken und dateibasierte Quellen** ist Airbyte
tragfähig und der einfachere Weg. Eine Connection steht in Minuten, Scheduling,
Retry-Logik, Job-Historie und Logs kommen mit. Die Eigenbau-Skripte, die heute für
Job-Ausführung und Logging nötig sind, entfallen.

Für **Jobs mit eigener Transformationslogik** ist Airbyte kein direkter Ersatz. Es
führt keinen eigenen Code aus und seit Version 2.1.1 auch kein dbt mehr. Solche Jobs
brauchen eine zweite Komponente und eine dritte Stelle, die die Reihenfolge herstellt.
Aus einem Werkzeug wird ein Werkzeugkasten.

Für **Binärdaten** ist Airbyte in der geprüften Konstellation ungeeignet, und zwar
nicht wegen einer fehlenden Funktion, sondern wegen der Art des Scheiterns. Der Sync
von 1.100 Bildern nach MySQL meldet Erfolg, legt die richtige Zeilenzahl an und lässt
den Inhalt fallen. Wer das nicht gezielt prüft, merkt es nicht.

Die ausformulierte Bewertung mit allen Abwägungen steht in
[bewertung-airbyte.md](bewertung-airbyte.md), die Befundtabelle in
[ergebnisse.md](ergebnisse.md).

---

## 2. Was wir gebaut haben

Die Evaluationsumgebung läuft vollständig lokal in Docker Desktop und bildet einen
Ausschnitt der Hochschul-Daten ab: anonymisierte Studierenden-, Gebäude-, Instituts-
und Personaldaten in zehn Quelltabellen.

Der Aufbau ist von Anfang bis Ende skriptgesteuert, in drei Schritten:

| Schritt | Skript | Was danach steht |
|---|---|---|
| 1 | `install` | Datenbank-Stack läuft, zehn Quelltabellen sind gefüllt |
| 2 | `setup-airbyte` | Airbyte Community Edition im kind-Cluster, UI erreichbar |
| 3 | `setup-szenarien` | Mapping, Bilder, Airbyte-Objekte, acht Syncs und dbt sind durch |

Schritt 3 arbeitet siebzehn Schritte in einer Reihenfolge ab, die nicht beliebig ist,
und überspringt, was schon steht. Der Weg von `git clone` bis zum vollständigen
Demo-Zustand steht in [installation-guide.md](installation-guide.md).

Dass es Schritt 3 gibt, ist selbst ein Ergebnis. Bis dahin endete der dokumentierte
Installationsweg nach Schritt 2, und wer ihn befolgte, landete bei einem leeren
Airbyte: die sieben Folgeschritte standen in der Dokumentation der einzelnen
Szenarien, aber nirgends als Ablauf.

Dazu gehört ein zweites Werkzeug, [`scripts/pruefe_szenarien.py`](../scripts/pruefe_szenarien.py).
Es prüft je Szenario den Sollzustand gegen die belegten Zahlen und gibt eine Tabelle
mit Soll, Ist und Status aus. Der Exit-Code ist 0, wenn alles stimmt. Die Zahlen in
diesem Bericht lassen sich damit nachrechnen statt nur nachlesen.

Der Code ist durch eine Testsuite abgedeckt, die bei jedem Pull Request gegen `main`
läuft ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)). Die Tests brauchen
keine laufende Datenbank: geprüft werden die reinen Funktionen der Loader und
Skripte, dazu die Sollwerte selbst und die zwingende Reihenfolge der Aufbauschritte.

---

## 3. Stand der Szenarien

| # | Szenario | Stand |
|---|---|---|
| 1 | Testdaten einspielen | vollständig verifiziert. PG nach PG und PG nach MySQL, je `fm_gebaeude` 25 und `k_plz` 34.172. Dazu `hso_students` mit 5.052 Zeilen über den File-Connector, wo `COPY` keine einzige Zeile schaffte |
| 2 | Facility Management | umgesetzt und verifiziert. Airbyte bringt die Rohtabellen nach dest-postgres, dbt baut `fm_raeume` mit 1.244 Räumen und 52.009 m², Airbyte reicht das Ergebnis nach MySQL weiter. Vier dbt-Tests grün |
| 3 | Bilder als BLOB | durchgeführt, mit dem deutlichsten Befund der Evaluation. 1.100 Bilder geladen (8.015 kB) und byteidentisch wieder exportiert. Der Sync nach MySQL legt 1.100 Zeilen an und lässt die Bildspalte in allen leer |
| 4 | Mapping Studenten und Personal | umgesetzt und verifiziert. 5.922 eindeutige Accounts nach HSO-Schema inklusive Kollisionszähler, dazu je eine Zieltabelle in dest-postgres: `hso_student_accounts` mit 5.052 und `hso_personal_accounts` mit 870 Zeilen, alle mit `user_id` und E-Mail |
| 5 | IdM-System | umgesetzt und verifiziert. View `hso_user` nach MySQL, Incremental mit Dedup über Cursor `updatedat` und Primärschlüssel `user_id`. 5.922 Zeilen mit 5.922 verschiedenen `user_id`, alle mit Bildverknüpfung |
| 6a | REST-API auf die Zieldaten | erfüllt über PostgREST, per GET verifiziert |
| 6b | SOAP gegen HISinOne | offen, hängt am externen Zugang |

Der Betreuer hat am 09.06.2026 klargestellt, dass die Herangehensweise und die
dokumentierten Lösungen zählen, nicht das vollständige Lösen aller sechs Szenarien
(siehe [betreuer-feedback-2026-06-09.md](betreuer-feedback-2026-06-09.md)). Wir haben
deshalb Tiefe vor Breite gewählt. Details je Szenario in
[testszenarien.md](testszenarien.md), der Abgleich gegen die Kickoff-Anforderungen in
[anforderungen.md](anforderungen.md).

---

## 4. Die tragenden Befunde

Die vollständige Liste mit je einem Beleg steht in [ergebnisse.md](ergebnisse.md).
Vier Befunde tragen die Entscheidung:

**BLOBs gehen still verloren.** Der Sync von BYTEA nach MySQL meldet Erfolg, überträgt
16,5 MB, legt 1.100 Zeilen an, und die Bildspalte ist in allen 1.100 leer. Die
Rohtabelle enthält die Daten noch, verloren gehen sie erst beim Aufbau der
Zieltabelle. `_airbyte_meta` verzeichnet keinen verworfenen Wert. Ein Job, der
abbricht, fällt auf. Dieser fällt erst auf, wenn jemand in die Spalte schaut.

**Der Primärschlüssel der Quelle kommt nicht mit.** `hso_user` wird mit `user_id` als
Primärschlüssel und Modus Append plus Deduped synchronisiert. In der Zieltabelle steht
danach kein eindeutiger Index, `SHOW KEYS` meldet für jeden Index `Non_unique = 1`.
Die 5.922 eindeutigen `user_id` sind allein das Ergebnis der Sync-Logik, nicht einer
Datenbank-Bedingung. Wer bisher darauf vertraut, dass die Ziel-DB unsaubere Daten
ablehnt, muss diese Absicherung selbst nachrüsten.

**Ein Cursor-Sync übersieht geänderte Ableitungslogik.** Nach dem Umbau einer View
hatten alle 5.922 Zeilen neue Werte. Der nächste Incremental-Sync übertrug genau eine.
Kein Fehler, keine Warnung. Nach jeder Änderung an Mappings oder Views braucht es
bewusst einen Full Refresh oder ein Anfassen der Cursor-Spalte.

**Airbyte 2.1.1 führt dbt nicht mehr aus.** Ein Connection-Objekt kennt weder
`transformations` noch `operations` oder `normalization`. Damit sind "Airbyte plus dbt"
zwei Werkzeuge mit zwei Zeitplänen, und die Reihenfolge stellt man selbst her.

### Ein Muster, das sich durch alle Befunde zieht

Die drei ersten Befunde haben denselben Zuschnitt: Airbyte meldet Erfolg, das Ergebnis
ist trotzdem falsch. Dasselbe Muster fanden wir zuletzt noch zweimal, als wir den
Aufbau von Null reproduzierbar machten. Zwei Connections, die denselben Stream in
dieselbe Zieltabelle schreiben, verdoppeln sie beim ersten Aufbau, weil Full Refresh
Overwrite nur echt ältere Generationen löscht und der Zähler pro Connection läuft. Und
eine Connection, deren Quelltabelle erst später im Ablauf entsteht, lässt sich vorher
nicht anlegen, weil Airbyte den Stream-Katalog einer Source zwischenspeichert. Beides
sind die Zeilen 27 und 28 in [ergebnisse.md](ergebnisse.md).

Beide wären in einem handgeklickten Setup unentdeckt geblieben. Für die Bewertung ist
das der eigentliche Punkt: der Betrieb von Airbyte braucht eigene Prüfungen im Ziel.
Die Job-Historie sagt, ob ein Sync gelaufen ist, nicht ob das Ergebnis stimmt.

---

## 5. Anforderungen aus dem Kickoff

| # | Anforderung | Ergebnis |
|---|---|---|
| A1 | Open Source und aktive Community | erfüllt |
| A2 | DB-Anbindungen, mindestens Informix, MySQL, PostgreSQL | teilweise. PostgreSQL und MySQL erfüllt, für Informix gibt es keinen OSS-Connector |
| A3 | Dateibasiert: CSV, Excel, JSON, XML | teilweise. CSV, JSON und Excel erfüllt, XML fehlt |
| A4 | SOAP- und REST-APIs abfragen | offen, Szenario 6b |
| A5 | Daten-Mapping und Transformation über eigenen Code | teilweise. Konzept steht, bedeutet aber einen Wechsel zu dbt und SQL |
| A6 | Low-Code REST-API bereitstellen | erfüllt über PostgREST als zusätzlichen Dienst |
| A7 | Code-Snippets ausführen | nicht erfüllt. Die größte Lücke gegenüber Talend |
| A8 | Logging und Monitoring von Jobs | erfüllt |
| A9 | Usability und einfache Konfiguration | erfüllt, mit abctl-spezifischen Stolpersteinen |
| A10 | Integration in die Hochschul-IT | teilweise. Lokal evaluiert, die Produktiv-Integration ist offen |

Begründungen je Zeile in [anforderungen.md](anforderungen.md).

---

## 6. Aufwand

Die Aufwandsschätzung ist der Teil, der am wenigsten mit dem Werkzeug zu tun hat.

Installation und Testumgebung sind gering und einmalig automatisierbar. Die
Einarbeitung in die Betriebsform ist dagegen hoch und wird unterschätzt: Airbyte
Community läuft über `abctl` in einem kind-Kubernetes-Cluster, und für die Fehlersuche
brauchte es `kubectl`. Undokumentierte Hürden waren durchgehend präsent. Vier standen
schon im Zwischenbericht, danach kamen ebenso viele dazu, keine davon in der
offiziellen Dokumentation.

Der größte Posten war die Datenaufbereitung. Der SQL-Init lud null von fünf Tabellen,
weil die Quell-CSVs eingebettete Header-Zeilen, NUL-Bytes, unquotierte Kommas und
doppelt kodierte Umlaute enthielten. Für die zehn Quelltabellen waren sieben eigene
Python-Loader nötig. Diese Arbeit kann Airbyte nicht übernehmen, denn es transportiert
roh und transformiert nicht unterwegs.

Für die Migration von Talend haben wir einen Datenpunkt, gemessen am Modell aus
Szenario 2. dbt einrichten war schnell: `pip install dbt-core dbt-postgres`, drei
kleine Konfigurationsdateien, keine Konflikte. Das Modell selbst ist einfaches SQL und
läuft in 0,10 s über 1.244 Zeilen.

Die Arbeit steckte woanders. Dass die Gebäudenummern in `fm_stamm` und `fm_gebaeude` in
zwei Formaten vorliegen und der Join deshalb ohne Normalisierung null Treffer liefert,
und dass das Institut an der Kostenstelle hängt und nicht am Nutzer, mussten wir erst
herausfinden. Beides steht in keiner Schema-Dokumentation.

Genau dieser Anteil steckt auch in den bestehenden Talend-Jobs, und er lässt sich nicht
übersetzen. Eine Migration ist keine Übertragung von Job zu Modell, sondern eine
erneute Auseinandersetzung mit den Daten. Wer den Aufwand schätzen will, sollte nicht
Jobs zählen, sondern fragen, wie viel undokumentiertes Wissen über Datenformate in
ihnen steckt. Eine belastbare Zahl setzt eine Inventur der bestehenden Jobs voraus, die
wir nicht hatten.

Ausführlich in [bewertung-airbyte.md, Kapitel 3](bewertung-airbyte.md#3-aufwand).

---

## 7. Empfehlung

Airbyte einführen für Replikation zwischen Datenbanken und für dateibasierte Quellen.
Dort spart es Eigenbau und bringt Monitoring mit.

Für Jobs mit Transformationslogik Airbyte plus dbt vorsehen. Die Kombination trägt, wir
haben sie in Szenario 2 durchgespielt: die Raumtabelle entsteht sauber, das Modell ist
getestet, das Ergebnis landet in MySQL. Der Preis ist Zerlegung. Ein Talend-Job wird zu
drei Schritten aus zwei Werkzeugen, und weil Airbyte dbt nicht ausführt und Connections
nicht verketten kann, liegt die Reihenfolge bei der Hochschul-IT. Für einen
überschaubaren Bestand ist das ein Skript, für viele abhängige Strecken ein
Orchestrator.

Die Entscheidung ist deshalb nicht "Airbyte statt Talend", sondern ob die Hochschul-IT
bereit ist, von einem Werkzeug auf einen kleinen Werkzeugkasten umzustellen.

**Drei Punkte vor einer Entscheidung klären:**

1. Muss Informix zwingend angebunden werden? Dann braucht es einen eigenen Connector
   über das Python-CDK oder ein vorgeschaltetes Skript.
2. Wie viele der bestehenden Jobs enthalten echte Transformationslogik? Das bestimmt
   den Migrationsaufwand fast vollständig.
3. Müssen Binärdaten übertragen werden? Nach dem BLOB-Befund ist das ein
   Ausschlusskriterium für diesen Weg.

Unabhängig von der Entscheidung: die Airbyte-Konfiguration gehört als Code versioniert,
per API-Skript oder Terraform-Provider. Sie liegt sonst nur im Cluster und ist nach
einem `abctl local uninstall` verloren. Uns ist das einmal passiert.

---

## 8. Was offen bleibt

**Szenario 6b (SOAP gegen HISinOne)** hängt am externen Zugang und ist nicht
umgesetzt. Der File-Connector unterstützt kein XML, SOAP-Antworten brauchen also
Vorverarbeitung.

**Szenario 6a Schreibzugriff.** Verifiziert ist der lesende Zugriff über PostgREST.
Insert und Update über JWT sind konzipiert, aber nicht durchgeführt.

Damit sind Szenario 1 bis 5 und 6a vollständig umgesetzt und verifiziert.

**Betriebsfragen**, die lokal nicht zu beantworten waren: Backup und
Wiederherstellung des Airbyte-Zustands, Rechte- und Rollenkonzept, Verhalten bei
Schema-Änderungen in Produktivquellen.

**Nächste sinnvolle Schritte** aus dieser Evaluation heraus stehen in
[bewertung-airbyte.md, Kapitel 5](bewertung-airbyte.md#5-ausblick). Der wichtigste:
ein echtes Talend-Mapping als dbt-Modell nachbauen. Das Gerüst steht, `fm_raeume`
zeigt, dass der Weg trägt. Erst ein Modell aus dem Produktivbestand misst den
Migrationsaufwand an realer Logik statt an unserem Testfall.

---

## 9. Nachvollziehen und nachrechnen

Die Umgebung lässt sich von Null aufbauen. Der Weg steht in
[installation-guide.md](installation-guide.md), drei Skripte und rund 40 Minuten,
davon der größere Teil Warten auf Downloads.

Danach beantwortet ein Aufruf die Frage, ob der Stand stimmt:

```bash
python scripts/pruefe_szenarien.py
```

Die Ausgabe stellt für jedes Szenario Soll und Ist gegenüber. Die Sollwerte sind
dieselben, die in [ergebnisse.md](ergebnisse.md) belegt sind, und sie sind hart
eingetragen. Liefert ein Lauf etwas anderes, ist das ein Befund und keine Einladung,
die Erwartung nachzuziehen.

Wir haben diesen Aufbau zum Abschluss einmal vollständig von Null durchgeführt, auf
leeren Datenbanken und frisch installiertem Airbyte. Drei Byte-Zahlen kamen dabei auf
das Byte genau wieder heraus: die 16.508.628 Bytes des Bild-Syncs, die 1.104.531 des
IdM-Syncs und die 191.991 des dbt-Ergebnisses, ebenso die Modelllaufzeit von 0,10 s.
Die Befunde dieses Berichts sind damit reproduzierbar und keine Eigenheit einer
einzelnen Sitzung.

---

## Anhang: Dokumentenübersicht

| Dokument | Inhalt |
|---|---|
| [ergebnisse.md](ergebnisse.md) | alle Befunde in einer Tabelle, je mit Beleg |
| [bewertung-airbyte.md](bewertung-airbyte.md) | ausformulierte Bewertung, Aufwand, Empfehlung, Ausblick |
| [testszenarien.md](testszenarien.md) | die sechs Szenarien im Detail |
| [anforderungen.md](anforderungen.md) | Kickoff-Anforderungen und Umsetzungsstand |
| [dbt.md](dbt.md) | dbt als Transformationsschicht, Modell und Tests |
| [performance.md](performance.md) | Messreihen zu den Sync-Strategien |
| [installation-guide.md](installation-guide.md) | Installation von `git clone` bis Demo-Zustand |
| [architektur.md](architektur.md) | Komponenten, Datenfluss, Netzwerk, Ports |
| [airbyte-setup.md](airbyte-setup.md) | Feld-Referenz aller Sources und Destinations |
| [airbyte_api.md](airbyte_api.md) | Public API und ihre Stolpersteine |
| [etl-prozess.md](etl-prozess.md) | Runbook des ersten ETL-Laufs |
| [quality_assurance.md](quality_assurance.md) | Vorgehen bei Tests und Qualitätssicherung |
| [zugang.md](zugang.md) | Zugangsdaten und Verbindungsparameter |
| [zwischenbericht.md](zwischenbericht.md) | Zwischenbericht vom 07.06.2026 |
