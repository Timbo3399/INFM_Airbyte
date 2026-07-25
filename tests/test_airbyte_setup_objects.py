"""Tests fuer die reinen Funktionen in scripts/airbyte_setup_objects.py.

Kein laufendes Airbyte noetig: getestet werden Credential-Aufloesung,
.env-Parsing und der Idempotenz-Abgleich gegen bereits vorhandene Objekte.
"""
import airbyte_setup_objects as a

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


def test_file_source_setzt_trennzeichen_als_reader_option():
    cfg = a.source_file_config("/local/hso_students.csv", "hso_students", separator="|")
    assert cfg["provider"] == {"storage": "local"}
    assert '"sep": "|"' in cfg["reader_options"]
