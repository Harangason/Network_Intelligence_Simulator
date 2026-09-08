# IP-Transport, Reparaturzyklus und Stabilitätsnachweis

Stand: 2026-09-08. Kanonisches Repository: `I:\PycharmProjects\My_first_Network_Simulator`.

## Ergebnis

Projektgebundene IPv4-/IPv6-Pakete und getrennte Ethernet-TX-/RX-Warteschlangen sind implementiert. Der positive Reparatur–Validierungs–Review–Apply–Re-Simulationszyklus ist über die laufende Anwendung nachgewiesen. Explizite empfangsabhängige Signalkaskaden und ein mehrgigabytegroßer Trace unter paralleler Dauerlast sind getestet. Dies ist keine pauschale Abnahme sämtlicher Fachmodelle der ursprünglichen Zielvereinbarung.

## Ethernet/IP: Verwendung und Modellgrenze

- Freigegebene Routen, Hardwareports, Interface-Konfigurationen und zugewiesene `TechnologyAddressBinding`-Datensätze fließen in den unveränderlichen SimulationSnapshot ein. Reine logische Diagnoseadressen werden nicht als IP-Adresse ausgegeben.
- `ipv4`, `ipv6`, `mac`/`mac_address`, `ip_version`, `transport_protocol`, `source_port`, `destination_port`, `udp_port`, `tcp_port`, `mtu` und `vlan_id` werden an den relevanten Interfaces bzw. Routen berücksichtigt. Die Snapshot-Konfiguration kann die IP-Familie und Transportparameter als Standard vorgeben. Interface-/Routenvorgaben gehen vor; widersprüchliche Familien werden abgewiesen.
- Fehlende IP-/MAC-Adressen erhalten deterministische, ausschließlich simulierte Adressen mit Kennzeichnung `simulation_derived`. Diese ändern keine kanonische Adressvergabe. Widersprüchliche zugewiesene Bindings, ungültige Adressen, Portnummern, VLAN-Konflikte und MTU-Überschreitungen werden nicht stillschweigend repariert.
- `formats: ["universal-jsonl", "universal-csv", "pcap", "pcapng"]` erzeugt die Dateien aus denselben Ethernet-Ereignissen. PCAP/PCAPNG enthalten genau die kanonischen Payload-Bytes, zugehörige IP-/Transportheader und Prüfsummen. `ethernet_packet_map.jsonl` verknüpft Route, Sequenz, TX/RX-Zeit, physische Ports und Payload-Hash. Verlorene Pakete werden nicht als erfolgreicher Empfang exportiert.
- Ethernet nutzt ein vereinfachtes Full-Duplex-Store-and-Forward-Modell mit getrennten TX-/RX-Queues. Last wird pro Port/Richtung statt als Summe eines fiktiven Shared Bus ermittelt. PCAPNG-Interfaces kennzeichnen die Empfangsports.
- In **Trace Analyse → Botschaften / Sequenz** ein Ereignis auswählen: „IP- und Port-Zuordnung“ zeigt Familie, Transport, IP:Port, physische Portreferenzen und Adressherkunft. IPv6 wird als `[Adresse]:Port` dargestellt. Der URL-Zeitfokus bleibt beim Wechsel der Ansichten erhalten.

IPv4/IPv6 über UDP sowie TCP-Datensegmente sind byteweise getestet. Dies ist **kein vollständiger IP-/TCP-Stack**: kein ARP/NDP, Routingprotokoll, TCP-Verbindungsaufbau/ACK-/Congestion-Zustand, Fragmentierungsmodell oder vollständiger SOME/IP-/DDS-Anwendungsstack. Ethernet-Routing bezeichnet hier den freigegebenen Kommunikationspfad und dessen Endpunkte, nicht eine emulierte Router-FIB. PROFINET/EtherCAT werden nicht pauschal in IP eingekapselt.

Headergrundlagen: [RFC 791](https://www.rfc-editor.org/rfc/rfc791), [RFC 8200](https://www.rfc-editor.org/rfc/rfc8200), [RFC 768](https://www.rfc-editor.org/rfc/rfc768).

Andere Bustechnologien verwenden weiterhin ihre vorhandenen technologieabhängigen Frame-/Timing-/Fehlermodelle im Universal Trace. Der Live-IP-Test enthält zusätzlich echten CAN-FD-Verkehr. Der separate ältere native CAN-Export wurde nicht auf den neuen gemeinsamen IP-Paketpfad umgestellt; ein bitgenauer nativer Export aller Technologien wird nicht behauptet.

## Geschlossene Fehler im Reparaturablauf

1. Direkte Reasoning-Empfehlungen blieben `PROPOSED`: Der bestehende Validator wird jetzt vor Rückgabe aufgerufen. Review und Apply bleiben getrennt und geschützt.
2. Eine freigegebene Busaufteilung änderte die Topologie, aber nicht den neuen Transport-Snapshot: Die bereits vorhandene Topologieprojektion wird jetzt beim Einfrieren genutzt. Mehrfach verwendete logische Interfaces erhalten getrennte ausführbare Segmentreferenzen.
3. Unbenutzte Modellinterfaces konnten auf nicht simulierte Netze verweisen: Der Transport-Snapshot enthält nur tatsächlich routenverwendete Interfaces. Das Engineering-Modell bleibt vollständig erhalten.
4. Hardwarevalidierung konnte scheitern, während der Job `completed` meldete: Echte Simulationsläufe werden jetzt mit der konkreten Validierungsursache als fehlgeschlagen behandelt.
5. Messvergleich und vollständige Ursachenklärung waren vermischt: `UNCONFIRMED_MECHANISM` alleine bedeutet keine fehlenden Messdaten. Vollständige, vergleichbare Messungen können eine Verbesserung belegen; `cause_explanation_complete` zeigt separat verbleibende Erklärungsgrenzen. Tatsächliche Daten-/Modell-/Fensterlücken blockieren weiterhin den Nachweis.

### Positiver Live-Nachweis

Testprojekt `astra-e2e-da66df60a957`, keine Stubs oder direkten DB-Reparaturen:

| Messgröße | Vorher | Nach freigegebener Segmentierung |
|---|---:|---:|
| Deadline-Verletzungen | 7 | 0 |
| Maximale Latenz | 6,473514 ms | 3,326666 ms |
| Höchste gemessene Netzlast | 64,735145 % | 35,071185 % |
| Nachrichtenverluste | 0 | 0 |
| Signalanomalien | 0 | 0 |

Seed 42, Dauer 0,12 s, Szenario NORMAL, 5-ms-Deadline, Hardwaregeschwindigkeit, Payloads und Sendezyklen sind in beiden Läufen identisch. Der kontrollierte QA-Engpass wurde vor beiden Läufen hergestellt. Die Reparatur verändert die physische Verteilung, nicht die Eingangslast. Stimulus-Signaturen sowie gleiche Transport-/Signalabdeckung verhindern Scheinverbesserungen durch verringerte Nutzlast oder andere Stimuli.

Vorheriger Job: `519ebbde21fb45e59b5d0358a26cbfd8`; nachher: `f0ac16a1ac8c4da8868255cf68a95f87`. Proposal: `cc16a1bd-f8c9-4e92-8e6a-830b9fd75c9f`. Proposal-Erzeugung verändert noch keine Topologie; Apply ohne Review-Intent wurde mit 403 abgelehnt, freigegebenes Apply tatsächlich ausgeführt. Ergebnis: `IMPROVEMENT_VERIFIED_IN_WINDOW`. Die weiterhin ungeklärten Zustands-/Jitter-Beobachtungen im Nachherlauf werden ausdrücklich nicht als geklärt ausgegeben.

Berichte: `backend/test-output/ip-repair-wizard-final.json`, `backend/test-output/ip-repair-cycle.json`. Der Vergleich wurde zusätzlich per **Ursache analysieren → Vorherige Analyse → Läufe vergleichen** in der Oberfläche ausgelöst und sichtbar bestätigt; keine Browserwarnungen/-fehler im geprüften Ablauf.

## Empfangsabhängige Kaskaden

Das opt-in Signal-/Verhaltensmodell `parameters.transport_inputs` beschreibt benannte Eingänge mit `signal_id`, `max_age_ms`, `fallback` und `on_stale` (`hold` oder `fallback`). Eine explizite Formel verarbeitet die am Empfänger bereits zugestellten Samples, nicht automatisch den zuletzt gesendeten Wert. Beispiel:

```json
{"formula":"upstream * 2","transport_inputs":{"upstream":{"signal_id":"temperature","max_age_ms":15,"fallback":0,"on_stale":"fallback"}}}
```

Tests prüfen Input → Steuerantwort → Ausgang, Ausfall, Stale-Fallback und Wiederherstellung mit CAN-FD, PROFINET und DDS/RTPS. Zusätzlich: CAN-Burst, Gateway-Verzögerung und DDS-Nachrichtenverzögerung. Quellereignis, Zustellzeit vor Auswertung, Altersgrenze, Eingangsregel und Formel werden unabhängig aus Trace und eingefrorenem Modell nachgerechnet. Nur verknüpfte validierte Wirkungen ergeben `CASCADE_FAILURE`; gefälschte oder beschädigte Herkunftsbelege bestätigen keine Kausalität.

Das ist ein geprüftes diskretes Sample-/Altersmodell, keine vollständige Fahrzeugregelung, SPS-Anlage oder DDS-Perception-Pipeline. Die Referenzformel verwendet ideale zuletzt publizierte Eingangswerte; sie ist kein eigenständiger physikalischer Fault-free-Replay. Weitere Domänenmodelle benötigen explizite Regeln und eigene Abnahmedaten.

## Großtrace-Stabilität

Bericht: `backend/test-output/ip-reasoning-large-trace-soak.json`.

- 2.164.926.732 Bytes (2,16 GB / rund 2,02 GiB), 786.336 Records.
- 180,14 Sekunden Messphase, vier parallele Reader.
- 12.256 Fensterabfragen und 1.532 begrenzte Reasoning-Auswertungen, **0 Fehler**.
- Fenster-p95 93,43 ms, Maximum 168,37 ms; Reasoning-p95 8,19 ms.
- Prozessspeicher initial 67,34 MiB, maximal 79,42 MiB, abschließend 79,34 MiB.

Neue sparse Zeitindizes erlauben direkten Einstieg in späte Zeitfenster, ohne das gesamte JSONL zu scannen. Größen-/mtime-Prüfung und geordnete Einträge sichern die Verwendung ab; veraltete/fehlende Indizes fallen auf den vorhandenen begrenzten Reader zurück. Gleiche Zeitstempel an Blockgrenzen gehen nicht verloren.

Die große Datei ist ein synthetisch vervielfältigter, gestreamter Lastkorpus auf Basis realer Simulatorereignisse, keine stundenlange physikalische Neusimulation. Drei Minuten Dauerlast sind **kein Übernacht-/24-Stunden-Nachweis**. Die Datei bleibt für Wiederholungen unter dem im Bericht genannten `backend/test-output/trace-soak-...`-Pfad erhalten. Vollständige seitenübergreifende Reasoning-Aggregation bleibt außerhalb dieses Nachweises; die bestehenden Evidenzbudgets und `PAGINATED_AGGREGATION` gelten weiter.

## Regression und Reproduktion

- Backend: 704 Tests bestanden, abschließender Gesamtbericht `backend/test-output/ip-full-regression-final.xml`; zusätzlich `ip-comparison-final.xml` für die Vergleichsgrenze.
- Frontend: 182 Tests bestanden; TypeScript und Produktionsbuild erfolgreich. React-Prüfung: Navigation als reine Ableitung der URL, keine zusätzlichen Effekt-/Fetch-Ketten, stabile React-Keys und vorhandene ARIA-Kontexte.
- API-Smoke: 236 registrierte Routen-/Methoden-Kombinationen, 0 Fehler (`backend/test-output/ip-endpoints.json`). Erwartete Validierungs-/Zugriffsantworten 400/403/404/409 zählen nicht als Fehler; dies ist keine fachliche Vollprüfung jeder Operation.
- Live-IP: IPv4 und IPv6 mit je neun heruntergeladenen und unabhängig dekodierten Paketen, plus CAN-FD im selben Universal Trace (`backend/test-output/ip-live-e2e.json`). Konfigurierte IP-Bindings werden separat über eine echte isolierte PostgreSQL-Datenbank getestet; Live-Wizard-Adressen sind gekennzeichnete Simulationsableitungen.

```text
backend/.venv/Scripts/python.exe scripts/verify-live-wizard.py --report backend/test-output/new-wizard.json
backend/.venv/Scripts/python.exe scripts/verify-repair-cycle.py --wizard-report backend/test-output/new-wizard.json --report backend/test-output/new-repair.json
backend/.venv/Scripts/python.exe scripts/verify-live-wizard.py --technology ethernet --report backend/test-output/new-ip-wizard.json
backend/.venv/Scripts/python.exe scripts/verify-live-ip.py --wizard-report backend/test-output/new-ip-wizard.json --report backend/test-output/new-ip.json
backend/.venv/Scripts/python.exe scripts/verify-large-trace-soak.py --help
```

Reparaturskripte nur mit einem neu erzeugten `astra-e2e-`-Testprojekt starten. Pytest benötigt die isolierte Testdatenbank und auf diesem Windows-Rechner einen neuen `--basetemp` unter `.tmp`. Keine Zugangsdaten in Berichte übernehmen.

## Schutz des bestehenden Projekts

Das Nutzerprojekt `20260908103453543-44dfbb43` wurde nicht freigegeben, umgeplant oder neu simuliert. Unveränderte Versionsbasis: Engineering 1, Network Editor 2, Parameter 76, Capacity 2, übrige Versionen 0. Sein dauerhafter Agent-Status ist weiterhin `REVIEW_REQUIRED`. Vor jeder Containerbereitstellung wurden aktive Jobs und der echte dauerhafte Ausführungszustand geprüft. Testprojekte und Testtraces wurden nicht gelöscht.
