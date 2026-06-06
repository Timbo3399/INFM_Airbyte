Campus Next-Gen Data-Hub Informatik Master Projekt SoSe 2026

---

Studentenprojekt Informatik Master SoSe 2026 I Prof. Dr. Jan Münchenberg 3 ETL Prozesse / Mapping 1 Große Datenmengen zwischen Datenbanksystemen spiegeln 2 SOAP Request einlesen und in eine Datenbank eintragen 3 DLL Scripte automatisieren / Tabellen erstellen 4 Einspielen von Bildern in eine Datenbank 5 Bilder als byteArray in ein Verzeichnis ablegen 6 Excel Dateien von einen Zielsystem holen (sftp) und in eine DB einspielen 7 REST Schnittstelle bereitstellen -> Api Funktion für Tabelle x (inserts, update, delete, get, getall) 8 Synchronisation zwischen tabellen/systemen

---

Studentenprojekt Informatik Master SoSe 2026 I Prof. Dr. Jan Münchenberg 4 Szenarieren 1) Einspielen der Testdaten 2) Facility Management 3) Testdaten für Bilder generieren 4) Mapping von Studenten / Personal 5) IdM System 6) Web APIs

---

Studentenprojekt Informatik Master SoSe 2026 I Prof. Dr. Jan Münchenberg 5 1) Einspielen der Testdaten Testen Sie allgemein wie Sie Daten mit ihrem Tool in die Datenbanksysteme MySQL und PostgreSQL bekommen. Dazu stehen ihnen die Testdatenquellen im Verzeichnis Testdaten zur Verfügung. Spielen Sie etwas rum versuchen Sie sich mit ihrem Tool und die Möglichkeiten vertraut zu machen

---

Studentenprojekt Informatik Master SoSe 2026 I Prof. Dr. Jan Münchenberg 6 2) Facility Management 1, Bauen Sie als erstes eine PostgreSQL Datenbank mit den Tabellen inst,geb,stamm auf 2. Füllen Sie diese Tabellen mit Testdaten 3. Bauen Sie eine MySQL Datenbank fürs FM auf indem Sie dort nur 1 Tabelle erstellen und diese mit den entsprechenden Daten für Räume füllen (bsp. Raumnr + Gebäude als Text + Kostenstelle zusätzlich mit Namen aus inst, usw…)

---

Studentenprojekt Informatik Master SoSe 2026 I Prof. Dr. Jan Münchenberg 7 3) Testdaten für Bilder generieren 1. Lassen Sie sich über eine offene API (bspw. https://picsum.photos/) Bilder massenweise (>1000) erzeugen und speichern Sie diese als Blob/ByteArray mit ID in eine Datenbank 2. Laden Sie diese Anschließend über einen neuen Prozess aus der Datenbank und Speichern Sie diese dann als Datei in ein Verzeichnis (am besten mit <ID>.png als name)

---

Studentenprojekt Informatik Master SoSe 2026 I Prof. Dr. Jan Münchenberg 8 4) Mapping von Studenten / Personal 1, anonymsierte Daten mit Random Namen + Adressen füllen (bspw. mit https://generatedata.com/) 2. Accountgenerator (siehe *.js Datei) im Tool definieren und userID setzen 3 Daten in neue PostgreSQL Tabelle für Studenten und für personal schreiben

---

Studentenprojekt Informatik Master SoSe 2026 I Prof. Dr. Jan Münchenberg 9 5) IdM System 1, Tabellen hso_personal und hso_students in neue mysql hso_user Tabelle syncrhonisieren (bei Änderung der Quelltabellen auch die hso_user Tabelle synchronisieren) 2. Zusätzlich die user_ids mit Bildern aus Szenario 3) verknüpfen

---

Studentenprojekt Informatik Master SoSe 2026 I Prof. Dr. Jan Münchenberg 10 6) Web APIs 1. eine Rest Schnittstelle zum einfügen und ändern von hso_students und hso_personal hinzufügen 2. Soap Webservice von https://hisinone.hs-offenburg.de/qisserver/services2 / abfragen und in DB speichern (später) a. Zugriff über Security Header (Zugang wird später testweise hergestellt)

---



