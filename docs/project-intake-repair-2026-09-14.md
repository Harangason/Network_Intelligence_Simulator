# Kleine Projekte aus einer natürlichen Anforderung aufnehmen

Stand: Implementiert, geprüft und am 14.09.2026 installiert. Build `3a963da2c3f2`.

## Nachgewiesener Fehler

Die Anforderung „ich möchte ein kleines Projekt: ich habe drei sensoren die temperatur
messen und ein respary pi und aktoren die ventile steuern“ wurde als Suche im bestehenden
Modell behandelt. Im schreibgeschützt gelesenen Produktprotokoll des Projekts
`network-project-20260910042736034-d11591d0` folgen auf `inspect_project` und
`inspect_assistant_capabilities` nur `search_model` und anschließend `ANSWERED`.
Es gibt keinen zugehörigen Erstellungsauftrag oder Modellvorschlag.

Eine zweite Ursache liegt im Geräteentwurf: Vor der Korrektur ergab dieselbe Anforderung
bei neutraler Domäne Temperatur-, Spannungs- und Stromsensoren, keinen Raspberry Pi
und einen angenommenen CAN-Anschluss. Gezählt wurde die Sensorzahl, aber die ausdrücklich
genannte Messgröße ging bei der Auffüllung aus dem Vorlagenkatalog verloren.

## Änderung

- Erkennbare neue Projektwünsche erhalten eine eigene Aufnahme über das echte MCP-Werkzeug
  `prepare_project_request`. Das lokale Sprachmodell erhält ausschließlich dieses
  Planungswerkzeug. Es kann fachliche Vorschläge und Rückfragen beitragen; die ursprüngliche
  Nutzeranforderung und die Projektbindung bleiben serverseitig erhalten.
- Eine leere Suchantwort oder ein nicht verfügbarer Modelldienst verhindern die geführte
  Aufnahme nicht. Die Ausgabe unterscheidet einen modellgestützten Planungsvorschlag von
  der geführten Grundaufnahme. Beides ist ein unbestätigter Entwurf, keine Modellanlage.
- Eine ausführbare Karte öffnet den bestehenden Engineering-Wizard mit dem editierbaren
  Anforderungstext. Der Entwurf ist an das Projekt und den Browsertab gebunden. Änderungen
  am Text überstehen ein Neuladen. Ein vorhandener Auftrag wird nicht überschrieben.
- Drei Temperaturmessstellen bleiben drei Temperaturmessstellen mit getrennten Signalnamen.
  Der Raspberry Pi wird als EmbeddedController erkannt. Ein vorhandener Controller anderer
  Unterklasse erfüllt das Controller-Soll; es wird dafür kein zusätzlicher Controller erfunden.
- Ungenannte Pi-Anschlüsse bleiben `Other`. Eine ungenannte Ventil-/Aktoranzahl erscheint
  in der übernommenen Anforderung als Pflichtfeld statt als bestätigte Null.
- Es werden keine Ventilanzahl, Sensor-Ventil-Zuordnung, elektrische Eignung oder bestätigte
  Regelungsfristen aus dem kurzen Satz erfunden. Die spätere Modellanlage bleibt an den
  vorhandenen Wizard- und Freigabevertrag gebunden.

## Prüfung und Grenzen

Die gezielte Prüfung umfasst natürliche Projektwünsche, Abgrenzung von Leseanfragen und
bestätigten Wizardaufträgen, eine unbrauchbare Suchantwort des Modells, unveränderte
Originalanforderungen trotz abweichender Modellargumente, Projektbindung, Geräteidentitäten
und offene Anschluss-/Anzahlfragen. Ein echter Browserlauf mit isoliertem Backend und MCP
prüft Chat → Karte → Wizard → Geräteumfang → Textänderung → Neuladen.

Der zusätzliche Test mit dem echten lokalen Modell `qwen3.8:27b` und ausgehandelter
MCP-Verbindung besteht (26,18 Sekunden; `planning_mode=model_assisted`). Die Antwort
und Toolspur liegen in `backend/test-output/project-intake-live-response.json`.
Der erste Diagnoselauf scheiterte beim Schreiben eines Unicode-Pfeils auf die
Windows-Testkonsole, nicht bei der Planung. Der Wiederholungslauf verwendet eine
UTF-8-Datei und ASCII-sichere Konsolenausgabe. Beim Testprozessende wurden außerdem
Hinweise des Datenbankpools protokolliert; der isolierte Datenbankcontainer wurde entfernt.
Der deterministische Release-Gate prüft die Offline-Aufnahme und die bisherigen kleinen
und großen Neun-Stufen-Abläufe. Diese Trennung verhindert, dass eine bloße Modellantwort
als Beweis für eine tatsächlich erzeugte und simulierte Architektur gilt.

Die ersten Gateansätze `cb7f48218b85` und `95581d5de724` wurden während der isolierten
Backendtests bewusst beendet, weil die anschließende fachliche Prüfung noch die Geräte-
Identität beziehungsweise die Entwurfserhaltung erweitert hatte. Ihre FAIL-Receipts bleiben
erhalten; sie sind keine Freigaben. Der nun eingefrorene Kandidat liegt unter
`backend/test-output/release-source/project-intake-20260914`. Er basiert auf dem zuvor
freigegebenen Stand `ab2ecd9d7d71` mit einzeln dokumentierten Änderungen. Andere Änderungen
im gemeinsam genutzten Arbeitsverzeichnis werden nicht mit ausgeliefert.

## Abgeschlossene Freigabe und Installation

Release-Gate `6edcdd977ed0`: **PASS**, alle sieben Prüfungen bestanden:
Typecheck, 331 Frontendtests, 1552 Backendtests (2 übersprungen), Produktionsbuild,
6 Browser-E2E sowie kleiner und großer HTTP-Akzeptanzlauf bis Stufe neun.
Der große Lauf prüfte 552 Hardware-Knoten, 653 Nachrichten, 1404 Signale und
838 Routen mit vollständiger beobachteter Abdeckung. Fachliche WARNING-Zustände
bei Kapazität, Validierung und Assessment bleiben sichtbar und werden nicht als
uneingeschränkte funktionale Timingfreigabe ausgegeben.

Installiert wurde exakt das im PASS-Receipt geprüfte Image
`sha256:40ce6512472c1f77a069ebb104d4b71a42aab718bb7771ef4f3a01fe903d1463`.
Die Quelle wurde gegen den vorigen Release abgegrenzt: 12 deklarierte geänderte
Dateien, 1492 unveränderte Dateien, keine unerwarteten Änderungen.

Vor der Installation entstand ein konsistentes Datenbankbackup (254540612 Bytes).
Die anschließende Prüfung besteht mit 18/18 Kontrollen: exaktes Image, Bereitschaft
und Build auf beiden Produktports, Projektbestand und Workflowrevision,
Snapshots und Jobs, Datenbankimage, Volumes, Laufzeiteinstellungen und GPU-Konfiguration.
Das aktuelle Projekt enthielt bereits vor dieser Installation keine Modellobjekte.
Die Nutzeranfrage wurde im Produkt nicht erneut abgeschickt und kein Hardwaremodell
ohne Wizardbestätigung angelegt.

Nachweise: `backend/test-output/project-intake-release-gates/6edcdd977ed0/receipt.json`,
`source-provenance.json`, `product-backup.json` und
`product-deployment-verification.json` im selben Verzeichnis.
