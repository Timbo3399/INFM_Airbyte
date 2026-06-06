Campus Next-Gen Data-Hub Informatik Master Projekt SoSe 2026 Prof. Dr. Max Mustermann I 31.08.2023

---

Das ist ein ganz spannender Vortrag I Prof. Dr. Max Mustermann 3 Ist - Stand Datensynchronisation Campus IT Talend Server ● Java Programme per Cronjob ● diverse Powershell Scripte für einzelne ETL Prozesse HIS SVA HIS FSV HisInOne COB & COA BAU IVS MBS FileServer Intrexx Infoview Smartlife Chipkarte eDirectory (LDAP) FileServer …

---

Das ist ein ganz spannender Vortrag I Prof. Dr. Max Mustermann 4 Ziel Architektur HIS SVA HIS FSV HisInOne COB & COA BAU IVS MBS Intrexx Infoview Smartlife Chipkarte FileServer Zentraler Data-Hub

---

Studentenprojekt Informatik Master SoSe 2026 I Prof. Dr. Jan Münchenberg 5 Welche Tools kommen in Frage ? • Apache Hophttps://hop.apache.org/ • Pentaho https://community.hitachivantara.com/s/article/downlo ads • Apache Nifi https://nifi.apache.org/ • Airbyte https://airbyte.com/

---

Studentenprojekt Informatik Master SoSe 2026 I Prof. Dr. Jan Münchenberg 6 Was muss das System können? • Abfragen von SOAP und Rest API Schnittstellen • Logging und Monitoring von Jobs/Task/… • Datei basierte Daten (csv, Excel, json, xml) einlesen • diverse DB Anbindungen bereitstellen (min. Informix, MySQL, PostgreSQL) • Daten Mapping und Transformation über eigene Code / Routinen / o.ä. • Low-Code Rest API für Datenzugriffe ermöglichen • Steuerung/Ausführung von eigenen Code-Snippets für komplexe Szenarien (like Selenium ??)

---

Studentenprojekt Informatik Master SoSe 2026 I Prof. Dr. Jan Münchenberg 7 Anforderungen • eingesetzes Tool sollte open source sein und eine aktive Community (support + weiterentwicklung) • Tests und evaluierung der Möglichkeiten der entsprechenden Szenarien • Usability einfache Konfiguration • Gut in Hochschul IT Systemlandschaft integrierbar

---

Studentenprojekt Informatik Master SoSe 2026 I Prof. Dr. Jan Münchenberg 8 zu Testen -> siehe Szenarien (später) • SOAP Requests bündeln in DB (h1) • PostgresSQL in mySQL dumpen • Spezifische Tabellen in eine andere DB • Excel Dateien in eine mySQL DB • komplexe ETL-Transformationen / Mapping • xml und json mapping/transformation • Anbindung als REST API • Ausführen von eigenen Code Snippets (python, javascript und/oder Groovy

---

9 Aufgaben • Evaluierung der möglichen Umsetzung von Testszenarien • Aufbau einer Systemumgebung für Evaluation/Tests (Dockercontainer ?) • Dokumentation der Tools und der Architektur des Projektes

---

• mySQL • informix • SOAP • csv (teilweise Versand per Mail) • MS Excel (muss teilweise von anderen orten abgeholt werden) • textfile (für Logs & Versand per Mail) Das ist ein ganz spannender Vortrag I Prof. Dr. Max Mustermann 10 • filtern • ändern (trim, replace, regex, if/else,...) • mappen • zuordnen (FK) • vereinigen Datenhandling Verschiedene Datenquellen/Ziele Anforderungen an das System • Fehler bei Datentransfers • Bestätigung von Aktionen Logging Exportierbarkeit Wartbarkeit Skalierbarkeit

---

• Talend generiert einzelne Jobs • custom Skripte für Job Ausführung und Logging • Aufgabenplanung stößt Skripte an → d.h. Wenn die Jobs exportierbar sind, könnten sie auch via der bisherigen Strukturen ausgeführt werden, sofern die Anwendung kein self scheduling zulässt. Das ist ein ganz spannender Vortrag I Prof. Dr. Max Mustermann 11 Logging und Scheduling Wie es momentan Läuft • einfaches editieren von Jobs, mappings und Tabellenschemas • pausieren von Jobs bei Wartungsarbeiten an Datenquellservern Wartung • Jobs können ohne weitere Probleme auf anderen Maschinen ausgeführt werden (bsp: Verwaltung kann ein Skript zum Anlegen von Studenten nutzen) Exportierung

---



