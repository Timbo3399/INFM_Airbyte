"""Tests fuer die reinen Hilfsfunktionen in scripts/load_k_plz.py (keine DB noetig)."""
import load_k_plz


def test_demojibake_repariert_umlaute():
    # 'GebÃ¤ude' ist doppelt-kodiertes 'Gebäude'
    assert load_k_plz.demojibake("GebÃ¤ude") == "Gebäude"


def test_demojibake_laesst_saubere_strings_unveraendert():
    assert load_k_plz.demojibake("Hamburg") == "Hamburg"
    assert load_k_plz.demojibake(None) is None


def test_clean_trimmt_und_macht_leer_zu_none():
    assert load_k_plz.clean("  Kiel  ") == "Kiel"
    assert load_k_plz.clean("   ") is None
    assert load_k_plz.clean(None) is None


def test_normalize_fuellt_fehlende_felder_mit_none():
    row = ["a", "12345", "b"]
    result = load_k_plz.normalize(row)
    assert len(result) == load_k_plz.N_COLS
    assert result[:3] == ["a", "12345", "b"]
    assert result[3] is None


def test_normalize_fuehrt_ueberzaehlige_felder_zusammen():
    # 12 Felder -> letztes Textfeld (vv_bez) nimmt die ueberzaehligen Kommas auf
    row = [str(i) for i in range(12)]
    result = load_k_plz.normalize(row)
    assert len(result) == load_k_plz.N_COLS
    assert result[load_k_plz.VVBEZ_IDX] == "9,10,11"
