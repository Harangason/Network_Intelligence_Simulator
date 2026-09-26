# NIS: Device Classes, Direct I/O und Technologieprofile

**Stand:** 25.09.2026  
**Ergebnis:** Umsetzung im produktiven NIS bereitgestellt; Release-Gate `PASS`.  
**Bezugsdokument:** `NIS_DEVICE_CLASS_DIRECT_IO_TECHNOLOGY_MODEL.md` (vom Nutzer bereitgestellt). Dessen fachliche Vorgaben wurden als Anforderungen geprüft und in das kanonische NIS-Modell integriert.

## Kurzbefund

Der Katalog umfasst 125 Technologien. Eine Katalogregistrierung gilt weiterhin nicht als Kapazitäts- oder Zeitnachweis. Für CAN, CAN FD, LIN, Ethernet, I2C und SPI gibt es jetzt technologiespezifische Rechenzweige. GPIO, PWM, ADC und DAC sind als Direct I/O mit Buskapazität `NOT_APPLICABLE` ausgewiesen. Bei den übrigen 115 Technologien fehlt weiterhin ein belastbares Kapazitäts- beziehungsweise Zeitmodell; sie erhalten keine künstliche Freigabe durch generische Rahmenadapter.

Für 82 Technologien zeigt NIS bereits vorhandene Katalograten als **prüfpflichtige Vorschläge**. Für 42 Technologien fordert es geräteabhängige Angaben; für I2C bietet es Standard-Mode-Grenzen als Auswahlvorschlag an. Die Vorschläge sind `REVIEW_REQUIRED` und werden ohne Bestätigung weder zur technischen Evidenz noch zu einer stillen Rate. Die Zahlen beschreiben den Vorschlagstyp je Technologie, nicht 125 verifizierte Profile.

| Status im Katalog | Anzahl | Bedeutung |
| --- | ---: | --- |
| `MODEL_AVAILABLE` | 6 | Technologiespezifischer Berechnungszweig vorhanden; konkrete Nachweise benötigen bestätigte Parameter. |
| `NOT_APPLICABLE` | 4 | Direkte I/O-Leitung; klassische paketbasierte Buslast ist fachlich nicht anwendbar. |
| `MODEL_MISSING` | 115 | Kein belastbarer eigener Berechnungszweig; Kapazität und Timing bleiben `UNVERIFIED`. |

## Umgesetzte Änderungen

### Kanonisches Gerät und Verbindung

- `DeviceClassProfile` definiert die Klassen 0 bis 4, `DataComplexity` die Datenart und `ConnectionType` die Art der Verbindung. Eine Klasse erzwingt keine feste Bustechnologie.
- `TechnologyCandidateResolver` schlägt technisch passende Verbindungen anhand von Klasse, Datenkomplexität, Hardwarefähigkeiten, vorhandenen Schnittstellen, Distanz, Zyklus, Bandbreite und Topologie vor. Der Vorschlag ersetzt keine Geräte- oder Engineering-Entscheidung.
- `DirectSignalBinding` ist am kanonischen Signalmodell verankert. Direkte Signale werden über Hardware-Port und elektrische beziehungsweise zeitliche Angaben gebunden. Es entsteht keine künstliche Message oder TransportUnit.
- Die Wizard- und Assistant-Pfade verwenden die Geräteklassifikation und die bestehende TechnologyProfile-Registry. Für Direct I/O legt der Wizard eine direkte Signalbindung an. Die Validierung schützt die Signalzuordnung und weist fachlich unpassende Kombinationen aus.

### Direct I/O und echte serielle Busse

- GPIO, PWM und analoge Ein-/Ausgabe werden als Direct I/O behandelt. Die Buskapazität ist `NOT_APPLICABLE`, nicht `0 %` und nicht `UNVERIFIED`. Relevante Flanken-, Entprell-, Abtast-, PWM-, ADC-, DAC- und Treiberzeiten bleiben separat prüfbar und bei fehlenden Gerätedaten offen.
- I2C und SPI bleiben Kommunikationsbusse. Eigene Rechner verwenden die jeweiligen Transaktions-, Overhead- und Timingparameter. Ohne bestätigte Taktfrequenz und nötige gerätespezifische Parameter bleiben Kapazität und Timing `UNVERIFIED`; ein Katalogwert wird nicht unbemerkt eingesetzt.
- In Kapazitätsansicht und Signalmetriken werden direkte Verbindungen ohne erfundene Last angezeigt. Ein Projekt mit ausschließlich Direct I/O erhält keinen fingierten Fehler wegen fehlender Busrouten.

### Parameterherkunft und Wizard

- Vorschlagswerte tragen Herkunft und Prüfstatus. Ein I2C-Kandidat kann im Parameterformular erscheinen, bleibt aber `TECHNOLOGY_PROFILE_REVIEW_PROPOSAL` und ist ohne bestätigte Hardwaredaten kein Rechennachweis.
- Explizite Angaben aus einem Auftrag, einschließlich getrennter CAN-FD-Arbitrations- und Datenrate, CAN-, LIN- und Ethernet-Raten, bleiben für alle tatsächlich verwendeten Technologien erhalten. Sie werden nicht durch generische Standardraten überschrieben.
- Fehlt ein technologiespezifisches Modell, beendet der Preflight den Pfad als nachweispflichtig. Beispiel: Modbus RTU kann mit einem prüfbaren Rate-Vorschlag erscheinen, aber ohne eigenen deterministischen Modellzweig nicht als verifizierte Simulation freigegeben werden.

## Prüfungen und Ergebnisse

Die Regressionen decken Klassen 0 bis 4, Hardware- und Datenkomplexitätsfilter, Direct-I/O-Bindung ohne TransportUnit, `NOT_APPLICABLE` ohne künstliche Buslast, I2C/SPI mit und ohne Pflichtparameter sowie Wizard- und Kapazitätspfade ab. Die Tests laufen isoliert von der Produktdatenbank.

| Prüfung | Ergebnis |
| --- | --- |
| Frontend-Typprüfung | PASS |
| Frontend-Unit-Tests | 455 PASS |
| Backend-Tests | 2105 PASS, 2 übersprungen |
| Browser-E2E | 69 PASS |
| Produktions-Build | PASS |
| Kleine und große HTTP-Wizard-Prüfung | PASS; großer Pfad mit 552 Knoten und 766 bewerteten Routen |
| Release-Gate | `PASS`, alle sieben Checks Exitcode 0 |

Die maschinenlesbare Quittung liegt unter `backend/test-output/release-gates/ff5eb0f72d07/receipt.json`. Der geprüfte Quellstand hat SHA-256 `a115c3c459c867c8994457424af250192ef863cb0f930b55f6f288c7d1853ddf`. Das geprüfte und ausgerollte Image hat ID `sha256:696e17932fab553791e37984636d02e508491efff7ee503a8ab36bfcdaf023ff` und Build-ID `a115c3c459c8`.

Nach dem Start antwortete `/api/ready` mit `status=ready`, `database=available` und `storage=available`. `/api/build-info` meldete Build `a115c3c459c8`; `docker inspect NetworkIS` bestätigte dieselbe Image-ID wie die PASS-Quittung. Der Start erfolgte über `start-networkis.ps1 -ReleaseReceipt` mit genau dieser Quittung.

## Fachliche Grenzen und nächste Arbeit

1. **115 Technologien:** Für diese existieren weiterhin keine technologiespezifischen Kapazitäts- oder Zeitmodelle. Ein üblicher Ratenbereich kann die Auswahl erleichtern, ersetzt aber nicht Protokolloverhead, Arbitration, PHY, Gerätegrenzen und Zeitplan. NIS zeigt `MODEL_MISSING` beziehungsweise `UNVERIFIED` und sperrt die Freigabe eines unbewiesenen Nachweises.
2. **42 geräteabhängige Profile:** Hier sind ohne Datenblatt oder bestätigte Gerätekonfiguration keine seriösen Standardraten hinterlegbar. NIS fordert die konkreten Werte an.
3. **Direct-I/O-Timing:** `NOT_APPLICABLE` gilt nur für paketbasierte Buslast. Ein funktionaler Reaktionszeitnachweis kann weiterhin Abtastung, Entprellung, Signalweg und Treiberlatenz erfordern.
4. **I2C/SPI:** Ein vorhandener Rechenzweig allein macht kein konkretes Projekt `VERIFIED`. Die projektspezifischen Master-, Adress-, Chip-Select-, Clock-Stretching-, Takt- und Transferangaben müssen bestätigt werden.
5. **Testumfang:** Das Release-Gate beweist die genannten automatisierten Pfade. Es ersetzt keine gerätespezifische Messung und keinen Nachweis für jede der 125 Technologien.

Die I2C-Grenzwerte stammen aus der [NXP-I²C-Spezifikation UM10204](https://www.nxp.com/docs/en/user-guide/UM10204.pdf). Die [Modbus Serial Line Specification](https://www.modbus.org/docs/Modbus_over_serial_line_V1_02.pdf) nennt unterstützte Standard-Übertragungsraten, aber keinen universellen Wert für jede Anlage; vorhandene Katalogkandidaten bleiben daher unbestätigt.

## Zugriff

- Lokal: <http://127.0.0.1:13500>
- VPN/LAN: <http://192.168.178.10:13500>

Der produktive Dienst läuft mit der getesteten Version. Vorhandene produktive Projekte wurden für diesen Release nicht als Testdaten verwendet.
