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


# --- Sollwerte (Belege in docs/ergebnisse.md und docs/testszenarien.md) -----

def _soll(id):
    return p.soll(id)


def test_sollwerte_szenario_1_deckt_beide_ziele_und_beide_quelltypen_ab():
    # Die Aufgabenstellung nennt MySQL und PostgreSQL als Ziel und zwei
    # Source-Typen. Fehlt eines davon, ist Szenario 1 nur halb geprueft.
    assert _soll("sz1-gebaeude-pg").erwartet == 25
    assert _soll("sz1-plz-pg").erwartet == 34172
    assert _soll("sz1-gebaeude-mysql").erwartet == 25
    assert _soll("sz1-plz-mysql").erwartet == 34172
    assert _soll("sz1-students-pg").erwartet == 5052


def test_sollwerte_szenario_2():
    assert _soll("sz2-stamm").erwartet == 1244
    assert _soll("sz2-inst").erwartet == 2083
    assert _soll("sz2-raeume-pg").erwartet == 1244
    assert _soll("sz2-raeume-institut").erwartet == 1184
    assert _soll("sz2-raeume-flaeche").erwartet == 52009
    assert _soll("sz2-raeume-mysql").erwartet == 1244


def test_szenario_2_prueft_die_raumuebersicht_als_join():
    # Zeilenzahlen allein belegen Teilaufgabe A nicht: alle drei Tabellen
    # koennen im Ziel stehen und der Join trotzdem nichts treffen (Befund 16).
    assert _soll("sz2-join").erwartet == 1244
    assert _soll("sz2-join").quelle == "dest_pg"


def test_szenario_2_haelt_den_formatkonflikt_als_befund_fest():
    naiv = _soll("sz2-join-naiv")

    assert naiv.erwartet == 0
    assert naiv.art == "befund"
    assert naiv.beleg == "Befund 16"


def test_sollwerte_szenario_3_teilaufgabe_a():
    assert _soll("sz3-bilder-quelle").erwartet == 1100
    assert _soll("sz3-bilder-inhalt").erwartet == 1100


def test_sollwerte_szenario_3_prueft_den_export_aus_teilaufgabe_b():
    # Teilaufgabe B verlangt den Export aus der Datenbank. Ohne diese Pruefung
    # galt Szenario 3 als erfuellt, ohne dass je eine Datei geschrieben wurde.
    assert _soll("sz3-export-anzahl").erwartet == 1100
    assert _soll("sz3-export-anzahl").quelle == "dateien"
    assert _soll("sz3-export-bytes").erwartet == _soll("sz3-bilder-bytes").erwartet


def test_der_blob_verlust_ist_ein_befund_und_kein_sollzustand():
    # Befund 1. Als "soll" gelesen hiesse die 0, dass ein Sync ohne Inhalt in
    # Ordnung ist. Als Befund heisst sie: genau das haben wir nachgewiesen.
    inhalt = _soll("sz3-mysql-inhalt")

    assert inhalt.erwartet == 0
    assert inhalt.art == "befund"
    assert inhalt.beleg == "Befund 1"


def test_sollwerte_szenario_4():
    assert _soll("sz4-uid-gesetzt").erwartet == 5922
    assert _soll("sz4-uid-eindeutig").erwartet == 5922
    assert _soll("sz4-mail-gesetzt").erwartet == 5922


def test_szenario_4_prueft_die_account_spec_aus_hso_accountgenerator():
    # maxLength-8 und ersetzte Umlaute, beides aus der Spec im JS-Original.
    assert _soll("sz4-uid-laenge").erwartet == 0
    assert _soll("sz4-uid-zeichen").erwartet == 0


def test_sollwerte_szenario_4_im_ziel():
    # Schritt 3 des Szenarios: die Accounts als eigene Zieltabellen je Gruppe.
    # 5.052 Studierende und 870 Personal, beide Zahlen in ergebnisse.md belegt.
    assert _soll("sz4-stud-accounts").erwartet == 5052
    assert _soll("sz4-pers-accounts").erwartet == 870


def test_die_ziel_pruefungen_von_szenario_4_lesen_dest_postgres():
    for id in ("sz4-stud-accounts", "sz4-pers-accounts"):
        assert _soll(id).quelle == "dest_pg"


def test_die_summe_der_beiden_gruppen_ergibt_die_gesamtzahl():
    # Haelt zusammen, was sonst auseinanderlaufen kann: 5.052 + 870 = 5.922.
    einzeln = (_soll("sz4-stud-accounts").erwartet
               + _soll("sz4-pers-accounts").erwartet)

    assert einzeln == _soll("sz4-uid-gesetzt").erwartet


def test_sollwerte_szenario_5():
    assert _soll("sz5-user-zeilen").erwartet == 5922
    assert _soll("sz5-user-eindeutig").erwartet == 5922
    assert _soll("sz5-user-bild").erwartet == 5922


def test_szenario_5_belegt_die_deduplizierung_ueber_die_rollenverteilung():
    # 5.052 Studierende plus 870 Personal muessen die 5.922 ergeben, sonst hat
    # der Dedup-Modus etwas zusammengeworfen oder verloren.
    einzeln = (_soll("sz5-user-studierende").erwartet
               + _soll("sz5-user-personal").erwartet)

    assert einzeln == _soll("sz5-user-zeilen").erwartet


def test_szenario_5_haelt_den_fehlenden_primaerschluessel_fest():
    index = _soll("sz5-kein-unique-index")

    assert index.erwartet == 0
    assert index.art == "befund"
    assert index.beleg == "Befund 2"


def test_die_rohtabelle_wird_als_mindestwert_geprueft():
    # Sie waechst mit jedem Sync (Befund 5). Eine feste Zahl waere eine
    # Erwartung an die Anzahl der Laeufe, nicht an den Aufbau.
    roh = _soll("sz5-rohtabelle")

    assert roh.vergleich == "mindestens"
    assert roh.erwartet == 5922


def test_sollwerte_szenario_6a_erwartet_http_200():
    assert _soll("sz6a-plz-status").erwartet == 200
    assert _soll("sz6a-students-status").erwartet == 200


def test_szenario_6a_prueft_nicht_nur_den_statuscode():
    # PostgREST antwortet auch auf eine leere Tabelle mit HTTP 200.
    zeilen = _soll("sz6a-plz-zeilen")

    assert zeilen.quelle == "postgrest_zeilen"
    assert zeilen.erwartet == 1


def test_szenario_6b_steht_als_nicht_umgesetzt_in_der_liste():
    # Weglassen waere die unehrlichere Variante: in einer Bewertung ist gerade
    # die Luecke eine Aussage.
    sechs_b = [s for s in p.SZENARIEN if s.kuerzel == "Sz6b"]

    assert len(sechs_b) == 1
    assert sechs_b[0].status == "nicht_umgesetzt"
    assert sechs_b[0].begruendung


def test_jede_sollwert_quelle_ist_bekannt():
    for s in p.SOLLWERTE:
        assert s.quelle in p.QUELLEN_NAMEN, f"{s.beschreibung}: Quelle {s.quelle}"


def test_jede_pruefung_hat_eine_eindeutige_id():
    ids = [s.id for s in p.SOLLWERTE]

    assert all(ids), "Pruefung ohne Id"
    assert len(ids) == len(set(ids)), "Id doppelt vergeben"


def test_jede_pruefung_traegt_das_kuerzel_ihres_szenarios():
    # Darauf beruhen SOLLWERTE und nur_szenarien, beide nutzt setup_szenarien.
    for s in p.SZENARIEN:
        for t in s.teilaufgaben:
            for pruefung in t.pruefungen:
                assert pruefung.szenario == s.kuerzel


def test_jeder_befund_nennt_seinen_beleg():
    for s in p.SOLLWERTE:
        if s.art == "befund":
            assert s.beleg, f"{s.id}: Befund ohne Beleg"


def test_jede_teilaufgabe_hat_mindestens_eine_pruefung():
    for s in p.SZENARIEN:
        for t in s.teilaufgaben:
            assert t.pruefungen, f"{s.kuerzel}/{t.name}: keine Pruefung"


def test_die_definition_lehnt_eine_doppelte_id_ab():
    doppelt = p._szenario("SzX", "x", "x", (
        p._teil("A", [p._p("gleiche-id", "a", 1, "dest_pg", "SELECT 1"),
                      p._p("gleiche-id", "b", 1, "dest_pg", "SELECT 1")]),))

    with pytest.raises(ValueError):
        p._pruefe_definition([doppelt])


def test_die_definition_lehnt_eine_unbekannte_quelle_ab():
    falsch = p._szenario("SzX", "x", "x", (
        p._teil("A", [p._p("x", "a", 1, "gibt_es_nicht", "SELECT 1")]),))

    with pytest.raises(ValueError):
        p._pruefe_definition([falsch])


def test_soll_wirft_bei_unbekannter_id():
    with pytest.raises(KeyError):
        p.soll("gibt-es-nicht")


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


def test_nur_szenario_objekte_filtert_auf_der_szenario_ebene():
    gefiltert = p.nur_szenario_objekte(p.SZENARIEN, ["sz3", "SZ6B"])

    assert [s.kuerzel for s in gefiltert] == ["Sz3", "Sz6b"]


def test_nur_szenario_objekte_ohne_auswahl_laesst_alles_durch():
    assert p.nur_szenario_objekte(p.SZENARIEN, []) == p.SZENARIEN


# --- Vergleich --------------------------------------------------------------

def test_stimmt_vergleicht_standardmaessig_auf_gleichheit():
    pruefung = p.Pruefung("Sz1", "a", 25, "dest_pg", "x", id="a")

    assert p.stimmt(pruefung, 25) is True
    assert p.stimmt(pruefung, 26) is False


def test_stimmt_akzeptiert_bei_mindestens_auch_mehr():
    # Die Rohtabelle waechst mit jedem Sync, mehr ist dort kein Fehler.
    pruefung = p.Pruefung("Sz5", "roh", 5922, "dest_mysql", "x", id="a",
                          vergleich="mindestens")

    assert p.stimmt(pruefung, 5922) is True
    assert p.stimmt(pruefung, 11845) is True
    assert p.stimmt(pruefung, 5921) is False


def test_stimmt_ist_falsch_wenn_die_messung_scheiterte():
    pruefung = p.Pruefung("Sz1", "a", 25, "dest_pg", "x", id="a",
                          vergleich="mindestens")

    assert p.stimmt(pruefung, None) is False


# --- Status einer einzelnen Pruefung ----------------------------------------

def test_status_eines_sollwerts_heisst_ok_oder_fehlt():
    pruefung = p.Pruefung("Sz1", "a", 25, "dest_pg", "x", id="a")

    assert p.status_von(pruefung, 25) == "ok"
    assert p.status_von(pruefung, 0) == "fehlt"


def test_ein_getroffener_befund_heisst_bestaetigt_und_nicht_ok():
    # Sonst liest sich Szenario 3 als "0 uebertragene Bilder sind in Ordnung".
    befund = p.Pruefung("Sz3", "Inhalt in MySQL", 0, "dest_mysql", "x",
                        id="a", art="befund", beleg="Befund 1")

    assert p.status_von(befund, 0) == "bestaetigt"


def test_ein_befund_der_nicht_mehr_auftritt_wird_als_solcher_gemeldet():
    # Dann ist nicht der Aufbau kaputt, sondern die Dokumentation veraltet.
    befund = p.Pruefung("Sz3", "Inhalt in MySQL", 0, "dest_mysql", "x",
                        id="a", art="befund", beleg="Befund 1")

    assert p.status_von(befund, 1100) == "NICHT reproduziert"


# --- Urteil je Szenario -----------------------------------------------------

def _mini(*werte, art="soll"):
    """Szenario mit einer Teilaufgabe je uebergebenem Sollwert."""
    teile = [p._teil(f"T{i}", [p._p(f"id{i}", f"pruefung {i}", w, "dest_pg",
                                    "SELECT 1", art=art,
                                    beleg="Befund X" if art == "befund" else "")])
             for i, w in enumerate(werte)]
    return p._szenario("SzX", "Test", "Ziel", tuple(teile))


def test_szenario_ist_erfuellt_wenn_jede_pflichtpruefung_stimmt():
    szenario = _mini(1, 2)

    assert p.szenario_urteil(szenario, {"id0": 1, "id1": 2}) == "erfuellt"


def test_szenario_ist_nicht_erfuellt_sobald_eine_pflichtpruefung_fehlt():
    szenario = _mini(1, 2)

    assert p.szenario_urteil(szenario, {"id0": 1, "id1": 99}) == "NICHT erfuellt"


def test_szenario_ist_nicht_erfuellt_wenn_eine_messung_scheiterte():
    szenario = _mini(1, 2)

    assert p.szenario_urteil(szenario, {"id0": 1}) == "NICHT erfuellt"


def test_ein_abweichender_befund_kippt_das_szenario_nicht():
    # Der Kern der Trennung: dass Airbyte BLOBs verliert, ist ein Ergebnis der
    # Evaluation und kein Mangel des Aufbaus.
    szenario = _mini(0, art="befund")

    assert p.szenario_urteil(szenario, {"id0": 1100}) == "erfuellt"


def test_ein_nicht_umgesetztes_szenario_bekommt_ein_eigenes_urteil():
    szenario = p._szenario("Sz6b", "SOAP", "Ziel", status="nicht_umgesetzt",
                           begruendung="kein Zugang")

    assert p.szenario_urteil(szenario, {}) == "nicht umgesetzt"


def test_zaehle_liefert_teilaufgaben_und_pflichtpruefungen():
    szenario = _mini(1, 2)

    assert p.zaehle(szenario, {"id0": 1, "id1": 99}) == (1, 2, 1, 2)


def test_zaehle_laesst_befunde_aus_der_quote_heraus():
    szenario = _mini(0, art="befund")

    assert p.zaehle(szenario, {"id0": 0}) == (0, 0, 0, 0)


def test_eine_teilaufgabe_aus_lauter_befunden_heisst_nicht_ok():
    # "ok" liest sich wie ein erreichter Sollzustand. Ein Befund ist keiner.
    teil = p._teil("Befunde", [
        p._p("bef", "b", 0, "dest_pg", "x", art="befund", beleg="Befund X")])

    assert p.teil_marke(teil, {"bef": 0}) == "Befund"


def test_eine_teilaufgabe_mit_pflicht_heisst_ok_oder_offen():
    teil = p._teil("A", [p._p("soll", "a", 1, "dest_pg", "x")])

    assert p.teil_marke(teil, {"soll": 1}) == "ok"
    assert p.teil_marke(teil, {"soll": 0}) == "OFFEN"


def test_teil_erfuellt_beachtet_nur_die_pflichtpruefungen():
    teil = p._teil("A", [
        p._p("soll", "a", 1, "dest_pg", "x"),
        p._p("bef", "b", 0, "dest_pg", "x", art="befund", beleg="Befund X"),
    ])

    assert p.teil_erfuellt(teil, {"soll": 1, "bef": 999}) is True


# --- Was offen ist ----------------------------------------------------------

def test_offene_teile_nennt_szenario_teilaufgabe_und_luecke():
    szenario = _mini(1, 2)

    offen = p.offene_teile([szenario], {"id0": 1, "id1": 99})

    assert len(offen) == 1
    s, t, luecken = offen[0]
    assert s.kuerzel == "SzX"
    assert t.name == "T1"
    assert [x.id for x, _ in luecken] == ["id1"]


def test_offene_teile_uebergeht_nicht_umgesetzte_szenarien():
    szenario = p._szenario("Sz6b", "SOAP", "Ziel", status="nicht_umgesetzt")

    assert p.offene_teile([szenario], {}) == []


def test_offene_teile_ist_leer_wenn_alles_stimmt():
    assert p.offene_teile([_mini(1, 2)], {"id0": 1, "id1": 2}) == []


def test_abweichende_befunde_meldet_nur_die_nicht_mehr_reproduzierbaren():
    szenario = _mini(0, art="befund")

    assert p.abweichende_befunde([szenario], {"id0": 0}) == []
    assert len(p.abweichende_befunde([szenario], {"id0": 1100})) == 1


# --- Ausgabe der Szenario-Tabelle -------------------------------------------

def test_die_szenario_tabelle_nennt_kuerzel_titel_und_urteil():
    zeilen = p.formatiere_szenarien([_mini(1, 2)], {"id0": 1, "id1": 2}).splitlines()

    treffer = [z for z in zeilen if "SzX" in z]
    assert len(treffer) == 1
    assert "Test" in treffer[0]
    assert "erfuellt" in treffer[0]


def test_die_szenario_tabelle_zeigt_wie_viele_teile_offen_sind():
    zeile = [z for z in p.formatiere_szenarien(
        [_mini(1, 2)], {"id0": 1, "id1": 99}).splitlines() if "SzX" in z][0]

    assert "1/2" in zeile
    assert "NICHT erfuellt" in zeile


def test_die_szenario_tabelle_kommt_mit_einem_nicht_umgesetzten_szenario_klar():
    szenario = p._szenario("Sz6b", "SOAP", "Ziel", status="nicht_umgesetzt",
                           begruendung="kein Zugang")

    zeile = [z for z in p.formatiere_szenarien([szenario], {}).splitlines()
             if "Sz6b" in z][0]

    assert "nicht umgesetzt" in zeile


def test_die_szenario_tabelle_hat_ihre_vier_spalten():
    kopf = p.formatiere_szenarien([], {}).splitlines()[0]

    for spalte in ("Szenario", "Teilaufgaben", "Pruefungen", "Status"):
        assert spalte in kopf


def test_der_offen_block_nennt_das_kommando_der_teilaufgabe():
    # Der pauschale Verweis auf setup_szenarien.py hilft genau dann nicht, wenn
    # der fehlende Schritt dort nicht steht.
    teil = p._teil("B  Export", [p._p("x", "Dateien", 1100, "dateien",
                                      "anzahl:data/images")],
                   "python scripts/images/export_images.py")
    szenario = p._szenario("Sz3", "Bilder", "Ziel", (teil,))

    text = p.formatiere_offen([szenario], {"x": 0})

    assert "export_images.py" in text
    assert "1.100" in text


def test_der_offen_block_ist_leer_wenn_nichts_offen_ist():
    assert p.formatiere_offen([_mini(1)], {"id0": 1}) == ""


def test_der_befund_block_steht_unter_eigener_ueberschrift():
    szenario = _mini(0, art="befund")

    text = p.formatiere_befunde([szenario], {"id0": 0})

    assert "Befund" in text
    assert "bestaetigt" in text


def test_der_befund_block_ist_leer_ohne_befunde():
    assert p.formatiere_befunde([_mini(1)], {"id0": 1}) == ""


def test_die_urteilszeile_zaehlt_erfuellte_und_offene_szenarien():
    erfuellt = p._szenario("Sz1", "a", "z", (
        p._teil("A", [p._p("ok", "a", 1, "dest_pg", "x")]),))
    offen = p._szenario("Sz2", "b", "z", (
        p._teil("A", [p._p("nein", "b", 1, "dest_pg", "x")]),))
    soap = p._szenario("Sz6b", "c", "z", status="nicht_umgesetzt")

    text = p.urteil_zeile([erfuellt, offen, soap], {"ok": 1, "nein": 0})

    assert "1 von 2 erfuellt" in text
    assert "1 nicht erfuellt" in text
    assert "1 nicht umgesetzt" in text


def test_die_urteilszeile_verschweigt_was_es_nicht_gibt():
    erfuellt = p._szenario("Sz1", "a", "z", (
        p._teil("A", [p._p("ok", "a", 1, "dest_pg", "x")]),))

    text = p.urteil_zeile([erfuellt], {"ok": 1})

    assert text == "Szenarien: 1 von 1 erfuellt."


def test_als_karte_schluesselt_nach_id():
    a = p.Pruefung("Sz1", "a", 1, "dest_pg", "x", id="eins")

    assert p.als_karte([(a, 42)]) == {"eins": 42}


# --- Bild-Export im Dateisystem ---------------------------------------------

def test_zerlege_dateiabfrage_trennt_frage_und_pfad():
    assert p.zerlege_dateiabfrage("anzahl:data/images") == ("anzahl", "data/images")
    assert p.zerlege_dateiabfrage("bytes:data/images") == ("bytes", "data/images")


def test_zerlege_dateiabfrage_wirft_bei_unsinn():
    for kaputt in ("data/images", "groesse:data/images", "anzahl:"):
        with pytest.raises(ValueError):
            p.zerlege_dateiabfrage(kaputt)


def test_dateien_quelle_zaehlt_und_summiert(tmp_path):
    ordner = tmp_path / "data" / "images"
    ordner.mkdir(parents=True)
    (ordner / "a.png").write_bytes(b"12345")
    (ordner / "b.png").write_bytes(b"678")
    frage = p.dateien_quelle(str(tmp_path))

    assert frage("anzahl:data/images") == 2
    assert frage("bytes:data/images") == 8


def test_dateien_quelle_uebergeht_unterverzeichnisse(tmp_path):
    ordner = tmp_path / "data" / "images"
    ordner.mkdir(parents=True)
    (ordner / "a.png").write_bytes(b"1")
    (ordner / "unter").mkdir()
    frage = p.dateien_quelle(str(tmp_path))

    assert frage("anzahl:data/images") == 1


def test_dateien_quelle_wirft_wenn_der_ordner_fehlt(tmp_path):
    # Muss werfen, damit messe() daraus ein "fehlt" macht statt einer stillen 0.
    frage = p.dateien_quelle(str(tmp_path))

    with pytest.raises(FileNotFoundError):
        frage("anzahl:data/images")


def test_der_export_wird_ueber_messe_zu_einem_fehlt(tmp_path):
    pruefung = p.soll("sz3-export-anzahl")
    quellen = {"dateien": p.dateien_quelle(str(tmp_path))}

    assert p.messe([pruefung], quellen) == [(pruefung, None)]
