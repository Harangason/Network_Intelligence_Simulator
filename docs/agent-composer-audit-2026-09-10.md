# Engineering-Assistent: Auftragsstart und Eingabe

Stand: 10.09.2026 · aktiver Build `f19f21d9f8cb`.

## Ursache

`GlobalAgentWidget` prüfte beim Öffnen, beim Fensterfokus und alle 30 Sekunden die Routing-Freigaben. Bei freigegebenen Routen und einem offenen Folge-Workflow erzeugte `queueEngineeringWorkflowContinuation` einen neuen Auftrag. `AgentChatCore` sendete zusätzlich gespeicherte Aufträge beim Laden und Task-Events sofort. Dadurch verschwand der Einstieg mit vier Fragen hinter einem bereits laufenden Auftrag.

Die vorhandene Texteingabe war während eines Laufs gesperrt. Verlauf, Aktivitätsprotokoll, Freigaben und Formular konkurrierten um die begrenzte Widget-Höhe. Eine Dateieingabe fehlte im Chat. Fragen über das externe `engineering-agent:ask`-Event konnten beim ersten Öffnen verloren gehen, weil der Chat erst danach gemountet wurde.

## Geändertes Verhalten

- Öffnen, Fokus, Statuspolling und Laden des Verlaufs senden keine Agentenanfrage und erzeugen keinen Folgeauftrag.
- Die vier Einstiegsfragen füllen einen bearbeitbaren Entwurf. Bei vorhandenem Verlauf sind sie unter „Frage vorbereiten“ erreichbar.
- Gespeicherte Aufträge und Task-Events erscheinen als „Vorbereiteter Auftrag“ mit Vorschau, „Auftrag starten“ und „Verwerfen“. Routing-Freigaben bleiben Voraussetzung für entsprechend gesperrte Aufträge. Abgeschlossene oder fehlerhafte Workflows starten keine automatische Schleife.
- Der Eingabebereich bleibt unter dem scrollbaren Gesprächsbereich sichtbar. Während einer Antwort kann bereits die nächste Frage geschrieben werden. Enter sendet, Umschalt+Enter erzeugt eine neue Zeile; IME-Komposition löst kein Senden aus.
- Externe Fragen werden vor dem erstmaligen Mounten erfasst und als Entwurf übernommen. Ein vorhandener Entwurf wird ergänzt.
- „+ Dokument“ unterstützt PDF mit Text, DOCX, TXT, Markdown, CSV, JSON, XML, DBC, ARXML, LDF, ASC, LOG und YAML. Höchstens vier Dateien à 5 MB; pro Datei bis 16.000 Textzeichen, bei PDFs bis 40 Seiten. Die Vorschau kennzeichnet Auszüge. Scans ohne Text benötigen OCR außerhalb dieser Funktion.
- Die Vorschau extrahiert tatsächlich Inhalte, einschließlich Word-Tabellen, ohne Agentenlauf oder Modelländerung. Leere, beschädigte, nicht unterstützte und übergroße Dateien werden abgewiesen.
- Dokumente werden als typisierte Quellen im Gespräch transportiert und bei Rückfragen beibehalten. Der Nutzerauftrag bleibt getrennt. Erst nach der Auftragsklassifikation fügt der lokale Reasoner die Quellen dem Modellkontext hinzu, ausdrücklich als nicht vertrauenswürdiges Quellenmaterial. Dokumenttext kann damit nicht durch Wizard-Schlüsselwörter den automatischen Auftragsverteiler auslösen.

## Prüfung

- 16 Backendtests: PDF/DOCX/Text-Extraktion, Zeichencodierungen, Größen- und Formatfehler, leere PDFs, Kennzeichnung gekürzter Texte, schreibfreie Vorschau und Quellenübergabe an den Reasoner.
- Zwei Frontendtests für den Datenvertrag von Anhängen.
- Der echte Next-POST-Handler wurde mit einem simulierten Agenten-Endpunkt geprüft: Frage und Dokumentquellen kommen getrennt an; Rückfragen behalten Quellen; ungültige Anhänge ergeben HTTP 400.
- Browserprüfung am laufenden NIS mit vollständig freigegebenen Routen und einem unvollständigen Workflow: Öffnen, 30-Sekunden-Poll und Fokus senden keinen Auftrag. Alle vier Einstiege sind bedienbar. PDF/DOCX/DBC werden über den echten Vorschau-Endpunkt gelesen. Genau zwei ausdrücklich ausgelöste Chat-Anfragen werden gesendet. Wiederöffnen, vorbereiteter Auftrag, Dateifehler, Auszug, Entfernen, externe Frage und Eingabe bei minimaler Höhe sowie 390 × 700 Pixeln geprüft; keine Browserfehler.
- Produktionsbuild und TypeScript-Prüfung erfolgreich.

Die Browserprüfung verwendet einen isolierten Gesprächsverlauf und simulierte Agentenantworten. Sie verändert keine Projektdaten und bewertet nicht die fachliche Qualität eines echten Modelllaufs.

Reproduzierbar mit `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_agent_documents.py -q`, im Frontend mit `node --test src/lib/agent/chat-attachments.test.mjs`, `node scripts/test-agent-chat-transport.mjs` und `node scripts/verify-agent-composer.mjs`. Die Browser-Fixtures entstehen durch `pdf_document()` und `docx_document()` aus dem Backendtest; Ergebnis unter `backend/runtime/agent-composer-browser-result.json`.
