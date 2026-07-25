-- Szenario 5 (IdM): gemeinsame Sicht auf Studierende und Personal.
--
-- Warum eine View und nicht zwei Airbyte-Streams?
-- Airbyte synchronisiert Streams 1:1. Zwei Quelltabellen werden zu zwei
-- Zieltabellen, ein UNION ist im Tool nicht vorgesehen. Die Zusammenfuehrung
-- muss also entweder vor Airbyte (diese View) oder nach Airbyte (dbt) passieren.
-- Wir nehmen die View: sie ist in der Quelle billig, Airbyte liest sie wie eine
-- Tabelle, und das Ergebnis ist genau die eine hso_user-Tabelle, die die
-- Aufgabenstellung verlangt.
--
-- Wichtig fuer den Sync:
--   user_id   = Primaerschluessel (ueber beide Gruppen hinweg eindeutig)
--   updatedat = Cursor fuer Incremental
--
-- Liegt NICHT in sql/source/ selbst, weil der Postgres-Init dort jede .sql
-- ausfuehren wuerde. Zum Zeitpunkt des Inits gibt es hso_personal noch nicht
-- (die Tabelle legt load_json.py an), die View liesse sich also gar nicht
-- erzeugen. Angewendet wird sie von scripts/mapping/create_hso_user_view.py.

-- Bildzuordnung (Szenario 5, zweiter Teil): die Testbilder aus Szenario 3
-- stehen in keinem echten Zusammenhang zu Personen, eine inhaltliche
-- Verknuepfung gibt es also nicht. Wir ordnen deterministisch zu, ueber einen
-- Hash der user_id modulo der Bildanzahl. Dieselbe Person bekommt damit bei
-- jedem Lauf dasselbe Bild, und die Verknuepfung laesst sich pruefen.

CREATE OR REPLACE VIEW hso_user AS
WITH bildanzahl AS (
    SELECT GREATEST(count(*), 1) AS n FROM hso_images
),
personen AS (
    SELECT
        s.user_id                    AS user_id,
        s.surname                    AS nachname,
        s.firstname                  AS vorname,
        s.hochschulemail             AS email,
        'student'::varchar(20)       AS rolle,
        s.studentstatus::varchar(50) AS status,
        s.updatedat                  AS updatedat
    FROM hso_students s
    WHERE COALESCE(s.user_id, '') <> ''

    UNION ALL

    SELECT
        p.user_id,
        p.nachname,
        p.vorname,
        p.hso_email,
        'personal'::varchar(20),
        p.h1_status::varchar(50),
        p.updatedat
    FROM hso_personal p
    WHERE COALESCE(p.user_id, '') <> ''
)
SELECT
    pe.user_id,
    pe.nachname,
    pe.vorname,
    pe.email,
    pe.rolle,
    pe.status,
    bi.image_id,
    pe.updatedat
FROM personen pe
CROSS JOIN bildanzahl ba
LEFT JOIN hso_images bi
       ON bi.ext_id = ((abs(hashtext(pe.user_id)) % ba.n) + 1)::varchar;
