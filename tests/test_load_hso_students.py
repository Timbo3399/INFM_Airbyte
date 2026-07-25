"""Tests fuer scripts/load_hso_students.py.

Der Kern ist der quote-bewusste Pipe-Parser. hso_students.csv ist
pipe-getrennt, und das Feld stg_key ist gequotet und enthaelt selbst Pipes
("84|LH|-|-|H|20221|2|P|V|1|"). Ein naiver Split an '|' liefert deshalb mehr
Felder als der Header mit seinen 40 Spalten vorgibt, und daran scheitert ein
direktes PostgreSQL-COPY. Genau das ist hier festgehalten.
"""
import os

import pytest

import load_hso_students as h

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(WURZEL, "sql", "source", "data", "hso_students.csv")


# --- der Parser gegen die echte Datei ---------------------------------------

@pytest.fixture(scope="module")
def zeilen():
    if not os.path.exists(CSV):
        pytest.skip(f"{CSV} fehlt")
    return h.read_rows(CSV)


def test_read_rows_liefert_header_plus_5052_datenzeilen(zeilen):
    assert len(zeilen) == 5053


def test_read_rows_liefert_fuer_jede_zeile_exakt_40_felder(zeilen):
    abweichend = [(i, len(r)) for i, r in enumerate(zeilen) if len(r) != len(h.COLS)]
    assert abweichend == []


def test_die_tabelle_hat_40_spalten():
    assert len(h.COLS) == 40


def test_erste_zeile_ist_der_header(zeilen):
    assert zeilen[0][0].strip().strip('"') == "mtknr"


def test_ein_naiver_split_wuerde_scheitern(zeilen):
    """Der Beleg dafuer, dass der quote-bewusste Parser noetig ist.

    Faellt read_rows auf einen einfachen split('|') zurueck, kommen fuer die
    Datenzeilen bis zu 56 Felder heraus statt 40.
    """
    with open(CSV, "rb") as f:
        rohzeilen = f.read().decode("utf-8", errors="replace").splitlines()

    naiv_zu_breit = [z for z in rohzeilen if len(z.split("|")) > len(h.COLS)]

    assert len(naiv_zu_breit) > 5000


def test_stg_key_behaelt_seine_pipes(zeilen):
    # stg_key ist Spalte 25 (Index 24) und enthaelt in der Quelle Pipes.
    idx = h.COLS.index("stg_key")
    mit_pipe = [r[idx] for r in zeilen[1:] if "|" in (r[idx] or "")]

    assert mit_pipe, "kein stg_key mit Pipe gefunden, Testdatei geaendert?"


# --- der Parser gegen konstruierte Faelle -----------------------------------

def _schreibe(tmp_path, inhalt: bytes):
    pfad = tmp_path / "probe.csv"
    pfad.write_bytes(inhalt)
    return str(pfad)


def test_read_rows_haelt_gequotete_pipes_in_einem_feld_zusammen(tmp_path):
    pfad = _schreibe(tmp_path, b'"1"|"a|b|c"|"3"\n')

    assert h.read_rows(pfad) == [["1", "a|b|c", "3"]]


def test_read_rows_entfernt_nul_bytes(tmp_path):
    pfad = _schreibe(tmp_path, b'"1"|"a\x00b"\n')

    assert h.read_rows(pfad) == [["1", "ab"]]


def test_read_rows_liest_kaputte_bytes_ohne_abzubrechen(tmp_path):
    # errors="replace": ein einzelnes ungueltiges Byte darf den Lauf nicht kippen.
    pfad = _schreibe(tmp_path, b'"1"|"\xff"\n')

    zeilen = h.read_rows(pfad)

    assert len(zeilen) == 1 and len(zeilen[0]) == 2


# --- Konvertierungen --------------------------------------------------------

def test_clean_trimmt_und_macht_leeres_zu_none():
    assert h.clean("  abc  ") == "abc"
    assert h.clean("   ") is None
    assert h.clean("") is None
    assert h.clean(None) is None


def test_to_int_akzeptiert_float_formatierte_ganzzahlen():
    # Die Semesterfelder kommen als "11.000000" aus der Quelle.
    assert h.to_int("11.000000") == 11


def test_to_int_liest_normale_ganzzahlen():
    assert h.to_int("176594") == 176594


def test_to_int_gibt_none_statt_zu_werfen():
    assert h.to_int("keine zahl") is None
    assert h.to_int("") is None
    assert h.to_int(None) is None


def test_to_date_nimmt_die_ersten_zehn_zeichen():
    import datetime
    assert h.to_date("2001-04-17 00:00:00") == datetime.date(2001, 4, 17)
    assert h.to_date("2001-04-17") == datetime.date(2001, 4, 17)


def test_to_date_gibt_none_bei_unbrauchbarem_wert():
    assert h.to_date("17.04.2001") is None
    assert h.to_date("") is None


def test_to_ts_liest_den_zeitstempel_der_quelle():
    import datetime
    assert h.to_ts("2026-03-30 11:10:59") == datetime.datetime(2026, 3, 30, 11, 10, 59)


def test_to_ts_gibt_none_bei_abweichendem_format():
    assert h.to_ts("2026-03-30T11:10:59") is None
    assert h.to_ts(None) is None


# --- convert waehlt nach Spaltenindex ---------------------------------------

def test_convert_macht_aus_mtknr_eine_zahl():
    assert h.convert(h.COLS.index("mtknr"), "176594") == 176594


def test_convert_macht_aus_dem_semester_eine_zahl():
    assert h.convert(h.COLS.index("universitysemester"), "11.000000") == 11


def test_convert_macht_aus_dateofbirth_ein_datum():
    import datetime
    idx = h.COLS.index("dateofbirth")
    assert h.convert(idx, "2001-04-17") == datetime.date(2001, 4, 17)


def test_convert_macht_aus_updatedat_einen_zeitstempel():
    import datetime
    idx = h.COLS.index("updatedat")
    assert h.convert(idx, "2026-03-30 11:10:59") == datetime.datetime(
        2026, 3, 30, 11, 10, 59)


def test_convert_laesst_textspalten_text():
    idx = h.COLS.index("surname")
    assert h.convert(idx, "  Mustermann  ") == "Mustermann"


def test_convert_belaesst_stg_key_als_text_mit_pipes():
    idx = h.COLS.index("stg_key")
    assert h.convert(idx, "84|LH|-|-|H|20221|2|P|V|1|") == "84|LH|-|-|H|20221|2|P|V|1|"


# --- Indexmengen passen zu den Spaltennamen ---------------------------------

def test_die_typindizes_zeigen_auf_die_gemeinten_spalten():
    assert h.INT_IDX == {h.COLS.index("mtknr")}
    assert h.DATE_IDX == {h.COLS.index("dateofbirth")}
    assert h.TS_IDX == {h.COLS.index("createdat"), h.COLS.index("updatedat")}
    assert h.FLOATINT_IDX == {
        h.COLS.index("universitysemester"), h.COLS.index("kollegsemester"),
        h.COLS.index("practicalsemester"), h.COLS.index("leavesemester"),
        h.COLS.index("studysemester"), h.COLS.index("curriculumsemester")}


def test_stg_key_ist_im_ddl_auf_50_zeichen_geweitet():
    # Werte sind bis 27 Zeichen lang, VARCHAR(20) aus dem alten Schema reicht nicht.
    assert "stg_key           VARCHAR(50)" in h.DDL_HSO_STUDENTS
