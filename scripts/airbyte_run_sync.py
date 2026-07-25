"""
airbyte_run_sync.py - startet einen Sync ueber die Public API und wartet darauf.

Damit lassen sich die Szenarien reproduzierbar durchspielen, ohne in der UI zu
klicken. Fuer den Aenderungstest in Szenario 5 ist das praktisch: Quelle
aendern, Sync starten, Ziel pruefen.

Aufruf:
    python scripts/airbyte_run_sync.py "HSO IdM hso_user nach MySQL"
    python scripts/airbyte_run_sync.py --list
"""

import os
import sys
import time

import requests

from airbyte_setup_objects import (
    API_URL, AirbyteApi, abctl_credentials_text, find_by_name, read_env_file,
    resolve_credentials,
)

ENDZUSTAENDE = {"succeeded", "failed", "cancelled"}
POLL_SEKUNDEN = 5
MAX_WARTEN = 900


def ist_fertig(status: str) -> bool:
    return (status or "").lower() in ENDZUSTAENDE


def laufender_job(jobs, connection_id: str):
    """Noch nicht abgeschlossener Job dieser Connection, sonst None.

    Airbyte laesst pro Connection nur einen Sync gleichzeitig zu und antwortet
    sonst mit HTTP 409. Besser vorher nachsehen als hinterher stolpern.
    """
    for job in jobs or []:
        if job.get("connectionId") == connection_id and not ist_fertig(job.get("status")):
            return job
    return None


def summarize_job(job: dict) -> str:
    teile = [f"Job {job.get('jobId')}", f"Status {job.get('status')}"]
    if job.get("rowsSynced") is not None:
        teile.append(f"{job['rowsSynced']} Zeilen")
    if job.get("bytesSynced") is not None:
        teile.append(f"{job['bytesSynced']} Bytes")
    if job.get("duration"):
        teile.append(f"Dauer {job['duration']}")
    return ", ".join(teile)


def _api():
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    datei_env = read_env_file(os.path.join(wurzel, ".env"))
    cid, csec = resolve_credentials(dict(os.environ), datei_env, None)
    if not cid:
        cid, csec = resolve_credentials({}, {}, abctl_credentials_text())
    if not cid:
        raise SystemExit("Keine API-Credentials gefunden, siehe .env.example.")
    return AirbyteApi(API_URL, cid, csec)


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        raise SystemExit(__doc__)

    api = _api()
    connections = api.liste("connections")

    if argv[0] == "--list":
        for c in connections:
            print(f"  {c['name']}  ({c['connectionId']})")
        return 0

    name = argv[0]
    connection_id = find_by_name(connections, name, "connectionId")
    if not connection_id:
        print(f"Connection '{name}' nicht gefunden. Vorhanden:")
        for c in connections:
            print(f"  {c['name']}")
        return 1

    offen = laufender_job(api.liste("jobs"), connection_id)
    if offen:
        print(f"Fuer '{name}' laeuft bereits Job {offen.get('jobId')}"
              f" (Status {offen.get('status')}).")
        print("    Abwarten oder abbrechen:"
              f" DELETE /api/public/v1/jobs/{offen.get('jobId')}")
        return 1

    print(f"Starte Sync: {name}")
    job = api.anlegen("jobs", {"connectionId": connection_id, "jobType": "sync"})
    job_id = job.get("jobId")
    print(f"    Job {job_id} gestartet, warte...")

    start = time.time()
    while time.time() - start < MAX_WARTEN:
        time.sleep(POLL_SEKUNDEN)
        r = requests.get(f"{api.base}/jobs/{job_id}", headers=api._headers, timeout=60)
        r.raise_for_status()
        job = r.json()
        if ist_fertig(job.get("status")):
            break
        print(f"    ... {job.get('status')} ({int(time.time() - start)} s)")
    else:
        print(f"    Zeitueberschreitung nach {MAX_WARTEN} s.")
        return 1

    print("    " + summarize_job(job))
    return 0 if job.get("status") == "succeeded" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
