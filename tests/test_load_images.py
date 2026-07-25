"""Tests fuer scripts/images/load_images.py (keine DB, kein Netz noetig).

Kern der Sache ist die Fehlertrennung: ein nicht erreichbares Bild darf den Lauf
nicht stoppen, ein Datenbankfehler dagegen schon. Vorher fing ein einziges
except beides ab. Weil psycopg2 nach einem Fehler die Transaktion abbricht,
scheiterten danach alle weiteren Inserts still, waehrend der Zaehler weiterlief.
Am Ende stand eine Erfolgsmeldung ueber einer halbleeren Tabelle.
"""
import pytest

import load_images as li


class FakeAntwort:
    def __init__(self, status_code, content=b""):
        self.status_code = status_code
        self.content = content


class FakeSession:
    """Liefert vorgegebene Antworten oder wirft, was ihr mitgegeben wurde."""

    def __init__(self, antwort=None, fehler=None):
        self.antwort, self.fehler = antwort, fehler
        self.aufrufe = []

    def get(self, url, timeout=None):
        self.aufrufe.append(url)
        if self.fehler:
            raise self.fehler
        return self.antwort


class FakeCursor:
    def __init__(self, fehler=None, rowcount=1):
        self.fehler, self.rowcount = fehler, rowcount
        self.ausgefuehrt = []

    def execute(self, sql, params=None):
        if self.fehler:
            raise self.fehler
        self.ausgefuehrt.append((sql, params))


# --- URL ----------------------------------------------------------------------

def test_seed_url_nutzt_seed_und_nicht_id():
    # /id/<n> liefert fuer viele Nummern 404, damit kamen wir nie ueber 1.000.
    url = li.seed_url(7)
    assert "/seed/hso7/" in url
    assert "/id/" not in url


def test_seed_url_ist_fuer_dieselbe_nummer_stabil():
    assert li.seed_url(42) == li.seed_url(42)


# --- HTTP-Fehler: ueberspringen -----------------------------------------------

def test_bild_wird_bei_status_200_geliefert():
    s = FakeSession(FakeAntwort(200, b"PNGDATEN"))
    assert li.fetch_image(s, 1) == b"PNGDATEN"


def test_status_ungleich_200_ergibt_none():
    s = FakeSession(FakeAntwort(404))
    assert li.fetch_image(s, 1) is None


def test_netzwerkfehler_wird_geschluckt_und_ergibt_none():
    s = FakeSession(fehler=OSError("Verbindung weg"))
    assert li.fetch_image(s, 1) is None


# --- DB-Fehler: durchreichen --------------------------------------------------

def test_store_image_zaehlt_eingefuegte_zeilen():
    cur = FakeCursor(rowcount=1)
    assert li.store_image(cur, "1", b"daten") == 1


def test_store_image_zaehlt_konflikt_nicht_mit():
    # ON CONFLICT DO NOTHING liefert rowcount 0, das ist kein Fehler.
    cur = FakeCursor(rowcount=0)
    assert li.store_image(cur, "1", b"daten") == 0


def test_datenbankfehler_wird_nicht_verschluckt():
    # Der eigentliche Bug: hier wurde frueher nur eine Zeile ausgegeben und
    # weitergemacht, obwohl die Transaktion tot war.
    cur = FakeCursor(fehler=RuntimeError("current transaction is aborted"))
    with pytest.raises(RuntimeError):
        li.store_image(cur, "1", b"daten")
