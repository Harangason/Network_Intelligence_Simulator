# Befunde der echten Qwen-Prüfung

## F1: Gemeinsame Architekturzeile kann mehrere Gerätearten nicht getrennt belegen

`Intelligentes HLK-Regelsystem.txt` scheitert in beiden tatsächlichen Modellantworten an derselben Grenze. Die Quelle nennt Raumcontroller, Sensorik, Aktoren und BMS/Cloud gemeinsam. Qwen ordnet diese Quelle mehrfach ein. `resolve_document_references()` lehnt mehrere Komponenten aus derselben `source_ref` ab. Die Korrekturaufforderung wird übermittelt, beseitigt den Fehler aber nicht.

Erste fehlerhafte ausführende Schicht: Quellenreferenz-Auflösung in `backend/nis/agent/orchestration/project_intake.py`, vor der fachlichen Validierung. Zusätzlich nennt die Modellprosa den allgemeinen Raumcontroller eine konkrete Instanz, obwohl weder eine individuelle Kennung noch eine Stückzahl vorliegt. Ein anderer Dateiname oder zusätzliche Controller-Stichwörter beheben diese strukturelle Grenze nicht.

Evidence: `building-wire.json` enthält beide echten Anfragen, das Validierungsfeedback und beide Antworten; `manifest.json` enthält den terminalen Fehler. Produktivdaten wurden nicht verändert.

Dasselbe terminale Problem tritt bei `Kollaborativer Roboterarm.txt` und `Infusionspumpe.txt` nach jeweils zwei echten Modellantworten auf. Die erste Roboterarm-Antwort trennt die Hardware fachlich sinnvoll in Aktor-, Sensor-, Controller- und sonstige Kategorien, kann diese Aufteilung mit der vorhandenen Quellenreferenz aber nicht ausdrücken. Die Korrektur wechselt Sicherheitssteuerung und Teach-Panel sogar von Kategorien zu Instanzen, ohne den eigentlichen Quellenkonflikt zu lösen. Bei der Infusionspumpe nennt die erste Antwort zusätzlich einen allgemeinen Embedded Controller mit Stückzahl 1 und „Embedded“/„Remote“ als ungeklärte Technologien. Diese Antworten wurden nicht als Vorschlag übernommen.

## F2: Formal akzeptierte Antwort kann unterschiedliche Hardwarerollen zusammenwerfen

`Chemieanlagen-Modul.txt` liefert nach einer echten Modellantwort einen prüfpflichtigen Vorschlag. Prozessmodul, Funktionen und Anforderungen passen zum Original; es werden keine Stückzahlen oder Busse erfunden. Allerdings wird die gesamte gemischte Architekturzeile als eine `CATEGORY/OTHER` gespeichert. Prozesssensorik, Aktoren und SPS/DCS werden damit nicht als getrennte Sensor-, Aktor- und Controllergruppen erfasst. Die Annahme nennt sogar Prozesssensorik und Aktoren ausdrücklich `role OTHER`.

Der Validator akzeptiert diesen Informationsverlust. `NATIVE_RETURNED` bedeutet daher nicht fachliches PASS. Für einen verwendbaren Geräteumfang ist dies ein Teilbefund, kein allgemeiner Erfolgsnachweis.

Evidence: `chemical-proposal.json`, `chemical-wire.json` und unveränderte Originalkopie `chemical-source.txt`.

## F3: Logische Verarbeitung wird in akzeptierter Telekommunikationsantwort zu Hardware

`5G-RAN-Komponente.txt` liefert einen prüfpflichtigen Vorschlag nach einem echten Modellaufruf. Der Telekommunikationskontext und die Funktionen Scheduling/QoS werden erkannt, konkrete Stückzahlen werden nicht erfunden. Die gesamte Architekturzeile landet jedoch wieder als `CATEGORY/OTHER`. Die Annahme bezeichnet ausdrücklich auch „Baseband-Processing“ als Hardwarekategorie. Damit geht die erforderliche Trennung zwischen Verarbeitung, Funkhardware und Schnittstellen verloren. Die registrierte 5G-Technologie wird aus dem Projekttitel erkannt; das belegt für sich noch keine konkrete Geräteanschluss-Zuordnung.

Evidence: `telecom-proposal.json` und `telecom-wire.json`. Auch dieser formal akzeptierte Vorschlag ist daher nur teilweise fachlich brauchbar.

## F4: Satelliten-Architektur scheitert ebenfalls; Transportqualifikation geht verloren

`Satelliten-Avionik.txt` wird nach zwei echten Antworten mit demselben Mehrfachreferenzfehler für die gemeinsame Hardwarezeile abgelehnt. Die Antworten erkennen FDIR, Telecommand, Sensortypen und Reaktionsräder. Ein übernehmbarer Vorschlag entsteht jedoch nicht. Die erste Antwort nennt UART ohne die Einschränkung „UART-ähnlich“ aus der Quelle; die Registry-Vorauswahl liefert UART bereits als verpflichtenden registrierten Kandidaten. Damit ist die Unterscheidung zwischen erwähntem Protokoll und bestätigter konkreter Realisierung nicht ausreichend im Vorschlag erhalten. Es fand keine physische Modellzuweisung statt.

Evidence: `space-wire.json`, `space-source.txt` und terminaler Fehler in `manifest.json`.

## F5: Ausführlicher Roboter liefert Gesamtvorschlag mit falscher Instanz- und Rollenbildung

`Mobiler Service‑Roboter mit Greifarm und 360°‑Sensorik.txt` wird in zwei echten Qwen-Aufrufen vollständig verarbeitet. Alle 5019 Zeichen sind in den tatsächlichen Anfragen nachgewiesen. Der Bereich 8–12 Ultraschallsensoren bleibt richtig eine Kategorie ohne feste Stückzahl. Raspberry Pi 5 wird aus der eigenen Hauptrechner-Deklaration erkannt. CAN, UART, GPIO, PWM und ROS2 bleiben als getrennte registrierte Technologien erhalten; Bluetooth wird nicht zu einer erfundenen Variante erweitert.

Der Gesamtvorschlag ist dennoch nur teilweise brauchbar:

- Die allgemeine Auswahlliste „Mikrocontroller (STM32, Arduino, ESP32) für Echtzeitmotorik“ wird zu einer konkreten Instanz mit Stückzahl 1. Die Quelle bestätigt keine individuelle Auswahl oder exakte Zahl. Der Gesamtauftrag fordert die Übernahme als eines von zwei konkret benannten Geräten, ohne hierzu eine Auswahlfrage zu stellen.
- „Motorcontroller (z. B. Roboclaw, ODrive)“ wird als `CATEGORY/ACTUATOR` geführt. Der vorhandene Rollencheck erkennt das zusammengesetzte Wort Motorcontroller nicht als ausdrücklichen Controller. Die Controllerrolle darf nicht aus dem Aktor-Kontext abgeleitet werden.
- I²C bleibt UNRESOLVED; ebenso wird WLAN trotz bereits erkanntem WiFi als zusätzlicher ungeklärter Begriff ausgegeben. Die aktuelle Erkennung behandelt diese Schreibweisen nicht einheitlich. Dies ist ein Befund zur Normalisierung, keine Berechtigung für eine beliebige Protokollersetzung.
- Die Quelle beschreibt Navigation, Manipulation, Autonomie und Teleoperation ausführlich, die strukturierte Ergebnisliste enthält aber keine einzige FUNCTION. Der daraus zusammengesetzte Gesamtauftrag enthält folglich keinen entsprechenden Funktionsschritt. Pro Abschnitt werden höchstens acht wesentliche Komponenten erfasst; vollständige Übertragung bedeutet daher keine vollständige semantische Erfassung.

Evidence: `mobile_robot-proposal.json`, beide echten Aufrufe in `mobile_robot-wire.json`, Originalkopie und Integritätsprüfung in `audit.json`.

## Mögliche Reparaturrichtung, noch nicht umgesetzt

Quellenstellen müssen mehrere unterscheidbare, weiterhin exakt belegte Hardwareaussagen innerhalb einer gemeinsamen Zeile tragen können, etwa über geprüfte Teilspannen. Identische Geräte dürfen dabei nicht dupliziert werden. Gemischte Rollen dürfen nicht als pauschale OTHER-Gruppe verschwinden. Allgemeine Controllerarten und beispielhafte Alternativen dürfen ohne individuelle Deklaration keine bestätigten Instanzen werden. Anschließend sind dieselben Originaldateien mit echten Modellantworten erneut zu prüfen; eine bloße Lockerung des Validators wäre kein Nachweis.

Dieser Auftrag ist eine zusätzliche Prüfung. Es wurde bislang kein Anwendungscode geändert und keine neue Produktivversion ausgeliefert.
