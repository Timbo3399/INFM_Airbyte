# Architektur — Campus Next-Gen Data-Hub

Dieses Dokument beschreibt den Aufbau der lokalen Evaluationsumgebung für Airbyte.

## 1. Entwurfsziele

- **Reproduzierbar & lokal:** Alles läuft in Docker Desktop, per Skript in < 20 Min. aufsetzbar.
- **Realistischer Datenausschnitt:** anonymisierte Hochschuldaten (Studierende, Gebäude, Institute, Personal, PLZ).
- **Klare Trennung Quelle/Ziel:** eine gefüllte Quell-DB, leere Ziel-DBs, in die Airbyte schreibt.
- **Zwei Zielsysteme** (PostgreSQL und MySQL), um Airbyte-Destination-Connectoren vergleichend zu testen.

## 2. Komponentenübersicht

| Komponente | Container | Image | Rolle | Host-Port → intern |
|---|---|---|---|---|
| Source-PostgreSQL | `hso_source_postgres` | `postgres:15-alpine` | Quell-DB mit Testdaten | `5433` → 5432 |
| Ziel-PostgreSQL | `hso_dest_postgres` | `postgres:15-alpine` | Airbyte-Ziel | `5434` → 5432 |
| Ziel-MySQL | `hso_dest_mysql` | `mysql:8.0` | Airbyte-Ziel | `3306` → 3306 |
| File-Server | `hso_fileserver` | `nginx:alpine` | HTTP-Browsing der CSV-Flatfiles (http://localhost:8888); der File-Connector selbst nutzt den `/local`-Mount, nicht diesen Server | `8888` → 80 |
| Airbyte | (kind-Cluster) | via `abctl` | ETL-Plattform / UI | `8000` (UI) |

Die vier erstgenannten Container werden über `docker-compose.yml` verwaltet. Airbyte wird **separat** über `abctl` installiert (eigener kind-Kubernetes-Cluster in Docker Desktop) und über das gemeinsame Netzwerk angebunden.

## 3. Netzwerk & Erreichbarkeit

- Alle Compose-Container liegen im Docker-Netz **`airbyte_net`** (bridge) und erreichen sich untereinander über ihre Container-Namen (z. B. `hso_source_postgres:5432`).
- **Airbyte läuft in einem kind-Cluster**, nicht direkt im selben Docker-Netz. Seine Connector-Pods erreichen die Datenbanken über den Host: **`host.docker.internal`** + den jeweiligen **Host-Port** (z. B. `host.docker.internal:5433` für die Source).

```
            ┌─────────────────────────── Docker Desktop ───────────────────────────┐
            │                                                                        │
  DB-Tools  │   ┌────────────────────┐                ┌───────────────────────────┐ │
  (DBeaver) │   │  hso_source_postgres│                │   Airbyte (kind-Cluster)  │ │
  ──5433──► │   │  Testdaten          │◄─ 5433 ───────►│   UI: localhost:8000      │ │
            │   └────────────────────┘  host.docker.   │   Worker/Connector-Pods   │ │
            │   ┌────────────────────┐  internal       └─────────────┬─────────────┘ │
  Browser   │   │  hso_fileserver     │◄─ 8888 ──────────────────────┤ schreibt       │
  ──8888──► │   │  CSV + /local/      │                              │ Ziele          │
            │   └────────────────────┘                ┌─────────────▼─────────────┐  │
            │   ┌────────────────────┐  5434           │  hso_dest_postgres        │  │
  ──5434──► │   │  hso_dest_postgres  │◄────────────────┤  (leer → Airbyte füllt)   │  │
            │   └────────────────────┘  3306           │  hso_dest_mysql           │  │
  ──3306──► │   │  hso_dest_mysql     │◄────────────────┴───────────────────────────┘  │
            │   └────────────────────┘   Netz: airbyte_net                              │
            └────────────────────────────────────────────────────────────────────────┘
```

## 4. Datenfluss (ETL)

1. **Extract:** Airbyte liest aus der Source-PostgreSQL (Stream pro Tabelle) bzw. aus CSV-Flatfiles über den File-Connector.
2. **Load/Transform:** Airbyte schreibt in die Ziel-DBs (PostgreSQL/MySQL). Transformationen/Normalisierung erfolgen je nach Szenario im Ziel (bzw. perspektivisch via dbt).

Die **Befüllung der Source-DB** erfolgt nicht durch Airbyte, sondern vorab durch tolerante Python-Loader (siehe Kap. 6), da die Roh-CSVs unsauber sind.

## 5. Designentscheidungen (Begründungen)

- **Ziel-PostgreSQL auf Port 5434** (statt 5432): Auf vielen Windows-Rechnern belegt ein nativer PostgreSQL-Dienst Port 5432; eine Airbyte-Verbindung über `host.docker.internal:5432` würde dort statt im Container landen. 5434 umgeht den Konflikt zuverlässig.
- **File-Connector via `local` Storage Provider** (`/local/<datei>.csv`) statt HTTP: Der `source-file`-Connector erzwingt bei „HTTPS: Public Web" eine TLS-Verbindung, ein lokaler HTTP-Server wird damit nicht erreicht. Unter abctl (Kubernetes/kind) sehen die Connector-Pods das Docker-Volume `oss_local_root` **nicht**; stattdessen mountet `setup-airbyte.ps1` das Verzeichnis `sql/source/data` beim Install via `abctl local install --volume …:/local` als `/local/` und aktiviert `JOB_KUBE_LOCAL_VOLUME_ENABLED=true` (Details: [airbyte-setup.md](airbyte-setup.md) Abschnitt 7).
- **MySQL mit `--local-infile=1`:** vom Airbyte-MySQL-Destination-Connector zum Laden benötigt.
- **Sync-Modus Cursor (`updatedat`)** statt CDC: vermeidet zusätzliche WAL-/Replication-Konfiguration (siehe offene Frage im Zwischenbericht).

## 6. Datenladung der Source-DB

Schema: `sql/source/00_tables.sql`. Die Daten werden **nach** dem Containerstart durch idempotente Python-Loader geladen (Host-Python **oder** automatischer Docker-Fallback), da die Quell-CSVs für ein direktes `COPY` zu unsauber sind:

| Loader | Tabelle | Besonderheit |
|---|---|---|
| `load_json.py` | `fm_rna`, `hso_personal` | JSON mit `{SQL_QUERY: [...]}`-Struktur |
| `load_fm_inst.py` | `fm_inst` | 86→24 Spalten, NUL-Bytes, Mojibake |
| `load_fm_gebaeude.py` | `fm_gebaeude` | unquotierte Kommas, eingebettete Header |
| `load_k_plz.py` | `k_plz` | 3.417 eingebettete Header gefiltert |

`hso_students` (CSV defekt) und `fm_stamm` (keine Quelldatei) sind aktuell nicht in der Source-DB — siehe Zwischenbericht, Kap. 6.

## 7. Ports & Zugang (Kurzreferenz)

| Dienst | Lokal (DB-Tools) | In Airbyte-UI eintragen |
|---|---|---|
| Source PostgreSQL | `localhost:5433` | `host.docker.internal:5433` |
| Ziel PostgreSQL | `localhost:5434` | `host.docker.internal:5434` |
| Ziel MySQL | `localhost:3306` | `host.docker.internal:3306` |
| File-Server (HTTP) | `http://localhost:8888` | `/local/<datei>.csv` |
| Airbyte UI | `http://localhost:8000` | — |

Zugangsdaten und Betreuer-Zugang: siehe [zugang.md](zugang.md).
