#!/usr/bin/env bash
# setup-airbyte.sh - Airbyte Community Edition via abctl (Linux/macOS)
# Pendant zu scripts/setup-airbyte.ps1.  Aufruf:  bash scripts/setup-airbyte.sh
#
# Voraussetzungen: Docker laeuft, mind. 2 CPUs / 8 GB RAM.

set -euo pipefail

cyan() { printf '\n==> %s\n' "$1"; }
ok()   { printf '    [OK] %s\n' "$1"; }
warn() { printf '    [!]  %s\n' "$1"; }
fail() { printf '    [X]  %s\n' "$1"; }

echo
echo "  Airbyte Setup (abctl) - Linux/macOS"
echo "  ==================================="

cyan "Pruefe Docker"
docker info >/dev/null 2>&1 && ok "Docker laeuft." || { fail "Docker-Daemon laeuft nicht."; exit 1; }

cyan "abctl installieren"
if command -v abctl >/dev/null 2>&1; then
  ok "abctl bereits vorhanden ($(abctl version 2>/dev/null | head -n1))."
else
  warn "Installiere abctl ueber den offiziellen Installer (get.airbyte.com)..."
  # Offizielle, plattformuebergreifende Installation (erkennt OS/Arch automatisch):
  curl -LsfS https://get.airbyte.com | bash -
  # Falls abctl danach nicht im PATH ist, typische Pfade ergaenzen:
  command -v abctl >/dev/null 2>&1 || export PATH="$PATH:$HOME/.airbyte/abctl:$HOME/.local/bin"
  if command -v abctl >/dev/null 2>&1; then
    ok "abctl installiert ($(abctl version 2>/dev/null | head -n1))."
  else
    fail "abctl nicht im PATH. Neues Terminal oeffnen, dann erneut ausfuehren."
    echo  "  Alternativ manuell: https://github.com/airbytehq/abctl/releases/latest"
    echo  "  (Asset: abctl-<version>-linux-amd64.tar.gz bzw. -darwin-arm64.tar.gz)"
    exit 1
  fi
fi

cyan "Airbyte lokal installieren (interaktiv, 5-10 Min.)"
echo  "  Du wirst nach E-Mail-Adresse und Organisations-Name gefragt."
printf "  Wenig RAM (unter 6 GB frei)? Low-Resource-Mode? (j/N) "
read -r lowres || lowres=""
case "$lowres" in
  j|J|y|Y) warn "Low-Resource-Mode aktiv."; abctl local install --low-resource-mode ;;
  *)       abctl local install ;;
esac
ok "Airbyte installiert."

cyan "Login-Credentials"
abctl local credentials || true
echo
echo  "  Eigenes/gemeinsames Passwort setzen: abctl local credentials --password <pw>"

cat <<'EOF'

  ===========================================================
  Airbyte laeuft!   UI: http://localhost:8000

  DB-Verbindung in Airbyte (host.docker.internal verwenden!):
    Source PG  ->  Host: host.docker.internal  Port: 5433
    Dest   PG  ->  Host: host.docker.internal  Port: 5434
    Dest MySQL ->  Host: host.docker.internal  Port: 3306

  Naechste Schritte: docs/airbyte-setup.md
  ===========================================================
EOF
