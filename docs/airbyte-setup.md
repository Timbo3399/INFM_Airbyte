# Airbyte lokal aufsetzen

Offizielle Doku: https://docs.airbyte.com/platform/using-airbyte/getting-started/oss-quickstart

## Voraussetzungen

| Anforderung | Minimum | Empfohlen |
|-------------|---------|-----------|
| Docker Desktop | laufend | laufend |
| CPUs | 2 | 4+ |
| RAM | 8 GB | 8 GB+ |

> Der DB-Stack muss bereits laufen (Windows: `.\scripts\install.ps1` · Linux/macOS: `bash scripts/install.sh`).

---

## 1. abctl installieren

`abctl` ist Airbybes offizielles CLI-Tool. Es installiert und verwaltet Airbyte in einem
lokalen Kubernetes-Cluster (Kind), der automatisch in Docker Desktop laeuft.

### Automatisch (empfohlen)

**Windows (PowerShell):**
```powershell
.\scripts\setup-airbyte.ps1
```
**Linux / macOS:**
```bash
bash scripts/setup-airbyte.sh
```

Das Skript installiert `abctl`, fuegt es zum PATH hinzu und startet die Installation.

### Manuell

**Windows:**
1. Passende Version von https://github.com/airbytehq/abctl/releases/latest laden
   (`abctl-<version>-windows-amd64.zip` bzw. `-arm64`)
2. ZIP entpacken, `abctl.exe` nach `C:\tools\airbyte\` kopieren
3. Verzeichnis zum PATH hinzufuegen, neues Terminal, pruefen: `abctl version`

**Linux / macOS:**
```bash
# offizieller Installer (erkennt OS/Arch automatisch):
curl -LsfS https://get.airbyte.com | bash -
abctl version
```
Alternativ das passende Release-Asset laden (`abctl-<version>-linux-amd64.tar.gz`
bzw. `-darwin-arm64.tar.gz`), entpacken und `abctl` in den PATH legen.

---

## 2. Airbyte installieren

```powershell
abctl local install
```

Bei wenig RAM (unter 6 GB frei):

```powershell
abctl local install --low-resource-mode
```

Das Kommando fragt nach:
- **E-Mail-Adresse** (fuer den Admin-Account)
- **Organisations-Name** (z. B. `HSO`)

Die Installation dauert **5-10 Minuten** (Container-Downloads).

---

## 3. Airbyte UI oeffnen

**http://localhost:8000**

---

## 4. Login-Credentials

### Aktuelle Credentials anzeigen

```powershell
abctl local credentials
```

Ausgabe:
```
Email:         deine@email.de
Password:      <generiertes-passwort>
Client-ID:     ...
Client-Secret: ...
```

### Passwort aendern

```powershell
abctl local credentials --email login@example.com --password MeinNeuesPasswort123
```

> Die E-Mail ist der Login-Name in der UI und muss mitangegeben werden. Fehlt sie
> (Ausgabe `Email: [not set]`), bricht der reine `--password`-Aufruf mit
> `unable to determine organization email` ab.

---

## 5. Sources konfigurieren

### Uebersicht aller Sources

| Name in Airbyte | Typ | Verbindung |
|-----------------|-----|-----------|
| `HSO Source PostgreSQL` | PostgreSQL | `host.docker.internal:5433` |
| `HSO CSV k_plz` | File (local) | `/local/k_plz.csv` |
| `HSO CSV fm_gebaeude` | File (local) | `/local/fm_gebaeude.csv` |
| `HSO CSV fm_inst` | File (local) | `/local/fm_inst.csv` |
| `HSO CSV hso_students` | File (local) | `/local/hso_students.csv` |

---

### Source: PostgreSQL (Testdaten)

In der Airbyte UI: **Sources** -> **New Source** -> **Postgres**

| Feld | Wert |
|------|------|
| Source name | `HSO Source PostgreSQL` |
| Host | `host.docker.internal` |
| Port | `5433` |
| Database | `sourcedb` |
| Username | `sourceuser` |
| Password | `sourcepassword` |
| SSL mode | `disable` |

**Advanced -> Update Method:** `Scan Changes with User Defined Cursor`

> **Warum Cursor statt CDC (WAL)?**
> CDC benoetigt `wal_level = logical` + Replication Slot + Publication in PostgreSQL.
> Das ist fuer unsere Test-Umgebung nicht konfiguriert.
> `Xmin System Column` waere eine Alternative, hat aber Einschraenkungen bei hohem
> Transaktionsvolumen. Der Cursor-Modus funktioniert direkt mit unserer `updatedat`-Spalte
> (Szenario 5) und braucht keine weitere DB-Konfiguration.

> **Warum `host.docker.internal`?** Airbyte lauft in einem Kind-Cluster innerhalb
> von Docker Desktop. Die Connector-Container erreichen den Host-Rechner (und damit
> unsere DB-Container auf ihren exponierten Ports) ueber `host.docker.internal`.

**Test connection** klicken -> sollte gruen werden -> **Set up source**

Nach erfolgreichem Setup sind folgende Streams verfuegbar:

| Stream | Inhalt |
|--------|--------|
| `fm_gebaeude` | Gebaeude der Hochschule (25 Zeilen) |
| `fm_inst` | Institute / Org-Einheiten (~2.080 Zeilen) |
| `fm_stamm` | Raumstammdaten (Tabelle vorhanden, aktuell ohne Daten) |
| `k_plz` | PLZ-Verzeichnis (~34.000 Zeilen) |
| `hso_students` | ⚠️ NICHT als PG-Stream verfuegbar (CSV defekt) – stattdessen File-Connector (Abschnitt 7) |
| `fm_rna` | Raumnutzungsarten (~380 Zeilen) |
| `hso_personal` | Personal anonymisiert (~870 Zeilen) |

> Die relationalen Quell-Tabellen werden nach dem Stackstart durch tolerante
> Python-Loader gefuellt (laufen automatisch in `install.ps1`, Host-Python ODER
> Docker-Fallback): `load_json.py` (fm_rna, hso_personal), `load_fm_inst.py`,
> `load_fm_gebaeude.py`, `load_k_plz.py`.
> `hso_students` ist ausgenommen (CSV strukturell defekt) und wird unten als
> File-Connector-Quelle eingebunden.

---

## 6. Destinations konfigurieren

### Uebersicht aller Destinations

| Name in Airbyte | Typ | Verbindung |
|-----------------|-----|-----------|
| `HSO Dest PostgreSQL` | PostgreSQL | `host.docker.internal:5434` |
| `HSO Dest MySQL` | MySQL | `host.docker.internal:3306` |

---

### Destination: PostgreSQL

**Destinations** -> **New Destination** -> **Postgres**

| Feld | Wert |
|------|------|
| Destination name | `HSO Dest PostgreSQL` |
| Host | `host.docker.internal` |
| Port | `5434` |
| Database | `destdb` |
| Username | `destuser` |
| Password | `destpassword` |
| SSL mode | `disable` |

> **Warum Port 5434 statt 5432?**
> Port 5432 ist der PostgreSQL-Standardport. Auf vielen Windows-Rechnern laeuft bereits
> eine native PostgreSQL-Installation als Windows-Dienst (`postgres.exe`) auf diesem Port.
> Da Docker Desktop seine Port-Mappings ueber denselben Host-Port legt, wuerde eine externe
> Verbindung via `host.docker.internal:5432` an den nativen PostgreSQL-Dienst weitergeleitet
> statt an unseren Container — Authentifizierung schlaegt dann fehl.
> Port **5434** umgeht diesen Konflikt zuverlaessig.

### Destination: MySQL

**Destinations** -> **New Destination** -> **MySQL**

| Feld | Wert |
|------|------|
| Destination name | `HSO Dest MySQL` |
| Host | `host.docker.internal` |
| Port | `3306` |
| Database | `destdb` |
| Username | `destuser` |
| Password | `destpassword` |
| SSL Connection | **aus** (Toggle off) |
| JDBC URL Params | `allowPublicKeyRetrieval=true` |
| Raw table database | `destdb` |

> **Wichtige Hinweise fuer MySQL 8.0:**
> - **SSL ausschalten** - sonst schlaegt der Verbindungstest mit SSL-Handshake-Fehler fehl.
> - **JDBC URL Params** benoetigt `allowPublicKeyRetrieval=true` fuer die caching_sha2_password-Authentifizierung.
> - **Raw table database** muss auf `destdb` gesetzt werden. Leer lassen wuerde `airbyte_internal` als separate Datenbank anlegen, auf die `destuser` keinen Zugriff hat.
> - Der MySQL-Container startet mit `--local-infile=1` (in `docker-compose.yml`), da Airbyte dieses Flag zum Laden von Daten benoetigt.

---

## 7. Source: CSV-Flatfiles (File Connector)

Der Airbyte File Connector liest die CSV-Dateien aus dem Verzeichnis `sql/source/data`,
das `setup-airbyte.ps1` beim Install als `/local` in den abctl/kind-Cluster einhaengt
(Mechanismus siehe Hinweis am Ende dieses Abschnitts).

**Sources** -> **New Source** -> **File (CSV, JSON, Excel, Feather, Parquet)**

Alle CSV-Sources verwenden **Storage Provider: `local: Local Filesystem (limited)`**.

### HSO CSV k_plz

| Feld | Wert |
|------|------|
| Source name | `HSO CSV k_plz` |
| Dataset Name | `k_plz` |
| File Format | `csv` |
| Storage Provider | `local: Local Filesystem (limited)` |
| URL | `/local/k_plz.csv` |
| Reader Options | `{"sep": ","}` |

### HSO CSV fm_gebaeude

| Feld | Wert |
|------|------|
| Source name | `HSO CSV fm_gebaeude` |
| Dataset Name | `fm_gebaeude` |
| File Format | `csv` |
| Storage Provider | `local: Local Filesystem (limited)` |
| URL | `/local/fm_gebaeude.csv` |
| Reader Options | `{"sep": ","}` |

### HSO CSV fm_inst

| Feld | Wert |
|------|------|
| Source name | `HSO CSV fm_inst` |
| Dataset Name | `fm_inst` |
| File Format | `csv` |
| Storage Provider | `local: Local Filesystem (limited)` |
| URL | `/local/fm_inst.csv` |
| Reader Options | `{"sep": ";"}` |

### HSO CSV hso_students

| Feld | Wert |
|------|------|
| Source name | `HSO CSV hso_students` |
| Dataset Name | `hso_students` |
| File Format | `csv` |
| Storage Provider | `local: Local Filesystem (limited)` |
| URL | `/local/hso_students.csv` |
| Reader Options | `{"sep": "\|"}` |

### Uebersicht alle CSV-Sources

| Source Name | URL | Trennzeichen |
|---|---|---|
| `HSO CSV k_plz` | `/local/k_plz.csv` | `,` |
| `HSO CSV fm_gebaeude` | `/local/fm_gebaeude.csv` | `,` |
| `HSO CSV fm_inst` | `/local/fm_inst.csv` | `;` |
| `HSO CSV hso_students` | `/local/hso_students.csv` | `\|` (Pipe) |

> **Warum `local` und nicht `HTTPS: Public Web`?**
> Der `source-file`-Connector erzwingt bei `HTTPS: Public Web` immer eine TLS-Verbindung -
> auch wenn die URL mit `http://` beginnt. Ein lokaler HTTP-Server (z. B. `hso_fileserver`)
> wird damit nicht erreicht (`SSLError: WRONG_VERSION_NUMBER`). Daher ist `local` der
> zuverlaessige Weg fuer lokale Dateien.

> **Wie kommt `/local` in den Cluster? (abctl-spezifisch)**
> Mit abctl laeuft Airbyte in Kubernetes/kind - das Docker-Volume `oss_local_root` reicht
> hier NICHT, die Connector-Pods sehen es nicht. `setup-airbyte.ps1` loest das in zwei
> Schritten (bei manueller Installation selbst ausfuehren):
> 1. **Mount beim Install:** `sql/source/data` wird als `/local` in den kind-Node gehaengt:
>    `abctl local install --volume "/c/<repo>/sql/source/data:/local"`
>    Windows-Pfade in MSYS-Form `/c/...` angeben - abctl trennt den `--volume`-String stur
>    an `:`, sodass `C:\...` zu `is not a valid volume spec` fuehrt.
> 2. **Volume fuer Connector-Pods aktivieren:** danach
>    `JOB_KUBE_LOCAL_VOLUME_ENABLED=true` setzen und launcher/worker neu starten (sonst
>    haengt der launcher `/local` nicht in die Job-Pods ein):
>    ```bash
>    docker exec airbyte-abctl-control-plane kubectl --kubeconfig /etc/kubernetes/admin.conf \
>      patch configmap airbyte-abctl-airbyte-env -n airbyte-abctl --type merge \
>      -p '{"data":{"JOB_KUBE_LOCAL_VOLUME_ENABLED":"true"}}'
>    docker exec airbyte-abctl-control-plane kubectl --kubeconfig /etc/kubernetes/admin.conf \
>      rollout restart deploy/airbyte-abctl-workload-launcher deploy/airbyte-abctl-worker -n airbyte-abctl
>    ```

> **Dateien aktualisieren:** `/local` ist ein Live-Bind-Mount von `sql/source/data` -
> geaenderte oder neue CSVs dort sind im Connector sofort sichtbar (kein Kopieren noetig).
> Nur ein *geaenderter Mount-Pfad* erfordert `abctl local uninstall` + Neuinstallation,
> da `--volume` ausschliesslich bei der Cluster-Erstellung greift.

---

## 8. Connection anlegen und Sync starten

1. **Connections** -> **New Connection**
2. Source und Destination auswaehlen
3. **Streams** auswaehlen (z. B. `fm_gebaeude`, `hso_students`, `k_plz`)
4. **Sync Mode** pro Stream waehlen (siehe Tabelle unten)
5. **Save and sync now**

### Sync-Modi

| Modus | Liest | Schreibt | Wann verwenden |
|-------|-------|---------|----------------|
| Full Refresh Overwrite | Alles | Ersetzt Ziel komplett | Erster Test, kleine Tabellen |
| Full Refresh Append | Alles | Haengt an Ziel an | Historisierung ganzer Snapshots |
| Full Refresh Overwrite + Deduped | Alles | Ersetzt + dedupliziert | Frischer Stand ohne Duplikate |
| Incremental Append | Nur neue Zeilen | Haengt neue Zeilen an | Wachsende Logs, kein Cursor noetig |
| Incremental Append + Deduped | Nur neue Zeilen | Haengt an + dedupliziert | IdM-Sync (Szenario 5), Cursor: `updatedat` |

---

## 8. Nuetzliche abctl-Befehle

```powershell
# Status pruefen
abctl local status

# Logs anzeigen
abctl local logs

# Airbyte stoppen (Daten bleiben erhalten)
abctl local uninstall

# Alles loeschen (inkl. Daten)
abctl local uninstall --persisted
# danach Rest-Verzeichnis entfernen:
#   Windows:      Remove-Item -Recurse "$env:USERPROFILE\.airbyte\abctl"
#   Linux/macOS:  rm -rf ~/.airbyte/abctl
```

> **Bequemer:** Das Skript `scripts/uninstall.ps1` (bzw. `uninstall.sh`) entfernt Airbyte,
> den Docker-Stack und die Volumes in einem Schritt:
> ```powershell
> .\scripts\uninstall.ps1               # vollstaendig (mit Rueckfrage)
> .\scripts\uninstall.ps1 -KeepData     # DB-Daten behalten
> .\scripts\uninstall.ps1 -RemoveAbctl  # zusaetzlich abctl-Binary + PATH entfernen
> ```

---

## Verbindungsuebersicht

| Service | Fuer DB-Tools (lokal) | Fuer Airbyte (in der UI) |
|---------|----------------------|--------------------------|
| Source PostgreSQL | `localhost:5433` | `host.docker.internal:5433` |
| Dest PostgreSQL | `localhost:5434` | `host.docker.internal:5434` |
| Dest MySQL | `localhost:3306` | `host.docker.internal:3306` |
| File Server (HTTP) | `http://localhost:8888` | `/local/<datei>.csv` (local Storage) |
| Airbyte UI | http://localhost:8000 | - |
