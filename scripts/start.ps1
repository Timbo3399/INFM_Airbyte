# start.ps1 - Startet alle Custom-Datenbanken
# Aufruf: .\scripts\start.ps1

$ErrorActionPreference = "Stop"
$ROOT = Split-Path $PSScriptRoot -Parent

Write-Host "==> Starte HSO Datenbank-Stack..." -ForegroundColor Cyan

# .env pruefen
if (-not (Test-Path "$ROOT\.env")) {
    Write-Host "Keine .env gefunden - erstelle aus .env.example" -ForegroundColor Yellow
    Copy-Item "$ROOT\.env.example" "$ROOT\.env"
}

# Docker pruefen
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker nicht gefunden. Bitte Docker Desktop installieren."
}

Set-Location $ROOT

# Externes Volume sicherstellen: docker-compose deklariert oss_local_root als external:true.
# Fehlt es, bricht "docker compose up" mit einem Fehler ab.
if (-not (docker volume ls --format "{{.Name}}" | Where-Object { $_ -eq "oss_local_root" })) {
    docker volume create oss_local_root | Out-Null
}

# Stack starten (kein --build noetig: alle Services nutzen fertige Images)
docker compose up -d

Write-Host ""
Write-Host "==> Stack laeuft. Verbindungsinfos:" -ForegroundColor Green
Write-Host "   Source  PostgreSQL : localhost:5433  (sourcedb / sourceuser)" -ForegroundColor White
Write-Host "   Dest    PostgreSQL : localhost:5434  (destdb   / destuser  )" -ForegroundColor White
Write-Host "   Dest    MySQL      : localhost:3306  (destdb   / destuser  )" -ForegroundColor White
Write-Host "   File    Server     : localhost:8888  (CSV-Flatfiles)" -ForegroundColor White
Write-Host ""
Write-Host "==> Naechster Schritt: Airbyte starten (siehe docs\airbyte-setup.md)" -ForegroundColor Cyan
