"""Tests fuer die reinen Funktionen in scripts/pruefe_szenarien.py (keine DB noetig).

Die Sollwerte selbst sind mitgetestet: sie stehen in docs/ergebnisse.md und
duerfen nicht stillschweigend an einen abweichenden Lauf angepasst werden.
"""
import pytest

import pruefe_szenarien as p


# --- Darstellung ------------------------------------------------------------

def test_tausender_setzt_punkt_als_trenner():
    assert p.tausender(34172) == "34.172"
    assert p.tausender(1244) == "1.244"
    assert p.tausender(25) == "25"


def test_tausender_zeigt_fehlende_messung_als_strich():
    assert p.tausender(None) == "-"


def test_tausender_behaelt_null_als_zahl():
    # Szenario 3 erwartet echte 0 (Bilder ohne Inhalt), nicht "keine Messung".
    assert p.tausender(0) == "0"


# --- Bewertung --------------------------------------------------------------

def test_bewerte_meldet_ok_bei_treffer():
    assert p.bewerte(25, 25) == "ok"


def test_bewerte_meldet_fehlt_bei_abweichung():
    assert p.bewerte(25, 24) == "fehlt"


def test_bewerte_meldet_ok_wenn_null_erwartet_und_gefunden_ist():
    # Befund 1: im Ziel 1.100 Zeilen, davon 0 mit Inhalt. 0 ist hier der Sollwert.
    assert p.bewerte(0, 0) == "ok"


def test_bewerte_meldet_fehlt_wenn_die_messung_scheiterte():
    assert p.bewerte(25, None) == "fehlt"


# --- Sollwerte (Belege in docs/ergebnisse.md) -------------------------------

def _soll(szenario, beschreibung_teil):
    treffer = [s for s in p.SOLLWERTE
               if s.szenario == szenario and beschreibung_teil in s.beschreibung]
    assert len(treffer) == 1, f"{szenario}/{beschreibung_teil}: {len(treffer)} Treffer"
    return treffer[0]


def test_sollwerte_szenario_1():
    assert _soll("Sz1", "fm_gebaeude").erwartet == 25
    assert _soll("Sz1", "k_plz").erwartet == 34172


def test_sollwerte_szenario_2():
    assert _soll("Sz2", "fm_raeume Zeilen").erwartet == 1244
    assert _soll("Sz2", "mit Institut").erwartet == 1184
    assert _soll("Sz2", "fm_raeume in MySQL").erwartet == 1244


def test_sollwerte_szenario_3_haelt_den_befund_fest():
    assert _soll("Sz3", "hso_images in der Quelle").erwartet == 1100
    assert _soll("Sz3", "hso_images Zeilen in MySQL").erwartet == 1100
    # Der Befund: Zeilen ja, Inhalt nein.
    assert _soll("Sz3", "mit Inhalt").erwartet == 0


def test_sollwerte_szenario_4():
    assert _soll("Sz4", "user_id gesetzt").erwartet == 5922
    assert _soll("Sz4", "eindeutige user_id").erwartet == 5922


def test_sollwerte_szenario_4_im_ziel():
    # Schritt 3 des Szenarios: die Accounts als eigene Zieltabellen je Gruppe.
    # 5.052 Studierende und 870 Personal, beide Zahlen in ergebnisse.md belegt.
    assert _soll("Sz4", "hso_student_accounts").erwartet == 5052
    assert _soll("Sz4", "hso_personal_accounts").erwartet == 870


def test_die_ziel_pruefungen_von_szenario_4_lesen_dest_postgres():
    for teil in ("hso_student_accounts", "hso_personal_accounts"):
        assert _soll("Sz4", teil).quelle == "dest_pg"


def test_die_summe_der_beiden_gruppen_ergibt_die_gesamtzahl():
    # Haelt zusammen, was sonst auseinanderlaufen kann: 5.052 + 870 = 5.922.
    einzeln = (_soll("Sz4", "hso_student_accounts").erwartet
               + _soll("Sz4", "hso_personal_accounts").erwartet)

    assert einzeln == _soll("Sz4", "user_id gesetzt").erwartet


def test_sollwerte_szenario_5():
    assert _soll("Sz5", "hso_user Zeilen").erwartet == 5922
    assert _soll("Sz5", "verschiedene user_id").erwartet == 5922
    assert _soll("Sz5", "mit image_id").erwartet == 5922


def test_sollwerte_szenario_6a_erwartet_http_200():
    assert _soll("Sz6a", "k_plz").erwartet == 200


def test_jede_sollwert_quelle_ist_bekannt():
    for s in p.SOLLWERTE:
        assert s.quelle in p.QUELLEN_NAMEN, f"{s.beschreibung}: Quelle {s.quelle}"


# --- Messung ----------------------------------------------------------------

def test_messe_fragt_die_zugeordnete_quelle():
    pruefung = p.Pruefung("Sz1", "test", 7, "dest_pg", "SELECT 7")
    quellen = {"dest_pg": lambda abfrage: 7}

    ergebnisse = p.messe([pruefung], quellen)

    assert ergebnisse == [(pruefung, 7)]


def test_messe_trennt_die_quellen_auseinander():
    a = p.Pruefung("Sz1", "a", 1, "dest_pg", "A")
    b = p.Pruefung("Sz2", "b", 2, "dest_mysql", "B")
    quellen = {"dest_pg": lambda _: 1, "dest_mysql": lambda _: 2}

    assert p.messe([a, b], quellen) == [(a, 1), (b, 2)]


def test_messe_liefert_none_wenn_die_abfrage_scheitert():
    # Fehlende Zieltabelle darf die Pruefung nicht abbrechen, sondern muss
    # als "fehlt" in der Tabelle landen.
    def kaputt(_):
        raise RuntimeError('relation "k_plz" does not exist')

    pruefung = p.Pruefung("Sz1", "k_plz", 34172, "dest_pg", "SELECT count(*) FROM k_plz")

    assert p.messe([pruefung], {"dest_pg": kaputt}) == [(pruefung, None)]


def test_messe_liefert_none_bei_unbekannter_quelle():
    pruefung = p.Pruefung("Sz1", "x", 1, "gibt_es_nicht", "SELECT 1")

    assert p.messe([pruefung], {}) == [(pruefung, None)]


# --- Tabelle ----------------------------------------------------------------

def _tabelle(ergebnisse):
    return p.formatiere_tabelle(ergebnisse)


def test_tabelle_hat_die_vier_geforderten_spalten():
    kopf = _tabelle([]).splitlines()[0]
    for spalte in ("Szenario", "erwartet", "gefunden", "Status"):
        assert spalte in kopf


def test_tabelle_zeigt_wert_und_status_je_zeile():
    pruefung = p.Pruefung("Sz1", "k_plz", 34172, "dest_pg", "x")
    zeilen = _tabelle([(pruefung, 34172)]).splitlines()

    treffer = [z for z in zeilen if "k_plz" in z]
    assert len(treffer) == 1
    assert "34.172" in treffer[0]
    assert "ok" in treffer[0]


def test_tabelle_markiert_fehlende_messung():
    pruefung = p.Pruefung("Sz1", "k_plz", 34172, "dest_pg", "x")
    zeile = [z for z in _tabelle([(pruefung, None)]).splitlines() if "k_plz" in z][0]

    assert "fehlt" in zeile
    assert "-" in zeile


def test_tabellenzeilen_sind_gleich_lang_ausgerichtet():
    kurz = p.Pruefung("Sz1", "a", 1, "dest_pg", "x")
    lang = p.Pruefung("Sz2", "eine deutlich laengere Beschreibung", 2, "dest_pg", "x")
    zeilen = _tabelle([(kurz, 1), (lang, 2)]).splitlines()

    breiten = {len(z) for z in zeilen}
    assert len(breiten) == 1, f"unterschiedliche Breiten: {breiten}"


# --- Gesamtergebnis ---------------------------------------------------------

def test_alles_ok_bei_lauter_treffern():
    a = p.Pruefung("Sz1", "a", 1, "dest_pg", "x")
    assert p.alles_ok([(a, 1)]) is True


def test_alles_ok_ist_falsch_sobald_eine_pruefung_fehlt():
    a = p.Pruefung("Sz1", "a", 1, "dest_pg", "x")
    b = p.Pruefung("Sz2", "b", 2, "dest_pg", "x")
    assert p.alles_ok([(a, 1), (b, 99)]) is False


def test_alles_ok_bei_leerer_liste():
    assert p.alles_ok([]) is True


def test_ratschlag_vermutet_bei_lauter_fehlern_den_stack():
    # Wenn KEINE einzige Messung durchkommt, liegt es fast immer daran, dass die
    # Container nicht laufen. Der Hinweis auf setup_szenarien fuehrt dann in die
    # falsche Richtung, und in einer Praesentation kostet das Minuten.
    a = p.Pruefung("Sz1", "a", 1, "dest_pg", "x")
    b = p.Pruefung("Sz2", "b", 2, "dest_mysql", "x")

    text = p.ratschlag([(a, None), (b, None)])

    assert "start" in text.lower()
    assert "setup_szenarien" not in text


def test_ratschlag_verweist_bei_einzelnen_luecken_auf_den_aufbau():
    a = p.Pruefung("Sz1", "a", 1, "dest_pg", "x")
    b = p.Pruefung("Sz2", "b", 2, "dest_pg", "x")

    text = p.ratschlag([(a, 1), (b, None)])

    assert "setup_szenarien" in text


def test_ratschlag_unterscheidet_null_messung_von_falschem_wert():
    # Eine gemessene, aber abweichende Zahl ist kein Stack-Problem.
    a = p.Pruefung("Sz1", "a", 1, "dest_pg", "x")

    text = p.ratschlag([(a, 99)])

    assert "setup_szenarien" in text


def test_ratschlag_ist_leer_wenn_alles_stimmt():
    a = p.Pruefung("Sz1", "a", 1, "dest_pg", "x")

    assert p.ratschlag([(a, 1)]) == ""


def test_zusammenfassung_zaehlt_treffer_und_fehler():
    a = p.Pruefung("Sz1", "a", 1, "dest_pg", "x")
    b = p.Pruefung("Sz2", "b", 2, "dest_pg", "x")

    text = p.zusammenfassung([(a, 1), (b, 99)])

    assert "1" in text and "2" in text


# --- MySQL-Zugriff ohne Python-Treiber --------------------------------------

def test_mysql_kommando_geht_ueber_docker_exec_in_den_container():
    argv = p.mysql_kommando("hso_dest_mysql", "destuser", "destdb", "SELECT 1")

    assert argv[:3] == ["docker", "exec", "-e"]
    assert "hso_dest_mysql" in argv
    assert argv[-2:] == ["-e", "SELECT 1"]


def test_mysql_kommando_uebergibt_das_passwort_nicht_auf_der_kommandozeile():
    # -p auf der Kommandozeile erzeugt bei jedem Aufruf eine Warnung auf stderr,
    # die mitten in der Demo-Ausgabe stehen wuerde. Deshalb MYSQL_PWD.
    argv = p.mysql_kommando("c", "destuser", "destdb", "SELECT 1")

    assert "MYSQL_PWD" in argv
    assert not any(a.startswith("-p") for a in argv)
    assert "destpassword" not in argv


def test_mysql_kommando_schaltet_kopfzeile_und_rahmen_ab():
    # Ohne -N -B liefert der Client eine ASCII-Tabelle, die kein int ergibt.
    argv = p.mysql_kommando("c", "u", "d", "SELECT 1")

    assert "-N" in argv and "-B" in argv


def test_erste_zahl_liest_den_skalar():
    assert p.erste_zahl("1244\n") == 1244


def test_erste_zahl_nimmt_das_erste_feld_bei_mehreren_spalten():
    assert p.erste_zahl("5922\t5922\n") == 5922


def test_erste_zahl_ignoriert_leerzeilen():
    assert p.erste_zahl("\n\n25\n") == 25


def test_erste_zahl_wirft_bei_leerer_ausgabe():
    # Muss werfen, damit messe() daraus ein "fehlt" macht statt einer stillen 0.
    with pytest.raises(ValueError):
        p.erste_zahl("")


# --- Filter fuer den Demo-Betrieb -------------------------------------------

def test_nur_szenario_filtert_auf_ein_szenario():
    gefiltert = p.nur_szenarien(p.SOLLWERTE, ["Sz3"])

    assert gefiltert
    assert {s.szenario for s in gefiltert} == {"Sz3"}


def test_nur_szenario_akzeptiert_mehrere_und_ist_schreibweisenunabhaengig():
    gefiltert = p.nur_szenarien(p.SOLLWERTE, ["sz1", "SZ6A"])

    assert {s.szenario for s in gefiltert} == {"Sz1", "Sz6a"}


def test_nur_szenarien_ohne_auswahl_laesst_alles_durch():
    assert p.nur_szenarien(p.SOLLWERTE, []) == p.SOLLWERTE
