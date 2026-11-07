# Verbindlicher Wizard-Ablauf und Regressionsschutz

Grundlage: Stabilitätsbefund vom 14.09.2026 und anschließende Nutzerfreigabe.
Gilt für Auftragsdialog, Chattransport, Python-Agent, MCP-Fachdienste,
Vorschläge, Projektzustand und Releaseprüfungen. Die Fachverträge für
Kommunikation, räumliche Zuordnung und Netzbenennung gelten zusätzlich.

## Auftrag und Steuerung

1. Ein bestätigter Auftrag besitzt Projekt-ID, Lauf-ID, vollständige Eingabe,
   Zielschritt und unveränderliche Revision. `START` speichert diese Angaben
   gemeinsam mit Gespräch und Ausführung. Scheitert die Speicherung, darf
   kein davon unabhängiger Agentenlauf starten.
2. `CONTINUE` verwendet die gespeicherte Eingabe und das gespeicherte Ziel.
   Die Formulierung der sichtbaren Chatnachricht steuert weder Ziel noch
   Freigaben. `AMEND` erzeugt eine neue Revision und erhält Ursprung und
   Ergänzungen. Eine Ergänzung gilt nicht als Freigabe neuer Vorschläge.
3. Eine Operation besitzt eine eindeutige ID. Wiederholung derselben Operation
   hat dieselbe Wirkung; dieselbe ID mit anderen Eingaben wird abgelehnt.
   Dazu zählen auch Frage-ID und ausgewählte Optionen. Der Server bestätigt
   die Annahme ausdrücklich. Ein HTTP-Sendeversuch allein ist keine Annahme.
4. Ausführungszustand und Auftragsrevision werden ausschließlich über dafür
   vorgesehene Backendkommandos geändert. Allgemeine UI-Kontextänderungen
   dürfen einen modernen Wizardlauf nicht überschreiben. Veraltete
   Revisionen dürfen weder Änderungen freigeben noch einen neueren Auftrag
   beenden oder abbrechen.
5. Nur der aktuelle Ausführungsbesitzer darf Fortschritt melden. Verspätete
   Heartbeats/Antworten dürfen abgeschlossene, blockierte oder abgebrochene
   Zustände nicht wieder auf laufend setzen. Wiederanlauf aktualisiert
   Ausführung und Gesprächsreservierung konsistent. Die unterstützte lokale
   Bereitstellung hat einen Backendprozess; mehrere unabhängige Backend-
   Instanzen benötigen eine gesondert geprüfte Besitzkoordination.

## Entscheidungen und Fachobjekte

6. Strukturierte Rückfragen werden mit gespeicherter Frage-ID, Status und
   Options-IDs dargestellt und beantwortet. Anzeigeprosa ist keine Auswahl-ID.
   Reload lädt offene Fragen und Entscheidungen aus dem Projektzustand.
7. Vorschläge beziehen sich auf alle relevanten Quellrevisionen und die
   Generatorversion. Unveränderte Wiederholung erzeugt keinen neuen Entwurf.
   Ein Nachfolger kennzeichnet die vorherige Fassung als abgelöst; eine alte
   Freigabe darf nicht auf die neue Fassung übertragen werden. Auch ein
   ungültiger Vorschlag bleibt mit seinen konkreten Befunden nachvollziehbar.
8. Logische Funktion/Kommunikationsschnittstelle und physischer Anschluss
   werden gemeinsam anhand des tatsächlichen Transportwegs aufgelöst.
   Der letzte Gatewayabschnitt bestimmt den Empfangstransport. Unbekannte
   oder mehrdeutige Bindungen bleiben Befunde. Es werden keine Empfänger,
   Gatewayfähigkeiten oder Kodierungen erfunden, um Validierung zu bestehen.
9. Signalunterauswahl verkleinert keinen bestehenden physischen Frame.
   Payloadgrenzen gelten pro tatsächlich durchlaufenem Transportabschnitt.
   Unabhängige Busauslastungen dürfen nicht zu einer fiktiven Auslastung
   eines einzelnen Busses addiert und dagegen freigegeben werden.
10. Jeder blockierte Schritt zeigt Ursache, betroffene Objekte und mögliche
    nächste Handlung. Freigaben laufen durch das vorhandene Review-/Apply-
    Verfahren. Ansichten lesen und schreiben stets das zum Auftrag gehörende
    Projekt; ein Wechsel des aktiven Projekts ist keine Umhängung des Auftrags.

### Branche und Technik erhalten

Die explizite Branche des aktuellen Auftrags bleibt in Parser, Geräteauswahl,
Generator und Vorschlag verbindlich. Technologievorkommen wie CAN oder Ethernet
sind kein Beweis für Automotive. Ohne passende bestätigte Technologievorgabe
oder freigegebenes Branchen-Default dürfen fehlende Anschlüsse keine Ersetzung
durch CAN, LIN oder Automotive-Ethernet auslösen. Nicht unterstützte Anschlüsse
bleiben klärungsbedürftig. Bekannte Technologien werden über ihre
Registeridentität aufgelöst. Bestätigte Geräteanzahlen und konkrete Gerätearten
(etwa Ventile) dürfen nicht mit fachfremden Vorlagengeräten aufgefüllt werden.

## Abnahme und Auslieferung

11. „Bis Schritt 9 geprüft“ erfordert alle neun erwarteten Schritte und deren
    tatsächlich gespeicherte Artefakte zu passenden Quellrevisionen. Der
    gesamte bestätigte Testumfang bleibt erhalten. Eine erforderliche
    Freigabe darf im E2E über reguläre UI-Aktionen erfolgen. Simulierte
    Schreibantworten, direkt gesetzte Erfolgsstatus oder nachträglich
    reparierte erzeugte Testdaten sind kein vollständiger E2E-Nachweis.
12. Datenbanktests laufen ausschließlich in isolierten Testdatenbanken und
    expliziten Projektkontexten. Der Launcher `scripts/run-isolated-tests.py`
    stellt eine Wegwerf-PostgreSQL-Instanz bereit; pytest verweigert
    Produktdatenbanken vor Testmodulimporten.
13. `scripts/run-release-gate.py` verbindet Typ-, Frontend-, Backend-, Browser-
    und HTTP-Prüfungen mit einem unveränderlichen Kandidatenimage. Die
    Bereitstellung über `scripts/deploy-verified-release.py` akzeptiert nur
    einen vollständigen erfolgreichen Nachweis für genau dieses Image.
    Vorbereitete Entwicklungsstacks sind ausdrücklich kein Release-PASS.
14. Pflichtfälle sind kleiner vollständiger Auftrag, gespeicherter aktueller
    Großauftrag, Interface-/Framefehler, Rückfragen, veraltete Revisionen,
    doppelte Operationen und Wiederaufnahme. Ein historischer Erfolg belegt
    keine spätere geänderte Quelle. Warnungen sind fachlich auszuwerten;
    fehlende Artefakte und technische Ausführungsfehler sind kein Erfolg.

Konkrete Testausführungen und Grenzen werden im jeweiligen Abnahmebericht
festgehalten. Dieser Vertrag allein behauptet keine bestandene Prüfung.
