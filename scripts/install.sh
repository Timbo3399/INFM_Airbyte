#!/usr/bin/env bash
# install.sh - Vollstaendiges Setup fuer Linux/macOS (Pendant zu scripts/install.ps1)
# Aufruf:  bash scripts/install.sh
#
# Was dieses Skript tut:
#   1. Voraussetzungen pruefen (git, docker, docker compose, Python)
#   2. .env aus .env.example erstellen (wenn nicht vorhanden)
#   3. oss_local_root Volume sicherstellen
#   4. Docker-Images laden
#   5. Datenbank-Stack starten
#   6. Warten bis alle Container healthy sind
#   7. Testdaten in source-postgres laden (tolerante Python-Loader: load_json,
#      load_fm_inst, load_fm_gebaeude, load_k_plz, load_lookups, load_hso_students,
#      load_fm_stamm - Host-Python ODER Docker-Fallback)
#   8. Verbindungsinfos ausgeben
#
# Die Entscheidung zwischen Host-Python und Docker-Fallback trifft dieses Skript
# nach derselben Regel wie install.ps1: Host-Python nur, wenn psycopg2 UND
# openpyxl danach importierbar sind. Die beiden Helfer find_python und
# confirm_py_package haben in install.ps1 ein wortgleiches Gegenstueck.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

cyan() { printf '\n==> %s\n' "$1"; }
ok()   { printf '    [OK] %s\n' "$1"; }
warn() { printf '    [!]  %s\n' "$1"; }
fail() { printf '    [X]  %s\n' "$1"; }

# Sucht ein echtes Python 3. Gleiche Logik wie in install.ps1: die
# Versionsausgabe pruefen, nicht nur ob der Befehl existiert (auf Windows ist
# "python" oft nur der Microsoft-Store-Platzhalter).
find_python() {
  for kandidat in python3 python py; do
    command -v "$kandidat" >/dev/null 2>&1 || continue
    if "$kandidat" --version 2>&1 | grep -q "Python 3"; then
      echo "$kandidat"
      return 0
    fi
  done
  return 1
}

# Stellt ein Python-Paket sicher: erst importieren, sonst nachinstallieren, auf
# PEP-668-Systemen (neuere Debian/Ubuntu) mit --break-system-packages, danach
# erneut importieren. Gleiche Logik wie in install.ps1, damit beide Skripte
# dieselbe Entscheidung treffen. Der Import ist der Pruefpunkt: ein Paket kann
# installiert und trotzdem nicht importierbar sein.
confirm_py_package() {   # $1=python  $2=Modul  $3=Paket
  local py="$1" modul="$2" paket="$3"
  "$py" -c "import $modul" >/dev/null 2>&1 && return 0
  printf '    Installiere %s...\n' "$paket"
  "$py" -m pip install --quiet "$paket" >/dev/null 2>&1 \
    || "$py" -m pip install --quiet --break-system-packages "$paket" >/dev/null 2>&1 \
    || true
  "$py" -c "import $modul" >/dev/null 2>&1
}

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

cyan "Testdaten laden (fm_rna, hso_personal, fm_inst, fm_gebaeude, k_plz, anredetitel, k_hochschule, k_res, hso_students, fm_stamm)"
loaders="scripts/load_json.py scripts/load_fm_inst.py scripts/load_fm_gebaeude.py scripts/load_k_plz.py scripts/load_lookups.py scripts/load_hso_students.py scripts/load_fm_stamm.py"

# Entscheidung ueber den Ladeweg, identisch zu install.ps1: Host-Python nur dann,
# wenn psycopg2 UND openpyxl danach wirklich importierbar sind. psycopg2 braucht
# jeder Loader, openpyxl nur load_fm_stamm.py (rooms.xltx). Klappt eines von
# beiden nicht, uebernimmt der Docker-Fallback komplett, statt sieben Loader
# einzeln scheitern zu lassen.
host_weg_ok=0
if PY="$(find_python)"; then
  psycopg_ok=1; openpyxl_ok=1
  confirm_py_package "$PY" psycopg2 psycopg2-binary || { psycopg_ok=0; warn "psycopg2 nicht verfuegbar."; }
  confirm_py_package "$PY" openpyxl openpyxl        || { openpyxl_ok=0; warn "openpyxl nicht verfuegbar."; }
  [ "$psycopg_ok" -eq 1 ] && [ "$openpyxl_ok" -eq 1 ] && host_weg_ok=1
else
  warn "Kein echtes Python 3 gefunden."
fi

if [ "$host_weg_ok" -eq 1 ]; then
  # Loader einzeln und TOLERANT ausfuehren: ein fehlschlagender Loader (kaputte CSV,
  # DB-Haenger) darf unter 'set -e' nicht das ganze Skript killen.
  failed=""
  for l in $loaders; do
    if ! "$PY" "$l"; then failed="$failed $l"; fi
  done
  if [ -z "$failed" ]; then
    ok "Testdaten erfolgreich geladen (Host-Python)."
  else
    warn "Einige Loader sind fehlgeschlagen - bitte manuell pruefen/nachladen:$failed"
  fi
else
  # Sonst: tolerante Loader in einem Wegwerf-Container (kein Host-Python noetig)
  warn "Kein brauchbares Host-Python - lade Daten ueber python:3.12-slim Container."
  docker run --rm --network airbyte_net --env-file .env \
    -e SOURCE_PG_HOST=hso_source_postgres -e SOURCE_PG_PORT=5432 \
    -v "$ROOT:/app" -w /app python:3.12-slim \
    sh -c "pip install --quiet psycopg2-binary openpyxl && python scripts/load_json.py && python scripts/load_fm_inst.py && python scripts/load_fm_gebaeude.py && python scripts/load_k_plz.py && python scripts/load_lookups.py && python scripts/load_hso_students.py && python scripts/load_fm_stamm.py" \
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

  Noch zwei Schritte bis zum Demo-Zustand:

    2) bash scripts/setup-airbyte.sh      Airbyte installieren (interaktiv)
    3) bash scripts/setup-szenarien.sh    Mapping, Bilder, Syncs, dbt

  Danach steht der Zustand, den docs/ergebnisse.md beschreibt. Nachpruefen:
    python3 scripts/pruefe_szenarien.py

  Der komplette Weg steht in docs/installation-guide.md
  ===================================================
EOF
