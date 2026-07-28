"""
pruefe_szenarien.py - prueft je Szenario, ob es laut seiner Definition
durchgelaufen ist, und gibt ein Urteil je Szenario aus.

Zwei Aufgaben in einem Werkzeug:

  * Abnahmetest nach einem Neuaufbau. Wer install, setup-airbyte und
    setup-szenarien durchlaufen hat, sieht hier, ob der Demo-Zustand steht.
  * Demo-Werkzeug fuer die Abschlusspraesentation. Eine Tabelle, sieben
    Szenarien, keine Klickerei in drei Datenbank-Tools.

Die Gliederung folgt docs/testszenarien.md: ein Szenario hat Teilaufgaben
(A/B bzw. Schritt 1/2/3), eine Teilaufgabe hat Pruefungen. Ein Szenario gilt
als erfuellt, wenn jede Pflichtpruefung jeder seiner Teilaufgaben stimmt. Damit
beantwortet das Skript die Frage, die eine flache Pruefungsliste offen laesst:
ist Szenario 2 durchgelaufen, oder nur die Haelfte davon?

Zwei Arten von Pruefung:

  * art="soll"   Die Aufgabenstellung verlangt diesen Zustand. Stimmt er nicht,
                 ist das Szenario nicht erfuellt und der Exit-Code 1.
  * art="befund" Ein in docs/ergebnisse.md dokumentierter Fehlschlag, den wir
                 absichtlich festhalten. Er wird nachgemessen, kippt aber kein
                 Szenario: dass Airbyte BLOBs verliert, ist ein Ergebnis der
                 Evaluation und kein Mangel des Aufbaus. Reproduziert ein Befund
                 nicht mehr, sagt das Skript das laut, denn dann ist die
                 Dokumentation veraltet.

Szenario 6b (SOAP) ist nicht umgesetzt und steht mit genau diesem Status in der
Tabelle. Weglassen waere die unehrlichere Variante: in einer Bewertung ist
gerade die Luecke eine Aussage.

Die Sollwerte sind bewusst hart eingetragen: liefert ein Lauf etwas anderes, ist
das ein Befund und keine Einladung, die Erwartung nachzuziehen. Jede Zahl traegt
im Kommentar ihren Beleg, entweder eine Zeile aus docs/ergebnisse.md, eine
Stelle in docs/testszenarien.md oder den Vermerk, dass sie am laufenden Aufbau
gemessen wurde.

Aufruf:
    python scripts/pruefe_szenarien.py              # alle Szenarien
    python scripts/pruefe_szenarien.py Sz3 Sz5      # nur diese
    python scripts/pruefe_szenarien.py --detail     # jede Pruefung einzeln
    python scripts/pruefe_szenarien.py --leise      # nur die Zusammenfassung

Exit-Code 0, wenn jedes gepruefte Szenario erfuellt ist, sonst 1. Damit taugt
das Skript auch fuer CI oder eine Schleife im Terminal.

Zugriff auf die Datenbanken:
  * PostgreSQL ueber psycopg2 auf die veroeffentlichten Ports (wie alle Loader)
  * MySQL ueber `docker exec` in den Container, damit kein zusaetzlicher
    Python-Treiber installiert werden muss
  * PostgREST ueber HTTP
  * das Dateisystem fuer den Bild-Export aus Szenario 3
"""

import dataclasses
import os
import subprocess
import sys
from dataclasses import dataclass

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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

QUELLEN_NAMEN = ("source_pg", "dest_pg", "dest_mysql", "postgrest",
                 "postgrest_zeilen", "dateien")


# --- Datenmodell ------------------------------------------------------------

@dataclass(frozen=True)
class Pruefung:
    """Ein Sollwert und die Abfrage, die ihn misst.

    Die ersten fuenf Felder stehen in der Reihenfolge, die sie seit jeher haben,
    und die neuen tragen Vorgabewerte. Damit bleiben vorhandene Aufrufe mit
    Positionsargumenten gueltig, in setup_szenarien.py wie in den Tests.

    art        "soll" zaehlt fuer das Szenario-Urteil, "befund" nicht.
    vergleich  "gleich" oder "mindestens". Mindestens braucht es dort, wo der
               Wert vom Lauf abhaengt: die Airbyte-Rohtabelle waechst mit jedem
               Sync (Befund 5), eine feste Zahl waere dort schlicht falsch.
    beleg      Woher der Sollwert stammt, erscheint in der Befundliste.
    """
    szenario: str
    beschreibung: str
    erwartet: int
    quelle: str
    abfrage: str
    id: str = ""
    art: str = "soll"
    vergleich: str = "gleich"
    beleg: str = ""


@dataclass(frozen=True)
class Teilaufgabe:
    """Ein Abschnitt eines Szenarios, so benannt wie in docs/testszenarien.md.

    `befehl` ist das Kommando, das diesen Teil herstellt. Es erscheint nur, wenn
    der Teil offen ist. Der pauschale Verweis auf setup_szenarien.py hilft
    naemlich genau dann nicht, wenn der fehlende Schritt dort gar nicht steht.
    """
    name: str
    pruefungen: tuple
    befehl: str = ""


@dataclass(frozen=True)
class Szenario:
    kuerzel: str
    titel: str
    ziel: str
    teilaufgaben: tuple = ()
    status: str = "geprueft"      # geprueft | nicht_umgesetzt
    begruendung: str = ""


def _teil(name: str, pruefungen, befehl: str = "") -> Teilaufgabe:
    return Teilaufgabe(name, tuple(pruefungen), befehl)


def _szenario(kuerzel, titel, ziel, teilaufgaben=(), status="geprueft",
              begruendung="") -> Szenario:
    """Baut ein Szenario und stempelt sein Kuerzel in jede Pruefung.

    So steht das Kuerzel in der Definition genau einmal, die Pruefung traegt es
    aber trotzdem als Feld. Darauf beruhen die flache Liste SOLLWERTE und der
    Filter nur_szenarien, beide werden von setup_szenarien.py benutzt.
    """
    gestempelt = tuple(
        _teil(t.name,
              [dataclasses.replace(p, szenario=kuerzel) for p in t.pruefungen],
              t.befehl)
        for t in teilaufgaben)
    return Szenario(kuerzel, titel, ziel, gestempelt, status, begruendung)


def _p(id, beschreibung, erwartet, quelle, abfrage, **rest) -> Pruefung:
    """Kurzform. Das Szenario-Kuerzel setzt _szenario nach."""
    return Pruefung("", beschreibung, erwartet, quelle, abfrage, id, **rest)


# --- Sollzustand ------------------------------------------------------------
#
# Gliederung und Wortlaut der Teilaufgaben folgen docs/testszenarien.md. Hinter
# jedem Sollwert steht sein Beleg.

SZENARIEN = [

    _szenario(
        "Sz1", "Einspielen der Testdaten",
        "Testdaten in MySQL und PostgreSQL laden, verschiedene Source-Typen testen",
        (
            # Befund 29 in ergebnisse.md: Replikation zwischen Datenbanken.
            _teil("A  Replikation PostgreSQL nach PostgreSQL", [
                _p("sz1-gebaeude-pg", "fm_gebaeude in dest-postgres", 25,
                   "dest_pg", "SELECT count(*) FROM fm_gebaeude"),
                _p("sz1-plz-pg", "k_plz in dest-postgres", 34172,
                   "dest_pg", "SELECT count(*) FROM k_plz"),
            ], 'python scripts/airbyte/run_sync.py "HSO PG nach PG (Full Refresh)"'),

            # Die Aufgabenstellung nennt beide Ziele. Bisher pruefte das Skript
            # nur das Postgres-Ziel, MySQL lief ungeprueft mit.
            _teil("B  Replikation PostgreSQL nach MySQL", [
                _p("sz1-gebaeude-mysql", "fm_gebaeude in dest-mysql", 25,
                   "dest_mysql", "SELECT count(*) FROM fm_gebaeude"),
                _p("sz1-plz-mysql", "k_plz in dest-mysql", 34172,
                   "dest_mysql", "SELECT count(*) FROM k_plz"),
            ], 'python scripts/airbyte/run_sync.py "HSO PG nach MySQL (Full Refresh)"'),

            # Befund 30: der File-Connector lud eine CSV, an der COPY scheiterte.
            _teil("C  File-Connector als zweiter Source-Typ", [
                _p("sz1-students-pg", "hso_students in dest-postgres", 5052,
                   "dest_pg", "SELECT count(*) FROM hso_students"),
            ], 'python scripts/airbyte/run_sync.py "HSO CSV hso_students nach PG"'),
        )),

    _szenario(
        "Sz2", "Facility Management",
        "FM-Tabellen nach PostgreSQL, denormalisierte Raumtabelle nach MySQL",
        (
            # Teilaufgabe A verlangt die Raumuebersicht als Join. Zeilenzahlen
            # allein belegen das nicht: der Join kann alle drei Tabellen sehen
            # und trotzdem nichts treffen, genau das ist Befund 16.
            _teil("A  FM-Tabellen in dest-postgres, Raumuebersicht joinbar", [
                _p("sz2-stamm", "fm_stamm in dest-postgres", 1244,
                   "dest_pg", "SELECT count(*) FROM fm_stamm"),
                _p("sz2-inst", "fm_inst in dest-postgres", 2083,
                   "dest_pg", "SELECT count(*) FROM fm_inst"),
                _p("sz2-join", "Raumuebersicht Gebaeude x Raum", 1244, "dest_pg",
                   """SELECT count(*) FROM fm_stamm s
                        JOIN fm_gebaeude g
                          ON lpad(s.geb_nr, 4, '0') = lpad(g.geb_nr, 4, '0')"""),
                _p("sz2-join-naiv", "derselbe Join ohne lpad trifft nichts", 0,
                   "dest_pg",
                   """SELECT count(*) FROM fm_stamm s
                        JOIN fm_gebaeude g ON s.geb_nr = g.geb_nr""",
                   art="befund", beleg="Befund 16"),
            ], 'python scripts/airbyte/run_sync.py "HSO FM nach PG"'),

            # Befund 32. Die Spaltenpruefung haelt die CREATE TABLE aus der
            # Aufgabenstellung fest, sieben Spalten mit festgelegten Namen.
            _teil("B  Raumtabelle fm_raeume, denormalisiert", [
                _p("sz2-raeume-pg", "fm_raeume Zeilen in dest-postgres", 1244,
                   "dest_pg", "SELECT count(*) FROM fm_raeume"),
                _p("sz2-raeume-gebaeude", "fm_raeume mit Gebaeudename", 1244,
                   "dest_pg", "SELECT count(gebaeude) FROM fm_raeume"),
                _p("sz2-raeume-institut", "fm_raeume mit Institut", 1184,
                   "dest_pg", "SELECT count(institut) FROM fm_raeume"),
                _p("sz2-raeume-flaeche", "fm_raeume Flaeche in m2", 52009,
                   "dest_pg", "SELECT round(sum(flaeche)) FROM fm_raeume"),
                _p("sz2-raeume-mysql", "fm_raeume in MySQL", 1244,
                   "dest_mysql", "SELECT count(*) FROM fm_raeume"),
                _p("sz2-raeume-mysql-institut", "fm_raeume in MySQL mit Institut",
                   1184, "dest_mysql", "SELECT count(institut) FROM fm_raeume"),
                _p("sz2-raeume-spalten",
                   "fm_raeume hat die sieben geforderten Spalten", 7,
                   "dest_mysql",
                   """SELECT count(*) FROM information_schema.columns
                        WHERE table_schema = 'destdb' AND table_name = 'fm_raeume'
                          AND column_name IN ('raum_id','raumnr','gebaeude',
                              'gebaeude_nr','institut','flaeche','kostenstelle')"""),
            ], "python -m dbt.cli.main run --project-dir dbt --profiles-dir dbt"
               ' && python scripts/airbyte/run_sync.py "HSO fm_raeume nach MySQL"'),
        )),

    _szenario(
        "Sz3", "Testdaten fuer Bilder generieren",
        ">1.000 Bilder per API abrufen, als BLOB speichern, danach exportieren",
        (
            # Befund 34: der Weg Datei nach BYTEA nach Datei verliert nichts.
            # Die Bytezahl ist reproduzierbar, weil load_images.py feste Seeds
            # benutzt (derselbe Seed liefert dasselbe Bild). Am Aufbau gemessen,
            # deckungsgleich mit den 8.015 kB aus testszenarien.md.
            _teil("A  1.100 Bilder als BLOB in der Quelle", [
                _p("sz3-bilder-quelle", "hso_images in der Quelle", 1100,
                   "source_pg", "SELECT count(*) FROM hso_images"),
                _p("sz3-bilder-inhalt", "hso_images mit Inhalt in der Quelle",
                   1100, "source_pg", "SELECT count(data) FROM hso_images"),
                _p("sz3-bilder-bytes", "hso_images Bytes in der Quelle", 8207021,
                   "source_pg",
                   "SELECT COALESCE(sum(octet_length(data)), 0) FROM hso_images"),
            ], "python scripts/images/load_images.py"),

            # Teilaufgabe B der Aufgabenstellung. Stimmt die Bytesumme der
            # Dateien mit der in der Datenbank ueberein, ist nichts verloren
            # gegangen; auf Byte-Gleichheit je Datei prueft tests/test_export_images.py.
            _teil("B  Bilder aus der Datenbank exportieren", [
                _p("sz3-export-anzahl", "Dateien in data/images", 1100,
                   "dateien", "anzahl:data/images"),
                _p("sz3-export-bytes", "Bytes in data/images", 8207021,
                   "dateien", "bytes:data/images"),
            ], "python scripts/images/export_images.py"),

            # Befund 1, das Ausschlusskriterium der Evaluation: der Sync meldet
            # Erfolg, legt die richtige Zeilenzahl an und laesst den Inhalt weg.
            # Das Szenario-Ziel haengt nicht daran, es ist ueber Python erfuellt.
            _teil("Airbyte-Evaluation: BYTEA nach MySQL", [
                _p("sz3-mysql-zeilen", "hso_images Zeilen in MySQL", 1100,
                   "dest_mysql", "SELECT count(*) FROM hso_images",
                   art="befund", beleg="Befund 1"),
                _p("sz3-mysql-inhalt", "hso_images mit Inhalt in MySQL", 0,
                   "dest_mysql", "SELECT count(data) FROM hso_images",
                   art="befund", beleg="Befund 1"),
            ], 'python scripts/airbyte/run_sync.py "HSO Bilder nach MySQL"'),
        )),

    _szenario(
        "Sz4", "Mapping von Studenten und Personal",
        "Anonymisierte Daten befuellen, Account-IDs vergeben, in neue Tabellen schreiben",
        (
            # Ohne Namen erzeugt der Generator keine einzige user_id, dieser
            # Schritt ist also die Voraussetzung fuer alles Weitere.
            _teil("1  Namen befuellen", [
                _p("sz4-nachname-stud", "hso_students mit Nachname", 5052,
                   "source_pg",
                   "SELECT count(*) FROM hso_students WHERE COALESCE(surname,'') <> ''"),
                _p("sz4-vorname-stud", "hso_students mit Vorname", 5052,
                   "source_pg",
                   "SELECT count(*) FROM hso_students WHERE COALESCE(firstname,'') <> ''"),
                _p("sz4-nachname-pers", "hso_personal mit Nachname", 870,
                   "source_pg",
                   "SELECT count(*) FROM hso_personal WHERE COALESCE(nachname,'') <> ''"),
                _p("sz4-vorname-pers", "hso_personal mit Vorname", 870,
                   "source_pg",
                   "SELECT count(*) FROM hso_personal WHERE COALESCE(vorname,'') <> ''"),
            ], "python scripts/mapping/fill_random_names.py"),

            # Die beiden Nullen pruefen die Spec aus hso_accountgenerator.js:
            # hoechstens acht Zeichen, Umlaute ersetzt. Am Aufbau gemessen.
            _teil("2  Accounts nach HSO-Schema vergeben", [
                _p("sz4-uid-gesetzt", "user_id gesetzt (students + personal)",
                   5922, "source_pg",
                   """SELECT (SELECT count(*) FROM hso_students
                                WHERE COALESCE(user_id, '') <> '')
                           + (SELECT count(*) FROM hso_personal
                                WHERE COALESCE(user_id, '') <> '')"""),
                _p("sz4-uid-eindeutig", "eindeutige user_id", 5922, "source_pg",
                   """SELECT count(DISTINCT user_id) FROM (
                          SELECT user_id FROM hso_students
                            WHERE COALESCE(user_id, '') <> ''
                          UNION ALL
                          SELECT user_id FROM hso_personal
                            WHERE COALESCE(user_id, '') <> ''
                      ) AS alle"""),
                _p("sz4-mail-gesetzt", "Hochschul-E-Mail gesetzt", 5922,
                   "source_pg",
                   """SELECT (SELECT count(*) FROM hso_students
                                WHERE COALESCE(hochschulemail, '') <> '')
                           + (SELECT count(*) FROM hso_personal
                                WHERE COALESCE(hso_email, '') <> '')"""),
                _p("sz4-uid-laenge", "user_id laenger als acht Zeichen", 0,
                   "source_pg",
                   """SELECT (SELECT count(*) FROM hso_students WHERE length(user_id) > 8)
                           + (SELECT count(*) FROM hso_personal WHERE length(user_id) > 8)"""),
                _p("sz4-uid-zeichen", "user_id mit Umlaut oder Sonderzeichen", 0,
                   "source_pg",
                   """SELECT (SELECT count(*) FROM hso_students WHERE user_id ~ '[^a-z0-9]')
                           + (SELECT count(*) FROM hso_personal WHERE user_id ~ '[^a-z0-9]')"""),
            ], "python scripts/mapping/generate_accounts.py"),

            # Getrennte Streams, damit sie nicht mit hso_students aus dem
            # File-Connector in derselben Zieltabelle landen (Befund 27).
            _teil("3  Accounts als eigene Zieltabellen je Gruppe", [
                _p("sz4-stud-accounts", "hso_student_accounts in dest-postgres",
                   5052, "dest_pg", "SELECT count(*) FROM hso_student_accounts"),
                _p("sz4-stud-accounts-uid",
                   "hso_student_accounts mit eindeutiger user_id", 5052,
                   "dest_pg",
                   "SELECT count(DISTINCT user_id) FROM hso_student_accounts"),
                _p("sz4-stud-accounts-mail", "hso_student_accounts mit E-Mail",
                   5052, "dest_pg",
                   "SELECT count(*) FROM hso_student_accounts WHERE COALESCE(email,'') <> ''"),
                _p("sz4-pers-accounts", "hso_personal_accounts in dest-postgres",
                   870, "dest_pg", "SELECT count(*) FROM hso_personal_accounts"),
                _p("sz4-pers-accounts-uid",
                   "hso_personal_accounts mit eindeutiger user_id", 870,
                   "dest_pg",
                   "SELECT count(DISTINCT user_id) FROM hso_personal_accounts"),
                _p("sz4-pers-accounts-mail", "hso_personal_accounts mit E-Mail",
                   870, "dest_pg",
                   "SELECT count(*) FROM hso_personal_accounts WHERE COALESCE(email,'') <> ''"),
            ], 'python scripts/mapping/create_account_views.py'
               ' && python scripts/airbyte/run_sync.py "HSO Accounts nach PG"'),
        )),

    _szenario(
        "Sz5", "IdM-System",
        "hso_students und hso_personal als gemeinsame hso_user nach MySQL, inkrementell",
        (
            # Befund 31. Dass Zeilenzahl und Anzahl verschiedener user_id
            # uebereinstimmen, ist der lesbare Beweis, dass die Deduplizierung
            # greift: bei Rueckfall auf Append stuenden hier Duplikate.
            _teil("A  hso_user in dest-mysql, dedupliziert", [
                _p("sz5-user-zeilen", "hso_user Zeilen in MySQL", 5922,
                   "dest_mysql", "SELECT count(*) FROM hso_user"),
                _p("sz5-user-eindeutig", "verschiedene user_id in MySQL", 5922,
                   "dest_mysql", "SELECT count(DISTINCT user_id) FROM hso_user"),
                _p("sz5-user-studierende", "davon Studierende", 5052,
                   "dest_mysql", "SELECT count(*) FROM hso_user WHERE rolle = 'student'"),
                _p("sz5-user-personal", "davon Personal", 870,
                   "dest_mysql", "SELECT count(*) FROM hso_user WHERE rolle = 'personal'"),
                _p("sz5-user-mail", "hso_user mit E-Mail", 5922, "dest_mysql",
                   "SELECT count(*) FROM hso_user WHERE COALESCE(email,'') <> ''"),
                _p("sz5-user-spalten",
                   "hso_user hat die sieben geforderten Spalten", 7,
                   "dest_mysql",
                   """SELECT count(*) FROM information_schema.columns
                        WHERE table_schema = 'destdb' AND table_name = 'hso_user'
                          AND column_name IN ('user_id','nachname','vorname',
                              'email','rolle','status','image_id')"""),
            ], 'python scripts/mapping/create_hso_user_view.py'
               ' && python scripts/airbyte/run_sync.py "HSO IdM hso_user nach MySQL"'),

            # Zweiter Teil des Szenarios: Verknuepfung mit den Bildern aus
            # Szenario 3. Die 1.095 stehen in testszenarien.md, Abschnitt
            # Bildverknuepfung, und sind am Aufbau nachgemessen.
            _teil("B  Verknuepfung mit den Bildern aus Szenario 3", [
                _p("sz5-user-bild", "hso_user mit image_id", 5922, "dest_mysql",
                   "SELECT count(image_id) FROM hso_user"),
                _p("sz5-user-bilder-verschieden", "verteilt auf verschiedene Bilder",
                   1095, "dest_mysql",
                   "SELECT count(DISTINCT image_id) FROM hso_user"),
            ], 'python scripts/airbyte/run_sync.py "HSO IdM hso_user nach MySQL"'),

            # Befund 2 und 5. Beides Eigenschaften von Airbyte, nicht des
            # Aufbaus, deshalb art="befund".
            _teil("Befunde zum Dedup-Modus", [
                _p("sz5-kein-unique-index",
                   "eindeutige Indizes auf hso_user in MySQL", 0, "dest_mysql",
                   """SELECT count(*) FROM information_schema.statistics
                        WHERE table_schema = 'destdb' AND table_name = 'hso_user'
                          AND non_unique = 0""",
                   art="befund", beleg="Befund 2"),
                # Waechst mit jedem Sync, eine feste Zahl waere hier falsch.
                _p("sz5-rohtabelle", "Rohtabelle behaelt jede Generation", 5922,
                   "dest_mysql", "SELECT count(*) FROM destdb_raw__stream_hso_user",
                   art="befund", vergleich="mindestens", beleg="Befund 5"),
            ]),
        )),

    _szenario(
        "Sz6a", "Web-API: REST",
        "REST-Schnittstelle auf die Zieldaten bereitstellen",
        (
            # Befund 14. Die Aufgabenstellung nennt beide Endpunkte namentlich.
            # Der Zeilentest unterscheidet eine leere Antwort von einer echten:
            # PostgREST liefert auch auf eine leere Tabelle HTTP 200.
            _teil("PostgREST auf dest-postgres", [
                _p("sz6a-plz-status", "GET /k_plz liefert HTTP", 200,
                   "postgrest", "/k_plz?limit=1"),
                _p("sz6a-plz-zeilen", "GET /k_plz liefert einen Datensatz", 1,
                   "postgrest_zeilen", "/k_plz?limit=1"),
                _p("sz6a-students-status", "GET /hso_students liefert HTTP", 200,
                   "postgrest", "/hso_students?limit=1"),
            ], "docker compose up -d postgrest"),
        )),

    _szenario(
        "Sz6b", "Web-API: SOAP (HISinOne)",
        "SOAP-Abfrage gegen hisinone.hs-offenburg.de, Antwort in die DB schreiben",
        status="nicht_umgesetzt",
        begruendung=("Zugang zu qisserver/services2 wurde nicht bereitgestellt."
                     " Airbyte hat ausserdem keinen XML-Support im File-Connector"
                     " (Befund 13), es braeuchte also ohnehin Vorverarbeitung.")),
]


def _pruefe_definition(szenarien):
    """Haelt die Definition selbst gesund: eindeutige Ids, bekannte Quellen.

    Laeuft beim Import. Ein Tippfehler in einer Id faellt damit sofort auf und
    nicht erst, wenn setup_szenarien.py den Sollwert nicht findet.
    """
    gesehen = set()
    for s in szenarien:
        for t in s.teilaufgaben:
            for p in t.pruefungen:
                if not p.id:
                    raise ValueError(f"{s.kuerzel}/{p.beschreibung}: Id fehlt")
                if p.id in gesehen:
                    raise ValueError(f"Id doppelt vergeben: {p.id}")
                gesehen.add(p.id)
                if p.quelle not in QUELLEN_NAMEN:
                    raise ValueError(f"{p.id}: unbekannte Quelle {p.quelle}")
                if p.art not in ("soll", "befund"):
                    raise ValueError(f"{p.id}: unbekannte Art {p.art}")
                if p.vergleich not in ("gleich", "mindestens"):
                    raise ValueError(f"{p.id}: unbekannter Vergleich {p.vergleich}")


_pruefe_definition(SZENARIEN)


def alle_pruefungen(szenarien) -> list:
    """Jede Pruefung aller Szenarien, in der Reihenfolge der Definition."""
    return [p for s in szenarien for t in s.teilaufgaben for p in t.pruefungen]


# Flache Liste ueber alle Szenarien. setup_szenarien.py und die Tests greifen
# darauf zu, deshalb bleibt sie erhalten und heisst weiter so.
SOLLWERTE = alle_pruefungen(SZENARIEN)


def soll(id: str) -> Pruefung:
    """Sollwert ueber seine Id. Der Weg fuer alles ausserhalb dieses Moduls.

    Vorher suchte setup_szenarien.py per Teilstring der Beschreibung. Das hielt,
    solange keine zweite Pruefung denselben Tabellennamen trug, und waere mit
    'fm_gebaeude in dest-mysql' neben 'fm_gebaeude in dest-postgres' beim Import
    mehrdeutig geworden.
    """
    for p in SOLLWERTE:
        if p.id == id:
            return p
    raise KeyError(f"unbekannte Pruefung: {id}")


# --- reine Funktionen -------------------------------------------------------

def tausender(wert) -> str:
    """Zahl mit Punkt als Tausendertrenner. Fehlende Messung wird zum Strich."""
    if wert is None:
        return "-"
    return f"{wert:,}".replace(",", ".")


def bewerte(erwartet, gefunden) -> str:
    return "ok" if gefunden == erwartet else "fehlt"


def stimmt(pruefung: Pruefung, gefunden) -> bool:
    """Trifft die Messung den Sollwert, unter dem Vergleich dieser Pruefung?"""
    if gefunden is None:
        return False
    if pruefung.vergleich == "mindestens":
        return gefunden >= pruefung.erwartet
    return gefunden == pruefung.erwartet


def status_von(pruefung: Pruefung, gefunden) -> str:
    """Der Status einer einzelnen Pruefung, in ihrer eigenen Sprache.

    Ein Befund ist kein Sollzustand, den man herstellt, sondern eine Beobachtung,
    die man reproduziert. "ok" waere dort irrefuehrend: bei Szenario 3 hiesse es,
    dass 0 uebertragene Bilder in Ordnung sind.
    """
    if pruefung.art == "befund":
        return "bestaetigt" if stimmt(pruefung, gefunden) else "NICHT reproduziert"
    return "ok" if stimmt(pruefung, gefunden) else "fehlt"


def nur_szenarien(pruefungen, auswahl):
    """Filtert Pruefungen auf die genannten Szenarien. Leere Auswahl laesst alles durch."""
    if not auswahl:
        return pruefungen
    gewuenscht = {a.lower() for a in auswahl}
    return [p for p in pruefungen if p.szenario.lower() in gewuenscht]


def nur_szenario_objekte(szenarien, auswahl):
    """Dasselbe auf der Ebene der Szenarien."""
    if not auswahl:
        return szenarien
    gewuenscht = {a.lower() for a in auswahl}
    return [s for s in szenarien if s.kuerzel.lower() in gewuenscht]


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


def als_karte(ergebnisse) -> dict:
    """{Pruefungs-Id: gemessener Wert}."""
    return {p.id: wert for p, wert in ergebnisse}


def alles_ok(ergebnisse) -> bool:
    return all(bewerte(p.erwartet, g) == "ok" for p, g in ergebnisse)


def zusammenfassung(ergebnisse) -> str:
    gesamt = len(ergebnisse)
    ok = sum(1 for p, g in ergebnisse if bewerte(p.erwartet, g) == "ok")
    return f"{gesamt} Pruefungen, {ok} ok, {gesamt - ok} fehlt"


# --- Urteil je Szenario -----------------------------------------------------

def soll_pruefungen(szenario) -> list:
    """Die Pruefungen, an denen das Szenario haengt. Befunde zaehlen nicht mit."""
    return [p for t in szenario.teilaufgaben for p in t.pruefungen
            if p.art == "soll"]


def befund_pruefungen(szenario) -> list:
    return [p for t in szenario.teilaufgaben for p in t.pruefungen
            if p.art == "befund"]


def teil_erfuellt(teilaufgabe, karte) -> bool:
    return all(stimmt(p, karte.get(p.id))
               for p in teilaufgabe.pruefungen if p.art == "soll")


def szenario_urteil(szenario, karte) -> str:
    """erfuellt | NICHT erfuellt | nicht umgesetzt."""
    if szenario.status == "nicht_umgesetzt":
        return "nicht umgesetzt"
    pflicht = soll_pruefungen(szenario)
    if not pflicht:
        return "erfuellt"
    return ("erfuellt" if all(stimmt(p, karte.get(p.id)) for p in pflicht)
            else "NICHT erfuellt")


def zaehle(szenario, karte):
    """(erfuellte Teilaufgaben, Teilaufgaben mit Pflicht, ok, Pflichtpruefungen)."""
    mit_pflicht = [t for t in szenario.teilaufgaben
                   if any(p.art == "soll" for p in t.pruefungen)]
    pflicht = soll_pruefungen(szenario)
    return (sum(1 for t in mit_pflicht if teil_erfuellt(t, karte)),
            len(mit_pflicht),
            sum(1 for p in pflicht if stimmt(p, karte.get(p.id))),
            len(pflicht))


def offene_teile(szenarien, karte):
    """[(Szenario, Teilaufgabe, [(Pruefung, Wert)])] fuer alles, was nicht stimmt."""
    offen = []
    for s in szenarien:
        if s.status == "nicht_umgesetzt":
            continue
        for t in s.teilaufgaben:
            luecken = [(p, karte.get(p.id)) for p in t.pruefungen
                       if p.art == "soll" and not stimmt(p, karte.get(p.id))]
            if luecken:
                offen.append((s, t, luecken))
    return offen


def abweichende_befunde(szenarien, karte):
    """Befunde, die sich nicht mehr reproduzieren lassen."""
    return [(s, p) for s in szenarien for p in befund_pruefungen(s)
            if not stimmt(p, karte.get(p.id))]


# --- Formatierung -----------------------------------------------------------

KOPF = ("Szenario", "Pruefung", "erwartet", "gefunden", "Status")
KOPF_SZENARIEN = ("Szenario", "Teilaufgaben", "Pruefungen", "Status")


def _tabelle(kopf, zeilen, rechts=()) -> str:
    """Feste Spaltenbreiten, damit sich Soll und Ist untereinander lesen lassen."""
    breiten = [max(len(kopf[i]), *(len(z[i]) for z in zeilen)) if zeilen
               else len(kopf[i]) for i in range(len(kopf))]

    def ausgeben(spalten):
        return "  ".join(
            wert.rjust(breiten[i]) if i in rechts else wert.ljust(breiten[i])
            for i, wert in enumerate(spalten)).rstrip()

    ausgabe = [ausgeben(kopf), "  ".join("-" * b for b in breiten)]
    ausgabe.extend(ausgeben(z) for z in zeilen)
    return "\n".join(ausgabe)


def formatiere_tabelle(ergebnisse) -> str:
    """Die Pruefungen einzeln, eine Zeile je Messung."""
    zeilen = [(p.szenario, p.beschreibung, tausender(p.erwartet),
               tausender(g), status_von(p, g)) for p, g in ergebnisse]
    # Die Spaltenbreiten richten sich am laengsten Eintrag aus, aber jede Zeile
    # wird auf dieselbe Breite gebracht: der Test darauf haelt die Ausgabe in
    # Doku und Praesentation stabil.
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


def formatiere_szenarien(szenarien, karte) -> str:
    """Die Kernausgabe: ein Urteil je Szenario."""
    breite = max((len(s.kuerzel) for s in szenarien), default=4)
    zeilen = []
    for s in szenarien:
        if s.status == "nicht_umgesetzt":
            teile, pruefungen = "-", "-"
        else:
            teil_ok, teil_alle, pruef_ok, pruef_alle = zaehle(s, karte)
            teile = f"{teil_ok}/{teil_alle}"
            pruefungen = f"{pruef_ok}/{pruef_alle}"
        zeilen.append((f"{s.kuerzel:<{breite}}  {s.titel}", teile, pruefungen,
                       szenario_urteil(s, karte)))
    return _tabelle(KOPF_SZENARIEN, zeilen, rechts=(1, 2))


def formatiere_offen(szenarien, karte) -> str:
    """Nur was fehlt, gruppiert nach Szenario und Teilaufgabe, mit Kommando."""
    offen = offene_teile(szenarien, karte)
    if not offen:
        return ""
    zeilen = ["Offen:"]
    for szenario, teilaufgabe, luecken in offen:
        zeilen.append(f"\n  {szenario.kuerzel}  {teilaufgabe.name}")
        for pruefung, gefunden in luecken:
            zeilen.append(f"      {pruefung.beschreibung:<48}"
                          f" erwartet {tausender(pruefung.erwartet):>9}"
                          f"   gefunden {tausender(gefunden):>9}")
        if teilaufgabe.befehl:
            zeilen.append(f"      -> {teilaufgabe.befehl}")
    return "\n".join(zeilen)


def formatiere_befunde(szenarien, karte) -> str:
    """Die dokumentierten Fehlschlaege, getrennt von den Sollzustaenden.

    Sie stehen unter einer eigenen Ueberschrift, damit niemand ein "0 Bilder
    uebertragen" fuer einen Mangel des Aufbaus haelt, und niemand ein Szenario
    fuer erfuellt, weil daneben ein ok steht.
    """
    zeilen = []
    for s in szenarien:
        for p in befund_pruefungen(s):
            gefunden = karte.get(p.id)
            zeilen.append((f"{s.kuerzel}  {p.beschreibung}",
                           tausender(p.erwartet) + (" oder mehr"
                                                    if p.vergleich == "mindestens" else ""),
                           tausender(gefunden), status_von(p, gefunden),
                           p.beleg))
    if not zeilen:
        return ""
    kopf = ("Dokumentierter Befund", "erwartet", "gemessen", "Status", "Beleg")
    return ("Dokumentierte Befunde (erwartete Fehlschlaege, kein Mangel des Aufbaus):\n\n"
            + _tabelle(kopf, zeilen, rechts=(1, 2)))


def teil_marke(teilaufgabe, karte) -> str:
    """ok | OFFEN | Befund.

    Eine Teilaufgabe, die nur Befunde enthaelt, ist nichts, das man erfuellt.
    Sie mit "ok" zu markieren liest sich wie ein erreichter Sollzustand.
    """
    if not any(p.art == "soll" for p in teilaufgabe.pruefungen):
        return "Befund"
    return "ok" if teil_erfuellt(teilaufgabe, karte) else "OFFEN"


def formatiere_detail(szenarien, karte) -> str:
    """Jede Pruefung einzeln, gruppiert wie die Definition."""
    bloecke = []
    for s in szenarien:
        kopf = f"{s.kuerzel}  {s.titel}\n     Ziel: {s.ziel}"
        if s.status == "nicht_umgesetzt":
            bloecke.append(f"{kopf}\n     nicht umgesetzt: {s.begruendung}")
            continue
        zeilen = [kopf]
        for t in s.teilaufgaben:
            zeilen.append(f"\n  [{teil_marke(t, karte):^6}] {t.name}")
            for p in t.pruefungen:
                gefunden = karte.get(p.id)
                zeilen.append(f"      {p.beschreibung:<52}"
                              f" {tausender(p.erwartet):>9}"
                              f" {tausender(gefunden):>9}"
                              f"   {status_von(p, gefunden)}")
        bloecke.append("\n".join(zeilen))
    return "\n\n".join(bloecke)


def urteil_zeile(szenarien, karte) -> str:
    """Die eine Zeile, die am Ende zaehlt."""
    geprueft = [s for s in szenarien if s.status != "nicht_umgesetzt"]
    erfuellt = [s for s in geprueft if szenario_urteil(s, karte) == "erfuellt"]
    offen = len(geprueft) - len(erfuellt)
    text = f"Szenarien: {len(erfuellt)} von {len(geprueft)} erfuellt"
    if offen:
        text += f", {offen} nicht erfuellt"
    nicht_umgesetzt = len(szenarien) - len(geprueft)
    if nicht_umgesetzt:
        text += f", {nicht_umgesetzt} nicht umgesetzt"
    return text + "."


def ratschlag(ergebnisse) -> str:
    """Was als naechstes zu tun ist, oder "" wenn alles stimmt.

    Zwei Fehlerbilder, die nach demselben aussehen: keine Messung kommt durch
    (dann laeuft der Stack nicht), oder einzelne Sollzustaende fehlen (dann fehlt
    ein Aufbauschritt). Der falsche Hinweis kostet in einer Demo Minuten.
    """
    offen = [(p, g) for p, g in ergebnisse if not stimmt(p, g)]
    if not offen:
        return ""
    if all(g is None for _, g in ergebnisse):
        return ("Keine einzige Messung kam durch. Laeuft der Stack?\n"
                "    docker ps\n"
                "    .\\scripts\\start.ps1      (Linux/macOS: bash scripts/start.sh)")
    return ("Die Kommandos je offener Teilaufgabe stehen oben. Den ganzen"
            " Demo-Zustand stellt her:\n"
            "    python scripts/setup_szenarien.py")


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


def zerlege_dateiabfrage(abfrage):
    """'anzahl:data/images' -> ('anzahl', 'data/images')."""
    was, _, pfad = abfrage.partition(":")
    if was not in ("anzahl", "bytes") or not pfad:
        raise ValueError(f"unbrauchbare Dateiabfrage: {abfrage}")
    return was, pfad


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


def postgrest_zeilen_quelle():
    """Anzahl der Datensaetze in der Antwort.

    PostgREST antwortet auch auf eine leere Tabelle mit HTTP 200. Der Statuscode
    allein belegt also nur, dass der Dienst laeuft, nicht dass er Daten liefert.
    """
    import requests

    def frage(pfad):
        antwort = requests.get(POSTGREST_URL.rstrip("/") + pfad, timeout=30)
        antwort.raise_for_status()
        return len(antwort.json())

    return frage


def dateien_quelle(wurzel=None):
    """Anzahl oder Gesamtgroesse der Dateien in einem Verzeichnis.

    Fuer Szenario 3, Teilaufgabe B: der Export schreibt ins Dateisystem, nicht
    in eine Datenbank. Ein fehlendes Verzeichnis wirft, damit messe() daraus ein
    "fehlt" macht statt einer stillen 0.
    """
    basis = wurzel or WURZEL

    def frage(abfrage):
        was, pfad = zerlege_dateiabfrage(abfrage)
        verzeichnis = os.path.join(basis, *pfad.split("/"))
        if not os.path.isdir(verzeichnis):
            raise FileNotFoundError(verzeichnis)
        dateien = [os.path.join(verzeichnis, n) for n in os.listdir(verzeichnis)]
        dateien = [d for d in dateien if os.path.isfile(d)]
        if was == "anzahl":
            return len(dateien)
        return sum(os.path.getsize(d) for d in dateien)

    return frage


def quellen():
    return {
        "source_pg": postgres_quelle(SOURCE_PG),
        "dest_pg": postgres_quelle(DEST_PG),
        "dest_mysql": mysql_quelle(),
        "postgrest": postgrest_quelle(),
        "postgrest_zeilen": postgrest_zeilen_quelle(),
        "dateien": dateien_quelle(),
    }


# --- Main -------------------------------------------------------------------

HILFE = """Aufruf: python scripts/pruefe_szenarien.py [Optionen] [Szenario ...]

    ohne Argumente   alle Szenarien pruefen
    Sz1 Sz3 Sz6a     nur die genannten
    --detail         jede einzelne Pruefung zeigen, nicht nur die offenen
    --leise          nur die Urteilszeile ausgeben

Ein Szenario gilt als erfuellt, wenn jede Pflichtpruefung jeder seiner
Teilaufgaben stimmt. Dokumentierte Befunde aus docs/ergebnisse.md werden
nachgemessen, zaehlen aber nicht gegen ein Szenario.

Exit-Code 0 wenn jedes gepruefte Szenario erfuellt ist, sonst 1.

Bekannte Szenarien:
""" + "\n".join(f"    {s.kuerzel:<6} {s.titel}" for s in SZENARIEN)


def main(argv):
    if any(a in ("-h", "--help") for a in argv):
        print(HILFE)
        return 0

    leise = "--leise" in argv
    detail = "--detail" in argv
    auswahl = [a for a in argv if not a.startswith("-")]

    szenarien = nur_szenario_objekte(SZENARIEN, auswahl)
    if not szenarien:
        print(f"Kein Szenario passt zu: {' '.join(auswahl)}")
        print("Bekannt: " + ", ".join(s.kuerzel for s in SZENARIEN))
        return 1

    ergebnisse = messe(alle_pruefungen(szenarien), quellen())
    karte = als_karte(ergebnisse)

    if not leise:
        print()
        print(formatiere_szenarien(szenarien, karte))
        print()

    print(urteil_zeile(szenarien, karte))

    if leise:
        return 0 if not offene_teile(szenarien, karte) else 1

    if detail:
        print()
        print(formatiere_detail(szenarien, karte))

    nicht_umgesetzt = [s for s in szenarien if s.status == "nicht_umgesetzt"]
    if nicht_umgesetzt:
        print()
        for s in nicht_umgesetzt:
            print(f"{s.kuerzel} nicht umgesetzt: {s.begruendung}")

    offen = formatiere_offen(szenarien, karte)
    if offen:
        print()
        print(offen)

    befunde = formatiere_befunde(szenarien, karte)
    if befunde:
        print()
        print(befunde)

    abweichend = abweichende_befunde(szenarien, karte)
    if abweichend:
        print("\nACHTUNG: diese Befunde reproduzieren nicht mehr."
              " Dann ist docs/ergebnisse.md veraltet:")
        for s, p in abweichend:
            print(f"    {s.kuerzel}  {p.beschreibung}  ({p.beleg})")

    if offen:
        hinweis = ratschlag(ergebnisse)
        if hinweis:
            print("\n" + hinweis)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
