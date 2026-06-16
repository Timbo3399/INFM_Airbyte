"""
load_fm_stamm.py - Laedt die Raumstammdaten in source-postgres.

Quelle: sql/source/data/rooms.xltx (Excel-Vorlage aus data.zip, Sheet "stamm_*").
Die 17 Spalten der Tabelle entsprechen 1:1 den Spalten des Sheets:
    geb_nr, ges_nr, raumid, raumnr, flaeche, rna_nr, bez, nutzer_nr, datum,
    kost_nr, traeger_nr, fkt_nr, kfa_nr, bem, raumco, text_bez, kurz_bez

Diese Tabelle ist die Systemtabelle fuer Raeume (Facility Management, Szenario 2)
und wird laut Betreuer-Feedback (09.06.2026) als Teil des ETL-Mappings aus der
rooms-Datei befuellt.

Sonderfaelle:
  - Werte sind stark mit Leerzeichen aufgefuellt ("A013    ")     -> trimmen
  - vereinzelt doppelt-kodierte Umlaute ("SanitÃ¤r...") -> demojibake
  - flaeche kommt als String ("17.00")                            -> Decimal
  - datum kommt als Excel-Datum                                   -> date
  - Primaerschluessel (geb_nr, ges_nr, raumid): doppelte Zeilen werden
    (defensiv) dedupliziert, damit der INSERT nicht am PK scheitert.

Aufruf:
    python scripts/load_fm_stamm.py

Voraussetzungen:
    pip install psycopg2-binary openpyxl
    DB-Stack laeuft (docker compose up -d)
"""

import os
from datetime import date, datetime

import psycopg2
from psycopg2.extras import execute_values

try:
    import openpyxl
except ImportError:
    raise SystemExit(
        "openpyxl fehlt. Installieren mit:  pip install openpyxl"
    )

DB = dict(
    host=os.getenv("SOURCE_PG_HOST", "localhost"),
    port=int(os.getenv("SOURCE_PG_PORT", "5433")),
    dbname=os.getenv("SOURCE_PG_DB", "sourcedb"),
    user=os.getenv("SOURCE_PG_USER", "sourceuser"),
    password=os.getenv("SOURCE_PG_PASSWORD", "sourcepassword"),
)

DDL_FM_STAMM = """
CREATE TABLE IF NOT EXISTS fm_stamm (
    db_einfuegemarke  VARCHAR(10),
    geb_nr            VARCHAR(10)  NOT NULL,
    ges_nr            VARCHAR(10)  NOT NULL,
    raumid            VARCHAR(20)  NOT NULL,
    raumnr            VARCHAR(20),
    flaeche           DECIMAL(14,2),
    rna_nr            VARCHAR(10),
    bez               VARCHAR(120),
    nutzer_nr         VARCHAR(20),
    datum             DATE,
    kost_nr           VARCHAR(20),
    traeger_nr        VARCHAR(20),
    fkt_nr            VARCHAR(10),
    kfa_nr            VARCHAR(10),
    bem               VARCHAR(255),
    raumco            VARCHAR(20),
    text_bez          VARCHAR(255),
    kurz_bez          VARCHAR(30),
    PRIMARY KEY (geb_nr, ges_nr, raumid)
);
"""

# Spaltenreihenfolge des Sheets (== Reihenfolge in der Tabelle ohne db_einfuegemarke)
COLS = ["geb_nr", "ges_nr", "raumid", "raumnr", "flaeche", "rna_nr", "bez",
        "nutzer_nr", "datum", "kost_nr", "traeger_nr", "fkt_nr", "kfa_nr",
        "bem", "raumco", "text_bez", "kurz_bez"]


def demojibake(s):
    """Repariert doppelt-kodierte UTF-8-Umlaute (z. B. 'GebÃ¤ude')."""
    if not isinstance(s, str) or ("Ã" not in s and "Â" not in s):
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def clean_str(v):
    """Excel liefert int/float/str/None; auf getrimmten String oder None bringen."""
    if v is None:
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)               # 101.0 -> "101" statt "101.0"
    s = demojibake(str(v).strip())
    return s if s != "" else None


def to_decimal(v):
    if v is None:
        return None
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return None


def to_date(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def read_rows(path: str):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    header = [str(c).strip() if c is not None else "" for c in rows[0]]
    assert header[:len(COLS)] == COLS, f"Unerwartete Spalten: {header}"
    return rows[1:]


def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "sql", "source", "data", "rooms.xltx")

    print(f"Verbinde mit source-postgres ({DB['host']}:{DB['port']})...")
    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        print("\nfm_stamm aus rooms.xltx laden...")
        cur.execute(DDL_FM_STAMM)
        cur.execute("TRUNCATE TABLE fm_stamm")

        data, seen, dups, skipped = [], set(), 0, 0
        for raw in read_rows(path):
            if raw is None or all(c is None for c in raw):
                continue
            vals = {COLS[i]: (raw[i] if i < len(raw) else None)
                    for i in range(len(COLS))}

            geb_nr = clean_str(vals["geb_nr"])
            ges_nr = clean_str(vals["ges_nr"])
            raumid = clean_str(vals["raumid"])
            if geb_nr is None or ges_nr is None or raumid is None:
                skipped += 1                 # PK-Teil fehlt
                continue
            pk = (geb_nr, ges_nr, raumid)
            if pk in seen:
                dups += 1
                continue
            seen.add(pk)

            data.append((
                None,                        # db_einfuegemarke (in Quelle nicht vorhanden)
                geb_nr, ges_nr, raumid,
                clean_str(vals["raumnr"]),
                to_decimal(vals["flaeche"]),
                clean_str(vals["rna_nr"]),
                clean_str(vals["bez"]),
                clean_str(vals["nutzer_nr"]),
                to_date(vals["datum"]),
                clean_str(vals["kost_nr"]),
                clean_str(vals["traeger_nr"]),
                clean_str(vals["fkt_nr"]),
                clean_str(vals["kfa_nr"]),
                clean_str(vals["bem"]),
                clean_str(vals["raumco"]),
                clean_str(vals["text_bez"]),
                clean_str(vals["kurz_bez"]),
            ))

        execute_values(cur, """
            INSERT INTO fm_stamm
                (db_einfuegemarke, geb_nr, ges_nr, raumid, raumnr, flaeche, rna_nr,
                 bez, nutzer_nr, datum, kost_nr, traeger_nr, fkt_nr, kfa_nr, bem,
                 raumco, text_bez, kurz_bez)
            VALUES %s
        """, data, page_size=1000)

        conn.commit()
        msg = f"    {len(data)} Zeilen in fm_stamm eingefuegt"
        extra = []
        if dups:
            extra.append(f"{dups} PK-Duplikate uebersprungen")
        if skipped:
            extra.append(f"{skipped} ohne Schluessel uebersprungen")
        print(msg + (f" ({', '.join(extra)})." if extra else "."))
        print("\nFertig. fm_stamm ist in source-postgres verfuegbar.")

    except Exception as e:
        conn.rollback()
        print(f"\nFEHLER: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
