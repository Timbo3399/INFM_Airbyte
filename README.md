# Campus Next-Gen Data-Hub: Airbyte-Evaluation

**Informatik Master SoSe 2026** | Evaluierung von [Airbyte](https://airbyte.com/) als ETL/Integrations-Tool zur Ablösung von Talend in der Hochschul-IT. Alle Dienste laufen lokal in Docker Desktop.

---

## Ergebnis

Fünf von sechs Szenarien sind umgesetzt und gegen das laufende System verifiziert.
Die wichtigsten Befunde:

- **BLOBs gehen still verloren.** Der Sync von 1.100 Bildern aus einer BYTEA-Spalte
  nach MySQL meldet Erfolg und legt 1.100 Zeilen an, die Bildspalte ist in allen
  1.100 leer. Airbyte verzeichnet dazu keinen verworfenen Wert.
- **Der Primärschlüssel der Quelle kommt nicht mit.** In der MySQL-Zieltabelle steht
  trotz konfiguriertem Primary Key und Dedup-Modus kein eindeutiger Index. Die
  Eindeutigkeit kommt allein aus der Sync-Logik, nicht aus der Datenbank.
- **Cursor-Syncs übersehen geänderte Ableitungslogik.** Nach einem Umbau der
  Quell-View hatten alle 5.922 Zeilen neue Werte, der nächste Sync übertrug genau
  eine. Ohne Fehler und ohne Warnung.
- **Airbyte 2.1.1 führt dbt nicht mehr aus.** Die Empfehlung "Airbyte plus dbt"
  bedeutet damit zwei Werkzeuge mit zwei Zeitplänen, die Reihenfolge stellt man
  selbst her.
- **Was trägt: Replikation zwischen Datenbanken und dateibasierte Quellen.**
  PostgreSQL und MySQL laufen als Quelle und als Ziel ohne Sonderbehandlung, der
  File-Connector lud eine CSV, an der `COPY` gescheitert war.

**Empfehlung:** Für Replikation zwischen Datenbanken und dateibasierte Quellen ist
Airbyte geeignet und spart Eigenbau. Für Talend-Jobs mit eigener Transformationslogik
ist es kein direkter Ersatz, sie brauchen dbt als zweite Komponente und eine dritte
Stelle, die die Reihenfolge herstellt.

→ **Alle Befunde mit Belegzahlen und Verweisen: [docs/ergebnisse.md](docs/ergebnisse.md)**
· ausformulierte Bewertung: [docs/bewertung-airbyte.md](docs/bewertung-airbyte.md)

---

## Schnellstart

> Ausführliche Anleitung (inkl. Troubleshooting): **[docs/installation-guide.md](docs/installation-guide.md)**

### Schritt 1: Voraussetzungen installieren

> **Plattform:** läuft unter **Windows, Linux und macOS**. Windows nutzt die
> PowerShell-Skripte (`.ps1`), Linux und macOS die Bash-Skripte (`.sh`). Die Logik ist identisch.

| Tool | Download |
|------|----------|
| Docker Desktop / Engine | https://www.docker.com/products/docker-desktop/ (Linux: Docker Engine + Compose-Plugin) |
| Git | https://git-scm.com/downloads |
| Python ab 3.11 *(optional)* | https://www.python.org/downloads/ · ohne Python greift der Docker-Fallback |

### Schritt 2: Repo klonen

```powershell
git clone https://github.com/Timbo3399/INFM_Airbyte.git
cd INFM_Airbyte
```

### Schritt 3: Alles automatisch installieren

**Windows (PowerShell):**
```powershell
.\scripts\install.ps1
```
**Linux / macOS:**
```bash
bash scripts/install.sh
```

Startet den Datenbank-Stack und lädt die Testdaten automatisch.

### Schritt 4: Airbyte einrichten

**Windows (PowerShell):**
```powershell
.\scripts\setup-airbyte.ps1
```
**Linux / macOS:**
```bash
bash scripts/setup-airbyte.sh
```

Installiert Airbyte (via `abctl`) und startet die UI.  
**Airbyte UI:** http://localhost:8000 · Login anzeigen mit `abctl local credentials` (siehe [docs/zugang.md](docs/zugang.md))

### Schritt 5: Testszenarien durchführen

→ **[docs/testszenarien.md](docs/testszenarien.md)**

---

## Dokumentation

| Dokument | Inhalt |
|---|---|
| [docs/ergebnisse.md](docs/ergebnisse.md) | **Alle Befunde der Evaluation in einer Tabelle**, mit Beleg und Verweis |
| [docs/bewertung-airbyte.md](docs/bewertung-airbyte.md) | Abschluss-Bewertung: Vor-/Nachteile, Aufwand, Empfehlung, Ausblick |
| [docs/testszenarien.md](docs/testszenarien.md) | Die 6 Evaluations-Szenarien |
| [docs/anforderungen.md](docs/anforderungen.md) | Anforderungen & Umsetzungsstand (Kickoff + Szenarien) |
| [docs/dbt.md](docs/dbt.md) | dbt als Transformationsschicht (Szenario 2), Aufbau und Aufwand |
| [docs/installation-guide.md](docs/installation-guide.md) | Schritt-für-Schritt-Installation + Troubleshooting |
| [docs/architektur.md](docs/architektur.md) | Architektur: Komponenten, Datenfluss, Netzwerk, Ports |
| [docs/zugang.md](docs/zugang.md) | Zugang zu Airbyte-UI & DBs (inkl. Betreuer-Zugang) |
| [docs/airbyte-setup.md](docs/airbyte-setup.md) | Airbyte (abctl) installieren, Sources/Destinations |
| [docs/airbyte_api.md](docs/airbyte_api.md) | Airbyte Public API: Token, Requests, Objekte per Skript |
| [docs/etl-prozess.md](docs/etl-prozess.md) | Runbook: erster ETL-Prozess (mit Screenshot-Punkten) |
| [docs/zwischenbericht.md](docs/zwischenbericht.md) | Zwischenbericht (Abgabe 7.6.) |

> Offizielle Airbyte-Doku: <https://docs.airbyte.com/> · [abctl (Deployment)](https://docs.airbyte.com/platform/deploying-airbyte/abctl) · [File Source Connector](https://docs.airbyte.com/integrations/sources/file)

---

## Architektur

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Desktop                       │
│                                                         │
│  ┌──────────────────┐        ┌───────────────────────┐  │
│  │  source-postgres │        │       Airbyte         │  │
│  │  (Testdaten)     │◄──────►│  UI: localhost:8000   │  │
│  │  localhost:5433  │        │  API: localhost:8001  │  │
│  └──────────────────┘        └────────┬──────────────┘  │
│                                       │                 │
│  ┌──────────────────┐  ┌──────────────▼────────────┐    │
│  │   dest-mysql     │  │     dest-postgres         │    │
│  │   localhost:3306 │  │     localhost:5434        │    │
│  └──────────────────┘  └───────────────────────────┘    │
│                                                         │
│  Netzwerk: airbyte_net (alle Container verbunden)       │
└─────────────────────────────────────────────────────────┘
```

**Source** (`source-postgres`) ist vorgeladen mit anonymisierten Hochschuldaten:

| Tabelle | Inhalt |
|---------|--------|
| `hso_students` | Studierende (5.052). Die CSV galt zunächst als defekt, ist aber pipe-getrennt mit Pipes in einem gequoteten Feld und damit vollständig ladbar |
| `fm_gebaeude` | Gebäude der Hochschule Offenburg (25) |
| `fm_inst` | Institute und Organisationseinheiten (rund 2.080) |
| `fm_stamm` | Raumstammdaten (1.244), über ETL-Mapping aus `rooms.xltx`. Die Quelle hat 1.245 Zeilen, eine davon ist eine PK-Dublette |
| `k_plz` | PLZ-Verzeichnis Deutschland (34.172) |
| `anredetitel`, `k_hochschule`, `k_res` | Schlüsseltabellen aus HISinOne |

**6 Testszenarien** → [docs/testszenarien.md](docs/testszenarien.md):

| # | Szenario | Kern-Feature |
|---|----------|--------------|
| 1 | Testdaten einspielen | DB-Connector, File-Connector |
| 2 | Facility Management | Sync + Denormalisierung (dbt) |
| 3 | Bilder als BLOB | BYTEA-Handling, Python-Scripts |
| 4 | Studenten/Personal Mapping | Account-Generator, dbt |
| 5 | IdM System (Incremental Sync) | Incremental + Dedup |
| 6 | Web APIs (REST + SOAP) | HTTP-Connector, PostgREST |

---

## Projektstruktur

```
INFM_Airbyte/
├── docker-compose.yml          ← DB-Stack (source + dest)
├── .env.example                ← Vorlage für Umgebungsvariablen
├── .gitignore
├── .gitattributes              ← LF/CRLF-Regeln (Cross-Platform)
│
├── sql/
│   └── source/
│       ├── 00_tables.sql       ← Tabellen-Schema für source-postgres
│       ├── 01_load_data.sql    ← nur Doku-Hinweis (COPY entfernt, s. u.)
│       └── data/               ← Quelldateien für den File-Connector (/local-Mount im
│                                  kind-Node): hso_students, fm_gebaeude, fm_inst,
│                                  k_plz, rooms.xltx
│
├── data/                       ← Quelldaten nur für die Host-Loader (nicht im /local-Mount)
│   ├── csv/                    ← anredetitel, k_hochschule + k_res/ (k_res1 bis 13) → load_lookups.py
│   ├── js/                     ← hso_accountgenerator.js (HSO-Original-Logik, REFERENZ,
│   │                             nicht geladen; portiert in mapping/generate_accounts.py)
│   └── json/                   ← fm_rna.json, hso_personal.json → load_json.py
│
├── docker/fileserver/          ← nginx-Config für den CSV-File-Server
│
├── docs/
│   ├── ergebnisse.md           ← alle Befunde der Evaluation in einer Tabelle
│   ├── installation-guide.md   ← ausführliche Installationsanleitung
│   ├── architektur.md          ← Architektur (Komponenten, Datenfluss, Netz)
│   ├── zugang.md               ← Zugang zu UI/DBs (inkl. Betreuer-Zugang)
│   ├── airbyte-setup.md        ← Airbyte installieren & konfigurieren
│   ├── airbyte_api.md          ← Airbyte Public API (Token, Requests)
│   ├── etl-prozess.md          ← Runbook: erster ETL-Prozess
│   ├── testszenarien.md        ← Konkrete Testfälle
│   ├── anforderungen.md        ← Anforderungen & Umsetzungsstand
│   ├── bewertung-airbyte.md    ← Abschluss-Bewertung + Empfehlung
│   ├── call-notes-2026-06-16.md ← Sync-Modi, Messreihen, Editionen
│   ├── zwischenbericht.md      ← Zwischenbericht (Abgabe 7.6.)
│   └── betreuer-feedback-2026-06-09.md  ← Betreuer-Feedback + unsere Reaktion
│
├── dbt/                        ← Transformationsschicht (Szenario 2)
│   ├── dbt_project.yml · profiles.yml
│   └── models/fm_raeume.sql    ← denormalisierte Raumtabelle + Tests
│
├── tests/                      ← pytest für die reinen Loader-/Mapping-Funktionen
│   └── conftest.py in der Wurzel macht scripts/ importierbar
├── .github/workflows/ci.yml    ← CI: pytest bei jedem PR gegen main
├── pictures/                   ← Screenshots für die Doku
├── moodle/                     ← Aufgabenstellung (Kickoff, Szenarien)
│
└── scripts/                    ← .ps1 = Windows · .sh = Linux/macOS (gleiche Logik)
    ├── install.ps1 · install.sh        ← Komplett-Setup (DB-Stack + Testdaten)
    ├── setup-airbyte.ps1 · .sh         ← Airbyte via abctl installieren
    ├── start.ps1 · start.sh            ← Stack starten
    ├── stop.ps1 · stop.sh              ← Stack stoppen (-v für vollständigen Reset)
    ├── uninstall.ps1 · uninstall.sh    ← Airbyte (abctl) + Stack komplett entfernen
    ├── load_json.py                    ← lädt fm_rna + hso_personal (JSON)
    ├── load_fm_inst.py                 ← lädt fm_inst (Semikolon-CSV, 86→24 Spalten)
    ├── load_fm_gebaeude.py             ← lädt fm_gebaeude (repariert kaputte Zeilen)
    ├── load_k_plz.py                   ← lädt k_plz (filtert eingebettete Header)
    ├── load_lookups.py                 ← lädt anredetitel, k_hochschule, k_res
    ├── load_hso_students.py            ← lädt hso_students (quote-bewusster Pipe-Parser)
    ├── load_fm_stamm.py                ← lädt fm_stamm aus rooms.xltx (ETL-Mapping)
    ├── airbyte_setup_objects.py        ← legt Sources/Destinations per Public API an
    ├── airbyte_setup_connections.py    ← legt die Connections per Public API an
    ├── airbyte_run_sync.py             ← startet einen Sync und wartet auf das Ergebnis
    ├── mapping/                        ← Szenario 4: fill_random_names.py (Namen befüllen)
    │                                     + generate_accounts.py (Account-Generator)
    └── images/                         ← Szenario 3: BLOB-Im-/Export
```

---

## Verbindungsparameter

Ports, Hosts und Zugangsdaten (DB-Tools **und** Airbyte-UI) stehen zentral in
**[docs/zugang.md](docs/zugang.md#3-verbindungsparameter-zentrale-referenz)**.

Kurz: DB-Tools nutzen `localhost:5433/5434/3306`, in der **Airbyte-UI** dagegen
`host.docker.internal:<Port>` (Airbyte läuft im kind-Cluster, nicht im Docker-Netz).

---

## Nützliche Befehle

```powershell
# Stack-Status prüfen
docker compose ps

# Logs anzeigen
docker compose logs -f source-postgres

# In source-postgres einloggen
docker exec -it hso_source_postgres psql -U sourceuser -d sourcedb

# Vollständiger Reset (alle Daten löschen)
.\scripts\stop.ps1 -v

# Komplett deinstallieren (Airbyte/abctl + DB-Stack + Volumes)
.\scripts\uninstall.ps1                 # mit Rückfrage
.\scripts\uninstall.ps1 -KeepData       # DB-Daten behalten
.\scripts\uninstall.ps1 -RemoveAbctl    # zusätzlich abctl-Binary entfernen
```
