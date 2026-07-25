"""
Szenario 5, Schritt 1: die View hso_user in source-postgres anlegen.

Fuehrt sql/source/views/hso_user.sql aus. Die View fasst hso_students und
hso_personal zu einer gemeinsamen IdM-Sicht zusammen, weil Airbyte selbst keine
zwei Streams in eine Zieltabelle vereinigen kann.

Voraussetzungen, beide zwingend vorher:
  * fill_random_names.py und generate_accounts.py, sonst ist die View leer
    (sie filtert auf gesetzte user_id)
  * scripts/images/load_images.py, denn die View liest hso_images fuer die
    Bildzuordnung. CREATE OR REPLACE VIEW prueft die referenzierten Tabellen
    sofort, ein fehlendes hso_images bricht hier ab mit
    'relation "hso_images" does not exist'.

Aufruf:
    python scripts/mapping/create_hso_user_view.py
"""

import os

import psycopg2

from generate_accounts import DB

VIEW_SQL = os.path.join("sql", "source", "views", "hso_user.sql")


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
        cur.execute("SELECT count(*), count(DISTINCT user_id) FROM hso_user")
        gesamt, eindeutig = cur.fetchone()
        conn.commit()

        print(f"    View hso_user angelegt: {gesamt} Zeilen, {eindeutig} eindeutige user_id")
        if gesamt == 0:
            print("    Achtung: keine Zeilen. Zuerst fill_random_names.py und"
                  " generate_accounts.py laufen lassen.")
        elif gesamt != eindeutig:
            print(f"    Achtung: {gesamt - eindeutig} doppelte user_id."
                  " Der Dedup-Sync wuerde sie zusammenfassen.")
        else:
            print("    user_id ist eindeutig, taugt also als Primaerschluessel.")
    except Exception as e:
        conn.rollback()
        print(f"\nFEHLER: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
