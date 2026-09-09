# Abgasnachbehandlung: Schnittstellenstatus

Geprüft am 09.09.2026 anhand des aktuellen Projekt-Exports von Backend-Port 15050, Projekt `network-project-20260909082213746-780a13ef`. Evidenz: `verification/2026-09-09-interface-status-live.json`. Dies ist eine Modell- und Routingprüfung, kein neuer Simulationsnachweis.

## CAN-FD IO

Interface `0ac88cdc-bc06-44ff-8d3a-9146fa14b619` ist der Funktion und Hardware Abgasnachbehandlung zugeordnet. Es besitzt keine eigenen Nachrichten, wird aber als Empfangsschnittstelle von zwei freigegebenen Routen verwendet:

- EGRValvePosition → Abgasnachbehandlung, Signal AGRVentilstellung, Bus Antrieb_03.
- ExhaustGasTemperature → Abgasnachbehandlung, Signal Abgastemperatur, Bus Antrieb_03.

Beide gespeicherten Routenvalidierungen sind gültig und warnungsfrei. Der Baum zeigt nur untergeordnete eigene Nachrichten; deshalb erscheint die Schnittstelle leer. Der Punkt ist ein Blatt-Symbol, kein Fehlerstatus. Die Schnittstelle darf nicht als unbenutzt gelöscht werden.

## LIN IO

Interface `1b5f446f-d4c0-44a0-a875-bc3002834418` besitzt die Nachricht „Abgasnachbehandlung LIN IO Befehl“, 100 ms, DLC 2. Zwei freigegebene Routen senden sie an den Schaltausgang auf Antrieb_05 und das Stellglied auf Antrieb_06. Die Nachricht enthält jedoch **keine definierten Signale**. Damit ist ein Transport modelliert, aber die Bedeutung der Befehlsbits nicht spezifiziert. Der Wizard erzeugt diesen Transport aus den Aktorketten ohne Befehlssignale (`backend/engineering/agent_tools/wizard_generation.py`).

Drei Empfangsrouten liefern Harnstofffüllstand, Schaltausgangstatus und Stellgliedstatus. Alle fünf gespeicherten LIN-Routenvalidierungen sind gültig; Harnstofffüllstand hat die Warnung `TIMEOUT_BELOW_CYCLE_BUDGET`: Zyklus 500 ms, erlaubter Jitter 5 ms, Timeout 500 ms.

## Weitere Inkonsistenzen und konkrete Lösungen

1. Empfang ist im Strukturbaum unsichtbar. Empfangene Nachrichten als Referenzen mit Quelle anzeigen; zusätzlich TX-/RX-Anzahl und tatsächliche Busse. Keine Duplikate kanonischer Nachrichten erzeugen.
2. Fehlende LIN-Befehlssemantik explizit als unvollständig kennzeichnen. Schaltbefehl und Stellwert benötigen fachlich festgelegte Datentypen, Bitpositionen, Einheiten, Wertebereiche und Empfängerzuordnung. Der Generator darf aus der Rückmeldungsgröße nicht automatisch eine vollständige Befehlsspezifikation ableiten.
3. Harnstoff-Timing fachlich auflösen: Bei beibehaltenem Zyklus und Jitter muss das Timeout mindestens das 505-ms-Budget abdecken; andernfalls muss der Sendeplan angepasst werden. Keine automatische Lockerung der vorhandenen Anforderung.
4. Physische Anschlüsse tragen noch `UNMAPPED`, obwohl die Routenvalidierung physische Pfade als zugeordnet nachweist. Status aus aktueller Bindung und Validierung ableiten, getrennt von Simulationsstatus.
5. Beide Schnittstellen sind `approved`/`reviewed`, ihr Lifecycle ist `draft`; Transportkonfigurationen enthalten `PROPOSED`. Diese unterschiedlichen Zustandsachsen dürfen nicht als gemeinsamer Nachweis „vollständig funktionsfähig“ präsentiert werden.

Die Prüfung hat keine Projektobjekte oder fachlichen Anforderungen verändert.

## Umsetzung nach Freigabe

Release `ee7fc6a30a2c` ist auf Port 13500/15050 bereitgestellt.

- Strukturbaum zeigt TX-/RX-Routen, Nachrichtenreferenzen, Signale, physische Busnamen und gespeicherte Validierungshinweise. Die kanonische Nachrichten-Zuordnung bleibt erhalten.
- Physische Anschlüsse zeigen ihre tatsächliche Busbindung statt des widersprüchlichen Standardwerts UNMAPPED. Fehler-, Überlast- und Veraltet-Zustände bleiben zusätzlich sichtbar. Busbindung ist kein Laufzeitnachweis.
- Generierte Aktorbefehle ohne kanonische Signale erhalten den maschinenlesbaren Routingfehler `COMMAND_SIGNALS_MISSING`. Damit steht der Befund auch API- und Agent-Aufrufern zur Verfügung. Der Baum markiert die Nachricht als unvollständig.
- Die zwei bestehenden LIN-Befehlsrouten wurden neu validiert und stehen jetzt auf CONFLICT. Nachfolgende Workflow-Ergebnisse werden dadurch als veraltet angezeigt. Vorhandene Freigaben bleiben als separate historische Zustandsachse erhalten.
- Harnstoff-Timingwarnung erscheint an der Empfangsroute. Keine Änderung von Timeout, Zyklus, Befehlspayload oder fachlichen Anforderungen.

Validierung: TypeScript-Prüfung und Produktionsbuild erfolgreich, 34 Routingtests und drei gezielte Frontendtests bestanden. Browserprüfung am aktuellen Projekt ohne JavaScript-Fehler bestanden: CAN 0 TX/2 RX, LIN 2 TX/3 RX, Busnamen, Signale, Timingwarnung und physische Busbindung. Evidenz: `verification/2026-09-09-interface-status-browser.json`, `verification/2026-09-09-interface-status.png`, `verification/2026-09-09-command-validation.json`.

Fachlich offen bleiben die konkrete Befehlsspezifikation und die Entscheidung über den Harnstoff-Sendeplan bzw. Timeout. Die neue Fehlererkennung ersetzt deren Festlegung nicht.
