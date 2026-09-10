# Routing-Wizard: Ursachen, Korrekturen und Nachweise

Projekt: `network-project-20260910042736034-d11591d0` · Prüfung vom 10.09.2026 · aktiver Build `f0f7c6471576`.

## Ergebnis

Die angezeigte Zuordnung zur Abgasnachbehandlung war ein Fehler der Namensauflösung im Wizard. Zusätzlich bestanden 36 echte Widersprüche zwischen logischen Empfängerschnittstellen und physischen LIN-Anschlüssen. Beide Ursachen wurden behoben; die 36 Datensätze wurden transaktional repariert und validiert. Die vollständige erneute Prüfung ergibt 386 valide Routen. 325 bleiben freigegeben, 61 sind offen; darunter die 36 reparierten Routen mit Status `READY_FOR_REVIEW`.

## 1. Warum im Wizard überall Abgasnachbehandlung stand

Die frühere Funktion `networkId()` leitete bei fehlender Konfiguration eine Netz-ID aus dem Schnittstellentyp ab. Dadurch erhielten verschiedene LIN-Netze denselben Ersatzschlüssel `network-lin`. `buildNetworkAliases()` gruppierte sie und verwendete den alphabetisch ersten Gerätenamen: Abgasnachbehandlung. Eine zweite Anzeige erfand unabhängig davon Namen wie `OilTemperature_LIN_1`. Die beiden Anzeigen konnten deshalb einander widersprechen.

Die kanonischen Gerätezuordnungen und physischen Anschlüsse waren bei den beiden gemeldeten Sensoren bereits richtig:

| Route | Fachlicher Empfänger | Tatsächlicher physischer Bus |
|---|---|---|
| RT-F6D2B8A6 – FrontLeftSuspensionTravel | Daempferregelung | Daempferregelung LIN 01 |
| RT-F64874FF – OilTemperature | Motorsteuerung | Motorsteuerung LIN 05 |

Der Wizard liest nun Nachrichtenbindungen, physische Anschlüsse und Routing-Endpunkte. Busnamen stammen vom realen Anschluss; Bus-IDs werden unverändert verwendet. Ein Bustyp ist kein Ersatz für eine Netz-ID. Fehlende oder mehrdeutige Anschlüsse werden ausdrücklich angezeigt. Bei mehreren Bussen bleibt die gewählte Port-ID erhalten oder der Anwender wählt den Anschluss. Die Optionslisten sind innerhalb der technischen Kompatibilitätsgruppen alphabetisch sortiert.

## 2. Herkunft der 36 echten Datenfehler

Die betroffenen Empfänger verwiesen auf eine logische CAN-FD-Schnittstelle, während Route und physischer Anschluss bereits LIN verwendeten. Für RT-F6D2B8A6 belegt das Routing-Audit den Vorgang `network-editor-bus-change`, 10.09.2026, 07:57:01 UTC, mit dem Grund „Physischer Bustyp geändert.“ Agent und Modell waren dort nicht gesetzt. Der Bustypwechsel aktualisierte die physischen Bindungen, ließ aber alte logische Empfängerreferenzen zurück.

Die Validierung verwendete bei vorhandenen Hardware-Anschlüssen deren Typ anstelle des logischen Schnittstellentyps. So blieb dieser Widerspruch unentdeckt.

Jetzt prüft die Validierung auch den logischen Typ jedes Endpunkts gegen dessen eigenes Protokoll. Ein Bustypwechsel berücksichtigt die Empfängerreferenzen. Automatisches Umhängen erfolgt nur bei genau einer kompatiblen Schnittstelle am selben Gerät und passendem bestehenden Anschluss. Mehrdeutige Fälle werden nicht alphabetisch entschieden.

Die Datenreparatur änderte ausschließlich `destinations[].interface_id`, plus Revision, Audit und Prüfstatus. Die 36 Routen gingen von Revision 3 auf 4. Geräte, Nachrichten, logische Schnittstellenobjekte, physische Anschlüsse, Topologie und Parameter blieben identisch. Alle anderen 350 Routen sind vollständig identisch zum gesicherten Ausgangsstand. Bestehende Freigaben wurden nicht automatisch neu erteilt.

## 3. Fachliche Wortzerlegung und bessere Entscheidungskriterien

Die bisherigen „93 % Match“ waren addierte Regeln für Gerät, Protokoll und bereits vorhandene Auswahl. Das war weder gemessene Genauigkeit noch eine Konfidenz des Sprachmodells. Die Anzeige nennt jetzt die tatsächliche technische Prüfung und ihre Gründe; eine bestehende Auswahl erhöht deren Bewertung nicht.

Für Zuordnung, Generierung und Wissenssuche wurde eine konservative fachliche Wortzerlegung ergänzt:

- `Fahrersitz` → `fahrer`, `sitz`; `Fahrwerk` bleibt ein eigener Begriff.
- `Dämpferregelung` → `daempfer`, `regelung`.
- `FrontLeftSuspensionTravel` → `front`, `left`, `suspension`, `travel`.
- `EGRValvePosition` → `egr`, `valve`, `position`.
- `Radar` trifft nicht auf `rad`; `DriverSeat` trifft nicht auf `drive`.

CamelCase, Akronyme und Umlaute werden berücksichtigt. Zusammengesetzte Wörter werden nur bei vollständiger Zerlegbarkeit anhand des Fachvokabulars aufgeteilt. Unbekannte Wörter bleiben erhalten. Regeln verwenden Wortgrenzen statt beliebiger Teilzeichenfolgen. Fachliche Familien priorisieren Federweg bei der Dämpferregelung und Motoröltemperatur bei der Motorsteuerung. Gleich bewertete Empfänger bleiben offen. Bestätigte manuelle Zuordnungen haben Vorrang vor solchen Ableitungen.

Keyword-Suche und lokale semantische Einbettung verwenden dieselbe Zerlegung. Die geänderte lokale Einbettung trägt die Version `local-hashed-engineering-embedding-v3`. Die kanonischen Wissensadapter bauen ihren lokalen Index aus den aktuellen Projektdaten auf. Das ist eine Verbesserung der fachlichen Vorverarbeitung und Entscheidungskriterien; das Sprachmodell und dessen eigener Tokenizer wurden nicht neu trainiert oder ausgetauscht. Die Regeln gewährleisten keine vollständige fachliche Interpretation beliebiger neuer Namen.

## 4. Darstellung und Bedienung

Die Zielkarten ordnen Überschrift und Felder oben an, statt den Inhalt über die gesamte Höhe zu verteilen. Schnittstelle und physischer Bus sind getrennt auswählbar. Eine Schnittstelle mit mehreren Bussen erhält eine kurze Zusammenfassung; der konkrete Bus ist direkt darunter sichtbar. Beim Wechsel werden logische Schnittstelle, physischer Port und Netz-ID zusammen behandelt. Formulareingaben und bestehende Mausnavigation bleiben erhalten.

## Nachweise

- 232 Frontend-Tests bestanden, einschließlich Automotive-, Rail-, Topologie-, Mehrdeutigkeits- und Wortgrenzentests.
- 91 Backend-Tests bestanden, einschließlich Bustypmigration, Routing-Validierung, Systemzuordnung und Wissenssuche.
- TypeScript-Prüfung und Produktionsbuild erfolgreich.
- Nachkontrolle des Reparaturbefehls: keine verbleibenden eindeutigen Reparaturen. Browserfehlerprotokoll im finalen Build leer.
- Alle 386 aktuellen Projektrouten mit der neuen Validierung erneut geprüft: 386 valide, keine Fehler. Prüfung ohne Änderung vorhandener Freigaben.
- Browser: RT-F6D2B8A6 zeigt Quelle und Ziel auf Daempferregelung LIN 01; RT-F64874FF zeigt Motorsteuerung LIN 05. Kein falscher Abgasname, keine 93-%-Anzeige, kein CAN-FD/LIN-Widerspruch. Die Schlussprüfung der Öltemperatur-Route meldet vollständige Wizard-Pflichtangaben.

Die gesicherten Daten und Maschinenberichte liegen unter `backend/runtime/`: `routing-context-audit-before.json`, `routing-context-repair-plan.json`, `routing-context-repair-applied.json`, `routing-context-audit-after.json`, `routing-context-consistency-summary.json` und `routing-context-live-validation.json`. Der Reparaturbefehl `python -m backend.engineering.routing.repair_receive_interfaces --project …` erzeugt standardmäßig nur eine Vorschau. Übernahme verlangt den unveränderten Vorschau-Token und erfolgt innerhalb einer Projekttransaktion.
