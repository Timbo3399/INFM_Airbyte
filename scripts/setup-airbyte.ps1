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

# 'docker info' schreibt bei gestopptem Docker auf stderr -> unter $ErrorActionPreference='Stop'
# wuerde 2>&1 das Skript mit NativeCommandError abbrechen, BEVOR die freundliche Meldung kommt.
# Darum EAP kurz auf 'Continue'; der Erfolg wird ueber $LASTEXITCODE geprueft.
$prevEAP = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
docker info 2>&1 | Out-Null
$dockerOk = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = $prevEAP
if (-not $dockerOk) {
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
    # abctl kann Hinweise (z.B. Update-Notice) auf stderr schreiben -> EAP kurz entschaerfen.
    $prevEAP = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    $ver = & $ABCTL_EXE version 2>&1
    $ErrorActionPreference = $prevEAP
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
# abctl hat keinen --quiet-Schalter; sein Fortschritts-Spinner "spammt" die Konsole,
# wenn die Ausgabe kein echtes TTY ist. Darum die gesamte Ausgabe in eine Logdatei
# umleiten (*> = alle Streams) und nur eine knappe Statuszeile zeigen.
$installLog = Join-Path $env:TEMP ("abctl-install-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
Write-Host "  Installiere Airbyte - laeuft ~5-10 Min ohne Live-Ausgabe." -ForegroundColor Yellow
Write-Host "  Live-Fortschritt optional im zweiten Fenster: Get-Content `"$installLog`" -Wait" -ForegroundColor DarkGray

# abctl schreibt seinen Fortschritts-Spinner auf stderr (KEINE echten Fehler). Beim
# Umleiten (*>) macht Windows-PowerShell daraus NativeCommandError-Records, die unter
# $ErrorActionPreference='Stop' das Skript faelschlich abbrechen wuerden. Darum NUR fuer
# diesen einen Aufruf auf 'Continue' setzen, den echten Exit-Code abgreifen und EAP
# danach wiederherstellen - so bleiben Logfile und ruhige Konsole erhalten.
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& $ABCTL_EXE @installArgs *> $installLog
$installExit = $LASTEXITCODE
$ErrorActionPreference = $prevEAP

if ($installExit -ne 0) {
    Write-Fail "abctl local install fehlgeschlagen (Exit-Code $installExit)."
    Write-Host "  Letzte Logzeilen ($installLog):" -ForegroundColor Gray
    Get-Content $installLog -Tail 20 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
    exit 1
}
Write-Ok "Airbyte erfolgreich installiert."

# --- 5b. File-Connector: lokales /local-Volume bereitstellen -----------------
# Drei Dinge sind noetig, damit der File-Connector (Provider 'local') unter abctl
# funktioniert - und damit ueberhaupt IRGENDEIN Connector laeuft:
#   1. --volume-Mount (oben): bringt die CSVs als /local in den kind-Node.
#   2. PVC 'airbyte-local-pvc': Bei aktiviertem lokalem Volume haengt der workload-
#      launcher dieses PVC in JEDEN Connector-Job-Pod. Fehlt es, bleiben ALLE
#      Connector-Pods 'Pending' (persistentvolumeclaim "airbyte-local-pvc" not found)
#      -> auch Postgres/MySQL-Connectoren starten dann nicht! abctl legt das PVC nicht
#      automatisch an, daher hier ein PV (hostPath /local) + PVC.
#   3. JOB_KUBE_LOCAL_VOLUME_ENABLED=true + Neustart von launcher/worker.

if (Test-Path $DATA_DIR) {
    Write-Step "File-Connector: lokales /local-Volume bereitstellen"

    # PV (hostPath auf den /local-Mount) + PVC 'airbyte-local-pvc' anlegen
    $pvcYaml = @"
apiVersion: v1
kind: PersistentVolume
metadata:
  name: airbyte-csv-local-pv
spec:
  capacity:
    storage: 5Gi
  accessModes: [ReadWriteMany]
  hostPath:
    path: /local
  persistentVolumeReclaimPolicy: Retain
  storageClassName: airbyte-local-manual
  claimRef:
    name: airbyte-local-pvc
    namespace: $ABCTL_NS
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: airbyte-local-pvc
  namespace: $ABCTL_NS
spec:
  accessModes: [ReadWriteMany]
  resources:
    requests:
      storage: 5Gi
  storageClassName: airbyte-local-manual
  volumeName: airbyte-csv-local-pv
"@
    # kubectl schreibt Hinweise/Warnungen auf stderr (z.B. "Warning: ... env[146] hides
    # previous definition of CHECK_JOB_MAIN_CONTAINER_CPU_REQUEST" beim rollout restart -
    # harmlos, stammt aus Airbytes eigenem Deployment). Mit 2>&1 macht Windows-PowerShell
    # daraus unter $ErrorActionPreference='Stop' terminierende NativeCommandError-Records,
    # die das Skript faelschlich abbrechen. Darum den gesamten nativen kubectl-Block auf
    # 'Continue' setzen - die Erfolgskontrolle laeuft ohnehin ueber $LASTEXITCODE/$pvcOk/$flagOk.
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'

    $pvcYaml | docker exec -i $KIND_NODE kubectl --kubeconfig $KUBE_CFG apply -f - 2>&1 | Out-Null
    $pvcOk = ($LASTEXITCODE -eq 0)

    # lokales Volume fuer die Connector-Pods aktivieren
    # Patch ueber stdin statt '-p <json>': PowerShell verschluckt beim Aufruf der
    # nativen docker.exe die inneren " des JSON-Strings, sodass kubectl ungueltiges
    # JSON ({data:...} statt {"data":...}) erhaelt -> "invalid character 'd'".
    # Der Weg ueber die Pipe (wie beim 'apply -f -' oben) umgeht das Quoting komplett.
    $patch = '{"data":{"JOB_KUBE_LOCAL_VOLUME_ENABLED":"true"}}'
    $patch | docker exec -i $KIND_NODE kubectl --kubeconfig $KUBE_CFG patch configmap airbyte-abctl-airbyte-env -n $ABCTL_NS --type merge --patch-file /dev/stdin 2>&1 | Out-Null
    $flagOk = ($LASTEXITCODE -eq 0)

    if ($pvcOk -and $flagOk) {
        # launcher/worker neu starten, damit sie das Flag einlesen
        docker exec $KIND_NODE kubectl --kubeconfig $KUBE_CFG rollout restart deploy/airbyte-abctl-workload-launcher deploy/airbyte-abctl-worker -n $ABCTL_NS 2>&1 | Out-Null
        docker exec $KIND_NODE kubectl --kubeconfig $KUBE_CFG rollout status deploy/airbyte-abctl-workload-launcher -n $ABCTL_NS --timeout=120s 2>&1 | Out-Null
        $ErrorActionPreference = $prevEAP
        Write-Ok "Lokaler File-Connector-Mount aktiv (Provider 'local', URL /local/<datei>.csv)."
    } else {
        $ErrorActionPreference = $prevEAP
        Write-Warn "Lokales File-Connector-Volume nicht vollstaendig eingerichtet (PVC ok: $pvcOk, Flag ok: $flagOk)."
        Write-Host "         ACHTUNG: Mit gesetztem Flag, aber ohne PVC 'airbyte-local-pvc' bleiben" -ForegroundColor Gray
        Write-Host "         ALLE Connector-Pods 'Pending'. Im Zweifel Flag wieder auf false setzen." -ForegroundColor Gray
    }
}

# --- 6. Login-Credentials setzen ---------------------------------------------
# WICHTIG (abctl 0.30.x + Airbyte 2.1.0): E-Mail und Passwort muessen in ZWEI
# getrennten Aufrufen gesetzt werden - erst --email, DANN --password. Der kombinierte
# Aufruf 'credentials --email X --password Y' loest einen Org-Lookup aus, der mit
# "unable to determine organization email" / "invalid character '<'" fehlschlaegt.
# Security: Passwoerter werden verdeckt eingelesen und NIE im Klartext ausgegeben.

Write-Step "Login-Credentials konfigurieren"

# abctl schreibt Hinweise (Org-Lookup etc.) auf stderr; unter $ErrorActionPreference='Stop'
# wuerden diese via 2>&1 / *> das Skript abbrechen. Fuer den gesamten Credentials-Block daher
# 'Continue' setzen - Erfolg/Fehlschlag wird ohnehin ueber $LASTEXITCODE ausgewertet.
$prevEAP = $ErrorActionPreference; $ErrorActionPreference = 'Continue'

# Aktuelle Login-E-Mail ermitteln - nur die E-Mail auslesen, das Passwort NICHT anzeigen.
$currentCreds = (& $ABCTL_EXE local credentials 2>&1 | Out-String)
$emailMatch   = [regex]::Match($currentCreds, '(?im)^\s*Email:\s*([^\s\[]+@\S+)')
$loginEmail   = if ($emailMatch.Success) { $emailMatch.Groups[1].Value } else { $null }
Write-Host ("  Aktuelle Login-E-Mail: {0}" -f ($(if ($loginEmail) { $loginEmail } else { "(noch nicht gesetzt)" }))) -ForegroundColor DarkGray
Write-Host ""

# 1) E-Mail (Login-Name) setzen - immer, wenn noch keine vorhanden ist; sonst optional.
$email = $null
if (-not $loginEmail) {
    $email = Read-Host "  Login-E-Mail setzen [admin@example.com]"
    if ([string]::IsNullOrWhiteSpace($email)) { $email = "admin@example.com" }
} elseif ((Read-Host "  Login-E-Mail aendern? (j/N)") -in @("j","J","y","Y")) {
    $email = Read-Host "  Neue Login-E-Mail"
}
if (-not [string]::IsNullOrWhiteSpace($email)) {
    & $ABCTL_EXE local credentials --email $email *> $null
    if ($LASTEXITCODE -eq 0) { Write-Ok "Login-E-Mail gesetzt: $email"; $loginEmail = $email }
    else { Write-Warn "E-Mail konnte nicht gesetzt werden. Manuell: abctl local credentials --email <email>" }
}

# 2) Passwort setzen - verdeckt einlesen, SEPARATER Aufruf NACH der E-Mail.
if ((Read-Host "  Eigenes Passwort setzen? (j/N)") -in @("j","J","y","Y")) {
    $securePass = Read-Host "  Neues Passwort" -AsSecureString
    $newPass    = [System.Net.NetworkCredential]::new("", $securePass).Password
    if (-not [string]::IsNullOrWhiteSpace($newPass)) {
        & $ABCTL_EXE local credentials --password $newPass *> $null
        if ($LASTEXITCODE -eq 0) { Write-Ok "Passwort gesetzt." }
        else { Write-Warn "Passwort konnte nicht gesetzt werden. Manuell: abctl local credentials --password <passwort>" }
        $newPass = $null; $securePass = $null   # sensible Variablen leeren
    } else {
        Write-Warn "Leeres Passwort - keine Aenderung vorgenommen."
    }
} else {
    Write-Warn "Generiertes Passwort beibehalten."
}
$ErrorActionPreference = $prevEAP

# Login-Hinweis OHNE Passwort-Klartext.
Write-Host ""
Write-Host ("  Login-E-Mail: {0}" -f ($(if ($loginEmail) { $loginEmail } else { "(siehe 'abctl local credentials')" }))) -ForegroundColor Cyan
Write-Host "  Passwort: aus Security-Gruenden nicht angezeigt. Bei Bedarf selbst abrufen: abctl local credentials" -ForegroundColor DarkGray

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
