# install.ps1 - Vollstaendiges Setup fuer alle Projektmitglieder
# Aufruf: .\scripts\install.ps1
#
# Was dieses Skript tut:
#   1. Voraussetzungen pruefen (Docker, Git, Python)
#   2. .env aus .env.example erstellen (wenn nicht vorhanden)
#   3. oss_local_root Volume sicherstellen
#   4. Docker-Images laden
#   5. Datenbank-Stack starten
#   6. Warten bis alle Container healthy sind
#   7. Testdaten in source-postgres laden (tolerante Python-Loader: load_json,
#      load_fm_inst, load_fm_gebaeude, load_k_plz, load_lookups, load_hso_students,
#      load_fm_stamm - Host-Python ODER Docker-Fallback)
#   8. Verbindungsinfos ausgeben
#
# Die Entscheidung zwischen Host-Python und Docker-Fallback trifft dieses Skript
# nach derselben Regel wie install.sh: Host-Python nur, wenn psycopg2 UND
# openpyxl danach importierbar sind. Die beiden Helfer Find-Python und
# Confirm-PyPackage haben in install.sh ein wortgleiches Gegenstueck.
#
# Danach fehlen noch zwei Schritte bis zum Demo-Zustand: setup-airbyte.ps1 und
# setup-szenarien.ps1 (siehe docs/installation-guide.md).

$ErrorActionPreference = "Stop"
# Exit-Codes nativer Befehle (docker, python, pip) selbst auswerten, statt dass
# PowerShell 7.4+ bei jedem Nicht-Null-Exit sofort abbricht.
$PSNativeCommandUseErrorActionPreference = $false
$ROOT = Split-Path $PSScriptRoot -Parent

# --- Hilfsfunktionen ---------------------------------------------------------

function Write-Step([string]$msg) {
    Write-Host "`n==> $msg" -ForegroundColor Cyan
}

function Write-Ok([string]$msg) {
    Write-Host "    [OK] $msg" -ForegroundColor Green
}

function Write-Warn([string]$msg) {
    Write-Host "    [!]  $msg" -ForegroundColor Yellow
}

function Write-Fail([string]$msg) {
    Write-Host "    [X]  $msg" -ForegroundColor Red
}

function Assert-Command([string]$cmd, [string]$hint) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Write-Fail "$cmd nicht gefunden."
        Write-Host "         $hint" -ForegroundColor Gray
        exit 1
    }
    Write-Ok "$cmd gefunden."
}

# Sucht ein echtes Python 3. Gleiche Logik wie in install.sh: die Versionsausgabe
# pruefen, nicht nur ob der Befehl existiert. "python" ist auf Windows haeufig
# nur der Microsoft-Store-Platzhalter, den Get-Command zwar findet, der aber
# keine echte Version liefert.
function Find-Python {
    foreach ($kandidat in @("py", "python", "python3")) {
        if (-not (Get-Command $kandidat -ErrorAction SilentlyContinue)) { continue }
        try { $ver = (& $kandidat --version 2>$null) | Out-String } catch { continue }
        if ($ver -match "Python\s+3") { return $kandidat }
    }
    return $null
}

# Stellt ein Python-Paket sicher: erst importieren, sonst nachinstallieren, auf
# PEP-668-Systemen mit --break-system-packages, danach erneut importieren.
# Gleiche Logik wie in install.sh, damit beide Skripte dieselbe Entscheidung
# treffen. Der Import ist der Pruefpunkt, nicht 'pip show': ein Paket kann
# installiert und trotzdem nicht importierbar sein.
function Confirm-PyPackage([string]$py, [string]$modul, [string]$paket) {
    & $py -c "import $modul" 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { return $true }
    Write-Host "    Installiere $paket..." -ForegroundColor DarkGray
    & $py -m pip install --quiet $paket 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        & $py -m pip install --quiet --break-system-packages $paket 2>$null | Out-Null
    }
    & $py -c "import $modul" 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

# --- Banner ------------------------------------------------------------------

Write-Host ""
Write-Host "  Campus Next-Gen Data-Hub - Installations-Skript" -ForegroundColor White
Write-Host "  =================================================" -ForegroundColor DarkGray
Write-Host ""

# --- 1. Voraussetzungen pruefen ----------------------------------------------

Write-Step "Voraussetzungen pruefen"

Assert-Command "git"    "Installieren: https://git-scm.com/download/win"
Assert-Command "docker" "Installieren: https://www.docker.com/products/docker-desktop/"

# Docker laeuft?
docker info 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Docker Desktop ist nicht gestartet."
    Write-Host "         Bitte Docker Desktop starten und erneut versuchen." -ForegroundColor Gray
    exit 1
}
Write-Ok "Docker Desktop laeuft."

# Docker Compose verfuegbar?
$composeVersion = docker compose version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Fail "docker compose nicht verfuegbar."
    Write-Host "         Docker Desktop auf Version >=4.x aktualisieren." -ForegroundColor Gray
    exit 1
}
Write-Ok "docker compose verfuegbar ($($composeVersion -replace 'Docker Compose version ',''))."

# Python ist optional: ohne laedt der Docker-Fallback die Testdaten.
$pythonCmd = Find-Python
if ($pythonCmd) {
    Write-Ok "Python gefunden (via '$pythonCmd')."
} else {
    Write-Warn "Kein echtes Python gefunden (evtl. nur Microsoft-Store-Platzhalter)."
    Write-Warn "JSON-Daten werden stattdessen ueber einen Docker-Container geladen (kein Python noetig)."
    Write-Warn "Optional installieren: winget install Python.Python.3.12  (oder https://www.python.org/downloads/)"
}

# --- 2. .env erstellen -------------------------------------------------------

Write-Step ".env Konfigurationsdatei"

Set-Location $ROOT

if (Test-Path ".env") {
    Write-Ok ".env existiert bereits - wird nicht ueberschrieben."
} else {
    Copy-Item ".env.example" ".env"
    Write-Ok ".env aus .env.example erstellt."
    Write-Warn "Passwoerter bei Bedarf in .env anpassen (aktuell: Standardwerte)."
}

# --- 3. oss_local_root Volume sicherstellen ----------------------------------

Write-Step "Docker-Volume oss_local_root vorbereiten"

$volExists = docker volume ls --format "{{.Name}}" 2>$null | Where-Object { $_ -eq "oss_local_root" }
if ($volExists) {
    Write-Ok "oss_local_root existiert bereits."
} else {
    docker volume create oss_local_root | Out-Null
    Write-Ok "oss_local_root erstellt (wird von file-server und spaeter Airbyte genutzt)."
}

# --- 4. Docker-Images laden --------------------------------------------------

Write-Step "Docker-Images herunterladen (dauert beim ersten Mal ca. 2 Minuten)"

docker compose pull
if ($LASTEXITCODE -ne 0) {
    Write-Fail "docker compose pull fehlgeschlagen."
    exit 1
}
Write-Ok "Images bereit."

# --- 5. Stack starten --------------------------------------------------------

Write-Step "Datenbank-Stack starten"

docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Fail "docker compose up fehlgeschlagen."
    Write-Host "         Tipp: Sind die Ports 5433, 5434, 3306, 8888 oder 3000 schon belegt?" -ForegroundColor Gray
    exit 1
}
Write-Ok "Container gestartet."

# --- 6. Auf healthy warten ---------------------------------------------------

Write-Step "Warte bis alle Container healthy sind..."

$services   = @("hso_source_postgres", "hso_dest_postgres", "hso_dest_mysql", "hso_fileserver")
$maxWaitSec = 120
$interval   = 5
$elapsed    = 0

while ($elapsed -lt $maxWaitSec) {
    $allHealthy = $true
    foreach ($svc in $services) {
        # Stringify-Subexpression "$(...)": existiert der Container (noch) nicht, liefert
        # docker inspect KEINE Zeile -> Ergebnis "" statt $null. Ohne diese Klammerung
        # wuerfe .Trim() auf einem $null-Wert eine terminierende Exception und das Skript
        # crashte mitten in der Warteschleife.
        $status = "$(docker inspect --format '{{.State.Health.Status}}' $svc 2>$null)".Trim()
        if ($status -ne "healthy") {
            $allHealthy = $false
        }
    }
    if ($allHealthy) { break }

    Write-Host "    Warte... ($elapsed/$maxWaitSec s)" -ForegroundColor DarkGray
    Start-Sleep -Seconds $interval
    $elapsed += $interval
}

if ($elapsed -ge $maxWaitSec) {
    Write-Warn "Timeout - nicht alle Container sind healthy. Status:"
    docker compose ps
    Write-Warn "Logs pruefen: docker logs hso_source_postgres --tail 30"
} else {
    foreach ($svc in $services) {
        Write-Ok "$svc ist healthy."
    }
}

# --- 7. Testdaten in source-postgres laden -----------------------------------

Write-Step "Testdaten laden (fm_rna, hso_personal, fm_inst, fm_gebaeude, k_plz, anredetitel, k_hochschule, k_res, hso_students, fm_stamm)"

# Entscheidung ueber den Ladeweg, identisch zu install.sh: Host-Python nur dann,
# wenn psycopg2 UND openpyxl danach wirklich importierbar sind. psycopg2 braucht
# jeder Loader, openpyxl nur load_fm_stamm.py (rooms.xltx). Klappt eines von
# beiden nicht, uebernimmt der Docker-Fallback komplett, statt sieben Loader
# einzeln scheitern zu lassen.
$hostWegOk = $false
if ($pythonCmd) {
    $psycopgOk = Confirm-PyPackage $pythonCmd "psycopg2" "psycopg2-binary"
    $openpyxlOk = Confirm-PyPackage $pythonCmd "openpyxl" "openpyxl"
    if (-not $psycopgOk)  { Write-Warn "psycopg2 nicht verfuegbar." }
    if (-not $openpyxlOk) { Write-Warn "openpyxl nicht verfuegbar." }
    $hostWegOk = $psycopgOk -and $openpyxlOk
}

if ($hostWegOk) {
    $loadOk = $true
    foreach ($loader in @("load_json.py", "load_fm_inst.py", "load_fm_gebaeude.py", "load_k_plz.py", "load_lookups.py", "load_hso_students.py", "load_fm_stamm.py")) {
        & $pythonCmd "$ROOT\scripts\$loader"
        if ($LASTEXITCODE -ne 0) { $loadOk = $false }
    }
    if ($loadOk) {
        Write-Ok "Testdaten erfolgreich geladen (Host-Python)."
    } else {
        Write-Warn "Laden (teilweise) fehlgeschlagen - Loader manuell ausfuehren: scripts\load_*.py"
    }
} else {
    # Kein brauchbares Host-Python: Loader in einem Wegwerf-Container ausfuehren.
    # Verbindet sich ueber das Docker-Netz airbyte_net direkt mit
    # hso_source_postgres:5432.
    Write-Host "    Lade Daten ueber python:3.12-slim Container (kein Host-Python noetig)..." -ForegroundColor DarkGray
    docker run --rm --network airbyte_net `
        --env-file "$ROOT\.env" `
        -e SOURCE_PG_HOST=hso_source_postgres -e SOURCE_PG_PORT=5432 `
        -v "${ROOT}:/app" -w /app python:3.12-slim `
        sh -c "pip install --quiet psycopg2-binary openpyxl && python scripts/load_json.py && python scripts/load_fm_inst.py && python scripts/load_fm_gebaeude.py && python scripts/load_k_plz.py && python scripts/load_lookups.py && python scripts/load_hso_students.py && python scripts/load_fm_stamm.py"
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "Testdaten erfolgreich geladen (via Docker)."
    } else {
        Write-Warn "Laden via Docker fehlgeschlagen. Alternativ mit Host-Python: scripts\load_*.py einzeln ausfuehren."
    }
}

# --- 8. Ergebnis und naechste Schritte ---------------------------------------

Write-Host ""
Write-Host "  ===================================================" -ForegroundColor DarkGray
Write-Host "  Stack laeuft. Verbindungsparameter:" -ForegroundColor Green
Write-Host ""
Write-Host "    Source  PostgreSQL  ->  localhost:5433  (sourcedb / sourceuser)" -ForegroundColor White
Write-Host "    Dest    PostgreSQL  ->  localhost:5434  (destdb   / destuser  )" -ForegroundColor White
Write-Host "    Dest    MySQL       ->  localhost:3306  (destdb   / destuser  )" -ForegroundColor White
Write-Host "    File    Server      ->  localhost:8888  (CSV-Flatfiles)" -ForegroundColor White
Write-Host ""
Write-Host "  Airbyte File Connector:" -ForegroundColor Cyan
Write-Host "    HTTP:  http://host.docker.internal:8888/<datei>.csv" -ForegroundColor White
Write-Host "    Local: /local/<datei>.csv  (nach oss_local_root-Copy oben)" -ForegroundColor White
Write-Host ""
Write-Host "  Noch zwei Schritte bis zum Demo-Zustand:" -ForegroundColor Cyan
Write-Host ""
Write-Host "    2) .\scripts\setup-airbyte.ps1      Airbyte installieren (interaktiv)" -ForegroundColor White
Write-Host "    3) .\scripts\setup-szenarien.ps1    Mapping, Bilder, Syncs, dbt" -ForegroundColor White
Write-Host ""
Write-Host "  Danach steht der Zustand, den docs\ergebnisse.md beschreibt. Nachpruefen:" -ForegroundColor Gray
Write-Host "    python scripts\pruefe_szenarien.py" -ForegroundColor White
Write-Host ""
Write-Host "  Der komplette Weg steht in docs\installation-guide.md" -ForegroundColor Cyan
Write-Host "  ===================================================" -ForegroundColor DarkGray
Write-Host ""
