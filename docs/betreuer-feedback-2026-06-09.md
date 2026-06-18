# Betreuer-Feedback & Reaktion — 09.06.2026

**Quelle:** Rückmeldung der Betreuung (CS / Prof. Dr. Jan Münchenberg) zum [Zwischenbericht](zwischenbericht.md).
**Reaktion dokumentiert (Stand):** 2026-06-16.

Dieses Dokument hält das Feedback fest und ordnet jeder Aussage unsere Reaktion und den
Umsetzungsstand zu. Es ist die zentrale Referenz; die „Offenen Fragen" in
[zwischenbericht.md §6](zwischenbericht.md) und [anforderungen.md §3](anforderungen.md)
verweisen hierauf.

Legende: ✅ umgesetzt · ◑ teilweise · ⏳ offen (für Endpräsentation)

---

## 1. Allgemeines Feedback

> - sehr gut strukturiert
> - Meilensteine sind sehr gut und detailliert
> - Architektur-Bild ist ok, sollte für die endgültige Präsentation aber noch besser visualisiert werden
> - Ansonsten sehr guter Zwischenbericht und auch sehr gute Dokumentation im GIT-Repo

**Reaktion:** Durchweg positiv — keine Korrektur nötig, mit **einer** Ausnahme:

- ⏳ **Architektur-Diagramm:** Aktuell ASCII-Darstellung in [architektur.md](architektur.md).
  Für die Abschlusspräsentation eine sauber visualisierte Grafik erstellen.

---

## 2. Antworten auf unsere Fragen — und unsere Reaktion

### 2.1 `hso_students.csv` — Soll-Struktur?

> Ja, die Daten sind so, wie sie beim Export erzeugt wurden. Sollten Sie mit Bordmitteln
> von Airbyte keine Datenkorrekturen ausführen können, dann ermitteln Sie sich bitte selbst
> Alternativen (zur Not auch händisch), aber dokumentieren dies bitte.

**Reaktion:** ✅ Eigene Alternative umgesetzt **und** dokumentiert. Die Datei ist
pipe-getrennt mit *gequoteten* Feldern (die frühere Diagnose „mehr Spalten als Header" war
falsch). Ein quote-bewusster Parser lädt alle **5.052 Zeilen** verlustfrei.

- Umsetzung: [`scripts/load_hso_students.py`](../scripts/load_hso_students.py)
- In die Installation eingebunden (`install.ps1`/`install.sh`), in
  [`01_load_data.sql`](../sql/source/01_load_data.sql) und
  [testszenarien.md](testszenarien.md) dokumentiert.
- Zusätzlich weiterhin über den Airbyte File-Connector verfügbar.

### 2.2 Raumstammdaten `fm_stamm`

> Die `fm_stamm` ist die Systemtabelle für die Räume; diese sollten Sie als Teil des
> ETL-Mappings selbst versuchen, mit den Daten aus der `rooms.xml` zu befüllen.

**Reaktion:** ✅ Umgesetzt. Quelle ist die Excel-Vorlage **`rooms.xltx`** (der Betreuer
schrieb „rooms.xml"). Das ETL-Mapping befüllt `fm_stamm` mit **1.245 Zeilen**
(1.244 + 1 übersprungene PK-Dublette).

- Umsetzung: [`scripts/load_fm_stamm.py`](../scripts/load_fm_stamm.py) (liest
  `sql/source/data/rooms.xltx`), in die Installation eingebunden.
- Dokumentiert in [etl-prozess.md](etl-prozess.md) (inkl. Stolperstein
  „Timestamp is not JSON serializable" beim File-Connector + Lösung).

### 2.3 Zugang für Betreuer

> Für die Evaluation reicht es aus, wenn Sie uns bei der Abschlusspräsentation das
> Live-System zeigen. Wichtig ist jedoch, dass Sie auch die Installation und „First-Steps"
> gut dokumentieren.

**Reaktion:** ✅ Kein Remote-/Dauer-Zugang nötig — Live-Demo bei der Abschlusspräsentation.
Installation und First-Steps sind dokumentiert:

- [installation-guide.md](installation-guide.md), [etl-prozess.md](etl-prozess.md),
  [zugang.md](zugang.md)
- `install.ps1`/`install.sh` richten den kompletten Stack inkl. aller Testdaten automatisch ein.

### 2.4 Sync-Strategie (CDC vs. Cursor)

> Ich bin leider nicht so vertraut mit der Strategie. Das sollten Sie eventuell mit in die
> Dokumentation schreiben — welche Vor-/Nachteile und was der Aufwand ist. […] Bei CDC
> handelt es sich um eine besondere Strategie mit Snapshots von Logs/Protokollen unabhängig
> von der Datenbank, und der Cursor-Modus läuft einfach über den Zeitstempel. Dann reicht
> der Zeitstempel als Synchronisationsstrategie aus.

**Reaktion:** ◑ Der Betreuer **bestätigt** unseren Ansatz: der **Cursor-Modus über den
Zeitstempel (`updatedat`) genügt** für die Evaluation. Ein Methodenvergleich
(CDC / Xmin / User-Defined-Cursor) steht bereits in
[airbyte-setup.md §5](airbyte-setup.md).

- ⏳ **Offen (Endpräsentation):** Den expliziten **Vor-/Nachteile-+-Aufwand-Abschnitt**
  ausformulieren und die hier bestätigte Entscheidung darin festhalten.

### 2.5 Scope / Szenario-Priorisierung

> Die Herangehensweise und die Streuung der Themen ist wichtig, nicht die konkreten
> Szenarien. Es wird also nicht bewertet, wenn Sie nur 4/6 Szenarien lösen konnten, sondern
> zu 99,999…% Ihre Herangehensweise und die Lösungen, die Sie im Team dokumentiert haben.

**Reaktion:** ✅ Kein Handlungsdruck, alle sechs Szenarien vollständig zu lösen. Fokus liegt
auf nachvollziehbarer Herangehensweise und sauberer Doku der gewählten Lösungen.

---

## 3. Zusammenfassung

| Punkt | Status |
|---|---|
| hso_students — eigene Alternative + Doku | ✅ |
| fm_stamm aus rooms befüllen | ✅ |
| Zugang Betreuer (Live-Demo + Installations-Doku) | ✅ |
| Scope (Herangehensweise zählt) | ✅ (informativ) |
| Sync-Strategie (Vor-/Nachteile + Aufwand) | ◑ bestätigt; Detail-Abschnitt offen |
| Architektur-Diagramm besser visualisieren | ⏳ offen |

**Vom Betreuer in dieser Runde *nicht* adressiert** (bleiben offen, siehe
[anforderungen.md §3](anforderungen.md)): Informix-Anbindung, Code-Snippet-Ausführung (A7),
SOAP/HISinOne-Zugang (Szenario 6b).
