# Lokale Subnetze und bestätigte ECU-Weiterleitung

Umsetzung der ergänzenden Anforderung vom 14.09.2026. Dieser Teil ergänzt die
Nachrichten-/Signalentscheidung „Geroutet“; er ersetzt keine Signal-Kodierung,
Empfängerfreigabe oder Timingprüfung.

## Wirksame vorhandene Funktionen

- `communication_contract.scope: LOCAL_IO` erhält lokale Sensor-/Aktorkommunikation
  für die kanonisch zugeordneten Empfänger. Validierung, Simulationexport und
  Kapazitätsberechnung prüfen diese Grenze. Eine lokale LIN-Übertragung verursacht
  weiterhin Last auf ihrem tatsächlichen lokalen Bus.
- `capacity/dimensioning.py::bus_schedule` reserviert periodische LIN-Slots mit
  Rahmendauer, Timingreserve und Master-Jitter. Der Runtimeplan bindet den Slot an
  das jeweilige Netz; die Simulation serialisiert Übertragungen und berücksichtigt
  verpasste Pollslots. Ein Gatewayübergang vererbt keinen LIN-Slot auf einen CAN-Bus.
- CAN verwendet Arbitration und nicht das LIN-Master-/Slave-Verfahren. Unabhängige
  Busse besitzen unabhängige Belegungszustände.

## Geschlossene Generierungslücke

Die allgemeine Routengenerierung berücksichtigt jetzt bereits bestätigte,
gerichtete ECU-Portpaare in `identity.communication_forwarding`. Die Suche nutzt
denselben `RepairPlanner` wie Reparatur und physische Validierung. Sie verlangt
aktuelle kanonische Ports, passende Netze und vorhandene gespeicherte Leitungen.
Ein reiner Nachbarschaftspfad über eine ECU bestätigt keinen Netzwechsel.

Der Vorschlag speichert den vollständigen physischen Port-/Leitungspfad. Quelle
und Ziel folgen dessen tatsächlichen Endports; die Nachrichten-Publisherbindung
bleibt verbindlich. Die ECU bleibt `device_type: ECU`. Es werden keine zusätzlichen
Ports, Empfänger, Freigaben oder Protokolltransformationen erzeugt.

Innerhalb genau einer Vorschlagserzeugung teilen Nachrichten und Empfänger einen
Graphen. Generierung und physische Validierung verwenden dabei denselben Planner.
Der Batch-Kontext wird auch bei Fehlern beendet; ein späterer Aufruf liest neue
Freigaben und Widerrufe erneut. Es existiert kein projektübergreifender Cache.

Widerruf, falsche Richtung, geänderte Netzbindung und fehlende Leitungen machen
diese Weiterleitung unzulässig. Eine fremde Projektfreigabe gilt nicht im aktuellen
Projekt. Der Vorschlag bleibt bei fehlendem Nachweis sichtbar ungültig.

Implementierung:

- `backend/engineering/routing/forwarding_candidates.py`
- `backend/engineering/routing/generation.py`
- `backend/tests/test_confirmed_ecu_routing.py`

## Bewusste Grenze der Master-/Slave-Aussage

Der vorhandene LIN-Scheduler prüft einen abstrakten Ein-Master-Pollplan pro Netz.
Eine explizite, kanonisch bestätigte Master-/Slave-Rolle pro Hardwareport samt
Prüfung widersprüchlicher oder mehrfacher Master ist noch nicht implementiert.
Dieser Änderungsteil erfindet keine solche Rolle aus Gerätenamen, räumlicher
Nähe oder ECU-Typ. „Plan unter Annahmen realisierbar“ ist deshalb kein Nachweis
einer bestätigten physischen Masterzuordnung oder funktionalen Echtzeitfreigabe.

Ein späteres Rollenmodell muss die konkrete Port-/Netzzuordnung erfassen und
fehlende oder widersprüchliche Zuordnungen sichtbar offen lassen. Explizite
Fristen dürfen dadurch nicht automatisch gelockert werden.

## Ausgeführte Prüfung

Isolierter PostgreSQL-Lauf über `scripts/run-isolated-tests.py`:

```text
backend/tests/test_confirmed_ecu_routing.py
backend/tests/test_routing.py
backend/tests/test_wizard_routing_stability.py
backend/tests/test_communication_repair.py
backend/tests/test_communication_runtime.py
backend/tests/test_wizard_generation.py
backend/tests/test_wizard_communication.py
backend/tests/test_specialist_execution.py
133 passed, 1 warning in 95.96s
```

Die 16 neuen SQL-Fälle prüfen bestätigte LIN-, CAN-FD- und Ethernet-Portpaare,
unbestätigte/fehlende/falsch gerichtete Freigaben, falsche Netze, entfernte oder
widersprüchliche Leitungen, verschobene Ports, Widerruf eines erzeugten Pfads,
unveränderte Publisherbindung, Projektisolation sowie einmaligen Graphaufbau im
Batch und erneutes Lesen nach dessen Ende oder Fehler. Die bestehende Warnung betrifft
das Pydantic-Feld `EngineeringModelDelta.validate`, keinen neuen Testfehler.

Dies ist ein fokussierter Service-/SQL-Regressionsnachweis. Die vollständige
Wizard-/Browser-/HTTP-Abnahme und Bereitstellung sind im zugehörigen Release-Gate
nachzuweisen; dieser Bericht behauptet keinen zusätzlichen Release-PASS.
