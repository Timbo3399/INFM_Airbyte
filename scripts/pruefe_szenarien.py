"""
pruefe_szenarien.py - prueft je Szenario den Sollzustand und gibt eine Tabelle aus.

Zwei Aufgaben in einem Werkzeug:

  * Abnahmetest nach einem Neuaufbau. Wer install, setup-airbyte und
    setup-szenarien durchlaufen hat, sieht hier, ob der Demo-Zustand steht.
  * Demo-Werkzeug fuer die Abschlusspraesentation. Eine Tabelle, sechs
    Szenarien, keine Klickerei in drei Datenbank-Tools.

Die Sollwerte stehen in docs/ergebnisse.md und sind dort belegt. Sie sind
bewusst hart eingetragen: liefert ein Lauf etwas anderes, ist das ein Befund
und keine Einladung, die Erwartung nachzuziehen. Ein Sollwert ist deshalb auch
die 0 in Szenario 3, sie haelt Befund 1 fest (Zeilen kommen an, Inhalt nicht).

Aufruf:
    python scripts/pruefe_szenarien.py              # alle Szenarien
    python scripts/pruefe_szenarien.py Sz3 Sz5      # nur diese
    python scripts/pruefe_szenarien.py --leise      # nur die Zusammenfassung

Exit-Code 0, wenn alles stimmt, sonst 1. Damit taugt das Skript auch fuer CI
oder eine Schleife im Terminal.

Zugriff auf die Datenbanken:
  * PostgreSQL ueber psycopg2 auf die veroeffentlichten Ports (wie alle Loader)
  * MySQL ueber `docker exec` in den Container, damit kein zusaetzlicher
    Python-Treiber installiert werden muss
  * PostgREST ueber HTTP
"""

import os
import subprocess
import sys
from dataclasses import dataclass

# --- Verbindungsparameter ---------------------------------------------------

SOURCE_PG = dict(
    host=os.getenv("SOURCE_PG_HOST", "localhost"),
    port=int(os.getenv("SOURCE_PG_PORT", "5433")),
    dbname=os.getenv("SOURCE_PG_DB", "sourcedb"),
    user=os.getenv("SOURCE_PG_USER", "sourceuser"),
    password=os.getenv("SOURCE_PG_PASSWORD", "sourcepassword"),
)

DEST_PG = dict(
    host=os.getenv("DEST_PG_HOST", "localhost"),
    port=int(os.getenv("DEST_PG_PORT", "5434")),
    dbname=os.getenv("DEST_PG_DB", "destdb"),
    user=os.getenv("DEST_PG_USER", "destuser"),
    password=os.getenv("DEST_PG_PASSWORD", "destpassword"),
)

MYSQL_CONTAINER = os.getenv("DEST_MYSQL_CONTAINER", "hso_dest_mysql")
MYSQL_DB = os.getenv("DEST_MYSQL_DB", "destdb")
MYSQL_USER = os.getenv("DEST_MYSQL_USER", "destuser")
MYSQL_PASSWORD = os.getenv("DEST_MYSQL_PASSWORD", "destpassword")

POSTGREST_URL = os.getenv("POSTGREST_URL", "http://localhost:3000")

QUELLEN_NAMEN = ("source_pg", "dest_pg", "dest_mysql", "postgrest")


# --- Sollzustand ------------------------------------------------------------

@dataclass(frozen=True)
class Pruefung:
    szenario: str
    beschreibung: str
    erwartet: int
    quelle: str
    abfrage: str


# Alle Zahlen sind in docs/ergebnisse.md belegt, die Zeilennummer steht dabei.
SOLLWERTE = [
    # Szenario 1: Replikation zwischen Datenbanken (Befund 29).
    Pruefung("Sz1", "fm_gebaeude in dest-postgres", 25, "dest_pg",
             "SELECT count(*) FROM fm_gebaeude"),
    Pruefung("Sz1", "k_plz in dest-postgres", 34172, "dest_pg",
             "SELECT count(*) FROM k_plz"),

    # Szenario 2: Airbyte transportiert roh, dbt baut fm_raeume (Befund 32).
    Pruefung("Sz2", "fm_raeume Zeilen in dest-postgres", 1244, "dest_pg",
             "SELECT count(*) FROM fm_raeume"),
    Pruefung("Sz2", "fm_raeume mit Institut", 1184, "dest_pg",
             "SELECT count(institut) FROM fm_raeume"),
    Pruefung("Sz2", "fm_raeume in MySQL", 1244, "dest_mysql",
             "SELECT count(*) FROM fm_raeume"),

    # Szenario 3: der BLOB-Befund. Zeilen kommen an, Inhalt bleibt weg (Befund 1).
    Pruefung("Sz3", "hso_images in der Quelle", 1100, "source_pg",
             "SELECT count(*) FROM hso_images"),
    Pruefung("Sz3", "hso_images Zeilen in MySQL", 1100, "dest_mysql",
             "SELECT count(*) FROM hso_images"),
    Pruefung("Sz3", "hso_images mit Inhalt in MySQL (Befund)", 0, "dest_mysql",
             "SELECT count(data) FROM hso_images"),

    # Szenario 4: Account-Mapping in der Quelle.
    Pruefung("Sz4", "user_id gesetzt (students + personal)", 5922, "source_pg",
             """SELECT (SELECT count(*) FROM hso_students
                          WHERE COALESCE(user_id, '') <> '')
                     + (SELECT count(*) FROM hso_personal
                          WHERE COALESCE(user_id, '') <> '')"""),
    Pruefung("Sz4", "eindeutige user_id", 5922, "source_pg",
             """SELECT count(DISTINCT user_id) FROM (
                    SELECT user_id FROM hso_students
                      WHERE COALESCE(user_id, '') <> ''
                    UNION ALL
                    SELECT user_id FROM hso_personal
                      WHERE COALESCE(user_id, '') <> ''
                ) AS alle"""),

    # Szenario 4, Schritt 3: die Accounts als eigene Zieltabellen je Gruppe.
    # Getrennte Streams, damit sie nicht mit hso_students aus dem File-Connector
    # in derselben Zieltabelle landen (Befund 27).
    Pruefung("Sz4", "hso_student_accounts in dest-postgres", 5052, "dest_pg",
             "SELECT count(*) FROM hso_student_accounts"),
    Pruefung("Sz4", "hso_personal_accounts in dest-postgres", 870, "dest_pg",
             "SELECT count(*) FROM hso_personal_accounts"),

    # Szenario 5: IdM-Sync mit Deduplizierung (Befund 31).
    Pruefung("Sz5", "hso_user Zeilen in MySQL", 5922, "dest_mysql",
             "SELECT count(*) FROM hso_user"),
    Pruefung("Sz5", "verschiedene user_id in MySQL", 5922, "dest_mysql",
             "SELECT count(DISTINCT user_id) FROM hso_user"),
    Pruefung("Sz5", "hso_user mit image_id", 5922, "dest_mysql",
             "SELECT count(image_id) FROM hso_user"),

    # Szenario 6a: PostgREST auf die Zieldaten (Befund 14).
    Pruefung("Sz6a", "GET /k_plz?limit=1 liefert HTTP", 200, "postgrest",
             "/k_plz?limit=1"),
]


# --- reine Funktionen -------------------------------------------------------

def tausender(wert) -> str:
    """Zahl mit Punkt als Tausendertrenner. Fehlende Messung wird zum Strich."""
    if wert is None:
        return "-"
    return f"{wert:,}".replace(",", ".")


def bewerte(erwartet, gefunden) -> str:
    return "ok" if gefunden == erwartet else "fehlt"


def nur_szenarien(pruefungen, auswahl):
    """Filtert auf die genannten Szenarien. Leere Auswahl laesst alles durch."""
    if not auswahl:
        return pruefungen
    gewuenscht = {a.lower() for a in auswahl}
    return [p for p in pruefungen if p.szenario.lower() in gewuenscht]


def messe(pruefungen, quellen):
    """[(Pruefung, gefunden)]. Eine gescheiterte Abfrage liefert None.

    Eine fehlende Zieltabelle ist der haeufigste Fall und genau der, den die
    Tabelle zeigen soll. Sie darf den Lauf deshalb nicht abbrechen.
    """
    ergebnisse = []
    for pruefung in pruefungen:
        frage = quellen.get(pruefung.quelle)
        if frage is None:
            ergebnisse.append((pruefung, None))
            continue
        try:
            ergebnisse.append((pruefung, frage(pruefung.abfrage)))
        except Exception:
            ergebnisse.append((pruefung, None))
    return ergebnisse


def alles_ok(ergebnisse) -> bool:
    return all(bewerte(p.erwartet, g) == "ok" for p, g in ergebnisse)


def zusammenfassung(ergebnisse) -> str:
    gesamt = len(ergebnisse)
    ok = sum(1 for p, g in ergebnisse if bewerte(p.erwartet, g) == "ok")
    return f"{gesamt} Pruefungen, {ok} ok, {gesamt - ok} fehlt"


def ratschlag(ergebnisse) -> str:
    """Was als naechstes zu tun ist, oder "" wenn alles stimmt.

    Zwei Fehlerbilder, die nach demselben aussehen: keine Messung kommt durch
    (dann laeuft der Stack nicht), oder einzelne Sollzustaende fehlen (dann fehlt
    ein Aufbauschritt). Der falsche Hinweis kostet in einer Demo Minuten.
    """
    offen = [(p, g) for p, g in ergebnisse if bewerte(p.erwartet, g) != "ok"]
    if not offen:
        return ""
    if all(g is None for _, g in ergebnisse):
        return ("Keine einzige Messung kam durch. Laeuft der Stack?\n"
                "    docker ps\n"
                "    .\\scripts\\start.ps1      (Linux/macOS: bash scripts/start.sh)")
    return ("Sollwerte stehen in docs/ergebnisse.md."
            " Fehlt ein Zielzustand, hilft meist:\n"
            "    python scripts/setup_szenarien.py")


KOPF = ("Szenario", "Pruefung", "erwartet", "gefunden", "Status")


def formatiere_tabelle(ergebnisse) -> str:
    """Feste Spaltenbreiten, damit sich Soll und Ist untereinander lesen lassen."""
    zeilen = [(p.szenario, p.beschreibung, tausender(p.erwartet),
               tausender(g), bewerte(p.erwartet, g)) for p, g in ergebnisse]
    breiten = [max(len(KOPF[i]), *(len(z[i]) for z in zeilen)) if zeilen
               else len(KOPF[i]) for i in range(len(KOPF))]

    def ausgeben(spalten):
        # Zahlen rechts, Text links.
        return "  ".join(
            wert.rjust(breiten[i]) if i in (2, 3) else wert.ljust(breiten[i])
            for i, wert in enumerate(spalten))

    ausgabe = [ausgeben(KOPF), "  ".join("-" * b for b in breiten)]
    ausgabe.extend(ausgeben(z) for z in zeilen)
    return "\n".join(ausgabe)


def mysql_kommando(container, benutzer, datenbank, abfrage):
    """Argumentliste fuer eine MySQL-Abfrage per docker exec.

    Das Passwort reist als MYSQL_PWD in der Umgebung des Containers mit, nicht
    als -p auf der Kommandozeile. Sonst schreibt der Client bei jedem Aufruf
    eine Warnung nach stderr, und die stuende mitten in der Demo-Ausgabe.

    -N -B schalten Kopfzeile und ASCII-Rahmen ab, damit die Antwort ein
    einzelner Wert ist.
    """
    return ["docker", "exec", "-e", "MYSQL_PWD", container,
            "mysql", "-u", benutzer, "-D", datenbank, "-N", "-B", "-e", abfrage]


def erste_zahl(text) -> int:
    """Erstes Feld der ersten nicht leeren Zeile als int.

    Wirft bei leerer Ausgabe: die darf nicht als 0 durchgehen, sonst zeigt die
    Tabelle bei Szenario 3 faelschlich ein ok.
    """
    zeilen = [z for z in (text or "").splitlines() if z.strip()]
    if not zeilen:
        raise ValueError("keine Ausgabe")
    return int(zeilen[0].split("\t")[0].strip())


# --- Quellen ----------------------------------------------------------------

def postgres_quelle(verbindung):
    """Liefert eine Funktion abfrage -> Skalar fuer diese Postgres-Verbindung."""
    import psycopg2

    def frage(abfrage):
        conn = psycopg2.connect(connect_timeout=10, **verbindung)
        try:
            with conn.cursor() as cur:
                cur.execute(abfrage)
                return cur.fetchone()[0]
        finally:
            conn.close()

    return frage


def mysql_quelle():
    def frage(abfrage):
        umgebung = dict(os.environ, MYSQL_PWD=MYSQL_PASSWORD)
        fertig = subprocess.run(
            mysql_kommando(MYSQL_CONTAINER, MYSQL_USER, MYSQL_DB, abfrage),
            capture_output=True, text=True, timeout=120, env=umgebung)
        if fertig.returncode != 0:
            raise RuntimeError((fertig.stderr or "").strip()[:200])
        return erste_zahl(fertig.stdout)

    return frage


def postgrest_quelle():
    import requests

    def frage(pfad):
        antwort = requests.get(POSTGREST_URL.rstrip("/") + pfad, timeout=30)
        return antwort.status_code

    return frage


def quellen():
    return {
        "source_pg": postgres_quelle(SOURCE_PG),
        "dest_pg": postgres_quelle(DEST_PG),
        "dest_mysql": mysql_quelle(),
        "postgrest": postgrest_quelle(),
    }


# --- Main -------------------------------------------------------------------

HILFE = """Aufruf: python scripts/pruefe_szenarien.py [--leise] [Szenario ...]

    ohne Argumente   alle Szenarien pruefen
    Sz1 Sz3 Sz6a     nur die genannten
    --leise          nur die Zusammenfassung ausgeben

Exit-Code 0 wenn alle Pruefungen stimmen, sonst 1."""


def main(argv):
    if any(a in ("-h", "--help") for a in argv):
        print(HILFE)
        return 0

    leise = "--leise" in argv
    auswahl = [a for a in argv if not a.startswith("-")]

    pruefungen = nur_szenarien(SOLLWERTE, auswahl)
    if not pruefungen:
        print(f"Keine Pruefung passt zu: {' '.join(auswahl)}")
        print("Bekannt: " + ", ".join(dict.fromkeys(p.szenario for p in SOLLWERTE)))
        return 1

    ergebnisse = messe(pruefungen, quellen())

    if not leise:
        print()
        print(formatiere_tabelle(ergebnisse))
        print()
    print(zusammenfassung(ergebnisse))

    hinweis = ratschlag(ergebnisse)
    if hinweis:
        print("\n" + hinweis)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
