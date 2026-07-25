# Zugang zum System

Dieses Dokument beschreibt, wie auf die Airbyte-Oberfläche und die Datenbanken
zugegriffen wird, einschließlich des Zugangs für die Betreuer (Herr Stippekohl und Dozent).

---

## 1. Airbyte-UI

| | |
|---|---|
| URL | **http://localhost:8000** |
| Login anzeigen | `abctl local credentials` |

`abctl local credentials` gibt E-Mail, ein generiertes Passwort sowie Client-ID und Secret aus.
Das Passwort erscheint dabei im **Klartext**, der Befehl sollte deshalb nur bei Bedarf laufen.

### Eigenes / gemeinsames Passwort setzen

In **zwei getrennten** Aufrufen, **erst die E-Mail**, dann das Passwort:

```powershell
abctl local credentials --email <login-email>            # 1) Login-Name (E-Mail)
abctl local credentials --password <gewuenschtes-passwort> # 2) Passwort
```

> **Warum getrennt?** Der **kombinierte** Aufruf `--email … --password …` schlägt mit
> abctl 0.30.x + Airbyte 2.1.0 fehl (`unable to determine organization email` /
> `invalid character '<'`, da der Org-Lookup HTML statt JSON liefert). Getrennt klappt es.
> Die E-Mail ist frei wählbar (z. B. `admin@example.com`) und der Login-Name in der UI.
> Das Setup-Skript erledigt beides automatisch.

> Für den Betreuer-Termin empfiehlt sich ein **bewusst gesetztes, gemeinsames Passwort**
> (statt des generierten), damit alle denselben Login verwenden können.

**Aktueller Zugang (von der Gruppe auszufüllen / NICHT öffentlich committen):**

| Feld | Wert |
|---|---|
| URL | http://localhost:8000 |
| E-Mail | ‹…› |
| Passwort | ‹separat und sicher teilen, nicht ins Repo› |

---

## 2. Zugang für die Betreuer (Herr Stippekohl + Dozent)

**Wichtige Rahmenbedingung:** Airbyte **Community Edition** (über `abctl`) ist im
Kern **Einzelnutzer-orientiert** und läuft auf `localhost` des Entwicklungsrechners.
Mehrbenutzer-/RBAC-Funktionen sind der Enterprise-/Cloud-Variante vorbehalten. Es
gibt daher keine getrennten Benutzerkonten pro Betreuer, sondern **einen Admin-Login**.

### Gewählte Variante

**Live-Demo im Termin.** Der Betreuer hat am 09.06.2026 entschieden, dass eine Vorführung
des laufenden Systems bei der Abschlusspräsentation genügt und kein Remote-Zugang nötig
ist (siehe [betreuer-feedback-2026-06-09.md](betreuer-feedback-2026-06-09.md)). Wir zeigen
das System live auf unserem Rechner, die Betreuer nutzen bei Bedarf den gemeinsamen
Admin-Login aus Abschnitt 1. Das erzeugt keinen zusätzlichen Aufwand und kein
Sicherheitsrisiko.

Falls doch einmal ein Zugang von außen gebraucht wird, lässt sich die lokale UI
kurzzeitig über einen Tunnel erreichbar machen:

```powershell
# Beispiel mit cloudflared (temporäre öffentliche URL auf localhost:8000)
cloudflared tunnel --url http://localhost:8000
```

Der erzeugte Link und die Login-Daten gehen dann direkt an die Betreuer. Ein solcher
Tunnel wird nur für den Zweck aktiviert und danach wieder beendet.

---

## 3. Verbindungsparameter (zentrale Referenz)

> **Diese Tabelle ist die einzige Quelle für Ports und Zugangsdaten im Projekt.**
> Andere Dokumente (README, installation-guide, architektur, airbyte-setup) verlinken hierher,
> statt die Werte zu duplizieren.

Standardwerte aus `.env.example`. Wurden sie in `.env` geändert, gelten die dortigen Werte.

| Dienst | DB-Tools (lokal) | In der Airbyte-UI eintragen | DB | User | Passwort |
|---|---|---|---|---|---|
| Source PostgreSQL | `localhost:5433` | `host.docker.internal:5433` | `sourcedb` | `sourceuser` | `sourcepassword` |
| Ziel PostgreSQL | `localhost:5434` | `host.docker.internal:5434` | `destdb` | `destuser` | `destpassword` |
| Ziel MySQL | `localhost:3306` | `host.docker.internal:3306` | `destdb` | `destuser` | `destpassword` |
| Airbyte UI | `http://localhost:8000` | entfällt | entfällt | entfällt | entfällt |
| PostgREST (Szenario 6) | `http://localhost:3000` | entfällt | entfällt | entfällt | entfällt |

> **Warum in Airbyte `host.docker.internal` statt der Container-Namen?**
> Airbyte läuft in einem kind-Cluster und **nicht** im Docker-Netz `airbyte_net`. Seine
> Connector-Pods erreichen die DB-Container deshalb nur über den Host, also über
> `host.docker.internal` und den jeweiligen **Host-Port** (5433, 5434 oder 3306). Ein
> Eintrag wie `hso_source_postgres:5432` funktioniert dort nicht.

---

## 4. Sicherheitshinweis

- Echte Passwörter **nicht** ins Git-Repository committen (`.env` ist in `.gitignore`).
- Remote-Tunnel nur temporär für den jeweiligen Zweck aktivieren und danach beenden.
