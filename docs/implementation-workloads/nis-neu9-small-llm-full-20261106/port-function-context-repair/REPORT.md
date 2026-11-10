# Anschlussplanung: Funktionskontext vor physischer Festlegung

Die bisherige Reihenfolge entschied und schloss physische Anschlüsse, bevor die ursprünglichen Funktionen ihren ausführenden Geräten zugeordnet waren. Der globale Quelltext war vorhanden; die aufgelöste Funktionsverantwortung fehlte am entscheidenden Planungsschritt.

Die Korrektur plant Funktionen und funktionale Abhängigkeiten nach dem vollständigen Hardwareinventar und vor dem Anschlussbedarf. Eine verlustfreie Sicht ergänzt die exakten Geräte-, Eigentümer- und ursprünglichen Funktionsfakten einschließlich übergeordneter zusammengesetzter Funktionen. Sie erzeugt keine Anschlüsse, keine Geräte und keine Standardtechnologien. Öffentliche Schemas, Validatoren und Modellgrenzen bleiben unverändert.

Nachweise:
- Normaler Planer mit kontrolliertem Transport: 2 RED vor der Korrektur; 23 PASS danach einschließlich bestehender Anschlussgruppenprüfungen.
- Isolierter breiter Lauf: 331 PASS / 4 FAIL. Drei direkte Testfixtures fehlten die im Produkt bereits vorhandene öffentliche Normalisierung; eine Schemaerwartung setzte noch eine einzelne SENSOR-Alternative voraus. Die genauen negativen Assertions bleiben erhalten. Gezielte Wiederholung: 12 PASS, darunter alle vier zuvor fehlgeschlagenen Fälle.
- Insgesamt 335 verschiedene Fälle PASS über die dokumentierten Läufe. Kein einzelner vollständig grüner 335er-Lauf behauptet; Original-FAIL-XML bleibt erhalten.
- Echte qwen3.5:9b-Gegenprobe: zwei selbst erstellte Quellen, sechs regulär abgeschlossene Modellantworten. Drei verschiedene LIN/CAN-FD/Ethernet-Anschlüsse beziehungsweise zwei I2C/Modbus-RTU-Anschlüsse. Die Gegenprobe stoppt vor dem ersten Parameterrequest. Offene Hardwarebefunde bleiben dokumentiert. Keine Original-, Modell- oder Simulationsabnahme daraus abgeleitet.
- AST-Vergleich bestätigt unveränderten restlichen Reasoner außerhalb Planer und neuer Kontextprojektion. Hashgebundene Rohantworten, Quellen- und Testnachweise stehen in source-scope-proof.json und regression-aggregate.json.

Der frühere neu9-Lauf84730 ist serverseitig CANCELED; Auslöser und Client-Exitcode bleiben unbekannt. Der veraltete Diagnose-Stack wurde vollständig wiederherstellbar archiviert und exakt stillgelegt; keine Images entfernt, PREPARED-Receipt unverändert erhalten. Die Produktion wurde nicht geändert.

Offen: vollständiger neuer neu9-Lauf, quellengebundene Review/Apply-Schritte, kanonisches Modell, erfolgreiche ALL-Simulation mit vollständigen Traces, vollständiges Releasegate und produktive Übernahme des exakt geprüften Images. Alle sieben Ergebnis- und sieben Prüfanforderungen bleiben erhalten. Der allgemeine Broadcast ist geschlossen.
