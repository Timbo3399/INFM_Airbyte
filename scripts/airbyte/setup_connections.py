"""
setup_connections.py - legt die Connections ueber die Public API an.

Ergaenzt setup_objects.py (Sources und Destinations) um den zweiten
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
    python scripts/airbyte/setup_connections.py
"""

import os
import sys

from setup_objects import api_verbinden, plan

FULL_REFRESH = "full_refresh_overwrite"
INCREMENTAL_DEDUP = "incremental_deduped_history"

# Beide Postgres-Sources brauchen eine Katalog-Auffrischung, nicht nur die
# Quelle. In dest-postgres entsteht fm_raeume erst durch dbt, also lange nach
# dem Anlegen der Source, und Airbyte kennt nur den gespeicherten Stand
# (Befund 25 in docs/ergebnisse.md).
AUFZUFRISCHENDE_SOURCES = ("HSO Source PostgreSQL", "HSO Transform PostgreSQL")


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


def stream_fehlt_noch(antwort) -> bool:
    """True, wenn die API den Stream nur noch nicht kennt.

    Tritt beim ersten Aufbau auf: fm_raeume entsteht erst durch dbt, also nach
    diesem Skript. Die Connection wird dann vertagt und in einem zweiten Lauf
    nachgezogen, statt den ganzen Aufbau abzubrechen. Alle anderen Fehler, etwa
    ein fehlendes Pflichtfeld, muessen weiter laut knallen.
    """
    return "no streams found" in (antwort or "").lower()


def katalog_meldung(quelle: str, erkannt) -> str:
    """Meldung zur Schema-Auffrischung einer Source.

    Unterscheidet drei Faelle, die sonst gleich aussehen: erkannt, erkannt aber
    leer, und gar nicht erkannt. Beim ersten Aufbau ist dest-postgres schlicht
    noch leer, und das ist kein Fehler.
    """
    if erkannt is None:
        return f"Hinweis: Schema von '{quelle}' nicht lesbar, nutze den Cache."
    if not erkannt:
        return (f"Schema von '{quelle}' neu eingelesen: 0 Streams,"
                " die Datenbank ist noch leer.")
    return f"Schema von '{quelle}' neu eingelesen: {len(erkannt)} Streams."


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
        # Szenario 2: die FM-Rohtabellen ins Ziel bringen. Dort baut dbt daraus
        # fm_raeume. Genau die Arbeitsteilung, die ELT ausmacht: Airbyte
        # transportiert roh, transformiert wird in der Ziel-DB.
        #
        # fm_gebaeude fehlt hier absichtlich, obwohl das dbt-Modell es braucht.
        # Es kommt schon ueber "HSO PG nach PG" in dieselbe Zieltabelle, und
        # zwei Connections auf denselben Stream im selben Ziel verdoppeln die
        # Zeilen: Full Refresh Overwrite erhoeht die _airbyte_generation_id und
        # loescht nur echt aeltere Generationen, der Zaehler laeuft aber pro
        # Connection. Beim ersten Aufbau stehen beide auf 1, also raeumt keine
        # die Zeilen der anderen weg. Nachgemessen: aus 25 Zeilen wurden 50.
        "HSO FM nach PG": (
            src["HSO Source PostgreSQL"], dst["HSO Dest PostgreSQL"],
            [stream("fm_stamm", FULL_REFRESH),
             stream("fm_inst", FULL_REFRESH)]),
        # Nach dem dbt-Lauf: das fertige Modell weiter nach MySQL.
        "HSO fm_raeume nach MySQL": (
            src["HSO Transform PostgreSQL"], dst["HSO Dest MySQL"],
            [stream("fm_raeume", FULL_REFRESH)]),
    }


# --- Main ---------------------------------------------------------------------

def main():
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    api = api_verbinden(wurzel)

    src = {s["name"]: s["sourceId"] for s in api.liste("sources")}
    dst = {d["name"]: d["destinationId"] for d in api.liste("destinations")}
    fehlend = [n for n in ("HSO Source PostgreSQL", "HSO CSV hso_students",
                           "HSO Transform PostgreSQL",
                           "HSO Dest PostgreSQL", "HSO Dest MySQL")
               if n not in src and n not in dst]
    if fehlend:
        raise SystemExit("Fehlende Sources/Destinations: " + ", ".join(fehlend)
                         + "\nZuerst: python scripts/airbyte/setup_objects.py")

    # Kataloge auffrischen, bevor wir Connections anlegen. Ohne das kennt Airbyte
    # Tabellen und Views nicht, die seit der letzten Erkennung dazugekommen sind,
    # und lehnt den Stream als unbekannt ab.
    for quelle in AUFZUFRISCHENDE_SOURCES:
        print(katalog_meldung(quelle, api.discover_schema(src[quelle])))

    gewuenscht = gewuenschte_connections(src, dst)
    vorhanden = api.liste("connections")
    neu, bekannt = plan(vorhanden, list(gewuenscht), "connectionId")

    print("\nConnections:")
    for name, cid in bekannt.items():
        print(f"    vorhanden: {name} ({cid})")

    angelegt, vertagt = 0, []
    for name in neu:
        source_id, destination_id, streams = gewuenscht[name]
        try:
            antwort = api.anlegen("connections", connection_payload(
                name, source_id, destination_id, streams))
        except RuntimeError as e:
            if not stream_fehlt_noch(str(e)):
                raise
            # Der Stream entsteht erst spaeter im Ablauf, etwa fm_raeume durch dbt.
            print(f"    vertagt  : {name} (Stream gibt es noch nicht)")
            vertagt.append(name)
            continue
        modi = ", ".join(sorted({s["syncMode"] for s in streams}))
        print(f"    angelegt : {name} ({antwort.get('connectionId')}) [{modi}]")
        angelegt += 1

    print(f"\nFertig. {angelegt} Connections neu angelegt,"
          f" {len(bekannt)} waren vorhanden"
          + (f", {len(vertagt)} vertagt." if vertagt else "."))
    if vertagt:
        print("Vertagt, weil die Quelltabelle erst spaeter entsteht:"
              f" {', '.join(vertagt)}")
        print("Dieses Skript danach einfach erneut aufrufen,"
              " setup_szenarien.py macht das selbst.")
    print("Syncs starten: in der UI oder per POST /jobs {jobType: sync}.")


if __name__ == "__main__":
    sys.exit(main())
