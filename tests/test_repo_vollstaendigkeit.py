"""Waechter: keine Datei, die der Aufbau braucht, darf von .gitignore erfasst sein.

Warum es diese Datei gibt: `scripts/airbyte/` fiel unter die .gitignore-Regel
`airbyte/`, die ohne fuehrenden Schraegstrich jedes Verzeichnis dieses Namens in
beliebiger Tiefe erfasst. Zwei der drei Airbyte-Skripte landeten deshalb nie im
Repo. Lokal lief alles, denn die Dateien lagen ja auf der Platte. Wer klonte,
bekam sie nicht und scheiterte beim Anlegen der Connections.

Geprueft wird bewusst die Ignore-Regel und nicht, ob eine Datei schon getrackt
ist. Eine frisch angelegte, noch nicht committete Datei ist normaler
Arbeitsstand und darf die Suite nicht rot machen. Eine ignorierte Datei ist
dagegen immer ein Fehler, denn sie taucht in `git status` nie auf.

`git check-ignore --no-index` fragt nur die Muster ab, unabhaengig davon, ob die
Datei bereits getrackt ist. Das ist wichtig: die eine Datei, die damals
durchkam, war getrackt und wurde deshalb von der Standardabfrage als harmlos
gemeldet, obwohl das Muster auf sie passte.

Ohne git werden die Tests uebersprungen, damit ein entpacktes Archiv keinen
falschen Alarm gibt.
"""
import os
import re
import subprocess

import pytest

import setup_szenarien as s

WURZEL = s.WURZEL


# --- Zugriff auf die Ignore-Regeln ------------------------------------------

def git_verfuegbar() -> bool:
    try:
        fertig = subprocess.run(["git", "rev-parse", "--git-dir"], cwd=WURZEL,
                                capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return fertig.returncode == 0


BUENDEL = 100          # Pfade pro Aufruf, damit die Kommandozeile kurz bleibt


def ignorierte(pfade):
    """Die Pfade, auf die eine .gitignore-Regel passt, in der Eingabereihenfolge.

    --no-index, damit auch bereits getrackte Dateien geprueft werden: eine
    passende Regel ist auch dann ein Fehler, sie schlaegt nur spaeter zu, beim
    naechsten Verschieben oder Umbenennen.

    Die Pfade gehen als Argumente mit, nicht ueber stdin. Auf Windows uebersetzt
    der Textmodus das Trennzeichen zu CRLF, und git nimmt das CR als Teil des
    Pfadnamens: die Antwort lautet dann "scripts/airbyte/run_sync.py\\r".
    """
    pfade = list(pfade)
    treffer = []
    for anfang in range(0, len(pfade), BUENDEL):
        buendel = pfade[anfang:anfang + BUENDEL]
        fertig = subprocess.run(
            ["git", "check-ignore", "--no-index", "--"] + buendel, cwd=WURZEL,
            capture_output=True, text=True, timeout=60)
        # Exit 0: mindestens einer ignoriert. 1: keiner. Sonst ein echter Fehler.
        if fertig.returncode not in (0, 1):
            raise RuntimeError(f"git check-ignore: {fertig.stderr.strip()[:200]}")
        treffer.extend(z.strip().replace(os.sep, "/")
                       for z in fertig.stdout.splitlines() if z.strip())
    return treffer


def relativ(pfad: str) -> str:
    """Absoluten Pfad in die Schreibweise von git bringen."""
    return os.path.relpath(pfad, WURZEL).replace(os.sep, "/")


@pytest.fixture(scope="module", autouse=True)
def _braucht_git():
    if not git_verfuegbar():
        pytest.skip("kein git-Arbeitsverzeichnis")


def _python_dateien(unterordner):
    treffer = []
    for wurzel, verzeichnisse, dateien in os.walk(os.path.join(WURZEL, unterordner)):
        verzeichnisse[:] = [v for v in verzeichnisse if v != "__pycache__"]
        treffer.extend(relativ(os.path.join(wurzel, d))
                       for d in dateien if d.endswith(".py"))
    return sorted(treffer)


HINWEIS = ("Diese Dateien passen auf eine .gitignore-Regel und landen deshalb"
           " nie im Repo. Haeufigste Ursache: ein Muster ohne fuehrenden"
           " Schraegstrich, das auf jedes Verzeichnis dieses Namens passt. ")


# --- die reine Hilfsfunktion -------------------------------------------------

def test_relativ_liefert_schraegstriche():
    ergebnis = relativ(os.path.join(WURZEL, "scripts", "setup_szenarien.py"))

    assert ergebnis == "scripts/setup_szenarien.py"


def test_ignorierte_meldet_nichts_bei_leerer_eingabe():
    assert ignorierte([]) == []


def test_ignorierte_erkennt_eine_tatsaechlich_ignorierte_datei():
    # .env steht in der .gitignore und ist der Referenzfall fuer diese Abfrage.
    assert ignorierte([".env"]) == [".env"]


def test_ignorierte_laesst_eine_normale_datei_durch():
    assert ignorierte(["scripts/setup_szenarien.py"]) == []


def test_ignorierte_liefert_mehrere_pfade_unverfaelscht():
    # Ab zwei Pfaden trat ein Windows-Fehler auf: die Newline-Uebersetzung haengte
    # jedem Pfad ein CR an, git gab ihn als "...py\\r" zurueck, und die
    # Fehlermeldung nannte Pfade, die es so nicht gibt.
    assert ignorierte([".env", "airbyte/x.log"]) == [".env", "airbyte/x.log"]


def test_ignorierte_mischt_ignorierte_und_harmlose_pfade_richtig():
    ergebnis = ignorierte(["scripts/setup_szenarien.py", ".env",
                           "scripts/pruefe_szenarien.py", "abctl/abctl.exe"])

    assert ergebnis == [".env", "abctl/abctl.exe"]


# --- ganze Verzeichnisse -----------------------------------------------------

def test_kein_python_skript_unter_scripts_ist_ignoriert():
    betroffen = ignorierte(_python_dateien("scripts"))

    assert betroffen == [], HINWEIS + ", ".join(betroffen)


def test_keine_testdatei_ist_ignoriert():
    betroffen = ignorierte(_python_dateien("tests"))

    assert betroffen == [], HINWEIS + ", ".join(betroffen)


def test_kein_dokument_unter_docs_ist_ignoriert():
    docs = sorted(relativ(os.path.join(WURZEL, "docs", d))
                  for d in os.listdir(os.path.join(WURZEL, "docs"))
                  if d.endswith(".md"))
    betroffen = ignorierte(docs)

    assert betroffen == [], HINWEIS + ", ".join(betroffen)


# --- was der Aufbau namentlich braucht ---------------------------------------

def test_kein_python_schritt_des_aufbaus_ist_ignoriert():
    betroffen = ignorierte([x.ziel for x in s.SCHRITTE if x.art == "python"])

    assert betroffen == [], HINWEIS + ", ".join(betroffen)


def test_das_sync_skript_ist_nicht_ignoriert():
    # Pfad aus kommando() holen statt selbst zusammenzubauen, sonst prueft der
    # Test seine eigene Annahme statt die des Produktivcodes.
    sync = next(x for x in s.SCHRITTE if x.art == "sync")
    argv = s.kommando(sync, "python")

    assert ignorierte([relativ(argv[1])]) == []


def test_die_dbt_dateien_sind_nicht_ignoriert():
    argv = s.kommando(next(x for x in s.SCHRITTE if x.art == "dbt"), "python")
    verzeichnisse = {relativ(argv[i + 1]) for i, a in enumerate(argv)
                     if a in ("--project-dir", "--profiles-dir")}
    gebraucht = [f"{v}/dbt_project.yml" for v in sorted(verzeichnisse)]
    gebraucht += ["dbt/profiles.yml", "dbt/models/fm_raeume.sql",
                  "dbt/models/schema.yml", "dbt/models/sources.yml"]

    assert ignorierte(gebraucht) == []


def test_die_view_definition_ist_nicht_ignoriert():
    assert ignorierte(["sql/source/views/hso_user.sql"]) == []


def test_die_wrapper_skripte_sind_nicht_ignoriert():
    wrapper = ["scripts/install.ps1", "scripts/install.sh",
               "scripts/setup-airbyte.ps1", "scripts/setup-airbyte.sh",
               "scripts/setup-szenarien.ps1", "scripts/setup-szenarien.sh"]

    assert ignorierte(wrapper) == []


def test_die_von_install_geladenen_loader_sind_nicht_ignoriert():
    """Die Loader-Liste aus install.sh gegen die Ignore-Regeln pruefen.

    Faengt zugleich eine Umbenennung, die install.sh nicht mitgezogen hat: die
    Liste muss auf vorhandene Dateien zeigen.
    """
    with open(os.path.join(WURZEL, "scripts", "install.sh"), encoding="utf-8") as f:
        loader = sorted(set(re.findall(r"scripts/load_\w+\.py", f.read())))

    assert loader, "keine Loader in install.sh gefunden, Format geaendert?"
    fehlend = [p for p in loader if not os.path.exists(os.path.join(WURZEL, p))]
    assert fehlend == [], "install.sh nennt Loader, die es nicht gibt: " + ", ".join(fehlend)
    assert ignorierte(loader) == []


def test_conftest_zeigt_nur_auf_vorhandene_verzeichnisse():
    # Ein sys.path-Eintrag auf ein fehlendes Verzeichnis faellt sonst erst auf,
    # wenn ein Import ins Leere greift.
    with open(os.path.join(WURZEL, "conftest.py"), encoding="utf-8") as f:
        eintrag = re.search(r"for _unterordner in \(([^)]*)\)", f.read()).group(1)
    namen = [n.strip().strip('"').strip("'") for n in eintrag.split(",") if n.strip()]

    assert namen, "conftest-Format geaendert, Test anpassen"
    for name in namen:
        pfad = os.path.join(WURZEL, "scripts", name)
        assert os.path.isdir(pfad), f"conftest verweist auf {pfad}"
