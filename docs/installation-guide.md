# Installationsanleitung: Campus Next-Gen Data-Hub

> **Für wen:** Alle Projektmitglieder (Timo + Kommilitonen)  
> **Zeitaufwand:** gut 35 bis 45 Minuten, der größere Teil davon Warten  
> **Betriebssystem:** Windows 10/11, Linux oder macOS  
> **Konvention:** Windows nutzt die PowerShell-Skripte (`.ps1`), Linux/macOS die Bash-Skripte (`.sh`). Beide treffen dieselben Entscheidungen und führen dieselben Python-Skripte aus.

Am Ende steht der Zustand, den [ergebnisse.md](ergebnisse.md) beschreibt.
`pruefe_szenarien.py` rechnet nach und sagt je Szenario, ob es laut seiner
Definition durchgelaufen ist.

---

## Der Weg in drei Schritten

Die Installation besteht aus drei Skripten, die aufeinander aufbauen. Wer nach
Schritt 2 aufhört, hat ein leeres Airbyte ohne Sources, Connections und Daten im
Ziel.

| Schritt | Skript | Dauer | Was danach steht |
|---|---|---|---|
| 1 | `install` | 15 bis 20 min | Datenbank-Stack läuft, zehn Quelltabellen sind gefüllt |
| 2 | `setup-airbyte` | 5 bis 10 min | Airbyte läuft im kind-Cluster, UI erreichbar |
| 3 | `setup-szenarien` | ca. 15 min | Mapping, Bilder, Airbyte-Objekte, Syncs und dbt sind durch |

Schritt 2 ist der einzige, der eine Eingabe verlangt (Low-Resource-Mode und
Passwort). Schritt 1 und 3 laufen selbstständig durch.

---

## Inhaltsverzeichnis

1. [Voraussetzungen installieren](#1-voraussetzungen-installieren)
2. [Repo klonen](#2-repo-klonen)
3. [Schritt 1: Datenbank-Stack und Testdaten](#3-schritt-1-datenbank-stack-und-testdaten)
4. [Schritt 2: Airbyte aufsetzen](#4-schritt-2-airbyte-aufsetzen)
5. [Schritt 3: Szenarien aufsetzen](#5-schritt-3-szenarien-aufsetzen)
6. [Zustand prüfen](#6-zustand-prüfen)
7. [Einzelne Schritte nachfahren](#7-einzelne-schritte-nachfahren)
8. [Manuelle Installation](#8-manuelle-installation)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Voraussetzungen installieren

### 1.1 Docker Desktop

1. Download: https://www.docker.com/products/docker-desktop/
2. Installieren und **Docker Desktop starten**
3. Prüfen: Rechte Maustaste auf Docker-Icon in der Taskleiste, dort muss "Docker Desktop is running" stehen

> **Wichtig:** Docker Desktop muss laufen, bevor die Skripte ausgeführt werden.
> Airbyte braucht mindestens 2 CPUs und 8 GB RAM.

### 1.2 Git

1. Download/Installation:
   - **Windows:** https://git-scm.com/downloads
   - **Linux:** Paketmanager, z. B. `sudo apt install git`
   - **macOS:** `xcode-select --install` oder `brew install git`
2. Prüfen im Terminal: `git --version`

### 1.3 Python

Für Schritt 1 ist Python **optional**: fehlt es, lädt `install` die Testdaten über
einen Wegwerf-Docker-Container. Für Schritt 3 ist es **Pflicht**, denn dbt und die
Airbyte-Skripte laufen auf dem Host. Einen Docker-Fallback gibt es dort nicht.

1. Download: https://www.python.org/downloads/ (mindestens 3.11)
2. Installer ausführen und dabei **"Add Python to PATH" aktivieren**
3. Prüfen: `python --version` muss `Python 3.x` ausgeben, nicht den Store-Platzhalter

Die Pakete installiert Schritt 3 selbst nach. Von Hand geht auch:

```bash
pip install -r requirements.txt
```

---

## 2. Repo klonen

Terminal öffnen. **Windows:** PowerShell (Win+X, dann "Terminal"), **Linux/macOS:** Terminal:

```bash
git clone https://github.com/Timbo3399/INFM_Airbyte.git
cd INFM_Airbyte
```

---

## 3. Schritt 1: Datenbank-Stack und Testdaten

**Windows (PowerShell):**
```powershell
.\scripts\install.ps1
```
**Linux / macOS:**
```bash
bash scripts/install.sh
```

Das Skript:
- prüft die Voraussetzungen (Docker, Git, Python)
- erstellt `.env` aus `.env.example`
- erstellt das Docker-Volume `oss_local_root` (nur für den HTTP-File-Server; der abctl-File-Connector nutzt stattdessen den `/local`-Mount, siehe [airbyte-setup.md](airbyte-setup.md) Abschnitt 7)
- lädt die Docker-Images
- startet die fünf Container (source-postgres, dest-postgres, dest-mysql, file-server, postgrest)
- wartet, bis alle Container healthy sind
- lädt die zehn Quelltabellen in source-postgres: `fm_rna`, `hso_personal`, `fm_inst`, `fm_gebaeude`, `k_plz`, `anredetitel`, `k_hochschule`, `k_res`, `hso_students`, `fm_stamm`

Ob die Loader auf dem Host oder in einem Container laufen, entscheidet das Skript
selbst: Host-Python nur dann, wenn `psycopg2` und `openpyxl` danach wirklich
importierbar sind, sonst der Docker-Fallback. Beide Plattformskripte wenden diese
Regel gleich an.

**Erfolgreich, wenn die Ausgabe endet mit:**
```
Stack laeuft. Verbindungsparameter: ...
```

Warum es sieben eigene Loader gibt und kein SQL-`COPY`: die Quell-CSVs haben
eingebettete Header-Zeilen, NUL-Bytes, unquotierte Kommas und doppelt kodierte
Umlaute. Der SQL-Init lud null von fünf Tabellen. Das ist Befund 15 in
[ergebnisse.md](ergebnisse.md).

---

## 4. Schritt 2: Airbyte aufsetzen

Airbyte läuft über `abctl` (das offizielle Airbyte CLI) in einem lokalen
Kubernetes-Cluster (kind) innerhalb von Docker Desktop.

**Windows (PowerShell):**
```powershell
.\scripts\setup-airbyte.ps1
```
**Linux / macOS:**
```bash
bash scripts/setup-airbyte.sh
```

Das Skript:
- installiert `abctl` (Windows: nach `C:\tools\airbyte\` plus PATH; Linux/macOS: über den offiziellen Installer `curl … get.airbyte.com`)
- fragt nach Low-Resource-Mode (empfohlen bei weniger als 6 GB freiem RAM)
- startet `abctl local install` und mountet dabei `sql/source/data` als `/local` in den Cluster, plus das File-Connector-Volume (Details: [airbyte-setup.md](airbyte-setup.md) Abschnitt 7)
- setzt danach das Login-Passwort

Die Installation dauert 5 bis 10 Minuten, überwiegend Container-Downloads.

**Status prüfen:**

```bash
abctl local status
```

**Airbyte UI öffnen:** http://localhost:8000

**Login-Credentials anzeigen:**

```bash
abctl local credentials
```

> Die Ausgabe zeigt E-Mail, generiertes Passwort, Client-ID und Client-Secret. Das
> Passwort steht im Klartext, deshalb nur bei Bedarf ausführen.

**Eigenes Passwort setzen.** E-Mail (also der Login-Name) und Passwort in **zwei
getrennten** Aufrufen, erst die E-Mail:

```bash
abctl local credentials --email login@example.com
```
```bash
abctl local credentials --password <gewuenschtes-passwort>
```

> Der **kombinierte** Aufruf `--email … --password …` schlägt fehl
> (`unable to determine organization email`). Hintergrund und Details:
> [airbyte-setup.md](airbyte-setup.md).

**Client-ID und Client-Secret in die `.env` eintragen.** Schritt 3 spricht die
Public API an und findet die Zugangsdaten dort zuerst:

```
AIRBYTE_CLIENT_ID=<aus abctl local credentials>
AIRBYTE_CLIENT_SECRET=<aus abctl local credentials>
```

Ohne die Einträge fragt Schritt 3 selbst `abctl local credentials` ab. Das
funktioniert, ist aber langsamer und setzt voraus, dass `abctl` im PATH liegt.

> **Nach einem Neuaufbau:** `abctl local install` vergibt neue Credentials, die
> alten in einer bestehenden `.env` gelten dann nicht mehr. Die Skripte merken
> das und fragen abctl nach den aktuellen Werten, melden es aber in der Ausgabe
> (`Credentials aus .env abgelehnt`). Wer die Zeile nicht sehen will, trägt die
> neuen Werte ein oder leert die beiden Zeilen.

---

## 5. Schritt 3: Szenarien aufsetzen

Hier entsteht der eigentliche Demo-Zustand. Bis hierher ist Airbyte leer: keine
Sources, keine Connections, nichts im Ziel.

**Windows (PowerShell):**
```powershell
.\scripts\setup-szenarien.ps1
```
**Linux / macOS:**
```bash
bash scripts/setup-szenarien.sh
```

Das Skript prüft die Voraussetzungen (Container laufen, Airbyte erreichbar,
Python-Pakete da) und arbeitet dann siebzehn Schritte in fester Reihenfolge ab:

| # | Schritt | Dauer | Was passiert |
|---|---|---|---|
| 1 | `namen` | ~2 s | Zufallsnamen in `hso_students` und `hso_personal` (die Quelldaten sind anonymisiert) |
| 2 | `accounts` | ~2 s | Account-IDs nach HSO-Schema, Szenario 4 |
| 3 | `bilder` | ~2 min | 1.100 Bilder als BYTEA in `hso_images`, Szenario 3 |
| 4 | `view` | ~1 s | View `hso_user` als gemeinsame IdM-Sicht, Szenario 5 |
| 5 | `accounts-views` | ~1 s | Views `hso_student_accounts` und `hso_personal_accounts`, Szenario 4 |
| 6 | `objekte` | ~30 s | Airbyte Sources und Destinations über die Public API |
| 7 | `connections` | ~2 min | Die acht Connections, inklusive Schema-Auffrischung |
| 8 | `sync-pg` | ~1 bis 2 min | `fm_gebaeude` und `k_plz` nach dest-postgres, Szenario 1 |
| 9 | `sync-mysql` | ~1 bis 2 min | dieselben beiden nach dest-mysql |
| 10 | `sync-students` | ~1 bis 2 min | `hso_students.csv` über den File-Connector |
| 11 | `sync-fm` | ~1 bis 2 min | `fm_stamm` und `fm_inst` nach dest-postgres |
| 12 | `sync-accounts` | ~1 bis 2 min | die beiden Account-Sichten je als eigene Zieltabelle, Szenario 4 |
| 13 | `sync-bilder` | ~1 bis 2 min | `hso_images` nach MySQL, Szenario 3 |
| 14 | `bilder-export` | ~10 s | die 1.100 Bilder zurück ins Dateisystem, Szenario 3 Teil B |
| 15 | `sync-idm` | ~1 bis 2 min | `hso_user` nach MySQL, Incremental mit Dedup, Szenario 5 |
| 16 | `dbt` | ~5 s | `fm_raeume` in dest-postgres bauen, Szenario 2 |
| 17 | `connections-raeume` | ~40 s | die vertagte Connection für `fm_raeume` nachziehen |
| 18 | `sync-raeume` | ~1 bis 2 min | das fertige Modell weiter nach MySQL |

Am Ende ruft das Skript `pruefe_szenarien.py` auf und zeigt den Sollzustand.

### Warum die Reihenfolge feststeht

- `accounts` braucht die Namen aus `namen`
- `view` braucht die Accounts, sonst ist sie leer (sie filtert auf gesetzte `user_id`)
- `view` braucht auch `bilder`, denn sie liest `hso_images`, und `CREATE OR REPLACE VIEW` prüft die referenzierten Tabellen sofort. Fehlt die Tabelle, bricht der Schritt mit `relation "hso_images" does not exist` ab
- `accounts-views` braucht die Accounts und muss vor `connections` liegen, denn Airbyte muss die Views beim Anlegen der Connection kennen
- `sync-idm` braucht die Bilder, sonst bleibt `image_id` im Ziel leer
- `dbt` braucht `sync-fm`, denn es baut `fm_raeume` aus `fm_stamm` in der Ziel-DB
- `sync-raeume` braucht `dbt`, denn es transportiert dessen Ergebnis
- `connections-raeume` liegt zwischen beiden: beim ersten Aufbau existiert `fm_raeume` in dest-postgres noch nicht, wenn `connections` läuft. Airbyte speichert den Stream-Katalog einer Source beim Anlegen zwischen (Befund 25), meldet den Stream also als unbekannt. Die Connection wird deshalb vertagt und nach dem dbt-Lauf nachgezogen

### Ein zweiter Lauf überspringt, was schon steht

Vor dem Lauf misst das Skript, welche Sollzustände erreicht sind, und lässt die
zugehörigen Schritte aus. Das lohnt sich, denn die Bilder brauchen drei Minuten
und jeder Sync rund eine. Auf einem fertigen Stack ist der Lauf in Sekunden
durch.

Nur ansehen, ohne etwas auszuführen:

```bash
python scripts/setup_szenarien.py --trockenlauf
```

---

## 6. Zustand prüfen

```bash
python scripts/pruefe_szenarien.py
```

Die Ausgabe beantwortet zuerst die Frage, auf die es ankommt: ist ein Szenario
laut seiner Definition durchgelaufen?

```
Szenario                                  Teilaufgaben  Pruefungen  Status
----------------------------------------  ------------  ----------  ---------------
Sz1   Einspielen der Testdaten                     3/3         5/5  erfuellt
Sz2   Facility Management                          2/2       10/10  erfuellt
Sz3   Testdaten fuer Bilder generieren             1/2         3/5  NICHT erfuellt
Sz4   Mapping von Studenten und Personal           3/3       15/15  erfuellt
Sz5   IdM-System                                   2/2         8/8  erfuellt
Sz6a  Web-API: REST                                1/1         3/3  erfuellt
Sz6b  Web-API: SOAP (HISinOne)                       -           -  nicht umgesetzt

Szenarien: 5 von 6 erfuellt, 1 nicht erfuellt, 1 nicht umgesetzt.
```

Ein Szenario gilt als erfüllt, wenn jede Pflichtprüfung jeder seiner
Teilaufgaben stimmt. Die Gliederung in Teilaufgaben folgt
[testszenarien.md](testszenarien.md): A und B bei Szenario 2 und 3, Schritt 1
bis 3 bei Szenario 4. Damit zeigt die Tabelle nicht nur, *dass* etwas fehlt,
sondern welcher Teil der Aufgabenstellung.

Was offen ist, steht darunter, mitsamt dem Kommando, das es herstellt:

```
Offen:

  Sz3  B  Bilder aus der Datenbank exportieren
      Dateien in data/images        erwartet     1.100   gefunden         0
      Bytes in data/images          erwartet 8.207.021   gefunden         0
      -> python scripts/images/export_images.py
```

Der Exit-Code ist 0, wenn jedes geprüfte Szenario erfüllt ist, sonst 1. Damit
taugt das Skript auch für CI oder eine Schleife im Terminal. Szenario 6b zählt
nicht dagegen: es ist nicht umgesetzt, weil der externe Zugang aussteht, und
steht mit genau diesem Status in der Tabelle. Es wegzulassen wäre die
unehrlichere Variante, in einer Bewertung ist gerade die Lücke eine Aussage.

### Dokumentierte Befunde stehen getrennt

Am Ende folgt ein eigener Block:

```
Dokumentierte Befunde (erwartete Fehlschlaege, kein Mangel des Aufbaus):

Dokumentierter Befund                                 erwartet  gemessen  Status      Beleg
---------------------------------------------  ---------------  --------  ----------  ---------
Sz2  derselbe Join ohne lpad trifft nichts                   0         0  bestaetigt  Befund 16
Sz3  hso_images Zeilen in MySQL                          1.100     1.100  bestaetigt  Befund 1
Sz3  hso_images mit Inhalt in MySQL                          0         0  bestaetigt  Befund 1
Sz5  eindeutige Indizes auf hso_user in MySQL                0         0  bestaetigt  Befund 2
Sz5  Rohtabelle behaelt jede Generation        5.922 oder mehr     5.922  bestaetigt  Befund 5
```

Die Zeile `hso_images mit Inhalt in MySQL` erwartet eine 0, und das ist kein
Tippfehler. Der Sync legt in MySQL 1.100 Zeilen an, überträgt den Bildinhalt
nicht und meldet trotzdem Erfolg. Das ist der wichtigste Befund der Evaluation,
nachzulesen in [ergebnisse.md](ergebnisse.md) Zeile 1.

Solche Befunde stehen bewusst nicht in der Szenario-Wertung. Sie sind Ergebnisse
der Evaluation, keine Mängel des Aufbaus: dass Airbyte BLOBs verliert, macht
Szenario 3 nicht unerfüllt, denn das Szenario-Ziel ist über die Python-Skripte
erreicht. Sie heißen deshalb `bestaetigt` und nicht `ok` — ein `ok` neben
"0 übertragene Bilder" liest sich, als wäre das in Ordnung.

Reproduziert ein Befund **nicht** mehr, meldet das Skript ihn laut als
`NICHT reproduziert`. Der Exit-Code bleibt davon unberührt: dann ist nicht der
Aufbau kaputt, sondern [ergebnisse.md](ergebnisse.md) veraltet.

### Weitere Aufrufe

Nur einzelne Szenarien prüfen, etwa für die Präsentation:

```bash
python scripts/pruefe_szenarien.py Sz3 Sz5
```

Jede einzelne Prüfung sehen, nach Teilaufgaben gruppiert:

```bash
python scripts/pruefe_szenarien.py --detail
```

Nur die Urteilszeile, etwa für ein Skript:

```bash
python scripts/pruefe_szenarien.py --leise
```

Alle Sollwerte sind belegt, in [ergebnisse.md](ergebnisse.md) oder in
[testszenarien.md](testszenarien.md); der Beleg steht im Kommentar daneben.
Weicht ein Lauf ab, ist das ein Befund und keine Einladung, die Erwartung
nachzuziehen.

---

## 7. Einzelne Schritte nachfahren

Manchmal soll nur ein Teil laufen, etwa nach einer Änderung am dbt-Modell.

```bash
python scripts/setup_szenarien.py --liste
```
zeigt alle Schritte mit ihren Namen.

```bash
python scripts/setup_szenarien.py --nur dbt,sync-raeume
```
führt genau diese aus, in der festen Reihenfolge.

```bash
python scripts/setup_szenarien.py --ab dbt
```
führt diesen Schritt und alles danach aus. Praktisch nach einem Abbruch, das
Skript nennt den passenden Aufruf selbst.

```bash
python scripts/setup_szenarien.py --erzwingen
```
lässt auch die Schritte laufen, deren Sollzustand schon steht.

Einen Sync einzeln starten und dabei zusehen:

```bash
python scripts/airbyte/run_sync.py --list
```
```bash
python scripts/airbyte/run_sync.py "HSO IdM hso_user nach MySQL"
```

---

## 8. Manuelle Installation

Falls das automatische Skript in Schritt 1 nicht durchläuft:

**1. Konfigurationsdatei anlegen.** Windows: `Copy-Item .env.example .env`, Linux/macOS: `cp .env.example .env` (Passwörter bei Bedarf in `.env` anpassen)

**2. bis 4. Images laden, Stack starten, Status prüfen** (auf allen Plattformen gleich):
```bash
docker compose pull
```
```bash
docker compose up -d
```
```bash
docker compose ps
```
Warten, bis alle Container "healthy" melden.

**5. Testdaten laden.** Die Loader in dieser Reihenfolge:
```bash
python scripts/load_json.py
```
```bash
python scripts/load_fm_inst.py
```
```bash
python scripts/load_fm_gebaeude.py
```
```bash
python scripts/load_k_plz.py
```
```bash
python scripts/load_lookups.py
```
```bash
python scripts/load_hso_students.py
```
```bash
python scripts/load_fm_stamm.py
```

Alle Loader sind idempotent (`TRUNCATE` plus `INSERT`), ein zweiter Lauf schadet
also nicht.

Schritt 2 und 3 gibt es nicht von Hand: `abctl local install` braucht den
`--volume`-Mount aus dem Setup-Skript, und die siebzehn Szenario-Schritte von
Hand nachzuklicken ist genau die Arbeit, die `setup-szenarien` abnimmt.

---

## 9. Troubleshooting

### Container startet nicht oder bleibt unhealthy

```bash
docker logs hso_source_postgres --tail 50
```
```bash
docker logs hso_dest_mysql --tail 50
```

Häufige Ursachen:
- **Port belegt:** Ein anderer Dienst nutzt Port 5433, 5434, 3306, 8888 oder 3000. In `.env` und `docker-compose.yml` einen anderen Port eintragen.
- **Volumes aus altem Start:** Windows `.\scripts\stop.ps1 -v`, Linux/macOS `bash scripts/stop.sh -v`, danach neu starten.

### Airbyte läuft nicht oder die UI ist nicht erreichbar

```bash
abctl local status
```
```bash
abctl local logs
```

Neustart bei hängenden kind-Containern besser über das Setup-Skript, damit der
`/local`-Mount wieder gesetzt wird:

```powershell
.\scripts\setup-airbyte.ps1
```

Ein manuelles `abctl local install` **ohne** `--volume` verliert den
`/local`-Mount, und danach findet der File-Connector die CSVs nicht mehr.

### Airbyte ist abgestürzt

Bei Ressourcen-Limits hängt sich Airbyte gelegentlich mit einer unspezifischen
Fehlermeldung auf. Dann den Cluster bereinigen:

1. Hängenden Pod finden (Status `unknown`, `CrashLoopBackOff` oder `error`):

```bash
docker exec airbyte-abctl-control-plane kubectl get pods -n airbyte-abctl
```

2. Pod löschen:

```bash
docker exec airbyte-abctl-control-plane kubectl delete pod <POD_NAME> -n airbyte-abctl --force
```

Die Komponente startet danach selbst neu.

### Airbyte-Connector kann die Datenbanken nicht erreichen

Die Connector-Container sprechen die Datenbanken über `host.docker.internal` an,
nicht über `localhost`. Airbyte läuft im kind-Cluster und damit nicht im
Docker-Netz der Datenbanken. DNS-Auflösung prüfen (muss `192.168.65.x` liefern):

```bash
docker run --rm alpine nslookup host.docker.internal
```

DB-Port vom Host prüfen:
- **Windows:** `Test-NetConnection -ComputerName localhost -Port 5433`
- **Linux / macOS:** `nc -zv localhost 5433`

Sind die Ports zu, läuft der DB-Stack nicht: Windows `.\scripts\start.ps1`,
Linux/macOS `bash scripts/start.sh`.

### Passwortfehler bei Dest PostgreSQL (password authentication failed)

Ursache: Auf Port 5432 läuft schon ein nativer PostgreSQL-Dienst
(`postgres.exe`). Verbindungen über `host.docker.internal:5432` landen dort statt
bei `hso_dest_postgres`.

Prüfen, ob ein zweiter Prozess auf 5432 lauscht:

```powershell
netstat -ano | findstr :5432
```
```bash
ss -ltnp 'sport = :5432'
```

**Lösung:** Dest PostgreSQL läuft deshalb auf Port **5434**. In der Airbyte UI
immer 5434 verwenden.

### Testdaten wurden nicht geladen (source-postgres ist leer)

Die Loader füllen die Tabellen **nach** dem Stackstart und sind idempotent.
Einfach `install` erneut ausführen oder die Loader einzeln aufrufen (siehe
[Abschnitt 8](#8-manuelle-installation)).

> Die CSV-`COPY`-Befehle im SQL-Init sind entfernt, weil die Quell-CSVs für ein
> direktes `COPY` zu unsauber sind.

### Nach einem erneuten install-Lauf fehlen Namen und Accounts

`install` lädt die zehn Quelltabellen per `TRUNCATE` und `INSERT` aus den CSVs
neu. Die sind anonymisiert, haben also keine Namen. Damit sind auch die
Zufallsnamen und die daraus abgeleiteten `user_id` weg, und die View `hso_user`
ist leer. `pruefe_szenarien.py` meldet Szenario 4 dann als `NICHT erfuellt` und
nennt unter "Offen" die Teilaufgabe `1 Namen befuellen`.

Reparatur ist ein Lauf von `setup-szenarien`: die Schritte `namen`, `accounts`
und `view` erkennen den fehlenden Sollzustand und laufen erneut, alles andere
wird übersprungen. Dauert wenige Sekunden.

Die Accounts kommen dabei identisch wieder, solange beide Tabellen vollständig
zurückgesetzt wurden: die Namen sind reproduzierbar, und die Vergabe läuft in
fester Reihenfolge (`ORDER BY mtknr` beziehungsweise `ORDER BY id`) aus einem
leeren Bestand. Nach einem **Teil**-Reset kann derselbe Mensch einen anderen
Kollisionszähler bekommen, dann passen Quelle und MySQL nicht mehr zusammen und
der IdM-Sync muss nochmal laufen:

```bash
python scripts/setup_szenarien.py --erzwingen --nur sync-idm
```

### setup-szenarien bricht bei einem Schritt ab

Das Skript nennt den Schritt und den passenden Wiedereinstieg. Nach der Ursache
sehen, dann:

```bash
python scripts/setup_szenarien.py --ab <schrittname>
```

Bei einem hängenden Sync hilft der Blick in die Job-Historie der UI unter
http://localhost:8000. Ein Sync, der als `incomplete` endet, ohne zu sagen woran,
ist meistens das MySQL-Ziel ohne `raw_data_schema` (Befund 24 in
[ergebnisse.md](ergebnisse.md)); `setup_objects.py` setzt das Feld
bereits.

### Ein Sync sieht eine Änderung nicht

Bei Incremental-Syncs über einen Cursor: ändert sich nicht die Daten, sondern die
Ableitungslogik (etwa eine View-Definition), bemerkt der Sync nichts. Kein
Fehler, keine Warnung. Abhilfe ist ein `UPDATE ... SET updatedat = NOW()` in der
Quelle. Das ist Befund 3 in [ergebnisse.md](ergebnisse.md).

### Eine Zieltabelle hat doppelt so viele Zeilen wie erwartet

Zwei Connections, die denselben Stream in dieselbe Zieltabelle schreiben,
verdoppeln sie beim ersten Aufbau. Full Refresh Overwrite erhöht die
`_airbyte_generation_id` und löscht nur echt ältere Generationen, der Zähler
läuft aber pro Connection. Beim ersten Lauf stehen beide auf 1, also räumt keine
die Zeilen der anderen weg. Prüfen lässt sich das so:

```bash
docker exec hso_dest_postgres psql -U destuser -d destdb -c "select _airbyte_generation_id, _airbyte_extracted_at, count(*) from fm_gebaeude group by 1,2"
```

Zwei verschiedene Zeitstempel bei gleicher Generation sind der Beleg.
`setup_connections.py` vermeidet die Überlappung inzwischen, und ein Test
in `tests/test_setup_connections.py` hält das fest.

### Python-Pakete fehlen

```bash
pip install -r requirements.txt
```

Auf neueren Debian- und Ubuntu-Systemen verweigert pip die Installation ins
System (PEP 668). Dann eine virtuelle Umgebung nutzen oder
`--break-system-packages` ergänzen. Die Setup-Skripte probieren beides selbst.

---

## Verbindungsübersicht

Alle Ports, Hosts und Zugangsdaten stehen zentral in
[zugang.md](zugang.md#3-verbindungsparameter-zentrale-referenz). DB-Tools nutzen
`localhost`, die Airbyte-UI `host.docker.internal`.

| Dienst | Adresse | Datenbank / Nutzer |
|---|---|---|
| Source PostgreSQL | `localhost:5433` | `sourcedb` / `sourceuser` |
| Dest PostgreSQL | `localhost:5434` | `destdb` / `destuser` |
| Dest MySQL | `localhost:3306` | `destdb` / `destuser` |
| File-Server | `localhost:8888` | CSV-Flatfiles |
| PostgREST | `localhost:3000` | REST auf `destdb` |
| Airbyte UI | `localhost:8000` | Login siehe `abctl local credentials` |

## Weiterlesen

- [ergebnisse.md](ergebnisse.md): alle Befunde mit Beleg, die Sollwerte der Prüfung
- [etl-prozess.md](etl-prozess.md): der erste ETL-Lauf zum Mitklicken
- [airbyte-setup.md](airbyte-setup.md): Feld-Referenz aller Sources und Destinations
- [airbyte_api.md](airbyte_api.md): die Public API und ihre Stolpersteine
- [dbt.md](dbt.md): das Modell `fm_raeume` und seine Tests
- [testszenarien.md](testszenarien.md): die Szenarien im Detail
