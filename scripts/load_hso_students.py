"""
load_hso_students.py - Laedt hso_students.csv in source-postgres.

Hintergrund (Betreuer-Feedback 09.06.2026): Die CSV ist "roh wie beim Export"
und liess sich per direktem PostgreSQL-COPY nicht laden. Eine fruehere Diagnose
nahm an, die Datenzeilen haetten mehr Spalten als der Header (40). Tatsaechlich
ist die Datei pipe-getrennt und das Feld `stg_key` ist ein **gequotetes** Feld,
das selbst Pipes enthaelt (z. B. "84|LH|-|-|H|20221|2|P|V|1|"). Ein
quote-bewusster CSV-Parser (delimiter='|', quotechar='"') rekonstruiert daher
alle 5052 Datenzeilen sauber zu exakt 40 Feldern -> die Datei IST ladbar, ganz
ohne haendische Korrektur.

Damit steht hso_students auch in der relationalen Source-DB zur Verfuegung
(nicht nur ueber den File-Connector) und entsperrt Szenario 4 (Account-Mapping)
und Szenario 5 (IdM-Sync).

Konvertierungen:
  - NUL-Bytes entfernen, quote-bewusst parsen
  - mtknr + Semesterfelder sind float-formatierte Ganzzahlen ("11.000000") -> int
  - dateofbirth -> date, createdAt/updatedAt -> timestamp
  - leere/anonymisierte Felder ("") -> NULL
  - stg_key kann 27 Zeichen lang sein -> Spalte defensiv auf VARCHAR(50) weiten

Aufruf:
    python scripts/load_hso_students.py
"""

import csv
import io
import os
from datetime import date, datetime

import psycopg2
from psycopg2.extras import execute_values

DB = dict(
    host=os.getenv("SOURCE_PG_HOST", "localhost"),
    port=int(os.getenv("SOURCE_PG_PORT", "5433")),
    dbname=os.getenv("SOURCE_PG_DB", "sourcedb"),
    user=os.getenv("SOURCE_PG_USER", "sourceuser"),
    password=os.getenv("SOURCE_PG_PASSWORD", "sourcepassword"),
)

# Spaltenreihenfolge == Header der CSV == Tabelle (fakultaet/createdat klein).
COLS = [
    "mtknr", "firstname", "surname", "allfirstnames", "academicTitle",
    "dateofbirth", "birthcity", "country", "gender", "nationalityId",
    "secondNationality", "accounts", "hochschulEmail", "privateEmail", "phone",
    "currentSem", "immaDat", "exmaDat", "exmaReason", "studyStatus",
    "universitysemester", "kollegsemester", "practicalsemester", "leavesemester",
    "stg_key", "stg", "fach", "degree", "poversion", "fakultaet", "stort",
    "studentstatus", "studysemester", "curriculumsemester", "progressvector",
    "subjectfocus", "h1_syncVers", "dbversion", "createdat", "updatedat",
]

INT_IDX = {0}                                   # mtknr
FLOATINT_IDX = {20, 21, 22, 23, 32, 33}         # *_semester ("11.000000" -> 11)
DATE_IDX = {5}                                   # dateofbirth
TS_IDX = {38, 39}                                # createdat, updatedat

DDL_HSO_STUDENTS = """
CREATE TABLE IF NOT EXISTS hso_students (
    mtknr             INTEGER,
    firstname         VARCHAR(100),
    surname           VARCHAR(100),
    allfirstnames     VARCHAR(100),
    academicTitle     VARCHAR(20),
    dateofbirth       DATE,
    birthcity         VARCHAR(100),
    country           VARCHAR(5),
    gender            CHAR(1),
    nationalityId     VARCHAR(5),
    secondNationality VARCHAR(5),
    accounts          VARCHAR(255),
    hochschulEmail    VARCHAR(255),
    privateEmail      VARCHAR(255),
    phone             VARCHAR(50),
    currentSem        VARCHAR(20),
    immaDat           VARCHAR(20),
    exmaDat           VARCHAR(20),
    exmaReason        VARCHAR(100),
    studyStatus       VARCHAR(50),
    universitysemester INTEGER,
    kollegsemester    INTEGER,
    practicalsemester INTEGER,
    leavesemester     INTEGER,
    stg_key           VARCHAR(50),
    stg               VARCHAR(20),
    fach              VARCHAR(10),
    degree            VARCHAR(10),
    poversion         VARCHAR(20),
    fakultaet         VARCHAR(100),
    stort             VARCHAR(20),
    studentstatus     VARCHAR(50),
    studysemester     INTEGER,
    curriculumsemester INTEGER,
    progressvector    VARCHAR(255),
    subjectfocus      VARCHAR(255),
    h1_syncVers       VARCHAR(50),
    dbversion         VARCHAR(50),
    createdat         TIMESTAMP,
    updatedat         TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_hso_students_updatedat ON hso_students (updatedat);
"""


def clean(v):
    if v is None:
        return None
    v = v.strip()
    return v if v != "" else None


def to_int(v):
    v = clean(v)
    if v is None:
        return None
    try:
        return int(float(v))         # toleriert "176594" und "11.000000"
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


def to_ts(v):
    v = clean(v)
    if v is None:
        return None
    try:
        return datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def convert(idx, v):
    if idx in INT_IDX or idx in FLOATINT_IDX:
        return to_int(v)
    if idx in DATE_IDX:
        return to_date(v)
    if idx in TS_IDX:
        return to_ts(v)
    return clean(v)


def read_rows(path: str) -> list:
    with open(path, "rb") as f:
        text = f.read().replace(b"\x00", b"").decode("utf-8", errors="replace")
    return list(csv.reader(io.StringIO(text), delimiter="|", quotechar='"'))


def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "sql", "source", "data", "hso_students.csv")

    print(f"Verbinde mit source-postgres ({DB['host']}:{DB['port']})...")
    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        print("\nhso_students.csv laden...")
        cur.execute(DDL_HSO_STUDENTS)
        # Defensiv: falls die Tabelle aus einem aelteren 00_tables.sql noch
        # stg_key VARCHAR(20) hat, hier weiten (Werte bis 27 Zeichen).
        cur.execute("ALTER TABLE hso_students ALTER COLUMN stg_key TYPE VARCHAR(50)")
        cur.execute("TRUNCATE TABLE hso_students")

        rows = read_rows(path)
        if rows and rows[0] and rows[0][0].strip().strip('"') == "mtknr":
            rows = rows[1:]                       # Header ueberspringen

        data, skipped = [], 0
        for r in rows:
            if not r or all((c or "").strip() == "" for c in r):
                continue
            if len(r) != len(COLS):
                skipped += 1
                continue
            data.append(tuple(convert(i, r[i]) for i in range(len(COLS))))

        execute_values(cur, f"""
            INSERT INTO hso_students ({', '.join(COLS)})
            VALUES %s
        """, data, page_size=1000)

        conn.commit()
        print(f"    {len(data)} Zeilen in hso_students eingefuegt"
              + (f" ({skipped} mit abweichender Spaltenzahl uebersprungen)."
                 if skipped else "."))
        print("\nFertig. hso_students ist in source-postgres verfuegbar.")

    except Exception as e:
        conn.rollback()
        print(f"\nFEHLER: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
