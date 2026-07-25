# setup-szenarien.ps1 - stellt den vollstaendigen Demo-Zustand her
# Aufruf: .\scripts\setup-szenarien.ps1
#
# Der dritte und letzte Schritt der Installation:
#   1. install.ps1         Datenbank-Stack und die zehn Quelltabellen
#   2. setup-airbyte.ps1   Airbyte im kind-Cluster
#   3. setup-szenarien.ps1 Mapping, Bilder, Airbyte-Objekte, Syncs, dbt   <-- hier
#
# Was dieses Skript tut:
#   1. Voraussetzungen pruefen (Docker, Container, Airbyte, Python-Pakete)
#   2. scripts/setup_szenarien.py ausfuehren, das die eigentliche Arbeit macht
#   3. scripts/pruefe_szenarien.py ausfuehren und den Sollzustand zeigen
#
# Die Reihenfolge und die Skip-Erkennung stecken in setup_szenarien.py, nicht
# hier. Dadurch verhalten sich dieses Skript und setup-szenarien.sh gleich, und
# nicht nur ungefaehr.
#
# Argumente werden durchgereicht, zum Beispiel:
#   .\scripts\setup-szenarien.ps1 --trockenlauf
#   .\scripts\setup-szenarien.ps1 --nur bilder,dbt
#   .\scripts\setup-szenarien.ps1 --ab dbt
#
# Ein voller Lauf dauert rund zwoelf Minuten, ein Lauf auf einem bereits
# befuellten Stack Sekunden.

$ErrorActionPreference = "Stop"
# Exit-Codes nativer Befehle selbst auswerten, statt dass PowerShell 7.4+ bei
# jedem Nicht-Null-Exit sofort abbricht.
$PSNativeCommandUseErrorActionPreference = $false
$ROOT = Split-Path $PSScriptRoot -Parent

function Write-Step([string]$msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok([string]$msg)   { Write-Host "    [OK] $msg" -ForegroundColor Green }
function Write-Warn([string]$msg) { Write-Host "    [!]  $msg" -ForegroundColor Yellow }
function Write-Fail([string]$msg) { Write-Host "    [X]  $msg" -ForegroundColor Red }

# Sucht ein echtes Python 3. "python" ist auf Windows haeufig nur der
# Microsoft-Store-Platzhalter, den Get-Command findet, der aber keine Version
# liefert. Deshalb die Versionsausgabe pruefen (gleiche Logik wie install.ps1).
function Find-Python {
    foreach ($kandidat in @("py", "python", "python3")) {
        if (-not (Get-Command $kandidat -ErrorAction SilentlyContinue)) { continue }
        try { $ver = (& $kandidat --version 2>$null) | Out-String } catch { continue }
        if ($ver -match "Python\s+3") { return $kandidat }
    }
    return $null
}

# Stellt ein Python-Paket sicher. Gleiche Logik wie in setup-szenarien.sh:
# erst importieren, sonst nachinstallieren, auf PEP-668-Systemen mit
# --break-system-packages, danach erneut importieren.
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

Write-Host ""
Write-Host "  Campus Next-Gen Data-Hub - Szenarien aufsetzen" -ForegroundColor White
Write-Host "  ==============================================" -ForegroundColor DarkGray

# --- 1. Voraussetzungen ------------------------------------------------------

Write-Step "Voraussetzungen pruefen"

docker info 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Docker Desktop ist nicht gestartet."
    exit 1
}
Write-Ok "Docker Desktop laeuft."

$fehlend = @()
foreach ($svc in @("hso_source_postgres", "hso_dest_postgres", "hso_dest_mysql", "hso_fileserver")) {
    $status = "$(docker inspect --format '{{.State.Status}}' $svc 2>$null)".Trim()
    if ($status -ne "running") { $fehlend += $svc }
}
if ($fehlend.Count -gt 0) {
    Write-Fail ("Diese Container laufen nicht: " + ($fehlend -join ", "))
    Write-Host "         Zuerst den Stack starten: .\scripts\start.ps1" -ForegroundColor Gray
    Write-Host "         Oder komplett neu aufsetzen: .\scripts\install.ps1" -ForegroundColor Gray
    exit 1
}
Write-Ok "Datenbank-Stack laeuft."

# Airbyte muss erreichbar sein, sonst scheitern die Objekt- und Sync-Schritte
# mitten im Lauf statt hier.
$airbyteDa = $false
try {
    $antwort = Invoke-WebRequest -Uri "http://localhost:8000" -TimeoutSec 15 -UseBasicParsing
    $airbyteDa = ($antwort.StatusCode -lt 500)
} catch {
    $airbyteDa = $false
}
if (-not $airbyteDa) {
    Write-Fail "Airbyte ist auf http://localhost:8000 nicht erreichbar."
    Write-Host "         Zuerst: .\scripts\setup-airbyte.ps1" -ForegroundColor Gray
    Write-Host "         Laeuft es schon, hilft: abctl local status" -ForegroundColor Gray
    exit 1
}
Write-Ok "Airbyte ist erreichbar."

$py = Find-Python
if (-not $py) {
    Write-Fail "Kein echtes Python 3 gefunden."
    Write-Host "         Anders als bei install.ps1 gibt es hier keinen Docker-Fallback:" -ForegroundColor Gray
    Write-Host "         dbt und die Airbyte-Skripte brauchen Host-Python." -ForegroundColor Gray
    Write-Host "         Installieren: winget install Python.Python.3.12" -ForegroundColor Gray
    exit 1
}
Write-Ok "Python gefunden (via '$py')."

Write-Step "Python-Pakete sicherstellen"
$pakete = @(
    @{ Modul = "psycopg2";      Paket = "psycopg2-binary" },
    @{ Modul = "requests";      Paket = "requests" },
    @{ Modul = "dbt.cli.main";  Paket = "dbt-core dbt-postgres" }
)
$paketeOk = $true
foreach ($p in $pakete) {
    if (Confirm-PyPackage $py $p.Modul $p.Paket) {
        Write-Ok "$($p.Modul) verfuegbar."
    } else {
        Write-Fail "$($p.Modul) fehlt und liess sich nicht installieren."
        $paketeOk = $false
    }
}
if (-not $paketeOk) {
    Write-Host "         Von Hand nachziehen: $py -m pip install -r requirements.txt" -ForegroundColor Gray
    exit 1
}

# --- 2. Szenarien aufsetzen --------------------------------------------------

Write-Step "Szenarien aufsetzen"

Set-Location $ROOT
& $py "$ROOT\scripts\setup_szenarien.py" @args
$setupCode = $LASTEXITCODE
if ($setupCode -ne 0) {
    Write-Fail "setup_szenarien.py endete mit Code $setupCode."
    exit $setupCode
}

# --- 3. Sollzustand pruefen --------------------------------------------------

Write-Step "Sollzustand pruefen"

& $py "$ROOT\scripts\pruefe_szenarien.py"
$pruefCode = $LASTEXITCODE

Write-Host ""
Write-Host "  ===================================================" -ForegroundColor DarkGray
if ($pruefCode -eq 0) {
    Write-Host "  Demo-Zustand steht, alle Pruefungen stimmen." -ForegroundColor Green
} else {
    Write-Host "  Es fehlt noch etwas, siehe Tabelle oben." -ForegroundColor Yellow
    Write-Host "  Die Sollwerte sind in docs\ergebnisse.md belegt." -ForegroundColor Gray
}
Write-Host ""
Write-Host "  Airbyte UI:  http://localhost:8000" -ForegroundColor White
Write-Host "  PostgREST:   http://localhost:3000/k_plz?limit=1" -ForegroundColor White
Write-Host ""
Write-Host "  Einzelne Szenarien nachpruefen:" -ForegroundColor Cyan
Write-Host "    $py scripts\pruefe_szenarien.py Sz3 Sz5" -ForegroundColor White
Write-Host "  ===================================================" -ForegroundColor DarkGray
Write-Host ""

exit $pruefCode
