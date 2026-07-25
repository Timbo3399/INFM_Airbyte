"""
Szenario 4, Schritt 2: Account-IDs nach HSO-Schema generieren.

Logik portiert aus data/js/hso_accountgenerator.js (Referenz-Artefakt, wird
nicht ausgefuehrt). Die dortige Spec lautet:

    account = maxLength-8(Vorname[0] + Nachname + (Anzahlaccounts_mit_dem_Schema + 1))

Der Zaehler in Klammern ist die Kollisionsbehandlung: faellt ein Account mit
einem bestehenden zusammen, wird hochgezaehlt. Weil die Laengenbegrenzung fuer
den GESAMTEN Namen gilt, wird die Basis dafuer weiter gekuerzt
("mmusterm" belegt -> "mmuster2", ab dem zehnten -> "mmuste10").

Voraussetzung: die Namensfelder sind befuellt. In den anonymisierten Quelldaten
sind firstname/surname (hso_students) und vorname/nachname (hso_personal) leer,
deshalb zuerst fill_random_names.py laufen lassen.

Geschrieben werden user_id und die daraus abgeleitete Hochschul-E-Mail, in
hso_students und hso_personal. updatedat wird mitgezogen, damit ein
Incremental-Sync ueber den Cursor updatedat die Aenderung ueberhaupt sieht
(Szenario 5).

Das Skript ist idempotent: bereits vergebene Accounts bleiben unangetastet, ein
zweiter Lauf vergibt nichts neu. Die Namen aus Schritt 1 sind reproduzierbar,
die Accounts sind es nur bedingt: welcher Zaehler an einen Namen geht, haengt
davon ab, was zu diesem Zeitpunkt schon vergeben war. Nach einem Teil-Reset kann
dieselbe Person also einen anderen Zaehler bekommen. Das entspricht der Spec
(wer zuerst kommt, mahlt zuerst) und ist auch im echten IdM so.

Aufruf:
    python scripts/mapping/generate_accounts.py
"""

import os
import re
import unicodedata

import psycopg2
from psycopg2.extras import execute_values

DB = dict(
    host=os.getenv("SOURCE_PG_HOST", "localhost"),
    port=int(os.getenv("SOURCE_PG_PORT", "5433")),
    dbname=os.getenv("SOURCE_PG_DB", "sourcedb"),
    user=os.getenv("SOURCE_PG_USER", "sourceuser"),
    password=os.getenv("SOURCE_PG_PASSWORD", "sourcepassword"),
)

# Kleinschreibung laeuft vor der Ersetzung, Grossbuchstaben braucht die Tabelle nicht.
UMLAUT = str.maketrans({'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss'})

MAX_LEN = 8
STUD_DOMAIN = "stud.hs-offenburg.de"
PERSONAL_DOMAIN = "hs-offenburg.de"


def normalize_name(value: str) -> str:
    """Kleinschreiben, Umlaute ersetzen, Akzente entfernen, Rest auf a-z reduzieren."""
    raw = (value or "").lower().translate(UMLAUT)
    raw = unicodedata.normalize('NFD', raw)
    raw = ''.join(c for c in raw if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z]', '', raw)


def generate_account(firstname: str, surname: str, taken=None) -> str:
    """Account nach HSO-Schema. `taken` enthaelt bereits vergebene Accounts."""
    base = normalize_name((firstname or "")[:1] + (surname or ""))
    if not base:
        return ""

    candidate = base[:MAX_LEN]
    if taken is None or candidate not in taken:
        return candidate

    n = 2
    while True:
        suffix = str(n)
        candidate = base[:MAX_LEN - len(suffix)] + suffix
        if candidate not in taken:
            return candidate
        n += 1


def hochschul_email(account: str, domain: str):
    if not account:
        return None
    return f"{account}@{domain}"


def hinweis_wenn_nichts_zu_tun(zeilen_ohne_namen: int) -> str:
    """Kein Kandidat gefunden: entweder fehlen die Namen, oder alles ist vergeben."""
    if zeilen_ohne_namen:
        return (f"Nichts zu tun: {zeilen_ohne_namen} Zeilen haben keine Namen."
                " Zuerst: python scripts/mapping/fill_random_names.py")
    return "Nichts zu tun, alle Accounts sind bereits vergeben."


def assign(rows, taken: set, domain: str) -> list:
    """(key, vorname, nachname) -> (key, account, email), kollisionsfrei."""
    out = []
    for key, vorname, nachname in rows:
        account = generate_account(vorname or "", nachname or "", taken)
        if not account:
            continue
        taken.add(account)
        out.append((key, account, hochschul_email(account, domain)))
    return out


def main():
    print(f"Verbinde mit source-postgres ({DB['host']}:{DB['port']})...")
    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        cur.execute("ALTER TABLE hso_students ADD COLUMN IF NOT EXISTS user_id VARCHAR(20)")

        # Bereits vergebene Accounts aus BEIDEN Tabellen einsammeln: Studierende und
        # Personal teilen sich in Szenario 5 die Tabelle hso_user mit user_id als PK.
        cur.execute("""
            SELECT user_id FROM hso_students WHERE user_id IS NOT NULL
            UNION
            SELECT user_id FROM hso_personal WHERE user_id IS NOT NULL AND user_id <> ''
        """)
        taken = {r[0] for r in cur.fetchall()}
        print(f"    {len(taken)} bereits vergebene Accounts eingelesen.")

        print("\n[1/2] hso_students...")
        cur.execute("""
            SELECT mtknr, firstname, surname FROM hso_students
            WHERE user_id IS NULL AND COALESCE(surname, '') <> ''
            ORDER BY mtknr
        """)
        students = assign(cur.fetchall(), taken, STUD_DOMAIN)
        if students:
            execute_values(cur, """
                UPDATE hso_students AS s
                SET user_id = v.user_id,
                    hochschulemail = v.email,
                    updatedat = NOW()
                FROM (VALUES %s) AS v(mtknr, user_id, email)
                WHERE s.mtknr = v.mtknr
            """, students, template="(%s::integer, %s, %s)", page_size=1000)
        print(f"    {len(students)} user_id gesetzt.")

        print("\n[2/2] hso_personal...")
        cur.execute("""
            SELECT id, vorname, nachname FROM hso_personal
            WHERE COALESCE(user_id, '') = '' AND COALESCE(nachname, '') <> ''
            ORDER BY id
        """)
        personal = assign(cur.fetchall(), taken, PERSONAL_DOMAIN)
        if personal:
            execute_values(cur, """
                UPDATE hso_personal AS p
                SET user_id = v.user_id,
                    hso_email = v.email,
                    updatedat = NOW()
                FROM (VALUES %s) AS v(id, user_id, email)
                WHERE p.id = v.id
            """, personal, template="(%s::integer, %s, %s)", page_size=1000)
        print(f"    {len(personal)} user_id gesetzt.")

        conn.commit()

        total = len(students) + len(personal)
        if total == 0:
            cur.execute("""
                SELECT (SELECT count(*) FROM hso_students  WHERE COALESCE(surname, '')  = '')
                     + (SELECT count(*) FROM hso_personal WHERE COALESCE(nachname, '') = '')
            """)
            print("\n" + hinweis_wenn_nichts_zu_tun(cur.fetchone()[0]))
        else:
            suffixe = sum(1 for _, a, _ in students + personal if a[-1].isdigit())
            print(f"\nFertig. {total} Accounts vergeben, alle eindeutig.")
            print(f"    davon {suffixe} mit Kollisionszaehler"
                  f" ({suffixe * 100 // total} Prozent, abhaengig von der Groesse"
                  f" des Namenspools in fill_random_names.py).")

    except Exception as e:
        conn.rollback()
        print(f"\nFEHLER: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
