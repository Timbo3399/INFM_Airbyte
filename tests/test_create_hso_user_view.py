"""Tests fuer scripts/mapping/create_hso_user_view.py (keine DB noetig).

Das Skript ist duenn: es fuehrt sql/source/views/hso_user.sql aus. Genau daran
haengt aber die Reihenfolge des Aufbaus, denn die View liest hso_images. Geprueft
wird deshalb, dass der Pfad stimmt und dass die SQL-Datei die Voraussetzungen
nennt, auf die setup_szenarien.py sich verlaesst.
"""
import os

import create_hso_user_view as v

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_sql_pfad_haengt_die_view_datei_an_die_wurzel():
    assert v.sql_pfad("/projekt") == os.path.join(
        "/projekt", "sql", "source", "views", "hso_user.sql")


def test_sql_pfad_zeigt_auf_eine_vorhandene_datei():
    # Faellt an, sobald die SQL-Datei verschoben oder umbenannt wird.
    assert os.path.exists(v.sql_pfad(WURZEL))


def test_die_view_definition_legt_hso_user_an():
    with open(v.sql_pfad(WURZEL), encoding="utf-8") as f:
        sql = f.read()

    assert "CREATE OR REPLACE VIEW hso_user" in sql


def test_die_view_liest_die_drei_erwarteten_tabellen():
    with open(v.sql_pfad(WURZEL), encoding="utf-8") as f:
        sql = f.read()

    for tabelle in ("hso_students", "hso_personal", "hso_images"):
        assert tabelle in sql, f"{tabelle} fehlt in der View-Definition"


def test_die_view_filtert_auf_gesetzte_user_id():
    # Ohne diesen Filter waere die View auch ohne generate_accounts.py gefuellt,
    # und die Skip-Erkennung in setup_szenarien.py wuerde falsch ueberspringen.
    with open(v.sql_pfad(WURZEL), encoding="utf-8") as f:
        sql = f.read()

    assert "COALESCE(s.user_id, '') <> ''" in sql
    assert "COALESCE(p.user_id, '') <> ''" in sql


def test_die_view_nutzt_updatedat_als_cursor_spalte():
    # Cursor des Incremental-Syncs in Szenario 5.
    with open(v.sql_pfad(WURZEL), encoding="utf-8") as f:
        sql = f.read()

    assert "updatedat" in sql
