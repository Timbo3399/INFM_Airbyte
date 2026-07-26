"""Tests fuer die reinen Funktionen in scripts/setup_szenarien.py (keine DB noetig).

Geprueft wird vor allem zweierlei: dass die zwingende Reihenfolge der Schritte
eingehalten ist, und dass die Skip-Erkennung nur dann ueberspringt, wenn der
Sollzustand des Schrittes wirklich schon erreicht ist.
"""
import pytest

import pruefe_szenarien as pz
import setup_szenarien as s


def _schritt(name):
    treffer = [x for x in s.SCHRITTE if x.name == name]
    assert len(treffer) == 1, f"Schritt {name}: {len(treffer)} Treffer"
    return treffer[0]


def _pos(name):
    return [x.name for x in s.SCHRITTE].index(name)


# --- Aufbau der Schrittliste ------------------------------------------------

def test_schrittnamen_sind_eindeutig():
    namen = [x.name for x in s.SCHRITTE]
    assert len(namen) == len(set(namen))


def test_jeder_schritt_hat_eine_bekannte_art():
    for x in s.SCHRITTE:
        assert x.art in ("python", "sync", "dbt"), f"{x.name}: {x.art}"


def test_die_sieben_geforderten_schritte_sind_enthalten():
    for name in ("namen", "accounts", "view", "bilder", "objekte",
                 "connections", "dbt"):
        assert _schritt(name)


def test_jede_pruefung_eines_schrittes_nutzt_eine_bekannte_quelle():
    for x in s.SCHRITTE:
        for p in x.pruefungen:
            assert p.quelle in pz.QUELLEN_NAMEN, f"{x.name}: {p.quelle}"


# --- Zwingende Reihenfolge --------------------------------------------------

def test_namen_kommen_vor_den_accounts():
    assert _pos("namen") < _pos("accounts")


def test_die_view_braucht_die_accounts():
    assert _pos("accounts") < _pos("view")


def test_airbyte_objekte_kommen_vor_den_connections():
    assert _pos("objekte") < _pos("connections")


def test_connections_kommen_vor_jedem_sync():
    grenze = _pos("connections")
    for x in s.SCHRITTE:
        if x.art == "sync":
            assert _pos(x.name) > grenze, f"{x.name} laeuft vor den Connections"


def test_dbt_braucht_den_fm_sync():
    assert _pos("sync-fm") < _pos("dbt")


def test_der_fm_raeume_sync_nach_mysql_braucht_dbt():
    # Erst baut dbt fm_raeume in dest-postgres, dann geht die Tabelle weiter.
    assert _pos("dbt") < _pos("sync-raeume")


def test_die_fm_raeume_connection_wird_nach_dbt_nachgezogen():
    """Beim ersten Aufbau gibt es fm_raeume in dest-postgres noch nicht.

    Airbyte speichert den Stream-Katalog einer Source beim Anlegen zwischen
    (Befund 25). Zum Zeitpunkt von 'connections' existiert die Tabelle noch
    nicht, die Connection wird deshalb vertagt. Nach dbt muss ein zweiter
    Durchgang sie nachziehen, sonst laeuft sync-raeume ins Leere.
    """
    assert _pos("dbt") < _pos("connections-raeume") < _pos("sync-raeume")


def test_der_zweite_connections_durchgang_ruft_dasselbe_skript():
    assert _schritt("connections-raeume").ziel == _schritt("connections").ziel


def test_die_account_sichten_brauchen_die_accounts():
    assert _pos("accounts") < _pos("accounts-views")


def test_die_account_sichten_liegen_vor_den_connections():
    # Airbyte muss die Views beim Anlegen der Connection kennen, sonst wird sie
    # vertagt und der Sync findet nichts (Befund 28).
    assert _pos("accounts-views") < _pos("connections")


def test_der_account_sync_kommt_nach_den_connections():
    assert _pos("connections") < _pos("sync-accounts")


def test_die_bilder_liegen_vor_der_view():
    """CREATE OR REPLACE VIEW prueft die referenzierten Tabellen sofort.

    sql/source/views/hso_user.sql liest hso_images, und die Tabelle legt erst
    load_images.py an. Steht die View davor, bricht der Aufbau auf einem frischen
    Stack ab mit: relation "hso_images" does not exist. Auf einem befuellten
    Stack faellt das nicht auf, weil die Tabelle schon da ist.
    """
    assert _pos("bilder") < _pos("view")


def test_die_view_liest_wirklich_hso_images():
    # Haelt die Begruendung des Tests darueber an der Quelle fest.
    import os
    pfad = os.path.join(s.WURZEL, "sql", "source", "views", "hso_user.sql")
    with open(pfad, encoding="utf-8") as f:
        sql = f.read()

    assert "hso_images" in sql


def test_die_bilder_liegen_vor_dem_idm_sync():
    # Die View verknuepft image_id ueber hso_images. Ohne Bilder waere die
    # Spalte im Ziel leer, und Szenario 5 verlangt 5.922 mit image_id.
    assert _pos("bilder") < _pos("sync-idm")


def test_die_bilder_liegen_vor_dem_bilder_sync():
    assert _pos("bilder") < _pos("sync-bilder")


# --- Kommandos --------------------------------------------------------------

def test_python_schritt_ruft_das_skript_mit_dem_interpreter():
    argv = s.kommando(_schritt("namen"), "python")

    assert argv[0] == "python"
    assert argv[1].endswith("fill_random_names.py")


def test_jeder_python_schritt_zeigt_auf_eine_vorhandene_datei():
    import os
    for x in s.SCHRITTE:
        if x.art != "python":
            continue
        pfad = os.path.join(s.WURZEL, x.ziel)
        assert os.path.exists(pfad), f"{x.name}: {pfad} fehlt"


def test_sync_schritt_ruft_run_sync_mit_dem_connection_namen():
    argv = s.kommando(_schritt("sync-fm"), "python")

    assert argv[1].endswith("run_sync.py")
    assert argv[2] == "HSO FM nach PG"


def test_das_sync_skript_liegt_wirklich_dort_wo_kommando_es_sucht():
    # Nur auf die Endung zu pruefen reicht nicht: ein falsches Verzeichnis faellt
    # damit nicht auf, und dann scheitert jeder Sync-Schritt zur Laufzeit.
    import os
    argv = s.kommando(_schritt("sync-fm"), "python")

    assert os.path.exists(argv[1]), f"{argv[1]} gibt es nicht"


def test_jeder_dbt_pfad_zeigt_auf_ein_vorhandenes_verzeichnis():
    import os
    argv = s.kommando(_schritt("dbt"), "python")
    for i, arg in enumerate(argv):
        if arg in ("--project-dir", "--profiles-dir"):
            assert os.path.isdir(argv[i + 1]), f"{arg}: {argv[i + 1]} fehlt"


def test_dbt_schritt_nutzt_projekt_und_profilverzeichnis():
    argv = s.kommando(_schritt("dbt"), "python")

    assert argv[1:4] == ["-m", "dbt.cli.main", "run"]
    assert "--project-dir" in argv and "--profiles-dir" in argv


def test_kommando_uebernimmt_den_uebergebenen_interpreter():
    argv = s.kommando(_schritt("dbt"), "py")

    assert argv[0] == "py"


def test_kommando_lehnt_unbekannte_art_ab():
    kaputt = s.Schritt("x", "x", "zauber", "x", "1 s", ())

    with pytest.raises(ValueError):
        s.kommando(kaputt, "python")


# --- Skip-Erkennung ---------------------------------------------------------

def _ergebnisse(schritt, werte):
    """Messergebnisse fuer die Pruefungen eines Schrittes."""
    return [(p, w) for p, w in zip(schritt.pruefungen, werte)]


def test_schritt_ist_erledigt_wenn_alle_pruefungen_stimmen():
    schritt = _schritt("bilder")
    werte = [p.erwartet for p in schritt.pruefungen]

    assert s.ist_erledigt(schritt, _ergebnisse(schritt, werte)) is True


def test_schritt_ist_nicht_erledigt_wenn_eine_pruefung_abweicht():
    schritt = _schritt("bilder")
    werte = [p.erwartet - 1 for p in schritt.pruefungen]

    assert s.ist_erledigt(schritt, _ergebnisse(schritt, werte)) is False


def test_schritt_ist_nicht_erledigt_wenn_die_messung_scheiterte():
    schritt = _schritt("bilder")
    werte = [None for _ in schritt.pruefungen]

    assert s.ist_erledigt(schritt, _ergebnisse(schritt, werte)) is False


def test_schritt_ohne_pruefung_gilt_nie_als_erledigt():
    # setup_objects ist selbst idempotent und billig, der laeuft immer.
    schritt = s.Schritt("x", "x", "python", "scripts/x.py", "1 s", ())

    assert s.ist_erledigt(schritt, []) is False


def test_ist_erledigt_ignoriert_fremde_messwerte():
    schritt = _schritt("bilder")
    fremd = pz.Pruefung("Sz9", "fremd", 1, "dest_pg", "SELECT 1")

    ergebnisse = [(fremd, 1)]

    assert s.ist_erledigt(schritt, ergebnisse) is False


# --- Plan -------------------------------------------------------------------

def test_plan_ueberspringt_erledigte_schritte():
    schritt = _schritt("bilder")
    ergebnisse = _ergebnisse(schritt, [p.erwartet for p in schritt.pruefungen])

    ergebnis = s.plan([schritt], ergebnisse, erzwingen=False)

    assert ergebnis == [(schritt, False)]


def test_plan_fuehrt_offene_schritte_aus():
    schritt = _schritt("bilder")
    ergebnisse = _ergebnisse(schritt, [0 for _ in schritt.pruefungen])

    assert s.plan([schritt], ergebnisse, erzwingen=False) == [(schritt, True)]


def test_erzwingen_laesst_auch_erledigte_schritte_laufen():
    schritt = _schritt("bilder")
    ergebnisse = _ergebnisse(schritt, [p.erwartet for p in schritt.pruefungen])

    assert s.plan([schritt], ergebnisse, erzwingen=True) == [(schritt, True)]


def test_plan_behaelt_die_reihenfolge_der_schritte():
    ergebnisse = []
    reihenfolge = [x.name for x, _ in s.plan(s.SCHRITTE, ergebnisse, False)]

    assert reihenfolge == [x.name for x in s.SCHRITTE]


# --- Messpunkte sammeln -----------------------------------------------------

def test_alle_pruefungen_sammelt_ueber_alle_schritte():
    gesammelt = s.alle_pruefungen(s.SCHRITTE)

    assert set(_schritt("bilder").pruefungen) <= set(gesammelt)


def test_alle_pruefungen_entfernt_doppelte_abfragen():
    p = pz.Pruefung("Sz1", "a", 1, "dest_pg", "SELECT 1")
    a = s.Schritt("a", "a", "python", "x", "1 s", (p,))
    b = s.Schritt("b", "b", "python", "x", "1 s", (p,))

    assert s.alle_pruefungen([a, b]) == [p]


# --- Auswahl auf der Kommandozeile -----------------------------------------

def test_nur_schritte_filtert_auf_die_genannten():
    gefiltert = s.nur_schritte(s.SCHRITTE, ["bilder", "dbt"])

    assert [x.name for x in gefiltert] == ["bilder", "dbt"]


def test_nur_schritte_behaelt_die_reihenfolge_der_liste():
    gefiltert = s.nur_schritte(s.SCHRITTE, ["dbt", "namen"])

    assert [x.name for x in gefiltert] == ["namen", "dbt"]


def test_nur_schritte_ohne_auswahl_laesst_alles_durch():
    assert s.nur_schritte(s.SCHRITTE, []) == s.SCHRITTE


def test_ab_schritt_laesst_den_rest_der_liste_laufen():
    ab = s.ab_schritt(s.SCHRITTE, "dbt")

    assert [x.name for x in ab] == [x.name for x in s.SCHRITTE][_pos("dbt"):]


def test_ab_schritt_wirft_bei_unbekanntem_namen():
    with pytest.raises(ValueError):
        s.ab_schritt(s.SCHRITTE, "gibt-es-nicht")


# --- Ausgabe ----------------------------------------------------------------

def test_formatiere_plan_nennt_jeden_schritt_mit_vorhaben():
    schritt = _schritt("bilder")
    text = s.formatiere_plan([(schritt, True)])

    assert "bilder" in text
    assert schritt.dauer in text


def test_formatiere_plan_kennzeichnet_uebersprungene_schritte():
    text = s.formatiere_plan([(_schritt("bilder"), False)])

    assert "ueberspringen" in text


def test_formatiere_plan_haelt_die_spalten_bei_langen_dauerangaben_ausgerichtet():
    # "~1 bis 2 min" ist breiter als "~5 s". Eine feste Spaltenbreite wuerde die
    # Folgespalte verschieben, sobald eine Angabe darueber liegt.
    kurz = s.Schritt("a", "a", "python", "x", "~5 s", ())
    lang = s.Schritt("b", "b", "python", "x", "~1 bis 2 min", ())
    zeilen = [z for z in s.formatiere_plan([(kurz, True), (lang, True)]).splitlines()
              if "[" in z]

    spalten = {z.index("ausfuehren") for z in zeilen}
    assert len(spalten) == 1, f"Spalte springt: {sorted(spalten)}"


def test_formatiere_plan_haelt_die_spalten_ab_der_zehnten_zeile_ausgerichtet():
    # Zaehler von [9/14] auf [10/14] wird ein Zeichen breiter. Ohne Auffuellen
    # verrutschen ab da alle Folgespalten.
    eintraege = [(x, True) for x in s.SCHRITTE]
    zeilen = [z for z in s.formatiere_plan(eintraege).splitlines() if "[" in z]

    spalten = {z.index("ausfuehren") for z in zeilen}
    assert len(spalten) == 1, f"Spalte springt: {sorted(spalten)}"
