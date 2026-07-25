"""Tests fuer scripts/load_fm_inst.py.

fm_inst.csv laesst sich nicht per COPY laden: sie ist semikolon-getrennt, hat
86 Spalten, von denen die Tabelle die ersten 24 nutzt, und enthaelt vereinzelt
NUL-Bytes. An denen bricht COPY mit "invalid byte sequence for encoding UTF8"
ab. Beides ist hier festgehalten.
"""
import datetime
import os

import pytest

import load_fm_inst as fi

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(WURZEL, "sql", "source", "data", "fm_inst.csv")


# --- gegen die echte Datei --------------------------------------------------

@pytest.fixture(scope="module")
def zeilen():
    if not os.path.exists(CSV):
        pytest.skip(f"{CSV} fehlt")
    return fi.read_rows(CSV)


def test_read_rows_liefert_2083_datenzeilen(zeilen):
    assert len(zeilen) == 2083


def test_jede_datenzeile_hat_86_felder(zeilen):
    abweichend = [(i, len(r)) for i, r in enumerate(zeilen) if len(r) != 86]
    assert abweichend == []


def test_read_rows_ueberspringt_den_header(zeilen):
    # Der Header wuerde als db_einfuegemarke "db_einfuegemarke" mitkommen.
    assert zeilen[0][0].strip() != "db_einfuegemarke"


def test_die_datei_enthaelt_wirklich_nul_bytes():
    # Der Beleg fuer den Sonderfall. Faellt das weg, ist die Testdatei getauscht.
    with open(CSV, "rb") as f:
        assert f.read().count(b"\x00") > 0


def test_kein_feld_enthaelt_nach_dem_parsen_noch_ein_nul_byte(zeilen):
    uebrig = [f for r in zeilen for f in r if f and "\x00" in f]
    assert uebrig == []


def test_die_tabelle_nutzt_die_ersten_24_spalten():
    assert fi.N_COLS == 24


def test_inst_nr_ist_in_allen_zeilen_gesetzt(zeilen):
    # inst_nr ist NOT NULL. Wer hier leer ist, wird beim Laden uebersprungen.
    ohne = [i for i, r in enumerate(zeilen) if fi.clean(r[1]) is None]
    assert ohne == []


# --- gegen konstruierte Faelle ----------------------------------------------

def _schreibe(tmp_path, inhalt: bytes):
    pfad = tmp_path / "probe.csv"
    pfad.write_bytes(inhalt)
    return str(pfad)


def test_read_rows_entfernt_nul_bytes(tmp_path):
    pfad = _schreibe(tmp_path, b"kopf;zeile\nab\x00c;d\n")

    assert fi.read_rows(pfad) == [["abc", "d"]]


def test_read_rows_trennt_an_semikolon(tmp_path):
    pfad = _schreibe(tmp_path, b"kopf\na;b;c\n")

    assert fi.read_rows(pfad) == [["a", "b", "c"]]


def test_read_rows_achtet_auf_anfuehrungszeichen(tmp_path):
    pfad = _schreibe(tmp_path, b'kopf\n"a;b";c\n')

    assert fi.read_rows(pfad) == [["a;b", "c"]]


def test_read_rows_liefert_leere_liste_wenn_nur_der_header_da_ist(tmp_path):
    pfad = _schreibe(tmp_path, b"kopf;zeile\n")

    assert fi.read_rows(pfad) == []


# --- Konvertierungen --------------------------------------------------------

def test_clean_trimmt_die_aufgefuellten_werte():
    # Die Quelle ist stark mit Leerzeichen aufgefuellt.
    assert fi.clean("  Institut fuer X   ") == "Institut fuer X"


def test_clean_macht_aus_leer_none():
    assert fi.clean("      ") is None
    assert fi.clean("") is None
    assert fi.clean(None) is None


def test_to_decimal_akzeptiert_komma_als_dezimaltrenner():
    assert fi.to_decimal("1234,56") == 1234.56


def test_to_decimal_akzeptiert_punkt():
    assert fi.to_decimal("1234.56") == 1234.56


def test_to_decimal_gibt_none_statt_zu_werfen():
    assert fi.to_decimal("kein Betrag") is None
    assert fi.to_decimal("") is None
    assert fi.to_decimal(None) is None


def test_to_int_liest_ganzzahlen():
    assert fi.to_int(" 42 ") == 42


def test_to_int_gibt_none_bei_dezimalwert():
    # Anders als in load_hso_students: orgstruktur ist hier eine echte
    # Ganzzahl, ein "42.0" waere ein Datenfehler und soll NULL werden.
    assert fi.to_int("42.0") is None


def test_to_int_gibt_none_statt_zu_werfen():
    assert fi.to_int("abc") is None
    assert fi.to_int(None) is None


def test_to_date_liest_das_iso_datum_der_quelle():
    assert fi.to_date("2020-01-01") == datetime.date(2020, 1, 1)


def test_to_date_gibt_none_bei_deutschem_format():
    assert fi.to_date("01.01.2020") is None
    assert fi.to_date("") is None


# --- DDL passt zur Konvertierung -------------------------------------------

def test_das_ddl_hat_genau_24_spalten():
    # Zeilenweise zaehlen, nicht an Kommas trennen: DECIMAL(14,2) enthaelt selbst
    # eines und wuerde die Zaehlung um drei nach oben treiben.
    inhalt = fi.DDL_FM_INST.split("(", 1)[1].rsplit(");", 1)[0]
    spalten = [z.strip() for z in inhalt.splitlines() if z.strip()]

    assert len(spalten) == fi.N_COLS


def test_die_umsatzspalten_sind_dezimal():
    for spalte in ("bes_umsatz", "bes_vj_umsatz1", "bes_vj_umsatz2"):
        assert f"{spalte}" in fi.DDL_FM_INST
    assert fi.DDL_FM_INST.count("DECIMAL(14,2)") == 3


def test_inst_nr_ist_im_ddl_not_null():
    assert "inst_nr           VARCHAR(20)  NOT NULL" in fi.DDL_FM_INST
