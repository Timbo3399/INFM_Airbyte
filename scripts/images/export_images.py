"""
Szenario 3b: Bilder aus DB auslesen und als <ID>.png-Dateien exportieren.
Aufruf: python scripts/images/export_images.py
"""

import os, psycopg2

DB = dict(
    host=os.getenv("SOURCE_PG_HOST", "localhost"),
    port=int(os.getenv("SOURCE_PG_PORT", "5433")),
    dbname=os.getenv("SOURCE_PG_DB", "sourcedb"),
    user=os.getenv("SOURCE_PG_USER", "sourceuser"),
    password=os.getenv("SOURCE_PG_PASSWORD", "sourcepassword"),
)

# Ausgabeverzeichnis an der Repo-Wurzel verankern (scripts/images/ -> .. -> ..), damit der
# Export unabhaengig vom aktuellen Arbeitsverzeichnis immer nach <repo>/data/images schreibt.
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.join(BASE, "data", "images")
os.makedirs(OUTPUT_DIR, exist_ok=True)

conn = psycopg2.connect(**DB)
cur = conn.cursor()
cur.execute("SELECT ext_id, data FROM hso_images ORDER BY image_id")

count = 0
for ext_id, data in cur.fetchall():
    path = os.path.join(OUTPUT_DIR, f"{ext_id}.png")
    with open(path, "wb") as f:
        f.write(bytes(data))
    count += 1

cur.close()
conn.close()
print(f"Export abgeschlossen: {count} Bilder nach {OUTPUT_DIR}/")
