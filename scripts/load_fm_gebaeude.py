"""
load_fm_gebaeude.py - Laedt fm_gebaeude.csv in source-postgres.

Sonderfall (laesst sich nicht per SQL-COPY laden):
  - komma-getrennt OHNE Header (26 Spalten)
  - vereinzelt UNQUOTIERTE Kommas in Textfeldern (z.B. geb2 = "Hoersaele,Bib.,RZ")
    -> betroffene Zeilen haben >26 Felder und brechen COPY mit
    "extra data after last expected column" ab
  - Umlaute liegen doppelt-kodiert vor ("GebÃ¤ude") -> werden repariert

Strategie: ueberzaehlige Felder werden wieder im Textfeld geb2 zusammengefuehrt.

Aufruf:
    python scripts/load_fm_gebaeude.py
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

DDL_FM_GEBAEUDE = """
CREATE TABLE IF NOT EXISTS fm_gebaeude (
    db_einfuegemarke  VARCHAR(10),
    geb_nr            VARCHAR(10)  NOT NULL,
    geb               VARCHAR(60),
    geb2              VARCHAR(60),
    baujahr           VARCHAR(10),
    besitz            VARCHAR(10),
    art               VARCHAR(10),
    gebber_nr         VARCHAR(10),
    hs_nr             VARCHAR(20),
    qkz               VARCHAR(10),
    fnw               INTEGER,
    pers_nr           INTEGER,
    denkmal_nr        VARCHAR(20),
    ort_nr            VARCHAR(10),
    stra_nr           VARCHAR(10),
    haus_nr           VARCHAR(20),
    gemark_nr         VARCHAR(10),
    flur_nr           VARCHAR(10),
    flurst_nr         VARCHAR(30),
    miete             DECIMAL(14,2),
    bauwerk           VARCHAR(20),
    b_grad            DECIMAL(15,10),
    l_grad            DECIMAL(15,10),
    bem               VARCHAR(255),
    text_geb          VARCHAR(255),
    kurz_geb          VARCHAR(20),
    PRIMARY KEY (geb_nr)
);
"""

N_COLS = 26
GEB2_IDX = 3  # Textfeld, das ueberzaehlige (unquotierte) Kommas aufnimmt


def demojibake(s):
    """Repariert doppelt-kodierte UTF-8 Umlaute (z.B. 'GebÃ¤ude' -> 'Gebäude')."""
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


def to_int(v):
    v = clean(v)
    if v is None:
        return None
    try:
        return int(v)
    except ValueError:
        return None


def to_decimal(v):
    v = clean(v)
    if v is None:
        return None
    try:
        return float(v.replace(",", "."))
    except ValueError:
        return None


def normalize(row: list) -> list:
    """Fuehrt >26-Feld-Zeilen wieder auf 26 zusammen (Ueberlauf in geb2)."""
    if len(row) > N_COLS:
        excess = len(row) - N_COLS
        merged = ",".join(row[GEB2_IDX:GEB2_IDX + excess + 1])
        row = row[:GEB2_IDX] + [merged] + row[GEB2_IDX + excess + 1:]
    while len(row) < N_COLS:
        row.append(None)
    return row


def read_rows(path: str) -> list:
    with open(path, "rb") as f:
        text = f.read().replace(b"\x00", b"").decode("utf-8", errors="replace")
    return list(csv.reader(io.StringIO(text), delimiter=",", quotechar='"'))  # kein Header


def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "sql", "source", "data", "fm_gebaeude.csv")

    print(f"Verbinde mit source-postgres ({DB['host']}:{DB['port']})...")
    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        print("\nfm_gebaeude.csv laden...")
        cur.execute(DDL_FM_GEBAEUDE)
        cur.execute("TRUNCATE TABLE fm_gebaeude")

        data, headers, skipped = [], 0, 0
        for raw in read_rows(path):
            if not raw or all((c or "").strip() == "" for c in raw):
                continue
            # eingebettete Header-Zeilen ueberspringen (kommen auch hier vor)
            if (raw[0].strip().strip('"') == "db_einfuegemarke"
                    or (len(raw) > 1 and raw[1].strip().strip('"') == "geb_nr")):
                headers += 1
                continue
            r = normalize(raw)
            c = [clean(x) for x in r]
            c[10] = to_int(r[10])      # fnw
            c[11] = to_int(r[11])      # pers_nr
            c[19] = to_decimal(r[19])  # miete
            c[21] = to_decimal(r[21])  # b_grad
            c[22] = to_decimal(r[22])  # l_grad
            if c[1] is None:           # geb_nr ist NOT NULL / PK
                skipped += 1
                continue
            data.append(tuple(c))

        execute_values(cur, """
            INSERT INTO fm_gebaeude
                (db_einfuegemarke, geb_nr, geb, geb2, baujahr, besitz, art, gebber_nr,
                 hs_nr, qkz, fnw, pers_nr, denkmal_nr, ort_nr, stra_nr, haus_nr,
                 gemark_nr, flur_nr, flurst_nr, miete, bauwerk, b_grad, l_grad, bem, text_geb, kurz_geb)
            VALUES %s
        """, data)

        conn.commit()
        print(f"    {len(data)} Zeilen in fm_gebaeude eingefuegt "
              f"({headers} Header-Zeilen ignoriert"
              + (f", {skipped} uebersprungen" if skipped else "") + ").")
        print("\nFertig. fm_gebaeude ist in source-postgres verfuegbar.")

    except Exception as e:
        conn.rollback()
        print(f"\nFEHLER: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
