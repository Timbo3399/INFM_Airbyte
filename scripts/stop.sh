#!/usr/bin/env bash
# stop.sh - Stoppt alle Container (Linux/macOS). Aufruf: bash scripts/stop.sh [-v]
#   -v  loescht zusaetzlich die Volumes (kompletter Reset)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ "${1:-}" = "-v" ]; then
  echo "==> Stoppe Stack und loesche alle Volumes (Reset)..."
  docker compose down -v
  echo "Alle Daten geloescht. Beim naechsten Start werden Testdaten neu geladen."
else
  echo "==> Stoppe Stack (Daten bleiben erhalten)..."
  docker compose down
  echo "Stack gestoppt. Volumes sind noch vorhanden."
fi
