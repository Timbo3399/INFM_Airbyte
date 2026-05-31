#!/usr/bin/env bash
# install.sh - Vollstaendiges Setup fuer Linux/macOS (Pendant zu scripts/install.ps1)
# Aufruf:  bash scripts/install.sh
#
# 1. Voraussetzungen pruefen (git, docker, docker compose)
# 2. .env aus .env.example erstellen
# 3. Volume oss_local_root sicherstellen
# 4. Images laden, Stack starten, auf healthy warten
# 5. Testdaten laden (Host-python3 mit psycopg2 ODER Docker-Fallback)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

cyan() { printf '\n==> %s\n' "$1"; }
ok()   { printf '    [OK] %s\n' "$1"; }
warn() { printf '    [!]  %s\n' "$1"; }
fail() { printf '    [X]  %s\n' "$1"; }

echo
echo "  Campus Next-Gen Data-Hub - Installation (Linux/macOS)"
echo "  ====================================================="

cyan "Voraussetzungen pruefen"
command -v git    >/dev/null 2>&1 && ok "git gefunden."    || { fail "git fehlt.";    exit 1; }
command -v docker >/dev/null 2>&1 && ok "docker gefunden." || { fail "docker fehlt."; exit 1; }
docker info             >/dev/null 2>&1 && ok "Docker laeuft."            || { fail "Docker-Daemon laeuft nicht (Docker Desktop / dockerd starten)."; exit 1; }
docker compose version  >/dev/null 2>&1 && ok "docker compose verfuegbar." || { fail "docker compose fehlt (Docker >= v2)."; exit 1; }

cyan ".env Konfigurationsdatei"
if [ -f .env ]; then
  ok ".env existiert bereits - wird nicht ueberschrieben."
else
  cp .env.example .env
  ok ".env aus .env.example erstellt."
  warn "Passwoerter bei Bedarf in .env anpassen (aktuell: Standardwerte)."
fi

cyan "Docker-Volume oss_local_root vorbereiten"
if docker volume ls --format '{{.Name}}' | grep -qx oss_local_root; then
  ok "oss_local_root existiert bereits."
else
  docker volume create oss_local_root >/dev/null
  ok "oss_local_root erstellt."
fi

cyan "Docker-Images herunterladen (beim ersten Mal ca. 2 Min.)"
docker compose pull
ok "Images bereit."

cyan "Datenbank-Stack starten"
docker compose up -d
ok "Container gestartet."

cyan "Warte bis alle Container healthy sind..."
services="hso_source_postgres hso_dest_postgres hso_dest_mysql hso_fileserver"
elapsed=0; max=120
while [ "$elapsed" -lt "$max" ]; do
  all=1
  for s in $services; do
    st="$(docker inspect --format '{{.State.Health.Status}}' "$s" 2>/dev/null || echo none)"
    [ "$st" = "healthy" ] || all=0
  done
  [ "$all" -eq 1 ] && break
  printf '    Warte... (%s/%s s)\n' "$elapsed" "$max"
  sleep 5; elapsed=$((elapsed + 5))
done
if [ "$elapsed" -ge "$max" ]; then
  warn "Timeout - nicht alle Container healthy. Status:"; docker compose ps
else
  ok "Alle Container sind healthy."
fi

cyan "Testdaten laden (fm_rna, hso_personal, fm_inst, fm_gebaeude, k_plz)"
loaders="scripts/load_json.py scripts/load_fm_inst.py scripts/load_fm_gebaeude.py scripts/load_k_plz.py"
if command -v python3 >/dev/null 2>&1 && python3 -c "import psycopg2" >/dev/null 2>&1; then
  # Host-Python mit psycopg2 vorhanden -> direkt nutzen
  for l in $loaders; do python3 "$l"; done
  ok "Testdaten erfolgreich geladen (Host-Python)."
else
  # Sonst: tolerante Loader in einem Wegwerf-Container (kein Host-Python noetig)
  warn "Kein Host-Python mit psycopg2 - lade Daten ueber python:3.12-slim Container."
  docker run --rm --network airbyte_net --env-file .env \
    -e SOURCE_PG_HOST=hso_source_postgres -e SOURCE_PG_PORT=5432 \
    -v "$ROOT:/app" -w /app python:3.12-slim \
    sh -c "pip install --quiet psycopg2-binary && python scripts/load_json.py && python scripts/load_fm_inst.py && python scripts/load_fm_gebaeude.py && python scripts/load_k_plz.py" \
    && ok "Testdaten erfolgreich geladen (via Docker)." \
    || warn "Laden fehlgeschlagen - manuell: docker ... python scripts/load_*.py"
fi

cat <<'EOF'

  ===================================================
  Stack laeuft. Verbindungsparameter:

    Source  PostgreSQL  ->  localhost:5433  (sourcedb / sourceuser)
    Dest    PostgreSQL  ->  localhost:5434  (destdb   / destuser  )
    Dest    MySQL       ->  localhost:3306  (destdb   / destuser  )
    File    Server      ->  localhost:8888  (CSV-Flatfiles)

  Naechster Schritt: Airbyte starten
    bash scripts/setup-airbyte.sh

  Oder direkt zum Installations-Guide:
    docs/installation-guide.md
  ===================================================
EOF
