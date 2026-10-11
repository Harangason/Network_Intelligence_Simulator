# Intelligence: Dimensionierung und doppelte Navigation
Projekt 20261009072206008-4bb505f1; /studio/intelligence.
Browsermarkierung 1: CommunicationSizingPanel hat bisher keine eigenen Layoutregeln; native Summary, Text, analysis-scenario-row und Aktion stehen ohne durchgehenden Innenabstand aneinander.
Browsermarkierung 2: IssueTable und IssueDetailDialog rendern stets Zum Editor und Netz öffnen. objectLink führt bei Network und Graph schon zum identischen /studio?mode=network mit Projektparameter.
Soll: zusammenhängende aufklappbare Karte mit gepolstertem Kopf, kurzen Orientierungstexten, adaptivem Eingaberaster, klarer Aktionszeile und gegliederten Ergebnissen; bestehende Planungs-/Übernahmesemantik bleibt identisch. Navigation je eindeutigem Ziel einmal; unterschiedliche Objekt-/Routing-/Capacity-Editoren behalten ihren eigenen Link plus Netz-Zugang. Gemeinsame Link-Komponente für Tabelle und Detaildialog.
Datenfluss: aktives Projekt -> dimensionCommunications -> CommunicationSizingPlan -> bestehende React-Anzeige -> applyCommunicationSizing. Keine Daten-/Rechenänderung beauftragt.
Quelle: Nutzerscreenshots und aktuelle Quellpfade; keine neue Laufzeitprüfung.
Bestehende Test-/Registry- und Kampagnenbestände aus vorangegangenen UI-Aufträgen unverändert. Keine neue Registry, keine Tests erstellt oder ausgeführt; ausdrückliche Testpause. Native details/summary und vorhandene React/CSS-Muster wiederverwenden.
