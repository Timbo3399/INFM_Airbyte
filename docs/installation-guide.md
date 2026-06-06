# Installationsanleitung – Campus Next-Gen Data-Hub

> **Für wen:** Alle Projektmitglieder (Timo + Kommilitonen)  
> **Zeitaufwand:** ca. 15–20 Minuten  
> **Betriebssystem:** Windows 10/11, Linux oder macOS  
> **Konvention:** Windows nutzt die PowerShell-Skripte (`.ps1`), Linux/macOS die Bash-Skripte (`.sh`) — gleiche Logik, gleiches Ergebnis.

---

## Inhaltsverzeichnis

1. [Voraussetzungen installieren](#1-voraussetzungen-installieren)
2. [Repo klonen](#2-repo-klonen)
3. [Automatische Installation (empfohlen)](#3-automatische-installation-empfohlen)
4. [Manuelle Installation](#4-manuelle-installation)
5. [Airbyte aufsetzen](#5-airbyte-aufsetzen)
6. [Erster Airbyte-Test](#6-erster-airbyte-test)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Voraussetzungen installieren

### 1.1 Docker Desktop

1. Download: https://www.docker.com/products/docker-desktop/
2. Installieren und **Docker Desktop starten**
3. Prüfen: Rechte Maustaste auf Docker-Icon in der Taskleiste → "Docker Desktop is running"

> **Wichtig:** Docker Desktop muss laufen, bevor die Skripte ausgeführt werden.

### 1.2 Git

1. Download/Installation:
   - **Windows:** https://git-scm.com/downloads
   - **Linux:** Paketmanager, z. B. `sudo apt install git`
   - **macOS:** `xcode-select --install` oder `brew install git`
2. Prüfen im Terminal: `git --version`

### 1.3 Python (optional)

Für das Standard-Setup **nicht zwingend nötig**: `install.ps1` lädt die Testdaten
sonst über einen Wegwerf-Docker-Container. Für die Szenarien 3 & 4 (Bild-Im/Export,
Account-Mapping) wird Python aber empfohlen.

1. Download: https://www.python.org/downloads/ (≥ 3.11)
2. Installer ausführen → **"Add Python to PATH" aktivieren!**
3. Prüfen: `python --version` (muss `Python 3.x` ausgeben, nicht den Store-Platzhalter)

---

## 2. Repo klonen

Terminal öffnen — **Windows:** PowerShell (Win+X → "Terminal"), **Linux/macOS:** Terminal:

```bash
git clone <repo-url>
cd INFM_Airbyte
```

---

## 3. Automatische Installation (empfohlen)

Das Installations-Skript übernimmt alles automatisch:

**Windows (PowerShell):**
```powershell
.\scripts\install.ps1
```
**Linux / macOS:**
```bash
bash scripts/install.sh
```

Das Skript:
- prueft alle Voraussetzungen (Docker, Git, Python)
- erstellt `.env` aus `.env.example`
- erstellt Docker-Volume `oss_local_root` (nur fuer den HTTP-File-Server; der abctl-File-Connector nutzt stattdessen den `/local`-Mount, s. airbyte-setup.md Abschnitt 7)
- laedt Docker-Images herunter
- startet alle vier Container (source-postgres, dest-postgres, dest-mysql, file-server)
- wartet bis alle Container healthy sind
- laedt die Testdaten in source-postgres via tolerante Python-Loader
  (`fm_rna`, `hso_personal`, `fm_inst`, `fm_gebaeude`, `k_plz`) — Host-Python optional,
  sonst automatischer Docker-Fallback (`hso_students` ist ausgenommen, s. u.)
- zeigt Verbindungsinfos an

**Erfolgreich, wenn die Ausgabe endet mit:**
```
Stack laeuft. Verbindungsparameter: ...
```

Danach weiter mit [Schritt 5: Airbyte aufsetzen](#5-airbyte-aufsetzen).

---

## 4. Manuelle Installation

Falls das automatische Skript nicht funktioniert:

**1. Konfigurationsdatei anlegen** — Windows: `Copy-Item .env.example .env` · Linux/macOS: `cp .env.example .env` (Passwörter bei Bedarf in `.env` anpassen)

**2.–4. Images laden, Stack starten, Status prüfen** (identisch auf allen Plattformen):
```bash
docker compose pull       # Images vorab laden
docker compose up -d      # Stack starten
docker compose ps         # warten bis alle "healthy" sind
```

> Anschließend Testdaten laden: Loader ausführen (siehe Abschnitt „Testdaten wurden nicht geladen" im Troubleshooting) — auf allen Plattformen via Host-Python **oder** Docker-Fallback.

---

## 5. Airbyte aufsetzen

Airbyte laeuft ueber `abctl` (offizielles Airbyte CLI) in einem lokalen Kubernetes-Cluster (Kind) innerhalb von Docker Desktop.

**Windows (PowerShell):**
```powershell
.\scripts\setup-airbyte.ps1
```
**Linux / macOS:**
```bash
bash scripts/setup-airbyte.sh
```

Das Skript:
- installiert `abctl` (Windows: nach `C:\tools\airbyte\` + PATH; Linux/macOS: via offiziellem Installer `curl … get.airbyte.com`)
- fragt nach Low-Resource-Mode (empfohlen bei weniger als 6 GB freiem RAM)
- startet `abctl local install` (läuft selbstständig, **nicht interaktiv**) und mountet dabei
  `sql/source/data` als `/local` in den Cluster + aktiviert das File-Connector-Volume
  (Details: [airbyte-setup.md](airbyte-setup.md) Abschnitt 7)
- danach Login-Passwort setzen (Schritt unten)

Die Installation dauert **5–10 Minuten** (Container-Downloads).

**Status pruefen:**

```powershell
abctl local status
```

**Airbyte UI oeffnen:** http://localhost:8000

**Login-Credentials anzeigen:**

```powershell
abctl local credentials
```

> Ausgabe zeigt E-Mail, generiertes Passwort, Client-ID und Client-Secret.

**Eigenes Passwort setzen** (E-Mail = Login-Name, muss mitangegeben werden):

```powershell
abctl local credentials --email login@example.com --password <gewuenschtes-passwort>
```

Weitere Details: [docs/airbyte-setup.md](airbyte-setup.md)

---

## 6. Erster Airbyte-Test

Der vollständige Walkthrough für den ersten ETL-Lauf (Postgres-Source → Postgres-Ziel,
Stream-Auswahl, Sync, mit Screenshot-Punkten) steht im Runbook:

→ **[etl-prozess.md](etl-prozess.md)**

Die ausführliche Feld-Referenz für **alle** Sources/Destinations (Postgres, MySQL, File)
findest du in [airbyte-setup.md](airbyte-setup.md).

---

## 7. Troubleshooting

### Container startet nicht / bleibt unhealthy

```powershell
# Logs des betroffenen Containers anzeigen
docker logs hso_source_postgres --tail 50
docker logs hso_dest_mysql --tail 50
```

Haeufige Ursachen:
- **Port belegt:** Ein anderer Dienst nutzt Port 5433, 5434 oder 3306. In `.env` und `docker-compose.yml` anderen Port eintragen.
- **Volumes aus altem Start:** Windows `.\scripts\stop.ps1 -v` · Linux/macOS `bash scripts/stop.sh -v` → dann neu starten

### Airbyte laeuft nicht / UI nicht erreichbar

```powershell
# Status pruefen
abctl local status

# Logs anzeigen
abctl local logs

# Neustart (bei haengenden Kind-Containern) - besser ueber das Setup-Skript,
# damit der File-Connector-Mount (/local) wieder gesetzt wird:
.\scripts\setup-airbyte.ps1
# (manuelles 'abctl local install' OHNE --volume verliert den /local-Mount!)
```

### Airbyte-Connector kann DBs nicht erreichen

Airbyte-Connector-Container kommunizieren ueber `host.docker.internal` mit den Datenbanken. Pruefen:

```bash
# DNS-Aufloesung testen (muss 192.168.65.x liefern) - alle Plattformen
docker run --rm alpine nslookup host.docker.internal
```
DB-Port vom Host prüfen (Ports 5433 / 5434 / 3306):
- **Windows:** `Test-NetConnection -ComputerName localhost -Port 5433`
- **Linux / macOS:** `nc -zv localhost 5433`

Falls die Ports nicht erreichbar sind, läuft der DB-Stack nicht → Windows `.\scripts\start.ps1`, Linux/macOS `bash scripts/start.sh`

### Airbyte: Passwortfehler bei Dest PostgreSQL (password authentication failed)

Ursache: Auf Port 5432 laeuft bereits ein nativer Windows-PostgreSQL-Dienst (`postgres.exe`).
Externe Verbindungen via `host.docker.internal:5432` landen dort statt bei `hso_dest_postgres`.

Pruefen ob ein zweiter Prozess auf Port 5432 lauscht:

```powershell
# Windows:
netstat -ano | findstr :5432
tasklist /fi "PID eq <pid>"        # postgres.exe = nativer PostgreSQL-Dienst
```
```bash
# Linux / macOS:
ss -ltnp 'sport = :5432'           # oder: lsof -i :5432
```

**Loesung:** Dest PostgreSQL laeuft deshalb auf Port **5434** (statt 5432).
In der Airbyte UI immer Port `5434` verwenden.

---

### Testdaten wurden nicht geladen (source-postgres ist leer)

Die relationalen Tabellen werden durch die Python-Loader **nach** dem Stackstart
gefüllt (idempotent: `TRUNCATE` + `INSERT`). Einfach erneut ausführen:

**Windows (PowerShell):**
```powershell
.\scripts\install.ps1
```
**Linux / macOS:**
```bash
bash scripts/install.sh
```
Oder die Loader einzeln (Host-Python mit `psycopg2`; sonst greift der Docker-Fallback der Skripte):
```bash
python3 scripts/load_json.py
python3 scripts/load_fm_inst.py
python3 scripts/load_fm_gebaeude.py
python3 scripts/load_k_plz.py
```

> Die CSV-`COPY`-Befehle im SQL-Init wurden entfernt — die Quell-CSVs sind zu
> unsauber für ein direktes `COPY` (eingebettete Header, unquotierte Trennzeichen,
> doppelt-kodierte Umlaute). `hso_students` bleibt in der Source-DB leer (CSV
> strukturell defekt) und wird via Airbyte File-Connector geladen.

### Python-Pakete fehlen

```bash
pip install requests psycopg2-binary      # Linux/macOS ggf. pip3 + virtuelle Umgebung (venv)
```

---

## Verbindungsübersicht

Alle Ports, Hosts und Zugangsdaten stehen zentral in
**[zugang.md](zugang.md#3-verbindungsparameter-zentrale-referenz)** (DB-Tools nutzen
`localhost`, die Airbyte-UI `host.docker.internal`).
