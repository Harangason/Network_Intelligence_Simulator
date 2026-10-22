# Abnahme der unveränderten Fahrzeugdatei

Dies ist eine Prüfliste, kein ausgeführter Test und keine Ersatzmodellierung.
NIS muss alle Modellvorschläge, Zuordnungen und Verbindungen selbst erzeugen.

Quelle: `C:/Users/marti/PycharmProjects/Benchmark_Modelle/Fahrzeug komplett.txt`,
SHA256 `86865975c689643d9b07ea73e21d68fa6f4a3a8770402ffb537dba2d7ecdf4d7`.
Neues Testprojekt: `20261016122109077-dc3a1aeb`. Die Quellenzeilen beziehen sich
auf die unveränderte Originaldatei; die Datei wird über den normalen Uploadweg
übergeben. Produktionsversion und tatsächliche Modellaufrufe zusätzlich sichern.

1. Die Originalübertragung enthält alle 19.088 Zeichen und 168 unterschiedlichen
   REQ-IDs. Alle typisierten Geräte, Funktionen und Anforderungen behalten ihre
   Originalzitate bis zur überprüften Wizard-Übernahme. Kein Abschneiden oder
   erneutes alleinstehendes Parsen einer kurzen Zusammenfassung.
2. Sensorikliste (Zeile 76) und Aktorikliste (Zeile 78) sind Gerätegruppen,
   keine konkreten Stückzahlen. Die menschlich bestätigte Mindestzahl von eins
   je genanntem Typ ist ausdrücklich eine Untergrenze. Sie beseitigt weder
   zusätzliche Bedarfsfragen noch die Redundanzanforderungen, beispielsweise
   REQ-SAFE-15 zu redundanten Positionssensoren der Lenkung (Zeile 479).
3. Die ADC-Aufgaben Sensorfusion, Perception, Planning und Vehicle Control
   (Zeilen 312–318) bleiben Funktionen auf ihrem ausdrücklich genannten Host.
   Kein zusätzlicher fiktiver Controller wird zur Vereinfachung angelegt.
   NIS muss interne funktionale Übergaben von externen Transporten unterscheiden.
4. REQ-ADC-02 (Zeile 342) fordert eine Objektliste mit Position, Geschwindigkeit
   und Klassifikation. Gespeicherte NIS-Vorschläge müssen diese Dateninhalte und
   ihren fachlichen Verbraucher nachvollziehbar machen. Ein Controllerstatus
   oder Gateway als Transportstation erfüllt diese Anforderung nicht.
5. Die Kette Sensor → Verarbeitung/Fusion → Planung/Steuerung → Stellbefehl →
   Aktor muss in NIS erzeugten Objekten und Beziehungen überprüfbar sein.
   Sender, fachliche Empfänger, Eigentümer und physischer Transport dürfen
   nicht durch Namensähnlichkeit oder den ersten vorhandenen Controller ersetzt
   werden. Die Batterieaspekte Temperatur, Spannung und Stromstärke stammen
   zusätzlich aus `user-amendment.txt`, nicht aus manuell erzeugten Modellzeilen.
6. REQ-FUS-01 bis -04 (Zeilen 558–561) nennen Radar-/Kamera-Synchronisation,
   IMU-, Raddrehzahl- und Lidar-Daten. Vorhandene Anforderungen bleiben auch
   bei noch fehlender Algorithmus-, Clock- oder Codec-Evidence sichtbar.
   NIS muss echte Lücken gezielt erfragen; keine erfundene Implementierung.
7. Jede Übernahme erfolgt über den vorgesehenen Vorschlags-/Freigabeweg. Kein
   direktes Datenbank-, Modell-, Routen- oder Signalpatching. NIS-eigene
   automatische Änderungen gegebenenfalls mit Vorher/Nachher und Herkunft sichern.
8. Routing, physisches Netzwerk, Parameterherkunft, Capacity & Timing und
   Validation/Preflight müssen ihre echten Gates erfüllen. Laufzeit-/Buslast-
   Evidence beweist keine funktionale Verarbeitung oder Safety-Freigabe.
9. Erst ein tatsächlich abgeschlossener, gespeicherter Simulationsjob und
   geprüfte Kommunikation/Signale belegen die Simulation. Job-ID, Umfang,
   beobachtete Daten und Empfänger sichern. Echte offene Fachentscheidungen
   einschließlich NIS-Rückfragen als konkrete Blocker melden; kein voller PASS,
   solange Pflichtschritte oder fachliche Verbindungen fehlen.
