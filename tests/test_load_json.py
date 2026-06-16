"""Tests fuer die reinen Hilfsfunktionen in scripts/load_json.py (keine DB noetig)."""
import json
from datetime import datetime, date

import load_json


def test_strip_row_entfernt_leerzeichen():
    row = {"a": "  hallo  ", "b": 42, "c": None}
    assert load_json.strip_row(row) == {"a": "hallo", "b": 42, "c": None}


def test_parse_ts_gueltig():
    assert load_json.parse_ts("2024-05-17 13:45:00") == datetime(2024, 5, 17, 13, 45, 0)


def test_parse_ts_leer_oder_none():
    assert load_json.parse_ts("") is None
    assert load_json.parse_ts(None) is None


def test_parse_ts_ungueltig_gibt_none():
    assert load_json.parse_ts("kein datum") is None


def test_parse_date_gueltig():
    assert load_json.parse_date("2024-05-17") == date(2024, 5, 17)


def test_parse_date_leer_oder_ungueltig():
    assert load_json.parse_date("") is None
    assert load_json.parse_date(None) is None
    assert load_json.parse_date("17.05.2024") is None


def test_load_json_file_liest_wert_des_ersten_keys(tmp_path):
    # Die Quelldateien haben die Struktur {"<SQL-QUERY>": [ {...}, {...} ]}
    p = tmp_path / "beispiel.json"
    p.write_text(json.dumps({"SELECT * FROM x": [{"id": 1}, {"id": 2}]}), encoding="utf-8")
    assert load_json.load_json_file(str(p)) == [{"id": 1}, {"id": 2}]
