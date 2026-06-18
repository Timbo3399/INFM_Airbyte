"""Tests fuer generate_account() aus scripts/mapping/generate_accounts.py (keine DB noetig)."""
import generate_accounts as ga


def test_erster_buchstabe_vorname_plus_nachname_kleingeschrieben():
    assert ga.generate_account("Max", "Mustermann") == "mmusterm"


def test_maximal_acht_zeichen():
    assert len(ga.generate_account("Alexander", "Schmidtberger")) == 8


def test_umlaute_werden_transliteriert():
    # Ü -> ue, also Vorname-Initiale 'u'? Nein: erster Buchstabe von "Über" ist Ü -> 'ue'
    assert ga.generate_account("Jens", "Müller") == "jmueller"


def test_sonderzeichen_und_akzente_werden_entfernt():
    assert ga.generate_account("José", "D'Angelo") == "jdangelo"


def test_leere_eingaben_ergeben_leeren_string():
    assert ga.generate_account("", "") == ""
