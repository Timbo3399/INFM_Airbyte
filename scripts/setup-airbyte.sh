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
install_args+=(--host localhost)
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
# abctl hat keinen --quiet-Schalter; sein Fortschritts-Spinner "spammt" die Konsole,
# wenn die Ausgabe kein echtes TTY ist. Darum Ausgabe in eine Logdatei umleiten.
INSTALL_LOG="$(mktemp -t abctl-install.XXXXXX.log 2>/dev/null || echo /tmp/abctl-install.log)"
warn "Installiere Airbyte - laeuft ~5-10 Min ohne Live-Ausgabe."
echo  "  Live-Fortschritt optional: tail -f \"$INSTALL_LOG\""
if abctl "${install_args[@]}" >"$INSTALL_LOG" 2>&1; then
  ok "Airbyte installiert."
else
  fail "abctl local install fehlgeschlagen. Letzte Logzeilen ($INSTALL_LOG):"
  tail -n 20 "$INSTALL_LOG" | sed 's/^/    /'
  exit 1
fi

# File-Connector-Volume bereitstellen. Drei Dinge sind noetig - und ohne das PVC
# bleiben sonst ALLE Connector-Pods (auch Postgres/MySQL) 'Pending':
#   1. --volume-Mount (oben): CSVs als /local in den kind-Node.
#   2. PVC 'airbyte-local-pvc': wird bei aktiviertem lokalem Volume in JEDEN Job-Pod
#      gehaengt; fehlt es -> "persistentvolumeclaim airbyte-local-pvc not found".
#   3. JOB_KUBE_LOCAL_VOLUME_ENABLED=true + Neustart launcher/worker.
if [ -d "$DATA_DIR" ]; then
  cyan "File-Connector: lokales /local-Volume bereitstellen"
  pvc_ok=0; flag_ok=0
  if cat <<EOF | docker exec -i "$KIND_NODE" kubectl --kubeconfig "$KUBE_CFG" apply -f - >/dev/null 2>&1
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
EOF
  then pvc_ok=1; fi

  if docker exec "$KIND_NODE" kubectl --kubeconfig "$KUBE_CFG" patch configmap airbyte-abctl-airbyte-env -n "$ABCTL_NS" --type merge -p '{"data":{"JOB_KUBE_LOCAL_VOLUME_ENABLED":"true"}}' >/dev/null 2>&1; then flag_ok=1; fi

  if [ "$pvc_ok" -eq 1 ] && [ "$flag_ok" -eq 1 ]; then
    docker exec "$KIND_NODE" kubectl --kubeconfig "$KUBE_CFG" rollout restart deploy/airbyte-abctl-workload-launcher deploy/airbyte-abctl-worker -n "$ABCTL_NS" >/dev/null 2>&1 || true
    docker exec "$KIND_NODE" kubectl --kubeconfig "$KUBE_CFG" rollout status  deploy/airbyte-abctl-workload-launcher -n "$ABCTL_NS" --timeout=120s >/dev/null 2>&1 || true
    ok "Lokaler File-Connector-Mount aktiv (Provider 'local', URL /local/<datei>.csv)."
  else
    warn "Lokales File-Connector-Volume nicht vollstaendig eingerichtet (PVC ok: $pvc_ok, Flag ok: $flag_ok)."
    warn "ACHTUNG: Flag gesetzt ohne PVC 'airbyte-local-pvc' -> ALLE Connector-Pods bleiben 'Pending'."
  fi
fi

cyan "Login-Credentials konfigurieren"
# WICHTIG (abctl 0.30.x + Airbyte 2.1.0): erst --email, DANN --password (getrennte
# Aufrufe). Kombiniert schlaegt der Org-Lookup fehl ("unable to determine
# organization email" / "invalid character '<'"). Security: Passwort verdeckt
# einlesen und NIE im Klartext ausgeben.

# Aktuelle Login-E-Mail ermitteln (nur E-Mail, Passwort NICHT anzeigen).
current_email="$(abctl local credentials 2>/dev/null | sed -nE 's/.*Email:[[:space:]]*([^[:space:]]+@[^[:space:]]+).*/\1/p' | head -n1)" || true
echo "  Aktuelle Login-E-Mail: ${current_email:-(noch nicht gesetzt)}"

# 1) E-Mail (Login-Name) setzen
email=""
if [ -z "$current_email" ]; then
  printf "  Login-E-Mail setzen [admin@example.com]: "; read -r email || email=""
  [ -z "$email" ] && email="admin@example.com"
else
  printf "  Login-E-Mail aendern? (j/N) "; read -r chg || chg=""
  case "$chg" in j|J|y|Y) printf "  Neue Login-E-Mail: "; read -r email || email="" ;; esac
fi
if [ -n "$email" ]; then
  if abctl local credentials --email "$email" >/dev/null 2>&1; then
    ok "Login-E-Mail gesetzt: $email"; current_email="$email"
  else
    warn "E-Mail konnte nicht gesetzt werden. Manuell: abctl local credentials --email <email>"
  fi
fi

# 2) Passwort setzen - verdeckt (read -rs), SEPARATER Aufruf NACH der E-Mail
printf "  Eigenes Passwort setzen? (j/N) "; read -r setpw || setpw=""
case "$setpw" in
  j|J|y|Y)
    printf "  Neues Passwort: "; read -rs newpass || newpass=""; echo
    if [ -n "$newpass" ]; then
      if abctl local credentials --password "$newpass" >/dev/null 2>&1; then
        ok "Passwort gesetzt."
      else
        warn "Passwort konnte nicht gesetzt werden. Manuell: abctl local credentials --password <pw>"
      fi
      unset newpass
    else
      warn "Leeres Passwort - keine Aenderung vorgenommen."
    fi
    ;;
  *) warn "Generiertes Passwort beibehalten." ;;
esac

echo
echo  "  Login-E-Mail: ${current_email:-(siehe \"abctl local credentials\")}"
echo  "  Passwort: aus Security-Gruenden nicht angezeigt. Bei Bedarf: abctl local credentials"

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
