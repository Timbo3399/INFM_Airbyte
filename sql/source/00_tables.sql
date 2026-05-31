-- Source PostgreSQL: Tabellen-Definitionen
-- Wird automatisch beim ersten Container-Start ausgeführt

-- FM: Gebäudedaten (Hochschule Offenburg)
CREATE TABLE IF NOT EXISTS fm_gebaeude (
    db_einfuegemarke  VARCHAR(10),
    geb_nr            VARCHAR(10)  NOT NULL,
    geb               VARCHAR(60),
    geb2              VARCHAR(60),
    baujahr           VARCHAR(10),
    besitz            VARCHAR(10),
    art               VARCHAR(10),
    gebber_nr         VARCHAR(10),
    hs_nr             VARCHAR(20),
    qkz               VARCHAR(10),
    fnw               INTEGER,
    pers_nr           INTEGER,
    denkmal_nr        VARCHAR(20),
    ort_nr            VARCHAR(10),
    stra_nr           VARCHAR(10),
    haus_nr           VARCHAR(20),
    gemark_nr         VARCHAR(10),
    flur_nr           VARCHAR(10),
    flurst_nr         VARCHAR(30),
    miete             DECIMAL(14,2),
    bauwerk           VARCHAR(20),
    b_grad            DECIMAL(15,10),
    l_grad            DECIMAL(15,10),
    bem               VARCHAR(255),
    text_geb          VARCHAR(255),
    kurz_geb          VARCHAR(20),
    PRIMARY KEY (geb_nr)
);

-- FM: Institute / Organisationseinheiten
CREATE TABLE IF NOT EXISTS fm_inst (
    db_einfuegemarke  VARCHAR(10),
    inst_nr           VARCHAR(20)  NOT NULL,
    uebinst_nr        VARCHAR(20),
    kname             VARCHAR(20),
    dname             VARCHAR(60),
    lname1            VARCHAR(120),
    lname2            VARCHAR(120),
    str               VARCHAR(60),
    gebname           VARCHAR(60),
    plz               VARCHAR(10),
    ort               VARCHAR(60),
    bes_pers          VARCHAR(60),
    bes_tel           VARCHAR(30),
    bes_umsatz        DECIMAL(14,2),
    bes_vj_umsatz1    DECIMAL(14,2),
    bes_vj_umsatz2    DECIMAL(14,2),
    ivs_pers          VARCHAR(60),
    ivs_tel           VARCHAR(30),
    fins              VARCHAR(20),
    lehr              VARCHAR(10),
    habpos            VARCHAR(10),
    orgstruktur       INTEGER,
    key_von           DATE,
    key_bis           DATE
);

-- Postleitzahlen Deutschland
CREATE TABLE IF NOT EXISTS k_plz (
    db_einfuegemarke  VARCHAR(10),
    plz               VARCHAR(10)  NOT NULL,
    ueberkey          VARCHAR(10),
    art               VARCHAR(5),
    aikz              VARCHAR(5),
    grokz             VARCHAR(5),
    ort               VARCHAR(60),
    krskfz            VARCHAR(50),   -- enthaelt teils Kreis-Namen (z.B. "Kr Hzgt Lauenburg")
    krs_astat         VARCHAR(10),
    vv_bez            VARCHAR(60)
);

-- FM: Stammdaten Räume (verknüpft geb + inst)
CREATE TABLE IF NOT EXISTS fm_stamm (
    db_einfuegemarke  VARCHAR(10),
    geb_nr            VARCHAR(10)  NOT NULL,
    ges_nr            VARCHAR(10)  NOT NULL,
    raumid            VARCHAR(20)  NOT NULL,
    raumnr            VARCHAR(20),
    flaeche           DECIMAL(14,2),
    rna_nr            VARCHAR(10),
    bez               VARCHAR(120),
    nutzer_nr         VARCHAR(20),
    datum             DATE,
    kost_nr           VARCHAR(20),
    traeger_nr        VARCHAR(20),
    fkt_nr            VARCHAR(10),
    kfa_nr            VARCHAR(10),
    bem               VARCHAR(255),
    raumco            VARCHAR(20),
    text_bez          VARCHAR(255),
    kurz_bez          VARCHAR(30),
    PRIMARY KEY (geb_nr, ges_nr, raumid)
);

-- Studierende (anonymisiert)
CREATE TABLE IF NOT EXISTS hso_students (
    mtknr             INTEGER,
    firstname         VARCHAR(100),
    surname           VARCHAR(100),
    allfirstnames     VARCHAR(100),
    academicTitle     VARCHAR(20),
    dateofbirth       DATE,
    birthcity         VARCHAR(100),
    country           VARCHAR(5),
    gender            CHAR(1),
    nationalityId     VARCHAR(5),
    secondNationality VARCHAR(5),
    accounts          VARCHAR(255),
    hochschulEmail    VARCHAR(255),
    privateEmail      VARCHAR(255),
    phone             VARCHAR(50),
    currentSem        VARCHAR(20),
    immaDat           VARCHAR(20),
    exmaDat           VARCHAR(20),
    exmaReason        VARCHAR(100),
    studyStatus       VARCHAR(50),
    universitysemester INTEGER,
    kollegsemester    INTEGER,
    practicalsemester INTEGER,
    leavesemester     INTEGER,
    stg_key           VARCHAR(20),
    stg               VARCHAR(20),
    fach              VARCHAR(10),
    degree            VARCHAR(10),
    poversion         VARCHAR(20),
    fakultaet         VARCHAR(100),
    stort             VARCHAR(20),
    studentstatus     VARCHAR(50),
    studysemester     INTEGER,
    curriculumsemester INTEGER,
    progressvector    VARCHAR(255),
    subjectfocus      VARCHAR(100),
    h1_syncVers       VARCHAR(50),
    dbversion         VARCHAR(50),
    createdat         TIMESTAMP,
    updatedat         TIMESTAMP
);
