#!/usr/bin/env bash
# setup-szenarien.sh - stellt den vollstaendigen Demo-Zustand her (Linux/macOS)
# Pendant zu scripts/setup-szenarien.ps1.  Aufruf:  bash scripts/setup-szenarien.sh
#
# Der dritte und letzte Schritt der Installation:
#   1. install.sh         Datenbank-Stack und die zehn Quelltabellen
#   2. setup-airbyte.sh   Airbyte im kind-Cluster
#   3. setup-szenarien.sh Mapping, Bilder, Airbyte-Objekte, Syncs, dbt   <-- hier
#
# Was dieses Skript tut:
#   1. Voraussetzungen pruefen (Docker, Container, Airbyte, Python-Pakete)
#   2. scripts/setup_szenarien.py ausfuehren, das die eigentliche Arbeit macht
#   3. scripts/pruefe_szenarien.py ausfuehren und den Sollzustand zeigen
#
# Die Reihenfolge und die Skip-Erkennung stecken in setup_szenarien.py, nicht
# hier. Dadurch verhalten sich dieses Skript und setup-szenarien.ps1 gleich, und
# nicht nur ungefaehr.
#
# Argumente werden durchgereicht, zum Beispiel:
#   bash scripts/setup-szenarien.sh --trockenlauf
#   bash scripts/setup-szenarien.sh --nur bilder,dbt
#   bash scripts/setup-szenarien.sh --ab dbt
#
# Ein voller Lauf dauert rund zwoelf Minuten, ein Lauf auf einem bereits
# befuellten Stack Sekunden.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

cyan() { printf '\n==> %s\n' "$1"; }
ok()   { printf '    [OK] %s\n' "$1"; }
warn() { printf '    [!]  %s\n' "$1"; }
fail() { printf '    [X]  %s\n' "$1"; }

# Sucht ein echtes Python 3. Wie in setup-szenarien.ps1 wird die Versionsausgabe
# geprueft und nicht nur, ob der Befehl existiert.
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

# Stellt ein Python-Paket sicher. Gleiche Logik wie in setup-szenarien.ps1:
# erst importieren, sonst nachinstallieren, auf PEP-668-Systemen (neuere
# Debian/Ubuntu) mit --break-system-packages, danach erneut importieren.
confirm_py_package() {   # $1=python  $2=Modul  $3=Paket(e)
  local py="$1" modul="$2" paket="$3"
  "$py" -c "import $modul" >/dev/null 2>&1 && return 0
  printf '    Installiere %s...\n' "$paket"
  # shellcheck disable=SC2086
  "$py" -m pip install --quiet $paket >/dev/null 2>&1 \
    || "$py" -m pip install --quiet --break-system-packages $paket >/dev/null 2>&1 \
    || true
  "$py" -c "import $modul" >/dev/null 2>&1
}

echo
echo "  Campus Next-Gen Data-Hub - Szenarien aufsetzen"
echo "  =============================================="

# --- 1. Voraussetzungen ------------------------------------------------------

cyan "Voraussetzungen pruefen"

docker info >/dev/null 2>&1 && ok "Docker laeuft." || { fail "Docker-Daemon laeuft nicht."; exit 1; }

fehlend=""
for svc in hso_source_postgres hso_dest_postgres hso_dest_mysql hso_fileserver; do
  st="$(docker inspect --format '{{.State.Status}}' "$svc" 2>/dev/null || echo none)"
  [ "$st" = "running" ] || fehlend="$fehlend $svc"
done
if [ -n "$fehlend" ]; then
  fail "Diese Container laufen nicht:$fehlend"
  printf '         Zuerst den Stack starten: bash scripts/start.sh\n'
  printf '         Oder komplett neu aufsetzen: bash scripts/install.sh\n'
  exit 1
fi
ok "Datenbank-Stack laeuft."

# Airbyte muss erreichbar sein, sonst scheitern die Objekt- und Sync-Schritte
# mitten im Lauf statt hier.
if curl -sfS -o /dev/null --max-time 15 http://localhost:8000 2>/dev/null \
   || curl -s -o /dev/null --max-time 15 -w '%{http_code}' http://localhost:8000 2>/dev/null | grep -qE '^[1-4]'; then
  ok "Airbyte ist erreichbar."
else
  fail "Airbyte ist auf http://localhost:8000 nicht erreichbar."
  printf '         Zuerst: bash scripts/setup-airbyte.sh\n'
  printf '         Laeuft es schon, hilft: abctl local status\n'
  exit 1
fi

PY="$(find_python)" || {
  fail "Kein echtes Python 3 gefunden."
  printf '         Anders als bei install.sh gibt es hier keinen Docker-Fallback:\n'
  printf '         dbt und die Airbyte-Skripte brauchen Host-Python.\n'
  exit 1
}
ok "Python gefunden (via '$PY')."

cyan "Python-Pakete sicherstellen"
pakete_ok=1
while IFS='|' read -r modul paket; do
  [ -n "$modul" ] || continue
  if confirm_py_package "$PY" "$modul" "$paket"; then
    ok "$modul verfuegbar."
  else
    fail "$modul fehlt und liess sich nicht installieren."
    pakete_ok=0
  fi
done <<'PAKETE'
psycopg2|psycopg2-binary
requests|requests
dbt.cli.main|dbt-core dbt-postgres
PAKETE
if [ "$pakete_ok" -ne 1 ]; then
  printf '         Von Hand nachziehen: %s -m pip install -r requirements.txt\n' "$PY"
  exit 1
fi

# --- 2. Szenarien aufsetzen --------------------------------------------------

cyan "Szenarien aufsetzen"

"$PY" "$ROOT/scripts/setup_szenarien.py" "$@"
setup_code=$?
if [ "$setup_code" -ne 0 ]; then
  fail "setup_szenarien.py endete mit Code $setup_code."
  exit "$setup_code"
fi

# --- 3. Sollzustand pruefen --------------------------------------------------

cyan "Sollzustand pruefen"

"$PY" "$ROOT/scripts/pruefe_szenarien.py"
pruef_code=$?

echo
echo "  ==================================================="
if [ "$pruef_code" -eq 0 ]; then
  echo "  Demo-Zustand steht, jedes gepruefte Szenario ist erfuellt."
else
  echo "  Mindestens ein Szenario ist nicht erfuellt, siehe Tabelle oben."
  echo "  Unter 'Offen' steht je Teilaufgabe das Kommando, das sie herstellt."
fi
cat <<EOF

  Airbyte UI:  http://localhost:8000
  PostgREST:   http://localhost:3000/k_plz?limit=1

  Einzelne Szenarien nachpruefen:
    $PY scripts/pruefe_szenarien.py Sz3 Sz5
  ===================================================

EOF

exit "$pruef_code"
