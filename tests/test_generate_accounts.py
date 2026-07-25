"""Tests fuer generate_account() aus scripts/mapping/generate_accounts.py (keine DB noetig)."""
import generate_accounts as ga


def test_erster_buchstabe_vorname_plus_nachname_kleingeschrieben():
    assert ga.generate_account("Max", "Mustermann") == "mmusterm"


def test_maximal_acht_zeichen():
    assert len(ga.generate_account("Alexander", "Schmidtberger")) == 8


def test_umlaute_werden_transliteriert():
    # "Müller" -> "mueller", der Account bleibt damit bei 8 Zeichen.
    assert ga.generate_account("Jens", "Müller") == "jmueller"


def test_sonderzeichen_und_akzente_werden_entfernt():
    assert ga.generate_account("José", "D'Angelo") == "jdangelo"


def test_leere_eingaben_ergeben_leeren_string():
    assert ga.generate_account("", "") == ""


# --- Kollisionen (HSOG-Spec: + Anzahlaccounts_mit_dem_Schema + 1) -------------
# data/js/hso_accountgenerator.js: account = maxLength-8(Vorname[0] + Nachname
# + (Anzahlaccounts_mit_dem_Schema + 1)). Der Zaehler zaehlt zur Laenge dazu,
# die Basis muss also weiter gekuerzt werden.

def test_ohne_kollision_bleibt_der_account_unveraendert():
    assert ga.generate_account("Max", "Mustermann", set()) == "mmusterm"


def test_kollision_erhaelt_zaehlersuffix():
    assert ga.generate_account("Max", "Mustermann", {"mmusterm"}) == "mmuster2"


def test_mehrfache_kollisionen_zaehlen_hoch():
    belegt = {"mmusterm", "mmuster2", "mmuster3"}
    assert ga.generate_account("Max", "Mustermann", belegt) == "mmuster4"


def test_account_bleibt_auch_mit_zaehler_bei_acht_zeichen():
    belegt = {"mmusterm"} | {f"mmuster{n}" for n in range(2, 10)}
    ergebnis = ga.generate_account("Max", "Mustermann", belegt)
    assert ergebnis == "mmuste10"
    assert len(ergebnis) == 8


def test_kurze_namen_werden_durch_den_zaehler_nicht_beschnitten():
    assert ga.generate_account("Ada", "Li", {"ali"}) == "ali2"


def test_leerer_account_bekommt_keinen_zaehler():
    assert ga.generate_account("", "", {""}) == ""


# --- Abgeleitete E-Mail-Adressen ---------------------------------------------

def test_hochschul_email_wird_aus_dem_account_gebildet():
    assert ga.hochschul_email("mmusterm", ga.STUD_DOMAIN) == "mmusterm@stud.hs-offenburg.de"


def test_hochschul_email_fuer_personal_nutzt_die_andere_domain():
    assert ga.hochschul_email("jmueller", ga.PERSONAL_DOMAIN) == "jmueller@hs-offenburg.de"


def test_ohne_account_gibt_es_keine_email():
    assert ga.hochschul_email("", ga.STUD_DOMAIN) is None


# --- Hinweis, wenn es nichts zu vergeben gibt --------------------------------
# Zwei verschiedene Gruende, die nicht verwechselt werden duerfen: entweder
# fehlen die Namen (dann fehlt Schritt 1), oder alles ist schon vergeben.

def test_hinweis_verweist_auf_schritt_1_wenn_namen_fehlen():
    assert "fill_random_names" in ga.hinweis_wenn_nichts_zu_tun(5922)


def test_hinweis_meldet_fertig_wenn_alle_namen_da_sind():
    text = ga.hinweis_wenn_nichts_zu_tun(0)
    assert "fill_random_names" not in text
    assert "bereits vergeben" in text
