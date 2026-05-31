#!/usr/bin/env bash
# start.sh - Startet alle Custom-Datenbanken (Linux/macOS). Aufruf: bash scripts/start.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Starte HSO Datenbank-Stack..."

[ -f .env ] || { echo "Keine .env gefunden - erstelle aus .env.example"; cp .env.example .env; }

command -v docker >/dev/null 2>&1 || { echo "Docker nicht gefunden. Bitte Docker installieren."; exit 1; }

# Externes Volume sicherstellen (docker-compose deklariert oss_local_root als external:true)
docker volume ls --format '{{.Name}}' | grep -qx oss_local_root || docker volume create oss_local_root >/dev/null

docker compose up -d

echo
echo "==> Stack laeuft. Verbindungsinfos:"
echo "   Source  PostgreSQL : localhost:5433  (sourcedb / sourceuser)"
echo "   Dest    PostgreSQL : localhost:5434  (destdb   / destuser  )"
echo "   Dest    MySQL      : localhost:3306  (destdb   / destuser  )"
echo "   File    Server     : localhost:8888  (CSV-Flatfiles)"
echo
echo "==> Naechster Schritt: bash scripts/setup-airbyte.sh (siehe docs/airbyte-setup.md)"
