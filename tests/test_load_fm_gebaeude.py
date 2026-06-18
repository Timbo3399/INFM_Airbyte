"""Tests fuer die reinen Hilfsfunktionen in scripts/load_fm_gebaeude.py (keine DB noetig)."""
import load_fm_gebaeude as g


def test_to_int_gueltig_und_ungueltig():
    assert g.to_int(" 42 ") == 42
    assert g.to_int("abc") is None
    assert g.to_int("") is None
    assert g.to_int(None) is None


def test_to_decimal_akzeptiert_komma_als_dezimaltrenner():
    assert g.to_decimal("3,14") == 3.14
    assert g.to_decimal("10") == 10.0
    assert g.to_decimal("keine zahl") is None
    assert g.to_decimal(None) is None


def test_clean_repariert_umlaute_und_trimmt():
    assert g.clean("  GebÃ¤ude  ") == "Gebäude"
    assert g.clean("   ") is None


def test_normalize_fuellt_auf_26_felder_auf():
    row = ["x"]
    result = g.normalize(row)
    assert len(result) == g.N_COLS


def test_normalize_fuehrt_unquotierte_kommas_in_geb2_zusammen():
    # geb2 (Index 3) soll die ueberzaehligen Felder aufnehmen, Rest bleibt korrekt
    row = [str(i) for i in range(28)]  # 2 Felder zu viel
    result = g.normalize(row)
    assert len(result) == g.N_COLS
    assert result[g.GEB2_IDX] == "3,4,5"
    # Feld direkt nach geb2 muss das urspruengliche Feld 6 sein
    assert result[g.GEB2_IDX + 1] == "6"
