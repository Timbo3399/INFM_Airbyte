"""
load_lookups.py - Laedt die restlichen Lookup-/Stammtabellen aus data.zip in
source-postgres:

    anredetitel   <- data/csv/anredetitel.csv             (Semikolon, 18 Spalten)
    k_hochschule  <- data/csv/k_hochschule.csv            (Komma, 16 Spalten)
    k_res         <- data/csv/k_res/k_res*.csv (8 Dateien) konsolidiert in EINE
                     Tabelle mit Diskriminator res_typ (1,2,3,4,5,11,12,13)

Alle drei sind klassische HISinOne-Schluesseltabellen (stark mit Leerzeichen
aufgefuellt, teils doppelt-kodierte Umlaute) und werden hier getrimmt,
demojibaked und typgerecht geladen.

Aufruf:
    python scripts/load_lookups.py
"""

import csv
import glob
import io
import os
import re
from datetime import date

import psycopg2
from psycopg2.extras import execute_values

DB = dict(
    host=os.getenv("SOURCE_PG_HOST", "localhost"),
    port=int(os.getenv("SOURCE_PG_PORT", "5433")),
    dbname=os.getenv("SOURCE_PG_DB", "sourcedb"),
    user=os.getenv("SOURCE_PG_USER", "sourceuser"),
    password=os.getenv("SOURCE_PG_PASSWORD", "sourcepassword"),
)


# --- Hilfsfunktionen --------------------------------------------------------

def demojibake(s):
    if not isinstance(s, str) or ("Ã" not in s and "Â" not in s):
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
        return int(float(v))
    except ValueError:
        return None


def to_date(v):
    v = clean(v)
    if v is None:
        return None
    try:
        return date.fromisoformat(v[:10])
    except ValueError:
        return None


def read_csv(path, delimiter):
    with open(path, "rb") as f:
        text = f.read().replace(b"\x00", b"").decode("utf-8", errors="replace")
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter, quotechar='"'))
    return rows[0], rows[1:]            # header, data


# --- anredetitel ------------------------------------------------------------

DDL_ANREDETITEL = """
CREATE TABLE IF NOT EXISTS anredetitel (
    db_einfuegemarke    VARCHAR(10),
    key_anredetitel     VARCHAR(20),
    ueberkey            VARCHAR(20),
    kurz_anredetitel_m  VARCHAR(30),
    kurz_anredetitel_w  VARCHAR(30),
    druck_anredetitelm  VARCHAR(80),
    druck_anredetitelw  VARCHAR(80),
    text_anredetitel_m  TEXT,
    text_anredetitel_w  TEXT,
    key_von             DATE,
    key_bis             DATE,
    brief_anredetitelm  TEXT,
    brief_anredetitelw  TEXT,
    obj_guid            VARCHAR(50),
    lock_version        INTEGER,
    id                  INTEGER,
    k_language_id       VARCHAR(10),
    sortorder           INTEGER
);
"""

ANREDETITEL_INT = {14, 15, 17}      # lock_version, id, sortorder
ANREDETITEL_DATE = {9, 10}          # key_von, key_bis


def load_anredetitel(cur, base):
    path = os.path.join(base, "data", "csv", "anredetitel.csv")
    cur.execute(DDL_ANREDETITEL)
    cur.execute("TRUNCATE TABLE anredetitel")
    _, rows = read_csv(path, ";")
    data = []
    for r in rows:
        if not r or all((c or "").strip() == "" for c in r):
            continue
        r = (r + [None] * 18)[:18]
        rec = []
        for i, v in enumerate(r):
            if i in ANREDETITEL_INT:
                rec.append(to_int(v))
            elif i in ANREDETITEL_DATE:
                rec.append(to_date(v))
            else:
                rec.append(clean(v))
        data.append(tuple(rec))
    execute_values(cur, """
        INSERT INTO anredetitel
            (db_einfuegemarke, key_anredetitel, ueberkey, kurz_anredetitel_m,
             kurz_anredetitel_w, druck_anredetitelm, druck_anredetitelw,
             text_anredetitel_m, text_anredetitel_w, key_von, key_bis,
             brief_anredetitelm, brief_anredetitelw, obj_guid, lock_version,
             id, k_language_id, sortorder)
        VALUES %s
    """, data, page_size=1000)
    return len(data)


# --- k_hochschule -----------------------------------------------------------

DDL_K_HOCHSCHULE = """
CREATE TABLE IF NOT EXISTS k_hochschule (
    db_einfuegemarke  VARCHAR(10),
    key_hochschule    VARCHAR(10),
    ueberkey          VARCHAR(10),
    kurz_hochschule   VARCHAR(60),
    druck_hochschule  VARCHAR(120),
    text_hochschule   TEXT,
    bund_hochschule   VARCHAR(10),
    key_von           DATE,
    key_bis           DATE,
    habil_recht       VARCHAR(5),
    land_hochschule   VARCHAR(10),
    art               VARCHAR(10),
    betriebsnummer    VARCHAR(20),
    haupt_neben_kz    VARCHAR(5),
    plz               VARCHAR(10),
    ort               VARCHAR(60)
);
"""

K_HOCHSCHULE_DATE = {7, 8}          # key_von, key_bis


def load_k_hochschule(cur, base):
    path = os.path.join(base, "data", "csv", "k_hochschule.csv")
    cur.execute(DDL_K_HOCHSCHULE)
    cur.execute("TRUNCATE TABLE k_hochschule")
    _, rows = read_csv(path, ",")
    data = []
    for r in rows:
        if not r or all((c or "").strip() == "" for c in r):
            continue
        r = (r + [None] * 16)[:16]
        rec = [to_date(v) if i in K_HOCHSCHULE_DATE else clean(v)
               for i, v in enumerate(r)]
        data.append(tuple(rec))
    execute_values(cur, """
        INSERT INTO k_hochschule
            (db_einfuegemarke, key_hochschule, ueberkey, kurz_hochschule,
             druck_hochschule, text_hochschule, bund_hochschule, key_von, key_bis,
             habil_recht, land_hochschule, art, betriebsnummer, haupt_neben_kz,
             plz, ort)
        VALUES %s
    """, data, page_size=1000)
    return len(data)


# --- k_res (8 Dateien -> 1 konsolidierte Tabelle) ---------------------------

DDL_K_RES = """
CREATE TABLE IF NOT EXISTS k_res (
    res_typ  VARCHAR(5)  NOT NULL,   -- aus Dateiname: 1,2,3,4,5,11,12,13
    res      VARCHAR(20) NOT NULL,   -- Schluesselwert (erste Spalte der Datei)
    aikz     VARCHAR(5),
    ktxt     VARCHAR(50),
    dtxt     VARCHAR(60),
    ltxt     VARCHAR(120),
    PRIMARY KEY (res_typ, res)
);
"""


def load_k_res(cur, base):
    cur.execute(DDL_K_RES)
    cur.execute("TRUNCATE TABLE k_res")
    pattern = os.path.join(base, "data", "csv", "k_res", "k_res*.csv")
    data, seen, dups = [], set(), 0
    for path in sorted(glob.glob(pattern)):
        m = re.search(r"k_res(\d+)_", os.path.basename(path))
        res_typ = m.group(1) if m else "?"
        _, rows = read_csv(path, ";")
        for r in rows:
            if not r or all((c or "").strip() == "" for c in r):
                continue
            r = (r + [None] * 5)[:5]
            res = clean(r[0])
            if res is None:
                continue
            pk = (res_typ, res)
            if pk in seen:
                dups += 1
                continue
            seen.add(pk)
            data.append((res_typ, res, clean(r[1]), clean(r[2]),
                         clean(r[3]), clean(r[4])))
    execute_values(cur, """
        INSERT INTO k_res (res_typ, res, aikz, ktxt, dtxt, ltxt)
        VALUES %s
    """, data, page_size=1000)
    return len(data), dups


# --- Main -------------------------------------------------------------------

def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    print(f"Verbinde mit source-postgres ({DB['host']}:{DB['port']})...")
    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        print("\n[1/3] anredetitel.csv laden...")
        n = load_anredetitel(cur, base)
        print(f"    {n} Zeilen in anredetitel eingefuegt.")

        print("\n[2/3] k_hochschule.csv laden...")
        n = load_k_hochschule(cur, base)
        print(f"    {n} Zeilen in k_hochschule eingefuegt.")

        print("\n[3/3] k_res*.csv laden (konsolidiert)...")
        n, dups = load_k_res(cur, base)
        print(f"    {n} Zeilen in k_res eingefuegt"
              + (f" ({dups} Duplikate uebersprungen)." if dups else "."))

        conn.commit()
        print("\nFertig. anredetitel, k_hochschule und k_res sind verfuegbar.")

    except Exception as e:
        conn.rollback()
        print(f"\nFEHLER: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
