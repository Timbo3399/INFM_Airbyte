"""Tests fuer die reinen Funktionen in scripts/airbyte/setup_objects.py.

Kein laufendes Airbyte noetig: getestet werden Credential-Aufloesung,
.env-Parsing und der Idempotenz-Abgleich gegen bereits vorhandene Objekte.
"""
import pytest

import setup_objects as a

# Beispielausgabe von `abctl local credentials` mit erfundenen Werten.
ABCTL_AUSGABE = """
  Provider: kind
  Kubeconfig: /home/user/.airbyte/abctl/abctl.kubeconfig
  Context: kind-airbyte-abctl
  Email: admin@example.com
  Password: nichtdasechte
  Client-Id: 11111111-2222-3333-4444-555555555555
  Client-Secret: abcdefabcdefabcdefabcdefabcdef12
"""


# --- abctl-Ausgabe parsen -----------------------------------------------------

def test_parst_client_id_und_secret_aus_der_abctl_ausgabe():
    assert a.parse_abctl_credentials(ABCTL_AUSGABE) == (
        "11111111-2222-3333-4444-555555555555",
        "abcdefabcdefabcdefabcdefabcdef12",
    )


def test_ohne_credentials_in_der_ausgabe_kommt_nichts_zurueck():
    assert a.parse_abctl_credentials("Provider: kind\nContext: irgendwas") == (None, None)


# --- .env lesen ---------------------------------------------------------------

def test_env_datei_wird_zu_dict(tmp_path):
    p = tmp_path / ".env"
    p.write_text(
        "# Kommentar\n"
        "\n"
        "AIRBYTE_CLIENT_ID=abc123\n"
        "  AIRBYTE_CLIENT_SECRET = xyz789  \n"
        "SOURCE_PG_PASSWORD=sourcepassword\n",
        encoding="utf-8",
    )
    werte = a.read_env_file(str(p))
    assert werte["AIRBYTE_CLIENT_ID"] == "abc123"
    assert werte["AIRBYTE_CLIENT_SECRET"] == "xyz789"
    assert "# Kommentar" not in werte


def test_fehlende_env_datei_ergibt_leeres_dict(tmp_path):
    assert a.read_env_file(str(tmp_path / "gibtesnicht")) == {}


def test_leere_werte_in_der_env_zaehlen_als_nicht_gesetzt(tmp_path):
    p = tmp_path / ".env"
    p.write_text("AIRBYTE_CLIENT_ID=\n", encoding="utf-8")
    assert a.read_env_file(str(p)).get("AIRBYTE_CLIENT_ID") in (None, "")


# --- Reihenfolge der Quellen --------------------------------------------------

def test_prozess_umgebung_schlaegt_env_datei():
    got = a.resolve_credentials(
        {"AIRBYTE_CLIENT_ID": "aus-prozess", "AIRBYTE_CLIENT_SECRET": "s1"},
        {"AIRBYTE_CLIENT_ID": "aus-datei", "AIRBYTE_CLIENT_SECRET": "s2"},
        ABCTL_AUSGABE,
    )
    assert got == ("aus-prozess", "s1")


def test_env_datei_schlaegt_abctl():
    got = a.resolve_credentials(
        {},
        {"AIRBYTE_CLIENT_ID": "aus-datei", "AIRBYTE_CLIENT_SECRET": "s2"},
        ABCTL_AUSGABE,
    )
    assert got == ("aus-datei", "s2")


def test_ohne_alles_greift_abctl():
    got = a.resolve_credentials({}, {}, ABCTL_AUSGABE)
    assert got == (
        "11111111-2222-3333-4444-555555555555",
        "abcdefabcdefabcdefabcdefabcdef12",
    )


def test_gar_keine_quelle_ergibt_none():
    assert a.resolve_credentials({}, {}, None) == (None, None)


def test_halbe_angabe_zaehlt_nicht_als_treffer():
    # Nur die ID ohne Secret ist unbrauchbar, dann lieber die naechste Quelle.
    got = a.resolve_credentials({"AIRBYTE_CLIENT_ID": "nur-id"}, {}, ABCTL_AUSGABE)
    assert got == (
        "11111111-2222-3333-4444-555555555555",
        "abcdefabcdefabcdefabcdefabcdef12",
    )


# --- Idempotenz ---------------------------------------------------------------

def test_findet_vorhandenes_objekt_am_namen():
    vorhanden = [{"name": "HSO Dest MySQL", "destinationId": "d-2"},
                 {"name": "HSO Dest PostgreSQL", "destinationId": "d-1"}]
    assert a.find_by_name(vorhanden, "HSO Dest PostgreSQL", "destinationId") == "d-1"


def test_unbekannter_name_ergibt_none():
    assert a.find_by_name([{"name": "X", "sourceId": "s-1"}], "Y", "sourceId") is None


def test_plan_trennt_anzulegende_von_vorhandenen():
    vorhanden = [{"name": "A", "sourceId": "s-1"}]
    gewuenscht = ["A", "B", "C"]
    neu, bekannt = a.plan(vorhanden, gewuenscht, "sourceId")
    assert neu == ["B", "C"]
    assert bekannt == {"A": "s-1"}


# --- Payloads -----------------------------------------------------------------
# Die Pflichtfelder stammen nicht aus der Doku, sondern aus den 422-Antworten
# der laufenden Instanz. Deshalb hier festgehalten.

def test_postgres_source_braucht_tunnel_method():
    # Ohne tunnel_method: HTTP 422 "required property 'tunnel_method' not found"
    cfg = a.source_postgres_config("host.docker.internal", 5433, "sourcedb", "u", "p")
    assert cfg["tunnel_method"] == {"tunnel_method": "NO_TUNNEL"}


def test_postgres_source_nutzt_user_defined_cursor_statt_cdc():
    cfg = a.source_postgres_config("h", 5433, "db", "u", "p")
    assert cfg["replication_method"] == {"method": "Standard"}
    assert cfg["ssl_mode"] == {"mode": "disable"}


def test_postgres_destination_braucht_tunnel_method():
    cfg = a.destination_postgres_config("h", 5434, "destdb", "u", "p")
    assert cfg["tunnel_method"] == {"tunnel_method": "NO_TUNNEL"}


def test_mysql_destination_braucht_tunnel_method_und_public_key_retrieval():
    cfg = a.destination_mysql_config("h", 3306, "destdb", "u", "p")
    assert cfg["tunnel_method"] == {"tunnel_method": "NO_TUNNEL"}
    assert cfg["jdbc_url_params"] == "allowPublicKeyRetrieval=true"


def test_mysql_destination_legt_rohdaten_in_die_eigene_datenbank():
    # Ohne raw_data_schema versucht Airbyte, die Datenbank airbyte_internal
    # anzulegen. destuser darf das nicht, der Sync bricht dann mit
    # "Destination process exited with non-zero exit code 1" ab.
    cfg = a.destination_mysql_config("h", 3306, "destdb", "u", "p")
    assert cfg["raw_data_schema"] == "destdb"


def test_file_source_setzt_trennzeichen_als_reader_option():
    cfg = a.source_file_config("/local/hso_students.csv", "hso_students", separator="|")
    assert cfg["provider"] == {"storage": "local"}
    assert '"sep": "|"' in cfg["reader_options"]


# --- Fallback, wenn Credentials nicht mehr gelten ----------------------------
#
# Nach einem 'abctl local uninstall' plus Neuinstallation erzeugt Airbyte neue
# Client-Credentials. In der .env stehen dann die alten. Weil .env vor abctl
# kommt, schickte das Skript die alten Werte und bekam "Invalid client id or
# token" zurueck, was nach einem Tippfehler aussieht und nicht nach veralteten
# Werten. Deshalb wird jeder Kandidat der Reihe nach ausprobiert.

def test_credential_kandidaten_kommen_in_der_richtigen_reihenfolge():
    kandidaten = a.credential_kandidaten(
        {"AIRBYTE_CLIENT_ID": "u", "AIRBYTE_CLIENT_SECRET": "u2"},
        {"AIRBYTE_CLIENT_ID": "e", "AIRBYTE_CLIENT_SECRET": "e2"},
        ABCTL_AUSGABE)

    abctl_id, _ = a.parse_abctl_credentials(ABCTL_AUSGABE)
    assert [k[1] for k in kandidaten] == ["u", "e", abctl_id]


def test_credential_kandidaten_nennt_jede_quelle_beim_namen():
    kandidaten = a.credential_kandidaten(
        {"AIRBYTE_CLIENT_ID": "u", "AIRBYTE_CLIENT_SECRET": "u2"}, {}, None)

    assert "Umgebung" in kandidaten[0][0]


def test_credential_kandidaten_ueberspringt_unvollstaendige_paare():
    # Nur die Id ohne Secret ist kein brauchbarer Kandidat.
    kandidaten = a.credential_kandidaten({"AIRBYTE_CLIENT_ID": "u"}, {}, None)

    assert kandidaten == []


def test_credential_kandidaten_ohne_jede_quelle_ist_leer():
    assert a.credential_kandidaten({}, {}, None) == []


def test_kurzer_grund_holt_die_kernaussage_aus_der_api_antwort():
    lang = ('Token-Anfrage fehlgeschlagen (HTTP 400): {"message":"Bad Request",'
            '"_embedded":{"errors":[{"message":"Invalid client id or token",'
            '"_embedded":{},"_links":{}}]}}')

    kurz = a.kurzer_grund(SystemExit(lang))

    assert "Invalid client id or token" in kurz
    assert len(kurz) < 80


def test_kurzer_grund_laesst_kurze_meldungen_stehen():
    assert a.kurzer_grund(SystemExit("Verbindung abgelehnt")) == "Verbindung abgelehnt"


def test_erste_funktionierende_nimmt_den_ersten_treffer():
    versucht = []

    def baue(cid, csec):
        versucht.append(cid)
        return f"api-{cid}"

    ergebnis = a.erste_funktionierende([("A", "1", "x"), ("B", "2", "y")], baue)

    assert ergebnis == "api-1"
    assert versucht == ["1"], "der zweite Kandidat haette nicht geprueft werden duerfen"


def test_erste_funktionierende_geht_bei_abgelehnten_credentials_weiter():
    def baue(cid, csec):
        if cid == "alt":
            raise SystemExit("Invalid client id or token")
        return f"api-{cid}"

    ergebnis = a.erste_funktionierende([("env", "alt", "x"), ("abctl", "neu", "y")], baue)

    assert ergebnis == "api-neu"


def test_erste_funktionierende_wirft_wenn_kein_kandidat_durchkommt():
    def baue(cid, csec):
        raise SystemExit("Invalid client id or token")

    with pytest.raises(SystemExit):
        a.erste_funktionierende([("env", "alt", "x")], baue)


def test_erste_funktionierende_wirft_bei_leerer_kandidatenliste():
    with pytest.raises(SystemExit):
        a.erste_funktionierende([], lambda cid, csec: "api")
