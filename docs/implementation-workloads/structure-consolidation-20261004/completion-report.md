# Konsequente NIS-Strukturkonsolidierung

Stand: 2026-10-04. Status: **ABGESCHLOSSEN, AUSGELIEFERT UND IN PRODUKTION VERIFIZIERT**.

Die erneute Prüfung bestätigt die Kritik an der bisherigen Umsetzung: Der frühere
Abschluss belegte R1–R5, erfasste aber nicht alle konkreten Technologiealgorithmen
in allgemeinen Generatoren und Trace-Diensten. Dieser Nachweis erweitert den
Umfang auf diese fachlichen Eigentümer und auf funktionslose Paketgerüste.

## Tatsächliche Änderungen

| Bereich | Fachlicher Eigentümer und Wirkung |
| --- | --- |
| CAN | Native Frame-/Signalformate, Nachrichtenkonstruktion, Payload-Kodierung, CRC/Bitpacking, BLF/DBC/MDF, Routing und Restbus-Beispiele liegen unter `backend/nis/communication/technologies/can/`. Die historische Generatorversion und ihre abweichende API bleiben ausdrücklich getrennt erhalten, ebenfalls unter CAN. |
| Ethernet | Frameformate, volle TX/RX-Portwarteschlangen, Portauslastung, Restbus-Sitzungen und Assessment-Findings liegen unter `ethernet/`. Allgemeine Trace-Dateien delegieren an diese Implementierungen. |
| IP, UDP, TCP, SOME/IP | Die vorhandenen Header- und Prüfsummenimplementierungen liegen beim jeweiligen Protokoll. Ethernet setzt diese Bausteine zusammen. IPv4/IPv6, VLAN und die bisherigen UDP-Nullprüfsummenverträge bleiben erhalten. |
| LIN | Poll-Slot-Ausrichtung, Weiterleitungswartezeit, native Taktevidenz und Reserve-/Budgetbewertungen liegen unter `lin/`. |
| CAN FD, I2C, SPI | CAN-FD-Phasen- und Anfrage/Antwortnachweise sowie Serial-Gerätetaktprüfungen gehören zu den registrierten Technologieeigentümern. Gemeinsame Provenienzaggregation bleibt im Assessmentdienst. |
| Registry | Scheduling und Parameteradapter werden vom bereits registrierten Timing-Eigentümer aufgelöst. Keine zweite Registry, kein fremder Technologiefallback. |
| Branchenbeispiele | Explizite Automotive-Demonstrationsdaten liegen als Vorlagen bei der Branche. Exportoptionen sind keine bestätigten Projektraten und registrieren keine neuen Fähigkeiten. |
| Altpfade | 106 überflüssige physische Technologie-Weiterleitungsdateien und damit beide alten Technologiequellbäume sind entfernt. Exakte alte Importnamen bleiben zentral registriert. Veröffentlichte ausführbare Dateieinstiege bleiben erhalten. |
| Leere Gerüste | Zehn unimplementierte Handler-Namensräume, fünf bloße BaseGenerator-Aliasordner, das unimplementierte allgemeine Physics-Gerüst und zwei leere Frontendrouten sind entfernt. Insgesamt wurden 35 nachweislich leere Verzeichnisse beseitigt. Tatsächlich konsumierte Workflow-/Automationsmetadaten bleiben erhalten. |

Die Importprüfung entdeckte zusätzlich einen Paketfehler beim alten Technologie-
Sammelpfad. Der unveränderte Ownership-Export ist jetzt ein echtes Paket; seine
Untermodulimporte funktionieren auch ohne physische Weiterleitungsdateien.

Die Zuordnungsliste erfasst auch Verbraucher von Altimporten, deren physische
Dateien bereits entfernt sind. Nicht beobachtbare externe oder persistierte
Verbraucher werden weiterhin ausdrücklich als Grenze ausgewiesen.

## Nachweise

- `ownership-before.json` und `ownership-after.json`: vollständiger AST-/Importbestand der geprüften kanonischen Quellbereiche. Nachher: keine physisch leeren Verzeichnisse und keine Leaf-Pakete mit ausschließlich einem Docstring unter `backend/nis` und `frontend/src`, ausgenommen generierte Caches.
- `behavior-equivalence.json`: Vergleich mit echten Vorher-Snapshots: 399 native Frames/Paketvergleiche, 15 Routing-/veränderbare Nachrichtenverträge, drei Restbus-Szenarien, 20 Runtime-Serialisierungen, 60 IPv4/IPv6/UDP/TCP/VLAN-Paketbytevergleiche und 225 Parameter-/Provenienzfälle ohne Abweichung.
- `final-targeted-complete.xml`: 290 gezielte Tests und 56 Subtests bestanden; eine vorhandene Modellfeldwarnung. `wildcard-imports.xml`: elf Fälle nach der abschließenden Exportkorrektur bestanden. Diese überlappenden Läufe werden nicht als 301 unabhängige Tests addiert.
- `installed-package-release.json`: echtes gebautes und separat installiertes Wheel; 125 Profile, 212 alte Technologieimporte mit identischer kanonischer Modulidentität und native Format-/Restbus-Smoketests bestanden. Keine Backendimporte aus dem Source-Checkout.
- `alias-inventory-verification.json`: absolute und bare Altimporte einer physisch entfernten Datei behalten ihre beobachteten Verbraucherkanten.
- `checker-release-result.json`: abschließende bestehende Tool-Checker-Suite: fünf von fünf Fällen PASS. Die historische EA-Kampagne ist hiervon unabhängig.
- `before-index.json`, `after-index.json`, `changes.patch`: ursprüngliche Snapshots, neue Dateien und Entfernungseinträge; nur Änderungen dieses Auftrags. 197 geänderte Dateien: 123 entfernt, 36 erstellt und 38 geändert. Bestehende Änderungen und historische Nachweise bleiben erhalten.

Alle SQL-Prüfungen verwenden `scripts/run-isolated-tests.py` mit temporären
Postgres-Containern. Der Produktdatenbestand ist kein Testziel.

## Abnahme des Migrationsplans

Der bisherige fachlich gegliederte Backend-/Frontendbestand, Datenpfade,
Identitätsprojektionen und Berechtigungsverträge bleiben durch ihre bestehenden
Tests geschützt. Diese Runde ergänzt die zuvor unvollständig geprüften
Technologieimplementierungen, Paketgrenzen und leeren Quellgerüste.
Die gesamte ursprüngliche Risikomatrix wird vom vollständigen Backend-/Frontend-
und Browser-/HTTP-Release-Gate geprüft. Ein gezielter PASS ersetzt diese Abnahme
und die anschließende Produktionsauslieferung nicht.

## Release und Produktion

`backend/.venv/Scripts/python.exe scripts/release-and-deploy.py` ist mit Exitcode 0
abgeschlossen. Der vollständige Receipt steht auf **PASS**, alle acht Checks auf
Exitcode 0. Derselbe Befehl hat das exakte getestete Image auf die kanonische
Produktionsinstanz `NetworkIS` ausgeliefert und die laufende Identität geprüft.

- Receipt: `backend/test-output/release-gates/delivery-ffc6f9dda8d7/bdc9bef1951e/receipt.json`.
- Getestetes und laufendes Image: `sha256:148b7646d74436524c99f833304674cebf5a80788f245181d99db3f1ff6a5f9f`.
- Geprüfter und laufender Quellhash: `eb9a582b7a121595d690d1ec048c0809913dbeb8857075f49ef79c52357da316`.
- Backend: **21.564 Tests und 56 Subtests bestanden**, zwei übersprungen, eine Warnung.
- Frontend: **564 Tests bestanden**, TypeScript-Prüfung bestanden.
- Browser: **86 Fälle bestanden**, einschließlich neun Stufen, Wiederherstellung,
  echter Modellübernahme und des bestätigten großen 50/250/250-Auftrags.
- HTTP, klein: neun Stufen, **6/6 Routen**, 18 erforderliche und beobachtete Signale,
  Konformität PASS und keine fehlgeschlagene Route.
- HTTP, groß: neun Stufen, **766/766 Routen**, 594 transportpflichtige Nachrichten
  und 1.169 erforderliche Signale vollständig abgedeckt, Konformität PASS und keine
  fehlgeschlagene Route. 59 Nachrichten mit 235 internen, nicht gerouteten Signalen
  bleiben ausdrücklich vom Transportscope ausgeschlossen; für sie wird keine
  funktionale Beobachtung oder Timing-Freigabe behauptet. Fachliche Warnungen im
  großen Szenario wurden über den echten Preflight-Freigabeschritt behandelt und
  bleiben sichtbar. Transportkonformität ersetzt keine funktionale Timing-Abnahme.
- Produktion: `healthy`, Readiness für Datenbank und Speicher vorhanden. Native
  CAN-/Ethernet-Erzeugung, Paketbytes, LIN-Ausrichtung, Zeitstempelpräzision,
  212 alte Importidentitäten und fünf Generator-Wildcard-Exporte bestanden.
  Beide früheren physischen Technologiequellbäume sind auch im Image abwesend.
- Der gesamte Technologiekatalog stimmt vor und nach der Auslieferung überein
  (125 Profile). `/api/ready`, `/api/build-info` und `/api/technologies` sind sowohl
  lokal als auch über LAN geprüft. Nachweise: `production-running-image.json`,
  `production-native-smoke.json`, `production-verification.json`,
  `delivery-release.log` und die Browser-/HTTP-Berichte neben dem Receipt.

Zwei frühere eigene Gate-Läufe wurden **vor dem Imagebau** als ABORTED beendet:
zunächst zur Entfernung der letzten zwei Technologie-Paketwurzeln, danach zur
Erhaltung der historischen Generator-Wildcard-Exporte. Diese Läufe sind keine
PASS-Nachweise. Der oben bezeichnete finale Lauf prüft und liefert den endgültigen
Quellstand aus. Historische Images wurden nicht bereinigt.

Zugriff: [Lokal](http://localhost:13500) · [VPN/LAN](http://192.168.178.10:13500).

`final-source-verification.json` bestätigt zusätzlich die Original-Snapshot-Hashes,
alle 197 aktuellen Datei-/Entfernungseinträge und die Gleichheit des lokalen
Quellhashs mit dem getesteten und ausgelieferten Stand.

## Abschluss und Grenzen

Die sechs erforderlichen Ergebnisse und fünf Validierungen dieses Auftrags sind
mit Datei-Hashes im `workload.json` belegt. Es bleiben keine offenen Befunde dieses
Auftrags. Der Completion-Guard bestätigt den Abschluss separat in
`completion-guard.json`; die historische EA-Kampagne wird dadurch nicht als PASS
erklärt. Die bestehenden vollständigen Release-Tests sowie die neuen Eigentümer-
und Importregressionen schützen den konsolidierten Bestand.

Der Nachweis umfasst den lokalen kanonischen Quellbestand, seine beobachtbaren
Verbraucher, das separat installierte Paket und die ausgelieferte Anwendung.
Nicht beobachtbare externe oder persistierte Verbraucher bleiben als Grenze der
Abhängigkeitsinventur ausgewiesen. Reale Workflow-/Automationsmetadaten und
veröffentlichte ausführbare Kompatibilitätseinstiege bleiben begründet erhalten.
