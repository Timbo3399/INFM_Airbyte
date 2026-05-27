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
#   7. JSON-Daten in source-postgres laden (fm_rna, hso_personal)
#   8. Verbindungsinfos ausgeben

$ErrorActionPreference = "Stop"
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
docker info 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Docker Desktop ist nicht gestartet."
    Write-Host "         Bitte Docker Desktop starten und erneut versuchen." -ForegroundColor Gray
    exit 1
}
Write-Ok "Docker Desktop laeuft."

# Docker Compose verfuegbar?
$composeVersion = docker compose version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Fail "docker compose nicht verfuegbar."
    Write-Host "         Docker Desktop auf Version >=4.x aktualisieren." -ForegroundColor Gray
    exit 1
}
Write-Ok "docker compose verfuegbar ($($composeVersion -replace 'Docker Compose version ',''))."

# Python (benoetigt fuer JSON-Daten laden + Szenarien 3 und 4)
$pythonAvailable = $false
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pyVer = python --version 2>&1
    Write-Ok "Python gefunden ($pyVer)."
    $pythonAvailable = $true
} else {
    Write-Warn "Python nicht gefunden - JSON-Daten koennen nicht geladen werden."
    Write-Warn "Installieren: https://www.python.org/downloads/ (>= 3.11, 'Add to PATH' aktivieren)"
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
    Write-Host "         Tipp: Sind die Ports 5432, 5433 oder 3306 schon belegt?" -ForegroundColor Gray
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
        $status = (docker inspect --format "{{.State.Health.Status}}" $svc 2>$null).Trim()
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

# --- 7. JSON-Daten in source-postgres laden ----------------------------------

Write-Step "JSON-Daten laden (fm_rna, hso_personal)"

if ($pythonAvailable) {
    # psycopg2-binary sicherstellen
    $pipOut = python -m pip show psycopg2-binary 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "    Installiere psycopg2-binary..." -ForegroundColor DarkGray
        python -m pip install psycopg2-binary --quiet
    }

    python "$ROOT\scripts\load_json.py"
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "JSON-Daten erfolgreich geladen."
    } else {
        Write-Warn "JSON-Laden fehlgeschlagen - manuell ausfuehren: python scripts\load_json.py"
    }
} else {
    Write-Warn "Python nicht verfuegbar - JSON-Daten nicht geladen."
    Write-Warn "Nach Python-Installation ausfuehren: python scripts\load_json.py"
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
Write-Host "  Naechster Schritt: Airbyte starten" -ForegroundColor Cyan
Write-Host "    .\scripts\setup-airbyte.ps1" -ForegroundColor White
Write-Host ""
Write-Host "  Oder direkt zum Installations-Guide:" -ForegroundColor Cyan
Write-Host "    docs\installation-guide.md" -ForegroundColor White
Write-Host "  ===================================================" -ForegroundColor DarkGray
Write-Host ""
