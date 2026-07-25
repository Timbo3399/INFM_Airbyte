"""
Szenario 4, Schritt 1: anonymisierte Daten mit Zufallsnamen befuellen.

Die Quelldaten sind so anonymisiert, dass die Namensfelder leer sind:
firstname/surname/allfirstnames in allen 5.052 Zeilen von hso_students,
vorname/nachname in allen 870 Zeilen von hso_personal. Ohne Namen erzeugt der
Account-Generator (Schritt 2) fuer keine einzige Zeile eine user_id, und
Szenario 5 haette in hso_user einen leeren Primaerschluessel.

Die Aufgabenstellung nennt dafuer generatedata.com. Wir erzeugen die Namen
stattdessen lokal: kein Netzzugriff, keine Ratenbegrenzung, und vor allem
deterministisch. Der Name haengt nur am Schluessel der Zeile (mtknr bzw. id),
ein zweiter Lauf liefert also dieselben Namen und schreibt nichts um.

Der Namenspool enthaelt bewusst Umlaute und Akzente, damit die
Transliteration im Account-Generator an echten Daten laeuft.

Zur Groesse des Pools: 50 Vor- mal 50 Nachnamen ergeben 2.500 Kombinationen
fuer 5.922 Personen. Namen wiederholen sich also haeufig, und gut 83 Prozent
der Accounts bekommen einen Kollisionszaehler. Das ist gewollt: so laeuft die
HSOG-Kollisionsregel an echtem Datenvolumen durch, statt nur in den Unit-Tests.
Wer realistischere Verteilungen braucht, vergroessert die beiden Listen unten,
das aendert an der Logik nichts.

Aufruf:
    python scripts/mapping/fill_random_names.py
"""

import hashlib
import random

import psycopg2
from psycopg2.extras import execute_values

# Verbindungsparameter und Namens-Normalisierung teilen wir uns mit dem
# Account-Generator, statt sie ein achtes Mal zu kopieren.
from generate_accounts import DB, normalize_name

PRIVATE_DOMAIN = "example.org"

FIRST_NAMES = [
    "Alexander", "Andrea", "Anna", "Benedikt", "Björn", "Carla", "Christoph",
    "Clara", "Daniel", "David", "Elena", "Elias", "Emilia", "Fabian", "Felix",
    "Franziska", "Greta", "Hannah", "Hendrik", "Ingrid", "Jana", "Jens",
    "Johanna", "Jonas", "Jörg", "Julia", "Katharina", "Kilian", "Lara",
    "Leon", "Lena", "Lukas", "Marie", "Markus", "Mia", "Miriam", "Niklas",
    "Nora", "Oliver", "Paul", "Pia", "René", "Sarah", "Sebastian", "Sofia",
    "Sören", "Stefan", "Theresa", "Tobias", "Vincent",
]

LAST_NAMES = [
    "Bauer", "Becker", "Böhm", "Brandt", "Braun", "Dietrich", "Engel",
    "Fischer", "Frank", "Franke", "Gruber", "Günther", "Haas", "Hartmann",
    "Herrmann", "Hoffmann", "Jäger", "Kaiser", "Keller", "Klein", "Koch",
    "König", "Krämer", "Krause", "Krüger", "Lang", "Lehmann", "Lorenz",
    "Ludwig", "Maier", "Müller", "Neumann", "Peters", "Pfeiffer", "Richter",
    "Roth", "Schäfer", "Schmidt", "Schneider", "Schröder", "Schulz",
    "Schwarz", "Seidel", "Stein", "Vogel", "Weber", "Werner", "Wolf",
    "Zimmermann", "Ziegler",
]


def _seed(key) -> int:
    """Stabiler Seed pro Zeile. hash() faellt aus, das ist pro Prozess gesalzen."""
    digest = hashlib.md5(str(key).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def generate_person(key):
    """Deterministischer (Vorname, Nachname) zum Zeilenschluessel."""
    rnd = random.Random(_seed(key))
    return rnd.choice(FIRST_NAMES), rnd.choice(LAST_NAMES)


def private_email(vorname: str, nachname: str):
    """vorname.nachname@example.org, transliteriert wie die Hochschul-Adresse."""
    links, rechts = normalize_name(vorname), normalize_name(nachname)
    if not links or not rechts:
        return None
    return f"{links}.{rechts}@{PRIVATE_DOMAIN}"


def main():
    print(f"Verbinde mit source-postgres ({DB['host']}:{DB['port']})...")
    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        print("\n[1/2] hso_students...")
        cur.execute("""
            SELECT mtknr FROM hso_students
            WHERE COALESCE(surname, '') = '' ORDER BY mtknr
        """)
        rows = []
        for (mtknr,) in cur.fetchall():
            vorname, nachname = generate_person(mtknr)
            rows.append((mtknr, vorname, nachname, private_email(vorname, nachname)))
        if rows:
            execute_values(cur, """
                UPDATE hso_students AS s
                SET firstname = v.firstname,
                    surname = v.surname,
                    allfirstnames = v.firstname,
                    privateemail = v.email,
                    updatedat = NOW()
                FROM (VALUES %s) AS v(mtknr, firstname, surname, email)
                WHERE s.mtknr = v.mtknr
            """, rows, template="(%s::integer, %s, %s, %s)", page_size=1000)
        print(f"    {len(rows)} Zeilen mit Namen befuellt.")

        print("\n[2/2] hso_personal...")
        cur.execute("""
            SELECT id FROM hso_personal
            WHERE COALESCE(nachname, '') = '' ORDER BY id
        """)
        prows = []
        for (pid,) in cur.fetchall():
            # Anderer Praefix als bei den Studierenden, sonst bekaeme
            # mtknr 42 denselben Namen wie Personal-ID 42.
            vorname, nachname = generate_person(f"personal-{pid}")
            prows.append((pid, vorname, nachname))
        if prows:
            execute_values(cur, """
                UPDATE hso_personal AS p
                SET vorname = v.vorname,
                    nachname = v.nachname,
                    updatedat = NOW()
                FROM (VALUES %s) AS v(id, vorname, nachname)
                WHERE p.id = v.id
            """, prows, template="(%s::integer, %s, %s)", page_size=1000)
        print(f"    {len(prows)} Zeilen mit Namen befuellt.")

        conn.commit()
        total = len(rows) + len(prows)
        if total == 0:
            print("\nNichts zu tun, alle Namensfelder sind bereits befuellt.")
        else:
            print(f"\nFertig. {total} Zeilen befuellt."
                  " Naechster Schritt: python scripts/mapping/generate_accounts.py")

    except Exception as e:
        conn.rollback()
        print(f"\nFEHLER: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
