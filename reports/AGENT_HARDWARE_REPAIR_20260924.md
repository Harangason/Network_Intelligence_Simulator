# Freier Hardwareauftrag: Reparatur und Stabilisierung

## Ausgangsfehler

`Erstelle eine ECU für die Datenerfassung des Fahrzeugs` geriet in die allgemeine
Sprachmodellplanung und endete nach einem Planungstimeout. Die Runtime hatte
zwar einen Goal/Plan gespeichert, führte diesen einfachen Auftrag aber nicht
deterministisch aus. Der abgefangene Timeout erreichte die zentrale
Fehlerklassifikation nicht.

## Änderung

- Eng begrenzte, vollständig erkannte Einzelaufträge für ECU, Controller und PLC
  erreichen einen registrierten Core-Adapter ohne Sprachmodellaufruf.
- Der Core verlangt für diese Controller eine Funktion und einen Betriebsstatus.
  Fehlende Statusanschlusstechnik und Statuszyklus werden deshalb konkret
  erfragt: `WAITING_FOR_ENGINEERING_DECISION`. Es gibt keinen erfundenen Bus,
  keinen Automotive-Fallback und keine abgeschwächte Validierung.
- Eine Antwort wie `Statusanschluss I2C, Statuszyklus 100 ms` setzt denselben
  projektgebundenen, in SQL gespeicherten Workload fort, auch nach einem Reload.
  Der Statuszyklus wird nicht als Abfragezyklus der Datenerfassung ausgegeben.
- Der vorhandene Geräteklassifikations-/Statusgenerator erzeugt einen gemeinsam
  validierten Vorschlag für Hardware, Funktion, Schnittstellen, Statusnachricht
  und Statussignal. Die bestehende menschliche Review-/Apply-Grenze bleibt bestehen.
- Gleiche aktuelle Vorschläge werden wiederverwendet. Bereits angelegte Hardware
  mit identischer Anforderung wird nicht erneut angelegt.
- Datenquellen, Erfassungsmodus, Statusempfänger und Netzzuordnung bleiben sichtbare
  offene Anforderungen. Es wird keine Route und kein betriebsfähiger Erfassungspfad
  behauptet. Die bestehende Statusvorlage ist ausdrücklich prüfpflichtig.
- Komplexere Eingaben bleiben in der allgemeinen Planung. Bei Planungstimeout
  gibt es einen begrenzten Wiederholungsversuch innerhalb des bisherigen
  Gesamtbudgets. Bereits ausgeführte Werkzeuge werden dafür nicht wiederholt.
  Ein weiterer Timeout wird als `ENGINEERING_EXECUTION_TIMEOUT` gespeichert;
  Completion darf daraus keinen Erfolg oder fertigen Review ableiten.
- Ein bloßes Klassifikationswerkzeug gilt nicht mehr als ausführbare
  Hardware-Erstellungsfähigkeit. Findings werden im Runtime-Ergebnis erhalten.

## Verifikation

211 Tests bestanden, ausgeführt ausschließlich über
`scripts/run-isolated-tests.py` mit Wegwerf-PostgreSQL. Geprüft wurden die
Agenten-Testmodule sowie Runtime, MCP, Capabilities, Controllerstatus,
Gerätekommunikation, Proposal-Abhängigkeiten und universeller Agent-I/O.

Neue Integrationstests prüfen:

- Fahrzeug-ECU, Roboter-Controller und Anlagen-PLC ohne erreichbaren Reasoner;
- fehlende Parameter, Fortsetzung unter derselben Workload-ID;
- echte MCP-Aufrufe, Proposal-Validierung, Review und kanonische SQL-Übernahme;
- Wiederholung ohne doppelte Hardware und Isolation zwischen Projekten;
- HTTP-Chat, neuer HTTP-Client als Reload, SQL-Kontextwiederherstellung sowie
  echte Review-/Apply-Endpunkte;
- Ablehnung der Teilinterpretation komplexerer oder verneinter Befehle;
- klassifizierten, gespeicherten Timeout und begrenzten Planungs-Retry.

Nur die Modellinferenz wurde in den neuen Integrationstests durch einen
absichtlich nicht verfügbaren Reasoner ersetzt. Core, MCP, SQL und schreibende
HTTP-Antworten wurden nicht gemockt. Keine Browser-E2E-Prüfung wird daraus abgeleitet.

Zusätzlich: neun bearbeitete Pythondateien syntaktisch geprüft; `git diff --check`
ohne Fehler. Eine bestehende Pydantic-Warnung über das Feld `validate` bleibt.

JUnit: [agent-hardware-repair-20260924.xml](agent-hardware-repair-20260924.xml)

## Grenze der Aussage

Dies ist die Reparatur des konkreten freien Hardwarepfads und seiner
Timeoutbehandlung, kein Nachweis sämtlicher Beispiele der vollständigen
Engineering-Assistant-Runtime-Architektur. Der direkte Parser unterstützt einen
begrenzten Satz eindeutiger Einzelgeräteformulierungen; andere Aufgaben verwenden
weiter den allgemeinen Agenten. Unbekannte Technik wird nicht geraten.

Die Änderungen sind lokal. Kein Deployment und kein vollständiger Release-Gate-
Lauf wurden durchgeführt. Die bereits laufende Produktinstanz enthält diese
Reparatur dadurch noch nicht.
