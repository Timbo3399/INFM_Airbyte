# Zwischenbericht — Campus Next-Gen Data-Hub

**Evaluation von Airbyte als ETL-/Integrationswerkzeug (Ablösung von Talend)**

| | |
|---|---|
| Modul | Informatik Master, SoSe 2026 |
| Gruppe | ‹Gruppenname / Mitglieder eintragen› |
| Bearbeiter | ‹Namen + Matrikelnummern› |
| Stand | 31.05.2026 |
| Abgabe | 07.06.2026 (Zwischenbericht + Doku) |

> *Hinweis: Mit ‹…› markierte Stellen sind vor der Abgabe von der Gruppe zu ergänzen.*

---

## 1. Projektziel & Kontext

Im Projekt evaluieren wir [Airbyte](https://airbyte.com/) als modernes ETL-/Daten­integrations­werkzeug mit dem Ziel, das bisher eingesetzte **Talend** in der Hochschul-IT abzulösen. Die gesamte Evaluationsumgebung läuft **lokal in Docker Desktop** und bildet einen realistischen Ausschnitt der Hochschul-Datenlandschaft (anonymisierte Studierenden-, Gebäude-, Instituts- und Personaldaten) ab.

Die Evaluation ist in **sechs Testszenarien** gegliedert (DB-Connector, Facility-Management-Sync, Bild-BLOBs, Studenten/Personal-Mapping, Incremental Sync/IdM, Web-APIs) — siehe [testszenarien.md](testszenarien.md).

---

## 2. Erreichte Meilensteine (Stand 31.05.2026)

| Meilenstein (lt. Betreuer-Mail) | Status | Beleg / Doku |
|---|---|---|
| **Installation des Systems** | ✅ Datenbank-Stack lauffähig; Airbyte vorbereitet | [installation-guide.md](installation-guide.md) |
| **Zugang für Betreuer** | ◑ dokumentiert, Einrichtung ‹ausstehend/erfolgt› | [zugang.md](zugang.md) |
| **Einfacher ETL-Prozess** | ◑ Runbook erstellt, Ausführung ‹ausstehend/erfolgt› | [etl-prozess.md](etl-prozess.md) |
| **Beginn der Dokumentation** | ✅ README + 6 Dokumente unter `docs/` | dieses Repo |

### 2.1 Installation

Das Setup ist vollständig skriptbasiert und reproduzierbar:

- `scripts/install.ps1` (Windows) bzw. `scripts/install.sh` (Linux/macOS) startet den kompletten Datenbank-Stack (Source-PostgreSQL, Ziel-PostgreSQL, Ziel-MySQL, CSV-File-Server), wartet auf den `healthy`-Status und lädt die Testdaten.
- `scripts/setup-airbyte.ps1` / `scripts/setup-airbyte.sh` installiert Airbyte Community Edition über das offizielle CLI `abctl` in einem lokalen Kubernetes-Cluster (kind) innerhalb von Docker Desktop.
- **Plattformen:** Das Setup steht für **Windows, Linux und macOS** bereit (identische Logik, plattformspezifische Skripte).

Alle vier Datenbank-/Server-Container laufen verifiziert im Zustand `healthy`.

### 2.2 Datenbasis (Source-PostgreSQL)

Die anonymisierten Testdaten sind geladen:

| Tabelle | Zeilen | Lademechanismus |
|---|---:|---|
| `fm_gebaeude` | 25 | `scripts/load_fm_gebaeude.py` |
| `fm_inst` | 2.083 | `scripts/load_fm_inst.py` |
| `k_plz` | 34.172 | `scripts/load_k_plz.py` |
| `fm_rna` | 379 | `scripts/load_json.py` |
| `hso_personal` | 870 | `scripts/load_json.py` |
| `hso_students` | 0 | ⚠️ nur via File-Connector (s. Kap. 4) |
| `fm_stamm` | 0 | keine Quelldatei (s. Kap. 5) |

---

## 3. Architektur (Kurzüberblick)

Detaillierte Beschreibung in [architektur.md](architektur.md). Kern: alle Dienste laufen in Docker Desktop in einem gemeinsamen Netzwerk (`airbyte_net`). Airbyte selbst läuft in einem kind-Cluster und erreicht die Datenbanken über `host.docker.internal`.

```
 Docker Desktop
 ┌──────────────────────────────────────────────────────────────┐
 │  source-postgres   ──┐                                        │
 │  (Testdaten)         │        Airbyte (kind-Cluster)          │
 │  localhost:5433      ├──────► UI  : localhost:8000            │
 │                      │        liest Source / schreibt Ziele   │
 │  file-server         │                                        │
 │  localhost:8888 ─────┘                │                       │
 │                          ┌────────────┴───────────┐           │
 │   dest-postgres  localhost:5434   dest-mysql  localhost:3306  │
 └──────────────────────────────────────────────────────────────┘
```

---

## 4. Besonderheit Datenqualität der Quell-CSVs

Die bereitgestellten CSV-Dateien ließen sich **nicht** per direktem PostgreSQL-`COPY` laden (Details in Kap. 5). Wir haben daher tolerante Python-Loader implementiert, die die Daten nach dem Containerstart bereinigt einspielen. Eine Datei — `hso_students.csv` — ist strukturell so inkonsistent, dass sie aktuell nicht zuverlässig in die relationale Source-DB geladen werden kann; Studierendendaten werden stattdessen über den **Airbyte File-Connector** als Flatfile-Quelle eingebunden.

---

## 5. Probleme & Lösungen

> *Dieses Kapitel ist gemäß Betreuer-Mail explizit gefordert.*

### 5.1 Windows-/Umgebungsspezifische Hürden

| Problem | Ursache | Lösung |
|---|---|---|
| `install.ps1` meldete „Python gefunden", JSON-Laden schlug aber fehl | `python` ist unter Windows oft nur der **Microsoft-Store-Platzhalter**; `Get-Command` findet ihn, er liefert aber keine echte Version | Echte Versionsprüfung (`py`/`python`/`python3`); zusätzlich **Docker-Fallback**, der die Daten ganz ohne Host-Python lädt |
| `setup-airbyte.ps1` fand kein abctl-Asset | Falsches Namensschema (`abctl_Windows_amd64.zip`) — korrekt ist `abctl-<version>-windows-<arch>.zip`; zudem liegt `abctl.exe` in einem Unterordner | Asset per Muster ermitteln, aus Unterordner entpacken; Architektur-Erkennung PowerShell-7-fest |
| File-Server-Container dauerhaft `unhealthy`, Setup lief in Timeout | Healthcheck nutzte `localhost` → im Container zuerst IPv6 (`::1`), nginx lauscht aber nur auf IPv4 | Healthcheck auf `127.0.0.1` umgestellt |

### 5.2 Datenqualität der Quell-CSVs (Hauptproblem)

Der SQL-Init lud die drei Kern-Tabellen **gar nicht** — `COPY` brach unter `ON_ERROR_STOP` bereits an der ersten fehlerhaften Datei ab, wodurch alle folgenden leer blieben. Die konkreten Defekte:

- **`fm_gebaeude.csv`**: unquotierte Kommas in Textfeldern (z. B. „Hörsäle,Bib.,RZ"), eingebettete Header-Zeilen.
- **`k_plz.csv`**: **3.417 Header-Zeilen** mitten in den Daten (zusammengesetzte Einzel-Exporte), Zeilen mit zu wenig Feldern, ein Feld (`krskfz`) breiter als das Schema (Kreis-Namen).
- **`fm_inst.csv`**: 86 Spalten (Tabelle nutzt 24), semikolon-getrennt, vereinzelt **NUL-Bytes**, doppelt-kodierte UTF-8-Umlaute.
- **`hso_students.csv`**: **strukturell defekt** — Datenzeilen haben mehr Spalten (~50–56) als der eigene Header (40), dazu unbalanciertes Quoting und Float-formatierte Integer.

**Lösung:** tolerante Python-Loader (`scripts/load_*.py`), die Header filtern, fehlerhafte Zeilen reparieren bzw. überspringen, NUL-Bytes und Mojibake bereinigen und Typkonvertierungen best-effort vornehmen. Der SQL-`COPY`-Schritt wurde entfernt (`01_load_data.sql`).

---

## 6. Offene Punkte / Fragen an die Betreuer

> *Ebenfalls gemäß Betreuer-Mail gefordert.*

1. **`hso_students.csv` — Soll-Struktur?** Die Datei ist nicht eindeutig ladbar (mehr Datenspalten als Header, defektes Quoting). Können Sie eine korrigierte Datei bereitstellen oder die beabsichtigte Spaltenstruktur/das Export-Format nennen? Dies blockiert aktuell Szenario 4 (Account-Mapping in die Source-DB).
2. **`fm_stamm`** (Raumstammdaten): Es liegt keine Quelldatei vor. Wird diese Tabelle benötigt, und woher sollen die Daten kommen?
3. **Zugang für Betreuer:** Airbyte Community Edition ist im Wesentlichen Single-User und läuft auf `localhost`. Wie soll Ihr Zugang erfolgen — gemeinsamer Admin-Login während des Vor-Ort-Termins, oder ist ein Remote-Zugang (z. B. Tunnel/VM) gewünscht? (Vorschlag in [zugang.md](zugang.md).)
4. **Sync-Strategie:** Wir nutzen den Cursor-Modus (`updatedat`) statt CDC, da CDC zusätzliche PostgreSQL-Konfiguration (logical WAL, Replication Slot) erfordert. Ist CDC für die Evaluation gewünscht?
5. **Scope:** Welche der sechs Szenarien haben für die Bewertung Priorität?

---

## 7. Nächste Schritte

- Ausführung des ersten ETL-Prozesses inkl. Screenshots ([etl-prozess.md](etl-prozess.md)).
- Bearbeitung der weiteren Szenarien (Facility-Management-Denormalisierung, BLOB-Bilder, Incremental Sync, Web-APIs).
- Klärung der offenen Fragen aus Kap. 6.

---

## Anhang: Repository-Struktur

Siehe [README.md](../README.md). Setup in unter 20 Minuten via `scripts/install.ps1` + `scripts/setup-airbyte.ps1`.
