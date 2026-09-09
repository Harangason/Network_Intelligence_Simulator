# Agent- und Portkorrekturen vom 9. September 2026

Die im Agent-Audit nachgewiesenen fünf Vertragsfehler wurden behoben. Zusätzlich wurde die physische Topologie an kanonische Hardwarekanäle gebunden und an einem isolierten Klon des Projekts mit 260 Geräten geprüft. Das Originalprojekt wurde durch diese Arbeiten nicht verändert.

## Umgesetzte Agent-Verträge

- Der Chatverlauf speichert Vorschlagsreferenzen mit exakten Mengenangaben. Die Review-Karte lädt die vollständige aktuelle Revision nach und zeigt jeweils 50 Änderungen. Ein fehlgeschlagener Vollabruf sperrt die Freigabe. Ein Regressionstest durchläuft alle 3.000 Änderungen und alle 60 Seiten nach dem erneuten Laden.
- Der Heartbeat führt die Verlängerung explizit im Projektkontext aus. Eine verlorene oder nicht bestätigte Gesprächssperre beendet den Hintergrundlauf kontrolliert. Allgemeine Fortschrittsereignisse löschen die gespeicherte Workload-ID nicht mehr.
- Freie Änderungsaufträge benötigen einen durch Werkzeuge erzeugten und validierten Vorschlag. Reine Erfolgssätze des Sprachmodells führen nicht zu einer Abschlussmeldung. Die Antwort unterscheidet Vorschlag, Freigabe und tatsächliche Übernahme.
- `pyproject.toml` und `uv.lock` enthalten nun die tatsächlich benötigten Abhängigkeiten `httpx` und das externe MCP-SDK. Eine neue Umgebung wurde mit `uv sync --frozen` aufgebaut und die Agent-/MCP-Tests darin ausgeführt.

## Physische Kanäle und Sendebindungen

`backend/engineering/physical_ports.py` erzeugt eine geordnete Liste prüfbarer Netz-, Hardwarekanal- und Nachrichtenänderungen zusammen mit der Topologie. Unabhängige Netze erhalten unterschiedliche Hardwarekanäle mit passender Technologie, Kanalnummer und Anschlussreferenz. Vorhandene geeignete Kanäle werden wiederverwendet. Neue Kanäle bleiben als zusätzliche Hardware-Ressourcen im Vorschlag sichtbar.

Die gemeinsame Prüfung erkennt fehlende Referenzen, falsche Geräteeigentümer, unterschiedliche Bustypen, falsche Netzwerkbindungen, mehrfach verwendete Kanäle sowie widersprüchliche Kantenendpunkte. Sie arbeitet sowohl mit gespeicherten IDs als auch mit dem vollständigen Vorschlagsmodell einschließlich `$local_ref`-Referenzen. Der Workflow bewertet die tatsächlichen kanonischen Bindungen; ein syntaktisch vollständiger Canvas reicht nicht mehr aus.

Eine Nachricht kann bewusst über mehrere physische Kanäle versendet werden. Dafür werden zusätzliche `Message.configuration.physical_transmit_bindings` explizit freigegeben. Geräte-, Technologie- und Netzwerkbezüge werden geprüft. Der Routing-Generator berücksichtigt diese Bindungen bei der Auswahl des Quellkanals; Payload, Nachrichten- und Signalidentität bleiben erhalten.

Beim gemeinsamen Übernehmen von Hardwarekanälen und Topologie wird die Modellinvalidierung vor dem Speichern der bestätigten Topologie ausgeführt. Andernfalls würde der gerade übernommene Netzwerkstand unmittelbar wieder als veraltet markiert. Die bestehenden Routen werden anschließend anhand ihrer bestätigten Topologie erneut geprüft.

## Nachweis am isolierten Bestandsklon

Projekt: `nis-correction-large-0909`, ausschließlich Testdatenbank auf Port 15439.

| Prüfung | Ergebnis |
|---|---:|
| Falsche Port-Netzbindungen vorher | 300 |
| Hardwarekanal-Aliase über unabhängige Netze vorher | 19 |
| Ethernet-Kanal als CAN-Port vorher | 1 |
| Neu deklarierte physische Netze | 84 |
| Aktualisierte bestehende Hardwarekanäle | 287 |
| Zusätzlich benötigte Hardwarekanäle | 13 |
| Nachrichten mit zusätzlicher expliziter Sendebindung | 9 |
| Kanonische Topologie nach Übernahme | 260 Geräte, 300 Ports, 216 Kanten, 84 Netze |
| Technisch gültige und weiterhin freigegebene Routen | 217 von 217 |
| Zweiter Migrationsdurchlauf | `UNCHANGED` |

Die technische Gültigkeit der vorhandenen Routen ersetzt keine fachliche Vollständigkeitsprüfung. Fehlende Kommunikationsanforderungen oder Verbraucher bleiben im separaten Coverage-Prüfschritt sichtbar.

Nach der ergänzenden Erstellung bestätigter Rückmeldungsrouten wurde die Topologie erneut aus 317 gültigen Routen erzeugt, geprüft und übernommen. Vorhandene Netze, Port- und Kanten-IDs, Geräteeigentümer und Layout blieben erhalten: 260 Geräte, 216 Kanten und alle 317 zugehörigen Routen, ohne zusätzliche Hardwarekanäle. Der Generator bevorzugt bestehende Verbindungen und kanonische Netzwerkbindungen vor Namensheuristiken. Neue Rückrouten werden der vorhandenen physischen Verbindung zugeordnet. Die weiterhin fehlenden Verbraucher für 47 Nachrichten bleiben im vollständigen Modellumfang als offene Anforderungen sichtbar.

Reproduzierbare Migration: `scripts/repair-physical-ports.py --project <Projekt-ID>`. Ohne `--apply` erfolgt eine reine Vorschau. `--apply` erzeugt, validiert, genehmigt und übernimmt den vollständigen Vorschlag in dem ausdrücklich angegebenen Projekt und prüft anschließend die Idempotenz. Die Testnachweise liegen unter `verification/2026-09-09-physical-port-migration-result.jsonl` und `verification/2026-09-09-physical-message-bindings-result.jsonl`.

## Lokale Modellanbindung

Der echte HTTP-Test zeigte zusätzlich den Ollama-Fehler `no user query found in messages`. Der lokale Chat erhielt kein explizites Kontextfenster; Werkzeugschemas und Ergebnisse konnten den Nutzerturn aus dem kleinen Standardfenster verdrängen. Die Anbindung setzt jetzt ein konfigurierbares Fenster (`LOCAL_AI_CONTEXT_TOKENS`, Standard 32768), begrenzt Ergebnisansichten und verwendet den nativen Ollama-Werkzeugvertrag mit `tool_name`. Der gleiche Fehler ist im [Ollama-Projekt dokumentiert](https://github.com/ollama/ollama/issues/18107); die offiziellen Verträge beschreiben [Werkzeugantworten](https://docs.ollama.com/capabilities/tool-calling) und [Kontextfenster](https://docs.ollama.com/faq).

Für die Modellansicht werden die MCP-`request`-Hülle und lokale Schematypreferenzen aufgelöst; der MCP-Client behält die tatsächliche Transporthülle. Fehlerhaftes JSON aus einem Modellaufruf wird als Werkzeugvalidierungsfehler zurückgegeben, damit der Agent es korrigieren kann. Kurze reine Hardware-Inventarfragen verwenden das konfigurierte schnelle Modell. Änderungsimperative bleiben beim Hauptmodell.

Die gezielte integrierte Regression lief mit 96 bestandenen Tests; die anschließende Routing-Auswahlprüfung mit 30 bestandenen Tests. Die native Modellanbindung bestand zehn gezielte Prüfungen, die anschließende Bestandserhaltung eine zusätzliche Regression. Die Läufe überschneiden sich und werden daher nicht zu einer Gesamtsumme addiert. Der gesamte aktuelle Backend-/Browser-Abnahmestand wird im Hauptbericht zusammengeführt.

## Echte Agent-Abnahme über HTTP

Auf dem isolierten Projekt `nis-correction-agent-roundtrip-401e1b4407` wurde das vorhandene Hardwareobjekt über den echten Agenten abgefragt. Die begrenzte Inventarfrage mit `llama3.1:8b` wurde in 25,31 Sekunden beantwortet. Ein freier Auftrag zur ausschließlichen Änderung der Beschreibung erzeugte mit dem konfigurierten Hauptmodell `qwen3.8:27b` in 152,85 Sekunden genau einen validierten Änderungsvorschlag. Dies sind einzelne beobachtete Laufzeiten, keine reproduzierbare Leistungskennzahl.

Sechs Prüfungen sind in `verification/2026-09-09-real-agent-roundtrip.json` dokumentiert: sachlich richtige Inventarauskunft, tatsächlicher Vorschlag bei unverändertem Modell vor Freigabe, abgewiesene Übernahme ohne Freigabeabsicht (`403`), abgewiesene veraltete Revision (`409`), erfolgreiche Freigabe und persistierte Übernahme einschließlich vollständig nachgeladenem Vorschlag aus der Chatverlaufsreferenz sowie idempotente erneute Übernahme. Nach dem tatsächlichen Review und Apply enthielt ausschließlich die gewünschte Beschreibung den neuen Wert. Die Abnahme nutzte Backend-Port 15059 und die Testdatenbank; das ursprüngliche Projekt wurde nicht verändert.
