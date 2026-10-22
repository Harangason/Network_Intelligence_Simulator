# D – Industrieautomation, Produktion und Robotik

**Anzahl Profile:** 10

## Index

| Nr. | Systemprofil |
|---:|---|
| 054 | Kollaborativer Roboterarm |
| 055 | Industrielle Roboterzelle |
| 056 | Mobiler Service-Roboter mit Greifarm |
| 057 | AGV/AMR-Flottensteuerung |
| 058 | CNC-Bearbeitungszentrum |
| 059 | Verpackungs- und Abfülllinie |
| 060 | Automatisiertes Hochregallager |
| 061 | Prozessleitsystem mit Safety Instrumented System |
| 062 | Digitale Fabriklinie / Montagewerk |
| 063 | Machine-Vision-Qualitätsprüfung |

---

## 054. Kollaborativer Roboterarm

### 1. Zweck und Systemübersicht
Flexible Montage und Handhabung in unmittelbarer Mensch-Roboter-Kollaboration.

### 2. Systemkontext und Grenze
Das System wird zusammen mit seinen Bedienern, Nutzern, physischen Umgebungsbedingungen, Energie-/Medienquellen, externen Leit- und Informationssystemen, Wartungsorganisationen sowie nachgelagerten Verbrauchern oder Prozessen modelliert. Externe Akteure bleiben außerhalb der Systemgrenze, ihre Erwartungen, Daten, Befehle und Fehlermodi werden jedoch als Schnittstellenanforderungen erfasst.

### 3. Architektur
Gelenkaktuatoren, Encoder, Kraft-/Momentensensorik, Sicherheitssteuerung, Motion Controller, Teach Pendant und Endeffektor.

Die Architektur ist in physische Komponenten, Steuerungs-/Rechenkomponenten, Softwaredienste, Kommunikations- und Energiepfade sowie Bedien-, Wartungs- und Backendanteile zu zerlegen. Redundanz, Verantwortlichkeit, Diagnose, Konfiguration und Freigabestatus werden je Element geführt.

### 4. Funktionsbeschreibung
- Bahnplanung, Kraftregelung, Speed/Separation Monitoring, Power and Force Limiting, Handführung, Tool Change und Diagnose..

### 5. Schnittstellen und Daten
Industrial Ethernet, Safety I/O, Werkzeugbus, Vision, MES/PLC und Wartung.

Für jede Schnittstelle werden Quelle, Senke, Richtung, Protokoll/Medium, Einheit, Datenqualität, Zeitverhalten, Grenzwerte, Fehlerreaktion, Security-Klasse, Diagnose und Variantenbezug definiert.

### 6. Betriebsmodi
- **Teach**
- **Auto**
- **Collaborative**
- **Reduced Speed**
- **Protective Stop**
- **Emergency Stop und Service.**

Moduswechsel besitzen Auslöser, Guard-Bedingungen, Aktionen, Timeout, Abbruch-/Rollback-Regeln und erlaubte Folge-/Fallbackzustände.

### 7. Referenzanforderungen
- **REQ-054-SYS-001:** Das System muss seine Mission erfüllen: Flexible Montage und Handhabung in unmittelbarer Mensch-Roboter-Kollaboration.
- **REQ-054-ARC-001:** Die Architektur muss die vorgesehenen Elemente und Verantwortlichkeiten abbilden: Gelenkaktuatoren, Encoder, Kraft-/Momentensensorik, Sicherheitssteuerung, Motion Controller, Teach Pendant und Endeffektor.
- **REQ-054-FUN-001:** Die folgenden Kernfunktionen müssen in klar definierten Zuständen und mit nachvollziehbaren Ein-/Ausgaben bereitgestellt werden: Bahnplanung, Kraftregelung, Speed/Separation Monitoring, Power and Force Limiting, Handführung, Tool Change und Diagnose.
- **REQ-054-IF-001:** Die Schnittstellen müssen Datenformat, Richtung, Aktualität, Fehlerverhalten, Zugriffsrecht und Version für folgende Kopplungen definieren: Industrial Ethernet, Safety I/O, Werkzeugbus, Vision, MES/PLC und Wartung.
- **REQ-054-MODE-001:** Das System muss mindestens die genannten Betriebs- und Fehlerzustände beherrschen: Teach, Auto, Collaborative, Reduced Speed, Protective Stop, Emergency Stop und Service.
- **REQ-054-SAFE-001:** Die zentralen Gefährdungen müssen erkannt, verhindert oder auf ein akzeptiertes Restrisiko reduziert werden: Quetschen, unerwartete Bewegung, Werkzeugverlust, fehlerhafte Sicherheitszone und Überlast.
- **REQ-054-DIAG-001:** Fehler, Grenzwertverletzungen, Qualitätsverluste und Konfigurationsabweichungen müssen erkannt, zeitgestempelt und diagnostizierbar gespeichert werden.
- **REQ-054-SEC-001:** Identitäten, Rollen, Kommunikation, Softwarestände, Konfigurationen und Fernzugriffe müssen gegen unautorisierte Nutzung und Veränderung abgesichert sein.
- **REQ-054-CFG-001:** Hardware-, Software-, Parameter-, Rezept-/Missions- und Schnittstellenversionen müssen eindeutig konfigurationsgeführt und freigegeben werden.
- **REQ-054-VER-001:** Jede sicherheits-, qualitäts- oder missionskritische Anforderung muss mit mindestens einem Testfall und einer nachprüfbaren Evidenz verknüpft sein.
- **REQ-054-REC-001:** Nach Teilfehlern oder Neustart muss das System in einen definierten, konsistenten und nachvollziehbaren Zustand übergehen.

### 8. Safety, Security, Qualität und Betrieb
Die Sicherheits- und Betriebsargumentation behandelt insbesondere: Quetschen, unerwartete Bewegung, Werkzeugverlust, fehlerhafte Sicherheitszone und Überlast.. Dazu gehören unabhängige Schutzebenen, sichere Zustände, Degradation, Alarmpriorität, Rollen-/Rechtekonzept, Änderungsfreigabe, sichere Fernwartung, Backup/Recovery, Audit und Lifecycle-Nachweise.

### 9. Verifikation und Testfälle
- **TC-054-01:** Kontakt mit Bediener. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-054-02:** Sicherheitslaser verletzt. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-054-03:** Encoderabweichung. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-054-04:** Werkzeug fällt aus. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-054-05:** Netzwerkkommando verspätet. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-054-06:** Wiederanlauf nach Schutzstopp. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-COMMON-01:** Neustart oder Teilwiederanlauf mit inkonsistentem Zwischenzustand; das System muss in einen definierten Recovery-Zustand wechseln.
- **TC-COMMON-02:** Unautorisierte Änderung eines kritischen Parameters oder Softwarestands; Änderung wird verhindert, alarmiert und protokolliert.

### 10. Varianten, Erweiterungen und Ergebnisartefakte
**Erweiterungen:** KI-Griffplanung, mobile Basis, digitale Arbeitszelle und automatische Kalibrierung.

Vollständige Ergebnisartefakte sind Systemkontext, Stakeholder-/Use-Case-Modell, Anforderungen, Funktions-/Zustandsmodelle, physische und logische Architektur, Schnittstellen-/Signalkatalog, Risiko-/Safety-/Security-Analysen, Betriebs- und Wartungskonzept, Testkatalog, Evidenzen, Konfigurations- und Releaseakte.

## 055. Industrielle Roboterzelle

### 1. Zweck und Systemübersicht
Hochgeschwindigkeits-Schweißen, Fügen, Lackieren oder Handling in abgegrenzter Produktionszelle.

### 2. Systemkontext und Grenze
Das System wird zusammen mit seinen Bedienern, Nutzern, physischen Umgebungsbedingungen, Energie-/Medienquellen, externen Leit- und Informationssystemen, Wartungsorganisationen sowie nachgelagerten Verbrauchern oder Prozessen modelliert. Externe Akteure bleiben außerhalb der Systemgrenze, ihre Erwartungen, Daten, Befehle und Fehlermodi werden jedoch als Schnittstellenanforderungen erfasst.

### 3. Architektur
Ein oder mehrere Industrieroboter, PLC, Safety PLC, Schutzzaun/Scanner, Werkzeugtechnik, Vision, Fördertechnik und HMI.

Die Architektur ist in physische Komponenten, Steuerungs-/Rechenkomponenten, Softwaredienste, Kommunikations- und Energiepfade sowie Bedien-, Wartungs- und Backendanteile zu zerlegen. Redundanz, Verantwortlichkeit, Diagnose, Konfiguration und Freigabestatus werden je Element geführt.

### 4. Funktionsbeschreibung
- Taktablauf, Bahnsteuerung, Werkzeugkoordination, Materialfluss, Sicherheitsverriegelung, Qualitätsdaten und Störungsbehandlung..

### 5. Schnittstellen und Daten
PROFINET/EtherCAT/OPC UA, Safety I/O, MES, Qualitätsdatenbank, Energie/Medien.

Für jede Schnittstelle werden Quelle, Senke, Richtung, Protokoll/Medium, Einheit, Datenqualität, Zeitverhalten, Grenzwerte, Fehlerreaktion, Security-Klasse, Diagnose und Variantenbezug definiert.

### 6. Betriebsmodi
- **Automatik**
- **Einrichten**
- **Handbetrieb**
- **Wartung**
- **Störung**
- **Not-Halt und Recovery.**

Moduswechsel besitzen Auslöser, Guard-Bedingungen, Aktionen, Timeout, Abbruch-/Rollback-Regeln und erlaubte Folge-/Fallbackzustände.

### 7. Referenzanforderungen
- **REQ-055-SYS-001:** Das System muss seine Mission erfüllen: Hochgeschwindigkeits-Schweißen, Fügen, Lackieren oder Handling in abgegrenzter Produktionszelle.
- **REQ-055-ARC-001:** Die Architektur muss die vorgesehenen Elemente und Verantwortlichkeiten abbilden: Ein oder mehrere Industrieroboter, PLC, Safety PLC, Schutzzaun/Scanner, Werkzeugtechnik, Vision, Fördertechnik und HMI.
- **REQ-055-FUN-001:** Die folgenden Kernfunktionen müssen in klar definierten Zuständen und mit nachvollziehbaren Ein-/Ausgaben bereitgestellt werden: Taktablauf, Bahnsteuerung, Werkzeugkoordination, Materialfluss, Sicherheitsverriegelung, Qualitätsdaten und Störungsbehandlung.
- **REQ-055-IF-001:** Die Schnittstellen müssen Datenformat, Richtung, Aktualität, Fehlerverhalten, Zugriffsrecht und Version für folgende Kopplungen definieren: PROFINET/EtherCAT/OPC UA, Safety I/O, MES, Qualitätsdatenbank, Energie/Medien.
- **REQ-055-MODE-001:** Das System muss mindestens die genannten Betriebs- und Fehlerzustände beherrschen: Automatik, Einrichten, Handbetrieb, Wartung, Störung, Not-Halt und Recovery.
- **REQ-055-SAFE-001:** Die zentralen Gefährdungen müssen erkannt, verhindert oder auf ein akzeptiertes Restrisiko reduziert werden: Zutritt während Automatik, Kollision, Schweiß-/Lasergefahr, Werkstückverlust und falsches Programm.
- **REQ-055-DIAG-001:** Fehler, Grenzwertverletzungen, Qualitätsverluste und Konfigurationsabweichungen müssen erkannt, zeitgestempelt und diagnostizierbar gespeichert werden.
- **REQ-055-SEC-001:** Identitäten, Rollen, Kommunikation, Softwarestände, Konfigurationen und Fernzugriffe müssen gegen unautorisierte Nutzung und Veränderung abgesichert sein.
- **REQ-055-CFG-001:** Hardware-, Software-, Parameter-, Rezept-/Missions- und Schnittstellenversionen müssen eindeutig konfigurationsgeführt und freigegeben werden.
- **REQ-055-VER-001:** Jede sicherheits-, qualitäts- oder missionskritische Anforderung muss mit mindestens einem Testfall und einer nachprüfbaren Evidenz verknüpft sein.
- **REQ-055-REC-001:** Nach Teilfehlern oder Neustart muss das System in einen definierten, konsistenten und nachvollziehbaren Zustand übergehen.

### 8. Safety, Security, Qualität und Betrieb
Die Sicherheits- und Betriebsargumentation behandelt insbesondere: Zutritt während Automatik, Kollision, Schweiß-/Lasergefahr, Werkstückverlust und falsches Programm.. Dazu gehören unabhängige Schutzebenen, sichere Zustände, Degradation, Alarmpriorität, Rollen-/Rechtekonzept, Änderungsfreigabe, sichere Fernwartung, Backup/Recovery, Audit und Lifecycle-Nachweise.

### 9. Verifikation und Testfälle
- **TC-055-01:** Schutztür geöffnet. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-055-02:** Roboter kollidiert mit Vorrichtung. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-055-03:** Falsches Rezept geladen. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-055-04:** Druckluft fällt aus. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-055-05:** Vision findet Bauteil nicht. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-055-06:** Safety-PLC-Kanalfehler. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-COMMON-01:** Neustart oder Teilwiederanlauf mit inkonsistentem Zwischenzustand; das System muss in einen definierten Recovery-Zustand wechseln.
- **TC-COMMON-02:** Unautorisierte Änderung eines kritischen Parameters oder Softwarestands; Änderung wird verhindert, alarmiert und protokolliert.

### 10. Varianten, Erweiterungen und Ergebnisartefakte
**Erweiterungen:** Adaptive Taktoptimierung, Offline Programming, virtuelle Inbetriebnahme und Predictive Maintenance.

Vollständige Ergebnisartefakte sind Systemkontext, Stakeholder-/Use-Case-Modell, Anforderungen, Funktions-/Zustandsmodelle, physische und logische Architektur, Schnittstellen-/Signalkatalog, Risiko-/Safety-/Security-Analysen, Betriebs- und Wartungskonzept, Testkatalog, Evidenzen, Konfigurations- und Releaseakte.

## 056. Mobiler Service-Roboter mit Greifarm

### 1. Zweck und Systemübersicht
Autonome Navigation, Objekterkennung, Greifen und Transport in Indoor- und Light-Outdoor-Umgebungen.

### 2. Systemkontext und Grenze
Das System wird zusammen mit seinen Bedienern, Nutzern, physischen Umgebungsbedingungen, Energie-/Medienquellen, externen Leit- und Informationssystemen, Wartungsorganisationen sowie nachgelagerten Verbrauchern oder Prozessen modelliert. Externe Akteure bleiben außerhalb der Systemgrenze, ihre Erwartungen, Daten, Befehle und Fehlermodi werden jedoch als Schnittstellenanforderungen erfasst.

### 3. Architektur
Mobile Basis, LiDAR/Kameras/Ultraschall, IMU/Encoder, Hauptrechner, Echtzeitcontroller, Greifarm, BMS und Funk.

Die Architektur ist in physische Komponenten, Steuerungs-/Rechenkomponenten, Softwaredienste, Kommunikations- und Energiepfade sowie Bedien-, Wartungs- und Backendanteile zu zerlegen. Redundanz, Verantwortlichkeit, Diagnose, Konfiguration und Freigabestatus werden je Element geführt.

### 4. Funktionsbeschreibung
- SLAM, Pfadplanung, Hindernisvermeidung, Docking, Objektlokalisierung, Armplanung, Greifen, Teleoperation und Fehlermanagement..

### 5. Schnittstellen und Daten
ROS2-ähnliche Middleware, CAN/UART/I²C, Web-HMI, Ladebasis, Flottenmanager und Diagnose.

Für jede Schnittstelle werden Quelle, Senke, Richtung, Protokoll/Medium, Einheit, Datenqualität, Zeitverhalten, Grenzwerte, Fehlerreaktion, Security-Klasse, Diagnose und Variantenbezug definiert.

### 6. Betriebsmodi
- **Autonom**
- **Teleoperation**
- **Manipulation**
- **Docking/Laden**
- **Diagnose**
- **Protective Stop und Emergency Stop.**

Moduswechsel besitzen Auslöser, Guard-Bedingungen, Aktionen, Timeout, Abbruch-/Rollback-Regeln und erlaubte Folge-/Fallbackzustände.

### 7. Referenzanforderungen
- **REQ-056-SYS-001:** Das System muss seine Mission erfüllen: Autonome Navigation, Objekterkennung, Greifen und Transport in Indoor- und Light-Outdoor-Umgebungen.
- **REQ-056-ARC-001:** Die Architektur muss die vorgesehenen Elemente und Verantwortlichkeiten abbilden: Mobile Basis, LiDAR/Kameras/Ultraschall, IMU/Encoder, Hauptrechner, Echtzeitcontroller, Greifarm, BMS und Funk.
- **REQ-056-FUN-001:** Die folgenden Kernfunktionen müssen in klar definierten Zuständen und mit nachvollziehbaren Ein-/Ausgaben bereitgestellt werden: SLAM, Pfadplanung, Hindernisvermeidung, Docking, Objektlokalisierung, Armplanung, Greifen, Teleoperation und Fehlermanagement.
- **REQ-056-IF-001:** Die Schnittstellen müssen Datenformat, Richtung, Aktualität, Fehlerverhalten, Zugriffsrecht und Version für folgende Kopplungen definieren: ROS2-ähnliche Middleware, CAN/UART/I²C, Web-HMI, Ladebasis, Flottenmanager und Diagnose.
- **REQ-056-MODE-001:** Das System muss mindestens die genannten Betriebs- und Fehlerzustände beherrschen: Autonom, Teleoperation, Manipulation, Docking/Laden, Diagnose, Protective Stop und Emergency Stop.
- **REQ-056-SAFE-001:** Die zentralen Gefährdungen müssen erkannt, verhindert oder auf ein akzeptiertes Restrisiko reduziert werden: Kollision, Umkippen, Quetschen am Arm, verlorenes Objekt, Sensorblindheit und Batteriestörung.
- **REQ-056-DIAG-001:** Fehler, Grenzwertverletzungen, Qualitätsverluste und Konfigurationsabweichungen müssen erkannt, zeitgestempelt und diagnostizierbar gespeichert werden.
- **REQ-056-SEC-001:** Identitäten, Rollen, Kommunikation, Softwarestände, Konfigurationen und Fernzugriffe müssen gegen unautorisierte Nutzung und Veränderung abgesichert sein.
- **REQ-056-CFG-001:** Hardware-, Software-, Parameter-, Rezept-/Missions- und Schnittstellenversionen müssen eindeutig konfigurationsgeführt und freigegeben werden.
- **REQ-056-VER-001:** Jede sicherheits-, qualitäts- oder missionskritische Anforderung muss mit mindestens einem Testfall und einer nachprüfbaren Evidenz verknüpft sein.
- **REQ-056-REC-001:** Nach Teilfehlern oder Neustart muss das System in einen definierten, konsistenten und nachvollziehbaren Zustand übergehen.

### 8. Safety, Security, Qualität und Betrieb
Die Sicherheits- und Betriebsargumentation behandelt insbesondere: Kollision, Umkippen, Quetschen am Arm, verlorenes Objekt, Sensorblindheit und Batteriestörung.. Dazu gehören unabhängige Schutzebenen, sichere Zustände, Degradation, Alarmpriorität, Rollen-/Rechtekonzept, Änderungsfreigabe, sichere Fernwartung, Backup/Recovery, Audit und Lifecycle-Nachweise.

### 9. Verifikation und Testfälle
- **TC-056-01:** Navigation durch dynamische Hindernisse. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-056-02:** Objekt mit definierter Masse greifen. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-056-03:** LiDAR fällt aus. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-056-04:** WLAN bricht ab. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-056-05:** Dockingkontakt fehlerhaft. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-056-06:** Arm überlastet. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-COMMON-01:** Neustart oder Teilwiederanlauf mit inkonsistentem Zwischenzustand; das System muss in einen definierten Recovery-Zustand wechseln.
- **TC-COMMON-02:** Unautorisierte Änderung eines kritischen Parameters oder Softwarestands; Änderung wird verhindert, alarmiert und protokolliert.

### 10. Varianten, Erweiterungen und Ergebnisartefakte
**Erweiterungen:** 3D-LiDAR, bessere KI-Perception, Multi-Robot-Fleet und Outdoor-GNSS.

Vollständige Ergebnisartefakte sind Systemkontext, Stakeholder-/Use-Case-Modell, Anforderungen, Funktions-/Zustandsmodelle, physische und logische Architektur, Schnittstellen-/Signalkatalog, Risiko-/Safety-/Security-Analysen, Betriebs- und Wartungskonzept, Testkatalog, Evidenzen, Konfigurations- und Releaseakte.

## 057. AGV/AMR-Flottensteuerung

### 1. Zweck und Systemübersicht
Koordinierter Materialtransport durch viele autonome Fahrzeuge in Lager und Produktion.

### 2. Systemkontext und Grenze
Das System wird zusammen mit seinen Bedienern, Nutzern, physischen Umgebungsbedingungen, Energie-/Medienquellen, externen Leit- und Informationssystemen, Wartungsorganisationen sowie nachgelagerten Verbrauchern oder Prozessen modelliert. Externe Akteure bleiben außerhalb der Systemgrenze, ihre Erwartungen, Daten, Befehle und Fehlermodi werden jedoch als Schnittstellenanforderungen erfasst.

### 3. Architektur
AMRs/AGVs, Fleet Manager, Map/Traffic Service, Order Interface, Charging, Safety Zones und MES/WMS-Anbindung.

Die Architektur ist in physische Komponenten, Steuerungs-/Rechenkomponenten, Softwaredienste, Kommunikations- und Energiepfade sowie Bedien-, Wartungs- und Backendanteile zu zerlegen. Redundanz, Verantwortlichkeit, Diagnose, Konfiguration und Freigabestatus werden je Element geführt.

### 4. Funktionsbeschreibung
- Auftragszuweisung, Routing, Verkehrsregeln, Deadlock Prevention, Ladeplanung, Priorisierung, Geofencing und Flottenanalyse..

### 5. Schnittstellen und Daten
WMS/MES/ERP, WLAN/5G, Fahrzeuge, Aufzüge/Tore, Ladestationen, Safety-PLC und Digital Twin.

Für jede Schnittstelle werden Quelle, Senke, Richtung, Protokoll/Medium, Einheit, Datenqualität, Zeitverhalten, Grenzwerte, Fehlerreaktion, Security-Klasse, Diagnose und Variantenbezug definiert.

### 6. Betriebsmodi
- **Mission**
- **Idle**
- **Charging**
- **Manual**
- **Recovery**
- **Emergency und Maintenance.**

Moduswechsel besitzen Auslöser, Guard-Bedingungen, Aktionen, Timeout, Abbruch-/Rollback-Regeln und erlaubte Folge-/Fallbackzustände.

### 7. Referenzanforderungen
- **REQ-057-SYS-001:** Das System muss seine Mission erfüllen: Koordinierter Materialtransport durch viele autonome Fahrzeuge in Lager und Produktion.
- **REQ-057-ARC-001:** Die Architektur muss die vorgesehenen Elemente und Verantwortlichkeiten abbilden: AMRs/AGVs, Fleet Manager, Map/Traffic Service, Order Interface, Charging, Safety Zones und MES/WMS-Anbindung.
- **REQ-057-FUN-001:** Die folgenden Kernfunktionen müssen in klar definierten Zuständen und mit nachvollziehbaren Ein-/Ausgaben bereitgestellt werden: Auftragszuweisung, Routing, Verkehrsregeln, Deadlock Prevention, Ladeplanung, Priorisierung, Geofencing und Flottenanalyse.
- **REQ-057-IF-001:** Die Schnittstellen müssen Datenformat, Richtung, Aktualität, Fehlerverhalten, Zugriffsrecht und Version für folgende Kopplungen definieren: WMS/MES/ERP, WLAN/5G, Fahrzeuge, Aufzüge/Tore, Ladestationen, Safety-PLC und Digital Twin.
- **REQ-057-MODE-001:** Das System muss mindestens die genannten Betriebs- und Fehlerzustände beherrschen: Mission, Idle, Charging, Manual, Recovery, Emergency und Maintenance.
- **REQ-057-SAFE-001:** Die zentralen Gefährdungen müssen erkannt, verhindert oder auf ein akzeptiertes Restrisiko reduziert werden: Kollision, Deadlock, falsche Karte, Funkverlust, blockierte Fluchtwege und unautorisierte Mission.
- **REQ-057-DIAG-001:** Fehler, Grenzwertverletzungen, Qualitätsverluste und Konfigurationsabweichungen müssen erkannt, zeitgestempelt und diagnostizierbar gespeichert werden.
- **REQ-057-SEC-001:** Identitäten, Rollen, Kommunikation, Softwarestände, Konfigurationen und Fernzugriffe müssen gegen unautorisierte Nutzung und Veränderung abgesichert sein.
- **REQ-057-CFG-001:** Hardware-, Software-, Parameter-, Rezept-/Missions- und Schnittstellenversionen müssen eindeutig konfigurationsgeführt und freigegeben werden.
- **REQ-057-VER-001:** Jede sicherheits-, qualitäts- oder missionskritische Anforderung muss mit mindestens einem Testfall und einer nachprüfbaren Evidenz verknüpft sein.
- **REQ-057-REC-001:** Nach Teilfehlern oder Neustart muss das System in einen definierten, konsistenten und nachvollziehbaren Zustand übergehen.

### 8. Safety, Security, Qualität und Betrieb
Die Sicherheits- und Betriebsargumentation behandelt insbesondere: Kollision, Deadlock, falsche Karte, Funkverlust, blockierte Fluchtwege und unautorisierte Mission.. Dazu gehören unabhängige Schutzebenen, sichere Zustände, Degradation, Alarmpriorität, Rollen-/Rechtekonzept, Änderungsfreigabe, sichere Fernwartung, Backup/Recovery, Audit und Lifecycle-Nachweise.

### 9. Verifikation und Testfälle
- **TC-057-01:** Vier Fahrzeuge an Engstelle. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-057-02:** Fleet Manager fällt aus. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-057-03:** Karte geändert. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-057-04:** Ladestation belegt. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-057-05:** Fußgänger tritt in Route. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-057-06:** WLAN-Roamingfehler. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-COMMON-01:** Neustart oder Teilwiederanlauf mit inkonsistentem Zwischenzustand; das System muss in einen definierten Recovery-Zustand wechseln.
- **TC-COMMON-02:** Unautorisierte Änderung eines kritischen Parameters oder Softwarestands; Änderung wird verhindert, alarmiert und protokolliert.

### 10. Varianten, Erweiterungen und Ergebnisartefakte
**Erweiterungen:** Cloud-Fleet, heterogene Herstellerflotte, KI-Dispatch und Energieoptimierung.

Vollständige Ergebnisartefakte sind Systemkontext, Stakeholder-/Use-Case-Modell, Anforderungen, Funktions-/Zustandsmodelle, physische und logische Architektur, Schnittstellen-/Signalkatalog, Risiko-/Safety-/Security-Analysen, Betriebs- und Wartungskonzept, Testkatalog, Evidenzen, Konfigurations- und Releaseakte.

## 058. CNC-Bearbeitungszentrum

### 1. Zweck und Systemübersicht
Präzise spanende Fertigung mit automatischem Werkzeugwechsel, Prozessüberwachung und Qualitätsnachweis.

### 2. Systemkontext und Grenze
Das System wird zusammen mit seinen Bedienern, Nutzern, physischen Umgebungsbedingungen, Energie-/Medienquellen, externen Leit- und Informationssystemen, Wartungsorganisationen sowie nachgelagerten Verbrauchern oder Prozessen modelliert. Externe Akteure bleiben außerhalb der Systemgrenze, ihre Erwartungen, Daten, Befehle und Fehlermodi werden jedoch als Schnittstellenanforderungen erfasst.

### 3. Architektur
CNC/PLC, Achsantriebe, Spindel, Werkzeugmagazin, Messtaster, Kühlung/Schmierung, Schutzraum und HMI.

Die Architektur ist in physische Komponenten, Steuerungs-/Rechenkomponenten, Softwaredienste, Kommunikations- und Energiepfade sowie Bedien-, Wartungs- und Backendanteile zu zerlegen. Redundanz, Verantwortlichkeit, Diagnose, Konfiguration und Freigabestatus werden je Element geführt.

### 4. Funktionsbeschreibung
- Interpolierte Bewegung, Spindelregelung, Werkzeugmanagement, Nullpunkt/Antasten, Kollisionsschutz, Prozessdaten und Diagnose..

### 5. Schnittstellen und Daten
Drive Bus, Safety I/O, DNC/MES, Werkzeugdatenbank, Messsysteme und Energie/Medien.

Für jede Schnittstelle werden Quelle, Senke, Richtung, Protokoll/Medium, Einheit, Datenqualität, Zeitverhalten, Grenzwerte, Fehlerreaktion, Security-Klasse, Diagnose und Variantenbezug definiert.

### 6. Betriebsmodi
- **Automatik**
- **MDI**
- **Jog**
- **Setup**
- **Tool Change**
- **Maintenance**
- **Safe Stop und Emergency.**

Moduswechsel besitzen Auslöser, Guard-Bedingungen, Aktionen, Timeout, Abbruch-/Rollback-Regeln und erlaubte Folge-/Fallbackzustände.

### 7. Referenzanforderungen
- **REQ-058-SYS-001:** Das System muss seine Mission erfüllen: Präzise spanende Fertigung mit automatischem Werkzeugwechsel, Prozessüberwachung und Qualitätsnachweis.
- **REQ-058-ARC-001:** Die Architektur muss die vorgesehenen Elemente und Verantwortlichkeiten abbilden: CNC/PLC, Achsantriebe, Spindel, Werkzeugmagazin, Messtaster, Kühlung/Schmierung, Schutzraum und HMI.
- **REQ-058-FUN-001:** Die folgenden Kernfunktionen müssen in klar definierten Zuständen und mit nachvollziehbaren Ein-/Ausgaben bereitgestellt werden: Interpolierte Bewegung, Spindelregelung, Werkzeugmanagement, Nullpunkt/Antasten, Kollisionsschutz, Prozessdaten und Diagnose.
- **REQ-058-IF-001:** Die Schnittstellen müssen Datenformat, Richtung, Aktualität, Fehlerverhalten, Zugriffsrecht und Version für folgende Kopplungen definieren: Drive Bus, Safety I/O, DNC/MES, Werkzeugdatenbank, Messsysteme und Energie/Medien.
- **REQ-058-MODE-001:** Das System muss mindestens die genannten Betriebs- und Fehlerzustände beherrschen: Automatik, MDI, Jog, Setup, Tool Change, Maintenance, Safe Stop und Emergency.
- **REQ-058-SAFE-001:** Die zentralen Gefährdungen müssen erkannt, verhindert oder auf ein akzeptiertes Restrisiko reduziert werden: Achskollision, Werkzeugbruch, offene Tür, Spindelüberdrehzahl, Brand und fehlerhaftes Programm.
- **REQ-058-DIAG-001:** Fehler, Grenzwertverletzungen, Qualitätsverluste und Konfigurationsabweichungen müssen erkannt, zeitgestempelt und diagnostizierbar gespeichert werden.
- **REQ-058-SEC-001:** Identitäten, Rollen, Kommunikation, Softwarestände, Konfigurationen und Fernzugriffe müssen gegen unautorisierte Nutzung und Veränderung abgesichert sein.
- **REQ-058-CFG-001:** Hardware-, Software-, Parameter-, Rezept-/Missions- und Schnittstellenversionen müssen eindeutig konfigurationsgeführt und freigegeben werden.
- **REQ-058-VER-001:** Jede sicherheits-, qualitäts- oder missionskritische Anforderung muss mit mindestens einem Testfall und einer nachprüfbaren Evidenz verknüpft sein.
- **REQ-058-REC-001:** Nach Teilfehlern oder Neustart muss das System in einen definierten, konsistenten und nachvollziehbaren Zustand übergehen.

### 8. Safety, Security, Qualität und Betrieb
Die Sicherheits- und Betriebsargumentation behandelt insbesondere: Achskollision, Werkzeugbruch, offene Tür, Spindelüberdrehzahl, Brand und fehlerhaftes Programm.. Dazu gehören unabhängige Schutzebenen, sichere Zustände, Degradation, Alarmpriorität, Rollen-/Rechtekonzept, Änderungsfreigabe, sichere Fernwartung, Backup/Recovery, Audit und Lifecycle-Nachweise.

### 9. Verifikation und Testfälle
- **TC-058-01:** Tür wird im Lauf geöffnet. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-058-02:** Werkzeugbruch erkannt. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-058-03:** Achse überschreitet Softwarelimit. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-058-04:** Kühlmittel fällt aus. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-058-05:** Falscher Nullpunkt. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-058-06:** Stromausfall und Wiederanlauf. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-COMMON-01:** Neustart oder Teilwiederanlauf mit inkonsistentem Zwischenzustand; das System muss in einen definierten Recovery-Zustand wechseln.
- **TC-COMMON-02:** Unautorisierte Änderung eines kritischen Parameters oder Softwarestands; Änderung wird verhindert, alarmiert und protokolliert.

### 10. Varianten, Erweiterungen und Ergebnisartefakte
**Erweiterungen:** Adaptive Feed Control, In-process Metrology, Digital Twin und Closed-Loop Quality.

Vollständige Ergebnisartefakte sind Systemkontext, Stakeholder-/Use-Case-Modell, Anforderungen, Funktions-/Zustandsmodelle, physische und logische Architektur, Schnittstellen-/Signalkatalog, Risiko-/Safety-/Security-Analysen, Betriebs- und Wartungskonzept, Testkatalog, Evidenzen, Konfigurations- und Releaseakte.

## 059. Verpackungs- und Abfülllinie

### 1. Zweck und Systemübersicht
Taktgenaues Formen, Füllen, Verschließen, Etikettieren, Prüfen und Palettieren.

### 2. Systemkontext und Grenze
Das System wird zusammen mit seinen Bedienern, Nutzern, physischen Umgebungsbedingungen, Energie-/Medienquellen, externen Leit- und Informationssystemen, Wartungsorganisationen sowie nachgelagerten Verbrauchern oder Prozessen modelliert. Externe Akteure bleiben außerhalb der Systemgrenze, ihre Erwartungen, Daten, Befehle und Fehlermodi werden jedoch als Schnittstellenanforderungen erfasst.

### 3. Architektur
Mehrere Maschinenmodule, PLC/Safety PLC, Servoachsen, Vision, Waagen, Fördertechnik, Rezept- und Batchsystem.

Die Architektur ist in physische Komponenten, Steuerungs-/Rechenkomponenten, Softwaredienste, Kommunikations- und Energiepfade sowie Bedien-, Wartungs- und Backendanteile zu zerlegen. Redundanz, Verantwortlichkeit, Diagnose, Konfiguration und Freigabestatus werden je Element geführt.

### 4. Funktionsbeschreibung
- Synchronisation, Produktwechsel, Füllmengenregelung, Reject, Etikettprüfung, OEE, Batch Traceability und CIP/SIP optional..

### 5. Schnittstellen und Daten
Industrial Ethernet, MES/ERP, Drucker/Scanner, Qualitätslabor, Medien und Safety.

Für jede Schnittstelle werden Quelle, Senke, Richtung, Protokoll/Medium, Einheit, Datenqualität, Zeitverhalten, Grenzwerte, Fehlerreaktion, Security-Klasse, Diagnose und Variantenbezug definiert.

### 6. Betriebsmodi
- **Produktion**
- **Formatwechsel**
- **Reinigung**
- **Anfahren**
- **Leerlauf**
- **Störung**
- **Wartung und Not-Halt.**

Moduswechsel besitzen Auslöser, Guard-Bedingungen, Aktionen, Timeout, Abbruch-/Rollback-Regeln und erlaubte Folge-/Fallbackzustände.

### 7. Referenzanforderungen
- **REQ-059-SYS-001:** Das System muss seine Mission erfüllen: Taktgenaues Formen, Füllen, Verschließen, Etikettieren, Prüfen und Palettieren.
- **REQ-059-ARC-001:** Die Architektur muss die vorgesehenen Elemente und Verantwortlichkeiten abbilden: Mehrere Maschinenmodule, PLC/Safety PLC, Servoachsen, Vision, Waagen, Fördertechnik, Rezept- und Batchsystem.
- **REQ-059-FUN-001:** Die folgenden Kernfunktionen müssen in klar definierten Zuständen und mit nachvollziehbaren Ein-/Ausgaben bereitgestellt werden: Synchronisation, Produktwechsel, Füllmengenregelung, Reject, Etikettprüfung, OEE, Batch Traceability und CIP/SIP optional.
- **REQ-059-IF-001:** Die Schnittstellen müssen Datenformat, Richtung, Aktualität, Fehlerverhalten, Zugriffsrecht und Version für folgende Kopplungen definieren: Industrial Ethernet, MES/ERP, Drucker/Scanner, Qualitätslabor, Medien und Safety.
- **REQ-059-MODE-001:** Das System muss mindestens die genannten Betriebs- und Fehlerzustände beherrschen: Produktion, Formatwechsel, Reinigung, Anfahren, Leerlauf, Störung, Wartung und Not-Halt.
- **REQ-059-SAFE-001:** Die zentralen Gefährdungen müssen erkannt, verhindert oder auf ein akzeptiertes Restrisiko reduziert werden: Kontamination, falsches Etikett, Über-/Unterfüllung, Quetschstelle und Vermischung von Chargen.
- **REQ-059-DIAG-001:** Fehler, Grenzwertverletzungen, Qualitätsverluste und Konfigurationsabweichungen müssen erkannt, zeitgestempelt und diagnostizierbar gespeichert werden.
- **REQ-059-SEC-001:** Identitäten, Rollen, Kommunikation, Softwarestände, Konfigurationen und Fernzugriffe müssen gegen unautorisierte Nutzung und Veränderung abgesichert sein.
- **REQ-059-CFG-001:** Hardware-, Software-, Parameter-, Rezept-/Missions- und Schnittstellenversionen müssen eindeutig konfigurationsgeführt und freigegeben werden.
- **REQ-059-VER-001:** Jede sicherheits-, qualitäts- oder missionskritische Anforderung muss mit mindestens einem Testfall und einer nachprüfbaren Evidenz verknüpft sein.
- **REQ-059-REC-001:** Nach Teilfehlern oder Neustart muss das System in einen definierten, konsistenten und nachvollziehbaren Zustand übergehen.

### 8. Safety, Security, Qualität und Betrieb
Die Sicherheits- und Betriebsargumentation behandelt insbesondere: Kontamination, falsches Etikett, Über-/Unterfüllung, Quetschstelle und Vermischung von Chargen.. Dazu gehören unabhängige Schutzebenen, sichere Zustände, Degradation, Alarmpriorität, Rollen-/Rechtekonzept, Änderungsfreigabe, sichere Fernwartung, Backup/Recovery, Audit und Lifecycle-Nachweise.

### 9. Verifikation und Testfälle
- **TC-059-01:** Füllmenge außerhalb Toleranz. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-059-02:** Falsches Label. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-059-03:** Produktstau. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-059-04:** Schutztür geöffnet. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-059-05:** Rezeptwechsel. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-059-06:** Batchdatenbank nicht verfügbar. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-COMMON-01:** Neustart oder Teilwiederanlauf mit inkonsistentem Zwischenzustand; das System muss in einen definierten Recovery-Zustand wechseln.
- **TC-COMMON-02:** Unautorisierte Änderung eines kritischen Parameters oder Softwarestands; Änderung wird verhindert, alarmiert und protokolliert.

### 10. Varianten, Erweiterungen und Ergebnisartefakte
**Erweiterungen:** Inline-Spektroskopie, AI-Vision, adaptive Taktung und digitale Chargenakte.

Vollständige Ergebnisartefakte sind Systemkontext, Stakeholder-/Use-Case-Modell, Anforderungen, Funktions-/Zustandsmodelle, physische und logische Architektur, Schnittstellen-/Signalkatalog, Risiko-/Safety-/Security-Analysen, Betriebs- und Wartungskonzept, Testkatalog, Evidenzen, Konfigurations- und Releaseakte.

## 060. Automatisiertes Hochregallager

### 1. Zweck und Systemübersicht
Sichere Ein-/Auslagerung, Bestandsführung und Materialfluss in hochdichten Lagern.

### 2. Systemkontext und Grenze
Das System wird zusammen mit seinen Bedienern, Nutzern, physischen Umgebungsbedingungen, Energie-/Medienquellen, externen Leit- und Informationssystemen, Wartungsorganisationen sowie nachgelagerten Verbrauchern oder Prozessen modelliert. Externe Akteure bleiben außerhalb der Systemgrenze, ihre Erwartungen, Daten, Befehle und Fehlermodi werden jedoch als Schnittstellenanforderungen erfasst.

### 3. Architektur
Regalbediengeräte/Shuttles, Fördertechnik, Lagerverwaltung, Materialflussrechner, Safety PLC, Scanner und Brandschutzkopplung.

Die Architektur ist in physische Komponenten, Steuerungs-/Rechenkomponenten, Softwaredienste, Kommunikations- und Energiepfade sowie Bedien-, Wartungs- und Backendanteile zu zerlegen. Redundanz, Verantwortlichkeit, Diagnose, Konfiguration und Freigabestatus werden je Element geführt.

### 4. Funktionsbeschreibung
- Lagerplatzstrategie, Transportaufträge, Sequenzierung, Bestandsabgleich, Störumfahrung, Inventur und Energieoptimierung..

### 5. Schnittstellen und Daten
WMS/ERP/MES, PLCs, Barcode/RFID, Tore, Brandschutz und Bedienplätze.

Für jede Schnittstelle werden Quelle, Senke, Richtung, Protokoll/Medium, Einheit, Datenqualität, Zeitverhalten, Grenzwerte, Fehlerreaktion, Security-Klasse, Diagnose und Variantenbezug definiert.

### 6. Betriebsmodi
- **Automatik**
- **manueller Auftrag**
- **Inventur**
- **Wartungsgasse**
- **Störung**
- **Evakuierung und Fire Mode.**

Moduswechsel besitzen Auslöser, Guard-Bedingungen, Aktionen, Timeout, Abbruch-/Rollback-Regeln und erlaubte Folge-/Fallbackzustände.

### 7. Referenzanforderungen
- **REQ-060-SYS-001:** Das System muss seine Mission erfüllen: Sichere Ein-/Auslagerung, Bestandsführung und Materialfluss in hochdichten Lagern.
- **REQ-060-ARC-001:** Die Architektur muss die vorgesehenen Elemente und Verantwortlichkeiten abbilden: Regalbediengeräte/Shuttles, Fördertechnik, Lagerverwaltung, Materialflussrechner, Safety PLC, Scanner und Brandschutzkopplung.
- **REQ-060-FUN-001:** Die folgenden Kernfunktionen müssen in klar definierten Zuständen und mit nachvollziehbaren Ein-/Ausgaben bereitgestellt werden: Lagerplatzstrategie, Transportaufträge, Sequenzierung, Bestandsabgleich, Störumfahrung, Inventur und Energieoptimierung.
- **REQ-060-IF-001:** Die Schnittstellen müssen Datenformat, Richtung, Aktualität, Fehlerverhalten, Zugriffsrecht und Version für folgende Kopplungen definieren: WMS/ERP/MES, PLCs, Barcode/RFID, Tore, Brandschutz und Bedienplätze.
- **REQ-060-MODE-001:** Das System muss mindestens die genannten Betriebs- und Fehlerzustände beherrschen: Automatik, manueller Auftrag, Inventur, Wartungsgasse, Störung, Evakuierung und Fire Mode.
- **REQ-060-SAFE-001:** Die zentralen Gefährdungen müssen erkannt, verhindert oder auf ein akzeptiertes Restrisiko reduziert werden: Kollision, Lastabsturz, falscher Bestand, Blockade, Brand und Person im Gefahrenbereich.
- **REQ-060-DIAG-001:** Fehler, Grenzwertverletzungen, Qualitätsverluste und Konfigurationsabweichungen müssen erkannt, zeitgestempelt und diagnostizierbar gespeichert werden.
- **REQ-060-SEC-001:** Identitäten, Rollen, Kommunikation, Softwarestände, Konfigurationen und Fernzugriffe müssen gegen unautorisierte Nutzung und Veränderung abgesichert sein.
- **REQ-060-CFG-001:** Hardware-, Software-, Parameter-, Rezept-/Missions- und Schnittstellenversionen müssen eindeutig konfigurationsgeführt und freigegeben werden.
- **REQ-060-VER-001:** Jede sicherheits-, qualitäts- oder missionskritische Anforderung muss mit mindestens einem Testfall und einer nachprüfbaren Evidenz verknüpft sein.
- **REQ-060-REC-001:** Nach Teilfehlern oder Neustart muss das System in einen definierten, konsistenten und nachvollziehbaren Zustand übergehen.

### 8. Safety, Security, Qualität und Betrieb
Die Sicherheits- und Betriebsargumentation behandelt insbesondere: Kollision, Lastabsturz, falscher Bestand, Blockade, Brand und Person im Gefahrenbereich.. Dazu gehören unabhängige Schutzebenen, sichere Zustände, Degradation, Alarmpriorität, Rollen-/Rechtekonzept, Änderungsfreigabe, sichere Fernwartung, Backup/Recovery, Audit und Lifecycle-Nachweise.

### 9. Verifikation und Testfälle
- **TC-060-01:** Doppelbelegung erkannt. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-060-02:** Last ragt heraus. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-060-03:** Regalbediengerät verliert Position. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-060-04:** WMS-Ausfall. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-060-05:** Brandalarm. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-060-06:** Person betritt Gasse. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-COMMON-01:** Neustart oder Teilwiederanlauf mit inkonsistentem Zwischenzustand; das System muss in einen definierten Recovery-Zustand wechseln.
- **TC-COMMON-02:** Unautorisierte Änderung eines kritischen Parameters oder Softwarestands; Änderung wird verhindert, alarmiert und protokolliert.

### 10. Varianten, Erweiterungen und Ergebnisartefakte
**Erweiterungen:** Robot Picking, Drohneninventur, dynamische Slotting-Optimierung und Digital Twin.

Vollständige Ergebnisartefakte sind Systemkontext, Stakeholder-/Use-Case-Modell, Anforderungen, Funktions-/Zustandsmodelle, physische und logische Architektur, Schnittstellen-/Signalkatalog, Risiko-/Safety-/Security-Analysen, Betriebs- und Wartungskonzept, Testkatalog, Evidenzen, Konfigurations- und Releaseakte.

## 061. Prozessleitsystem mit Safety Instrumented System

### 1. Zweck und Systemübersicht
Regelung und sichere Abschaltung kontinuierlicher oder batchorientierter Industrieprozesse.

### 2. Systemkontext und Grenze
Das System wird zusammen mit seinen Bedienern, Nutzern, physischen Umgebungsbedingungen, Energie-/Medienquellen, externen Leit- und Informationssystemen, Wartungsorganisationen sowie nachgelagerten Verbrauchern oder Prozessen modelliert. Externe Akteure bleiben außerhalb der Systemgrenze, ihre Erwartungen, Daten, Befehle und Fehlermodi werden jedoch als Schnittstellenanforderungen erfasst.

### 3. Architektur
DCS, unabhängiges SIS, Feldinstrumente, Aktoren, Historian, Engineering Station, Operator HMI und Alarmmanagement.

Die Architektur ist in physische Komponenten, Steuerungs-/Rechenkomponenten, Softwaredienste, Kommunikations- und Energiepfade sowie Bedien-, Wartungs- und Backendanteile zu zerlegen. Redundanz, Verantwortlichkeit, Diagnose, Konfiguration und Freigabestatus werden je Element geführt.

### 4. Funktionsbeschreibung
- Regelkreise, Sequenzen, Rezepturen, Interlocks, ESD, Alarmierung, Trend/Audit und Management of Change..

### 5. Schnittstellen und Daten
HART/Fieldbus/Industrial Ethernet, Package Units, Lab/MES, Historian und Maintenance.

Für jede Schnittstelle werden Quelle, Senke, Richtung, Protokoll/Medium, Einheit, Datenqualität, Zeitverhalten, Grenzwerte, Fehlerreaktion, Security-Klasse, Diagnose und Variantenbezug definiert.

### 6. Betriebsmodi
- **Start-up**
- **Normal**
- **Grade/Recipe Change**
- **Shutdown**
- **Emergency Shutdown**
- **Maintenance und Proof Test.**

Moduswechsel besitzen Auslöser, Guard-Bedingungen, Aktionen, Timeout, Abbruch-/Rollback-Regeln und erlaubte Folge-/Fallbackzustände.

### 7. Referenzanforderungen
- **REQ-061-SYS-001:** Das System muss seine Mission erfüllen: Regelung und sichere Abschaltung kontinuierlicher oder batchorientierter Industrieprozesse.
- **REQ-061-ARC-001:** Die Architektur muss die vorgesehenen Elemente und Verantwortlichkeiten abbilden: DCS, unabhängiges SIS, Feldinstrumente, Aktoren, Historian, Engineering Station, Operator HMI und Alarmmanagement.
- **REQ-061-FUN-001:** Die folgenden Kernfunktionen müssen in klar definierten Zuständen und mit nachvollziehbaren Ein-/Ausgaben bereitgestellt werden: Regelkreise, Sequenzen, Rezepturen, Interlocks, ESD, Alarmierung, Trend/Audit und Management of Change.
- **REQ-061-IF-001:** Die Schnittstellen müssen Datenformat, Richtung, Aktualität, Fehlerverhalten, Zugriffsrecht und Version für folgende Kopplungen definieren: HART/Fieldbus/Industrial Ethernet, Package Units, Lab/MES, Historian und Maintenance.
- **REQ-061-MODE-001:** Das System muss mindestens die genannten Betriebs- und Fehlerzustände beherrschen: Start-up, Normal, Grade/Recipe Change, Shutdown, Emergency Shutdown, Maintenance und Proof Test.
- **REQ-061-SAFE-001:** Die zentralen Gefährdungen müssen erkannt, verhindert oder auf ein akzeptiertes Restrisiko reduziert werden: Überdruck, Übertemperatur, gefährliche Reaktion, falsche Ventilstellung und Common-Cause zwischen DCS/SIS.
- **REQ-061-DIAG-001:** Fehler, Grenzwertverletzungen, Qualitätsverluste und Konfigurationsabweichungen müssen erkannt, zeitgestempelt und diagnostizierbar gespeichert werden.
- **REQ-061-SEC-001:** Identitäten, Rollen, Kommunikation, Softwarestände, Konfigurationen und Fernzugriffe müssen gegen unautorisierte Nutzung und Veränderung abgesichert sein.
- **REQ-061-CFG-001:** Hardware-, Software-, Parameter-, Rezept-/Missions- und Schnittstellenversionen müssen eindeutig konfigurationsgeführt und freigegeben werden.
- **REQ-061-VER-001:** Jede sicherheits-, qualitäts- oder missionskritische Anforderung muss mit mindestens einem Testfall und einer nachprüfbaren Evidenz verknüpft sein.
- **REQ-061-REC-001:** Nach Teilfehlern oder Neustart muss das System in einen definierten, konsistenten und nachvollziehbaren Zustand übergehen.

### 8. Safety, Security, Qualität und Betrieb
Die Sicherheits- und Betriebsargumentation behandelt insbesondere: Überdruck, Übertemperatur, gefährliche Reaktion, falsche Ventilstellung und Common-Cause zwischen DCS/SIS.. Dazu gehören unabhängige Schutzebenen, sichere Zustände, Degradation, Alarmpriorität, Rollen-/Rechtekonzept, Änderungsfreigabe, sichere Fernwartung, Backup/Recovery, Audit und Lifecycle-Nachweise.

### 9. Verifikation und Testfälle
- **TC-061-01:** Druck überschreitet Trip. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-061-02:** Sensor driftet. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-061-03:** ESD-Ventil schließt nicht. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-061-04:** DCS-Netz fällt aus. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-061-05:** Proof-Test entdeckt verdeckten Fehler. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-061-06:** Unberechtigte Setpoint-Änderung. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-COMMON-01:** Neustart oder Teilwiederanlauf mit inkonsistentem Zwischenzustand; das System muss in einen definierten Recovery-Zustand wechseln.
- **TC-COMMON-02:** Unautorisierte Änderung eines kritischen Parameters oder Softwarestands; Änderung wird verhindert, alarmiert und protokolliert.

### 10. Varianten, Erweiterungen und Ergebnisartefakte
**Erweiterungen:** Advanced Process Control, digitaler Prozesszwilling, Predictive Maintenance und Remote Operations.

Vollständige Ergebnisartefakte sind Systemkontext, Stakeholder-/Use-Case-Modell, Anforderungen, Funktions-/Zustandsmodelle, physische und logische Architektur, Schnittstellen-/Signalkatalog, Risiko-/Safety-/Security-Analysen, Betriebs- und Wartungskonzept, Testkatalog, Evidenzen, Konfigurations- und Releaseakte.

## 062. Digitale Fabriklinie / Montagewerk

### 1. Zweck und Systemübersicht
Durchgängige Steuerung einer mehrstufigen Fertigungslinie von Materialbereitstellung bis End-of-Line-Test.

### 2. Systemkontext und Grenze
Das System wird zusammen mit seinen Bedienern, Nutzern, physischen Umgebungsbedingungen, Energie-/Medienquellen, externen Leit- und Informationssystemen, Wartungsorganisationen sowie nachgelagerten Verbrauchern oder Prozessen modelliert. Externe Akteure bleiben außerhalb der Systemgrenze, ihre Erwartungen, Daten, Befehle und Fehlermodi werden jedoch als Schnittstellenanforderungen erfasst.

### 3. Architektur
PLC-/Robotikzellen, Materialfluss, MES, Qualitätsmanagement, Andon, Werkerassistenz, Traceability und Energieplattform.

Die Architektur ist in physische Komponenten, Steuerungs-/Rechenkomponenten, Softwaredienste, Kommunikations- und Energiepfade sowie Bedien-, Wartungs- und Backendanteile zu zerlegen. Redundanz, Verantwortlichkeit, Diagnose, Konfiguration und Freigabestatus werden je Element geführt.

### 4. Funktionsbeschreibung
- Produktionsplanung, Variantensteuerung, Sequenz, Takt, Qualitätsgates, Nacharbeit, Genealogie, OEE und Störungseskalation..

### 5. Schnittstellen und Daten
ERP/PLM/MES, Maschinen, AGV, Prüfstände, Scanner/RFID, Energie- und Personalplanung.

Für jede Schnittstelle werden Quelle, Senke, Richtung, Protokoll/Medium, Einheit, Datenqualität, Zeitverhalten, Grenzwerte, Fehlerreaktion, Security-Klasse, Diagnose und Variantenbezug definiert.

### 6. Betriebsmodi
- **Serienproduktion**
- **Ramp-up**
- **Modellwechsel**
- **Nacharbeit**
- **Wartung**
- **Störung und kontrollierter Shutdown.**

Moduswechsel besitzen Auslöser, Guard-Bedingungen, Aktionen, Timeout, Abbruch-/Rollback-Regeln und erlaubte Folge-/Fallbackzustände.

### 7. Referenzanforderungen
- **REQ-062-SYS-001:** Das System muss seine Mission erfüllen: Durchgängige Steuerung einer mehrstufigen Fertigungslinie von Materialbereitstellung bis End-of-Line-Test.
- **REQ-062-ARC-001:** Die Architektur muss die vorgesehenen Elemente und Verantwortlichkeiten abbilden: PLC-/Robotikzellen, Materialfluss, MES, Qualitätsmanagement, Andon, Werkerassistenz, Traceability und Energieplattform.
- **REQ-062-FUN-001:** Die folgenden Kernfunktionen müssen in klar definierten Zuständen und mit nachvollziehbaren Ein-/Ausgaben bereitgestellt werden: Produktionsplanung, Variantensteuerung, Sequenz, Takt, Qualitätsgates, Nacharbeit, Genealogie, OEE und Störungseskalation.
- **REQ-062-IF-001:** Die Schnittstellen müssen Datenformat, Richtung, Aktualität, Fehlerverhalten, Zugriffsrecht und Version für folgende Kopplungen definieren: ERP/PLM/MES, Maschinen, AGV, Prüfstände, Scanner/RFID, Energie- und Personalplanung.
- **REQ-062-MODE-001:** Das System muss mindestens die genannten Betriebs- und Fehlerzustände beherrschen: Serienproduktion, Ramp-up, Modellwechsel, Nacharbeit, Wartung, Störung und kontrollierter Shutdown.
- **REQ-062-SAFE-001:** Die zentralen Gefährdungen müssen erkannt, verhindert oder auf ein akzeptiertes Restrisiko reduziert werden: Falsche Variante, fehlendes Teil, Qualitätsmerkmal ungeprüft, Taktstau und Datenlücke in Genealogie.
- **REQ-062-DIAG-001:** Fehler, Grenzwertverletzungen, Qualitätsverluste und Konfigurationsabweichungen müssen erkannt, zeitgestempelt und diagnostizierbar gespeichert werden.
- **REQ-062-SEC-001:** Identitäten, Rollen, Kommunikation, Softwarestände, Konfigurationen und Fernzugriffe müssen gegen unautorisierte Nutzung und Veränderung abgesichert sein.
- **REQ-062-CFG-001:** Hardware-, Software-, Parameter-, Rezept-/Missions- und Schnittstellenversionen müssen eindeutig konfigurationsgeführt und freigegeben werden.
- **REQ-062-VER-001:** Jede sicherheits-, qualitäts- oder missionskritische Anforderung muss mit mindestens einem Testfall und einer nachprüfbaren Evidenz verknüpft sein.
- **REQ-062-REC-001:** Nach Teilfehlern oder Neustart muss das System in einen definierten, konsistenten und nachvollziehbaren Zustand übergehen.

### 8. Safety, Security, Qualität und Betrieb
Die Sicherheits- und Betriebsargumentation behandelt insbesondere: Falsche Variante, fehlendes Teil, Qualitätsmerkmal ungeprüft, Taktstau und Datenlücke in Genealogie.. Dazu gehören unabhängige Schutzebenen, sichere Zustände, Degradation, Alarmpriorität, Rollen-/Rechtekonzept, Änderungsfreigabe, sichere Fernwartung, Backup/Recovery, Audit und Lifecycle-Nachweise.

### 9. Verifikation und Testfälle
- **TC-062-01:** Falsches Teil gescannt. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-062-02:** Prüfstand offline. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-062-03:** Modellwechsel im Takt. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-062-04:** AGV-Lieferung verspätet. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-062-05:** MES-Verbindung unterbrochen. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-062-06:** Qualitätsfreigabe fehlt. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-COMMON-01:** Neustart oder Teilwiederanlauf mit inkonsistentem Zwischenzustand; das System muss in einen definierten Recovery-Zustand wechseln.
- **TC-COMMON-02:** Unautorisierte Änderung eines kritischen Parameters oder Softwarestands; Änderung wird verhindert, alarmiert und protokolliert.

### 10. Varianten, Erweiterungen und Ergebnisartefakte
**Erweiterungen:** Closed-Loop PLM, KI-Engpassprognose, flexible Zellen und digitale Arbeitsanweisungen.

Vollständige Ergebnisartefakte sind Systemkontext, Stakeholder-/Use-Case-Modell, Anforderungen, Funktions-/Zustandsmodelle, physische und logische Architektur, Schnittstellen-/Signalkatalog, Risiko-/Safety-/Security-Analysen, Betriebs- und Wartungskonzept, Testkatalog, Evidenzen, Konfigurations- und Releaseakte.

## 063. Machine-Vision-Qualitätsprüfung

### 1. Zweck und Systemübersicht
Automatische Erkennung, Vermessung und Klassifikation von Produktfehlern inline oder im Labor.

### 2. Systemkontext und Grenze
Das System wird zusammen mit seinen Bedienern, Nutzern, physischen Umgebungsbedingungen, Energie-/Medienquellen, externen Leit- und Informationssystemen, Wartungsorganisationen sowie nachgelagerten Verbrauchern oder Prozessen modelliert. Externe Akteure bleiben außerhalb der Systemgrenze, ihre Erwartungen, Daten, Befehle und Fehlermodi werden jedoch als Schnittstellenanforderungen erfasst.

### 3. Architektur
Kameras/Optik/Beleuchtung, Trigger, Edge-Rechner, ML-/Regelalgorithmen, Reject-Mechanik, Datenbank und Review-HMI.

Die Architektur ist in physische Komponenten, Steuerungs-/Rechenkomponenten, Softwaredienste, Kommunikations- und Energiepfade sowie Bedien-, Wartungs- und Backendanteile zu zerlegen. Redundanz, Verantwortlichkeit, Diagnose, Konfiguration und Freigabestatus werden je Element geführt.

### 4. Funktionsbeschreibung
- Bildaufnahme, Kalibrierung, Vorverarbeitung, Merkmal/AI-Inferenz, Entscheidung, Unsicherheitsbehandlung, Traceability und Modellüberwachung..

### 5. Schnittstellen und Daten
PLC/MES/QMS, Kamera/Beleuchtung, Encoder, Label/Serial, Review Station und Model Registry.

Für jede Schnittstelle werden Quelle, Senke, Richtung, Protokoll/Medium, Einheit, Datenqualität, Zeitverhalten, Grenzwerte, Fehlerreaktion, Security-Klasse, Diagnose und Variantenbezug definiert.

### 6. Betriebsmodi
- **Production**
- **Calibration**
- **Teach**
- **Validation**
- **Degraded/Manual Review**
- **Maintenance und Offline Replay.**

Moduswechsel besitzen Auslöser, Guard-Bedingungen, Aktionen, Timeout, Abbruch-/Rollback-Regeln und erlaubte Folge-/Fallbackzustände.

### 7. Referenzanforderungen
- **REQ-063-SYS-001:** Das System muss seine Mission erfüllen: Automatische Erkennung, Vermessung und Klassifikation von Produktfehlern inline oder im Labor.
- **REQ-063-ARC-001:** Die Architektur muss die vorgesehenen Elemente und Verantwortlichkeiten abbilden: Kameras/Optik/Beleuchtung, Trigger, Edge-Rechner, ML-/Regelalgorithmen, Reject-Mechanik, Datenbank und Review-HMI.
- **REQ-063-FUN-001:** Die folgenden Kernfunktionen müssen in klar definierten Zuständen und mit nachvollziehbaren Ein-/Ausgaben bereitgestellt werden: Bildaufnahme, Kalibrierung, Vorverarbeitung, Merkmal/AI-Inferenz, Entscheidung, Unsicherheitsbehandlung, Traceability und Modellüberwachung.
- **REQ-063-IF-001:** Die Schnittstellen müssen Datenformat, Richtung, Aktualität, Fehlerverhalten, Zugriffsrecht und Version für folgende Kopplungen definieren: PLC/MES/QMS, Kamera/Beleuchtung, Encoder, Label/Serial, Review Station und Model Registry.
- **REQ-063-MODE-001:** Das System muss mindestens die genannten Betriebs- und Fehlerzustände beherrschen: Production, Calibration, Teach, Validation, Degraded/Manual Review, Maintenance und Offline Replay.
- **REQ-063-SAFE-001:** Die zentralen Gefährdungen müssen erkannt, verhindert oder auf ein akzeptiertes Restrisiko reduziert werden: False Negative, Drift, falsches Modell, Beleuchtungsänderung, Datenverlust und unkontrollierter Auto-Reject.
- **REQ-063-DIAG-001:** Fehler, Grenzwertverletzungen, Qualitätsverluste und Konfigurationsabweichungen müssen erkannt, zeitgestempelt und diagnostizierbar gespeichert werden.
- **REQ-063-SEC-001:** Identitäten, Rollen, Kommunikation, Softwarestände, Konfigurationen und Fernzugriffe müssen gegen unautorisierte Nutzung und Veränderung abgesichert sein.
- **REQ-063-CFG-001:** Hardware-, Software-, Parameter-, Rezept-/Missions- und Schnittstellenversionen müssen eindeutig konfigurationsgeführt und freigegeben werden.
- **REQ-063-VER-001:** Jede sicherheits-, qualitäts- oder missionskritische Anforderung muss mit mindestens einem Testfall und einer nachprüfbaren Evidenz verknüpft sein.
- **REQ-063-REC-001:** Nach Teilfehlern oder Neustart muss das System in einen definierten, konsistenten und nachvollziehbaren Zustand übergehen.

### 8. Safety, Security, Qualität und Betrieb
Die Sicherheits- und Betriebsargumentation behandelt insbesondere: False Negative, Drift, falsches Modell, Beleuchtungsänderung, Datenverlust und unkontrollierter Auto-Reject.. Dazu gehören unabhängige Schutzebenen, sichere Zustände, Degradation, Alarmpriorität, Rollen-/Rechtekonzept, Änderungsfreigabe, sichere Fernwartung, Backup/Recovery, Audit und Lifecycle-Nachweise.

### 9. Verifikation und Testfälle
- **TC-063-01:** Bekannter Defektkatalog. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-063-02:** Beleuchtung altert. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-063-03:** Kamera verschoben. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-063-04:** Modellversion falsch. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-063-05:** Unsicheres Ergebnis wird geroutet. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-063-06:** Datenbankausfall. Prüfkriterien sind Erkennung, Reaktionszeit bzw. Sequenz, erreichter Zustand, Bedienerinformation, Diagnoseeintrag und Daten-/Konfigurationsnachweis.
- **TC-COMMON-01:** Neustart oder Teilwiederanlauf mit inkonsistentem Zwischenzustand; das System muss in einen definierten Recovery-Zustand wechseln.
- **TC-COMMON-02:** Unautorisierte Änderung eines kritischen Parameters oder Softwarestands; Änderung wird verhindert, alarmiert und protokolliert.

### 10. Varianten, Erweiterungen und Ergebnisartefakte
**Erweiterungen:** Self-supervised Learning, 3D-Vision, Explainability und Flottenlernen über Linien.

Vollständige Ergebnisartefakte sind Systemkontext, Stakeholder-/Use-Case-Modell, Anforderungen, Funktions-/Zustandsmodelle, physische und logische Architektur, Schnittstellen-/Signalkatalog, Risiko-/Safety-/Security-Analysen, Betriebs- und Wartungskonzept, Testkatalog, Evidenzen, Konfigurations- und Releaseakte.
