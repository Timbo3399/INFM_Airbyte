-- Szenario 4, Schritt 3: die generierten Accounts als eigene Sichten je Gruppe.
--
-- Die Aufgabenstellung verlangt, die Ergebnisse des Account-Generators in neue
-- Tabellen zu schreiben, getrennt fuer Studierende und Personal. Airbyte kopiert
-- Streams 1:1, also liefert je eine View je Zieltabelle.
--
-- Warum die Views nicht hso_students und hso_personal heissen:
-- der File-Connector schreibt hso_students bereits nach dest-postgres. Zwei
-- Connections, die denselben Stream in dieselbe Zieltabelle schreiben,
-- verdoppeln sie beim ersten Aufbau, weil Full Refresh Overwrite nur echt
-- aeltere Generationen loescht und der Zaehler pro Connection laeuft (Befund 27
-- in docs/ergebnisse.md). Eigene Stream-Namen umgehen das.
--
-- Beide Views filtern auf gesetzte user_id. Ohne generate_accounts.py sind sie
-- also leer, und die Skip-Erkennung in setup_szenarien.py sieht das.
--
-- Angewendet von scripts/mapping/create_account_views.py.

-- Studierende: 5.052 Zeilen, Schluessel ist die Matrikelnummer.
CREATE OR REPLACE VIEW hso_student_accounts AS
SELECT
    s.user_id                        AS user_id,
    s.mtknr                          AS mtknr,
    s.firstname                      AS vorname,
    s.surname                        AS nachname,
    s.hochschulemail                 AS email,
    s.fakultaet                      AS fakultaet,
    s.stg                            AS studiengang,
    s.studentstatus::varchar(50)     AS status,
    s.updatedat                      AS updatedat
FROM hso_students s
WHERE COALESCE(s.user_id, '') <> '';

-- Personal: 870 Zeilen, Schluessel ist die Personal-Id.
CREATE OR REPLACE VIEW hso_personal_accounts AS
SELECT
    p.user_id                        AS user_id,
    p.id                             AS personal_id,
    p.vorname                        AS vorname,
    p.nachname                       AS nachname,
    p.hso_email                      AS email,
    p.dienstart                      AS dienstart,
    p.sva_rolle                      AS rolle,
    p.h1_status::varchar(50)         AS status,
    p.updatedat                      AS updatedat
FROM hso_personal p
WHERE COALESCE(p.user_id, '') <> '';
