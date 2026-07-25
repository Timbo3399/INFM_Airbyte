# dbt als Transformationsschicht

Airbyte transportiert Daten, es transformiert sie nicht. Für Szenario 2 brauchen wir
aber einen Join über drei Tabellen. Diese Lücke schließt dbt, und zwar als eigener
Schritt nach dem Sync.

---

## 1. Airbyte führt dbt nicht mehr aus

Ältere Airbyte-Versionen konnten pro Connection eine dbt-Transformation anstoßen
("Custom Transformation"). In unserer Instanz gibt es das nicht mehr.

Nachgesehen in Airbyte **2.1.1** (Community Edition): ein Connection-Objekt der
Public API hat die Felder

```
configurations, connectionId, createdAt, destinationId, name,
namespaceDefinition, nonBreakingSchemaUpdatesBehavior, prefix, schedule,
sourceId, status, tags, workspaceId
```

Kein `transformations`, kein `operations`, kein `normalization`. Der interne Endpunkt
`/api/v1/operations/list` antwortet mit 403.

Das ist für die Bewertung wichtiger, als es zunächst klingt. Die Empfehlung "Airbyte
für die Extraktion, dbt für die Transformation" bedeutet damit nicht ein Werkzeug mit
zwei Modi, sondern **zwei getrennte Werkzeuge mit zwei getrennten Zeitplänen**. Wer
"erst syncen, dann transformieren" braucht, muss die Reihenfolge selbst herstellen,
über ein Skript oder einen Orchestrator. Verkettung von Läufen kann Airbyte ohnehin
nicht (siehe [bewertung-airbyte.md](bewertung-airbyte.md)).

---

## 2. Aufbau

```
dbt/
├── dbt_project.yml        Projektdefinition
├── profiles.yml           Verbindung zu dest-postgres, Werte aus der Umgebung
└── models/
    ├── sources.yml        die drei von Airbyte gelieferten Rohtabellen
    ├── fm_raeume.sql      das Modell
    └── schema.yml         Tests auf dem Modell
```

Der Datenfluss für Szenario 2:

```
source-postgres          dest-postgres                    dest-mysql
  fm_stamm     ─┐         fm_stamm    ─┐
  fm_gebaeude  ─┼─ Airbyte ─► fm_gebaeude ─┼─ dbt ─► fm_raeume ─ Airbyte ─► fm_raeume
  fm_inst      ─┘         fm_inst     ─┘
```

Airbyte taucht zweimal auf: einmal um die Rohtabellen ins Ziel zu bringen, einmal um
das fertige Modell weiterzureichen. Dazwischen liegt dbt.

---

## 3. Ausführen

```powershell
pip install -r requirements.txt
python -m dbt.cli.main run  --project-dir dbt --profiles-dir dbt
python -m dbt.cli.main test --project-dir dbt --profiles-dir dbt
```

`python -m dbt.cli.main` statt `dbt`, weil das Skript `dbt.exe` unter Windows in
einem Verzeichnis landet, das oft nicht im PATH steht.

Voraussetzung ist ein Lauf der Connection `HSO FM nach PG`, sonst fehlen die
Quelltabellen:

```powershell
python scripts/airbyte/run_sync.py "HSO FM nach PG"
```

---

## 4. Das Modell fm_raeume

1.244 Zeilen, gebaut aus `fm_stamm`, `fm_gebaeude` und `fm_inst`. Zwei Dinge daran
sind der eigentliche Grund, warum es dbt braucht und Kopieren nicht reicht.

**Die Gebäudenummern passen nicht zusammen.** In `fm_stamm` steht `101`, in
`fm_gebaeude` `0101`. Die Raumdaten stammen aus einer Excel-Datei, die die führende
Null als Zahl verschluckt hat, die Gebäudedaten aus einer CSV, die sie als Text
behalten hat. Der naive Join trifft **0 von 1.244** Zeilen. Mit `lpad(geb_nr, 4, '0')`
trifft er **alle 1.244**.

Ein Join, der stillschweigend nichts findet, ist die unangenehme Sorte Fehler: das
Modell läuft durch, die Tabelle entsteht, und die Gebäudespalte ist eben leer. Deshalb
steht im Modell ein `not_null`-Test auf `gebaeude`. Er schlägt fehl, sobald die
Normalisierung wegfällt.

**Das Institut hängt an der Kostenstelle.** `fm_stamm.kost_nr` auf `fm_inst.inst_nr`
trifft 1.184 von 1.244 Zeilen. Der naheliegendere Weg über `nutzer_nr` trifft keine
einzige. Beide Joins sind bewusst LEFT JOINs: ein Raum ohne Institut soll in der
Tabelle bleiben.

Ergebnis: 1.244 Räume, alle mit Gebäudenamen, 1.184 mit Institut, zusammen
52.009 m².

---

## 5. Tests

`dbt test` prüft vier Bedingungen, alle grün:

| Test | Spalte | Warum |
|---|---|---|
| `unique` | `raum_id` | zusammengesetzt aus geb_nr, ges_nr und raumid |
| `not_null` | `raum_id` | Schlüssel der Zieltabelle |
| `not_null` | `gebaeude_nr` | normalisierte Gebäudenummer |
| `not_null` | `gebaeude` | schlägt an, wenn die Normalisierung wegfällt |

Das ist ein Punkt für dbt gegenüber einer reinen SQL-View: die Tests laufen mit dem
Modell zusammen und im selben Werkzeug. Airbyte selbst prüft nichts dergleichen, wie
die Befunde zu Primärschlüsseln und BLOBs in [testszenarien.md](testszenarien.md)
zeigen.

---

## 6. Aufwand

Für die Aufwandsschätzung im Projekt, ehrlich gemessen an diesem einen Modell:

| Posten | Aufwand |
|---|---|
| Installation (`pip install dbt-core dbt-postgres`) | wenige Minuten, keine Konflikte mit dem bestehenden Stack |
| Projekt aufsetzen (`dbt_project.yml`, `profiles.yml`, `sources.yml`) | einmalig, überschaubar |
| Das Modell schreiben | der Join selbst ist einfaches SQL |
| **Die Datenprobleme finden** | **der eigentliche Aufwand** |

Die letzte Zeile ist die Botschaft. Das SQL für `fm_raeume` ist ein Nachmittag für
niemanden. Zu erkennen, dass die Gebäudenummern in zwei Formaten vorliegen und dass
das Institut an der Kostenstelle hängt und nicht am Nutzer, war die Arbeit. Genau
dieser Anteil steckt auch in den bestehenden Talend-Jobs und lässt sich nicht
automatisch übersetzen. Eine Migration ist deshalb keine Übersetzung von Job zu
Modell, sondern eine erneute Auseinandersetzung mit den Daten.

Modelllaufzeit: 0,10 s für 1.244 Zeilen, Tests 0,23 s. Die Ausführung ist der
billigste Teil.
