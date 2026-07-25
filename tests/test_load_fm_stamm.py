"""Tests fuer die reinen Hilfsfunktionen in scripts/load_fm_stamm.py (keine DB noetig)."""
import os

import load_fm_stamm as S

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOMS = os.path.join(_ROOT, "sql", "source", "data", "rooms.xltx")


def zeile(geb_nr, ges_nr, raumid, flaeche=None):
    """Eine Sheet-Zeile in Spaltenreihenfolge (17 Spalten)."""
    werte = [geb_nr, ges_nr, raumid, None, flaeche] + [None] * 12
    return tuple(werte)


def test_clean_str_macht_aus_float_ganzzahlen_saubere_strings():
    assert S.clean_str(101.0) == "101"


def test_clean_str_trimmt_und_repariert_doppelte_kodierung():
    assert S.clean_str("  SanitÃ¤r  ") == "Sanitär"
    assert S.clean_str("   ") is None


def test_build_records_uebernimmt_gueltige_zeilen():
    data, dups, skipped = S.build_records([zeile("307", "0", "5")])
    assert (len(data), dups, skipped) == (1, 0, 0)


def test_build_records_ueberspringt_pk_duplikate():
    doppelt = [zeile("307", "0", "5"), zeile("307", "0", "5")]
    data, dups, skipped = S.build_records(doppelt)
    assert (len(data), dups, skipped) == (1, 1, 0)


def test_build_records_ueberspringt_zeilen_ohne_vollstaendigen_schluessel():
    data, dups, skipped = S.build_records([zeile(None, "0", "5")])
    assert (data, dups, skipped) == ([], 0, 1)


def test_build_records_ignoriert_komplett_leere_zeilen():
    data, _, skipped = S.build_records([tuple([None] * 17)])
    assert (data, skipped) == ([], 0)


def test_reale_quelle_ergibt_1244_zeilen():
    # rooms.xltx enthaelt 1245 Datenzeilen, davon ist genau eine eine
    # PK-Dublette (geb_nr 307, ges_nr 0, raumid 5). Geladen werden 1244.
    # Diese Zahl steht so in der Doku und wird hier festgenagelt.
    data, dups, skipped = S.build_records(S.read_rows(ROOMS))
    assert (len(data), dups, skipped) == (1244, 1, 0)
