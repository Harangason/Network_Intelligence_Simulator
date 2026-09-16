# Trace-Dateiimport

Der Dateidialog in `/trace-analysis` sendet die Datei an `POST /api/trace-import?filename=...`.
Der Python-Adapter liefert eine reine Analyseprojektion zurück. Er schreibt keine
Engineering-Objekte, Evidence oder TraceLinks. Originaldatei, Herkunfts-Hash und
normalisierte Ereignisse werden unter `SAVED/<Projekt>/trace-imports/<Session>/` gespeichert.

| Format | Unterstützte Inhalte |
| --- | --- |
| CSV, JSON, JSONL | Universal-Trace-Ereignisse mit Zeitspalte in Sekunden; vorhandene Signalwerte bleiben erhalten |
| ASC, BLF | CAN/CAN-FD-Frames einschließlich IDs, Kanal, Payload und Richtung |
| LOG, TRC | CAN-Logs über python-can; LOG bezeichnet das candump-Format |
| PCAP | Rohpakete; Ethernet-MAC/EtherType, erkannte IPv4/IPv6-Adressen, TCP/UDP-Ports und TCP-Flags |
| PCAPNG | Eine Section und eine Schnittstelle, Enhanced Packet Blocks; andere Layouts werden ausdrücklich abgelehnt |
| MDF 3, MDF 4 / MF4 | Skalare Messkanäle mit gespeicherten Konvertierungen und Einheiten; MDF-4-CAN-Busaufzeichnungen als Rohframes |

Binärformate werden anhand der Signatur erkannt, auch bei abweichender Endung.
Eine Binärendung ohne passende Signatur wird abgelehnt. CAN-Textdateien unterstützen
UTF-8 und Windows-1252. Nicht unterstützte Busobjekte sind keine dekodierten Signale.
DBC-/ARXML-gestützte Decodierung von Rohframes ist noch nicht Teil dieses Imports.

Der Upload umfasst maximal 500 MiB. Text-, CAN- und Capture-Importe werden vollständig
normalisiert; der Browser lädt begrenzte Seiten mit maximal 2.000 Ereignissen.
`GET /api/trace-import/<session_id>` unterstützt Byte-Cursor, Zeitfenster und Textfilter.
Sessions sind projektgebunden und nach dem Neuladen wieder verfügbar.
Unterstützte skalare MDF-Kanäle werden in begrenzten Blöcken vollständig gelesen;
nicht unterstützte strukturierte Kanäle und Busobjekte bleiben ausdrücklich gekennzeichnete Grenzen. MDF erlaubt maximal
256 Messkanäle; strukturierte Messkanäle werden mit Hinweis ausgelassen. Eine
gekürzte Vorschau wird ausdrücklich markiert und ist keine vollständige Analyse
der Quelldatei. Originalzeitstempel bleiben erhalten; MDF-Busframes werden auf die
relative MDF-Zeitachse zurückgeführt. Ein Dateiwechsel setzt UI-Filter zurück.
Fehler ersetzen eine zuvor erfolgreich geladene Session nicht.

Parser: `backend/app/trace_import.py`; Next-Proxy:
`frontend/src/app/api/trace-import/route.ts`; Anzeige:
`frontend/src/components/trace-analysis-workbench.tsx`.
Runtime-Abhängigkeiten stehen in requirements.txt, requirements.lock und uv.lock.

## Verifikation

`backend/.venv/Scripts/python.exe scripts/run-isolated-tests.py -- backend/tests/test_trace_import.py -q`

Die Tests verwenden tatsächlich geschriebene ASC-/BLF-/LOG-/TRC-/PCAP-/PCAPNG-/MDF-Dateien,
CAN FD, rohe CAN-MF4-Aufzeichnungen, Fehlerfälle, Vorschaukürzung und den Flask-HTTP-Endpunkt.
Sie beweisen keine Browser-E2E- oder Wizard-Releaseabnahme. Eine produktive Auslieferung
ist getrennt vom hier geprüften Importumfang zu bewerten.

## Universelle Darstellung

Die Darstellung verwendet die erweiterbare Profilregistrierung in
`frontend/src/lib/trace-profiles.ts`. CAN, Ethernet/IP und Messsignale besitzen
Spaltenvorgaben. Gemischte und unbekannte Inhalte erhalten eine generische Ansicht.
Der Protokollfilter verwendet die tatsächliche Technologiebezeichnung, sodass
auch unbekannte Protokolle getrennt ausgewählt werden können. Das automatische
Profil und die verfügbaren Spalten werden aus dem vollständigen geladenen
Sessionfenster abgeleitet und wechseln nicht durch den lokalen Textfilter.

Originalfelder bleiben in `TraceEvent.original` erhalten. Zusätzliche Felder sind
als Spalten auswählbar (bis sechs Ebenen); tiefere Strukturen bleiben vollständig
in der Ereignisdetailansicht sichtbar. Null, false und 0 werden unterschieden.
Neue Profile sind Präsentationsadapter, keine Decoder: Protokollinterpretation
geschieht im Python-Importer. Fehlende Signaldecodierung ist kein Fehlerbefund.

JSON-Ereignisse ohne Zeit erhalten `time_status: unavailable`, keine künstliche
Nullzeit. Sie bleiben in der Tabelle sichtbar und sind entsprechend beschriftet.
Originalzeitwerte, Quellreihenfolge und vorhandene Zeitbasis bleiben erhalten.
Unterschiedliche explizite Zeitbasen werden beim Import nicht gemeinsam sortiert.
Eine Synchronisierung unterschiedlicher Uhren wird nicht durchgeführt.


Große Uploads werden in 1-MiB-Blöcken in eine temporäre Datei geschrieben und
nach erfolgreichem Import mit der Session gespeichert; temporäre Uploads werden gelöscht. Capture-Validierung nutzt eine Dateispeicherabbildung;
CSV, JSONL und JSON werden fortlaufend in den Session-Speicher geschrieben. Die ersten
2.000 Ereignisse sind keine vollständige Analyse der Datei. Der Assistent kann
Trace-Dateien bis 500 MiB auswählen und erhält nur einen als Auszug markierten
Text mit maximal 16.000 Zeichen. Normale Dokumentanhänge bleiben bei 5 MiB.
