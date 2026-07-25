# Allgemeine Qualitätssicherung von Airbyte

## Connectoren
  - plattformunabhängig, Bereitstellung als isolierte Docker-Container 
  - Unterscheidung zwischen zertifizierten Connectoren und Connectoren aus der Community
  - **zertifiziert**
      - aktiv gewartet und supported von Airbyte
      - **müssen "High-Strictness-Level" aktivieren** --> müssen robusteste und umfangreichste
  Sammlung an Integrationstests fehlerfrei durchlaufen haben
      - **Verpflichtende Sicherheitsvorkehrungen** : Müssen in ihren Metadaten "Allowed Hosts" definieren um den Zugriff auf Netzwerkebene einzuschränken 
      - Standard-Akzeptanztests werden direkt gegen das Docker-Image des jeweiligen Connectors ausgeführt
  - **Community**
      - nicht offiziell unterstützt
      - von der Community gepflegt
      - kann durch ausreichend hohe Nutzung den "zertifiziert" Status erhalten
          - Hierfür müssen die von Airbyte vorgeschriebenen Architektur-, Test-, und Sicherheitsrichtlinien eingehalten sein
          - strenge Richtlinien-Kriterien: Nutzungsmetriken, Testabdeckung, Zuverlässigkeit, Sicherheit und Funktionsumfang und Dokumentation
          - Durchläuft dann die Stufen: **Alpha Connectors**, **Beta Connectors** und schließlich **Generally Available Connectors** nach strengen Kriterien (erst in der letzten Stufe kann volle Robustheit garantiert werden)
          [Kriterien Connectoren](https://airbyte.com/blog/connector-release-stages)
## **Validierungstests von Airbyte**
  - **Connector Acceptance Tests**
      - prüft die Connectoren in der Entwicklungsphase automatisiert durch eine CI-Pipeline
      - Standard-Testsuite basiert auf dem Framework pytest und läuft gegen das Docker-Image des Connectors
          - Prüfung von Test Spec (Test auf korrekte Spezifikation/Test auf Sicherheitslücken insbesondere bei verschlüsselten Daten)
          - Test Connection (Prüft ob Connector mit korrekter Konfiguration Verbindung erfolgreich aufbauen kann)
          - Test Discovery (Prüft Schema korrekt erkannt wurde und als Katalog ausgegeben wird)
          - Test Basic Read & Incremental Sync (Testet ob Datenformate richtig gelesen werden und incremental Sync problemlos funktioniert )
          - Striktheit (Um zertifiziert zu werden muss "high strictness" aktiviert sein, alle Tests müssen erfolgreich durchlaufen )
  - Datenvalidierung/Qualitätssicherung in der Pipeline
      - Airbyte ist primär für den zuverlässigen Transport der Daten vorgesehen
      - Airbyte übernimmt nur strukturelle Integritätsprüfungen
          - Verbindungstest mit den konfigurierten Parametern, wenn es fehlschlägt kann die Connection nicht angelegt werden
          - Schema-Erkennung: "Discovery"-Prozess liest die Struktur der Tabellen, Felder und Datentypen aus und generiert daraus einen Katalog (das Datenschema)
          - Laufende Integritätsprüfung direkt vor und während des Syncs (kontinuierliche Integritätsprüfung der eingehenden Daten basierend auf dem erkannten Schema im Discovery-Prozess)
              - Strikte Schema Validierung (Überprüfung das Quelle mit dem ermittelten Bauplan des Schema übereinstimmt)
              -  **Schema change Management**
                  - Cloud: direkt vor dem Sync, spätestens alle 15 Minuten
                  - Self-managed: direkt vor dem Sync, spätestens alle 24h 
                  - Verhalten mit modifiziertem Schema ist konfigurierbar
                     - Propagate field changes only (Änderungen Automatisch aber nur bei Änderung der Spalte)
                     - Propagate all field and stream changes (Automatisch alle Änderung des Schemas übernehmen und Ziel anpassen)
                     - Approve all changes myself (Manuelle Genehmigung)
                     - Stop future syncs
              - **Record Change History**: Prüft ob einzelne Records ungültig oder zu groß für das Zielsystem sind um den kompletten Sync vor einem Absturz zu schützen
                  - Ändert den entsprechenden Record gegebenenfalls
                  - Ergänzt diese Information in den Airbyte-Metadaten im Zielsystem
              - Isolierung von Typisierungsfehlern einzelner Records (wird genulled anstatt den gesamten Sync abstürzen zu lassen: Ergänz im Zielsystem folgendes: _airbyte_meta.errors)
      - Inhaltliche Validierung durch externe Tools erst im Zielsystem
          - Sql-basierte Tests: z.B. dbt und dbt-expectations
          - Python-basierte Tests: z.B. Great Expectations
          - Automatisierte Überwachung: z.B Monte Carlo oder Soda
 ## **Error Handling**
   - **Retry**
          - Per Default: Bei Server Errors (HTTP 5xx) und zu viele Requests (HTTP 429) wird der Sync bis zu 5-mal wiederholt
          - Retry mit **exponentiellen Backoff** (Automatische Drosselung des Datenabrufs: Verdoppelung der Wartezeit nach jedem Versuch),
      oder **selbst konfiguriert** zum Beispiel: Auslesen aus dem HTTP-Header wie Retry-After oder X-RateLimit-Reset
          - alle anderen Erros führen zu einem *Failed Read* 
          - Verhalten umfangreich konfigurierbar
   - **AirbyteTraceMessages** : Damit Connectoren Metadaten über ihren Laufzeitstatus und ihre Leistung an die Plattform übermitteln können
        - **Strukturierte Fehlermeldungen**
             - **Interne** (für Entwickler: Stacktrace) vs. **externe** Meldung (für Anwender: z.B. ungültiger API-Schlüssel)
             - **Fehler-Kategorisierung**
                  - **system_error**: Problem der Infrastruktur/des Netzwerks --> Retry sinnvoll
                  - **config_error**: Konfigurationsfehler des Nutzers --> tieferliegendes Problem, User muss eingreifen
          - **Aufwands- und Volumenschätzung**: Information für Orchestrator, wie viele Daten in einem Sync voraussichtlich transportiert werden.
              - Schätzwerte für Datenmenge und Anzahl der Records, wird regelmäßig überschrieben
              - sinnvoll für Fortschrittsanzeige für den User
    - **Hearbeat**: Parameter *maxSecondsBetweenMessage* des Quell-Connectors gibt der Plattform an, wie viele Sekunden maximal zwischen zwei gesendeten Nachrichten liegen darf. Wird die Zeit überschritten kommt es zu einem Timeout und der Sync wird kontrolliert abgebrochen, um das dauerhafte Einfrieren zu verhindern. Der gesamte Sync-Job wird neugestartet.
## **State-Management**
  - Connectoren speichern den Zustand (State) zur Fehlerwiederherstellung im korrekten Intervall
  - Mechanismus, der den Fortschritt einer Datenübertragung kontinuierlich speichert
  - **technische Umsetzung**
    - Während eines Syncs **liest** Source-Connector die Daten aus der Source und erzeugt einen Datenstream bestehend aus:
        - **AirbyteRecordMessages**: tatsächliche zu transportierende Datensätze
        - **AirbyteStateMessages**: Checkpoints (= Lesezeichen), die den aktuellen Lesefortschritt der Quelle markieren.
                   Ausgabe (Daten + State)  kontinuierlich über ihre Standardausgabe STDOUT
          - **Transport durch die Airbyte-Plattform**
                - Airbyte-Plattform nimmt Nachrichtenstream entgegeben
                - Inhalt der Stream-Nachrichten ist für Airbyte selbst eine reine Black Box
                - Airbyte reicht sie unverändert an das Ziel weiter: Daten + State wird in den Standardeingang (STDIN) des Ziel-Connectors geladen
          - **Bestätigung durch das Zielsystem**
                - strenger Sicherheitsmechanismus: Zielsystem darf State-Message erst wieder ausgegeben, wenn alle Datensätze die vor dieser Nachricht empfangen wurden erfolgreich und fehlerfrei in das Ziel geschrieben wurden
                - Wenn erfolgreich geschrieben wurde wird das Zielsystem getriggert die selbe **AirbyteStateMessage** über seinen eigenen Standardausgang STDOUT als **Bestätigung** zurückzusenden
          - **Speicherung des finalen Checkpoints für den nächsten Lauf:**
                - Airbyte-Plattform wartet auf die Rückmeldung des Zielsystems
                - State wird nur dann für nächsten Durchlauf gespeichert, wenn er sowohl von der Quelle gesendet als auch vom Ziel bestätigt wurde
                - Wenn Bestätigung empfangen wurde speichert Airbyte diesen Checkpoint in seiner Metdaten-Datenbank ab
                - Bei nächstem Sync-Lauf übergibt Airbyte die zuletzt bestätigte State als Startpunkt an die Quelle
                - wenn der State null ist muss die Source ganz von Beginn starten
      - **Wofür ist es wichtig?**
          -wichtig bei **Inkrementeller Synchronisation**: welche Daten wurden das letzte mal übertragen und an welcher Stelle muss begonnen werden?
          - Rettung bei Abstürzen: zum Beispiel bei Netzwerkfehler oder Serverausfall
              - Nach Neustart kann Sync dann ab dem letztem Checkpoint starten ohne ganz von vorne beginnen zu müssen


# Monitoring

## Logs
- **Sync-Logs:** 
    - Airbyte-UI → Connections → entsprechende Connection anklicken -> Timeline -> auf das Punktemenü rechts neben dem entsprechenden Event klicken -> View Logs (kann auch als .txt Datei gedownloadet werden)
        - Im Header: Attempt wählbar (wenn fehlgeschlagen), Timestamp, Anzahl extracted/geladener records, Job id, Dauer in Sekunden
        - wenn Warning/Fail: Kurzbeschreibung: zum Beispiel: "Failure in source: Checking source connection failed - please review this connection's configuration to prevent future syncs from failing"
        - bietet Suchfunktion, filterbar nach sources (replication-orchestrator, source, destination, platform) und filterbar nach Log levels (info, warn, error, debug, trace)
        - Logfile: enthält weitere nützliche Informationen (zum Beispiel detailliertes Sync summary)
          
          Hier ein beispielhafter Auszug eines erfolgreichen Syncs:

          ```json
          {
            "status" : "completed",
            "recordsSynced" : 1245,
            "bytesSynced" : 363574,
            "startTime" : 1781532526967,
            "endTime" : 1781532557644,
            "totalStats" : {
              "recordsEmitted" : 1245,
              "recordsCommitted" : 1245
              (...)
 
            },
            "streamStats" : [ {
              "streamName" : "fm_stamm"
            } ]
          }
    - Logs über die Airbyte API auszulesen ist aktuell noch nicht möglich
## **Alerting**: integriertes System für Notifications über verschiedene Events
   - Fehlgeschlagener/Erfolreicher Sync, Schema-Änderung, Verbindungsausfälle,..
   - Benachrichtigung über Email oder Webhook (z.B. Slack)
## **Erweiterte System-Metriken** lassen sich in professionelle Monitoring-Stacks integrieren
   - interne Metriken lassen sich über Exporter im Prometheus-Format bereitstellen
   - Mit Grafana lassen sich diese dann in Dashboards visualisieren (zum Beispiel für das Tracken von Latenzen)
   - Self-Managed Enterprise-Kunden können Airbyte so konfigurieren, dass Telemetriedaten direkt über einen OpenTelemetry-Collector an gängige Monitoring-Tools wie Datadog, Prometheus oder Grafana weitergeleitet werden.
