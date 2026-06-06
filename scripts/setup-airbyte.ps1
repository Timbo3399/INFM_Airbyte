# setup-airbyte.ps1 - Airbyte Community Edition mit abctl installieren
# Aufruf: .\scripts\setup-airbyte.ps1
#
# Was dieses Skript tut:
#   1. abctl (Airbyte CLI) herunterladen und in C:\tools\airbyte\ ablegen
#   2. abctl zur PATH-Variable hinzufuegen (Session + dauerhaft)
#   3. Airbyte lokal installieren (abctl local install)
#   4. Login-Credentials setzen
#   5. Verbindungsinfos ausgeben
#
# Offizielle Doku: https://docs.airbyte.com/platform/using-airbyte/getting-started/oss-quickstart
#
# Systemanforderungen:
#   - Docker Desktop muss laufen
#   - Mindestens 2 CPUs und 8 GB RAM (empfohlen: 4 CPUs / 8 GB)

$ErrorActionPreference = "Stop"

$AIRBYTE_DIR  = "C:\tools\airbyte"
$ABCTL_EXE    = "$AIRBYTE_DIR\abctl.exe"
$RELEASES_URL = "https://api.github.com/repos/airbytehq/abctl/releases/latest"

# --- Hilfsfunktionen ---------------------------------------------------------

function Write-Step([string]$msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok([string]$msg)   { Write-Host "    [OK] $msg" -ForegroundColor Green }
function Write-Warn([string]$msg) { Write-Host "    [!]  $msg" -ForegroundColor Yellow }
function Write-Fail([string]$msg) { Write-Host "    [X]  $msg" -ForegroundColor Red }

# --- Banner ------------------------------------------------------------------

Write-Host ""
Write-Host "  Airbyte Setup (abctl) - Campus Next-Gen Data-Hub" -ForegroundColor White
Write-Host "  ===================================================" -ForegroundColor DarkGray
Write-Host ""

# --- 1. Docker pruefen -------------------------------------------------------

Write-Step "Pruefe Docker Desktop"

docker info 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Docker Desktop ist nicht gestartet."
    Write-Host "         Bitte Docker Desktop starten und erneut versuchen." -ForegroundColor Gray
    exit 1
}
Write-Ok "Docker Desktop laeuft."

# --- 2. Zielverzeichnis ------------------------------------------------------

Write-Step "Zielverzeichnis vorbereiten: $AIRBYTE_DIR"

if (-not (Test-Path $AIRBYTE_DIR)) {
    New-Item -ItemType Directory -Path $AIRBYTE_DIR | Out-Null
    Write-Ok "Verzeichnis erstellt."
} else {
    Write-Ok "Verzeichnis existiert bereits."
}

# --- 3. abctl herunterladen --------------------------------------------------

Write-Step "abctl (Airbyte CLI) herunterladen"

if (Test-Path $ABCTL_EXE) {
    $ver = & $ABCTL_EXE version 2>&1
    Write-Ok "abctl bereits vorhanden ($ver) - ueberspringe Download."
} else {
    Write-Host "    Lade aktuelle Version von GitHub..." -ForegroundColor DarkGray

    # Prozessorarchitektur ermitteln (funktioniert in Windows PowerShell 5.1 UND PowerShell 7+;
    # Get-WmiObject existiert in PowerShell 7 nicht mehr).
    $arch = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "arm64" } else { "amd64" }

    try {
        $release = Invoke-RestMethod -Uri $RELEASES_URL -UseBasicParsing
        # Asset-Namensschema: abctl-<tag>-windows-<arch>.zip  (z.B. abctl-v0.30.4-windows-amd64.zip)
        $asset = $release.assets |
            Where-Object { $_.name -like "abctl-*-windows-$arch.zip" } |
            Select-Object -First 1

        if (-not $asset) {
            Write-Fail "Kein Windows-$arch-Asset im Release $($release.tag_name) gefunden."
            Write-Host "  Manuell herunterladen: https://github.com/airbytehq/abctl/releases/latest" -ForegroundColor Yellow
            exit 1
        }

        $zipPath = "$AIRBYTE_DIR\abctl.zip"
        Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zipPath -UseBasicParsing

        # Das ZIP enthaelt abctl.exe in einem Unterordner (abctl-<tag>-windows-<arch>\abctl.exe).
        # Daher in ein Temp-Verzeichnis entpacken und die EXE nach $AIRBYTE_DIR heben.
        $tmpDir = Join-Path $AIRBYTE_DIR "_extract"
        if (Test-Path $tmpDir) { Remove-Item $tmpDir -Recurse -Force }
        Expand-Archive -Path $zipPath -DestinationPath $tmpDir -Force
        $foundExe = Get-ChildItem -Path $tmpDir -Recurse -Filter "abctl.exe" | Select-Object -First 1
        if (-not $foundExe) {
            Write-Fail "abctl.exe wurde im Archiv nicht gefunden."
            exit 1
        }
        Copy-Item $foundExe.FullName $ABCTL_EXE -Force
        Remove-Item $tmpDir -Recurse -Force
        Remove-Item $zipPath -Force

        Write-Ok "abctl heruntergeladen (Version: $($release.tag_name))."
    } catch {
        Write-Fail "Download fehlgeschlagen: $_"
        Write-Host ""
        Write-Host "  Manuell installieren:" -ForegroundColor Yellow
        Write-Host "  1. https://github.com/airbytehq/abctl/releases/latest" -ForegroundColor Gray
        Write-Host "  2. abctl-<version>-windows-amd64.zip herunterladen und entpacken" -ForegroundColor Gray
        Write-Host "  3. abctl.exe nach $AIRBYTE_DIR kopieren" -ForegroundColor Gray
        exit 1
    }
}

# --- 4. abctl zur PATH-Variable hinzufuegen ----------------------------------

Write-Step "abctl zum PATH hinzufuegen"

$currentPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
if ($currentPath -notlike "*$AIRBYTE_DIR*") {
    [System.Environment]::SetEnvironmentVariable("Path", "$currentPath;$AIRBYTE_DIR", "User")
    Write-Ok "PATH dauerhaft aktualisiert (wirkt ab dem naechsten Terminal-Start)."
} else {
    Write-Ok "Verzeichnis ist bereits im PATH."
}
# Fuer die aktuelle Session sofort verfuegbar machen
$env:Path = "$env:Path;$AIRBYTE_DIR"

# --- 5. Airbyte installieren -------------------------------------------------

Write-Step "Airbyte lokal installieren"
Write-Host ""
Write-Host "  HINWEIS: Der naechste Schritt ist interaktiv." -ForegroundColor Yellow
Write-Host "  Du wirst nach E-Mail-Adresse und Organisations-Name gefragt." -ForegroundColor Yellow
Write-Host "  Die Installation dauert bis zu 10 Minuten (Downloads im Hintergrund)." -ForegroundColor Yellow
Write-Host ""

$lowRes = Read-Host "  Wenig RAM (unter 6 GB frei)? Low-Resource-Mode aktivieren? (j/N)"
$installArgs = @("local", "install")
if ($lowRes -in @("j","J","y","Y")) {
    $installArgs += "--low-resource-mode"
    Write-Warn "Low-Resource-Mode aktiv (2 CPUs / 8 GB RAM Minimum)."
}

Write-Host ""
& $ABCTL_EXE @installArgs

if ($LASTEXITCODE -ne 0) {
    Write-Fail "abctl local install fehlgeschlagen (Exit-Code $LASTEXITCODE)."
    Write-Host "  Logs pruefen: abctl local logs" -ForegroundColor Gray
    exit 1
}
Write-Ok "Airbyte erfolgreich installiert."

# --- 6. Credentials setzen ---------------------------------------------------

Write-Step "Login-Credentials konfigurieren"
Write-Host ""

$currentCreds = & $ABCTL_EXE local credentials 2>&1
Write-Host "  Aktuelle Credentials:" -ForegroundColor DarkGray
Write-Host "  $currentCreds" -ForegroundColor DarkGray
Write-Host ""

$setPassword = Read-Host "  Eigenes Passwort setzen? (j/N)"
if ($setPassword -in @("j","J","y","Y")) {
    # Passwort verdeckt einlesen (kein Klartext in der Konsole)
    $securePass = Read-Host "  Neues Passwort" -AsSecureString
    $newPass    = [System.Net.NetworkCredential]::new("", $securePass).Password
    if (-not [string]::IsNullOrWhiteSpace($newPass)) {
        # abctl benoetigt eine gesetzte Organisations-E-Mail. Ist keine vorhanden
        # ("Email: [not set]"), schlaegt der interne Lookup mit "unable to
        # determine organization email" / "invalid character '<'" fehl (die API
        # liefert dann HTML statt JSON). Darum E-Mail explizit per --email setzen.
        $emailMatch = [regex]::Match("$currentCreds", '(?im)^\s*Email:\s*([^\s\[]+@\S+)')
        if ($emailMatch.Success) {
            $email = $emailMatch.Groups[1].Value
        } else {
            $email = Read-Host "  E-Mail fuer den Login (noch keine gesetzt) [admin@example.com]"
            if ([string]::IsNullOrWhiteSpace($email)) { $email = "admin@example.com" }
        }
        & $ABCTL_EXE local credentials --email $email --password $newPass
        if ($LASTEXITCODE -eq 0) {
            Write-Ok "Passwort gesetzt."
        } else {
            Write-Warn "Passwort konnte nicht gesetzt werden. Manuell: abctl local credentials --email <email> --password <passwort>"
        }
    } else {
        Write-Warn "Leeres Passwort - keine Aenderung vorgenommen."
    }
} else {
    Write-Warn "Standard-Credentials beibehalten. Zum Aendern: abctl local credentials --password <passwort>"
}

# Credentials noch einmal anzeigen
Write-Host ""
Write-Host "  Aktuelle Login-Daten:" -ForegroundColor Cyan
& $ABCTL_EXE local credentials 2>&1 | ForEach-Object { Write-Host "    $_" -ForegroundColor White }

# --- 7. Ergebnis -------------------------------------------------------------

Write-Host ""
Write-Host "  ===========================================================" -ForegroundColor DarkGray
Write-Host "  Airbyte laeuft!" -ForegroundColor Green
Write-Host ""
Write-Host "    UI:  http://localhost:8000" -ForegroundColor White
Write-Host ""
Write-Host "  DB-Verbindung in Airbyte (host.docker.internal verwenden!):" -ForegroundColor Cyan
Write-Host "    Source PG  ->  Host: host.docker.internal  Port: 5433" -ForegroundColor White
Write-Host "    Dest   PG  ->  Host: host.docker.internal  Port: 5434" -ForegroundColor White
Write-Host "    Dest MySQL ->  Host: host.docker.internal  Port: 3306" -ForegroundColor White
Write-Host ""
Write-Host "  Naechste Schritte: docs\airbyte-setup.md" -ForegroundColor Cyan
Write-Host "  ===========================================================" -ForegroundColor DarkGray
Write-Host ""
