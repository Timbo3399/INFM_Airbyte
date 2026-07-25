"""Tests fuer scripts/mapping/fill_random_names.py (keine DB noetig).

Szenario 4, Schritt 1: die anonymisierten Quelldaten haben leere Namensfelder
(firstname/surname in allen 5.052 Studierenden-Zeilen, vorname/nachname in allen
870 Personal-Zeilen). Ohne Namen erzeugt der Account-Generator nichts.
"""
import fill_random_names as f


def test_gleiche_id_ergibt_immer_denselben_namen():
    # Deterministisch, damit ein zweiter Lauf die DB nicht umschreibt.
    assert f.generate_person(176594) == f.generate_person(176594)


def test_verschiedene_ids_ergeben_verschiedene_namen():
    namen = {f.generate_person(i) for i in range(200)}
    assert len(namen) > 150          # keine nennenswerte Haeufung


def test_name_ist_nie_leer():
    for i in (0, 1, 42, 176594):
        vorname, nachname = f.generate_person(i)
        assert vorname.strip() and nachname.strip()


def test_namenspool_enthaelt_umlaute():
    # Sonst laeuft die Umlaut-Transliteration im Account-Generator nie durch.
    alle = "".join(f.FIRST_NAMES + f.LAST_NAMES)
    assert any(c in alle for c in "äöüßÄÖÜ")


def test_private_email_folgt_dem_namen():
    assert f.private_email("Jens", "Müller") == "jens.mueller@example.org"


def test_private_email_entfernt_akzente_und_sonderzeichen():
    assert f.private_email("José", "D'Angelo") == "jose.dangelo@example.org"
