# Zugang zum System

Dieses Dokument beschreibt, wie auf die Airbyte-Oberfläche und die Datenbanken
zugegriffen wird — inkl. des Zugangs für die Betreuer (Herr Stippekohl + Dozent).

---

## 1. Airbyte-UI

| | |
|---|---|
| URL | **http://localhost:8000** |
| Login anzeigen | `abctl local credentials` |

`abctl local credentials` gibt E-Mail, ein generiertes Passwort sowie Client-ID/Secret aus.

### Eigenes / gemeinsames Passwort setzen

```powershell
abctl local credentials --email <login-email> --password <gewuenschtes-passwort>
```

> **Die E-Mail ist der Login-Name in der UI.** `--email` immer mitangeben: Ist in der
> Installation noch keine E-Mail gesetzt (`abctl local credentials` zeigt dann
> `Email: [not set]`), schlägt der reine `--password`-Aufruf mit
> `unable to determine organization email` fehl. Die E-Mail ist frei wählbar
> (z. B. `admin@example.com`).

> Für den Betreuer-Termin empfiehlt sich ein **bewusst gesetztes, gemeinsames Passwort**
> (statt des generierten), damit alle denselben Login verwenden können.

**Aktueller Zugang (von der Gruppe auszufüllen / NICHT öffentlich committen):**

| Feld | Wert |
|---|---|
| URL | http://localhost:8000 |
| E-Mail | ‹…› |
| Passwort | ‹… — separat/sicher teilen, nicht ins Repo› |

---

## 2. Zugang für die Betreuer (Herr Stippekohl + Dozent)

**Wichtige Rahmenbedingung:** Airbyte **Community Edition** (über `abctl`) ist im
Kern **Einzelnutzer-orientiert** und läuft auf `localhost` des Entwicklungsrechners.
Mehrbenutzer-/RBAC-Funktionen sind der Enterprise-/Cloud-Variante vorbehalten. Es
gibt daher keine getrennten Benutzerkonten pro Betreuer, sondern **einen Admin-Login**.

### Empfohlene Optionen

1. **Vor-Ort-Termin (ab 8.6., empfohlen):** Wir zeigen das System live auf unserem
   Rechner; die Betreuer nutzen bei Bedarf den gemeinsamen Admin-Login (Kap. 1).
   → Kein zusätzlicher Aufwand, keine Sicherheitsrisiken.
2. **Temporärer Remote-Zugang (falls vorab gewünscht):** Die lokale UI kann über
   einen Tunnel kurzzeitig erreichbar gemacht werden, z. B.:
   ```powershell
   # Beispiel mit cloudflared (temporäre öffentliche URL auf localhost:8000)
   cloudflared tunnel --url http://localhost:8000
   ```
   Den so erzeugten Link + die Login-Daten würden wir den Betreuern direkt zukommen
   lassen. *(Nur temporär aktivieren; danach beenden.)*

> **Offene Frage an die Betreuer** (siehe Zwischenbericht, Kap. 6): Welche Variante
> ist gewünscht — gemeinsamer Login im Termin oder vorheriger Remote-Zugang?

---

## 3. Verbindungsparameter (zentrale Referenz)

> **Diese Tabelle ist die einzige Quelle für Ports und Zugangsdaten im Projekt.**
> Andere Dokumente (README, installation-guide, architektur, airbyte-setup) verlinken hierher,
> statt die Werte zu duplizieren.

Standardwerte aus `.env.example` — bei Änderung in `.env` gelten die dortigen Werte.

| Dienst | DB-Tools (lokal) | In der Airbyte-UI eintragen | DB | User | Passwort |
|---|---|---|---|---|---|
| Source PostgreSQL | `localhost:5433` | `host.docker.internal:5433` | `sourcedb` | `sourceuser` | `sourcepassword` |
| Ziel PostgreSQL | `localhost:5434` | `host.docker.internal:5434` | `destdb` | `destuser` | `destpassword` |
| Ziel MySQL | `localhost:3306` | `host.docker.internal:3306` | `destdb` | `destuser` | `destpassword` |
| Airbyte UI | `http://localhost:8000` | — | — | — | — |
| PostgREST (Szenario 6) | `http://localhost:3000` | — | — | — | — |

> **Warum in Airbyte `host.docker.internal` statt der Container-Namen?**
> Airbyte läuft in einem kind-Cluster und **nicht** im Docker-Netz `airbyte_net`. Seine
> Connector-Pods erreichen die DB-Container daher nur über den Host — also
> `host.docker.internal` + den jeweiligen **Host-Port** (5433/5434/3306), nicht über
> `hso_source_postgres:5432` o. ä.

---

## 4. Sicherheitshinweis

- Echte Passwörter **nicht** ins Git-Repository committen (`.env` ist in `.gitignore`).
- Remote-Tunnel nur temporär für den jeweiligen Zweck aktivieren und danach beenden.
