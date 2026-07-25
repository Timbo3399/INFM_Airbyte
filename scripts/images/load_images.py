"""
Szenario 3a: >1.000 Bilder von picsum.photos abrufen und als BLOB in source-postgres speichern.
Aufruf: python scripts/images/load_images.py
Voraussetzung: pip install requests psycopg2-binary
"""

import os, requests, psycopg2

DB = dict(
    host=os.getenv("SOURCE_PG_HOST", "localhost"),
    port=int(os.getenv("SOURCE_PG_PORT", "5433")),
    dbname=os.getenv("SOURCE_PG_DB", "sourcedb"),
    user=os.getenv("SOURCE_PG_USER", "sourceuser"),
    password=os.getenv("SOURCE_PG_PASSWORD", "sourcepassword"),
)

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS hso_images (
    image_id   SERIAL PRIMARY KEY,
    ext_id     VARCHAR(50) UNIQUE,
    data       BYTEA,
    created_at TIMESTAMP DEFAULT NOW()
);
"""

conn = psycopg2.connect(**DB)
cur = conn.cursor()
cur.execute(CREATE_TABLE)
conn.commit()

# /seed/<seed> liefert deterministisch ein Bild und antwortet IMMER mit 200 - anders als
# /id/<n>, das fuer viele IDs 404 liefert (-> man landete deutlich unter 1000 Bildern).
TARGET = 1100  # >1.000 (Szenario 3a)

total = 0
for i in range(1, TARGET + 1):
    try:
        resp = requests.get(f"https://picsum.photos/seed/hso{i}/200/200", timeout=15)
        if resp.status_code == 200:
            cur.execute(
                "INSERT INTO hso_images (ext_id, data) VALUES (%s, %s) ON CONFLICT (ext_id) DO NOTHING",
                (str(i), psycopg2.Binary(resp.content)),
            )
            total += cur.rowcount   # nur tatsaechlich eingefuegte Zeilen zaehlen (nicht Versuche)
    except Exception as e:
        print(f"  Bild {i} übersprungen: {e}")

    if i % 100 == 0:
        conn.commit()
        print(f"{i}/{TARGET} verarbeitet ({total} gespeichert)...")

conn.commit()
cur.close()
conn.close()
print(f"\nFertig: {total} Bilder in hso_images gespeichert.")
