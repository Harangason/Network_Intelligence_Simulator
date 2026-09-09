# Agent-Prüfung — 9. September 2026

Umfang: Chat-Oberfläche → Python EngineeringAgent → MCP → Vorschlag, Validierung, Freigabe und Übernahme → gespeicherter Gesprächsstand und Fortsetzung. Projekt: `I:/PycharmProjects/My_first_Network_Simulator`. Dieser Bericht enthält Analyse und Lösungsvorschläge. Bestehende uncommittete Dateien wurden nicht überschrieben.

Der Agent ist tatsächlich angebunden: Die Oberfläche überträgt strukturierte Ereignisse an den Python-Dienst, MCP handelt Werkzeuge aus, und Modelländerungen durchlaufen gespeicherte Vorschläge und eine menschliche Freigabe. Vier konkrete Laufzeitfehler und eine Installationslücke verhindern jedoch, den gesamten Agenten als verlässlich zu betrachten.

## Befunde

### P1 — Große Vorschläge verlieren beim Speichern des Chatverlaufs ihre vollständige Freigabeansicht

`frontend/src/lib/agent-chat-history.ts:45–66` kürzt rekursiv jede Liste auf 100 Elemente und fügt einen String als Kürzungshinweis an. Das betrifft auch `proposal.changes`, eine typisierte Liste von Änderungsobjekten. `frontend/src/lib/agent/proposal-client.ts:19–21` lädt bei unveränderter Vorschlags-ID und Revision nur den Status nach. Die Freigabekomponente behandelt dieses Ergebnis als geladen (`frontend/src/components/engineering-agent-event.tsx:45–50`) und aktiviert die Freigabe.

Isolierte Reproduktion mit den tatsächlichen Hilfsfunktionen: Aus einem Vorschlag mit 200 Änderungen werden 101 Einträge; der letzte lautet `[100 weitere Eintraege nicht gecacht]`. Die Aktualisierung derselben Revision belässt es bei 101 Einträgen und ruft ausschließlich `?view=status` auf. Der kanonisch gespeicherte Vorschlag enthält weiterhin 200 Änderungen. Ein erneut geöffneter Chat kann damit eine Freigabe auf Basis unvollständig dargestellter Inhalte anbieten. Das ist gerade bei Wizard-Projekten mit Hunderten oder Tausenden Objekten relevant.

Lösung: Im Verlauf Vorschlagsreferenzen und unveränderliche Zusammenfassungen mit exakten Anzahlen speichern. Vor Aktivierung der Freigabe den vollständigen kanonischen Vorschlag laden oder eine vollständig zugängliche Prüfung mit Seitennavigation anbieten. Stringmarker dürfen keine typisierten Fachobjekte ersetzen.

Abnahme: Vorschlag mit 3.000 Änderungen → Verlauf speichern → Chat schließen und öffnen → alle 3.000 Änderungen zugänglich, Anzahl korrekt; Freigabe bleibt deaktiviert, solange die vollständigen Prüfdaten fehlen. Unveränderte Revision und fehlgeschlagenes Nachladen ausdrücklich testen.

### P1 — Der Hintergrund-Heartbeat verlängert die Gesprächssperre im falschen Projekt

`backend/engineering/agent_tools/api.py:320–331` startet einen einfachen `threading.Thread` und ruft `conversation.renew(run_id)` ohne aktivierten Projektkontext auf. `conversation.renew` (`conversation.py:164–179`) ermittelt das Projekt über `current_project_id()`. Dessen ContextVar verwendet standardmäßig `default` (`backend/engineering/project_context.py:13–16`). Die umgebenden `execute(authority, ...)`-Aufrufe setzen den Kontext nur für ihre eigene Ausführung; der neue Heartbeat-Thread übernimmt ihn nicht. Der Wizard-Tracker setzt seinen eigenen Kontext erst für seine separate Aktualisierung nach `renew`.

Isolierte Reproduktion mit echtem Thread: Im übergeordneten Thread ist `audit-actual-project` aktiv, im Heartbeat-Thread dagegen `default`. Die tatsächliche Gesprächssperre gilt anfangs 300 Sekunden (`conversation.py:105`). Für die falsche Projekt-/Laufkombination liefert `renew` false; dieses Ergebnis wird ignoriert. Lange Läufe können deshalb im Wizard weiterhin aktiv erscheinen, während ihre Gesprächssperre abläuft. Ein zweiter Auftrag kann dann dasselbe Gespräch übernehmen; der erste Worker kann beim nächsten gespeicherten Ereignis scheitern.

Lösung: Verlängerung in einer ausdrücklich projektgebundenen Transaktion ausführen, Rückgabewert prüfen und eine gemeinsame gespeicherte Ausführungsidentität für Gespräch und Wizard verwenden.

Abnahme: Ein Lauf über sechs Minuten verlängert seine Sperre im korrekten Projekt, weist parallele Anfragen zurück, verändert das Standardprojekt nicht und bleibt nach Verbindungsverlust fortsetzbar. Eine beschleunigte Testuhr ist geeignet; dabei muss der tatsächliche Thread-/Callback-Pfad laufen. Ein isolierter `renew`-Test mit bereits gesetztem Projektkontext genügt nicht.

### P1 — Frei formulierte Erstellungsaufträge können Erfolg ohne Erstellungswerkzeug behaupten

`backend/agent_core/core/engineering_agent.py:585–598` weist eine Erfolgsaussage ohne Werkzeugaufruf nur für Prompts mit speziellen bestätigten Wizard-Markierungen zurück. Normale Anfragen erhalten `ANSWERED`, sofern vorherige Werkzeugaufrufe erfolgreich waren; bereits das anfängliche `inspect_project` erfüllt diese Bedingung. Der Modelltext wird unverändert an das RESULT-Ereignis weitergegeben.

Isolierte Reproduktion: Auftrag `Lege ein Gateway an.`, injizierte Reasoner-Antwort `Das Gateway wurde erfolgreich angelegt.`, keine Werkzeugaufrufe → Status `ANSWERED`, ausschließlich `inspect_project`, null Vorschläge. Damit ist belegt, dass die Orchestrierung eine unbelegte Erfolgsaussage zulässt. Nicht belegt ist, dass das echte Sprachmodell genau diese Aussage im aktuellen Nutzerprojekt ausgegeben hat.

Lösung: Für jede Anfrage Lese- oder Änderungsabsicht und erwartete Ergebnisse ausdrücklich festhalten. Erfolgsmeldungen müssen auch im normalen Chat aus Werkzeugergebnissen beziehungsweise bestätigten kanonischen IDs entstehen. Ohne Änderungsvorschlag `INCOMPLETE` mit der fehlenden Arbeit melden und nacharbeiten oder den konkreten Hinderungsgrund nennen.

Abnahme: Bewusst irreführende Reasoner-Antworten ohne Werkzeuge dürfen frei formulierte Anlege-, Änderungs- und Löschaufträge niemals als ausgeführt darstellen. Echte Lesefragen dürfen weiterhin `ANSWERED` liefern.

### P2 — Allgemeine Fortschrittsmeldungen löschen die gespeicherte Workload-ID

`backend/engineering/agent_tools/conversation.py:140–141` ersetzt `active_workload` bedingungslos durch `event['workload'].get('workload_id')`. Allgemeine Fortschrittsereignisse verwenden dasselbe Feld nur mit `completed` und `total` (`engineering_agent.py:14–17, 621–626`). Dadurch überschreiben sie eine vorhandene Workload-ID mit `None`. Ein strukturiertes `RESUME` stellt den Auftrag anschließend aus diesem Feld wieder her (`conversation.py:110`).

Isolierte Reproduktion: Zustand `active_workload='workload-existing'` + PROGRESS `{completed:1,total:12}` → `active_workload=None`. Das ist ein belegter Fehler im Zustandsvertrag. Eine sichtbare Duplikaterzeugung oder fehlgeschlagene Fortsetzung im Liveprojekt wurde nicht ausgelöst.

Lösung: Ausführungsfortschritt und Workload-Referenz getrennt modellieren oder die gespeicherte Identität nur bei ausdrücklich vorhandener und gültiger Workload-ID aktualisieren.

Abnahme: Wechselnde Workload-, Reasoning-, Wizard- und Frageereignisse erhalten die aktive Workload-ID bis zu einem ausdrücklichen Abschluss oder Zurücksetzen.

### P1 — Die dokumentierte lokale Neuinstallation enthält das benötigte MCP-Paket nicht

Die README empfiehlt `uv sync --project backend` für die Erstinstallation (`README.md:76,349`). `backend/requirements.txt:8` nennt `mcp>=2.1,<3`; `backend/pyproject.toml` enthält diesen Eintrag nicht. Auch in den 38 Paketen der bestehenden `backend/uv.lock` fehlt `mcp` vollständig. Docker installiert dagegen ausdrücklich aus `backend/requirements.txt` (`Dockerfile:20–22`). Damit beschreiben lokale Installation und Container unterschiedliche Abhängigkeiten.

Es handelt sich um eine echte externe Laufzeitabhängigkeit, nicht um eine interne Ersatzimplementierung: `backend/agent_core/api/mcp_client.py:3` importiert `Client` aus `mcp`; `backend/simulator_engineering_mcp/server.py:5–6` importiert `MCPServer` und `ToolAnnotations` aus dem SDK. In der vorhandenen lokalen Umgebung kommt `mcp` aus `backend/.venv/Lib/site-packages/mcp/__init__.py`, Version `2.1.1`. `create_app` importiert die Agent-API verpflichtend (`backend/app/__init__.py:21–22`); ein fehlendes SDK betrifft deshalb bereits den Backendstart.

Kontrollierte Reproduktion ohne Installation oder Deinstallation: Ein Importfilter simuliert ausschließlich das fehlende `mcp`-Paket. Der tatsächliche Aufruf `create_app(testing=True)` endet dann mit `ModuleNotFoundError: No module named 'mcp'`. Eine vollständig neue `uv`-Umgebung wurde für diesen Nachweis nicht angelegt. Der bestehende Lockfile-Stand erklärt jedoch, weshalb der dokumentierte Installationsweg das benötigte SDK nicht bereitstellt.

`httpx` fehlt zwar ebenfalls als direkte Abhängigkeit in `pyproject.toml`, ist aber im Lockfile über `openai` transitiv enthalten. Das ist gegenwärtig **kein zusätzlicher belegter Installationsblocker**. Da eigener Anwendungscode `httpx` importiert, sollte die direkte Abhängigkeit trotzdem ausdrücklich deklariert werden.

Lösung: Eine verbindliche Quelle für Python-Abhängigkeiten pflegen, `mcp` dort aufnehmen, Lockfile aktualisieren und Docker-/lokalen Installationsweg daraus ableiten. Die README muss denselben überprüften Weg beschreiben.

Abnahme: Leere Umgebung ausschließlich nach README aufsetzen; ohne nachträgliches manuelles Nachinstallieren Backend und Agent laden, MCP-Discovery sowie einen isolierten Werkzeugaufruf ausführen. Lokale Installation und Container müssen dieselben benötigten Pakete und kompatiblen Versionen enthalten.

## Gültigkeit für Arbeitsverzeichnis und laufenden Container

Die lesende Prüfung des laufenden Docker-Containers `NetworkIS` unter `/app` bestätigt:

- `conversation.py`, `engineering_agent.py`, `agent-chat-history.ts` und `project_context.py` sind nach Vereinheitlichung der Zeilenumbrüche identisch zum Arbeitsverzeichnis.
- `api.py` weicht insgesamt ab, der fehlerhafte Heartbeat-Pfad ist jedoch gleich: Containerzeilen 264–275, Arbeitsverzeichniszeilen 320–331.
- `proposal-client.ts` weicht insgesamt ab; `refreshProposal` in den Zeilen 14–27 ist gleich.

Die vier Laufzeitbefunde sind somit in beiden geprüften Codeständen vorhanden. Die Reproduktionen liefen gegen die Quellen im Arbeitsverzeichnis. Produktionsmodelldaten wurden nicht verändert und keine Produktionsinferenz wurde ausgeführt. Die zusätzliche Installationslücke betrifft den dokumentierten lokalen Aufbau; im laufenden Container ist das SDK vorhanden.

## Prüfung und Grenzen

- Bestehende Backendtests: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_agent_core.py backend/tests/test_agent_chat_ux.py backend/tests/test_engineering_mcp.py -q -p no:cacheprovider --basetemp .tmp/audit-agent-20260909-tests` → **79 bestanden in 30,62 Sekunden**. Enthalten sind ausgehandeltes MCP, Vorschlagsberechtigungen und Projekttrennung, Zurückweisung veralteter Modellstände, atomare Übernahme, Verbindungsabbruch, strukturierte Fragen und Tests mit injiziertem Reasoner. Datenbank-Fixtures verwenden eigene Testprojekt-IDs.
- Gezielte Frontendtests für `proposal-client`, `agent-response`, `agent-run-status` und `agent-task-events` → **34 bestanden**, keine Fehler oder übersprungenen Tests. Die grünen Tests decken die vier vollständigen Laufzeitfehlerpfade oben bisher nicht ab.
- Ollama `/api/tags` ist erreichbar und listet die konfigurierten Modellnamen `qwen3.8:27b` und `llama3.1:8b`. Eine Modellliste belegt Verfügbarkeit, aber keine erfolgreiche echte Werkzeugausführung durch das Sprachmodell.
- Die Reproduktionen unter `verification/2026-09-09-agent-repro.py` und `verification/2026-09-09-agent-history-repro.mjs` verwenden ausschließlich Arbeitsspeicherzustand und simulierte Werkzeug-/Fetch-Ergebnisse. Ihre Ausgaben liegen daneben. Die Installationsprüfung ist separat als `verification/2026-09-09-agent-dependency-repro.py` mit Ausgabe gespeichert.
- Ein echter Sprachmodellauftrag vom Prompt über Prüfung, Freigabe, Übernahme, Neuladen und Fortsetzung bis zur Simulation wurde im Rahmen dieser Analyse nicht ausgeführt. Diese Abnahme bleibt in einem isolierten Referenzprojekt erforderlich.

## Empfohlene Agent-Abnahme vor Freigabe einer Version

Ein kleines, eindeutig spezifiziertes Referenzsystem und ein großes Projekt durch dieselbe sichtbare Oberfläche führen: Auftrag → Soll-/Ist-Abgleich → deterministische Fachvalidierung → vollständige Vorschlagsprüfung → einmalige Übernahme → Neuladen → Fortsetzung → Simulation → Ergebnis. Voraussetzungen sind exakte Soll-, erzeugte, gültige und freigegebene Anzahlen, erhaltene Identitäten, vollständig zugängliche Prüfdaten, keine doppelten Objekte nach Wiederholungen und Abschlussnachweise für die aktuelle Modellrevision. Sowohl Wizard als auch frei formulierten Chat prüfen, einschließlich nicht verfügbarem Modell, langer Inferenz, Verbindungsverlust, veraltetem Vorschlag und Backendneustart.
