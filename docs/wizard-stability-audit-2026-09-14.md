# Wizard-Stabilität: Befund und Umsetzungsplan

Stand: 14.09.2026. **Analyse und Planung; noch keine Umsetzung der nachstehenden Korrekturen.**

## Auftrag und Prüfgrundlage

Der Auftrag ist, die wiederkehrenden Wizard-Abbrüche gründlich zu analysieren und zuerst einen belegten Befund sowie einen konkreten Plan zur Stabilisierung vorzulegen. Der Benutzerweg muss einschließlich der neun Projektschritte abgesichert werden. Dieser Bericht ersetzt keine Freigabe des aktuellen Builds.

- Repository: `I:\PycharmProjects\My_first_Network_Simulator`, HEAD `43089d0`, mit bereits vorhandenen lokalen Änderungen. Die Untersuchung bezieht diese Änderungen ein; HEAD allein beschreibt den untersuchten Stand daher nicht vollständig.
- Projekt: `network-project-20260914053234318-2da25012` / NIS Projekt 2.
- Auftrag: `bf32c5c7-e5df-4931-937a-9db52571d5fd`.
- Aktiver Routingvorschlag: `d5ee7a8b-53c2-4af5-be4c-91fd4a21d047`.
- Fachliche Grundlage: `SPATIAL_ARCHITECTURE_CONTRACT.md`, `COMMUNICATION_DESIGN_CONTRACT.md`, `NETWORK_NAMING_CONTRACT.md`.

Es wurden keine Produktdateien geändert, keine Vorschläge übernommen und keine schreibenden Live-APIs oder Datenbanktests ausgeführt. Gespeichert wurden ausschließlich Analysebelege und dieser Bericht. Vorhandene lokale Änderungen stammen aus vorangegangenen Arbeiten.

## Ergebnis zum aktuellen Abbruch

Der Auftrag stoppt zu Recht an einer technischen Inkonsistenz. **Die Erzeugung dieser Inkonsistenz, ihre fehlende Anzeige und die Wiederaufnahme sind jedoch fehlerhaft.**

Der aktuelle Routingvorschlag enthält 838 Routen; 827 bestehen die Validierung, 11 nicht. Bei allen elf wird `Kombiinstrument_CAN_FD_IO` als logische Kommunikationsschnittstelle mit einem physischen Ethernet-Anschluss kombiniert. Der gespeicherte physische Weg ist vorhanden; es fehlt nicht allgemein an einer Gatewayverbindung.

Betroffene Sender zum Kombiinstrument: Elektromotorsteuerung, Getriebesteuerung, Motorsteuerung, Batteriemanagement, Energieversorgung, Allradsteuerung, Bremsregelung, Daempferregelung, Hinterachslenkung, Lenkung und Reifendruckkontrolle.

Die UI meldet nur einen angehaltenen Routingvorschlag. Inzwischen existieren drei Vorschläge mit jeweils 838 Einträgen. Keine dieser Wiederholungen hat den fachlichen Konflikt gelöst. Da noch keine Routen übernommen wurden, sind die angezeigten 0 % allein kein Beweis für verlorene Daten; es fehlt eine klare Unterscheidung zwischen erzeugt, gültig, geprüft und übernommen.

Das Modell umfasst aktuell 552 Hardwareteilnehmer, 90 Funktionen, 655 logische Interfaces, 653 Nachrichten und 1.404 Signale. Die neun Projektschritte dürfen nicht mit den sechs Eingabeseiten des Auftragsdialogs verwechselt werden.

## Bestätigte Fehler und Lücken

P1 bedeutet: vor der nächsten Abnahme der Wizard-Durchgängigkeit zu korrigieren. P2 bedeutet: für eine belastbare Release-Absicherung ebenfalls erforderlich. Prioritäten sind keine Aussagen über einen Sicherheitsvorfall.

### F01 · P1 · Logische und physische Empfängerschnittstelle werden getrennt ausgewählt

**Beleg:** [generation.py:269](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/routing/generation.py:269) bevorzugt ein logisches Zielinterface passend zur Quelltechnologie. [generation.py:337](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/routing/generation.py:337) bestimmt erst danach den physischen Zielport anhand des letzten Gatewayabschnitts. Eine erneute Abstimmung fehlt.

Der echte Generator wurde mit kontrollierten Datenzugriffen im Speicher geprüft: Quelle CAN-FD, Empfänger mit lokalem CAN-FD und Ethernet; Ergebnis war ein logisches CAN-FD-Interface zusammen mit dem Ethernet-Port. Dies entspricht dem Livefehler `DESTINATION_LOGICAL_PROTOCOL_MISMATCH`.

**Korrektur:** Funktion, Gerät, logisches Interface, physischer Port, Netz und Transport gemeinsam auflösen. Der Empfang muss zum letzten tatsächlichen Streckenabschnitt passen. Mehrdeutige Zuordnungen bleiben als konkrete Entscheidung offen. Funktionale Partner, Nachrichten, Signale und Kodierungen bleiben erhalten. Die bestehende Ablehnung inkonsistenter Routen wird nicht gelockert.

**Abnahme:** Gemischte CAN-FD/Ethernet-Empfänger mit lokalem IO, direkte Wege und mehrere Gatewayabschnitte. Der aktuelle unveränderte Auftrag erzeugt keine dieser elf Protokollinkonsistenzen; verbleibende andere Befunde werden einzeln ausgewiesen.

### F02 · P1 · Signalauswahl kann die physische Framegröße fälschlich verkleinern

**Beleg:** [validation.py:530](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/routing/validation.py:530) summiert bei vorhandenen `signal_ids` deren Bitlängen und verwendet dann nicht mehr die vollständige Nachrichtenlänge. Die Größenprüfung bezieht sich anschließend auf das Quellprotokoll.

Isolierte Reproduktion: Dieselbe 64-Byte-Nachricht auf CAN wird mit einem ausgewählten 1-Bit-Signal als gültiger 1-Byte-Payload bewertet. Ohne Signalunterauswahl wird sie korrekt wegen 64 Byte > 8 Byte abgelehnt. Auch die dort ermittelte Last fällt entsprechend unterschiedlich aus. Dies ist ein nachgewiesener Fehler der Routingvalidierung; daraus wird nicht pauschal abgeleitet, dass jede andere Kapazitätsberechnung denselben Fehler hat.

**Korrektur:** Physische Nachrichtenlänge und semantisch ausgewählte Werte getrennt behandeln. Jeden durchlaufenen Transportabschnitt prüfen. Kleinere weitergeleitete Frames benötigen eine eigene explizite Kodierung/Transformation. Auswahl weniger Signale allein ändert weder DLC noch Übertragungslast des bestehenden Frames.

**Abnahme:** Unveränderte DLC bei Signalunterauswahl; korrekte Protokollgrenzen an jedem Abschnitt; explizites Repacking gesondert geprüft; Multicast zählt keine mehrfachen physischen Sendungen. Kapazität, Schedule und funktionale Timingfreigabe bleiben getrennt.

### F03 · P1 · Ein Fortsetzungsweg verliert das Workflowziel

**Beleg:** [agent-chat-core.tsx:2174](I:/PycharmProjects/My_first_Network_Simulator/frontend/src/components/agent-chat-core.tsx:2174) sendet nach Routingfreigabe `workflowTarget` als eigenes Feld. [route.ts:14](I:/PycharmProjects/My_first_Network_Simulator/frontend/src/app/api/agent/chat/route.ts:14) übernimmt dieses Feld nicht. Der backendseitige Ablauf erwartet stattdessen `Ziel: ...` im Text ([engineering_agent.py:208](I:/PycharmProjects/My_first_Network_Simulator/backend/agent_core/core/engineering_agent.py:208)); der Text dieses UI-Wegs hat ein anderes Format.

**Folge:** Die deterministische Fortsetzung bis zum Ziel wird nicht ausgewählt. Andere Fortsetzungsbuttons können funktionieren, weil sie zufällig das erwartete Textmuster verwenden.

**Korrektur/Abnahme:** Ein strukturiertes Start-/Fortsetzungsprotokoll mit gespeichertem Auftrag, Ziel und Revision. Einzelprüfung, Sammelfreigabe, manuelles Fortsetzen und Wiederaufnahme müssen denselben validierten Übergang auslösen. Steuerung darf nicht von der Formulierung eines Satzes abhängen.

### F04 · P1 · Wiederholungen erzeugen doppelte oder verwenden veraltete Vorschläge

**Beleg:** [run_status.py:43](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/agent_tools/run_status.py:43) hängt Fortsetzungstext unter einer separaten Überschrift an. [wizard_generation.py:604](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/agent_tools/wizard_generation.py:604) entfernt beim Fingerprint nur die Überschriftszeile. Der verbleibende Fortsetzungstext verändert die Identität desselben Auftrags. [conversation.py:140](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/agent_tools/conversation.py:140) enthält dasselbe Muster. Die drei Livevorschläge haben unterschiedliche Fingerprints.

Umgekehrt fehlen im Routingfingerprint relevante Änderungen an logischen Interfaces/Funktionen sowie die Generatorversion. Ein Treffer wird unabhängig vom Validierungsergebnis wiederverwendet. Alte ungültige Vorschläge werden nicht konsequent durch den aktuellen ersetzt.

**Korrektur:** Fachliche Eingabe unveränderlich und strukturiert speichern. Operationsidentität aus Projekt, Auftragsrevision, Schritt, allen relevanten Quellrevisionen und Generatorversion bilden. Wiederholung desselben Zustands erzeugt keinen neuen Vorschlag; korrigierte Eingaben erzeugen oder revalidieren ausdrücklich einen Nachfolger. Ein ungültiger unveränderter Vorschlag bleibt mit seinen Befunden sichtbar, statt endlos neu erzeugt zu werden.

**Abnahme:** Doppelklick, verlorene Antwort und unterschiedliche Fortsetzungswege ergeben eine aktive Vorschlagsrevision. Änderungen am Zielinterface invalidieren den alten Vorschlag. Alte Vorschläge bleiben nachvollziehbar, aber nicht parallel als aktuelle Entscheidungen offen.

### F05 · P1 · Routingfehler und strukturierte Rückfragen erreichen die Wizardansicht nicht zuverlässig

**Beleg Fehleranzeige:** [agent-chat-core.tsx:3102](I:/PycharmProjects/My_first_Network_Simulator/frontend/src/components/agent-chat-core.tsx:3102) zeigt die Vorschlagsprüfung bei `BLOCKED` nur für `engineering_model`, nicht für `routing`. Die elf gespeicherten Routingbefunde werden dadurch ausgeblendet. Die gespeicherten äußeren Befunde enthalten teilweise eine verschachtelte Fehlerstruktur lediglich als Meldungstext, was gezielte UI-Aktionen erschwert.

**Beleg Rückfragen:** Die Wizarderkennung liest Textteile ([agent-chat-core.tsx:975](I:/PycharmProjects/My_first_Network_Simulator/frontend/src/components/agent-chat-core.tsx:975)), die API liefert strukturierte `data-engineering`-Ereignisse ([route.ts:64](I:/PycharmProjects/My_first_Network_Simulator/frontend/src/app/api/agent/chat/route.ts:64)). Der Wizard antwortet an [agent-chat-core.tsx:2066](I:/PycharmProjects/My_first_Network_Simulator/frontend/src/components/agent-chat-core.tsx:2066) mit Freitext statt `QUESTION_ANSWER` samt Frage-ID. [conversation.py:117](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/agent_tools/conversation.py:117) kann dies als neuen Auftrag behandeln und bisherige Antworten verwerfen. Der normale Chat besitzt bereits strukturierte Fragekomponenten.

**Korrektur:** Gemeinsame Ereignis-, Befund-, Review- und Frageanzeige für alle Schritte. Befunde tragen Code, Objektbezug, Schritt, Ursache und zulässige Aktion. Antworten enthalten die gespeicherte Frage-ID und Auswahl; Wiederöffnen lädt diese aus dem Backend.

**Abnahme:** Jeder blockierte Schritt zeigt den konkreten Grund und einen passenden Korrekturweg. Rückfragen und Antworten überstehen Reload. Keine Antwort startet versehentlich einen neuen Auftrag. Technische Kennungen erscheinen bei Bedarf im Detail; der Benutzer sieht zuerst Gerät, Verbindung und verständliche Ursache.

### F06 · P1 · Wiederanlauf und Zustandseigentum sind nicht durchgängig abgesichert

**Beleg:** [run_status.py:51](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/agent_tools/run_status.py:51) setzt unterbrochene Ausführungen auf wiederaufnehmbar, aktualisiert aber nicht die Gesprächsreservierung des alten Workers. [conversation.py:51](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/agent_tools/conversation.py:51) kann einen neuen Lauf wegen der noch gültigen fünfminütigen Reservierung ablehnen. Gleichzeitig verbraucht die UI ihren automatischen Versuch bereits vor einer erfolgreichen Annahme ([agent-chat-core.tsx:2116](I:/PycharmProjects/My_first_Network_Simulator/frontend/src/components/agent-chat-core.tsx:2116)). Dieser Pfad ist im Code belegt; ein echter Live-Neustart wurde in dieser Analyse nicht ausgelöst.

Zusätzlich startet die UI auch nach fehlgeschlagenem Speichern des Wizardkontexts den Auftrag ([agent-chat-core.tsx:1969](I:/PycharmProjects/My_first_Network_Simulator/frontend/src/components/agent-chat-core.tsx:1969)). Serverseitige Steuerfelder wie `agent_execution` und `wizard_request` können über den allgemeinen Kontextpfad gesetzt werden ([service.py:812](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/workflow/service.py:812)), ohne ein einheitliches Übergangs- und Revisionsprotokoll.

**Korrektur:** Start atomar speichern und zuordnen. Ausführung, Gespräch, Workerbesitz und Wiederaufnahme gemeinsam verwalten. Änderungen an Steuerdaten ausschließlich über validierte Kommandos; normale Kontextänderungen enthalten nur dafür bestimmte Benutzereinstellungen. Alte Workerantworten dürfen keinen neuen Lauf überschreiben. Automatische Wiederaufnahme zählt erst nach Annahme.

**Abnahme:** Neustart während Generierung, Freigabe und Simulation; Fortsetzen trotz alter Reservierung; verspäteter Heartbeat; verlorene Antwort nach Commit; zwei Tabs; veraltete Revision. Keine doppelte Übernahme und kein Zurücksetzen abgeschlossener Schritte auf laufend.

### F07 · P1 · Ein Integrationstest ist nicht sauber vom Defaultprojekt isoliert

**Beleg:** [test_wizard_generation.py:644](I:/PycharmProjects/My_first_Network_Simulator/backend/tests/test_wizard_generation.py:644) liest und schreibt den Gesprächszustand außerhalb seines projektspezifischen `execute`-/`activate_project`-Kontexts. Nach `execute` wird der Kontext zurückgesetzt ([runtime.py:100](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/agent_tools/runtime.py:100)); ohne äußeren Kontext ist das Projekt `default`. Ein zentraler, nicht umgehbarer Testdatenbank-Schutz fehlt in der untersuchten pytest-Konfiguration.

**Korrektur:** Wegwerfdatenbank bzw. eigener Testcontainer, fest vorgegebene Test-DSN und ein Schutz vor jeder Testausführung, der Produktdatenbanken ablehnt. Jeder Testzugriff muss seinen Projektkontext explizit besitzen; Fremdprojektzugriffe werden als Fehler geprüft.

**Abnahme:** Die komplette Suite läuft auf einer frischen Testdatenbank. Ein Lauf mit Produkt-DSN wird vor dem ersten schreibenden Test abgelehnt. Paralleltests verändern weder Default- noch andere Testprojekte. Der betroffene Test wurde in dieser Analyse deshalb nicht erneut ausgeführt.

### F08 · P1 · Vorhandene Nachweise decken den tatsächlichen großen Browserauftrag nicht ab

**Beleg:** [verify-wizard-continuity.mjs:21](I:/PycharmProjects/My_first_Network_Simulator/frontend/scripts/verify-wizard-continuity.mjs:21) ersetzt schreibende API-Antworten durch `200 {}` und prüft vor allem die Sichtbarkeit der neun Schrittbezeichnungen. Das ist ein UI-Sichtbarkeitstest.

[test_wizard_generation.py:434](I:/PycharmProjects/My_first_Network_Simulator/backend/tests/test_wizard_generation.py:434) prüft echte Services, verändert aber erzeugte Netz-/Port-/Timingdaten und reduziert den großen Eingabesatz auf vier Beziehungen. Die Simulation läuft synchron ohne echte Jobpersistenz. Das ist ein vorbereiteter Integrationstest.

Es gibt auch einen stärkeren realen HTTP-Test: [verify-live-wizard.py:78](I:/PycharmProjects/My_first_Network_Simulator/scripts/verify-live-wizard.py:78) verwendet Chat, Review und Apply und prüft bei vollständigem Scope echte Beobachtungsabdeckung. Er muss erhalten und erweitert werden. Der historische Großtest belegt 261 Knoten, 386 Routen und 725 Signale auf einem Build vom 10.09.; er beweist nicht den aktuellen Auftrag mit 552 Hardwareteilnehmern und 1.404 Signalen. Außerdem werden die neun erwarteten Statusschlüssel noch nicht vollständig erzwungen.

**Korrektur/Abnahme:** Versionierte vollständige Eingaben und echte Browserbedienung über API, MCP, Datenbank und persistierenden Simulationsworker. Keine nachträglichen Fixture-Reparaturen am erzeugten Modell und keine fingierten Schreibantworten. Kleine Referenz und aktueller Großauftrag müssen bis Schritt 9 überprüfbare Artefakte liefern. Bestehende Komponenten- und HTTP-Tests bleiben zusätzliche Prüfebenen.

### F09 · P1/P2 · Prüfungen sind keine verbindliche Releasebedingung

**Beleg:** Im untersuchten Repository wurden keine CI-Konfiguration und keine Playwright-Testkonfiguration für diesen Durchlauf gefunden. `package.json` enthält keinen vollständigen E2E-Testbefehl. [start-networkis.ps1:171](I:/PycharmProjects/My_first_Network_Simulator/start-networkis.ps1:171) baut und startet unmittelbar; der Dockerbuild enthält keine entsprechende Prüfung. Ein erfolgreicher Readiness-Check beweist keine Wizard-Durchgängigkeit.

Zusätzlich unterscheiden sich die JavaScript-Lockfiles: npm/Installation Next 16.3.2, pnpm-Lockfile Next 16.2.11. Python wird im Dockerbuild aus Versionsbereichen installiert. Das Buildmanifest erfasst die ausgeführte Extraktionsbrücke `frontend/scripts/extract-wizard-specification.mjs` nicht ([write-build-info.py:11](I:/PycharmProjects/My_first_Network_Simulator/scripts/write-build-info.py:11)).

**Korrektur/Abnahme:** Einheitlicher Installationsweg und vollständige Abhängigkeitsfixierung; vollständiges Manifest der ausgeführten Quellen. Pflichtprüfungen sowohl in CI als auch im lokalen Releaseweg. Genau das getestete unveränderliche Containerimage wird gestartet. Testergebnis, Build-ID und Schema-/Migrationsstand gehören zusammen; ein neuer Build braucht einen neuen Nachweis.

## Risiken mit noch ausstehender Laufzeitreproduktion

Diese Punkte sind aus dem Code abgeleitet und dürfen nicht als bereits beobachtete Livefehler ausgegeben werden:

- Ein verspäteter Heartbeat könnte einen Abschlussstatus überschreiben: Update ohne durchgängigen Eigentümer-/Revisionsvergleich, Heartbeat-Stopp erst nach `finished()` ([run_status.py:174](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/agent_tools/run_status.py:174), [api.py:425](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/agent_tools/api.py:425)).
- Ein Projektwechsel bei geöffnetem Wizard kann widersprüchliche Kontexte liefern: einmalig erfasste Wizardprojekt-ID gegenüber API-Helfern mit global aktivem Projekt. Ein tatsächlicher Fremdprojekt-Schreibvorgang wurde nicht nachgewiesen.
- Wiederanlauferkennung anhand einer anderen Serverinstanz benötigt für mehrere gleichzeitig laufende Worker eine tragfähige Besitzprüfung.

Diese Risiken werden durch reproduzierbare Störfalltests entschieden und anschließend entweder behoben oder mit einem nachgewiesenen Schutz als erledigt dokumentiert.

## Umsetzungsplan mit verbindlichen Abnahmen

| Paket | Umsetzung und betroffene Bereiche | Abnahme vor dem nächsten Paket |
|---|---|---|
| A · Sichere Ausgangsbasis | Testdatenbank-Schutz und Projektfixtures; aktuellen vollständigen Auftrag samt Cluster-, HMI-, Kodierungs- und Funktionsentscheidungen als versionierten Testfall sichern. Build-/Quellstand erfassen. | Keine Tests können Produktdaten verändern. F01–F05 haben reproduzierbare zunächst fehlschlagende Regressionstests. Keine nachträgliche Anpassung der erzeugten Nutzdaten im Test. |
| B · Fachliche Erzeugung | Gemeinsame Endpunktauflösung in Routinggeneration; vollständige Framegrößen und Abschnittsprüfung; strukturierte Routingbefunde. Vorhandene Kommunikationsverträge nutzen. | Die elf aktuellen Interfacekonflikte sind reproduziert und behoben. Frame-/Gateway-/HMI-/lokale-IO-Tests bestehen, ohne Empfänger, Kodierungen oder bestätigte Fristen zu erfinden/ändern. |
| C · Einheitlicher Ablauf | Strukturierte Kommandos für Start, Antwort, Review, Apply, Fortsetzen und Abbruch; gespeicherter Auftrag/Ziel/Revision; stabile Operations-ID; alte Vorschläge ausdrücklich ablösen. Serverseitig erlaubte Zustandsübergänge festlegen. | Alle UI-Einstiege steuern denselben Ablauf. Unveränderte Wiederholung erzeugt weder neue Vorschläge noch Jobs. Geänderte Modelle invalidieren die richtigen Folgeartefakte. Veraltete Kommandos werden mit verständlichem Konflikt abgelehnt. |
| D · Anzeige und Wiederaufnahme | Gemeinsame Fragen-/Review-/Befundkomponenten; Backend als maßgebliche Zustandsquelle; atomarer Start; konsistente Workerreservierung und Schutz gegen alte Antworten. | Blockierte Schritte nennen konkrete Objekte und Aktionen. Antworten, HMI-Auswahl, Vorschläge und Freigaben bleiben nach Reload/Neustart erhalten. Zwei Tabs und verspätete Antworten überschreiben keine neuere Revision. |
| E · Vollständiges E2E | Playwright-Suite mit realem Backend/MCP/SQL/Worker; vorhandenen HTTP-Test stärken. Kleiner Auftrag und vollständiger aktueller Großauftrag über reguläre Benutzereingaben/Freigaben bis Schritt 9. | Alle neun Schritte besitzen echte, zueinander passende Artefakte. Keine gemockten Schreibantworten, keine direkte Statussetzung, keine Verkleinerung des Auftrags. Ein erneutes Fortsetzen erzeugt keine zweite Simulation. |
| F · Störfälle und Release | Neustart-/Netzwerk-/Parallelitätsmatrix; feste Abhängigkeiten und vollständige Build-ID; verpflichtende lokale und CI-Prüfung vor Umschaltung auf das getestete Image. | Frische Installation und Wiederaufnahme bestehen. Fehler blockieren die Freigabe. Browsertrace, Fehlerlogs, Quellrevisionen, Status- und Coverageergebnisse werden dem getesteten Image zugeordnet. |

Die Änderungen sollten paketweise integriert werden. Routinggenerator, Kommunikationsvalidierung, Orchestrierung, Zustandsmigration und UI dürfen nicht als ein ungeprüfter Großumbau zusammengeführt werden. Bestehende menschliche Freigaben und fachliche Grenzen bleiben Teil des Ablaufs.

### Was „bis Schritt 9 bestanden“ künftig konkret bedeutet

1. **Engineering-Modell:** vollständiger bestätigter Auftragsumfang; gültige Identitäten, Zuordnungen, Kodierungen und Funktionspartner. Keine stillen Scope-Kürzungen.
2. **Routing:** gültige übernommene Routen zur aktuellen Modellrevision; korrekte logische/physische Endpunkte; HMI-Auswahl und lokale Empfängergrenzen eingehalten.
3. **Netzwerk-Editor:** persistierte Topologie stimmt mit den kanonischen Ports, Netzen und Routen überein; keine veralteten oder erfundenen Verbindungen.
4. **Parameter:** alle tatsächlich benötigten Werte vorhanden; explizite Vorgaben bleiben erhalten; Herkunft von Defaults nachvollziehbar.
5. **Capacity & Timing:** Berechnung aus denselben freigegebenen Frames und Wegen; Last, Schedule und funktionale Timingbeurteilung getrennt. Kein Bestehen durch Verkleinerung von DLC oder Lockerung bestätigter Anforderungen.
6. **Validation / Preflight:** aktuelle Ergebnisse zu denselben Revisionen. Technische Fehler blockieren; fachliche Warnungen bleiben mit konkretem Grund sichtbar und werden nicht pauschal unterdrückt.
7. **Simulation:** echter persistierter Job im bestätigten Scope; ein Lauf pro Operation; Neustart und erneutes Fortsetzen erzeugen keine Duplikate.
8. **Results / Analysis:** gespeicherte Ergebnisse gehören zu diesem Job; für den Testfall vollständige erwartete Beobachtung der Routen/Signale/Netze, keine unbemerkten Ausfälle.
9. **Data Science & Intelligence:** Bewertung nutzt diese Ergebnisse und nennt ihre Grenzen. Warnungen können ein fachlich korrektes Ergebnis sein; fehlende Artefakte oder Ausführungsfehler dürfen nicht als erfolgreicher Abschluss erscheinen.

Die Tests verlangen ausdrücklich alle neun erwarteten Schritte. Ein grüner Prozentbalken, neun sichtbare Karten oder ein technisch fertiger Job allein reichen nicht.

### Pflichtmatrix gegen Regressionen

- Direktverbindung und Gatewaywechsel; CAN, CAN-FD, LIN und Ethernet; gemischte lokale und externe Interfaces am selben Gerät.
- Funktion zu Funktion, lokales Sensor-/Aktor-IO, explizite direkte Gerätenutzung, an-/abgewählte HMI-Werte und getrennte Payloads.
- Größen-/Kodierungsgrenzen, unveränderte DLC bei Signalunterauswahl, Multicast und fehlende Transporttransformation.
- Ungültiges Modell/Routing/Topologie mit sichtbarer Korrektur und erfolgreicher Wiederaufnahme.
- Doppelklick, zwei Tabs, Antwortverlust vor/nach Commit, Browserreload und Projektwechsel.
- Backend-/Workerneustart während Generierung, Review, Apply und Simulation; alte Heartbeats/Antworten; veraltete Freigabe nach Modelländerung.
- Speicherung scheitert: entweder kein Auftrag gestartet oder derselbe bereits gespeicherte Auftrag eindeutig wiedergefunden.
- Kleine Referenz bei jeder Änderung; aktueller vollständiger Großauftrag vor jeder entsprechenden Releasefreigabe. Ergänzende periodische Großtests ersetzen die Releaseprüfung nicht.

## Erreichter Prüfumfang und Grenzen

- **Durchgeführt:** projektweite Python-Syntaxprüfung von 617 eigenen Dateien ohne Syntaxfehler; Frontend-TypeScript-Prüfung erfolgreich; gezielte statische Querschnittssuche; tiefe Prüfung von Wizard-UI, API-Brücke, Routinggeneration/-validierung, Vorschlagsidentität, Gesprächs-/Ausführungszustand sowie Test- und Releasepfaden.
- **Durchgeführt:** lesende Live-Abfrage von Workflow, Gespräch und Vorschlägen; isolierte Reproduktion des Interfacefehlers und des Framegrößenfehlers; unabhängige Teilprüfungen für Routing, Workflow und Tests/Release.
- **Nicht durchgeführt:** schreibender kompletter Live-Browserdurchlauf, vollständige Datenbanktestsuite, Neustartkampagne oder Umsetzung der Korrekturen. Der aktuelle Auftrag bleibt blockiert und unverändert.
- **Keine pauschale Zertifizierung:** Syntax-/Typprüfung beweist keine funktionale Fehlerfreiheit. Das gesamte Repository ist damit nicht Zeile für Zeile fachlich oder als vollständiges Sicherheitsaudit geprüft. Weitere Backend-, Import-/Export-, Reparatur-, Kapazitäts- und Analysepfade benötigen die paketweise Vertrags- und Laufzeitprüfung im Umsetzungsplan. Suchtreffer wie abstrakte `NotImplementedError` sind allein kein Fehlernachweis.

Die frühere Formulierung „bis Schritt 9 geprüft“ war für den tatsächlichen Benutzerweg zu weitgehend. Der bisherige vorbereitete Integrationstest und die UI-Sichtbarkeitstests rechtfertigen diese Aussage für den aktuellen großen Auftrag nicht. Erst die oben definierte Abnahme liefert diesen Nachweis.

## Analysebelege

- [Aktueller Workflow](I:/PycharmProjects/My_first_Network_Simulator/backend/runtime/stability-audit-workflow.json)
- [Gesprächs- und Vorschlagszustand](I:/PycharmProjects/My_first_Network_Simulator/backend/runtime/stability-audit-conversation.json)
- [Vorschlagsübersicht](I:/PycharmProjects/My_first_Network_Simulator/backend/runtime/stability-audit-proposals.json)
- [Aktiver Routingvorschlag mit elf Fehlern](I:/PycharmProjects/My_first_Network_Simulator/backend/runtime/stability-audit-active-proposal.json)

Die Runtime-Dateien sind Diagnosebelege, noch keine dauerhaft versionierten Testfixtures. Paket A überführt die erforderlichen Eingaben und Erwartungen in reproduzierbare Testdaten.
