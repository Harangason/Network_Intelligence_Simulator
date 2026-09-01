# Kanonischer Projektpfad

## Umzug

Der Communication Simulator wurde am 27. August 2026 auf den kanonischen
Arbeits- und Startpfad

```text
I:\PycharmProjects\My_first_Network_Simulator
```

verschoben. Frühere Benutzerprofil-Kopien sind nur noch Altstand und dürfen
nicht als Start- oder Projektwurzel verwendet werden.

## Externe Laufzeitdaten

Große Ollama-Modelle liegen bewusst außerhalb des Repositories:

```text
I:\engineering-intelligence-platform\models\ollama
```

Die private gemeinsame Provider-Konfiguration bleibt ebenfalls außerhalb des
Repositories und wird über `NETWORKIS_SHARED_ENV_FILE` referenziert:

```text
%USERPROFILE%\PycharmProjects\.env
```

API-Schlüssel werden weder in diese Dokumentation noch in das Repository
übernommen.

## Standardstart

```powershell
Set-Location I:\PycharmProjects\My_first_Network_Simulator
.\start-networkis-local-ai.bat
```

Der lokale Standard ist `qwen3.8:27b` über Ollama. OpenAI und
NVIDIA NIM/Nemotron bleiben Bedarfsprovider.
