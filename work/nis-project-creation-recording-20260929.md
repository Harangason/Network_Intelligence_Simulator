# Aufzeichnungsprotokoll – NIS-Projekterstellung

- Start der Aufzeichnung: 2026-09-29 11:09:50 Europe/Berlin (09:09:50 UTC)
- Erster beobachteter URL-Kontext: `http://127.0.0.1:13500/?project=20260928193908615-9d3edbe7` (Ambient-Browserkontext)
- Tatsächlich sichtbarer Browserzustand bei der ersten Aufnahme: `http://127.0.0.1:13500/studio/engineering?project=20260929090918029-7409db8c`
- Angezeigte Projekt-ID: `network-project-20260929090918029-7409db8c`
- Projektname: „Neues Projekt“
- Workflow: Schritt 1 „Engineering-Modell“, geführter Auftrag „Engineering-Auftrag erstellen“, Fragebogen Schritt 4 von 5 „Geräteumfang“.
- Beobachteter Stand: noch kein kanonisches Engineering-Modell; Workflow-Karten 1–9 LEER.
- Sichtbare Blocker/Hinweise: Controller: 0 erkannt, 1 vorgegeben; zwei Teilnehmer ohne eindeutige Controller-Zuordnung; das Ventil hat offene Angaben für Stellbefehl und Anschluss, der Temperatursensor einen offenen Anschluss. „Übernehmen“ und mehrere Zuordnungsaktionen sind deaktiviert.
- Im sichtbaren Entwurf: 1 Kommunikationssystem `embedded_systems · i2c`, 2 geplante Netzverbindungen; aktiver Cluster „Sensorik · 2 Teilnehmer“.
- Aufzeichnungsmethode: ausschließlich lesende Beobachtung des sichtbaren Browser-/Accessibility-Zustands; keine UI-Aktion durch den Assistenten.
- Fortsetzung: weitere sichtbare Zustandsänderungen nach neuen Beobachtungen mit Zeitstempel ergänzen.

## Zweiter Aufzeichnungsabschnitt – Geräteumfang bis Statusübersicht

- Beobachteter Projektkontext aus Browser-Kommentaren: `http://127.0.0.1:13500/studio/engineering?project=20260929091001224-3ec166dc`; Backend-Build `c79f85d23692`.
- Beobachtete Beschreibung: „ein sensor temperatur mess, eine ECU, ein Aktor Ventil schließen“; die UI fügt darunter einen JSON-artigen Aktor-Befehl in den Beschreibungstext ein.
- Im Schritt „Geräteumfang“ zeigte die UI zunächst Controller: 0 erkannt, 1 laut Text. Dadurch fehlten Controller-Auswahl und Zuordnung für den Sensorik-Cluster; zwei Teilnehmer blieben unzugeordnet. Der Nutzer meldet, dass „ECU“ im Feld „Controller im Auftrag ergänzen“ nicht übernommen wird und das Feld offenbar einen Pi erwartet.
- Der Nutzer hatte I2C im vorherigen Schritt gewählt; bei Temperatur- und Ventilteilnehmer standen die Anschlussauswahlen trotzdem auf „Bitte auswählen“. Die UI bot „I2C für alle offenen Anschlüsse übernehmen“, was den Verlust der vorherigen Auswahl zusätzlich sichtbar macht.
- Korrektur führte zurück zur Projektbeschreibung; der Aktor-Befehl erschien als eingebettetes JSON. Laut Nutzer wurde danach erneut ein Pi als ECU erwartet. Nach Eingabe eines Pi und „Korrektur übernehmen“ wurde Schritt 5 freigegeben. Das ist ein beobachteter manueller Workaround und darf nicht als fachlich korrekte Zuordnung interpretiert werden.
- Statusübersicht danach: Modell vollständig, Routing freigegeben, Netzwerk vollständig, Parameter freigegeben; Capacity & Timing Warnung (85 %), Validation / Preflight angehalten (99 %), Simulation/Analyse/Intelligence leer. Auftrag angehalten bei 65 % Gesamtfortschritt.
- Sichtbare Preflight-Gründe: für RaspberryPI/I2C I/O Segment 1 fehlt bestätigte Bitrate; zusätzlich fehlen technologieabhängige Overhead-/Scheduling-Parameter. Vorschlag meldet 4 I2C-Netze und 4 Anschlüsse ohne Kapazitätsnachweis. Modellfreigabe ist erfolgt, aber Kapazität nicht nachgewiesen.
- Nutzer meldet zusätzlich einen Zustand „Technologiekatalog wird geladen …“ ohne Fortschritt. Die finale sichtbare Statusübersicht zeigt jedoch einen konkreten Preflight-Halt; Katalog-Ladeproblem und fachlicher Preflight-Blocker sind getrennte Befunde und müssen getrennt reproduziert werden.
- Abschluss der Aufzeichnung: 2026-09-29, nach Erfassung der Statusübersicht. Keine UI-Aktionen durch den Assistenten.

## Anmerkungen des Nutzers – zusammengefasste Defekte

1. Der Controller aus „eine ECU“ wird nicht als konkretes Gerät gezählt; „Soll laut Text“ zeigt 1, „Konkrete Geräte“ aber 0.
2. Die Zähldifferenz erzeugt Folgefehler: Controller bleibt 0, Clusterteilnehmer bleiben ohne Controller, Wizard-Schritt bleibt blockiert.
3. „ECU“ wird im Controller-Ergänzungsfeld abgelehnt; die Oberfläche scheint einen Raspberry Pi zu erwarten, obwohl die Beschreibung nur eine ECU nennt.
4. Die Buswahl I2C wird nicht auf die Anschlussauswahl des Temperatursensors übertragen.
5. Dieselbe I2C-Auswahl wird auch nicht auf den Ventilanschluss übertragen.
6. Wegen falscher ECU-/Controller-Erkennung fehlt die Controlleroption in der Mehrfachzuordnung.
7. „Anforderung korrigieren“ bringt den Nutzer zur Beschreibung zurück, verlangt offenbar eine neue Pi-Eingabe und stellt den generierten Aktor-Befehl als JSON im Freitext dar.
8. Auch die explizite Eingabe „ECU“ im Ergänzungsfeld wird laut Nutzer nicht übernommen.
9. Schritt 5 wurde erst nach Pi-Eingabe und Übernahme der Korrektur freigegeben – ein Hinweis auf eine unerwünschte Kopplung an einen konkreten Pi statt an die angeforderte ECU.
10. Der Parameter-Buskatalog zeigt nicht alle benötigten Bustypen (insbesondere I2C; der Nutzer nennt auch weitere fehlende Typen). Damit lassen sich zuvor erkannte Technologien nicht an dieser Stelle korrigieren.
11. Nutzer meldet „Technologiekatalog wird geladen …“ und Stillstand; finaler sichtbarer Zustand ist ein Preflight-Halt wegen fehlender I2C-Bitrate und Scheduling-/Overheadparameter. Diese beiden Fehlerklassen getrennt testen.
