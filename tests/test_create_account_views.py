"""Tests fuer scripts/mapping/create_account_views.py (keine DB noetig).

Szenario 4, Schritt 3. Der Kern ist nicht das Skript, sondern die Namensgebung
der beiden Views: sie duerfen nicht wie ihre Quelltabellen heissen, sonst landet
der Sync in derselben Zieltabelle wie der File-Connector und verdoppelt sie
(Befund 27 in docs/ergebnisse.md).
"""
import os

import create_account_views as v

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _sql():
    with open(v.sql_pfad(WURZEL), encoding="utf-8") as f:
        return f.read()


# --- Pfad --------------------------------------------------------------------

def test_sql_pfad_haengt_die_view_datei_an_die_wurzel():
    assert v.sql_pfad("/projekt") == os.path.join(
        "/projekt", "sql", "source", "views", "hso_accounts.sql")


def test_sql_pfad_zeigt_auf_eine_vorhandene_datei():
    assert os.path.exists(v.sql_pfad(WURZEL))


# --- Namensgebung ------------------------------------------------------------

def test_beide_views_werden_angelegt():
    sql = _sql()

    for view in v.VIEWS:
        assert f"CREATE OR REPLACE VIEW {view}" in sql


def test_die_views_heissen_nicht_wie_ihre_quelltabellen():
    # Der eigentliche Zweck der Umbenennung. Faellt sie weg, kollidiert der Sync
    # mit hso_students aus dem File-Connector.
    assert "hso_students" not in v.VIEWS
    assert "hso_personal" not in v.VIEWS


def test_es_sind_genau_zwei_views_eine_je_gruppe():
    assert len(v.VIEWS) == 2
    assert len(set(v.VIEWS)) == 2


def test_die_view_namen_passen_zu_den_streams_der_connection():
    import setup_connections as c
    src = {"HSO Source PostgreSQL": "s", "HSO CSV hso_students": "s2",
           "HSO Transform PostgreSQL": "s3"}
    dst = {"HSO Dest PostgreSQL": "d", "HSO Dest MySQL": "d2"}

    _, _, streams = c.gewuenschte_connections(src, dst)["HSO Accounts nach PG"]

    assert sorted(s["name"] for s in streams) == sorted(v.VIEWS)


# --- Inhalt der Views --------------------------------------------------------

def test_die_studierenden_sicht_liest_hso_students():
    sql = _sql()
    abschnitt = sql.split("CREATE OR REPLACE VIEW hso_student_accounts")[1]
    abschnitt = abschnitt.split("CREATE OR REPLACE VIEW")[0]

    assert "FROM hso_students" in abschnitt
    assert "mtknr" in abschnitt


def test_die_personal_sicht_liest_hso_personal():
    sql = _sql()
    abschnitt = sql.split("CREATE OR REPLACE VIEW hso_personal_accounts")[1]

    assert "FROM hso_personal" in abschnitt
    assert "hso_email" in abschnitt


def test_beide_views_filtern_auf_gesetzte_user_id():
    # Ohne den Filter waeren die Views auch ohne generate_accounts.py gefuellt,
    # und die Skip-Erkennung in setup_szenarien.py wuerde falsch ueberspringen.
    sql = _sql()

    assert sql.count("COALESCE(s.user_id, '') <> ''") == 1
    assert sql.count("COALESCE(p.user_id, '') <> ''") == 1


def test_beide_views_fuehren_user_id_als_erste_spalte():
    # Der Account ist der Zweck dieser Tabellen, er gehoert nach vorn.
    for zeile in _sql().splitlines():
        if zeile.strip().startswith("s.user_id") or zeile.strip().startswith("p.user_id"):
            assert "AS user_id" in zeile
