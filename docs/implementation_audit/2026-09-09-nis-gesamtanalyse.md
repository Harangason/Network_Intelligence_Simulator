# NIS: Gesamtanalyse und verbindlicher Verbesserungsplan

Stand: 9. September 2026. Untersucht wurde ausschließlich das kanonische Projekt `I:/PycharmProjects/My_first_Network_Simulator`, einschließlich des laufenden Projekts `network-project-20260909082213746-780a13ef` auf Port 13500.

## Ergebnis

Der NIS besitzt einen funktionierenden technischen Kern und eine reale Agent-/MCP-Anbindung. Als durchgängig verlässliches Engineering- und Simulationswerkzeug ist der untersuchte Stand noch nicht abnahmefähig. Mehrere Übergänge zwischen Wizard, Modellansichten, Routing, Simulation und Agent verlieren Informationen oder interpretieren dieselben Daten unterschiedlich. Dadurch kann ein gültiges Objekt als unzugeordnet erscheinen und eine fehlerhafte beziehungsweise unvollständige Simulation erfolgreich aussehen.

Die sichtbaren Probleme sind damit nachvollziehbar und keine bloße Frage der Bedienung. Weitere einzelne Oberflächenkorrekturen reichen nicht aus. Vorrang haben gemeinsame Modellregeln, verlustfreie Übergaben und eine Abnahme am selben vollständigen Referenzsystem.

Diese Analyse enthält keine Änderungen an Produktcode oder fachlichen Daten des Nutzerprojekts. Belege, Reproduktionsskripte und Berichte wurden separat gespeichert. Vorhandene lokale Änderungen wurden erhalten.

## Die drei Browserkommentare

### 1. Was bedeuten die Interfaces?

Zwei unterschiedliche Begriffe sind fachlich sinnvoll:

| Begriff | Bedeutung | Verständliche Bezeichnung in der Oberfläche |
| --- | --- | --- |
| Hardware Interface | Physischer Anschluss beziehungsweise Controllerkanal eines Geräts, mit Netz-/Portbindung und technischen Eigenschaften | Physische Anschlüsse |
| Interface | Logischer Kommunikationszugang, unter dem Nachrichten zusammengefasst werden; Eigentümer kann eine Funktion oder direkt Hardware sein | Kommunikationsschnittstellen |

Eine ECU kann einen CAN-FD-Anschluss zum Backbone, einen weiteren CAN-FD-Anschluss für lokale Teilnehmer und LIN-Anschlüsse haben. Mehrere Schnittstellen sind deshalb nicht automatisch Duplikate. Namen wie `Abgasnachbehandlung 1` erklären jedoch weder Rolle noch Netzbindung. Die Oberfläche sollte zu jeder Schnittstelle Eigentümer, Netz, physischen Anschluss und Nachrichtenanzahl anzeigen.

Der aktuelle Structure Tree bildet nur die Kette Hardware → Funktion → Interface → Nachricht → Signal ab. Der Generator erlaubt für einfache Geräte ausdrücklich Hardware → Interface → Nachricht → Signal. **Alle 199 dort als nicht zugeordnet angezeigten Interfaces haben einen existierenden Hardware-Eigentümer.** Für diese Interfaces fehlen nicht die Daten, sondern der richtige Darstellungsweg.

**Lösung:** Einen gemeinsamen Resolver für Eigentümerbeziehungen verwenden. Der Baum muss beide gültigen Pfade darstellen. Ein Objekt ist erst verwaist, wenn kein zulässiger, existierender Eigentümer aufgelöst werden kann. Keine künstlichen Funktionen erzeugen, um eine zu starre Oberfläche zufriedenzustellen.

### 2. Warum stehen in der Signaltabelle Striche?

Die Funktionsspalte läuft ausschließlich über Signal → Nachricht → Interface → Funktion. Im Modell haben **215 von 520 Signalen** auf diesem Weg keine Funktion; ihre Eigentümer sind Geräte der Klasse 1, für die eine eigene Funktion nicht vorgesehen ist. Der Strich vermischt damit „fachlich nicht erforderlich“ und „Zuordnung tatsächlich defekt“.

**Lösung:** Hardware-Eigentümer und Systemzuordnung immer anzeigen; Funktion als optionale zusätzliche Spalte behandeln. Für gültige direkte Zuordnung etwa `Direkt an EGRValvePosition` beziehungsweise `Keine eigene Funktion erforderlich` anzeigen. Für einen echten Referenzfehler dagegen einen konkreten Fehler mit Reparaturmöglichkeit darstellen.

### 3. Wurde EGRValvePosition im Wizard richtig zugeordnet?

Ja: Im gespeicherten Wizard-Feedback steht `EGRValvePosition → Abgasnachbehandlung`, `accepted=true`, Quelle `wizard-submission`. Auch die gespeicherte Verbindung und die freigegebene Route führen zur Abgasnachbehandlung.

Die Systemrahmen-Ansicht des Structure Tree rekonstruiert Zugehörigkeiten aber aus Namen; die 260 Hardwareobjekte besitzen keine persistierte explizite System-Eigentümerreferenz. Bei **41 Teilnehmern** weicht die daraus erzeugte Anzeige von der bestätigten Wizard-Zuordnung ab. Bei diesen 41 stimmt die gespeicherte Topologie mit dem akzeptierten Wizard-Feedback überein. Das bestätigte Feedback selbst wurde dabei nicht überschrieben.

**Lösung:** Bestätigte Systemzugehörigkeiten als ID-basierte Modellbeziehungen speichern und in allen Ansichten lesen. Namensähnlichkeit darf Vorschläge liefern, aber keine bestätigte Zuordnung ersetzen. Das vorhandene Feedback ermöglicht einen gezielten Migrationsvorschlag mit Vorher-/Nachher-Vergleich.

Details und genaue Codefundstellen: [Modell- und Wizardprüfung](I:/PycharmProjects/My_first_Network_Simulator/docs/implementation_audit/2026-09-09-model-wizard-audit.md).

## Priorisierte Befunde über den gesamten Ablauf

P1 bezeichnet Fehler, die eine belastbare fachliche Abnahme blockieren. P2 bezeichnet wesentliche Bedienungs-, Zustands- oder Wartbarkeitsprobleme. „Live“ bedeutet Nachweis am gespeicherten Nutzerprojekt; „Repro“ bedeutet kontrolliert gegen echte Programmfunktionen reproduziert, ohne den Fehler im Nutzerprojekt auszulösen.

| Priorität | Befund und Nachweis | Konkrete Lösung |
| --- | --- | --- |
| P1 | **Timing-Grenzen gehen verloren.** Alle 217 eingefrorenen Routen besitzen unter anderem ein Jitterlimit von 5 ms. Die Laufzeitprüfung übernimmt diese Grenzen nicht korrekt. 20 Routen überschreiten 5 ms und melden trotzdem PASS; ein Beispiel erreicht rund 9,244 ms. Live und Code. | Einen typisierten Timing-Vertrag Route → SimulationSnapshot → Runtime-Auswertung verwenden; Feldnamen vereinheitlichen. Nicht ausgewertete Anforderungen ausdrücklich kennzeichnen. |
| P1 | **Gateway-Zielnetz fehlt in der Simulation.** Capacity enthält 83 Netze, Simulation und Trace nur 82. `Infotainment_08-S01` fehlt; acht Gateway-Routen verlieren die Zielnetzübertragung, weil Endpunkte auf das Quellnetz abgebildet werden. Live und Code. | Quellsegment, Gateway und Zielsegment mit ihren tatsächlichen Ports und Technologien erhalten; jeden Transportabschnitt simulieren und im Trace nachweisen. |
| P1 | **Gesamtabdeckung wird nicht vor Freigabe erzwungen.** Der Lauf enthält 169/520 Signale und 162/309 Nachrichten. 351 Signale beziehungsweise 147 Nachrichten fehlen im Transportlauf. Intelligence zeigt die Lücke später, während Preflight APPROVED und Simulation/Results COMPLETE sind. Live. | Vor dem Start jeden eingeschlossenen Kommunikationspfad einer Route zuordnen. Bewusste Ausschlüsse vorab begründen. Nach dem Lauf erwartete und beobachtete IDs abgleichen; Laufabschluss und fachliche Vollständigkeit getrennt bewerten. |
| P1 | **Physische Anschlüsse werden zwischen Netzen verwechselt.** 14 HardwareInterface-IDs werden für mehrere getrennte physische Netze wiederverwendet. Der Generator wählt den ersten Anschluss passender Technologie. Bei Abgasnachbehandlung wird trotz vorhandenem CAN_FD_IO-Anschluss der Backbone-Anschluss für das lokale Netz verwendet. Live und Code. | Anschlüsse über Hardware-ID, Port-ID, physische Netz-ID und Technologie eindeutig binden; vorhandene kanonische Route-Portreferenzen übernehmen. Physische Ressourcentrennung validieren. |
| P1 | **Vollständiger Kommunikationsausfall kann PASS ergeben.** Repro mit zwei gesendeten und null empfangenen Frames ergibt 100 % Drop, null Timeouts und PASS. Der Timeoutrechner betrachtet nur Abstände zwischen erfolgreichen Empfängen. | Erwartete Sende-/Empfangsereignisse und vollständiges Beobachtungsfenster auswerten, einschließlich erstem Empfang und Laufende. Für Fehlerkampagnen Sollfehler-Erkennung und Kommunikationskonformität getrennt ausgeben. |
| P1 | **Golden Trace ist keine konsistente fehlerfreie Referenz.** Bei einem Signaloffset zeigt das Golden-Ereignis einen korrigierten Wert, enthält aber weiterhin fehlerbehaftete Payload, Empfangswerte und Fault-Metadaten. Repro. | Fehlerfreie Ereignisse vor Fehleranwendung separat erzeugen oder deterministisch aus identischen Eingängen berechnen. Payload, dekodierte Werte, Timing und Metadaten müssen zu derselben Referenz gehören. |
| P1 | **Große Agent-Vorschläge werden im Chatverlauf gekürzt.** 200 Änderungen werden als 101 Einträge einschließlich Textmarker gespeichert; ein Status-Refresh derselben Revision lädt die Vollfassung nicht nach. Repro; relevanter Code auch live. | Im Verlauf Proposal-ID, Revision und Zusammenfassung speichern. Vollständige beziehungsweise vollständig paginierbare Reviewdaten vor Freigabe aus dem Backend laden. |
| P1 | **Lange Agent-Läufe verlieren ihre Bearbeitungssperre.** Der Heartbeat-Thread verwendet das Projekt `default`; die echte projektgebundene Lease wird nicht verlängert und läuft nach fünf Minuten ab. Repro; relevanter Code auch live. | Projektkontext explizit im Thread setzen, Erneuerung prüfen und Conversation/Wizard an dieselbe dauerhafte Laufidentität binden. |
| P1 | **Freier Agent-Auftrag kann eine unbelegte Erfolgsmeldung liefern.** Ein kontrollierter Reasoner antwortet auf „Lege ein Gateway an“ mit „erfolgreich angelegt“; die Orchestrierung akzeptiert dies mit nur `inspect_project`, ohne Änderungsvorschlag. Repro, keine Behauptung einer solchen konkreten Live-LLM-Antwort. | Änderungsabsicht und erwartete Artefakte erfassen. Erfolg nur aus tatsächlichen Toolergebnissen und persistierten Objekt-/Proposal-IDs ableiten; unvollständige Arbeit fortsetzen oder konkret als unvollständig ausweisen. |
| P1 | **Frische lokale Installation ist nicht reproduzierbar.** Docker installiert `mcp` aus requirements.txt; pyproject.toml und uv.lock enthalten es nicht. Die dokumentierte uv-Installation kann dadurch den verpflichtenden Agent-/MCP-Import nicht erfüllen. Kontrollierter Import-Repro. | Einen gepflegten Abhängigkeitsstand verwenden, Lockfile synchronisieren und einen Starttest in einer wirklich frischen Umgebung ergänzen. |
| P2 | **Structure Tree, Formular und Structure Wizard widersprechen gültigen Direktzuordnungen.** 199 falsche Waisen, 215 unerklärte Funktionslücken; der Wizard verlangt dennoch eine Funktion. Live und Code. | Eine gemeinsame Eigentümerregel für Generator, Validator, Formular, Tree und Wizard einsetzen. |
| P2 | **Systemrahmen-Anzeige widerspricht bestätigter Zuordnung.** 41 Abweichungen zur bestätigten Wizard-Zuordnung durch die Namensheuristik. Live. | Explizite Systembeziehungen speichern; bestehende bestätigte Evidence gezielt übernehmen. |
| P2 | **Allgemeiner Fortschritt löscht die Workload-ID.** Ein Fortschrittsereignis ohne workload_id überschreibt active_workload mit None. Repro. | Fortschritt und Workload-Identität getrennt modellieren; Identität nur bei explizitem Zustandsübergang ändern. |
| P2 | **Browser und getesteter Arbeitsstand sind nicht derselbe Release.** Vier von zehn gezielt verglichenen Quelldateien unterscheiden sich zum laufenden Container. Belegt durch normalisierte SHA-256-Vergleiche. | Build-/Commit-ID und Schema-Version sichtbar machen; Tests und Browserabnahme an genau demselben gebauten Artefakt durchführen. |

Technische Belege, Reproduktionsdetails und präzise Codefundstellen stehen in der [Workflow-/Simulationsprüfung](I:/PycharmProjects/My_first_Network_Simulator/docs/implementation_audit/2026-09-09-workflow-simulation-audit.md) und der [Agentprüfung](I:/PycharmProjects/My_first_Network_Simulator/docs/implementation_audit/2026-09-09-agent-audit.md).

## Warum die Entwicklung trotz grüner Tests nicht zuverlässig vorankommt

Die Fehler liegen überwiegend an Übergängen. Der Generator und das UI verwenden unterschiedliche Eigentümerregeln. Die Route besitzt Grenzwerte und Zielports, der Simulationsadapter verliert sie. Die Datenbank besitzt vollständige Vorschläge, der Chatcache enthält gekürzte Objekte. Ein einzelner Test einer Hilfsfunktion kann dabei erfolgreich sein, obwohl der vollständige Benutzerablauf scheitert.

Zusätzlich vermischen Zustände unterschiedliche Aussagen: „Objekte vorhanden“, „Lauf beendet“, „alle angeforderten Inhalte geprüft“ und „Anforderungen erfüllt“. Auf der untersuchten Intelligence-Seite stehen 32,5 % Signal Coverage neben 100 % Requirement Coverage, Simulation Pass Rate und Timing Compliance. Die unterschiedlichen Nenner und Prüfbedingungen sind nicht hinreichend sichtbar; bei Timing kommt ein echter Auswertungsfehler hinzu.

Auch der Arbeitsstand erschwert die Zuordnung von Verbesserungen: Auf Port 13500 läuft ein gebautes Docker-Image ohne Quellcode-Mount. Lokale Änderungen erscheinen darin erst nach einem neuen Build und Deployment. Ein erfolgreicher lokaler Test allein bestätigt deshalb keine Behebung in der sichtbaren Anwendung.

## Zielbild und Umsetzung in überprüfbaren Paketen

### Paket 1: Datenmodell und Zuordnung vereinheitlichen

Ein zentraler Dienst löst für jedes Objekt Hardware-Eigentümer, optionale Funktion, Systemzugehörigkeit, logische Schnittstelle und physischen Anschluss auf. Alle Ansichten und Werkzeuge nutzen dieselbe Auskunft. Systemzugehörigkeit, funktionale Eigentümerschaft und elektrische Verbindung bleiben unterschiedliche Beziehungen.

Abnahme am vorhandenen Datenstand: null falsche Waisen für die 199 gültigen direkten Interfaces; alle 215 direkten Signale mit sichtbarem Hardware-Eigentümer; EGRValvePosition bleibt nach Wizard, Übernahme und Neuladen im bestätigten Abgassystem; keine ungeprüfte Systemzuordnung aus Namen. Separater Test mit absichtlich gelöschter Elternreferenz muss einen echten Fehler zeigen.

### Paket 2: Simulation aus dem kanonischen Modell vollständig ableiten

Die Konvertierung in den SimulationSnapshot erhält IDs, Ports, Netzsegmente, Technologien, Nachricht-/Signalzuordnung und Timing-Grenzen verlustfrei. Preflight prüft nicht nur, ob vorhandene Routen gültig sind, sondern ob der gesamte gewählte Simulationsumfang abgedeckt ist.

Abnahme: jede eingeschlossene Nachricht und jedes eingeschlossene Signal ist geroutet oder vorab mit Begründung ausgenommen; die erwarteten Signal-IDs erscheinen im Lauf; Gateway-Verkehr erscheint sowohl im Quell- als auch im Zielnetz. Ein physischer Port kann nicht unbemerkt unabhängige Busse ersetzen. Der vorhandene 5-ms-Jitterfall muss als Verletzung erkannt werden. 100 % Drop und Ausfall am Laufende dürfen keine erfolgreiche Kommunikationsbewertung erzeugen. Golden-Daten müssen über Payload-Dekodierung und Timing konsistent sein.

### Paket 3: Agent als nachprüfbaren Arbeitsablauf absichern

Die Schritte Auftrag → erwartete Ergebnisse → Tools → validierter Vorschlag → vollständige Reviewansicht → einmalige Übernahme → erneutes Laden → Fortsetzung werden durch dauerhafte IDs und eindeutige Zustände verbunden. Der Text des Sprachmodells ist keine Bestätigung einer erfolgten Änderung.

Abnahme: freier Chat und Wizard bestehen denselben Auftrag; ein Vorschlag mit 3.000 Änderungen bleibt nach Neuladen vollständig prüfbar; ein Lauf über sechs Minuten hält seine richtige Projektsperre; Disconnect, Retry und Backend-Neustart erzeugen keine Duplikate. Allgemeiner Fortschritt erhält die aktive Workload-ID. „Erstellt“ wird ausschließlich mit tatsächlich gespeicherten Ergebnissen angezeigt.

### Paket 4: Durchgängige Produktabnahme und eindeutiger Release

Zuerst ein kleines Referenzsystem mit zwei ECUs, einem Sensor, einem Aktor, Gateway und mindestens zwei Netzsegmenten vollständig durch die Oberfläche führen. Anschließend denselben Prüfablauf mit einer isolierten Kopie des aktuellen 260-Knoten-Projekts ausführen. Die Anzahl der Objekte allein ist kein Erfolgskriterium.

Pflichtpfad: Wizard beziehungsweise freier Agentauftrag → Übernahme → Engineering-Ansichten → Routing → Netzwerk → Parameter → Capacity → Preflight → Simulation → Trace → Intelligence → Speichern/Öffnen und Fortsetzung. Fehlerfälle: Grenzwertverletzung, vollständiger Drop, veralteter Vorschlag, Verbindungsabbruch, Neustart und fehlender Modelldienst. Ergebnisse müssen sich auf dieselbe Modellrevision und dieselbe Build-ID beziehen.

Die Pakete 1/2 und 3 können parallel umgesetzt werden. Breitere Feature-Erweiterungen sollten erst nach dieser Abnahme folgen. Vor allem das grüne PASS der Laufzeitauswertung muss früh korrigiert werden, damit weitere Entscheidungen auf belastbaren Ergebnissen beruhen.

## Durchgeführte Prüfung und Grenzen

- Read-only Export des aktuellen Modells: 260 Hardware-Knoten, 326 physische Anschlüsse, 61 Funktionen, 326 logische Interfaces, 309 Nachrichten, 520 Signale und 217 Routen. Gespeicherte Analysen, eingefrorener Snapshot und vorhandener Simulationslauf wurden ausgewertet.
- Browserprüfung: Engineering, Structure Tree mit AGR-Filter, Signaltabelle, Results und Intelligence. Die drei markierten Stellen sind reproduziert; in diesen geprüften Ansichten wurden keine Browser-JavaScriptfehler gemeldet.
- Frontend: **196 Tests bestanden**. TypeScript: **keine Fehler** bei `tsc --noEmit --incremental false`.
- Backend: **719 Tests bestanden, 0 Fehler, 0 übersprungen**, Laufzeit 143,27 s. Die Datenbank dieses Laufs war eine eigens angelegte, von den Nutzerprojekten getrennte PostgreSQL-Instanz auf `127.0.0.1:15439`; der ausschließlich dafür angelegte Container wurde anschließend gestoppt. Der erste Durchlauf hatte 715 bestandene Tests und vier Setupfehler wegen eines von dieser Prüfung noch nicht angelegten Elternverzeichnisses für temporäre Dateien. Nach Korrektur des Prüfaufrufs bestand die gesamte Suite; dies war kein Produktfehler.
- Eigene Fehler-Repros prüfen echte Funktionen mit kontrollierten Eingängen; bei Agent-Erfolgsaussagen ist der Reasoner absichtlich ersetzt, damit der Orchestrierungsfehler unabhängig von zufälligem Modellverhalten nachweisbar ist.
- Quellcodeparität: Der laufende Container verwendet Image `sha256:1335ed56d4e70eae3f865c6da20b742a69323e42da6d7535f78b84ce8e16309c`. Vier geprüfte Dateien unterscheiden sich vom Workspace. Die konkreten relevanten Fehlerpfade wurden für die Agentbefunde zusätzlich im Container kontrolliert; Tree, Wizard-Generator, Simulationsadapter und Runtime-Auswertung stimmen mit dem Workspace überein.

Keine vollständige Neuabnahme jedes Protokolls, jeder Branche, sämtlicher physikalischer Modelle, binärer Exportformate oder aller Langzeit-/Mehrbenutzerszenarien. Kein neuer echter LLM-Auftrag mit Modelländerung wurde im Nutzerprojekt ausgeführt. Vorhandene Modellverfügbarkeit und grüne Unit-/Integrationstests ersetzen diese noch ausstehende Produktabnahme nicht. Eine vollständige Neuentwicklung lässt sich aus den Befunden nicht ableiten; die beschriebenen Übergänge lassen sich gezielt konsolidieren.

## Reproduzierbare Nachweise

- [Modellprojektionen und bestätigte Zuordnungen](I:/PycharmProjects/My_first_Network_Simulator/docs/implementation_audit/verification/2026-09-09-model-projection-audit.json)
- [Simulation, Grenzwerte, Ausfall und Golden-Repro](I:/PycharmProjects/My_first_Network_Simulator/docs/implementation_audit/verification/2026-09-09-workflow-sim-audit.json)
- [Agentzustands-Repros](I:/PycharmProjects/My_first_Network_Simulator/docs/implementation_audit/verification/2026-09-09-agent-repro.py)
- [Proposal-History-Repro](I:/PycharmProjects/My_first_Network_Simulator/docs/implementation_audit/verification/2026-09-09-agent-history-repro.mjs)
- [Workspace-/Containervergleich](I:/PycharmProjects/My_first_Network_Simulator/docs/implementation_audit/verification/2026-09-09-source-parity.json)
- [Vollständiger Backend-Testnachweis](I:/PycharmProjects/My_first_Network_Simulator/docs/implementation_audit/verification/2026-09-09-nis-full-pytest-final.xml)

Der vollständige Projekt-Export liegt als lokale Belegdatei unter `verification/2026-09-09-nis-project-bundle.json` (rund 81 MB). Er dient der Nachvollziehbarkeit dieser Analyse; er wurde weder veröffentlicht noch committet.
