"""Tests fuer scripts/load_lookups.py.

Zwei Besonderheiten stehen im Mittelpunkt:

  * k_res kommt als acht Dateien (k_res1 bis k_res13) und wird in EINE Tabelle
    konsolidiert. Der Diskriminator res_typ steckt nur im Dateinamen, nicht in
    den Daten.
  * Die HISinOne-Schluesseltabellen sind mit Leerzeichen aufgefuellt und
    enthalten doppelt kodierte Umlaute.
"""
import datetime
import glob
import os

import pytest

import load_lookups as l

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
K_RES_MUSTER = os.path.join(WURZEL, "data", "csv", "k_res", "k_res*.csv")


# --- res_typ steckt im Dateinamen -------------------------------------------

def test_res_typ_aus_einstelligem_dateinamen():
    assert l.res_typ_aus_dateiname("k_res1_202603301110.csv") == "1"


def test_res_typ_aus_zweistelligem_dateinamen():
    assert l.res_typ_aus_dateiname("k_res13_202603301110.csv") == "13"


def test_res_typ_findet_sich_auch_im_vollen_pfad():
    assert l.res_typ_aus_dateiname(
        os.path.join("data", "csv", "k_res", "k_res12_202603301110.csv")) == "12"


def test_res_typ_ist_fragezeichen_wenn_der_name_nicht_passt():
    # Lieber ein sichtbares "?" in der Tabelle als ein Abbruch mitten im Laden.
    assert l.res_typ_aus_dateiname("irgendwas.csv") == "?"


def test_res_typ_verlangt_den_unterstrich_nach_der_nummer():
    assert l.res_typ_aus_dateiname("k_res13.csv") == "?"


def test_die_acht_echten_dateien_ergeben_die_erwarteten_typen():
    dateien = sorted(glob.glob(K_RES_MUSTER))
    if not dateien:
        pytest.skip("k_res-Dateien fehlen")

    typen = {l.res_typ_aus_dateiname(p) for p in dateien}

    assert typen == {"1", "2", "3", "4", "5", "11", "12", "13"}


# --- Konsolidierung: Dubletten pro (res_typ, res) ---------------------------

def test_sammle_k_res_uebernimmt_die_fuenf_spalten():
    zeilen = [["A", "x", "kurz", "druck", "lang"]]

    daten, dubletten = l.sammle_k_res("1", zeilen, set())

    assert daten == [("1", "A", "x", "kurz", "druck", "lang")]
    assert dubletten == 0


def test_sammle_k_res_zaehlt_eine_dublette_und_nimmt_sie_nicht_auf():
    zeilen = [["A", "x", "", "", ""], ["A", "y", "", "", ""]]

    daten, dubletten = l.sammle_k_res("1", zeilen, set())

    assert len(daten) == 1
    assert dubletten == 1


def test_sammle_k_res_haelt_denselben_schluessel_unter_zwei_typen_auseinander():
    # res "A" darf in k_res1 und in k_res2 vorkommen, der PK ist (res_typ, res).
    gesehen = set()
    erste, _ = l.sammle_k_res("1", [["A", "", "", "", ""]], gesehen)
    zweite, dubletten = l.sammle_k_res("2", [["A", "", "", "", ""]], gesehen)

    assert len(erste) == 1 and len(zweite) == 1
    assert dubletten == 0


def test_sammle_k_res_ueberspringt_zeilen_ohne_schluessel():
    daten, _ = l.sammle_k_res("1", [["   ", "x", "", "", ""]], set())

    assert daten == []


def test_sammle_k_res_ueberspringt_ganz_leere_zeilen():
    daten, _ = l.sammle_k_res("1", [[], ["", "", ""]], set())

    assert daten == []


def test_sammle_k_res_fuellt_zu_kurze_zeilen_auf():
    daten, _ = l.sammle_k_res("1", [["A"]], set())

    assert daten == [("1", "A", None, None, None, None)]


def test_sammle_k_res_schneidet_zu_lange_zeilen_ab():
    daten, _ = l.sammle_k_res("1", [["A", "b", "c", "d", "e", "ueberzaehlig"]], set())

    assert daten == [("1", "A", "b", "c", "d", "e")]


def test_sammle_k_res_traegt_die_schluessel_in_die_uebergebene_menge_ein():
    gesehen = set()
    l.sammle_k_res("7", [["A", "", "", "", ""]], gesehen)

    assert ("7", "A") in gesehen


def test_die_echten_k_res_dateien_ergeben_97_zeilen():
    dateien = sorted(glob.glob(K_RES_MUSTER))
    if not dateien:
        pytest.skip("k_res-Dateien fehlen")

    gesehen, gesamt, dubletten = set(), 0, 0
    for pfad in dateien:
        _, zeilen = l.read_csv(pfad, ";")
        daten, dup = l.sammle_k_res(l.res_typ_aus_dateiname(pfad), zeilen, gesehen)
        gesamt += len(daten)
        dubletten += dup

    assert (gesamt, dubletten) == (97, 0)


# --- Zeilenbreite normalisieren --------------------------------------------

def test_auf_breite_fuellt_mit_none_auf():
    assert l.auf_breite(["a"], 3) == ["a", None, None]


def test_auf_breite_schneidet_ueberzaehlige_felder_ab():
    assert l.auf_breite(["a", "b", "c", "d"], 3) == ["a", "b", "c"]


def test_auf_breite_laesst_passende_zeilen_unveraendert():
    assert l.auf_breite(["a", "b"], 2) == ["a", "b"]


def test_auf_breite_macht_aus_einer_leeren_zeile_lauter_none():
    assert l.auf_breite([], 2) == [None, None]


# --- read_csv ---------------------------------------------------------------

def _schreibe(tmp_path, inhalt: bytes):
    pfad = tmp_path / "probe.csv"
    pfad.write_bytes(inhalt)
    return str(pfad)


def test_read_csv_trennt_header_und_daten(tmp_path):
    pfad = _schreibe(tmp_path, b"a;b\n1;2\n3;4\n")

    header, zeilen = l.read_csv(pfad, ";")

    assert header == ["a", "b"]
    assert zeilen == [["1", "2"], ["3", "4"]]


def test_read_csv_entfernt_nul_bytes(tmp_path):
    pfad = _schreibe(tmp_path, b"a;b\n1\x002;3\n")

    _, zeilen = l.read_csv(pfad, ";")

    assert zeilen == [["12", "3"]]


def test_read_csv_beachtet_den_uebergebenen_trenner(tmp_path):
    pfad = _schreibe(tmp_path, b"a,b\n1,2\n")

    header, zeilen = l.read_csv(pfad, ",")

    assert header == ["a", "b"] and zeilen == [["1", "2"]]


def test_read_csv_achtet_auf_anfuehrungszeichen(tmp_path):
    pfad = _schreibe(tmp_path, b'a;b\n"1;2";3\n')

    _, zeilen = l.read_csv(pfad, ";")

    assert zeilen == [["1;2", "3"]]


def test_die_echten_lookup_dateien_haben_die_erwartete_spaltenzahl():
    fuer = {"anredetitel.csv": (";", 18), "k_hochschule.csv": (",", 16)}
    for name, (trenner, spalten) in fuer.items():
        pfad = os.path.join(WURZEL, "data", "csv", name)
        if not os.path.exists(pfad):
            pytest.skip(f"{name} fehlt")
        header, _ = l.read_csv(pfad, trenner)
        assert len(header) == spalten, f"{name}: {len(header)} Spalten"


# --- Konvertierungen --------------------------------------------------------

def test_demojibake_repariert_doppelt_kodierte_umlaute():
    assert l.demojibake("GebÃ¤ude") == "Gebäude"


def test_demojibake_laesst_saubere_texte_in_ruhe():
    assert l.demojibake("Gebäude") == "Gebäude"
    assert l.demojibake("Institut") == "Institut"


def test_demojibake_gibt_nicht_texte_unveraendert_zurueck():
    assert l.demojibake(None) is None
    assert l.demojibake(7) == 7


def test_clean_trimmt_und_repariert_in_einem_schritt():
    assert l.clean("   PrÃ¼fungsamt   ") == "Prüfungsamt"


def test_clean_laesst_unvollstaendige_sequenzen_stehen():
    # Ein einzelnes "Â" ist keine vollstaendige UTF-8-Sequenz. Lieber den Wert
    # unveraendert durchlassen als beim Dekodieren abbrechen.
    assert l.clean("  ProfessorÂ  ") == "ProfessorÂ"


def test_clean_macht_aus_leer_none():
    assert l.clean("    ") is None
    assert l.clean(None) is None


def test_to_int_akzeptiert_float_formatierte_werte():
    assert l.to_int("3.000000") == 3


def test_to_int_gibt_none_statt_zu_werfen():
    assert l.to_int("keine Zahl") is None
    assert l.to_int("") is None


def test_to_date_liest_iso_und_schneidet_die_zeit_ab():
    assert l.to_date("1900-01-01 00:00:00") == datetime.date(1900, 1, 1)


def test_to_date_gibt_none_bei_unbrauchbarem_wert():
    assert l.to_date("31.12.9999") is None
    assert l.to_date(None) is None


# --- Indexmengen zeigen auf die gemeinten Spalten ---------------------------

def test_die_datumsspalten_von_anredetitel_sind_key_von_und_key_bis():
    assert l.ANREDETITEL_DATE == {9, 10}


def test_die_datumsspalten_von_k_hochschule_sind_key_von_und_key_bis():
    assert l.K_HOCHSCHULE_DATE == {7, 8}


def test_k_res_hat_den_zusammengesetzten_primaerschluessel():
    assert "PRIMARY KEY (res_typ, res)" in l.DDL_K_RES
