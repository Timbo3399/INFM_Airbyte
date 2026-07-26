"""
Szenario 4, Schritt 3: die Account-Sichten in source-postgres anlegen.

Fuehrt sql/source/views/hso_accounts.sql aus. Die beiden Views hso_student_accounts
und hso_personal_accounts sind die Quellen fuer je eine Zieltabelle in
dest-postgres. Damit landet das Ergebnis des Account-Generators dort, wo die
Aufgabenstellung es verlangt: in neuen Tabellen, getrennt nach Gruppe.

Voraussetzung: fill_random_names.py und generate_accounts.py sind gelaufen. Sonst
sind die Views leer, denn sie filtern auf gesetzte user_id.

Aufruf:
    python scripts/mapping/create_account_views.py
"""

import os

import psycopg2

from generate_accounts import DB

VIEW_SQL = os.path.join("sql", "source", "views", "hso_accounts.sql")

VIEWS = ("hso_student_accounts", "hso_personal_accounts")


def sql_pfad(wurzel: str) -> str:
    return os.path.join(wurzel, VIEW_SQL)


def main():
    wurzel = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    pfad = sql_pfad(wurzel)
    if not os.path.exists(pfad):
        raise SystemExit(f"SQL-Datei nicht gefunden: {pfad}")

    with open(pfad, encoding="utf-8") as f:
        ddl = f.read()

    print(f"Verbinde mit source-postgres ({DB['host']}:{DB['port']})...")
    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor()
    try:
        cur.execute(ddl)

        leer = []
        for view in VIEWS:
            cur.execute(f"SELECT count(*), count(DISTINCT user_id) FROM {view}")
            gesamt, eindeutig = cur.fetchone()
            print(f"    View {view}: {gesamt} Zeilen,"
                  f" {eindeutig} eindeutige user_id")
            if gesamt == 0:
                leer.append(view)
            elif gesamt != eindeutig:
                print(f"    Achtung: {gesamt - eindeutig} doppelte user_id in {view}.")
        conn.commit()

        if leer:
            print("    Achtung: keine Zeilen in " + ", ".join(leer)
                  + ". Zuerst fill_random_names.py und generate_accounts.py"
                    " laufen lassen.")
        else:
            print("\nFertig. Beide Account-Sichten stehen in source-postgres.")
    except Exception as e:
        conn.rollback()
        print(f"\nFEHLER: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
