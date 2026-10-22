# Fahrzeug komplett – echte NIS-Prüfung am 16.10.2026

**Gesamtergebnis: BLOCKIERT, keine vollständige End-to-End-Abnahme und keine Simulation.** Der reguläre Wizard verhindert die Modellübernahme, weil konkrete Sensor-/Aktor-Teilnehmer, Stückzahlen und Anschlussentscheidungen fehlen. Zusätzlich ist der native Dokumentvorschlag fachlich nicht vollständig belastbar. Diese Prüfung hat Produktlücken gefunden; sie ist kein neuer Release-PASS.

Projekt: `20261016090147666-38290e41` (kanonisch `network-project-20261016090147666-38290e41`), Name „TEST 2026-10-16 Fahrzeug komplett – NIS selbst erzeugt“. Über die normale Projektübersicht neu angelegt. Der einmalige Zeitplan wurde vor Prüfungsbeginn pausiert.

Produktivimage unverändert: `sha256:96998221884773057e89efa677a8d234067cef829b9d9e92cd11084c4062e44a`, Quelle `33897ec545e995fb303e32c0a8bb42596a8c56128a4e4db3b5a6615c048b1f2f`. Identität, Health sowie Datenbank-/Speicher-Readiness vor und nach der Prüfung bestätigt. Kein Code, kein Build, kein Deployment und kein Neustart.

## Tatsächlich ausgeführter Weg

| Schritt | Ergebnis und Beleg |
|---|---|
| Original einlesen | Originaldatei über FileChooser geladen, vollständig19.088 Zeichen/20.406 Bytes; SHA256 `86865975c689643d9b07ea73e21d68fa6f4a3a8770402ffb537dba2d7ecdf4d7`; anschließend bytegleich zur unveränderten Quelldatei. |
| Nativer lokaler Qwen | Normaler UI-Befehl „Lokalen Qwen-Vorschlag erstellen“, `qwen3.8:27b`, sieben Abschnitte, Produktresultat REVIEW_REQUIRED. Serverseitiger Tool-Audit SUCCESS am16.10.09:45:25UTC, Trace `0e16af6e-b12c-4669-b08f-34da598796dd`. Mindestens sieben echte Abschnittsaufrufe durch diesen Produktweg; eine exakte Zahl aller HTTP-Inferenzversuche stellt die UI nicht bereit. Keine Korrektur-Progressemeldung beobachtet; keine Antworten ersetzt. |
| Vollständigkeit | UI-Datei19.088 Zeichen; Qwen-Quelle19.243 Zeichen, da der unveränderte Frontendweg einen155-Zeichen-Anlagenrahmen voranstellt. Rekonstruktion passt exakt zur angezeigten Länge und enthält die vollständige Originaldatei. Sie ist als Rekonstruktion gekennzeichnet, keine behauptete Netzwerkaufzeichnung. |
| Fachliche Dokumentprüfung | Fünf benannte Domain-Controller, zehn als Kategorien eingeordnete Gruppen, elf Funktionen,25 Anforderungsgruppen. Alle168 eindeutigen nummerierten REQ-IDs in Zitaten erhalten; keine zusätzlichen REQ-IDs. Mehrere falsche Kategorien und Technikzuordnungen, siehe Befunde. |
| Normale Wizardprüfung | Technologien-, Architektur-, Geräteumfang- und Statusseiten angesehen. Explizite Fahrzeugbranche anhand der Quelldatei bestätigt. Keine Mengen, Teilnehmer, Anschlüsse, Busse, Architektur oder Parameter manuell ergänzt. |
| Modellübernahme | Übernehmen und Auftrag starten gesperrt. Kein fehlerhafter Vorschlag freigegeben. |
| Routing, Netzwerk/Physik, Parameterfreigabe, Capacity/Timing | Nicht erreicht, da kein freigabefähiger Geräteumfang/Modellauftrag vorliegt. Vorschau/Defaults sind kein gespeicherter Modell- oder Transportnachweis. |
| Validation/Preflight und Simulation | Nicht ausgeführt, keine Umgehung. Keine Simulation, keine beobachtete Kommunikation und kein Scope-/Conformance-PASS. |

## Fachliche Befunde

1. **Offene Auslegung aus der Quelle:** Sensorik (Radar, Kamera, Lidar, Ultraschall, IMU, Raddrehzahl) und Aktorik (Brems-, Lenk-, Antriebsaktuator) sind Typengruppen ohne konkrete Stückzahlen. Diese dürfen weder als null vorhandene Geräte noch als jeweils ein beliebiges Gerät freigegeben werden. Die Sperre ist richtig. Vier Controller-Anschlüsse bleiben im Wizard offen. Die Datei nennt mehrere Netze und Alternativen, aber keine vollständig bestätigte konkrete Anschlussmatrix.
2. **Falsche Gerätekategorien:** „Sensor- und Aktorfehler erkennen und behandeln“ und der Normalbetriebssatz „Das System verarbeitet kontinuierlich Sensordaten...“ werden als Gerätegruppen abgefragt. Auch „Domain-Controller-Design“ und Sensorlinks werden als Hardwarekategorien behandelt. Das sind eigenständige Parserbefunde, keine fehlenden Nutzer-Stückzahlen.
3. **Falsche Technik-/Partnersemantik:** CDC/PDC werden korrekt als Controllerkürzel und zusätzlich als ungeklärte Technik geführt. „Direkte“, „Verbindung“, „Bremsanforderungen“ und „Ethernet möglich“ sind weitere falsche technische Kandidaten. In der Quelle benennen CDC/PDC fachliche Empfänger der Lenk-/Brems-/Antriebsanforderungen; diese Bedeutung darf nicht durch eine Bus-Rückfrage verloren gehen.
4. **Normalisierung/Quellenabdeckung:** Der Qwen-Vorschlag führt CAN-FD unter zwei Schreibweisen (`can‑fd`, `can_fd`); die Wizardfamilie selbst ist nur einmal vorhanden.25 Anforderungsgruppen enthalten alle168 nummerierten IDs. Beim unnummerierten Top-Level-Block bleiben17 Aussagen ohne wortgetreuen eigenen Quellenbeleg im sichtbaren Vorschlagsbereich; der Eintrag „Das System muss“ ist nur eine Überschrift. Eine semantische Gleichwertigkeit anderer Zitate wurde nicht bewiesen. Das ist keine Behauptung, dass exakt17 unterschiedliche Semantiken sicher verloren sind.
5. **Laufzeit:** Die einmalige normale UI-Auswertung dauerte ungefähr44 Minuten. Keine spekulative Ursache und kein präziser Modellbenchmark werden daraus abgeleitet.

## Kamera/Fahrerassistenz/Aktor-Kette

Die Quelle fordert explizit die Objektliste mit Position, Geschwindigkeit und Klassifikation (REQ-ADC-02), Sensorfusion/Perception/Planning/Vehicle Control, CDC für Lenk-/Bremsanforderungen und PDC für Antriebsanforderungen. Diese Aussagen sind als Soll geprüft. **Es existiert in diesem Test noch keine erzeugte und simulierte Ist-Kette** Kamera/Sensorik→Verarbeitung/Objektdaten→Fahrerassistenz→CDC/PDC→Aktoren. Ein Gateway- oder Statuspfad gilt nicht als Ersatznachweis.

Die abschließenden öffentlichen Projekt-APIs bestätigen jeweils0 Hardwareknoten, physische Anschlüsse, Funktionen, Kommunikationsschnittstellen, Nachrichten, Signale und Beziehungen. Es wurde kein Modell stellvertretend korrigiert, keine Route ergänzt und keine Simulation erzwungen. Der erfolgreiche Dokument-Toolaufruf allein ist kein fachlich freigabefähiges Gesamtmodell.

## Nachweise und Fortsetzung

`baseline.json`, `source-original.txt`, `source-completeness.json`, `source-review-criteria.json`, `qwen-progress.jsonl`, `qwen-result-dom.txt`, `qwen-result-visible-data.json`, `proposal-review.json`, `findings.json`, `scope-blocked-dom.txt`, `technologies-dom.txt`, `architecture-preview-dom.txt`, `start-blocked-dom.txt`, `final-blocked-dom.txt`, `final-blocked.png`, `project-tool-audit.json`, `final-project-state.json`, `final-production-state.json`.

Der Dokumentvorschlag bleibt im Browser-Prüftab zur Einsicht offen; seine Quellenzitate sind zusätzlich dauerhaft gesichert. Kein Cache-Replay wird als frische Inferenz bezeichnet. Der Auftrag enthielt keine Codekorrektur; die Produktbefunde sind zur späteren allgemeinen Behebung dokumentiert. Für eine tatsächlich vollständige Simulation benötigt NIS außerdem quellenbelegte Geräteinstanzen/Stückzahlen und konkrete Anschlussentscheidungen. Es wurden keine technischen Freigaben oder Sicherheitszertifizierungen aus dem Lastenheft abgeleitet.

[Testprojekt lokal](http://127.0.0.1:13500/studio/engineering?project=20261016090147666-38290e41) · [LAN/VPN](http://192.168.178.10:13500/studio/engineering?project=20261016090147666-38290e41)
