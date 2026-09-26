# 🔍 Tool Checker — Kurzlauf zu Technologie-Kapazitätslücken

**Modus:** gezielte, lesende Diagnose (`VERIFY_ONLY`), keine vollständige S01–S60-/EA-Kampagnenrunde und kein Release Gate. **Ziel:** prüfen, was im laufenden NIS-Produkt auf Port 13500 vorhanden ist. Projektansicht: `20260924204620805-295989d5`. Die bestehende Tool-Checker-Kampagne blieb unverändert.

## Ergebnis

**Die Lücke ist im laufenden Produkt weiterhin vorhanden.** `/api/build-info` meldete Build `ec011a3fdd2f` (25.09.2026, 01:29 MESZ). Die aktuelle Capacity-Analyse der geöffneten Projektansicht nutzt Berechnungsversion **3.3** und enthält kein `capacity_verified`-Feld in der Übersicht. Der reparierte Checkout nutzt Version **3.4**, wurde wegen eines fehlgeschlagenen Wizard-Release-Gates nicht bereitgestellt.

| Prüffrage | Laufendes Produkt | Aktueller Checkout |
| --- | --- | --- |
| Katalogeinträge | 125 | 125 |
| Generisches Rahmenmodell über die rohen 125 Katalog-IDs | 115 | nicht als Freigabenachweis verwendet; die fünf genannten Typen bleiben als generische Vorschau markiert |
| Eigene deterministische `bus_schedule`-Zweige | 4: CAN, CAN FD, LIN, Ethernet; 121 ohne eigenen Zweig | dieselben vier belastbaren Grundzweige; fehlende Nachweise führen zu `UNVERIFIED` |
| Rohe IDs ohne direkten Routing-Kapazitätsschlüssel oder GPIO/PWM-Ausnahme | 99 | keine fremde Ersatzkapazität für unsupported Modelle |
| EtherCAT, Profinet, Modbus RTU, I2C, SPI bei 8 Byte ohne Parameter | jeweils `GENERIC_ESTIMATE`, 256 Bit, 0,256 ms | weiterhin generische, ausdrücklich ungeprüfte Vorschau; keine Freigabe daraus |
| CAN XL bei 8 Byte | als `CAN_FD` und `CAN_FD_PHASE_ESTIMATE` ausgegeben | als `CAN_XL` und `GENERIC_ESTIMATE` gekennzeichnet |
| Fehlende Rate am Beispiel RS485 | 1.000.000 bit/s aus `CUSTOM` | kein Ersatzwert (`null`) |
| Config Builder | 100-Mbit/s-Ersatzwert im Code vorhanden | Ersatzwert entfernt |

**Einordnung der früheren Zahlen 114 und 97:** Der Audit vom 25.09. zählte Codezweige und Routing-Einträge mit Alias-Auflösung. Die direkte Produktprobe verwendete dagegen die unveränderten Katalog-IDs. `ros2` läuft so tatsächlich durch `GENERIC_ESTIMATE`, während nur `ROS_2` den speziellen Rechnerzweig erreicht: daher **115 statt 114**. Im Routing heißen zwei Tabellenschlüssel `SOME_IP` und `ROS_2`, während die Katalog-IDs `someip` und `ros2` heißen: daher **99 statt 97** bei rohem ID-Abgleich. Die ursprünglichen Zahlen sind als aliasbereinigte Bestandsaufnahme zu lesen, nicht als Ergebnis eines unmittelbaren Aufrufs mit jeder Katalog-ID. Die Alias-Differenz ist ein zusätzlicher Integrationsbefund.

Die 125 Einträge umfassen auch höhere Protokollschichten und direkte Signale. „Kein eigener Zeitplanzweig“ bedeutet nicht automatisch, dass ein vollständig bestätigter physischer Unterbau unmöglich wäre; es ist hier ein direkter Abdeckungsindikator.

## Belege und Grenzen

- [`product-probe.json`](20260925_src_bus_technology_gap_quickcheck_product-probe.json): lesende Python-Probe im laufenden Container `NetworkIS`; enthält alle generischen und nicht unmittelbar abgedeckten Katalog-IDs sowie die konkreten Rechenbeispiele.
- [`product-state.json`](20260925_src_bus_technology_gap_quickcheck_product-state.json): lesende HTTP-Antworten von `/api/build-info` und der vorhandenen Capacity-Analyse; keine Neuberechnung und keine Produktdatenmutation.
- [`checkout-probe.json`](20260925_src_bus_technology_gap_quickcheck_checkout-probe.json): dieselben Modellproben aus dem aktuellen lokalen Quellstand.
- Vorheriger [Vollständigkeits-Audit](../../../docs/BUS_TECHNOLOGY_COMPLETENESS_AUDIT_2026-09-25.md) und [Reparaturbericht](../../../docs/BUS_TECHNOLOGY_REPAIR_REPORT_2026-09-25.md).

Diese Diagnose ist kein Test aller 125 Technologien im echten Wizard, kein Neulauf der kumulativen Tool-Checker-Suite und kein positiver Produkt-Releasebeleg. Die Bereitstellung der Checkout-Reparatur bleibt durch die fünf dokumentierten Wizard-End-to-End-Blocker gesperrt.
