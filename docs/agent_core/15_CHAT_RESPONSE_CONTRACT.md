# Engineering Assistant: Antwortvertrag und Gesprächszustand

Die Chat-UX-Spezifikation wird in die bestehende Python-Agent-Core/MCP-Architektur integriert. Der Frontend-Chat bleibt Transport und Darstellung; Fachänderungen laufen weiterhin über Proposal, Validierung, menschliche Freigabe und Apply.

## Datenfluss

`UI AgentInput → Next-Transport → Python Gesprächsdienst → Agent Core → MCP-Fachdienste → AgentResponse → Schema-Prüfung → UI-Karte`.

Auswahlantworten enthalten Frage-ID und Options-IDs. Anzeigetext ist keine Engineering-Eingabe. PostgreSQL speichert pro Projekt die aktive Frage, beantwortete Entscheidungen, Vorschlag, Workload, Freigaben und Auswahlkontext. Ein zeitlich begrenzter Run-Lease verhindert parallele Fortsetzungen desselben Gesprächs. Die vorhandene projektweite Transaktion schützt Antwortprüfung und Zustandswechsel gemeinsam.

Fragen sind OPEN, ANSWERED, SKIPPED, EXPIRED oder OUTDATED. Modellrevision, Gültigkeitsdauer und Auswahlkontext werden vor der Fortsetzung geprüft. Browserhistorie kann diesen Zustand nicht überschreiben. Findings erhalten persistierte Entscheidungen; bei gewünschter Wiedervorlage führt eine Modelländerung zu NEEDS_REVIEW.

Der Python-Vertrag liegt in `backend/agent_core/api/agent_response.py`; Frontend-Ereignisse werden zusätzlich mit Zod geprüft. Ungültige Karten werden als sichere TEXT-Antwort mit protokolliertem Vertragsfehler angezeigt. Es gibt keine durch das Sprachmodell erzeugten UI-Komponenten oder ausführbaren Aktionsziele.

## Verifikation

Die Abnahme umfasst Vertragsfehler, Auswahlvalidierung, konkurrierende Antworten, Kontextalterung, den Kamera-Dialog einschließlich separater Freigabe/Übernahme und Browserbedienung. Konkrete Ergebnisse werden nach Durchführung im Implementierungsaudit ergänzt.

## As-built: Speicherung, Aktionen und Grenzen

Schema 23 ergänzt `engineering_agent_conversations` und `engineering_agent_responses`. Das Gespräch besitzt einen 300-Sekunden-Lease; laufende Antworten, neue Fragen und Auswahlannahme verwenden denselben projektweiten PostgreSQL-Lock. Eine verlorene Verbindung beendet den Lauf; RESUME übernimmt gespeicherte Antworten und den bestehenden Workload bzw. Vorschlag. Ein neuer Freitextauftrag beginnt eine neue Klärung, ohne historische Modellobjekte zu löschen.

Die zehn Antworttypen sind in `agent_response.schema.json` maschinenlesbar dokumentiert. `CONTEXT` und `HEARTBEAT` sind interne Transportnachrichten, keine sichtbaren Kartentypen. Die UI akzeptiert ausschließlich bekannte Navigationstypen und interne Projekt-URLs. Modellgeneriertes Markup wird nicht interpretiert. Große Texte und Analysedaten erhalten eine Antwort-ID: Die Bubble transportiert die Kurzfassung, `/studio/agent?project=…&response=…` lädt die vollständige Auswertung projektgebunden nach.

Der serverseitige UI-Verlauf vereinigt Nachrichten-IDs atomar, hält höchstens 60 Nachrichten und schützt vollständige Antworten gegen ältere Teilstände. Die Oberfläche rendert zunächst 20 Nachrichten; weitere werden ausdrücklich geladen. Ein fehlender UI-Cache kann die aktuelle Frage aus dem Backend wiederherstellen. Die Browser synchronisieren ruhende Verläufe regelmäßig. Scrollen in alten Nachrichten unterbindet automatisches Springen; neue Antworten erhalten einen Hinweis.

Normale Auswahlantworten senden QUESTION_ANSWER mit Frage-ID und Options-IDs, optionale Fragen SKIP_QUESTION. Fehler lassen sich ausdrücklich mit RESUME fortsetzen. FINDING_ACTION startet die Maßnahmenanalyse anhand des gespeicherten Findings. Risikoübernahme verlangt eine Begründung mit mindestens zehn Zeichen; die Wiedervorlage bei Modelländerungen wird mitgespeichert. Eine Maßnahme bleibt ein Vorschlag und erhält keine implizite Freigabe.

Bearbeiten erzeugt eine neue Vorschlagsfassung mit geänderter Beschreibung und/oder Objektnamen. Die alte Fassung wird abgelehnt und mit ihrem Nachfolger verknüpft. Validierung und menschliche Freigabe müssen erneut erfolgen. Das Öffnen einer alten Review-Karte findet die aktuelle Fassung; historische MCP-Abfragen behalten den ursprünglichen Vorschlag.

Der Kamera-Dialog klärt nacheinander Abdeckung, Ausgaben, Sensoranordnung und Vorschlagserstellung. Vier Kameras ergeben sich ausschließlich aus der ausdrücklich gewählten Vierkamera-Anordnung mit dokumentierter Sichtfeldannahme. Ethernet, Erfassungsfunktionen, Vision Controller und Daten-/Statusmodelle werden über den bestehenden Proposal-Dienst erzeugt. Noch fehlende Bildraten-, Kodierungs-, Bandbreiten- und Timingdimensionierung wird als Finding ausgewiesen. Der Chat behauptet damit keine freigegebene Gesamtkommunikation oder bestandene Simulation. Explizite Mengenaufträge für Funktionen und Signale bleiben im vorhandenen Generator-/Workload-Pfad.

Der Graph-Button bleibt erhalten. Minimieren lässt einen laufenden Chat weiterarbeiten und zeigt seinen Aktivitätszustand am Graphen. Farbwerte folgen Theme-Tokens; reduzierte Bewegung wird beachtet. Die geöffnete Ansicht ist auf Desktop 380–440 Pixel breit und mobil ein Drawer über die volle Fensterhöhe.
