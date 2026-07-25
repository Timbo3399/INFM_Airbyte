"""Tests fuer die reinen Funktionen in scripts/airbyte_setup_connections.py."""
import airbyte_setup_connections as c


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
