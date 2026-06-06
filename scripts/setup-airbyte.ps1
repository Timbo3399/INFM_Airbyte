# setup-airbyte.ps1 - Airbyte Community Edition mit abctl installieren
# Aufruf: .\scripts\setup-airbyte.ps1
#
# Was dieses Skript tut:
#   1. abctl (Airbyte CLI) herunterladen und in C:\tools\airbyte\ ablegen
#   2. abctl zur PATH-Variable hinzufuegen (Session + dauerhaft)
#   3. Airbyte lokal installieren (abctl local install) inkl. /local-Mount der CSVs
#      und Aktivierung des File-Connector-Volumes (JOB_KUBE_LOCAL_VOLUME_ENABLED)
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

# Repo-Wurzel relativ zum Skript (scripts/ -> ..). Enthaelt sql/source/data mit den CSVs,
# die als /local in den abctl/kind-Cluster gemountet werden (File-Connector, Schritt 5).
$REPO_ROOT    = Split-Path -Parent $PSScriptRoot
$DATA_DIR     = Join-Path $REPO_ROOT "sql\source\data"
$KIND_NODE    = "airbyte-abctl-control-plane"   # kind-Node-Container von abctl
$ABCTL_NS     = "airbyte-abctl"                  # Kubernetes-Namespace von Airbyte
$KUBE_CFG     = "/etc/kubernetes/admin.conf"     # kubeconfig im kind-Node

# --- Hilfsfunktionen ---------------------------------------------------------

function Write-Step([string]$msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok([string]$msg)   { Write-Host "    [OK] $msg" -ForegroundColor Green }
function Write-Warn([string]$msg) { Write-Host "    [!]  $msg" -ForegroundColor Yellow }
function Write-Fail([string]$msg) { Write-Host "    [X]  $msg" -ForegroundColor Red }

# Wandelt einen Windows-Pfad (C:\a\b) in die von abctl/kind erwartete MSYS-Form (/c/a/b) um.
# Noetig, weil abctl den --volume-String stur an ':' trennt und der Laufwerks-Doppelpunkt
# sonst zu "is not a valid volume spec" fuehrt. Docker Desktop loest /c/... wieder auf C: auf.
function ConvertTo-AbctlVolumePath([string]$winPath) {
    $full  = (Resolve-Path $winPath).Path
    $drive = $full.Substring(0,1).ToLower()
    $rest  = ($full.Substring(2)) -replace '\\','/'
    return "/$drive$rest"
}

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
Write-Host "  HINWEIS: Die Installation laeuft selbststaendig (nicht interaktiv)." -ForegroundColor Yellow
Write-Host "  Sie dauert bis zu 10 Minuten (Image-Downloads im Hintergrund)." -ForegroundColor Yellow
Write-Host "  Login-Daten werden danach in Schritt 6 gesetzt." -ForegroundColor Yellow
Write-Host ""

$lowRes = Read-Host "  Wenig RAM (unter 6 GB frei)? Low-Resource-Mode aktivieren? (j/N)"
$installArgs = @("local", "install")
if ($lowRes -in @("j","J","y","Y")) {
    $installArgs += "--low-resource-mode"
    Write-Warn "Low-Resource-Mode aktiv (2 CPUs / 8 GB RAM Minimum)."
}

# CSV-Verzeichnis als /local in den kind-Node mounten, damit der Airbyte File-Connector
# (Storage Provider "local", URL /local/<datei>.csv) die Flatfiles lesen kann.
# WICHTIG: Wird nur bei der ERSTEN Cluster-Erstellung angewandt. Existiert der Cluster
# bereits, ignoriert abctl --volume - dann vorher 'abctl local uninstall' ausfuehren.
if (Test-Path $DATA_DIR) {
    $dataVol = ConvertTo-AbctlVolumePath $DATA_DIR
    $installArgs += @("--volume", "${dataVol}:/local")
    Write-Ok "CSV-Verzeichnis wird als /local gemountet: $DATA_DIR"
} else {
    Write-Warn "Datenverzeichnis nicht gefunden ($DATA_DIR) - File-Connector-Mount uebersprungen."
}

Write-Host ""
& $ABCTL_EXE @installArgs

if ($LASTEXITCODE -ne 0) {
    Write-Fail "abctl local install fehlgeschlagen (Exit-Code $LASTEXITCODE)."
    Write-Host "  Logs pruefen: abctl local logs" -ForegroundColor Gray
    exit 1
}
Write-Ok "Airbyte erfolgreich installiert."

# --- 5b. File-Connector: lokalen /local-Mount aktivieren ---------------------
# Der --volume-Mount bringt die CSVs in den kind-Node. Damit die dynamisch
# gestarteten Connector-Pods sie auch sehen, muss JOB_KUBE_LOCAL_VOLUME_ENABLED=true
# sein. abctl setzt das nicht automatisch -> hier per kubectl im kind-Node patchen
# und launcher/worker neu starten (sonst greift die Aenderung nicht).

if (Test-Path $DATA_DIR) {
    Write-Step "File-Connector: lokalen /local-Mount aktivieren"
    $patch = '{"data":{"JOB_KUBE_LOCAL_VOLUME_ENABLED":"true"}}'
    docker exec $KIND_NODE kubectl --kubeconfig $KUBE_CFG patch configmap airbyte-abctl-airbyte-env -n $ABCTL_NS --type merge -p $patch 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        docker exec $KIND_NODE kubectl --kubeconfig $KUBE_CFG rollout restart deploy/airbyte-abctl-workload-launcher deploy/airbyte-abctl-worker -n $ABCTL_NS 2>&1 | Out-Null
        docker exec $KIND_NODE kubectl --kubeconfig $KUBE_CFG rollout status deploy/airbyte-abctl-workload-launcher -n $ABCTL_NS --timeout=120s 2>&1 | Out-Null
        Write-Ok "Lokaler File-Connector-Mount aktiv (Provider 'local', URL /local/<datei>.csv)."
    } else {
        Write-Warn "JOB_KUBE_LOCAL_VOLUME_ENABLED konnte nicht gesetzt werden."
        Write-Host "         Manuell im kind-Node nachholen:" -ForegroundColor Gray
        Write-Host "         docker exec $KIND_NODE kubectl --kubeconfig $KUBE_CFG patch configmap airbyte-abctl-airbyte-env -n $ABCTL_NS --type merge -p '$patch'" -ForegroundColor Gray
    }
}

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
