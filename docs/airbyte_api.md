# Airbyte API

API Docs: <https://reference.airbyte.com/reference/getting-started>

Neben der Verwendung von Airbyte über die UI, ist auch eine programmatische Interaktion mit Airbyte möglich.
Es kann zum Beispiel in Kombination mit Orchestrierungstools wie Airflow genutzt werden.
Im Folgenden sollen die ersten Schritte beschrieben werden. (siehe auch: <https://docs.airbyte.com/platform/using-airbyte/configuring-api-access>)

## 1. Access Token holen ##

Die Endpunkte der Airbyte Public API sind gesichert und erfordern eine Authentifizierung mittels **Bearer Token**.
Um dieses Token zu erhalten, muss zunächst über User-->Application zu den Applications navigiert werden.
Dieses repräsentiert in Airbyte einen einzelnen Benutzer anhand einer Client-ID und eines Client Secrets.
Falls defaultmäßig noch keine Application vorhanden ist, muss über "Create an application" eine neue Anwendung erstellt werden.

**Es gibt zwei Möglichkeiten, um an den Access Token zu kommen:**

### Token manuell über die UI holen ###

Bei Applications muss auf "Default User Application" gehovert werden, dann erscheint der Button *"Generate access token"*
**Wichtig: Der Token wird nur einmal angezeigt. Bei Verlust muss ein neuer Key generiert werden.**

### Token über die Kommandozeile holen ###

Mit folgendem Request, kann sich der Token programmatisch geholt werden.
Die **Client-ID** und das **Client-Secret** müssen dafür zunächst aus der Applications Abschnitt ausgelesen werden.

`curl --request POST \
     --url http://localhost:8000/api/public/v1/applications/token \
     --header 'accept: application/json' \
     --header 'content-type: application/json' \
     --data '
{
  "client_id": "<YOUR_CLIENT_ID>",
  "client_secret": "<YOUR_CLIENT_SECRET>",
  "grant-type": "client_credentials"
}
'`

Bei Erfolg hält man einen Response mit dem Access-Token in folgender Form:

`{
  "access_token": "<YOUR_ACCESS_TOKEN>",
  "token_type": "Bearer",
  "expires_in": 900
}`

**Der Token expired nach 15 Minuten. Anschließend muss über die UI oder die Konsole erst ein neuer Token generiert werden.**

## 2. API-Requests ###

Der generierte Access-Token muss anschließend für alle Requests zur Authentifizierung verwendet werden.

**Im Folgenden wird ein GET-Request durchgeführt, um alle Airbyte Source-Connectors aufzulisten.**

`curl --request GET \
     --url 'http://localhost:8000/api/public/v1/sources' \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_ACCESS_TOKEN>'`

**Die Response wird in dieser Form zurückgesendet:**

```json
{
  "data": [
    {
      "sourceId": "f226c273-95cd-4343-b001-f4e1a85e1fb7",
      "name": "HSO Source PostgreSQL",
      "sourceType": "postgres",
      "definitionId": "decd338e-5647-4c0b-adf4-da0e75f5a750",
      "workspaceId": "4f566621-6a5c-464c-9fbd-43651c987e90",
      "configuration": {
        "host": "host.docker.internal",
        "port": 5433,
        "...": "..." 
      },
      "createdAt": 1780234554
    },
    {
      "...": "Weitere Datenquellen wurden zur Übersichtlichkeit gekürzt..."
    }
  ],
  "previous": "",
  "next": "http://localhost:8001/api/public/v1/sources?..."
}
```

Auf diese Weise lassen sich auch Automatisierung umsetzen.

Die Airbyte-API Doku mit allen möglichen Requests: <https://reference.airbyte.com/reference/getting-started>