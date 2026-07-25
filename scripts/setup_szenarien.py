"""
setup_szenarien.py - stellt aus dem Zustand nach install + setup-airbyte den
vollstaendigen Demo-Zustand her.

Warum es dieses Skript gibt: install.ps1 laedt die zehn Quelltabellen,
setup-airbyte.ps1 installiert Airbyte, und danach war Schluss. Wer dem
Installationsguide folgte, landete bei einem leeren Airbyte. Die sieben
Folgeschritte standen zwar in der Doku der einzelnen Szenarien, aber nirgends
als ein Ablauf.

Aufgerufen wird das Skript ueber die Wrapper, die vorher noch die
Voraussetzungen pruefen:
    scripts/setup-szenarien.ps1      (Windows)
    scripts/setup-szenarien.sh       (Linux/macOS)

Direkt geht auch:
    python scripts/setup_szenarien.py                  # alles Offene
    python scripts/setup_szenarien.py --liste          # nur zeigen, was ansteht
    python scripts/setup_szenarien.py --trockenlauf    # Plan ohne Ausfuehrung
    python scripts/setup_szenarien.py --nur bilder,dbt # einzelne Schritte
    python scripts/setup_szenarien.py --ab dbt         # ab hier den Rest
    python scripts/setup_szenarien.py --erzwingen      # auch Erledigtes neu

Idempotenz: vor dem Lauf wird einmal gemessen, welche Sollzustaende schon
stehen. Ein Schritt, dessen Sollzustand erreicht ist, wird uebersprungen. Das
lohnt sich, denn die Bilder brauchen ein bis drei Minuten und jeder Sync ein
bis zwei. Die Sollwerte sind dieselben wie in pruefe_szenarien.py und in
docs/ergebnisse.md belegt.

Die Reihenfolge ist nicht beliebig:
  * generate_accounts braucht die Namen aus fill_random_names
  * die View hso_user braucht die Accounts
  * die View braucht auch die Bilder: sie liest hso_images, und
    CREATE OR REPLACE VIEW prueft die referenzierten Tabellen sofort
  * der IdM-Sync braucht die Bilder, sonst bleibt image_id im Ziel leer
  * dbt braucht den FM-Sync, denn es baut fm_raeume aus fm_stamm im Ziel
  * der Sync von fm_raeume nach MySQL braucht dbt

Die Dauerangaben sind gemessen, nicht geschaetzt: einmal beim Aufbau von Null auf
einem frisch installierten Airbyte, einmal auf warmem Stack. Wo die Werte
auseinandergehen, steht der hoehere. Ein voller Aufbau von Null lag bei
14 Minuten 31 Sekunden. Der grosse Posten sind die sieben Syncs mit ihrem
Grundoverhead unabhaengig vom Datenvolumen (Befund 7 in docs/ergebnisse.md), die
1.100 Bilder und die Schema-Erkennung beim Anlegen der Connections.
"""

import os
import subprocess
import sys
import time
from dataclasses import dataclass

import pruefe_szenarien as pz

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Die Airbyte-Skripte liegen in scripts/airbyte/ und werden auch einzeln
# aufgerufen, sind also keine Pakete. Fuer den Import von hier aus muss ihr
# Verzeichnis auf sys.path (dasselbe macht conftest.py fuer die Tests).
sys.path.insert(0, os.path.join(WURZEL, "scripts", "airbyte"))
from setup_objects import read_env_file  # noqa: E402


# --- Schrittliste -----------------------------------------------------------

@dataclass(frozen=True)
class Schritt:
    name: str            # Schluessel fuer --nur und --ab
    beschreibung: str
    art: str             # python | sync | dbt
    ziel: str            # Skriptpfad, Connection-Name, bei dbt ungenutzt
    dauer: str           # Groessenordnung, fuer die Planausgabe
    pruefungen: tuple    # alle erfuellt bedeutet: Schritt ist erledigt


def _soll(szenario: str, teil: str):
    """Sollwert aus pruefe_szenarien holen, damit er nur an einer Stelle steht."""
    treffer = [p for p in pz.SOLLWERTE
               if p.szenario == szenario and teil in p.beschreibung]
    if len(treffer) != 1:
        raise ValueError(f"{szenario}/{teil}: {len(treffer)} Treffer in SOLLWERTE")
    return treffer[0]


# Zusaetzliche Messpunkte, die kein Szenario-Sollwert sind, sondern nur die
# Frage beantworten: ist dieser Schritt schon gelaufen? Alle Zahlen sind in
# docs/ergebnisse.md belegt (Befunde 2, 30, 31).
NAMEN_GESETZT = pz.Pruefung(
    "Sz4", "Studierende mit Nachname", 5052, "source_pg",
    "SELECT count(*) FROM hso_students WHERE COALESCE(surname, '') <> ''")
PERSONAL_GESETZT = pz.Pruefung(
    "Sz4", "Personal mit Nachname", 870, "source_pg",
    "SELECT count(*) FROM hso_personal WHERE COALESCE(nachname, '') <> ''")
VIEW_DA = pz.Pruefung(
    "Sz5", "View hso_user in der Quelle", 5922, "source_pg",
    "SELECT count(*) FROM hso_user")
STUDENTS_IM_ZIEL = pz.Pruefung(
    "Sz1", "hso_students in dest-postgres", 5052, "dest_pg",
    "SELECT count(*) FROM hso_students")
FM_STAMM_IM_ZIEL = pz.Pruefung(
    "Sz2", "fm_stamm in dest-postgres", 1244, "dest_pg",
    "SELECT count(*) FROM fm_stamm")
GEBAEUDE_IN_MYSQL = pz.Pruefung(
    "Sz1", "fm_gebaeude in dest-mysql", 25, "dest_mysql",
    "SELECT count(*) FROM fm_gebaeude")
PLZ_IN_MYSQL = pz.Pruefung(
    "Sz1", "k_plz in dest-mysql", 34172, "dest_mysql",
    "SELECT count(*) FROM k_plz")


SCHRITTE = [
    Schritt("namen", "Zufallsnamen in hso_students und hso_personal setzen",
            "python", "scripts/mapping/fill_random_names.py", "~2 s",
            (NAMEN_GESETZT, PERSONAL_GESETZT)),

    Schritt("accounts", "Account-IDs nach HSO-Schema vergeben (Szenario 4)",
            "python", "scripts/mapping/generate_accounts.py", "~2 s",
            (_soll("Sz4", "user_id gesetzt"), _soll("Sz4", "eindeutige user_id"))),

    # Vor der View, nicht danach: die View liest hso_images, und
    # CREATE OR REPLACE VIEW prueft die referenzierten Tabellen sofort. Auf
    # einem frischen Stack existiert hso_images erst nach diesem Schritt.
    Schritt("bilder", "1.100 Bilder als BYTEA laden (Szenario 3)",
            "python", "scripts/images/load_images.py", "~2 min",
            (_soll("Sz3", "hso_images in der Quelle"),)),

    Schritt("view", "View hso_user anlegen (Szenario 5)",
            "python", "scripts/mapping/create_hso_user_view.py", "~1 s",
            (VIEW_DA,)),

    # Ohne Pruefung: beide Skripte sind selbst idempotent und brauchen nur
    # Sekunden. Sie laufen immer, damit ein fehlendes Airbyte-Objekt nach einem
    # abctl-Neuaufbau garantiert nachgezogen wird (Befund 19).
    Schritt("objekte", "Airbyte Sources und Destinations anlegen",
            "python", "scripts/airbyte/setup_objects.py", "~30 s", ()),

    Schritt("connections", "Airbyte Connections anlegen",
            "python", "scripts/airbyte/setup_connections.py", "~2 min", ()),

    Schritt("sync-pg", "Sync fm_gebaeude und k_plz nach dest-postgres (Szenario 1)",
            "sync", "HSO PG nach PG (Full Refresh)", "~1 bis 2 min",
            (_soll("Sz1", "fm_gebaeude"), _soll("Sz1", "k_plz"))),

    Schritt("sync-mysql", "Sync fm_gebaeude und k_plz nach dest-mysql (Szenario 1)",
            "sync", "HSO PG nach MySQL (Full Refresh)", "~1 bis 2 min",
            (GEBAEUDE_IN_MYSQL, PLZ_IN_MYSQL)),

    Schritt("sync-students", "Sync hso_students.csv per File-Connector",
            "sync", "HSO CSV hso_students nach PG", "~1 bis 2 min",
            (STUDENTS_IM_ZIEL,)),

    # fm_gebaeude liegt schon aus sync-pg im Ziel und darf hier nicht nochmal
    # kommen, sonst verdoppelt sich die Tabelle (siehe Kommentar in
    # setup_connections.py).
    Schritt("sync-fm", "Sync fm_stamm und fm_inst nach dest-postgres",
            "sync", "HSO FM nach PG", "~1 bis 2 min",
            (FM_STAMM_IM_ZIEL,)),

    Schritt("sync-bilder", "Sync hso_images nach MySQL (Szenario 3, Befund 1)",
            "sync", "HSO Bilder nach MySQL", "~1 bis 2 min",
            (_soll("Sz3", "hso_images Zeilen in MySQL"),
             _soll("Sz3", "mit Inhalt"))),

    Schritt("sync-idm", "Sync hso_user nach MySQL, Incremental mit Dedup (Szenario 5)",
            "sync", "HSO IdM hso_user nach MySQL", "~1 bis 2 min",
            (_soll("Sz5", "hso_user Zeilen"), _soll("Sz5", "verschiedene user_id"),
             _soll("Sz5", "mit image_id"))),

    Schritt("dbt", "fm_raeume in dest-postgres bauen (Szenario 2)",
            "dbt", "", "~5 s",
            (_soll("Sz2", "fm_raeume Zeilen"), _soll("Sz2", "mit Institut"))),

    # Beim ersten Aufbau gab es fm_raeume in dest-postgres noch nicht, als
    # 'connections' lief, die Connection wurde deshalb vertagt. Jetzt existiert
    # die Tabelle, also nachziehen. Die Pruefung ist dieselbe wie bei
    # sync-raeume: liegt fm_raeume schon in MySQL, ist hier nichts zu tun.
    Schritt("connections-raeume", "Vertagte Connection fuer fm_raeume nachziehen",
            "python", "scripts/airbyte/setup_connections.py", "~40 s",
            (_soll("Sz2", "fm_raeume in MySQL"),)),

    Schritt("sync-raeume", "Sync fm_raeume nach MySQL (Szenario 2, Teil B)",
            "sync", "HSO fm_raeume nach MySQL", "~1 bis 2 min",
            (_soll("Sz2", "fm_raeume in MySQL"),)),
]


# --- reine Funktionen -------------------------------------------------------

def kommando(schritt: Schritt, python_exe: str) -> list:
    """Argumentliste fuer diesen Schritt."""
    if schritt.art == "python":
        return [python_exe, os.path.join(WURZEL, schritt.ziel)]
    if schritt.art == "sync":
        return [python_exe,
                os.path.join(WURZEL, "scripts", "airbyte", "run_sync.py"),
                schritt.ziel]
    if schritt.art == "dbt":
        return [python_exe, "-m", "dbt.cli.main", "run",
                "--project-dir", os.path.join(WURZEL, "dbt"),
                "--profiles-dir", os.path.join(WURZEL, "dbt")]
    raise ValueError(f"unbekannte Art: {schritt.art}")


def alle_pruefungen(schritte) -> list:
    """Messpunkte aller Schritte, jede Abfrage nur einmal."""
    gesehen, gesammelt = set(), []
    for schritt in schritte:
        for p in schritt.pruefungen:
            schluessel = (p.quelle, p.abfrage)
            if schluessel in gesehen:
                continue
            gesehen.add(schluessel)
            gesammelt.append(p)
    return gesammelt


def ist_erledigt(schritt: Schritt, ergebnisse) -> bool:
    """True, wenn jeder Sollzustand dieses Schrittes schon gemessen wurde.

    Ein Schritt ohne Pruefung gilt nie als erledigt: das sind die idempotenten
    und billigen, die einfach immer laufen duerfen.
    """
    if not schritt.pruefungen:
        return False
    gemessen = {(p.quelle, p.abfrage): wert for p, wert in ergebnisse}
    return all(gemessen.get((p.quelle, p.abfrage)) == p.erwartet
               for p in schritt.pruefungen)


def plan(schritte, ergebnisse, erzwingen: bool) -> list:
    """[(Schritt, ausfuehren?)] in der Reihenfolge der Liste."""
    return [(schritt, True if erzwingen else not ist_erledigt(schritt, ergebnisse))
            for schritt in schritte]


def nur_schritte(schritte, auswahl):
    """Filtert auf die genannten Namen, behaelt aber die feste Reihenfolge."""
    if not auswahl:
        return schritte
    gewuenscht = {a.strip().lower() for a in auswahl if a.strip()}
    return [s for s in schritte if s.name.lower() in gewuenscht]


def ab_schritt(schritte, name: str):
    """Diesen Schritt und alles danach."""
    namen = [s.name.lower() for s in schritte]
    if name.strip().lower() not in namen:
        raise ValueError(f"unbekannter Schritt: {name}")
    return schritte[namen.index(name.strip().lower()):]


def formatiere_plan(eintraege) -> str:
    zeilen = []
    gesamt = len(eintraege)
    breite = len(str(gesamt))          # damit [9/15] und [10/15] gleich breit sind
    # Spalten am laengsten Eintrag ausrichten, nicht an festen Zahlen: ein neuer
    # Schritt oder eine laengere Dauerangabe darf die Folgespalten nicht
    # verschieben.
    namen = max((len(s.name) for s, _ in eintraege), default=0)
    dauern = max((len(s.dauer) for s, _ in eintraege), default=0)
    einzug = " " * len(f"  [{'':>{breite}}/{gesamt}] ")
    for nummer, (schritt, ausfuehren) in enumerate(eintraege, start=1):
        vorhaben = ("ausfuehren" if ausfuehren
                    else "ueberspringen (Sollzustand steht)")
        zeilen.append(f"  [{nummer:>{breite}}/{gesamt}] {schritt.name:<{namen}} "
                      f"{schritt.dauer:<{dauern}} {vorhaben}")
        zeilen.append(f"{einzug}{schritt.beschreibung}")
    return "\n".join(zeilen)


def dauer_text(sekunden: float) -> str:
    if sekunden < 60:
        return f"{sekunden:.0f} s"
    return f"{int(sekunden // 60)} min {int(sekunden % 60):02d} s"


# --- Ausfuehrung ------------------------------------------------------------

def umgebung() -> dict:
    """Prozessumgebung plus .env, ohne bereits gesetzte Werte zu ueberschreiben.

    dbt liest Host, Port und Passwort ueber env_var aus profiles.yml. Ohne die
    .env laeuft es auf den Standardwerten, was bei angepassten Passwoertern
    schiefgeht, und zwar erst im dbt-Lauf.
    """
    werte = dict(os.environ)
    for schluessel, wert in read_env_file(os.path.join(WURZEL, ".env")).items():
        werte.setdefault(schluessel, wert)
    return werte


def fuehre_aus(schritt: Schritt, python_exe: str) -> int:
    argv = kommando(schritt, python_exe)
    start = time.time()
    fertig = subprocess.run(argv, cwd=WURZEL, env=umgebung())
    print(f"    ({dauer_text(time.time() - start)})")
    return fertig.returncode


HILFE = """Aufruf: python scripts/setup_szenarien.py [Optionen]

    --liste            nur den Plan zeigen, nichts ausfuehren
    --trockenlauf      wie --liste (nach dem Messen), nichts ausfuehren
    --nur a,b          nur diese Schritte
    --ab name          diesen Schritt und alles danach
    --erzwingen        auch erledigte Schritte neu ausfuehren
    --python PFAD      Interpreter fuer die Unterprozesse

Schritte in der festen Reihenfolge:
""" + "\n".join(f"    {s.name:<14} {s.dauer:<7} {s.beschreibung}"
                for s in SCHRITTE)


def wert_nach(argv, option, standard=None):
    """Wert einer Option, sowohl '--nur a,b' als auch '--nur=a,b'."""
    for i, arg in enumerate(argv):
        if arg == option and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith(option + "="):
            return arg.split("=", 1)[1]
    return standard


def main(argv):
    if any(a in ("-h", "--help") for a in argv):
        print(HILFE)
        return 0

    python_exe = wert_nach(argv, "--python", sys.executable)
    schritte = SCHRITTE
    auswahl = wert_nach(argv, "--nur")
    if auswahl:
        schritte = nur_schritte(schritte, auswahl.split(","))
        if not schritte:
            print(f"Kein Schritt passt zu: {auswahl}")
            return 1
    ab = wert_nach(argv, "--ab")
    if ab:
        try:
            schritte = ab_schritt(schritte, ab)
        except ValueError as e:
            print(str(e))
            return 1

    if "--liste" in argv:
        print(HILFE)
        return 0

    print("Messe, welche Sollzustaende schon stehen...")
    ergebnisse = pz.messe(alle_pruefungen(schritte), pz.quellen())
    eintraege = plan(schritte, ergebnisse, erzwingen="--erzwingen" in argv)

    offen = [s for s, tun in eintraege if tun]
    print()
    print(formatiere_plan(eintraege))
    print(f"\n{len(offen)} von {len(eintraege)} Schritten auszufuehren.")

    if "--trockenlauf" in argv:
        print("Trockenlauf, es wird nichts ausgefuehrt.")
        return 0
    if not offen:
        print("Der Demo-Zustand steht schon. Nachpruefen:"
              " python scripts/pruefe_szenarien.py")
        return 0

    start = time.time()
    for nummer, (schritt, ausfuehren) in enumerate(eintraege, start=1):
        if not ausfuehren:
            print(f"\n==> [{nummer}/{len(eintraege)}] {schritt.name}:"
                  " uebersprungen, Sollzustand steht.")
            continue
        print(f"\n==> [{nummer}/{len(eintraege)}] {schritt.name}"
              f" ({schritt.dauer}): {schritt.beschreibung}")
        code = fuehre_aus(schritt, python_exe)
        if code != 0:
            print(f"\nAbbruch: Schritt '{schritt.name}' endete mit Code {code}.")
            print("Nach der Ursache sehen, dann hier weitermachen:")
            print(f"    python scripts/setup_szenarien.py --ab {schritt.name}")
            return code

    print(f"\nFertig in {dauer_text(time.time() - start)}.")
    print("Zustand pruefen: python scripts/pruefe_szenarien.py")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
