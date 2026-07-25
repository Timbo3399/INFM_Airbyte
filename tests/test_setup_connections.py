"""Tests fuer die reinen Funktionen in scripts/airbyte/setup_connections.py."""
import setup_connections as c


def test_stream_fuer_full_refresh_braucht_weder_cursor_noch_pk():
    s = c.stream("fm_gebaeude", c.FULL_REFRESH)
    assert s == {"name": "fm_gebaeude", "syncMode": "full_refresh_overwrite"}


def test_stream_fuer_incremental_dedup_traegt_cursor_und_pk():
    s = c.stream("hso_user", c.INCREMENTAL_DEDUP, cursor="updatedat", pk="user_id")
    assert s["syncMode"] == "incremental_deduped_history"
    assert s["cursorField"] == ["updatedat"]
    assert s["primaryKey"] == [["user_id"]]


def test_dedup_ohne_primaerschluessel_ist_ein_fehler():
    # Airbyte lehnt den Modus sonst ab, das soll frueh und deutlich knallen.
    try:
        c.stream("hso_user", c.INCREMENTAL_DEDUP, cursor="updatedat")
    except ValueError as e:
        assert "primaryKey" in str(e) or "Primaerschluessel" in str(e)
    else:
        raise AssertionError("ValueError erwartet")


def test_dedup_ohne_cursor_ist_ein_fehler():
    try:
        c.stream("hso_user", c.INCREMENTAL_DEDUP, pk="user_id")
    except ValueError as e:
        assert "cursor" in str(e).lower()
    else:
        raise AssertionError("ValueError erwartet")


def test_connection_payload_setzt_manuellen_zeitplan():
    p = c.connection_payload("X", "s-1", "d-1", [c.stream("a", c.FULL_REFRESH)])
    assert p["sourceId"] == "s-1"
    assert p["destinationId"] == "d-1"
    assert p["schedule"] == {"scheduleType": "manual"}
    assert p["configurations"]["streams"][0]["name"] == "a"


def test_connection_payload_uebernimmt_alle_streams():
    streams = [c.stream("a", c.FULL_REFRESH), c.stream("b", c.FULL_REFRESH)]
    p = c.connection_payload("X", "s-1", "d-1", streams)
    assert [s["name"] for s in p["configurations"]["streams"]] == ["a", "b"]


# --- Kein Stream darf zwei Besitzer haben -----------------------------------

SRC = {"HSO Source PostgreSQL": "s-pg", "HSO CSV hso_students": "s-csv",
       "HSO Transform PostgreSQL": "s-tr"}
DST = {"HSO Dest PostgreSQL": "d-pg", "HSO Dest MySQL": "d-my"}


def test_keine_zwei_connections_schreiben_denselben_stream_in_dasselbe_ziel():
    """Sonst verdoppelt sich die Zieltabelle beim ersten Aufbau.

    Full Refresh Overwrite erhoeht die _airbyte_generation_id und loescht nur
    echt aeltere Generationen. Der Zaehler laeuft pro Connection und Stream.
    Schreiben zwei Connections denselben Stream in dieselbe Zieltabelle, stehen
    beim ersten Lauf beide auf Generation 1: keine raeumt die Zeilen der
    anderen weg. Nachgemessen an fm_gebaeude in dest-postgres, 25 Zeilen wurden
    zu 50. Erst ein zweiter Lauf derselben Connection (Generation 2) hat
    aufgeraeumt.
    """
    besitzer = {}
    doppelt = []
    for name, (_, destination_id, streams) in c.gewuenschte_connections(
            SRC, DST).items():
        for s in streams:
            schluessel = (destination_id, s["name"])
            if schluessel in besitzer:
                doppelt.append((s["name"], destination_id,
                                besitzer[schluessel], name))
            besitzer[schluessel] = name

    assert doppelt == []


# --- Streams, die es noch nicht gibt ----------------------------------------
#
# fm_raeume entsteht erst durch dbt, also nach dem Anlegen der Connections.
# Airbyte antwortet dann mit "No streams found with name [fm_raeume]" (Befund 25
# in docs/ergebnisse.md: der Stream-Katalog einer Source ist zwischengespeichert).
# Das darf den Aufbau nicht abbrechen, die Connection wird spaeter nachgezogen.

def test_erkennt_einen_noch_fehlenden_stream():
    antwort = ('POST /connections -> HTTP 400: {"message":"No streams found with'
               ' name [fm_raeume] and namespace [null]"}')

    assert c.stream_fehlt_noch(antwort) is True


def test_erkennt_fehlenden_stream_auch_ohne_klammern():
    assert c.stream_fehlt_noch("No streams found with name fm_raeume") is True


def test_haelt_einen_echten_fehler_nicht_fuer_einen_fehlenden_stream():
    # Ein Pflichtfeld-Fehler muss laut knallen und nicht vertagt werden.
    antwort = ("POST /connections -> HTTP 422: required property"
               " 'tunnel_method' not found")

    assert c.stream_fehlt_noch(antwort) is False


def test_leere_antwort_ist_kein_fehlender_stream():
    assert c.stream_fehlt_noch("") is False
    assert c.stream_fehlt_noch(None) is False


def test_katalog_meldung_unterscheidet_leer_von_unlesbar():
    # Beim ersten Aufbau ist dest-postgres schlicht leer. Das ist etwas anderes
    # als eine gescheiterte Erkennung und darf nicht so aussehen.
    leer = c.katalog_meldung("HSO Transform PostgreSQL", [])
    unlesbar = c.katalog_meldung("HSO Transform PostgreSQL", None)

    assert "leer" in leer
    assert "nicht lesbar" not in leer
    assert "nicht lesbar" in unlesbar


def test_katalog_meldung_nennt_die_anzahl_der_streams():
    meldung = c.katalog_meldung("HSO Source PostgreSQL", ["a", "b", "c"])

    assert "3" in meldung
    assert "HSO Source PostgreSQL" in meldung


def test_die_transform_source_wird_mit_aufgefrischt():
    # Ohne Auffrischung kennt Airbyte fm_raeume in dest-postgres nie, denn der
    # Katalog wurde beim Anlegen der Source gespeichert, als die Tabelle fehlte.
    assert "HSO Transform PostgreSQL" in c.AUFZUFRISCHENDE_SOURCES
    assert "HSO Source PostgreSQL" in c.AUFZUFRISCHENDE_SOURCES
