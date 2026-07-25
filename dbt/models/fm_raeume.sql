{{ config(materialized='table') }}

-- Szenario 2, Teilaufgabe B: eine denormalisierte Raumtabelle aus den drei
-- FM-Rohtabellen. Genau der Join, den Airbyte selbst nicht ausfuehren kann.
--
-- Zwei Dinge, die diese Transformation noetig machen und die zeigen, warum
-- reines Kopieren nicht reicht:
--
-- 1. Die Gebaeudenummern passen nicht zusammen. In fm_stamm steht "101",
--    in fm_gebaeude "0101". Die Raumdaten kommen aus einer Excel-Datei, die
--    die fuehrende Null als Zahl verschluckt hat, die Gebaeudedaten aus einer
--    CSV, die sie als Text behalten hat. Ohne lpad trifft der Join null von
--    1.244 Zeilen, mit lpad alle 1.244.
--
-- 2. Das Institut haengt an der Kostenstelle (fm_stamm.kost_nr auf
--    fm_inst.inst_nr), nicht an nutzer_nr. Ueber nutzer_nr gibt es keinen
--    einzigen Treffer, ueber kost_nr 1.184 von 1.244.
--
-- Beide Joins sind LEFT JOIN: ein Raum ohne zugeordnetes Institut soll in der
-- Tabelle stehen bleiben, nicht verschwinden.

with stamm as (
    select
        geb_nr,
        ges_nr,
        raumid,
        raumnr,
        kost_nr,
        flaeche,
        lpad(geb_nr, 4, '0') as geb_nr_normalisiert
    from {{ source('airbyte', 'fm_stamm') }}
),

gebaeude as (
    select geb_nr, geb from {{ source('airbyte', 'fm_gebaeude') }}
),

institute as (
    select inst_nr, dname from {{ source('airbyte', 'fm_inst') }}
)

select
    s.geb_nr || '-' || s.ges_nr || '-' || s.raumid as raum_id,
    s.raumnr                                       as raumnr,
    g.geb                                          as gebaeude,
    s.geb_nr_normalisiert                          as gebaeude_nr,
    i.dname                                        as institut,
    cast(s.flaeche as numeric(14, 2))              as flaeche,
    s.kost_nr                                      as kostenstelle
from stamm s
left join gebaeude g on g.geb_nr = s.geb_nr_normalisiert
left join institute i on i.inst_nr = s.kost_nr
