# Reparaturbericht: Kapazitäts- und Zeitnachweise aller Bustypen

Stand: 25.09.2026. Projekt: `I:\PycharmProjects\My_first_Network_Simulator`.

## Auftrag und Entscheidung

Der vorausgehende [Vollständigkeits-Audit](BUS_TECHNOLOGY_COMPLETENESS_AUDIT_2026-09-25.md) erfasste 125 katalogisierte Kommunikationstechnologien. Für viele davon gab es nur einen generischen Rahmenrechner oder eine fremde Ersatzrate. Der Nutzer hat die Regel bestätigt: Fehlende technologiespezifische Kapazitäts- oder Zeitnachweise werden als `UNVERIFIED` ausgewiesen und sperren die Freigabe, bis Profil- und Gerätedaten bestätigt sind. Die bestehenden Modelle für CAN, CAN FD, LIN und Ethernet bleiben nutzbar, sofern die benötigte Rate belegt ist. Diese Reparatur implementiert die sichere Sperre; sie behauptet keine neu erfundenen Protokollmodelle für die übrigen Technologien.

## Ursache

Routing, Capacity und Konfigurationsaufbau verwendeten voneinander getrennte Tabellen und Ersatzwerte. Ein nicht abgedeckter Transport konnte im Routing als `CUSTOM` mit 1 Mbit/s, im Config Builder mit 100 Mbit/s und im Capacity-Rechner mit generischem Overhead weitergerechnet werden. `CAN_XL` wurde sogar als CAN FD ausgegeben. Generische Schätzungen waren nur `INFO`; der Preflight konnte sie dadurch als ausreichenden Nachweis behandeln. Auch automatisch eingesetzte Registryraten waren nicht von explizit bestätigten Raten getrennt. Die Einzelbefunde und die Technologiematrix stehen im Audit.

## Änderungen

| Schicht | Umsetzung | Wirkung |
| --- | --- | --- |
| Routingvalidierung | Kein `CUSTOM`-Kapazitätsfallback mehr; fehlende Modelle erzeugen `CAPACITY_MODEL_UNVERIFIED`. Payloadgrenzen kommen, soweit vorhanden, aus dem registrierten Profil. Eine Last wird nur mit expliziter positiver Rate und unterstütztem Modell gebildet. | I2C, SPI, Profinet, EtherCAT, RS485 und weitere Typen bekommen keine frei erfundene 1-Mbit/s-Routenlast. |
| Konfigurationsaufbau und Planung | 100-Mbit/s-Ersatzwert entfernt; Kapazitätsoptimierung überspringt Typen ohne eines der vier unterstützten Modelle. | Unbekannte Transporte werden nicht als belastbare Kapazitätskandidaten verglichen. |
| Rahmenmodell | `CAN_XL` wird nicht mehr durch den CAN-FD-Zweig umbenannt. Es bleibt als generische, ungeprüfte Schätzung unter eigener Protokollidentität sichtbar. | Keine falsche CAN-FD-Freigabe. |
| Capacity und Zeitplan | Routen, Segmente, Netze, Nachrichten und Übersicht tragen `capacity_verified`. Registrydefaults belegen eine Rate nicht; explizite Vorgaben oder konkrete positive Netz-/Portwerte tun es. Für CAN FD müssen Arbitrierungsrate (`arbitration_bitrate` oder das vorhandene Feld `bitrate`) und `data_bitrate` getrennt belegt sein. Fehlendes Modell oder fehlende Rate ergibt `UNVERIFIED`, `CAPACITY_RATE_UNVERIFIED`, `GENERIC_ESTIMATE` beziehungsweise `COMMUNICATION_UNVERIFIED` mit `REVIEW`. Aus einer ungeprüften Rate berechnete Jitterverletzungen werden nicht als harte Grenzverletzung behauptet. | Der Preflight sperrt die Simulation bei offenen Nachweisen. Numerische Vorschauwerte bleiben intern erhalten, gelten aber nicht als Freigabe. |
| Auswertung und Oberfläche | Kapazitäts- und Stressstatus sind `UNVERIFIED`; die Capacity-Ansicht zeigt „Nicht nachgewiesen“ statt Last, Reserve oder Reaktionszeit ohne Verifikation. Die Ergebnisansicht zeigt prognostizierte Werte nur bei bestätigtem Nachweis. | Die Benutzeroberfläche stellt generische Zahlen nicht als bewiesen dar. |
| Snapshot-Version | Capacity-Berechnung von 3.3 auf 3.4 erhöht. | Alte Snapshots gelten als veraltet und müssen neu berechnet werden. |
| Technologiekatalog und Registry | Alle 125 Profile enthalten jetzt `capacity_evidence` mit explizitem Modellstatus sowie Frame- und Schedule-Modellnamen. Die Registry bietet Timing-/Lastadapter nur für die vier tatsächlich modellierten Basisprotokolle an. Importierte Technologiepakete können durch deklarative Metadaten keinen ausführbaren Kapazitätsnachweis behaupten. | Katalogisierung und ausführbare Basisadapter werden nicht mehr als Nachweis für 121 unmodellierte Technologien missverstanden. |
| Generischer Rechner und Simulator | Die allgemeine 1-Mbit/s-Ersatzrate wurde entfernt. Ohne Profil- oder Netzrate wird nur die ungeprüfte Rahmengröße, aber keine Übertragungszeit ausgegeben. Höhere Protokollschichten und FlexRay geben keine scheinbar bestätigten Ethernet-/FlexRay-Rahmenmodelle mehr zurück. Der eigenständige Trace-Lauf verlangt bei fehlender Profilrate eine ausdrücklich angegebene Rate; die interaktive CLI erfragt sie. Der `CUSTOM`-Eintrag mit 1 Mbit/s wurde aus der Routing-Kapazitätstabelle entfernt. | Keine stillschweigende Fremdrate in diesen Rechenpfaden. Die verbleibenden Profileinträge sind weiterhin keine formale Kapazitätsfreigabe. |
| Wizard-Preflight | Der blockierte Lauf speichert die konkreten Befunde, bleibt mit derselben Lauf-ID fortsetzbar und zeigt in der Oberfläche Befund, Objekt und Empfehlung. | Fehlende Nachweise sind für die Nutzer sichtbar und nach Korrektur erneut prüfbar; eine Simulation startet erst nach positivem Preflight. |
| Registrierte Protokollidentität | Physische Routensegmente behalten ihre registrierte Technik, auch wenn der alte Routing-Kapazitätsschlüssel fehlt. | Beispielsweise wird RS485 nicht mehr als `CUSTOM` umbenannt. Ein fehlender Modellzweig bleibt ein Befund. |
| Öffentlicher Technologiekatalog | Die empfohlenen Technologien bleiben zuerst; danach folgen alle weiteren Profile ihrer Domäne mit ihrem Nachweisstatus. | Auch die 17 bisher im öffentlichen Katalog nicht erreichbaren Einträge sind nun sichtbar. Die isolierte Katalogprüfung findet 125 eindeutige IDs und 4 verfügbare Nachweismodelle. |

Direkte PWM-/GPIO-Signale bleiben bei der Buskapazität `n/a`; ihre Reaktionszeiten benötigen die bereits ausgewiesenen Signal- und Geräteparameter. Hardwareprofil-Vorschläge für I2C/SPI/PWM/GPIO sind weiterhin prüfbare Vorschläge, kein automatischer Zeitnachweis.

## Nachweise

Alle SQL-bezogenen Tests liefen mit `scripts/run-isolated-tests.py` gegen eine jeweils disposable PostgreSQL-Instanz. Die Produktdatenbank wurde nicht als Testziel verwendet.

| Prüfung | Ergebnis |
| --- | --- |
| Gezielte Routing-/Capacity-Regression nach der letzten Korrektur | 111 bestanden. |
| Wizard mit explizit bestätigten Raten und neue Technologie-Regressionen | 13 bestanden. |
| Großer 50/250/250-Routingfall mit offenem Ratenstatus | 1 bestanden; Laufzeit 7:06 min. |
| TypeScript-Prüfung | Bestanden. |
| Frontend-Unitprüfungen im Release Gate | 455 bestanden. |
| Vollständige isolierte Backendsuite im zweiten Release Gate | 2081 bestanden, 2 übersprungen, 1 bestehende Pydantic-Warnung. |
| Vollständige isolierte Backendsuite nach der abschließenden CAN-FD-Phasenregel | 2082 bestanden, 2 übersprungen, 1 bestehende Pydantic-Warnung; Laufzeit 13:08 min. |
| Produktionsbuild im zweiten Release Gate | Bestanden; Image-ID `sha256:081dc56d7caa1bdc83f3c3edefb0901e2ba8ca68a92c8622e4ce41c4ba98ef11`. |
| Browser-End-to-End im zweiten Release Gate | 64 bestanden, 5 fehlgeschlagen; Gate `FAIL`. |
| `git diff --check` der betroffenen Dateien | Keine Whitespace-Fehler; lediglich Hinweise auf CRLF/LF-Konvertierung. |
| Gezielte Regression nach der Katalog-/Registry-Korrektur | 140 bestanden; zusätzliche Einzelprüfung 15 bestanden. Das sind lokale Tests, kein neues Release Gate. |
| Nachbesserung von Rechner, Trace und Wizard-Fortsetzung | Isolierte Teilgruppen mit 35, 100, 56 und 29 bestandenen Tests; TypeScript und 12 gezielte Frontend-Tests bestanden. |
| Vollständige isolierte Backendsuite nach der ersten zusammenhängenden Korrektur | **2088 bestanden, 2 übersprungen**, 1 bestehende Pydantic-Warnung; 14:22 min. Danach wurden die vier Adapter an die tatsächlichen Rahmenrechner gebunden und die Routingidentität korrigiert; diese Nacharbeiten haben gezielte Tests (41, 47 und 65 bestanden), aber noch keinen neuen Vollsuite- oder Release-Gate-Beleg. |
| Gezielte 125er-Inventur des aktuellen Checkouts | 125 geprüft: 4 Profile mit Modell, 121 ohne; 121 generische, ungeprüfte Rahmenvorschauen; kein unmodellierter Typ mit ausführbarem Registry-Timingadapter; kein RS485-Fremdratenwert. Beleg: [`checkout.json`](../tool-checker/runs/20260925_src_bus_capacity_repair_verify/20260925_src_bus_capacity_repair_verify_checkout.json). |
| Abschließende gezielte Regressionen nach Adapter- und Routingänderung | 41, 47 und 65 isolierte Backendtests bestanden; 455 Frontendtests und TypeScript-Prüfung bestanden. Diese Prüfungen ersetzen das vollständige Release Gate nicht. |
| Katalogvollständigkeit | 24 gezielte Backendtests bestanden; der API-Katalog enthält im Checkout nun alle 125 eindeutigen Profile. Ein älterer isolierter Entwicklungsbuild zeigte noch 108 eindeutige Katalogeinträge und belegt die Lücke vor dieser letzten Änderung. |
| Isolierter HTTP-Nachtest des letzten Katalogstands | Build `8bcbacba3cd3` meldete über `/api/technologies` **125 eindeutige Profile**, davon **4 `MODEL_AVAILABLE` und 121 `MODEL_MISSING`**. [HTTP-Beleg](../tool-checker/runs/20260925_src_bus_capacity_repair_verify/20260925_src_bus_capacity_repair_verify_isolated-http.json). Der zugehörige Stack war ausdrücklich `PREPARED` und wurde danach entfernt; das ist kein Release-PASS. |

Der erste vollständige Backendlauf fand drei an die neue Nachweisregel anzupassende Fälle (2077 bestanden, 3 fehlgeschlagen, 2 übersprungen). Nach Korrektur der positiven Testfixture und der Behandlung ungeprüfter Zeitgrenzen ist die gesamte Backendsuite im zweiten Gate grün. Der erste Gate-Beleg `backend/test-output/release-gates/cfbddce73032/receipt.json` ist `FAIL` in der Backendphase. Der zweite Beleg `backend/test-output/release-gates/cbc45d3585f2/receipt.json` ist `FAIL` in der Browserphase; Tracebacks, Screenshots und Traces liegen im selben Gate-Verzeichnis.

Die CAN-FD-Zwei-Phasen-Regel wurde **nach** dem zweiten Gate ergänzt. Ihr endgültiger Quellstand ist durch den anschließenden vollständigen isolierten Backendtest nachgewiesen, besitzt aber keinen neuen Release-Gate-Beleg und keine neue getestete Image-ID. Die oben genannte Image-ID bezeichnet ausschließlich den früheren zweiten Gate-Kandidaten.

## Verbleibende Releaseblocker

Die fünf bisherigen Browser-Erfolgstests erwarten neun vollständige Wizardstufen und Simulation ohne neu bestätigte Nachweise. Alle fünf erreichen jetzt `Wizard BLOCKED at validation` im Preflight:

1. Kleines CAN-FD-Projekt ohne vollständig bestätigte Rate an allen verwendeten Ports/Netzen.
2. Raspberry-Pi-Projekt mit I2C ohne vollständig bestätigten technologiespezifischen Zeit- und Kapazitätsnachweis.
3. Raspberry-Pi-Projekt mit Modbus RTU ohne solchen Nachweis.
4. Erfasster 50/250/250-Auftrag mit offenen Raten-/Zeitnachweisen im bestätigten Originalauftrag.
5. AMEND nach Modellübernahme mit denselben offenen Nachweisen.

Diese Befunde sind mit der vom Nutzer bestätigten Sperrregel konsistent. Für einen PASS-Beleg müssen die E2E-Fälle fachlich um Bestätigungswege und echte Protokollmodelle ergänzt werden. Ein positiver neun-Stufen-Fall muss die nötigen Profil-/Gerätedaten ausdrücklich bestätigen; Fälle ohne diese Angaben müssen die sichtbare, fortsetzbare Review-Sperre prüfen. I2C und Modbus RTU benötigen ihre eigenen belastbaren Mechanismen und Geräteparameter, bevor ein positiver Simulationsnachweis möglich ist. Das ist noch nicht implementiert. Eine bloße Änderung der Testerwartung auf Erfolg oder das Übergehen des Preflight wäre fachlich falsch.

Die nachfolgende Korrektur macht einen solchen Preflight-Stopp fortsetzbar und zeigt die Befunde im Wizard. **Für die fünf alten Browserfälle liegt aber noch kein erneuter E2E-Durchlauf vor.** Die bisherige Release-Dokumentation verlangt für I2C/Modbus RTU und den unveränderten Großauftrag weiterhin eine vollständige Simulation ohne die jetzt verpflichtenden Geräte-/Modellnachweise. Eine Konzeptentscheidung zur Änderung dieses Abnahmevertrags ist angefragt und noch offen; bis dahin werden weder Erfolgserwartungen abgeschwächt noch unbestätigte Werte freigegeben.

**Freigabestatus:** kein PASS-Beleg. Das getestete Image wurde nicht in den Produktbereich ausgerollt; der laufende Produktserver und seine Projekte wurden nicht verändert. Der Quellstand enthält die Reparatur, aber das Release Gate verbietet eine Produktbereitstellung. Der zweite Gate-Lauf erreichte die Browserphase; die nachgelagerten HTTP-Abnahmen wurden nach deren FAIL nicht mehr ausgeführt.

Eine erneute lesende Prüfung des Produkts nach den lokalen Änderungen zeigte weiterhin Build `ec011a3fdd2f`. Der aktuelle Checkout ist nicht im Produkt aktiv. Der neue Quellstand benötigt nach Klärung des E2E-Vertrags einen frischen PASS-Beleg und die Bereitstellung genau dieses Images.

## Grenzen und nächste fachliche Arbeit

- Die 125 Technologien wurden im Audit klassifiziert, aber nicht einzeln als vollständiger Wizard-zu-Simulation-Produktfall getestet. Die Reparatur legt für 121 Typen kein neues deterministisches Modell an; sie verhindert deren falsche Freigabe.
- `average_load_percent` und ähnliche Felder werden intern als ungeprüfte Vorschau weiter berechnet. API-Nutzer müssen `capacity_verified` und `status` auswerten; die UI unterdrückt diese Zahlen bereits. Eine spätere API-Trennung in bewiesene Werte und Vorschauen ist sinnvoll.
- Für die offenen Technologien müssen TechnologyProfile, Gerätedaten, physische Topologie, Arbitrierung/Transfergrenzen und gegebenenfalls Anwendungsschichten jeweils fachlich spezifiziert und bestätigt werden. Die Audittabelle priorisiert die Gruppen.
- Die Wizard-End-to-End-Verträge in `docs/WIZARD_RELEASE_GATE.md` verlangen bislang vollständige positive I2C-/Modbus- und Großfälle. Sie müssen zusammen mit realen Bestätigungswegen und positiven Nachweisen überarbeitet werden. Ohne diesen Schritt bleibt die Deployment-Sperre bestehen.

Die Umsetzung folgt der bestätigten Sicherheitsentscheidung; sie ist **nicht** als vollständige Implementierung aller Busmodelle oder als Produktfreigabe zu verstehen.
