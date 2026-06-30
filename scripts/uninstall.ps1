# uninstall.ps1 - Entfernt Airbyte (abctl) und den Docker-Stack (Windows)
# Gegenstueck zu install.ps1 + setup-airbyte.ps1.
#
# Aufruf:
#   .\scripts\uninstall.ps1                 # vollstaendig (mit Rueckfrage)
#   .\scripts\uninstall.ps1 -KeepData       # Container/Airbyte entfernen, DB-Daten behalten
#   .\scripts\uninstall.ps1 -RemoveAbctl    # zusaetzlich abctl-Binary + PATH-Eintrag loeschen
#   .\scripts\uninstall.ps1 -Force          # ohne Rueckfrage
#
# Was passiert (Standard, ohne Flags):
#   1. Airbyte via 'abctl local uninstall --persisted' entfernen (inkl. kind-Cluster + Daten)
#   2. Docker-Stack via 'docker compose down -v' entfernen (DB-Volumes inklusive)
#   3. Externes Volume oss_local_root loeschen
#   (abctl-Binary + PATH bleiben erhalten, ausser mit -RemoveAbctl)

param(
    [switch]$KeepData,
    [switch]$RemoveAbctl,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
# Nicht-Null-Exitcodes nativer Befehle (docker, abctl) selbst auswerten.
$PSNativeCommandUseErrorActionPreference = $false
$ROOT        = Split-Path $PSScriptRoot -Parent
$AIRBYTE_DIR = "C:\tools\airbyte"

function Write-Step([string]$msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok([string]$msg)   { Write-Host "    [OK] $msg" -ForegroundColor Green }
function Write-Warn([string]$msg) { Write-Host "    [!]  $msg" -ForegroundColor Yellow }
function Write-Fail([string]$msg) { Write-Host "    [X]  $msg" -ForegroundColor Red }

# abctl finden: zuerst im PATH, sonst Standardpfad aus setup-airbyte.ps1
$abctl = (Get-Command abctl -ErrorAction SilentlyContinue).Source
if (-not $abctl -and (Test-Path "$AIRBYTE_DIR\abctl.exe")) { $abctl = "$AIRBYTE_DIR\abctl.exe" }

# --- Banner ------------------------------------------------------------------

Write-Host ""
Write-Host "  Campus Next-Gen Data-Hub - Deinstallation" -ForegroundColor White
Write-Host "  =========================================" -ForegroundColor DarkGray
Write-Host ""
if ($KeepData) {
    Write-Host "  Modus: DB-Daten und Airbyte-Daten BLEIBEN erhalten." -ForegroundColor Yellow
} else {
    Write-Host "  Modus: VOLLSTAENDIG - Container, Volumes und Airbyte-Daten werden GELOESCHT." -ForegroundColor Yellow
}
if ($RemoveAbctl) { Write-Host "  Zusaetzlich: abctl-Binary ($AIRBYTE_DIR) + PATH-Eintrag werden entfernt." -ForegroundColor Yellow }
Write-Host ""

if (-not $Force) {
    $confirm = Read-Host "  Fortfahren? (j/N)"
    if ($confirm -notin @("j","J","y","Y")) {
        Write-Warn "Abgebrochen - keine Aenderungen vorgenommen."
        exit 0
    }
}

# Docker verfuegbar?
docker info 2>$null | Out-Null
$dockerUp = ($LASTEXITCODE -eq 0)
if (-not $dockerUp) {
    Write-Warn "Docker Desktop laeuft nicht - Container/Volumes koennen nicht entfernt werden."
}

# --- 1. Airbyte (abctl) deinstallieren ---------------------------------------

Write-Step "Airbyte (abctl) deinstallieren"
if ($abctl -and $dockerUp) {
    $uninstallArgs = @("local", "uninstall")
    if (-not $KeepData) { $uninstallArgs += "--persisted" }
    & $abctl @uninstallArgs
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "Airbyte deinstalliert."
    } else {
        Write-Warn "abctl local uninstall meldete einen Fehler (evtl. war nichts installiert)."
    }
} elseif (-not $abctl) {
    Write-Warn "abctl nicht gefunden - Airbyte-Deinstallation uebersprungen."
} else {
    Write-Warn "Docker aus - Airbyte-Deinstallation uebersprungen."
}

# --- 2. Docker-Stack entfernen -----------------------------------------------

Write-Step "Datenbank-Stack (docker compose) entfernen"
if ($dockerUp) {
    Set-Location $ROOT
    if ($KeepData) {
        docker compose down
        Write-Ok "Container entfernt - Volumes (DB-Daten) bleiben erhalten."
    } else {
        docker compose down -v
        Write-Ok "Container und compose-Volumes entfernt."
    }
} else {
    Write-Warn "Uebersprungen (Docker laeuft nicht)."
}

# --- 3. Externes Volume oss_local_root ---------------------------------------
# Wird von install.ps1 als 'external' angelegt und von 'compose down -v' NICHT erfasst.

if (-not $KeepData -and $dockerUp) {
    Write-Step "Volume oss_local_root entfernen"
    $volExists = docker volume ls --format "{{.Name}}" 2>$null | Where-Object { $_ -eq "oss_local_root" }
    if ($volExists) {
        docker volume rm oss_local_root 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Ok "oss_local_root geloescht."
        } else {
            Write-Warn "oss_local_root konnte nicht geloescht werden (evtl. noch in Benutzung)."
        }
    } else {
        Write-Ok "oss_local_root existiert nicht (mehr)."
    }
}

# --- 4. abctl-Binary + PATH (optional) ---------------------------------------

if ($RemoveAbctl) {
    Write-Step "abctl-Binary und PATH-Eintrag entfernen"
    if (Test-Path $AIRBYTE_DIR) {
        Remove-Item -Recurse -Force $AIRBYTE_DIR
        Write-Ok "$AIRBYTE_DIR geloescht."
    } else {
        Write-Ok "$AIRBYTE_DIR existiert nicht."
    }
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -like "*$AIRBYTE_DIR*") {
        $newPath = ($userPath -split ';' | Where-Object { $_ -and ($_ -ne $AIRBYTE_DIR) }) -join ';'
        [System.Environment]::SetEnvironmentVariable("Path", $newPath, "User")
        Write-Ok "PATH-Eintrag entfernt (wirkt ab dem naechsten Terminal-Start)."
    } else {
        Write-Ok "Kein PATH-Eintrag fuer $AIRBYTE_DIR gefunden."
    }
}

# --- Ergebnis ----------------------------------------------------------------

Write-Host ""
Write-Host "  ===========================================================" -ForegroundColor DarkGray
Write-Host "  Deinstallation abgeschlossen." -ForegroundColor Green
if (-not $KeepData) {
    Write-Host "  Neu aufsetzen: .\scripts\install.ps1  +  .\scripts\setup-airbyte.ps1" -ForegroundColor White
}
Write-Host "  ===========================================================" -ForegroundColor DarkGray
Write-Host ""
