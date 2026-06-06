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

# Repo-Wurzel + CSV-Verzeichnis (wird als /local fuer den File-Connector gemountet)
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="$REPO_ROOT/sql/source/data"
KIND_NODE="airbyte-abctl-control-plane"   # kind-Node-Container von abctl
ABCTL_NS="airbyte-abctl"                   # Kubernetes-Namespace von Airbyte
KUBE_CFG="/etc/kubernetes/admin.conf"      # kubeconfig im kind-Node

cyan "Airbyte lokal installieren (nicht interaktiv, 5-10 Min.)"
install_args=(local install)
printf "  Wenig RAM (unter 6 GB frei)? Low-Resource-Mode? (j/N) "
read -r lowres || lowres=""
case "$lowres" in
  j|J|y|Y) warn "Low-Resource-Mode aktiv."; install_args+=(--low-resource-mode) ;;
esac
# CSV-Verzeichnis als /local in den kind-Node mounten (File-Connector, Provider "local").
# WICHTIG: Wird nur bei der ERSTEN Cluster-Erstellung angewandt; existiert der Cluster
# schon, ignoriert abctl --volume - dann vorher 'abctl local uninstall' ausfuehren.
if [ -d "$DATA_DIR" ]; then
  install_args+=(--volume "$DATA_DIR:/local")
  ok "CSV-Verzeichnis wird als /local gemountet: $DATA_DIR"
else
  warn "Datenverzeichnis nicht gefunden ($DATA_DIR) - File-Connector-Mount uebersprungen."
fi
abctl "${install_args[@]}"
ok "Airbyte installiert."

# File-Connector-Volume aktivieren: damit die Connector-Pods /local sehen, muss
# JOB_KUBE_LOCAL_VOLUME_ENABLED=true sein. abctl setzt das nicht automatisch.
if [ -d "$DATA_DIR" ]; then
  cyan "File-Connector: lokalen /local-Mount aktivieren"
  if docker exec "$KIND_NODE" kubectl --kubeconfig "$KUBE_CFG" patch configmap airbyte-abctl-airbyte-env -n "$ABCTL_NS" --type merge -p '{"data":{"JOB_KUBE_LOCAL_VOLUME_ENABLED":"true"}}' >/dev/null 2>&1; then
    docker exec "$KIND_NODE" kubectl --kubeconfig "$KUBE_CFG" rollout restart deploy/airbyte-abctl-workload-launcher deploy/airbyte-abctl-worker -n "$ABCTL_NS" >/dev/null 2>&1 || true
    docker exec "$KIND_NODE" kubectl --kubeconfig "$KUBE_CFG" rollout status  deploy/airbyte-abctl-workload-launcher -n "$ABCTL_NS" --timeout=120s >/dev/null 2>&1 || true
    ok "Lokaler File-Connector-Mount aktiv (Provider 'local', URL /local/<datei>.csv)."
  else
    warn "JOB_KUBE_LOCAL_VOLUME_ENABLED konnte nicht gesetzt werden (File-Connector 'local' ggf. nicht verfuegbar)."
  fi
fi

cyan "Login-Credentials"
abctl local credentials || true
echo
echo  "  Eigenes/gemeinsames Passwort setzen: abctl local credentials --email <email> --password <pw>"

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
