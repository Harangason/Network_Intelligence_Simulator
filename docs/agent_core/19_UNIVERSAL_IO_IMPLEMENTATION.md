# Universal Input/Output: integriertes Agenten-Update

Stand: 14.09.2026. Grundlage: Nutzerfreigabe des Updateplans in
[18_UNIVERSAL_INPUT_OUTPUT_UPDATE.md](18_UNIVERSAL_INPUT_OUTPUT_UPDATE.md).

## Implementierter Umfang

Die erste integrierte Fassung erweitert den bestehenden Agenten, Gesprächsspeicher,
MCP-Katalog und Anschlussauftrag. Es gibt keine zusätzliche Ausführungszustandsmaschine
für Modellmutationen und keine zweite Engineering-Berechnung.

- `api/input_output.py` definiert versionierte Eingabe-, Typing-, Reasoning-,
  Visualisierungs- und Ausgabeverträge. Vorhandene Text-, Datei-, Auswahl- und
  Entscheidungsrequests werden in `conversation.begin` normalisiert und zusammen
  mit dem angenommenen Auftrag gespeichert. Berechtigungen kommen weiterhin vom Server.
- `context/input_adapter.py` trennt Nutzertext von Dokumentquellen, erfasst Hashes
  des extrahierten Textes und verwendet vorhandene Lauf-/Operations-/Revisionsbezüge.
  Diese Texthashes sind keine Hashes der Originaldatei und keine Echtheitsgarantie.
- `goal_execution/typing.py` löst kanonische IDs, Namen und explizite Aliase auf.
  Mehrdeutigkeit bleibt offen; Intent und Objekttyp sind getrennt. Die bestehende
  Graphsuche und Anschlussplanung verwenden diese gemeinsame Auflösung.
- Die bestehende Capabilityliste liefert Skillverträge und eine explizite Liste
  unterstützter Eingabeadapter. Die Verfügbarkeit berücksichtigt registrierte
  Werkzeuge und serverseitige Berechtigungen. `type_engineering_input` ist ein
  lesendes MCP-Werkzeug; Autorisierungsoperationen werden dadurch nicht freigegeben.
- Anschlusspläne enthalten Versionen und einen Outputplan. Der vorhandene
  `GoalCompletionEvaluator` kann fehlende aktuelle Pflichtoutputs erkennen.
- `goal_execution/outputs.py` erzeugt aus den tatsächlich gespeicherten physischen
  Pfaden ein Netzwerkdiagramm sowie getrennte Routing-, Kapazitäts-, Sendeplan-,
  Timing- und Preflightnachweise. Es berechnet diese Fachwerte nicht neu.
- `AgentResponse.outputs` transportiert mehrere typisierte Ergebnisse; Backend-,
  Frontendschema und JSON-Schemadokument wurden gemeinsam erweitert. Allgemeine
  Ergebnisantworten erhalten einen CHAT-Output mit Input-/Werkzeugreferenzen.
- `engineering-outputs.tsx` rendert ausschließlich Daten durch registrierte React-
  Komponenten. Es nutzt vorhandene Farbtokens, ein scrollbar begrenztes Diagramm
  und eine zugängliche Beziehungstabelle. Layoutkoordinaten sind keine Einbauorte.

## Fehler, Wiederaufnahme und Revision

Ausgaben werden nach der kanonischen Ausführung außerhalb ihres Rollbackblocks
erzeugt. Ein Ausgabefehler setzt den Auftrag auf `OUTPUT_PENDING` und den Gesamtabschluss
auf unvollständig; der fachliche Zustand bleibt gespeichert. Eine ausdrückliche
Fortsetzung erzeugt nur die fehlende Ausgabe. Ports, Routen und Jobs werden nicht
wegen eines Darstellungsfehlers nochmals angelegt.

Aktuelle Ausgaben werden anhand eines revisions- und evidenzgebundenen Fingerprints
wiederverwendet. Ändert sich die Quellarchitektur, werden alte Outputs als STALE und
der Auftrag als PLAN_STALE ausgewiesen. Die Ergebnisabfrage prüft diesen Zustand;
die Oberfläche lädt ihn nach Mount, Fokuswechsel und Modelländerungsereignissen.
Ausstehende Simulationsfolgen benutzen weiterhin die vorhandene Folgeausführung.

## Tatsächliche Grenzen

Dies ist die im Plan beschriebene erste integrierte Fassung, nicht die vollständige
Unterstützung sämtlicher Eingabe-/Diagrammarten des Ursprungsdokuments.

- IMAGE, TABLE, STRUCTURED_DATA, EVENT, TRACE, SIMULATION_RESULT und MCP_RESULT
  sind noch keine allgemein aufrufbaren Eingabeadapter. Die Capabilityantwort
  weist sie als nicht verfügbar aus; ein entsprechender `input_type` am Chat-
  Einstieg wird vor Auftragsstart mit NOT_SUPPORTED zurückgewiesen. Bestehende
  spezielle Trace-/Simulationswerkzeuge bleiben verfügbar.
- Dateiunterstützung bedeutet weiterhin begrenzte Textextraktion, keinen allgemeinen
  fachlichen DBC-/ARXML-/LDF-Import und keine Bilderkennung.
- Kanonische Typisierung und bestehende einzelne Klassifikationswerkzeuge sind
  integriert; eine universelle automatische ML-/Ontologie-Kaskade für unbekannte
  neue Objekte wird nicht behauptet.
- Netzwerkdiagramm und Prüftabelle sind implementiert. Zeitreihen, Timelines,
  Sequenzdiagramme und neue Report-/Dateiexporter benötigen eigene Adapter.
- Die Ausgabe ist der betroffene Anschlussumfang, nicht automatisch das gesamte
  Projekt. Über 200 Diagrammobjekte/Tabellenzeilen bzw. 400 Beziehungen werden als
  ausdrücklich gekennzeichneter Ausschnitt dargestellt.
- Die erweiterten Anschlussausgaben sind kein allgemeiner Ausführungsadapter für
  alle GoalTypes. Die Grenzen aus `16_MODEL_AWARE_EXECUTION.md` bleiben bestehen.

## Prüfungen

Der erste gezielte Lauf bestand mit **90 Backendtests**, darunter neue echte
SQL-Prüfungen für ParkAssist, Ausgabe-Wiederverwendung, Ausgabefehler nach erfolgreicher
Modellarbeit und veraltete Revisionen. TypeScript und **17 gezielte Frontendtests**
bestanden. Die Tests laufen ausschließlich über die isolierte Datenbankinfrastruktur.

Der echte MCP-Verbindungstest prüft zusätzlich die beiden Outputs, Projektbindung
und die kanonischen Labels ParkAssist, DriverAssistance und Chassis_CAN.

Eine separate Browser-Komponentenprüfung mit Beispieldaten prüfte Desktop und
420-Pixel-Mobilansicht. Die mobile Dokumentbreite blieb bei 420 Pixel; das Diagramm
scrollt innerhalb seines Bereichs. Dies ist ausdrücklich kein zusätzlicher
neunstufiger Wizard-E2E-Nachweis. Eine dabei gefundene React-Tooltipwarnung wurde korrigiert.

Der vollständige Release-Nachweis und ein eventueller Bereitstellungsstand werden
erst anhand der finalen unveränderlichen Gate-Receipt ergänzt. Frühere oder während
Quelländerungen laufende Prüfungen sind kein Release-PASS für die endgültige Fassung.

Zwischenstand der vollständigen Prüfung: Gate `99664c75c05e` bestand TypeScript,
330 Frontendtests und 1.345 Backendtests (988,27 Sekunden). Die Receipt ist dennoch
korrekt FAIL mit `Sources changed during unit verification`: Die nachträgliche
Tooltip-/Typisierungsbereinigung benötigt einen neuen unveränderten Lauf.

Der Folgelauf `13e051e8459e` startete mit Source-SHA
`3ac47bc6cc49eeb1f548a72ea98c729d0e132cfcf64fcf33517383e031fb4b5e`.
Während dieses Laufs wurden außerhalb dieses Updates `trace-analysis-workbench.tsx`
und die gemeinsame `globals.css` geändert; der Arbeitsstand hat nun eine andere
Source-SHA. Deshalb kann auch dieser Lauf keinen gemeinsamen Release-PASS belegen.
Die eigenen Styles wurden kontrolliert und sind weiterhin vorhanden. Die gemeinsame
Releaseprüfung benötigt einen anschließend stabilen Quellstand. Kein Deployment wurde
durch dieses Update ausgeführt.

Visuelle Prüfartefakte: `backend/test-output/universal-output-desktop.png`,
`universal-output-mobile.png` und `verify-universal-output.cjs` im selben Verzeichnis.
Die erneute Komponentenprüfung nach der Tooltipkorrektur erzeugte keine React-Warnung.

## Freigegebene Auflösung paralleler Änderungen

Nach ausdrücklicher Freigabe wird die Abnahme auf einer eingefrorenen Kopie
innerhalb des kanonischen Projekts ausgeführt. Die Kopie enthält Quellcode und
Tests; beide Manifeste wurden vor und nach dem Kopieren mit dem Arbeitsstand
verglichen. Die Release-Gate-Prüfungen bleiben vollständig aktiv. Spätere
Arbeitsverzeichnisänderungen gehören nicht automatisch zum geprüften Image.

Der erste eingefrorene Lauf fand eine veraltete Trace-Testannahme: Die bereits
implementierte Importgrenze beträgt 500 MiB, der Test erwartete noch 5 MiB.
Test und Trace-Dokumentation wurden an die tatsächliche Grenze angepasst; der
Test prüft zusätzlich den konkreten Grenzwert und weiterhin dessen Überschreitung.

Aktueller Kandidat: Source `a1051d80c6041fddb718846f926444f396b23d225ed6b3a3db235b215f8f2cfc`,
Verification `3d78d7b3e0d17deff9b7e23fb475f1c5e54e8040452baecfc35db8c6f74942e0`.
Snapshot: `backend/test-output/release-snapshots/20260914-141834`.
Receipt: `backend/test-output/release-gates/7001200f9dec/receipt.json`.
Der Lauf ist noch nicht abgeschlossen; dies ist noch kein PASS-Nachweis.

Der vollständige eingefrorene Lauf `7001200f9dec` bestand TypeScript, 333
Frontendtests, 1.350 Backendtests (ein Skip) und den Produktionsbuild. Drei von
vier Browserfällen bestanden. Die große 50/250/250-Abnahme scheiterte korrekt:
Alle 1.404 Signale und 838 Routen waren beobachtet, aber fünf Routen mit 1.000 ms
Periode hatten im fest vorgegebenen einsekündigen Wizard-Lauf nur ein Ereignis.
Ihre Jitter-Anforderung blieb NOT_EVALUATED. Die PASS-Anforderung wird beibehalten.

Korrektur: Nur die automatische Wizard-Normalprüfung fordert jetzt
AUTO_OBSERVATION an. Beim Einfrieren des Simulationssnapshots wird nach der
Scope-Auswahl eine Dauer von mindestens zwei Perioden der langsamsten Route
bestimmt. Das Ereignisbudget berücksichtigt Perioden und physische Segmente mit
Reserve für Kontrollereignisse. Explizite Laufzeiten/Ereignisgrenzen werden nicht
überschrieben. Unvertretbare automatische Umfänge werden abgelehnt (maximal
3.600 Sekunden bzw. 10 Millionen dimensionierte Ereignisse). Diese Dimensionierung
ist kein Konformitätsnachweis; die tatsächlichen Runtime-Prüfungen bleiben maßgeblich.
21 gezielte Scope-/Simulationsregressionen bestanden.


Der Dreiperioden-Kandidat `cc53304d4b87` bestand 1.357 Backendtests (ein Skip),
333 Frontendtests, TypeScript und den Build. Im großen Browserfall überschritt
die Simulation jedoch die unveränderte 240-Sekunden-Stufengrenze. Deshalb nutzt
die automatische Beobachtung zwei volle Perioden: genügend für zwei Ankünfte und
eine beobachtete Jitterdifferenz auch bei phasenversetztem Sendebeginn.
Eine direkte Wiederholung des gespeicherten großen Snapshots bestätigte damit
PASS, alle 1.404 Signale und alle 838 Routen, ohne unbewertete oder fehlerhafte
Route. Dies ist ein diagnostischer Wiederholungsnachweis, kein Release-Receipt.

Endgültiger Kandidat: `a8cb288922a9b5cfdc1ddd2283740a631b3278c8a0b6b68b77e7e3ff05db24ac`.
Snapshot: `backend/test-output/release-snapshots/20260914-155240`.
Gate: `backend/test-output/release-gates/1d5c99246bd4/receipt.json` (noch laufend).
