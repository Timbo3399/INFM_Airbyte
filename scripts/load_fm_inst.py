"""
load_fm_inst.py - Laedt fm_inst.csv in source-postgres.

Sonderfall (laesst sich nicht per SQL-COPY laden):
  - semikolon-getrennt, 86 Spalten (die Tabelle nutzt die ersten 24,
    Namen + Reihenfolge sind identisch)
  - enthaelt vereinzelt NUL-Bytes (0x00) -> COPY bricht mit
    "invalid byte sequence for encoding UTF8" ab

Dieses Skript entfernt NUL-Bytes, nimmt die ersten 24 Spalten und schreibt
sie typgerecht nach fm_inst (idempotent: TRUNCATE + INSERT).

Aufruf:
    python scripts/load_fm_inst.py

Voraussetzungen:
    pip install psycopg2-binary
    DB-Stack laeuft (docker compose up -d)
"""

import csv
import io
import os
import psycopg2
from psycopg2.extras import execute_values
from datetime import date

# --- Verbindungsparameter (wie load_json.py / generate_accounts.py) ---------

DB = dict(
    host=os.getenv("SOURCE_PG_HOST", "localhost"),
    port=int(os.getenv("SOURCE_PG_PORT", "5433")),
    dbname=os.getenv("SOURCE_PG_DB", "sourcedb"),
    user=os.getenv("SOURCE_PG_USER", "sourceuser"),
    password=os.getenv("SOURCE_PG_PASSWORD", "sourcepassword"),
)

# Tabelle nutzt die ersten 24 Spalten der CSV (identische Namen + Reihenfolge).
DDL_FM_INST = """
CREATE TABLE IF NOT EXISTS fm_inst (
    db_einfuegemarke  VARCHAR(10),
    inst_nr           VARCHAR(20)  NOT NULL,
    uebinst_nr        VARCHAR(20),
    kname             VARCHAR(20),
    dname             VARCHAR(60),
    lname1            VARCHAR(120),
    lname2            VARCHAR(120),
    str               VARCHAR(60),
    gebname           VARCHAR(60),
    plz               VARCHAR(10),
    ort               VARCHAR(60),
    bes_pers          VARCHAR(60),
    bes_tel           VARCHAR(30),
    bes_umsatz        DECIMAL(14,2),
    bes_vj_umsatz1    DECIMAL(14,2),
    bes_vj_umsatz2    DECIMAL(14,2),
    ivs_pers          VARCHAR(60),
    ivs_tel           VARCHAR(30),
    fins              VARCHAR(20),
    lehr              VARCHAR(10),
    habpos            VARCHAR(10),
    orgstruktur       INTEGER,
    key_von           DATE,
    key_bis           DATE
);
"""

N_COLS = 24  # nur die ersten 24 der 86 CSV-Spalten werden uebernommen


def clean(v):
    """Trimmt Whitespace (die Quelle ist stark mit Leerzeichen aufgefuellt);
    leere Werte werden zu NULL."""
    if v is None:
        return None
    v = v.strip()
    return v if v != "" else None


def to_decimal(v):
    v = clean(v)
    if v is None:
        return None
    try:
        return float(v.replace(",", "."))
    except ValueError:
        return None


def to_int(v):
    v = clean(v)
    if v is None:
        return None
    try:
        return int(v)
    except ValueError:
        return None


def to_date(v):
    v = clean(v)
    if v is None:
        return None
    try:
        return date.fromisoformat(v)  # Quelle liefert ISO (YYYY-MM-DD)
    except ValueError:
        return None


def read_rows(path: str) -> list:
    """Liest die CSV binaer, entfernt NUL-Bytes und parst sie semikolon-getrennt."""
    with open(path, "rb") as f:
        raw = f.read().replace(b"\x00", b"")
    text = raw.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text), delimiter=";", quotechar='"')
    rows = list(reader)
    return rows[1:]  # Header ueberspringen


def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "sql", "source", "data", "fm_inst.csv")

    print(f"Verbinde mit source-postgres ({DB['host']}:{DB['port']})...")
    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        print("\nfm_inst.csv laden...")
        cur.execute(DDL_FM_INST)
        cur.execute("TRUNCATE TABLE fm_inst")

        data = []
        skipped = 0
        for r in read_rows(path):
            if len(r) < N_COLS:
                skipped += 1
                continue
            c = [clean(x) for x in r[:N_COLS]]
            c[13] = to_decimal(r[13])   # bes_umsatz
            c[14] = to_decimal(r[14])   # bes_vj_umsatz1
            c[15] = to_decimal(r[15])   # bes_vj_umsatz2
            c[21] = to_int(r[21])       # orgstruktur
            c[22] = to_date(r[22])      # key_von
            c[23] = to_date(r[23])      # key_bis
            if c[1] is None:            # inst_nr ist NOT NULL
                skipped += 1
                continue
            data.append(tuple(c))

        execute_values(cur, """
            INSERT INTO fm_inst
                (db_einfuegemarke, inst_nr, uebinst_nr, kname, dname, lname1, lname2, str,
                 gebname, plz, ort, bes_pers, bes_tel, bes_umsatz, bes_vj_umsatz1, bes_vj_umsatz2,
                 ivs_pers, ivs_tel, fins, lehr, habpos, orgstruktur, key_von, key_bis)
            VALUES %s
        """, data)

        conn.commit()
        print(f"    {len(data)} Zeilen in fm_inst eingefuegt"
              + (f" ({skipped} uebersprungen)." if skipped else "."))
        print("\nFertig. fm_inst ist in source-postgres verfuegbar.")

    except Exception as e:
        conn.rollback()
        print(f"\nFEHLER: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
