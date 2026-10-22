# Abnahme des tatsächlichen gemeinsamen NIS-Laufs

Diese Liste operationalisiert die vorhandenen Nutzeraufträge und Projektverträge.
Sie ist kein bestandener Nachweis, erzeugt kein Modell und ersetzt keine Gates.
Alle Punkte anhand tatsächlicher gespeicherter Produktantworten prüfen.

1. Originalbytes und Originalhash, vollständige Quellenzitate, Kapitel-/Systemkontext
   und Fact-ID-Zuordnung erhalten. Fahrzeug: alle 168 formalen REQ-Kennungen.
   Robotik: alle zehn Profile 054–063 und deren 110 vollständige REQ-Zeilen;
   aktueller quellengeprüfter Ausgangsstand 221 Befunde. Frühere Gruppierungen
   nicht mit einer zwingenden Hardwareklassifikation verwechseln.
2. Primärinventar, bestätigte Nutzerantwort und ergänzende Referenz getrennt
   erhalten. `neu 9.txt` ersetzt weder ursprüngliche Stückzahlen noch den
   ursprünglichen Systemumfang. Neue Beispieldaten bleiben begründete
   `REFERENCE_ASSUMPTION` und werden regulär geprüft/übernommen.
3. Alle Quellenfunktionen und Anforderungen im kanonischen Modell nachweisen;
   passive Baugruppen und Software nicht als unbelegte ECU erzeugen. COMPOSITE
   erhält seine realisierenden Funktionen; ATOMIC erhält tatsächliche Ausführer.
4. Messung, Verarbeitung, Funktionsausgang, fachlicher Verbraucher, Steuerung,
   Stellbefehl und Ausführungsrückmeldung getrennt nachweisen. Kamera-Objektdaten
   müssen den erforderlichen fachlichen Verbraucher erreichen. Derselbe
   Ausführer darf eine logische Funktionsabhängigkeit verwenden; keine künstliche
   physische Selbstverbindung. Gateway/Transportstation ersetzt keinen Empfänger.
5. Jede gewählte Technologie und jeder physische Anschluss stammen aus der
   TechnologyRegistry und dem konkreten Entwurf. Lokale Messungen, Befehle und
   Feedback nicht durch unbestätigte Controller-/Diagnoserouten weiterleiten.
   Kodierung, Einheiten, Wertebereiche und explizite Rohcodes bewahren.
6. Nur CONFIGURATION-Werte als Auslegungsannahmen. Keine erfundenen EVIDENCE-
   oder REFERENCE-Bestätigungen, WCET, Hardwarequalifikation, Safetyfreigaben
   oder funktionale Fristen. Unbekannte Daten bleiben sichtbare Befunde.
7. Aktuellen akzeptierten Designstand und Revision über den regulären Wizard,
   Proposal-, Review- und Apply-Weg übernehmen. Keine handgeschriebenen
   Ersatzgeräte, Routen, Signale, Profile oder direkten SQL-Modelländerungen.
8. Routing, physische Topologie, Parameterherkunft, Capacity/Timing und
   Validation/Preflight anhand der tatsächlichen Projektartefakte prüfen.
   Transportnachweis unter Annahmen ist keine funktionale Timingakzeptanz.
9. Tatsächlich gespeicherte Simulationen beider Originale mit passender
   Projekt-/Job-/Snapshotidentität, vollständigem ALL-Scope, PASS-Konformität,
   null fehlgeschlagenen Routen und vollständigen beobachteten Signalen,
   Routen und Netzen prüfen. Vollständige Trace-Seiten sichern. Ausschlüsse
   nur nach dem vorhandenen Vertrag für ausdrücklich nicht geroutete
   FUNCTION_OUTPUT-Nachrichten; Inventar und fachliche Grenzen erhalten.
10. Abschließend vollständiger Release-Gate für das unveränderliche finale
    Image, `release-and-deploy.py` mit vollständigem passendem PASS-Receipt,
    tatsächliche Produktionsidentität, Gesundheit und betroffene Funktionen.
    Erst mit allen erfüllten Required Outcomes den Gesamtauftrag abschließen.

Die ursprünglichen Required Outcomes/Validation Requirements bleiben vollständig
in `../workload.json` enthalten. Normale Referenzannahmenfreigabe verleiht keine
fehlenden technischen oder normativen Nachweise.

Zusatz zur Inventarreparatur vom19.10.: Eindeutige Sensor-/Aktortypenlisten getrennt im akzeptierten Entwurf und am gespeicherten HardwareNode über `source_bindings.reference_member` nachweisen. Originalkind CATEGORY, Originalzitat und `REFERENCE_ASSUMPTION`/fehlende Hardwarequalifikation erhalten. Native Fortsetzung größerer Gruppen darf keine Zwei-Geräte-Gesamtgrenze erzeugen. Keine IO-Planung bei fehlender Inventarabdeckung. Das sind Abnahmekriterien, keine bereits bestandenen Originalprüfungen.
