# Prüfung aller katalogisierten Kommunikationstechnologien (25.09.2026)

## Auftrag und Prüfumfang

Geprüft wurde der Quellstand `ef08e18d` des kanonischen Projekts `I:\PycharmProjects\My_first_Network_Simulator`. Der Auftrag ist eine Bestandsaufnahme der Auffälligkeit „registrierter Bustyp, aber fehlende oder irreführende Kapazitäts- und Zeitbasis“. Es wurden keine Produktdaten, Technologieverträge oder Implementierungen geändert. Die vollständige Einzelmatrix steht in [BUS_TECHNOLOGY_COMPLETENESS_MATRIX_2026-09-25.md](BUS_TECHNOLOGY_COMPLETENESS_MATRIX_2026-09-25.md).

Die Prüfung trennt Katalogeintrag, ausführbaren generischen Adapter, explizite physische Beschreibung, Routing-Kapazitätseintrag, Rahmenschätzung und deterministischen Zeitplan. Die 125 Katalogeinträge sind nicht alle physische Busse: Es gibt auch Protokollschichten, Funktechnologien, Sicherheitsprofile und direkte I/O-Signale. Ein fehlender eigener PHY-Eintrag ist für eine Anwendungsschicht nicht automatisch ein Fehler, wenn der bestätigte Transport-Stack vollständig ausgewertet wird. Die vorliegende Matrix misst daher **direkte** Profilabdeckung; sie ist kein Konformitätszertifikat.

## Ergebnis in Zahlen

| Prüfmerkmal | Anzahl von 125 | Einordnung |
| --- | ---: | --- |
| Katalogstatus `IMPLEMENTED` | 15 | Status wird in `catalog.py:_status` zugewiesen; er beschreibt nicht die gesamte Engineering-Kette. |
| `PARTIAL` / `EXPERIMENTAL` / `LEGACY` / `PLANNED` | 53 / 30 / 5 / 22 | Auch die ersten drei erhalten generische ausführbare Registry-Komponenten. |
| Explizites Rate-Modell in `TECHNOLOGY_SEMANTICS` | 8 | Sonst wird aus Katalog-Bitrate ein generisches Ein-Bitrate-Modell oder „inherited/not applicable“. |
| Mechanismus-Metadaten | 13 | Metadaten allein bedeuten keine simulierte oder validierte Protokollmechanik. |
| Direkter PHY-Eintrag oder Alias | 16 | Fehlende PHY-Profile werden bei physischer Realisierung als Review ausgewiesen. |
| Direkter Routing-Kapazitätsschlüssel oder GPIO/PWM-Ausnahme | 28 | 97 Einträge besitzen keinen solchen Schlüssel; Anwendungsschichten können teilweise auf einen Basistransport aufgelöst werden. |
| Eigener Zweig in `estimate_frame` | 11 | CAN XL ist darin ein Sonderfall: Es wird mit CAN-FD-Formel berechnet und als `CAN_FD` zurückgegeben. |
| Eigener deterministischer `bus_schedule`-Zweig | 4 | CAN, CAN FD, LIN, Ethernet; weitere Technologien enden dort mit `UNVERIFIED`. |

Die Zählung stammt aus einer AST-Auswertung der literalen Katalog- und Routing-Tabellen. Die Formel- und Zeitplanabdeckung wurde zusätzlich am tatsächlichen Codepfad kontrolliert. Die 125 Einzelzeilen sind in der Matrix nach Katalogreihenfolge aufgeführt.

## Bestätigte Fehlerpfade

### P0 – Fremde Ersatzraten und scheinbare Kapazitätszahlen

`routing/validation.py:16-47` führt eine zweite, handgepflegte Kapazitätstabelle. Ein nicht erfasster Routing-Transport erzeugt bei `:528-529` zwar `CUSTOM_PROTOCOL`, wird bei `:654`, `:657` und `:699` aber mit dem `CUSTOM`-Wert von 1 Mbit/s beziehungsweise dessen Payload-Grenze weitergerechnet. `capacity/service.py:71-90` übernimmt denselben Fallback. `routing/config_builder.py:184` enthält zusätzlich einen Ersatzwert von 100 Mbit/s. Das widerspricht dem Vertrag „TechnologyProfile als Single Source of Truth“ und kann eine plausible, technisch unbelegte Auslastung erzeugen. Ein vorhandener Tabellenwert ist ebenfalls nur ein Nennwert, kein bestätigter Geräte- oder Netzwerknachweis.

Die separate Planungsroutine `intelligence/network_planning.py:_candidate_route_load` berechnet Kandidaten aus dieser Tabelle und `estimate_frame`; sie sperrt generische Schätzungen nicht grundsätzlich. Dadurch können Technologien mit generischem Rahmenmodell in Optimierungsvorschlägen numerisch verglichen werden. Zu prüfen ist jeder Aufrufer, der solche Vorschläge als entscheidungsfähig anzeigt.

### P0 – Generisches Rahmenmodell für fast alle Bustypen

`capacity/calculators.py:32-78` hat spezifische Zweige für CAN, CAN FD, CAN XL, Ethernet/SOME-IP/UDP/TCP/DDS/ROS 2, LIN und FlexRay. Alle übrigen Technologien erhalten `GENERIC_ESTIMATE`: 24 Byte Overhead und, ohne mitgelieferte Rate, 1 Mbit/s. Die Kapazitätsausgabe kennzeichnet dies nur als `INFO` (`capacity/service.py:866-875`); route- und netzwerkbezogene Lastzahlen werden vorher dennoch gebildet. Der nachgelagerte Zeitplan ist meist `UNVERIFIED`, und `timing_verified` wird korrekt erst bei einem passenden Zeitplan gesetzt (`capacity/service.py:565-646`). Laststatus und Timingstatus müssen dennoch konsistent als nicht belastbar erkennbar sein.

Eine kleine Verhaltensprobe ohne Datenbank ergab bei jeweils 8 Byte und leeren Parametern für `ETHERCAT`, `PROFINET`, `MODBUS_RTU`, `I2C`, `SPI`, `RS485`, `PWM` und `GPIO` denselben Wert `GENERIC_ESTIMATE`, 0,256 ms. Das ist kein technologiespezifischer Nachweis. `CAN_XL` ergab `CAN_FD_PHASE_ESTIMATE` und den Ausgabenamen `CAN_FD`.

### P0 – Katalogstatus und ausführbare Registry können Reife suggerieren

`catalog.py:73-109` markiert 15 Technologien als `IMPLEMENTED`. `core/registry.py:119-135` registriert für alle `IMPLEMENTED`, `PARTIAL`, `EXPERIMENTAL` und `LEGACY` dieselben Basisklassen, darunter `TechnologyTransportGenerator`, `TechnologyTimingModel`, `TechnologyLoadCalculator` und `IdentityEncoder/Decoder`. Die Encoder und Decoder kopieren Bytes unverändert (`core/components.py:153-160`); die generische Zeitfunktion serialisiert Payload plus Profil-Overhead bei Default-Bitrate (`:126-149`). Die Auflösung als „ausführbar“ beweist daher keine protokollspezifische Kodierung, Arbitrierung oder Ende-zu-Ende-Zeitgrenze. Das betrifft sogar mehrere `IMPLEMENTED`-Einträge, etwa Profinet, EtherCAT und Modbus RTU.

### P1 – Physische Evidenz und direkte I/O

`core/physical.py:87-125` beschreibt sieben eigene PHYs plus neun Aliase. Für I2C und SPI sind Leitungen beziehungsweise Chip-Select-Ressourcen teilweise modelliert; gerätespezifische Adresse, Master, Clock-Stretching und bestätigter Transfer/Takt fehlen ohne Nutzereingabe. `capacity/dimensioning.py:22-57` bietet dafür, entsprechend der erteilten Konzeptentscheidung, prüfbare Hardwareprofilfelder. PWM und GPIO sind direkte Signalleitungen, keine paketbasierten Busse; der Zeitplan markiert sie `UNVERIFIED` und die Kapazitätsansicht als nicht anwendbar. Für UART, RS232/422/485, 1-Wire, USB, PCIe, MIPI, LVDS, ADC/DAC sowie die übrigen Feldbus-, Funk- und Bahnprofile gibt es kein gleichwertig ausformuliertes gerätespezifisches Review in `LOCAL_EVIDENCE_FIELDS`.

### P1 – Routing-/Wizard-Abdeckung weicht vom Katalog ab

Die Routing-Tabelle erfasst nur 26 Katalog-IDs direkt; mit den gesonderten GPIO/PWM-Ausnahmen sind es 28. `physical_route_technology` kann für einzelne Anwendungsschichten über den Stack auf CAN/Ethernet zurückgehen. Das ersetzt keine vollständige Validierung der oberen Schicht. Andere Katalogtechnologien erhalten in der Routenprüfung `CUSTOM_PROTOCOL`; zugleich akzeptiert `proposal_service.py:196-207` bei Network-Proposals jede registrierte Technologie auch ohne Routing-Kapazität. `wizard_generation.py:_network_protocol` gibt für fehlende Tabellenschlüssel einen registrierten Topologiebus zurück. Die Produktkette kann dadurch ein Netzwerkobjekt besitzen, dessen Kapazitäts- und Zeitnachweis nicht technologiespezifisch ist. Unbekannte IDs werden im Wizard dagegen ausdrücklich abgewiesen (`wizard_generation.py:_topology_bus`).

## Betroffene Gruppen und Priorisierung

1. **Schon als `IMPLEMENTED` bezeichnet, aber ohne eigenen deterministischen Zeitplan:** `ip`, `udp`, `tcp`, `canopen`, `someip`, `profinet`, `ethercat`, `modbus_tcp`, `modbus_rtu`, `dds`, `ros2`. Bei Protokollschichten muss der physische Unterbau samt schichtspezifischem Overhead, Queue und Mechanismen geprüft werden; bloßes Herunterreichen auf Ethernet oder CAN ist kein vollständiger Nachweis.
2. **Vorhandener Tabellenwert, aber generischer Rahmenrechner:** unter anderem `ethercat`, `profinet`, `modbus_tcp`, `modbus_rtu`, `opc_ua`, `io_link`, `uart`, `i2c`, `spi`, `pcie`, `mil_std_1553`, `mvb`, `wtb`, `etb`, `trdp`. Diese Gruppe hat besonders hohes Risiko für glaubwürdig wirkende Zahlen.
3. **Katalogisiert, aber ohne direkten Routing-Kapazitätsschlüssel:** 97 Einträge; Einzelheiten stehen in der CSV. Dazu gehören viele weitere physische/industrielle Typen (`profibus_dp`, `profibus_pa`, `ethernet_ip`, `rs485`, `i3c`, `one_wire`, `usb`, `nmea2000`, `bacnet_mstp`, `knx_tp`, `dali`, `m_bus`, `hart`, `foundation_fieldbus_h1`, `spacewire`) und höhere Schichten. Die fachliche Behandlung muss pro Schicht/Stack festgelegt werden.
4. **Direkte Signale:** `gpio`, `pwm`, `adc`, `dac` sollten nicht mit paketbasierter Buslast gleichgesetzt werden. GPIO/PWM besitzen bereits eine Ausnahme; ADC/DAC haben derzeit keine entsprechende direkte Ausnahmeregel in der Routing-Tabelle.
5. **Planned:** 22 Katalogeinträge sind ausdrücklich nicht als ausführbar markiert. Für sie ist eine sichtbare `NOT_SUPPORTED`/Datenlücke fachlich angemessener als die `CUSTOM`-Rechnung.

## Empfohlene Fehlerbehebung, ohne hier eine Konzeptänderung vorzunehmen

1. Kapazitätsquelle vereinheitlichen: `PROTOCOL_CAPACITY`, 1-Mbit/s- und 100-Mbit/s-Ersatzwerte aus Routing, Capacity und Config Builder entfernen oder strikt als nicht freigabefähige Vorschau kennzeichnen. Für jeden physischen Transport aus bestätigtem TechnologyProfile, konkretem Port und Netzwerkparametern auflösen; fehlende Evidenz ergibt `UNVERIFIED` statt numerischer Freigabe.
2. Zwei getrennte Abdeckungsmerkmale führen: „registriert/generierbar“ und „Kapazitäts-/Zeitmodell belastbar“. `IMPLEMENTED` darf nicht automatisch als letzteres erscheinen. Für `PLANNED` keinen generischen Ausführungspfad zulassen.
3. Profilweise Modelle ergänzen, beginnend mit in realen Projekten verwendeten Technologien. Bei I2C/SPI und weiteren lokalen Schnittstellen gerätespezifische Hardwareprofil-Vorschläge bis zur Bestätigung als ungeprüft zeigen; für PWM/GPIO/ADC/DAC Signalreaktionszeiten statt Buskapazität prüfen. Für EtherCAT/Profinet/Modbus/IO-Link die zugehörigen bestätigten Betriebsparameter und Mechanismen abfragen.
4. Tests als Katalogmatrix ausführen: jede ID durch Profil → Wizard → Routing → Rahmenmodell → Zeitplan → Preflight; dabei fehlende Evidenz, gemischte Stacks und die Anzeige prüfen. Insbesondere `CAN_XL` darf nicht als CAN FD ausgegeben werden. SQL-Tests ausschließlich mit `scripts/run-isolated-tests.py`; Produktdeployment nur nach `scripts/run-release-gate.py` mit PASS-Beleg und exakt getestetem Image.

Die Auswahl der fachlichen Modelle und Pflichtfelder pro Technologie ist eine Konzeptentscheidung. Wegen der früheren Nutzeranweisung „Bei Konzeptänderungen Rückfrage stellen“ enthält diese Prüfung bewusst keine Änderung solcher Regeln.

## Nachweisgrenzen

Es handelt sich um eine Quellcodeprüfung der allgemeinen Verarbeitungskette und eine kleine isolierte Funktionsprobe von `estimate_frame`, nicht um 125 vollständige Produkt- oder Hardwaretests. Die bestehende Testdatei `test_technology_profile_semantics.py` prüft ausgewählte Profile, nicht die gesamte Matrix. Ein Lauf des allgemeinen Project-Scanner-Skripts wurde begonnen und wegen des Umfangs der Laufzeit-/Testartefakte ohne neue Ausgabe beendet; die gezielte AST- und Codeprüfung sowie die CSV-Matrix sind davon unabhängig. PEP 8 wurde nicht geprüft. Im aktuellen Auftrag gab es keinen Release-Gate-Lauf und keine Produktdeploymentänderung.
