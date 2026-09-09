# NIS: umgesetzte Korrekturen und Abnahme

Stand: 9. September 2026. Kanonisches Projekt: `I:/PycharmProjects/My_first_Network_Simulator`. Laufender Release auf Port 13500: **0eddb7b2938d**.

Die vier Pakete der Gesamtanalyse wurden im Produkt umgesetzt und auf den laufenden NIS übertragen. Die drei markierten Browserprobleme sind im bestehenden Projekt korrigiert. Die technische Abnahme besteht mit einem vollständig spezifizierten Referenzprojekt. Das große Bestandsprojekt enthält weiterhin offene Kommunikationsanforderungen: **47 Nachrichten mit 235 Signalen besitzen keinen bestätigten Empfänger**. Dafür wird keine Gesamtfreigabe vorgetäuscht.

## Was sich geändert hat

| Bereich | Ergebnis |
|---|---|
| Struktur, Formular, Wizard | Gültige direkte Gerätezuordnungen funktionieren neben der optionalen Funktionsstufe. Die bisherigen 199 vermeintlich verwaisten Schnittstellen haben einen gültigen Darstellungsweg. |
| Signaltabelle | System, Quellgerät und optionale Funktion sind getrennt sichtbar. `AGRVentilstellung` zeigt `Abgasnachbehandlung`, `EGRValvePosition` und die Erklärung, warum keine eigene Funktion erforderlich ist. |
| Begriffe und Eigentümer | Physische Anschlüsse und Kommunikationsschnittstellen sind unterscheidbar. Bestätigte Systemzuordnungen werden mit IDs gespeichert; die Anzeige rekonstruiert sie nicht mehr aus Namen. |
| Physische Netze | Anschlüsse werden dem tatsächlichen Netz und Port zugeordnet. Getrennte Busse können nicht denselben physischen Kanal vortäuschen. Auch manuelles Netzwerkspeichern materialisiert die notwendigen Kanäle. |
| Routing und Gateway | Alle bestätigten Nachrichten und Rückmeldungen werden berücksichtigt. Quellnetz, Gateway und Zielnetz bleiben im Simulationsmodell und Trace erhalten. Capacity rechnet mit den tatsächlichen Segmenten und Portbitraten. |
| Vollständigkeit | Ein gemeinsamer gespeicherter Umfang gilt für Parameter, Preflight, Snapshot und Lauf. Der Server prüft die vollständigen kanonischen IDs. Teilumfänge brauchen eine Begründung; ausgeschlossene Netze und Teilrouten erzeugen keine falschen Ergebnisse. |
| Laufzeitbewertung | Konfiguriertes Timing, Jitter, Timeout und Freshness bleiben erhalten. Vollständiger Ausfall sowie fehlende Anfangs-/Endempfänge werden ausgewertet. Fehlende Evidenz ergibt `NOT_EVALUATED`; ein abgeschlossener Job ist nicht automatisch ein fachliches PASS. |
| Golden Trace | Eine getrennte deterministische Ausführung ohne Fehler erzeugt die Referenz. Payload, Werte, Timing und Metadaten passen zueinander. |
| Agent | Vollständige Vorschläge bleiben über Verlauf und Neuladen prüfbar. Projektsperren werden im richtigen Kontext verlängert; Fortschritt erhält die Workload-ID. Unbelegte Erfolgsaussagen werden nicht als erledigte Änderung gewertet. |
| Modellanbindung | Die lokale Ollama-Anbindung verarbeitet mehrstufige Werkzeugaufrufe und Argumentreparaturen. Die frische MCP-Installation ist über pyproject/Lockfile vervollständigt. |
| Betriebsstand | Oberfläche, Agent, Job-API und Backend verwenden dieselbe konfigurierte Instanz. Der Windows-Listener verhindert das unbemerkte Übernehmen desselben Ports durch einen zweiten Backendprozess. Die Build-ID ist im Browsercode und Ergebnis-Snapshot verankert. |

## Am bestehenden Projekt übernommen

Vor der Übernahme wurden ein aktueller Projektexport und der Quellstand des laufenden Containers gesichert. Die fachlichen Ausgangsdaten stimmten mit dem bereits getesteten Klon überein. Die Migrationen wurden gezielt auf `network-project-20260909082213746-780a13ef` angewendet.

| Bestand | Vorher | Nachher |
|---|---:|---:|
| Hardwareknoten | 260 | 260 |
| Funktionen | 61 | 61 |
| Kommunikationsschnittstellen | 326 | 326 |
| Nachrichten | 309 | 309 |
| Signale | 520 | 520 |
| Physische Anschlussobjekte | 326 | 339 |
| Routen | 217 | 317 |
| Nachrichten mit Transport | 162/309 | 262/309 |
| Signale mit Transport | 169/520 | 285/520 |

209 bestätigte Systemzuordnungen wurden übernommen. Die Portmigration hat 287 Anschlussobjekte angepasst, 13 notwendige Anschlüsse ergänzt, 84 physische Netzdefinitionen materialisiert und neun Nachrichten um bestätigte zusätzliche Übertragungsbindungen ergänzt. Alle bisherigen Anschluss-IDs bleiben erhalten. Nach der Portmigration sind die geprüften Netz-/Kanal-/Technologiefehler verschwunden.

100 fehlende Transporte wurden aus bereits bestätigten Projektangaben ergänzt. Die Topologie enthält weiterhin dieselben 260 Geräte und 216 Kanten; sie bindet alle 317 Routen ein. Wiederholte Migrationen erzeugen keine zusätzlichen Änderungen oder Routen.

Der Vorher-/Nachher-Abgleich bestätigt unveränderte Geräteidentitäten, Nachrichtendefinitionen, sämtliche Signalobjekte sowie die bisherigen Routing-Payloads und Timinggrenzen. Der Simulationsumfang bleibt **ALL**. Frühere Simulationen und Ergebnisse sind nach der Modelländerung korrekt als **OUTDATED** markiert.

## Nachgewiesene Abnahme

- **802 Backendtests**, keine Fehler; vollständiger Lauf auf dem endgültigen Stand, 137,36 Sekunden.
- **209 Frontendtests**, keine Fehler; TypeScript-Prüfung und Produktionsbuild erfolgreich.
- Vollständiger Wizard mit **251 Geräten**: Modell → Review → Routing → Topologie → Parameter → Capacity → Preflight → tatsächliche Simulation → Results → Intelligence; Wiederholung ohne zweiten Simulationsjob.
- Vollständiger HTTP-Ablauf durch die laufende Oberfläche auf Port 13500: **6/6 Nachrichten, 17/17 Signale**, alle erwarteten Routen und Netze beobachtet, Konformität PASS. Das Ergebnis enthält Release `0eddb7b2938d`. Intelligence behält seine berechtigte Warnungsbewertung.
- Browserprüfung des realen Bestands: alle drei markierten Stellen korrigiert; Preflight verlinkt jede der 47 offenen Nachrichten und alle 235 betroffenen Signale. Keine JavaScript-Seitenfehler in diesen Prüfungen.
- Browserprüfung mit 3.000 Vorschlagsänderungen: alle 60 Seiten erreichbar, Vollfassung nach Neuladen derselben Revision vorhanden, Freigabe bei fehlgeschlagenem Vollabruf gesperrt.
- Echter lokaler Sprachmodelllauf durch die laufende Oberfläche auf Port 13500, auf isoliertem Projekt: Modell lesen, gezielten Änderungsvorschlag erstellen, vor Freigabe unverändertes Modell, Review, Apply, Reload und idempotente Wiederholung. Fehlende menschliche Prüfabsicht wird mit 403, veraltete Revision mit 409 abgewiesen. Die Auskunft dauerte in diesem Lauf 32,8 Sekunden, der Änderungsvorschlag 134,5 Sekunden; das ist ein Einzelbeleg, keine allgemeine Laufzeitgarantie.
- Neustart der Produktionsanwendung bestanden: Projektstatus, Agentänderung, Vorschlag, Verlauf und Ergebnis-Snapshot bleiben erhalten. Der Simulationsjob existiert weiterhin genau einmal; erneutes Apply nach Neustart bleibt idempotent.
- Offline-Nachrechnung des ursprünglichen großen Laufs: 83 Netze, 225 Transportsegmente, 12.800 tatsächliche und 12.800 unabhängige Golden-Ereignisse. 193 Routen PASS und 24 FAIL; keine zuvor übersehenen Jitterverletzungen als PASS. Das ist ein Fehlernachweis am historischen Umfang und keine Freigabe aller 520 Signale.

## Offene Projektentscheidungen

Die [Liste der offenen Kommunikationsanforderungen](2026-09-09-offene-kommunikationsanforderungen.md) enthält die 47 Nachrichten mit Quellgerät und direktem Link zum Modellobjekt. Für jede Nachricht ist der tatsächliche Empfänger bzw. Transportbedarf festzulegen. Danach können die entsprechenden Routen angelegt und Capacity, Preflight und Simulation neu ausgeführt werden. Ein bewusst kleinerer Prüfauftrag ist über einen begründeten Teilumfang möglich; er erteilt keine Freigabe für das Gesamtmodell.

Zehn vorhandene Timeout-Budgets passen nicht zum Nachrichtenzyklus einschließlich zulässigem Jitter. Diese Widersprüche sind ebenfalls in der Liste aufgeführt. Zu entscheiden ist jeweils, ob der Sendeplan oder die fachliche Anforderung geändert werden soll. Die Migration hat keine Grenzwerte gelockert.

## Belege und Wiederherstellung

- [Vorher-/Nachher-Integrität](verification/2026-09-09-live-integrity.json)
- [Live-Routingmigration und Folgeprüfungen](verification/2026-09-09-live-route-migration.json)
- [Live-Browserabnahme](verification/2026-09-09-live-browser.json)
- [Live-Wizard und Simulationsbewertung](verification/2026-09-09-live-wizard-all-http.json)
- [Echter Agent auf der laufenden Version](verification/2026-09-09-live-agent-roundtrip.json)
- [Neustart und erneute Übernahme](verification/2026-09-09-live-restart-verification.json)
- [Identität von Workspace, Frontend und Backend](verification/2026-09-09-live-release-parity.json)
- [Vollständige Backendprüfung](verification/2026-09-09-backend-final-frozen.xml)
- [Agent- und Portdetails](2026-09-09-agent-und-portkorrekturen.md), [Modell-/Wizarddetails](2026-09-09-model-wizard-corrections.md), [Simulationsdetails](2026-09-09-transport-implementation.md)

Der unveränderte Projektexport liegt unter `verification/2026-09-09-live-before-deploy.nis-project.json`, der vorherige Containerquellstand unter `verification/2026-09-09-live-before-deploy-source.tgz`. Das alte Docker-Image konnte wegen bereits fehlender Docker-Content-Digests nicht als Image gesichert werden; deshalb wurde dessen laufender Quellstand direkt archiviert. Die Datenbank und das Runtime-Volume blieben bestehen. Die Sicherungen wurden nicht veröffentlicht.

Die Abnahme umfasst die beschriebenen Referenzabläufe und Regressionen. Sie ist keine Behauptung einer erschöpfenden Prüfung sämtlicher Protokolle, physikalischer Modelle oder Langzeit-/Mehrbenutzerlasten.
