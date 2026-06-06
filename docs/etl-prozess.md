# Erster ETL-Prozess (Runbook)

Ziel: der **einfachste vollständige ETL-Lauf** als Meilenstein-Nachweis — eine
Tabelle aus der Source-PostgreSQL über Airbyte in die Ziel-PostgreSQL kopieren
(Full Refresh | Overwrite). Mit 📸-Markierungen für die Screenshots, die in den
Zwischenbericht gehören.

Detaillierte Feld-Tabellen siehe [airbyte-setup.md](airbyte-setup.md); hier der
kompakte, reproduzierbare Ablauf.

---

## Voraussetzungen

**Windows (PowerShell):**
```powershell
.\scripts\install.ps1        # DB-Stack + Testdaten (einmalig)
.\scripts\setup-airbyte.ps1  # Airbyte via abctl (einmalig, interaktiv)
```
**Linux / macOS:**
```bash
bash scripts/install.sh
bash scripts/setup-airbyte.sh
```

Airbyte-UI erreichbar unter **http://localhost:8000** (Login: `abctl local credentials`).

---

## Schritt 1 — Source anlegen (PostgreSQL)

**Sources → + New Source → Postgres**

| Feld | Wert |
|---|---|
| Source name | `HSO Source PostgreSQL` |
| Host | `host.docker.internal` |
| Port | `5433` |
| Database | `sourcedb` |
| Username | `sourceuser` |
| Password | `sourcepassword` |
| SSL mode | `disable` |

→ **Set up source** → Verbindungstest grün. 📸 **Screenshot 1:** erfolgreich angelegte Source.

## Schritt 2 — Destination anlegen (PostgreSQL)

**Destinations → + New Destination → Postgres**

| Feld | Wert |
|---|---|
| Destination name | `HSO Dest PostgreSQL` |
| Host | `host.docker.internal` |
| Port | `5434` |
| Database | `destdb` |
| Username | `destuser` |
| Password | `destpassword` |
| SSL mode | `disable` |

→ **Set up destination** → Verbindungstest grün. 📸 **Screenshot 2:** erfolgreich angelegte Destination.

## Schritt 3 — Connection & Stream-Auswahl

**Connections → + New Connection** → Source `HSO Source PostgreSQL`, Destination `HSO Dest PostgreSQL`.

- Streams auswählen: für den ersten Lauf **`fm_gebaeude`** und **`k_plz`** (klein + groß).
- Sync mode: **Full Refresh | Overwrite**.
- Schedule: **Manual** (für den Test ausreichend).

📸 **Screenshot 3:** Stream-Auswahl mit Sync-Modus.

## Schritt 4 — Sync ausführen

**Save and sync now** (bzw. **Sync now**). Auf den Status **„Succeeded"** warten.

📸 **Screenshot 4:** erfolgreicher Sync mit Zeilenzahlen (Records emitted/committed).

## Schritt 5 — Ergebnis verifizieren (Ziel-DB)

```bash
# funktioniert auf allen Plattformen (Docker)
docker exec -it hso_dest_postgres psql -U destuser -d destdb -c "\dt"
docker exec -it hso_dest_postgres psql -U destuser -d destdb -c "SELECT count(*) FROM fm_gebaeude;"
docker exec -it hso_dest_postgres psql -U destuser -d destdb -c "SELECT count(*) FROM k_plz;"
```

Erwartet: `fm_gebaeude` = 25, `k_plz` = 34.172 (entspricht der Source).
📸 **Screenshot 5:** Zeilenzahlen in der Ziel-DB (Nachweis, dass Daten angekommen sind).

---

## Screenshot-Checkliste für den Bericht

- [ ] Source erfolgreich angelegt
- [ ] Destination erfolgreich angelegt
- [ ] Connection mit Streams + Sync-Modus
- [ ] Erfolgreicher Sync (Status „Succeeded" + Record-Zahlen)
- [ ] Verifikation in der Ziel-DB

---

## Optional: zweites Ziel (MySQL)

Zum Vergleich kann dieselbe Source zusätzlich nach MySQL synchronisiert werden
(`host.docker.internal:3306`, SSL **aus**, JDBC-Param `allowPublicKeyRetrieval=true`,
Raw table database `destdb`) — Details in [airbyte-setup.md](airbyte-setup.md), Kap. 6.

## Optional: File-Connector (Flatfile-ETL)

Studierendendaten (`hso_students`) liegen wegen der defekten CSV nur als Flatfile vor
und werden über den **File-Connector** (`/local/hso_students.csv`, Trennzeichen `|`)
eingebunden — siehe [airbyte-setup.md](airbyte-setup.md), Kap. 7.
