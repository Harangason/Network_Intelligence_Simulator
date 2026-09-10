# Umsetzung der LIN- und Signalanalyse – 10.09.2026

Die freigegebenen Korrekturen aus dem [Referenz- und Bremsbus-Audit](I:/PycharmProjects/My_first_Network_Simulator/docs/lin-reference-and-brake-bus-audit-2026-09-10.md) sind im laufenden Projekt `network-project-20260910042736034-d11591d0` aktiv. Frontend und Backend verwenden Build `8ef09506f01b`. Dieser Bericht beschreibt den tatsächlich geprüften Umfang einschließlich der verbleibenden Nachweisgrenzen.

## Datenkorrektur und Erzeugung

278 nachweisbar vom bisherigen Generator verursachte Signaldefinitionen wurden transaktional berichtigt: 97 numerische Signale mit erfundenem Fehlercode, 66 Quality-Signale, 66 Alive-Counter und 49 als Zustand fehlklassifizierte physikalische Rückmeldungen. Die Herkunftsprüfung begrenzt die Reparatur auf bekannte Generatormuster. Vorherige Definitionen sind am Signal als Provenienz erhalten. Importierte oder individuell definierte Zustandsdomänen werden nicht pauschal ersetzt.

Messgrößen behalten Einheit, Skalierung und Wertebereich auch dann, wenn der Name „Status“ enthält. Begleitsignale erhalten eigene Domänen. Die Bitprüfung berücksichtigt die tatsächlichen Rohcodes einschließlich expliziter Reserve- und Fehlercodes. Freie Kodierungen werden nicht automatisch zu Fehlercodes erklärt. Die Anzeige ergänzt keine erfundenen Zustandslisten mehr.

Alle 725 Signale bestehen die aktuelle rechnerische Konsistenzprüfung: 0 Fehler, 0 offene Kodierungsbefunde. Bitpositionen, Bitlängen, Faktoren, Offsets, Nachrichten-IDs und physische Topologie blieben bei dieser Reparatur unverändert. Alle 386 Routen wurden erneut validiert und freigegeben. Wiederholtes Anwenden erzeugt 0 weitere Änderungen.

## Bewertung und Simulation

Capacity & Timing und die an Intelligence übergebenen Netzdaten unterscheiden jetzt fünf Fragen:

1. Passt die Nutzlast einschließlich ihrer Kodierung?
2. Wie hoch ist der nominale beziehungsweise durch Ereignisraten begrenzte Kapazitätsbedarf?
3. Ist der Busplan unter seinen ausgewiesenen Annahmen ausführbar?
4. Überschreitet das Stressszenario das Planungsziel?
5. Ist die geforderte funktionale Reaktionszeit nachgewiesen?

Ein Stressfaktor beschreibt keine gleichzeitig sendenden Teilnehmer. Eine Bus-Antwortgrenze allein weist keine Bremsfunktion nach. Die letzte Frage verlangt bestätigte Anforderungen sowie Abtast- und Aktuationszeiten. Fehlende Angaben bleiben sichtbar offen.

CYCLIC, EVENT, ON_REQUEST und MIXED verwenden dieselbe Profilprüfung in Dimensionierung und Simulation. Nichtzyklische Profile brauchen einen Mindestabstand und einen Auslöser. On-change-Verkehr vergleicht kodierte Signalwerte. Explizite Ereignisse und Anfragen werden anhand ihrer Szenariozeitpunkte ausgeführt; ohne Anfragen entstehen keine zyklischen Ersatzantworten. MIXED unterstützt einen Heartbeat unter Beachtung des Mindestabstands.

Diese Regeln sind in [COMMUNICATION_DESIGN_CONTRACT.md](I:/PycharmProjects/My_first_Network_Simulator/docs/COMMUNICATION_DESIGN_CONTRACT.md), den Projektanweisungen und den Vorgaben für den lokalen KI-Reasoner verankert. Das ist eine überprüfbare Erzeugungs- und Validierungsregel, kein neu trainiertes Modell.

## Aktueller Bremsbus statt historischer Sammelbus

Die frühere Aussage „acht Sensor-Sender plus Steuergerät“ bezog sich auf den damaligen Sammelbus. Die inzwischen bestätigte räumliche Aufteilung bleibt erhalten. Aktuell gilt:

| Zweig | Sensor-Sender | Nominaler Bedarf | Reservierte Slots |
| --- | ---: | ---: | ---: |
| Bremsregelung LIN VR | 2 | 13,33 % | 20,00 % |
| Bremsregelung LIN VL | 2 | 13,33 % | 20,00 % |
| Bremsregelung LIN HL | 2 | 13,33 % | 20,00 % |
| Bremsregelung LIN HR | 1 | 6,67 % | 10,00 % |
| Bremsregelung LIN HR 02 | 1 | 6,67 % | 10,00 % |
| Bremsregelung LIN Ort offen | 1 | 6,67 % | 10,00 % |

Jeweils kommt das Steuergerät hinzu. Der separate Aktorzweig „Bremsregelung LIN 03“ hat 9,48 % nominalen Bedarf und 15 % Slotreservierung. Die beiden bestehenden HR-Anschlüsse wurden nicht ungefragt zusammengelegt; eine unbekannte Position wurde nicht erfunden. Im Browser geprüft: VR zeigt 2 Sender, 3 Teilnehmer, 2 Nachrichten und 2 rechnerisch passende Signale mit jeweils 2 Byte Payload. Die Signale wurden nicht verkleinert, um einen Lastwert zu erreichen.

## Verifikation

- 153 Backendtests für Kodierung, Dimensionierung, Laufzeit, Trace-Export, Transport und Raumaufteilung bestanden; nach der letzten Ergänzung zur Rohcode-Bitbreite nochmals 30 gezielte Tests bestanden.
- 74 Workflow-, Wizard- und Netzszenentests bestanden.
- 69 Frontendtests sowie TypeScript-Prüfung und Next-Produktionsbuild bestanden.
- SQL-Test mit vollständiger Projektkopie: veraltete Änderungsvorschau abgewiesen, erzwungener Fehler während der zweiten Signaländerung vollständig zurückgerollt, erfolgreiche Reparatur und wiederholtes Anwenden geprüft. Kodierung und Topologie vor/nach der Reparatur verglichen.
- Anwendung im aktuellen Projekt: 278 Korrekturen, 725 konsistente Signale, 386 gültige und freigegebene Routen. Kein Wiederherstellen einer älteren Projektkopie über den aktuellen Stand.
- Live-Preflight: 0 Fehler, 12 Hinweise, Simulation ausführbar.
- Live-Smoke-Test `71ff1c0df0a84211bbc6436c3dc3a092`: abgeschlossen, 3.895 Trace-Ereignisse, 311/311 Nachrichten und 725/725 Signale erfasst, 0 Modellfehler und 0 Modellwarnungen. Keine fehlenden beobachteten Routen oder Netze. Die Laufzeitbewertung konnte 376/386 Routen beurteilen; 10 bleiben nicht bewertet. Deshalb ist der Gesamtstatus WARNING und keine Konformitätsfreigabe.
- Intelligence neu berechnet, nicht veraltet; getrennte Bewertung für alle 116 Netze enthalten. Alle neun Workflow-Schritte referenzieren den aktuellen Projektstand.
- Geöffnete Netzdetails im laufenden Browser auf Inhalt und Darstellung geprüft.

Maschinenlesbare Belege: [Live-Reparatur](I:/PycharmProjects/My_first_Network_Simulator/backend/runtime/signal-integrity-live.json), [SQL-Prüfung](I:/PycharmProjects/My_first_Network_Simulator/backend/runtime/signal-integrity-sql.json), [Workflow- und Laufnachweis](I:/PycharmProjects/My_first_Network_Simulator/backend/runtime/lin-analysis-implementation-verification.json).

## Verbleibende Grenzen

Die globale Kapazitätsbewertung bleibt WARNING: Drei LIN-Zweige überschreiten im Stressszenario das 60-%-Planungsziel; für fünf Ethernet-Netze bleibt die Port-/Technologieanalyse erforderlich. Das ist keine nominale LIN-Überlast von 310 oder 405 %. Die funktionalen Reaktionszeiten bleiben ohne bestätigte Anforderungen unbewiesen.

ON_REQUEST unterstützt explizite externe Anwendungseingaben im Szenario. Eine über den Bus transportierte Anfrage benötigt zusätzlich ein kausales Anfrage-/Antwortmodell; dessen vollständige Umsetzung wird hier nicht behauptet. Auch funktionale Nachweise über mehrere Busabschnitte bleiben offen. Bestehende zyklische Statusmeldungen werden ohne bestätigte Auslöser und Anforderungen nicht automatisch in reine Ereignismeldungen umgewandelt.

Vollständige DBC-/ARXML-/LDF-Ausgaben sind weiterhin ein nachgelagerter Umsetzungsschritt. Der Datenvertrag dafür ist festgehalten; dieser Stand erklärt weder einen vollständigen Export noch eine funktionale Bremsfreigabe. Die Audi-OBD-Beispiele werden weiterhin als Diagnose-CAN-Referenz behandelt und nicht als LIN-Spezifikation.
