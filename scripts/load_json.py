"""
load_json.py - Laedt fm_rna.json und hso_personal.json in source-postgres

Aufruf:
    python scripts/load_json.py

Voraussetzungen:
    pip install psycopg2-binary
    DB-Stack laeuft (docker compose up -d)
"""

import json
import os
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, date

# --- Verbindungsparameter ---------------------------------------------------

DB = dict(
    host=os.getenv("SOURCE_PG_HOST", "localhost"),
    port=int(os.getenv("SOURCE_PG_PORT", "5433")),
    dbname=os.getenv("SOURCE_PG_DB", "sourcedb"),
    user=os.getenv("SOURCE_PG_USER", "sourceuser"),
    password=os.getenv("SOURCE_PG_PASSWORD", "sourcepassword"),
)

# --- Hilfsfunktionen --------------------------------------------------------

def load_json_file(path: str) -> list:
    """Liest eine JSON-Datei mit der ungewoehnlichen {SQL_QUERY: [...]} Struktur."""
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    # Erster (und einziger) Schluessel ist die SQL-Query, Wert ist die Liste
    return list(raw.values())[0]


def strip_row(row: dict) -> dict:
    """Bereinigt String-Werte: entfernt fuehrende/nachfolgende Leerzeichen."""
    return {
        k: (v.strip() if isinstance(v, str) else v)
        for k, v in row.items()
    }


def parse_ts(val):
    """Konvertiert Timestamp-Strings ins Python-datetime-Objekt."""
    if val is None or val == "":
        return None
    try:
        return datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def parse_date(val):
    """Konvertiert Datums-Strings ins Python-date-Objekt."""
    if val is None or val == "":
        return None
    try:
        return date.fromisoformat(val)
    except Exception:
        return None


# --- fm_rna -----------------------------------------------------------------

DDL_FM_RNA = """
CREATE TABLE IF NOT EXISTS fm_rna (
    rna_nr          VARCHAR(20),
    kurz_rna        VARCHAR(50),
    rna             VARCHAR(60),
    text_rna        TEXT,
    rnaber_nr       VARCHAR(10),
    db_einfuegemarke VARCHAR(50)
);
"""

def load_fm_rna(cur, rows: list):
    cur.execute("TRUNCATE TABLE fm_rna")
    data = [
        (
            r.get("rna_nr"),
            r.get("kurz_rna"),
            r.get("rna"),
            r.get("text_rna"),
            r.get("rnaber_nr"),
            r.get("db_einfuegemarke"),
        )
        for r in rows
    ]
    execute_values(cur, """
        INSERT INTO fm_rna
            (rna_nr, kurz_rna, rna, text_rna, rnaber_nr, db_einfuegemarke)
        VALUES %s
    """, data)
    return len(data)


# --- hso_personal -----------------------------------------------------------

DDL_HSO_PERSONAL = """
CREATE TABLE IF NOT EXISTS hso_personal (
    id          INTEGER PRIMARY KEY,
    nachname    VARCHAR(100),
    vorname     VARCHAR(100),
    user_id     VARCHAR(20),
    sva_rolle   VARCHAR(60),
    dienstart   VARCHAR(60),
    h1_status   VARCHAR(20),
    geschlecht  VARCHAR(5),
    geb_dat     DATE,
    titel_key   VARCHAR(10),
    titel       VARCHAR(60),
    hso_email   VARCHAR(255),
    createdat   TIMESTAMP,
    updatedat   TIMESTAMP,
    sva_last    DATE
);
CREATE INDEX IF NOT EXISTS idx_hso_personal_updatedat ON hso_personal (updatedat);
"""

def load_hso_personal(cur, rows: list):
    cur.execute("TRUNCATE TABLE hso_personal")
    data = [
        (
            r.get("ID"),
            r.get("nachname") or None,
            r.get("vorname") or None,
            r.get("user_id") or None,
            r.get("sva_rolle"),
            r.get("dienstart"),
            r.get("h1_status"),
            r.get("geschlecht"),
            parse_date(r.get("geb_dat")),
            r.get("titel_key"),
            r.get("titel"),
            r.get("hso_email") or None,
            parse_ts(r.get("createdAt")),
            parse_ts(r.get("updatedAt")),
            parse_date(r.get("sva_last")),
        )
        for r in rows
    ]
    execute_values(cur, """
        INSERT INTO hso_personal
            (id, nachname, vorname, user_id, sva_rolle, dienstart,
             h1_status, geschlecht, geb_dat, titel_key, titel, hso_email,
             createdat, updatedat, sva_last)
        VALUES %s
    """, data)
    return len(data)


# --- Main -------------------------------------------------------------------

def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    print(f"Verbinde mit source-postgres ({DB['host']}:{DB['port']})...")
    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # fm_rna
        print("\n[1/2] fm_rna.json laden...")
        cur.execute(DDL_FM_RNA)
        rows = [strip_row(r) for r in load_json_file(
            os.path.join(base, "data", "json", "fm_rna.json")
        )]
        n = load_fm_rna(cur, rows)
        print(f"    {n} Zeilen in fm_rna eingefuegt.")

        # hso_personal
        print("\n[2/2] hso_personal.json laden...")
        cur.execute(DDL_HSO_PERSONAL)
        rows = [strip_row(r) for r in load_json_file(
            os.path.join(base, "data", "json", "hso_personal.json")
        )]
        n = load_hso_personal(cur, rows)
        print(f"    {n} Zeilen in hso_personal eingefuegt.")

        conn.commit()
        print("\nFertig. Beide Tabellen sind in source-postgres verfuegbar.")

    except Exception as e:
        conn.rollback()
        print(f"\nFEHLER: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
