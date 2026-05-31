"""
load_k_plz.py - Laedt k_plz.csv (PLZ-Verzeichnis) in source-postgres.

Sonderfall (laesst sich nicht per SQL-COPY laden):
  - komma-getrennt (10 Spalten), aber die Quelle ist aus vielen Einzel-Exporten
    zusammengesetzt: alle ~10 Zeilen steht erneut eine HEADER-Zeile
    ("db_einfuegemarke,plz,...") mitten in den Daten -> COPY bricht ab
    ("value too long for ... db_einfuegemarke")
  - einige Zeilen haben zu wenige (7) oder zu viele (11) Felder

Strategie: Header-Zeilen ueberspringen, fehlende Felder mit NULL auffuellen,
ueberzaehlige Felder ins letzte Textfeld (vv_bez) zusammenfuehren. Die fuehrenden
Schluesselfelder (plz, ort) bleiben so immer korrekt.

Aufruf:
    python scripts/load_k_plz.py
"""

import csv
import io
import os
import psycopg2
from psycopg2.extras import execute_values

DB = dict(
    host=os.getenv("SOURCE_PG_HOST", "localhost"),
    port=int(os.getenv("SOURCE_PG_PORT", "5433")),
    dbname=os.getenv("SOURCE_PG_DB", "sourcedb"),
    user=os.getenv("SOURCE_PG_USER", "sourceuser"),
    password=os.getenv("SOURCE_PG_PASSWORD", "sourcepassword"),
)

DDL_K_PLZ = """
CREATE TABLE IF NOT EXISTS k_plz (
    db_einfuegemarke  VARCHAR(10),
    plz               VARCHAR(10)  NOT NULL,
    ueberkey          VARCHAR(10),
    art               VARCHAR(5),
    aikz              VARCHAR(5),
    grokz             VARCHAR(5),
    ort               VARCHAR(60),
    krskfz            VARCHAR(50),   -- enthaelt teils Kreis-Namen (z.B. "Kr Hzgt Lauenburg")
    krs_astat         VARCHAR(10),
    vv_bez            VARCHAR(60)
);
"""

N_COLS = 10
VVBEZ_IDX = 9  # letztes (Text-)Feld nimmt ueberzaehlige Kommas auf


def demojibake(s):
    if s is None or ("Ã" not in s and "Â" not in s):
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def clean(v):
    if v is None:
        return None
    v = demojibake(v.strip())
    return v if v != "" else None


def normalize(row: list) -> list:
    if len(row) > N_COLS:
        merged = ",".join(row[VVBEZ_IDX:])
        row = row[:VVBEZ_IDX] + [merged]
    while len(row) < N_COLS:
        row.append(None)
    return row


def read_rows(path: str) -> list:
    with open(path, "rb") as f:
        text = f.read().replace(b"\x00", b"").decode("utf-8", errors="replace")
    return list(csv.reader(io.StringIO(text), delimiter=",", quotechar='"'))


def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "sql", "source", "data", "k_plz.csv")

    print(f"Verbinde mit source-postgres ({DB['host']}:{DB['port']})...")
    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        print("\nk_plz.csv laden...")
        cur.execute(DDL_K_PLZ)
        cur.execute("TRUNCATE TABLE k_plz")

        data, headers, skipped = [], 0, 0
        for raw in read_rows(path):
            if not raw or all((c or "").strip() == "" for c in raw):
                continue
            # eingebettete Header-Zeilen ueberspringen
            if (raw[0].strip().strip('"') == "db_einfuegemarke"
                    or (len(raw) > 1 and raw[1].strip().strip('"') == "plz")):
                headers += 1
                continue
            r = normalize(raw)
            c = [clean(x) for x in r]
            if c[1] is None:           # plz ist NOT NULL
                skipped += 1
                continue
            data.append(tuple(c))

        execute_values(cur, """
            INSERT INTO k_plz
                (db_einfuegemarke, plz, ueberkey, art, aikz, grokz, ort, krskfz, krs_astat, vv_bez)
            VALUES %s
        """, data, page_size=1000)

        conn.commit()
        print(f"    {len(data)} Zeilen in k_plz eingefuegt "
              f"({headers} Header-Zeilen ignoriert"
              + (f", {skipped} ohne PLZ uebersprungen" if skipped else "") + ").")
        print("\nFertig. k_plz ist in source-postgres verfuegbar.")

    except Exception as e:
        conn.rollback()
        print(f"\nFEHLER: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
