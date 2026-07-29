### Ausgangssituation: Ist-Stand der Datensynchronisation mit Talend

Die Campus-IT der Hochschule Offenburg betreibt einen zentralen Talend-Server, der als Dreh- und Angelpunkt für den Datenaustausch zwischen den verschiedenen Hochschulsystemen dient. Technisch besteht er aus zwei Teilen: Java-Programmen, die per Cronjob zeitgesteuert laufen, und einer Reihe von PowerShell-Skripten, die jeweils für einzelne ETL-Prozesse (Extract-Transform-Load) geschrieben wurden.

Auf der Quellseite hängen am Talend-Server unter anderem HIS SVA, HIS FSV (mit den Teilmodulen IVS, BAU, MBS, COB und COA), ein FileServer, HisInOne sowie das eDirectory per LDAP. Versorgt werden darüber Zielsysteme wie Intrexx, Infoview, die Smartlife-Chipkarte, wieder der FileServer und eine offene Zahl weiterer angebundener Systeme.

Im Ist-Zustand läuft der Datenfluss weitgehend unidirektional und punktuell verdrahtet: Jede Quelle wird über ein eigenes Skript oder Java-Programm abgeholt, zentral verarbeitet und dann in Zieldatenbanken oder direkt in Zielsysteme geschrieben. Eine einheitliche, zentrale Verwaltung der Verbindungen gibt es nicht — jede Strecke von Quelle über Talend zum Ziel ist im Grunde eine eigene Insellösung, gewachsen über die Jahre.

Angestrebt wird stattdessen ein zentraler Data-Hub, der alle Systeme (HIS SVA, HIS FSV, HisInOne, Intrexx, Infoview, Smartlife Chipkarte, FileServer usw.) bidirektional anbindet. Statt vieler einzelner, starrer Skript-Strecken soll ein zentrales System entstehen, über das Daten in beide Richtungen fließen, einheitlich gemappt, überwacht und gewartet.

Das bisherige System funktioniert zwar, hat aber deutliche Schwächen: Es ist schwer wartbar, weil die Skript-Logik verteilt ist und ein einheitliches Monitoring fehlt. Es ist schlecht dokumentiert und hängt stark an einzelnen Personen. Neue Quellen oder Ziele lassen sich nicht ohne Weiteres anbinden, und ein modernes Job-Logging- oder Monitoring-Konzept fehlt komplett.

Genau deshalb wird jetzt geprüft, ob ein modernes ETL/ELT-Tool diese Rolle übernehmen kann — Kandidaten sind Apache Hop, Pentaho, Apache NiFi und Airbyte, wobei diese Evaluierung sich auf Airbyte konzentriert.

---

### Anforderungen an das neue System (Airbyte)

Aus der Analyse des Ist-Stands lassen sich folgende Anforderungen an ein Nachfolgesystem ableiten.

Bei den Schnittstellen und Datenquellen muss das System SOAP- und REST-APIs abfragen sowie dateibasierte Formate wie CSV, Excel, JSON und XML einlesen können. Es muss diverse Datenbanken anbinden, mindestens Informix, MySQL und PostgreSQL, und eine Low-Code-REST-API für Datenzugriffe bieten (Insert, Update, Delete, Get, GetAll). Für komplexere Szenarien braucht es die Möglichkeit, eigene Code-Snippets auszuführen — Python, JavaScript und/oder Groovy, gegebenenfalls auch Selenium-artige Automatisierung.

Beim Datenhandling geht es um Filtern, Ändern (Trim, Replace, Regex, if/else …), Mappen, das Zuordnen über Foreign Keys und das Vereinigen von Datensätzen. Beim Logging und Monitoring braucht es eine Protokollierung von Jobs und Tasks, Fehler bei Datentransfers müssen erfasst werden, und erfolgreiche Aktionen sollten sich bestätigen lassen.

Dazu kommen einige nicht-funktionale Anforderungen, von denen eine besonders zentral ist: Open Source mit einer aktiven Community, die Support und Weiterentwicklung trägt. Daneben spielen Exportierbarkeit eine Rolle (Jobs müssen auf anderen Maschinen lauffähig sein), Wartbarkeit (einfaches Editieren von Jobs, Mappings und Tabellenschemas, Pausieren bei Wartungsarbeiten), Skalierbarkeit, eine einfache Konfiguration und eine gute Integrierbarkeit in die bestehende Hochschul-IT-Landschaft.

Gerade die Anforderung "Open Source mit aktiver Community" ist der Punkt, an dem die Geschäftsmodell-Frage direkt andockt: Ein Tool kann funktional exzellent sein — wenn das dahinterstehende Geschäftsmodell instabil ist oder sich die Lizenzbedingungen ändern können, ist die langfristige Investitionssicherheit gefährdet. Genau das ist bei Talend bereits passiert.

---

### Ist Airbyte mit seinem Geschäftsmodell geeignet? Droht das gleiche Szenario wie bei Talend?

Diese Frage ist berechtigt, und sie lässt sich anhand der jüngeren Geschichte von Talend sehr konkret beantworten.

**Was bei Talend passiert ist:** Talend Open Studio war rund 17 Jahre lang eine kostenlose Open-Source-Variante, mit der die Hochschule ihre aktuelle Lösung aufgebaut hat. Im Mai 2023 wurde Talend vom Konzern Qlik übernommen. Schon im November 2023 kündigte Qlik an, Talend Open Studio zum 31. Januar 2024 vollständig einzustellen. Seitdem gibt es keinen kostenlosen Einstiegspunkt mehr — bestehende Nutzer mussten auf kostenpflichtige Qlik-Talend-Cloud-Abonnements umsteigen oder das Tool wechseln. Wer die alte Version weiterbetreibt, bekommt keine Sicherheitsupdates mehr, und auch die rechtliche Lage der Weiternutzung ist unklar geblieben, weil Downloadlinks und Hosting eingestellt wurden. Dazu kommt, dass Talends Preismodell — kapazitätsbasiert, über Datenvolumen, Job-Ausführungen und Laufzeit — als intransparent und schwer planbar gilt.

Das ist genau das Risiko. Ein Anbieter wird übernommen oder ändert strategisch die Richtung, stellt die kostenlose Version ein, und Bestandskunden stehen vor einem Zwangsupgrade.

**Wie Airbytes Geschäftsmodell aufgebaut ist:** Airbyte trennt strikt zwischen zwei Produktlinien. Airbyte Core läuft selbst gehostet auf eigener Infrastruktur; der Code der Konnektoren steht unter MIT-Lizenz, die Plattform selbst unter der Elastic License v2 (ELv2). Diese Variante bleibt kostenlos, mit unbegrenztem Datenvolumen und Zugriff auf über 600 Konnektoren. Daneben gibt es Airbyte Cloud als gehostetes, kostenpflichtiges Angebot, über das das Unternehmen tatsächlich Geld verdient.

Warum das strukturell sicherer ist als bei Talend, aber trotzdem nicht risikofrei:

Für Airbyte spricht, dass die kostenlose Basis von Anfang an so konzipiert war, dass sie dauerhaft bestehen bleibt — das Unternehmen verdient sein Geld explizit über das separate Cloud-Produkt, nicht über den Verkauf der Kernsoftware. Airbyte selbst beschreibt die Strategie so: Alles, was einzelnen Entwicklern oder kleinen Teams dient, soll frei bleiben, während organisationsweite Bedürfnisse monetarisiert werden. Selbst wenn Airbyte Inc. das Geschäftsmodell künftig ändert oder übernommen wird, bleibt bereits veröffentlichter Code unter MIT/ELv2 rechtlich nutzbar, veränderbar und weiter betreibbar — er kann nicht nachträglich zurückgezogen werden wie ein Hosting-Angebot. Das ist der strukturelle Unterschied zu Talend Open Studio, das kein echtes dauerhaftes Nutzungsrecht bot, sondern schlicht ein Angebot war, das der Hersteller einstellen konnte. Und sollte sich Airbyte Inc. dennoch ungünstig entwickeln, gäbe es, wie bei anderen verlassenen Open-Source-Projekten üblich, die Möglichkeit eines Community-Forks, wie es bei Talend mit "Talaxie" als Reaktion auf die Einstellung bereits passiert ist.

Ein Restrisiko bleibt trotzdem: Airbyte ist ebenfalls ein VC-finanziertes Unternehmen mit Monetarisierungsdruck, ähnlich wie Talend es war. Schon jetzt lässt sich beobachten, dass neue, komplexere oder "Enterprise"-Konnektoren zunehmend hinter kostenpflichtigen Stufen (Plus/Pro/Enterprise) landen, die Kernplattform und die meisten Standard-Konnektoren bleiben zwar frei, aber der Trend geht dahin, neue Premium-Funktionen nur noch zahlenden Kunden anzubieten. Und auch der Betrieb der selbst gehosteten Variante ist nicht umsonst: Infrastruktur, Kubernetes- oder Docker-Betrieb und DevOps-Aufwand kosten etwas — kostenlos heißt nicht aufwandsfrei.

**Fazit:** Airbyte ist im Vergleich zu Talend die strukturell sicherere Wahl, weil das Geschäftsmodell von Anfang an auf einer klaren Trennung zwischen dauerhaft freier Kernsoftware (MIT/ELv2) und einem separat finanzierten Cloud-Geschäft beruht, und weil einmal veröffentlichter Open-Source-Code nicht nachträglich entzogen werden kann, anders als ein eingestelltes Hosting- oder Studio-Angebot wie bei Talend Open Studio. Einen hundertprozentigen Schutz vor kommerziellem Druck gibt es trotzdem nicht: Wie bei jedem VC-finanzierten Open-Source-Unternehmen sollte man davon ausgehen, dass neue, fortgeschrittene Features eher in Richtung kostenpflichtiger Stufen wandern, während die Kernfunktionalität frei bleibt. Empfehlenswert ist deshalb, bei der Einführung auf Versionspinning zu achten, keine funktionale Abhängigkeit von reinen Cloud-Exklusivfeatures aufzubauen und die Lizenzlage der einzelnen benötigten Konnektoren im Blick zu behalten.

