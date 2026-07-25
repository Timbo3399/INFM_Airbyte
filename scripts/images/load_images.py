"""
Szenario 3a: ueber 1.000 Bilder von picsum.photos holen und als BLOB (BYTEA) in
source-postgres ablegen.

Fehlerbehandlung, und warum sie hier getrennt sein muss:
  * Ein nicht erreichbares Bild ist ein Einzelfall. Ueberspringen, weitermachen.
  * Ein Datenbankfehler ist es nicht. psycopg2 bricht danach die Transaktion ab,
    jedes weitere execute scheitert mit "current transaction is aborted".
Frueher fing ein einziges except beides ab. Der Zaehler lief weiter, am Ende
stand eine Erfolgsmeldung ueber einer halbleeren Tabelle. Jetzt schluckt
fetch_image nur Netz- und HTTP-Fehler, store_image reicht DB-Fehler durch.

Aufruf:
    python scripts/images/load_images.py            # 1.100 Bilder
    python scripts/images/load_images.py 50         # weniger, zum Ausprobieren

Voraussetzung: pip install requests psycopg2-binary
"""

import os
import sys

import psycopg2
import requests

DB = dict(
    host=os.getenv("SOURCE_PG_HOST", "localhost"),
    port=int(os.getenv("SOURCE_PG_PORT", "5433")),
    dbname=os.getenv("SOURCE_PG_DB", "sourcedb"),
    user=os.getenv("SOURCE_PG_USER", "sourceuser"),
    password=os.getenv("SOURCE_PG_PASSWORD", "sourcepassword"),
)

TARGET = 1100          # ueber 1.000, wie in der Aufgabenstellung gefordert
GROESSE = 200
TIMEOUT = 15
COMMIT_ALLE = 100

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS hso_images (
    image_id   SERIAL PRIMARY KEY,
    ext_id     VARCHAR(50) UNIQUE,
    data       BYTEA,
    created_at TIMESTAMP DEFAULT NOW()
);
"""

INSERT = """
INSERT INTO hso_images (ext_id, data) VALUES (%s, %s)
ON CONFLICT (ext_id) DO NOTHING
"""


def seed_url(index: int, groesse: int = GROESSE) -> str:
    """Seed-URL statt /id/<n>.

    /id/<n> liefert fuer viele Nummern 404, damit kamen wir nie ueber 1.000
    Bilder. /seed/<wort> antwortet immer mit 200 und liefert zum selben Seed
    reproduzierbar dasselbe Bild.
    """
    return f"https://picsum.photos/seed/hso{index}/{groesse}/{groesse}"


def fetch_image(session, index: int, timeout: int = TIMEOUT):
    """Bilddaten oder None. Netz- und HTTP-Fehler enden hier."""
    try:
        antwort = session.get(seed_url(index), timeout=timeout)
    except Exception as e:                      # Netzfehler: ueberspringen
        print(f"    Bild {index} uebersprungen: {e}")
        return None
    if antwort.status_code != 200:
        print(f"    Bild {index} uebersprungen: HTTP {antwort.status_code}")
        return None
    return antwort.content


def store_image(cur, ext_id: str, daten: bytes) -> int:
    """Speichert ein Bild und liefert die Zahl der eingefuegten Zeilen.

    Faengt bewusst nichts ab: ein Datenbankfehler soll den Lauf beenden, nicht
    stillschweigend jede weitere Zeile verschlucken.
    """
    cur.execute(INSERT, (ext_id, psycopg2.Binary(daten)))
    return cur.rowcount


def main(ziel: int = TARGET) -> int:
    print(f"Verbinde mit source-postgres ({DB['host']}:{DB['port']})...")
    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor()

    gespeichert = uebersprungen = 0
    try:
        cur.execute(CREATE_TABLE)
        conn.commit()

        print(f"\nLade {ziel} Bilder von picsum.photos...")
        with requests.Session() as session:     # Verbindung wiederverwenden
            for i in range(1, ziel + 1):
                daten = fetch_image(session, i)
                if daten is None:
                    uebersprungen += 1
                    continue
                gespeichert += store_image(cur, str(i), daten)

                if i % COMMIT_ALLE == 0:
                    conn.commit()
                    print(f"    {i}/{ziel} verarbeitet ({gespeichert} gespeichert)")

        conn.commit()
        print(f"\nFertig. {gespeichert} Bilder in hso_images"
              + (f", {uebersprungen} uebersprungen." if uebersprungen else "."))
        return 0

    except Exception as e:
        conn.rollback()
        print(f"\nFEHLER nach {gespeichert} gespeicherten Bildern: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    ziel = int(sys.argv[1]) if len(sys.argv) > 1 else TARGET
    sys.exit(main(ziel))
