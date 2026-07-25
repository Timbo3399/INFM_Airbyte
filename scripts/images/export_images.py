"""
Szenario 3b: die Bilder wieder aus der Datenbank holen und als <ID>.png ablegen.

Gegenstueck zu load_images.py. Der Dateiname folgt der Aufgabenstellung
(<ID>.png); picsum liefert JPEG-Daten, die Endung sagt also nichts ueber das
Format aus.

Gelesen wird in Haeppchen. Ein fetchall ueber alle BLOBs zoege den kompletten
Bildbestand in den Speicher, und der waechst mit jedem Durchlauf.

Aufruf:
    python scripts/images/export_images.py
"""

import os
import sys

import psycopg2

DB = dict(
    host=os.getenv("SOURCE_PG_HOST", "localhost"),
    port=int(os.getenv("SOURCE_PG_PORT", "5433")),
    dbname=os.getenv("SOURCE_PG_DB", "sourcedb"),
    user=os.getenv("SOURCE_PG_USER", "sourceuser"),
    password=os.getenv("SOURCE_PG_PASSWORD", "sourcepassword"),
)

BATCH = 100


def ausgabe_verzeichnis() -> str:
    """<repo>/data/images, unabhaengig vom aktuellen Arbeitsverzeichnis."""
    basis = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(basis, "data", "images")


def ziel_pfad(verzeichnis: str, ext_id: str) -> str:
    return os.path.join(verzeichnis, f"{ext_id}.png")


def schreibe_bild(pfad: str, daten) -> None:
    """psycopg2 liefert BYTEA als memoryview, deshalb der Umweg ueber bytes()."""
    with open(pfad, "wb") as f:
        f.write(bytes(daten))


def batches(cur, groesse: int = BATCH):
    """Zeilen haeppchenweise nachladen, statt alles auf einmal zu holen."""
    while True:
        haeppchen = cur.fetchmany(groesse)
        if not haeppchen:
            return
        for zeile in haeppchen:
            yield zeile


def main() -> int:
    verzeichnis = ausgabe_verzeichnis()
    os.makedirs(verzeichnis, exist_ok=True)

    print(f"Verbinde mit source-postgres ({DB['host']}:{DB['port']})...")
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    try:
        cur.execute("SELECT ext_id, data FROM hso_images ORDER BY image_id")
        anzahl = bytes_gesamt = 0
        for ext_id, daten in batches(cur):
            if daten is None:
                continue
            schreibe_bild(ziel_pfad(verzeichnis, ext_id), daten)
            anzahl += 1
            bytes_gesamt += len(daten)

        print(f"Export abgeschlossen: {anzahl} Bilder"
              f" ({bytes_gesamt} Bytes) nach {verzeichnis}")
        return 0
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
