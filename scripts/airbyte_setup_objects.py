"""
airbyte_setup_objects.py - legt Sources und Destinations ueber die Airbyte
Public API an, statt sie in der UI zusammenzuklicken.

Hintergrund: Der Datenbank-Stack ist per Skript reproduzierbar, die
Airbyte-Konfiguration war es nicht. Sie lebt im kind-Cluster und ist nach
`abctl local uninstall` oder `docker compose down -v` weg. Dieses Skript stellt
sie wieder her.

Das Skript ist idempotent: Objekte werden am Namen erkannt und nicht doppelt
angelegt. Ein zweiter Lauf meldet nur, was schon da ist.

Credentials werden in dieser Reihenfolge gesucht:
  1. Prozess-Umgebung (AIRBYTE_CLIENT_ID / AIRBYTE_CLIENT_SECRET)
  2. .env im Projektstamm
  3. `abctl local credentials`

Stolperstein bei 3: abctl faerbt seine Ausgabe ein und schreibt dabei rund 80
ANSI-Escape-Sequenzen mitten in die Werte. Wer die nicht entfernt, schickt acht
Zeichen Steuercode mit und bekommt vom Token-Endpunkt nur ein wenig hilfreiches
"Invalid client id or token".

Aufruf:
    python scripts/airbyte_setup_objects.py
"""

import json
import os
import re
import subprocess
import sys

import requests

API_URL = os.getenv("AIRBYTE_API_URL", "http://localhost:8000")
ABCTL_KANDIDATEN = ["abctl", r"C:\tools\airbyte\abctl.exe"]

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
TIMEOUT = 60

# In der Airbyte-UI muss host.docker.internal stehen, nicht localhost: Airbyte
# laeuft im kind-Cluster und damit nicht im Docker-Netz der Datenbanken.
DB_HOST = os.getenv("AIRBYTE_DB_HOST", "host.docker.internal")

# Pflichtfeld in allen DB-Connectoren. Fehlt es, antwortet die API mit
# HTTP 422 "required property 'tunnel_method' not found".
NO_TUNNEL = {"tunnel_method": "NO_TUNNEL"}


# --- reine Funktionen ---------------------------------------------------------

def read_env_file(path: str) -> dict:
    """Liest eine .env in ein dict. Fehlt die Datei, kommt {} zurueck."""
    werte = {}
    if not os.path.exists(path):
        return werte
    with open(path, encoding="utf-8") as f:
        for zeile in f:
            zeile = zeile.strip()
            if not zeile or zeile.startswith("#") or "=" not in zeile:
                continue
            schluessel, _, wert = zeile.partition("=")
            werte[schluessel.strip()] = wert.strip()
    return werte


def parse_abctl_credentials(text: str):
    """(Client-Id, Client-Secret) aus der Ausgabe von `abctl local credentials`."""
    sauber = ANSI.sub("", text or "")
    cid = re.search(r"Client-Id:\s*(\S+)", sauber)
    csec = re.search(r"Client-Secret:\s*(\S+)", sauber)
    return (cid.group(1) if cid else None, csec.group(1) if csec else None)


def resolve_credentials(prozess_env: dict, datei_env: dict, abctl_text):
    """Erste Quelle, die BEIDE Werte liefert, gewinnt."""
    for quelle in (prozess_env, datei_env):
        cid = (quelle or {}).get("AIRBYTE_CLIENT_ID")
        csec = (quelle or {}).get("AIRBYTE_CLIENT_SECRET")
        if cid and csec:
            return cid, csec
    if abctl_text:
        cid, csec = parse_abctl_credentials(abctl_text)
        if cid and csec:
            return cid, csec
    return None, None


def find_by_name(items, name: str, id_key: str):
    """Id des Objekts mit diesem Namen, sonst None."""
    for item in items or []:
        if item.get("name") == name:
            return item.get(id_key)
    return None


def plan(existing, desired_names, id_key):
    """(anzulegen, bereits vorhanden) fuer eine Liste gewuenschter Namen."""
    neu, bekannt = [], {}
    for name in desired_names:
        oid = find_by_name(existing, name, id_key)
        if oid:
            bekannt[name] = oid
        else:
            neu.append(name)
    return neu, bekannt


# --- Payloads -----------------------------------------------------------------

def source_postgres_config(host, port, database, username, password, schemas=("public",)):
    return {
        "sourceType": "postgres",
        "host": host,
        "port": int(port),
        "database": database,
        "username": username,
        "password": password,
        "schemas": list(schemas),
        "ssl_mode": {"mode": "disable"},
        # User Defined Cursor statt CDC: die Quelle hat kein wal_level=logical.
        "replication_method": {"method": "Standard"},
        "tunnel_method": NO_TUNNEL,
    }


def source_file_config(url, dataset_name, separator=","):
    return {
        "sourceType": "file",
        "url": url,
        "provider": {"storage": "local"},
        "format": "csv",
        "dataset_name": dataset_name,
        "reader_options": json.dumps({"sep": separator}),
    }


def destination_postgres_config(host, port, database, username, password, schema="public"):
    return {
        "destinationType": "postgres",
        "host": host,
        "port": int(port),
        "database": database,
        "schema": schema,
        "username": username,
        "password": password,
        "ssl_mode": {"mode": "disable"},
        "tunnel_method": NO_TUNNEL,
    }


def destination_mysql_config(host, port, database, username, password):
    return {
        "destinationType": "mysql",
        "host": host,
        "port": int(port),
        "database": database,
        "username": username,
        "password": password,
        "ssl": False,
        # Ohne allowPublicKeyRetrieval verweigert MySQL 8 die Verbindung.
        "jdbc_url_params": "allowPublicKeyRetrieval=true",
        # Rohdaten in dieselbe Datenbank schreiben. Voreingestellt waere
        # airbyte_internal, und weil das in MySQL eine eigene Datenbank ist,
        # muesste der Connector sie anlegen duerfen. destuser darf nur auf
        # destdb, der Sync stirbt sonst mit Exit-Code 1 im Destination-Prozess.
        "raw_data_schema": database,
        "tunnel_method": NO_TUNNEL,
    }


# --- API-Zugriff --------------------------------------------------------------

class AirbyteApi:
    def __init__(self, base_url: str, client_id: str, client_secret: str):
        self.base = base_url.rstrip("/") + "/api/public/v1"
        self._token = self._hole_token(client_id, client_secret)

    def _hole_token(self, client_id, client_secret):
        r = requests.post(
            f"{self.base}/applications/token", timeout=TIMEOUT,
            headers={"accept": "application/json", "content-type": "application/json"},
            json={"client_id": client_id, "client_secret": client_secret,
                  "grant-type": "client_credentials"})
        if r.status_code != 200:
            raise SystemExit(
                f"Token-Anfrage fehlgeschlagen (HTTP {r.status_code}): {r.text[:200]}")
        return r.json()["access_token"]

    @property
    def _headers(self):
        return {"accept": "application/json", "content-type": "application/json",
                "authorization": f"Bearer {self._token}"}

    def liste(self, pfad: str) -> list:
        r = requests.get(f"{self.base}/{pfad}?limit=100", headers=self._headers,
                         timeout=TIMEOUT)
        r.raise_for_status()
        return r.json().get("data", [])

    def anlegen(self, pfad: str, payload: dict) -> dict:
        r = requests.post(f"{self.base}/{pfad}", headers=self._headers,
                          json=payload, timeout=TIMEOUT)
        if r.status_code not in (200, 201):
            raise RuntimeError(f"POST /{pfad} -> HTTP {r.status_code}: {r.text[:400]}")
        return r.json()

    def workspace_id(self) -> str:
        ws = self.liste("workspaces")
        if not ws:
            raise SystemExit("Kein Workspace gefunden.")
        return ws[0]["workspaceId"]


# --- gewuenschter Soll-Zustand ------------------------------------------------

def gewuenschte_objekte(env: dict):
    """(sources, destinations) als {Name: configuration}."""
    def wert(name, default):
        return os.getenv(name) or env.get(name) or default

    src = dict(
        username=wert("SOURCE_PG_USER", "sourceuser"),
        password=wert("SOURCE_PG_PASSWORD", "sourcepassword"),
        database=wert("SOURCE_PG_DB", "sourcedb"))
    dst_pg = dict(
        username=wert("DEST_PG_USER", "destuser"),
        password=wert("DEST_PG_PASSWORD", "destpassword"),
        database=wert("DEST_PG_DB", "destdb"))
    dst_my = dict(
        username=wert("DEST_MYSQL_USER", "destuser"),
        password=wert("DEST_MYSQL_PASSWORD", "destpassword"),
        database=wert("DEST_MYSQL_DB", "destdb"))

    sources = {
        "HSO Source PostgreSQL": source_postgres_config(DB_HOST, 5433, **src),
        "HSO CSV hso_students": source_file_config(
            "/local/hso_students.csv", "hso_students", separator="|"),
        "HSO CSV k_plz": source_file_config("/local/k_plz.csv", "k_plz"),
        "HSO CSV fm_gebaeude": source_file_config(
            "/local/fm_gebaeude.csv", "fm_gebaeude"),
        "HSO CSV fm_inst": source_file_config(
            "/local/fm_inst.csv", "fm_inst", separator=";"),
    }
    destinations = {
        "HSO Dest PostgreSQL": destination_postgres_config(DB_HOST, 5434, **dst_pg),
        "HSO Dest MySQL": destination_mysql_config(DB_HOST, 3306, **dst_my),
    }
    return sources, destinations


# --- Main ---------------------------------------------------------------------

def abctl_credentials_text():
    for kandidat in ABCTL_KANDIDATEN:
        try:
            fertig = subprocess.run([kandidat, "local", "credentials"],
                                    capture_output=True, text=True, timeout=120)
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            continue
        if fertig.returncode == 0:
            return fertig.stdout
    return None


def main():
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    datei_env = read_env_file(os.path.join(wurzel, ".env"))

    client_id, client_secret = resolve_credentials(dict(os.environ), datei_env, None)
    if not client_id:
        print("Keine Credentials in Umgebung oder .env, frage abctl...")
        client_id, client_secret = resolve_credentials(
            {}, {}, abctl_credentials_text())
    if not client_id:
        raise SystemExit(
            "Keine API-Credentials gefunden. AIRBYTE_CLIENT_ID und"
            " AIRBYTE_CLIENT_SECRET in .env eintragen (siehe .env.example)"
            " oder abctl verfuegbar machen.")

    print(f"Verbinde mit Airbyte ({API_URL})...")
    api = AirbyteApi(API_URL, client_id, client_secret)
    ws = api.workspace_id()
    print(f"    Workspace {ws}")

    sources, destinations = gewuenschte_objekte(datei_env)
    angelegt = 0

    for pfad, gewuenscht, id_key, titel in (
            ("sources", sources, "sourceId", "Sources"),
            ("destinations", destinations, "destinationId", "Destinations")):
        print(f"\n{titel}:")
        vorhanden = api.liste(pfad)
        neu, bekannt = plan(vorhanden, list(gewuenscht), id_key)
        for name, oid in bekannt.items():
            print(f"    vorhanden: {name} ({oid})")
        for name in neu:
            antwort = api.anlegen(pfad, {"name": name, "workspaceId": ws,
                                         "configuration": gewuenscht[name]})
            print(f"    angelegt : {name} ({antwort.get(id_key)})")
            angelegt += 1

    if angelegt:
        print(f"\nFertig. {angelegt} Objekte neu angelegt.")
    else:
        print("\nFertig. Alles war bereits vorhanden, nichts geaendert.")
    print("Connections fuer die Szenarien werden separat angelegt.")


if __name__ == "__main__":
    sys.exit(main())
