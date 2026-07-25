"""
airbyte_setup_connections.py - legt die Connections ueber die Public API an.

Ergaenzt airbyte_setup_objects.py (Sources und Destinations) um den zweiten
Teil der Airbyte-Konfiguration. Zusammen stellen die beiden Skripte nach einem
`abctl local uninstall` den kompletten Stand wieder her.

Angelegt werden:
  * die drei im Zwischenbericht dokumentierten Full-Refresh-Connections
  * die IdM-Connection aus Szenario 5: hso_user nach MySQL, Incremental mit
    Deduplizierung ueber den Cursor updatedat und den Primaerschluessel user_id

Voraussetzung fuer Szenario 5 ist die View hso_user in der Quelle:
    python scripts/mapping/create_hso_user_view.py

Idempotent: Connections werden am Namen erkannt und nicht doppelt angelegt.

Aufruf:
    python scripts/airbyte_setup_connections.py
"""

import os
import sys

from airbyte_setup_objects import (
    API_URL, AirbyteApi, abctl_credentials_text, plan, read_env_file,
    resolve_credentials,
)

FULL_REFRESH = "full_refresh_overwrite"
INCREMENTAL_DEDUP = "incremental_deduped_history"


# --- reine Funktionen ---------------------------------------------------------

def stream(name: str, sync_mode: str, cursor: str = None, pk: str = None) -> dict:
    """Ein Stream-Eintrag fuer das Connection-Payload.

    Bei Dedup verlangt Airbyte Cursor UND Primaerschluessel. Fehlt eines davon,
    kommt die Ablehnung sonst erst aus der API zurueck, und zwar unspezifisch.
    """
    if sync_mode == INCREMENTAL_DEDUP:
        if not cursor:
            raise ValueError(f"{name}: Incremental mit Dedup braucht einen cursor")
        if not pk:
            raise ValueError(f"{name}: Incremental mit Dedup braucht einen primaryKey")

    eintrag = {"name": name, "syncMode": sync_mode}
    if cursor:
        eintrag["cursorField"] = [cursor]
    if pk:
        eintrag["primaryKey"] = [[pk]]
    return eintrag


def connection_payload(name, source_id, destination_id, streams) -> dict:
    """Zeitplan bewusst manuell: die Syncs sollen wir selbst ausloesen."""
    return {
        "name": name,
        "sourceId": source_id,
        "destinationId": destination_id,
        "configurations": {"streams": streams},
        "schedule": {"scheduleType": "manual"},
    }


def gewuenschte_connections(src: dict, dst: dict) -> dict:
    """{Name: (sourceId, destinationId, streams)} fuer die Soll-Connections."""
    return {
        "HSO PG nach PG (Full Refresh)": (
            src["HSO Source PostgreSQL"], dst["HSO Dest PostgreSQL"],
            [stream("fm_gebaeude", FULL_REFRESH), stream("k_plz", FULL_REFRESH)]),
        "HSO PG nach MySQL (Full Refresh)": (
            src["HSO Source PostgreSQL"], dst["HSO Dest MySQL"],
            [stream("fm_gebaeude", FULL_REFRESH), stream("k_plz", FULL_REFRESH)]),
        "HSO CSV hso_students nach PG": (
            src["HSO CSV hso_students"], dst["HSO Dest PostgreSQL"],
            [stream("hso_students", FULL_REFRESH)]),
        "HSO IdM hso_user nach MySQL": (
            src["HSO Source PostgreSQL"], dst["HSO Dest MySQL"],
            [stream("hso_user", INCREMENTAL_DEDUP,
                    cursor="updatedat", pk="user_id")]),
        # Szenario 3: BYTEA-Handling der Destination pruefen.
        "HSO Bilder nach MySQL": (
            src["HSO Source PostgreSQL"], dst["HSO Dest MySQL"],
            [stream("hso_images", FULL_REFRESH)]),
        # Szenario 2: die drei FM-Rohtabellen ins Ziel bringen. Dort baut dbt
        # daraus fm_raeume. Genau die Arbeitsteilung, die ELT ausmacht:
        # Airbyte transportiert roh, transformiert wird in der Ziel-DB.
        "HSO FM nach PG": (
            src["HSO Source PostgreSQL"], dst["HSO Dest PostgreSQL"],
            [stream("fm_stamm", FULL_REFRESH),
             stream("fm_gebaeude", FULL_REFRESH),
             stream("fm_inst", FULL_REFRESH)]),
        # Nach dem dbt-Lauf: das fertige Modell weiter nach MySQL.
        "HSO fm_raeume nach MySQL": (
            src["HSO Transform PostgreSQL"], dst["HSO Dest MySQL"],
            [stream("fm_raeume", FULL_REFRESH)]),
    }


# --- Main ---------------------------------------------------------------------

def main():
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    datei_env = read_env_file(os.path.join(wurzel, ".env"))

    client_id, client_secret = resolve_credentials(dict(os.environ), datei_env, None)
    if not client_id:
        client_id, client_secret = resolve_credentials({}, {}, abctl_credentials_text())
    if not client_id:
        raise SystemExit("Keine API-Credentials gefunden, siehe .env.example.")

    print(f"Verbinde mit Airbyte ({API_URL})...")
    api = AirbyteApi(API_URL, client_id, client_secret)

    src = {s["name"]: s["sourceId"] for s in api.liste("sources")}
    dst = {d["name"]: d["destinationId"] for d in api.liste("destinations")}
    fehlend = [n for n in ("HSO Source PostgreSQL", "HSO CSV hso_students",
                           "HSO Transform PostgreSQL",
                           "HSO Dest PostgreSQL", "HSO Dest MySQL")
               if n not in src and n not in dst]
    if fehlend:
        raise SystemExit("Fehlende Sources/Destinations: " + ", ".join(fehlend)
                         + "\nZuerst: python scripts/airbyte_setup_objects.py")

    # Katalog der Postgres-Quelle auffrischen, bevor wir Connections anlegen.
    # Ohne das kennt Airbyte Tabellen und Views nicht, die seit der letzten
    # Erkennung dazugekommen sind, und lehnt den Stream als unbekannt ab.
    erkannt = api.discover_schema(src["HSO Source PostgreSQL"])
    if erkannt:
        print(f"Schema der Quelle neu eingelesen: {len(erkannt)} Streams.")
    else:
        print("Hinweis: Schema-Erkennung nicht moeglich, nutze den Cache.")

    gewuenscht = gewuenschte_connections(src, dst)
    vorhanden = api.liste("connections")
    neu, bekannt = plan(vorhanden, list(gewuenscht), "connectionId")

    print("\nConnections:")
    for name, cid in bekannt.items():
        print(f"    vorhanden: {name} ({cid})")
    for name in neu:
        source_id, destination_id, streams = gewuenscht[name]
        antwort = api.anlegen("connections", connection_payload(
            name, source_id, destination_id, streams))
        modi = ", ".join(sorted({s["syncMode"] for s in streams}))
        print(f"    angelegt : {name} ({antwort.get('connectionId')}) [{modi}]")

    print(f"\nFertig. {len(neu)} Connections neu angelegt,"
          f" {len(bekannt)} waren vorhanden.")
    print("Syncs starten: in der UI oder per POST /jobs {jobType: sync}.")


if __name__ == "__main__":
    sys.exit(main())
