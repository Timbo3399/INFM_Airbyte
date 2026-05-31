"""
Szenario 4: Account-IDs nach HSO-Schema generieren (Logik aus data/js/hso_accountgenerator.js).
Aufruf: python scripts/mapping/generate_accounts.py
Schreibt user_id zurück in hso_students der source-postgres.
"""

import os, re, unicodedata, psycopg2

DB = dict(
    host=os.getenv("SOURCE_PG_HOST", "localhost"),
    port=int(os.getenv("SOURCE_PG_PORT", "5433")),
    dbname=os.getenv("SOURCE_PG_DB", "sourcedb"),
    user=os.getenv("SOURCE_PG_USER", "sourceuser"),
    password=os.getenv("SOURCE_PG_PASSWORD", "sourcepassword"),
)

UMLAUT = str.maketrans({'ä':'ae','ö':'oe','ü':'ue','ß':'ss',
                         'Ä':'ae','Ö':'oe','Ü':'ue'})

def generate_account(firstname: str, surname: str) -> str:
    raw = (firstname[:1] + surname).lower()
    raw = raw.translate(UMLAUT)
    raw = unicodedata.normalize('NFD', raw)
    raw = ''.join(c for c in raw if unicodedata.category(c) != 'Mn')
    raw = re.sub(r'[^a-z]', '', raw)
    return raw[:8]


conn = psycopg2.connect(**DB)
cur = conn.cursor()

# Spalte anlegen falls noch nicht vorhanden
cur.execute("ALTER TABLE hso_students ADD COLUMN IF NOT EXISTS user_id VARCHAR(20)")
conn.commit()

cur.execute("SELECT mtknr, firstname, surname FROM hso_students WHERE user_id IS NULL")
rows = cur.fetchall()

updated = 0
for mtknr, firstname, surname in rows:
    uid = generate_account(firstname or '', surname or '')
    if uid:
        cur.execute("UPDATE hso_students SET user_id = %s WHERE mtknr = %s", (uid, mtknr))
        updated += 1

conn.commit()
cur.close()
conn.close()
print(f"user_id für {updated} Studierende gesetzt.")
