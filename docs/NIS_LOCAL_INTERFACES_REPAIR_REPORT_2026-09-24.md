# Reparaturbericht: I2C, SPI, PWM und GPIO

Stand: 25.09.2026. Betroffenes produktives Projekt: `20260924204620805-295989d5`.

## Ausgangsbefund

Im Raspberry-Pi-Projekt meldete NIS für mehrere PWM-Routen und eine GPIO-Route fehlende Standardkapazitäten. Daneben blieben die Zeitnachweise für I2C, SPI, PWM und GPIO mit allgemeinen Datenlücken offen. Der Nutzer bestätigte, dass NIS prüfbare, ausdrücklich ungeprüfte Hardwareprofil-Vorschläge anbieten und die Zeitfreigabe bis zur fachlichen Bestätigung sperren soll.

## Ursachen

1. Der Routing-Validator kannte GPIO/PWM als Schnittstellenprotokolle, behandelte sie bei der Kapazitätsrechnung aber als unbekannte paketbasierte Transporte. Dadurch erschienen `CUSTOM_PROTOCOL` und eine fiktive 1-Mbit/s-Auslastung.
2. Die Capacity-Analyse hielt den Zeitnachweis korrekt offen, bot die benötigten gerätespezifischen Felder aber nur als Fließtext an. Ein ungeklärtes Netz bekam im Dimensionierungsplan keinen ausklappbaren Nachweisblock.
3. Die Hardware-Interface-Bearbeitung bot für die vier lokalen Technologien keine strukturierten Felder mit Nachweisquelle. Das Projekt enthält beim Raspberry Pi 5 nur eine textuelle Produktangabe; ein bestätigtes Geräteprofil für die angeschlossenen Peripheriegeräte fehlt.

## Umsetzung

- GPIO und PWM gelten im Routing als direkte Signalleitungen. Paketnutzlastgrenzen, Buslastprozente und Standardkapazitätswarnungen werden dafür nicht mehr behauptet. Der Messwert `route_load_percent` bleibt `null`.
- Die bestehende TechnologyProfile-Registry liefert für I2C/SPI höchstens einen *ungeprüften Profilkandidaten* für die Bitrate. PWM/GPIO erhalten keine künstliche Bitrate. Der vollständige Reaktionszeitnachweis bleibt `UNVERIFIED`.
- Die Capacity-Analyse liefert je physischem Stream einen strukturierten Vorschlag mit offenen Feldern, Quelle und Endpunktkandidaten. Verschiedene I2C-Slave-Adressen verschiedener Geräte werden separat gezeigt.
- In der Netzdetailansicht und im Dimensionierungsplan sind diese Vorschläge sichtbar. Ein Hardware Interface kann I2C-Master, Slave-Adresse, Clock-Stretching und Transferumfang beziehungsweise SPI-Master, Chip Select und Transfergrenze sowie PWM-/GPIO-Zeitgrenzen mit Nachweisquelle speichern. Eine Bestätigung ist nur mit vollständigen Angaben und Quelle möglich.
- Auch bestätigte Eingaben geben ohne deterministisches, gerätespezifisches Scheduling-Modell keinen automatischen Zeit-PASS. Das verhindert eine Scheinsicherheit aus bloßen Profilwerten.

## Verifikation

- Isolierte SQL-/Backendtests: 88 bestanden (`test_routing.py`, `test_communication_dimensioning.py`, `test_capacity_can_schedule.py`).
- Frontend-Typprüfung: bestanden.
- `git diff --check`: keine Patch-Whitespace-Fehler.
- Erster vollständiger Gate-Lauf `f7d5a3db8fee`: Frontend-Typprüfung, Frontendtests und 2.052 Backendtests bestanden; das Gate beendete den Lauf mit `FAIL`, weil parallel in einem anderen aktiven Task Produktquelldateien geändert wurden (`Sources changed during unit verification`). Das war kein Testfehler der hier beschriebenen Reparatur.
- Zweiter vollständiger Gate-Lauf `f5dac634bd24`: **PASS**. Frontend-Typprüfung, Frontendtests, 2.056 Backendtests (2 übersprungen), Produktionsbuild, 68 Browser-End-to-End-Tests und beide HTTP-Prüfungen erfolgreich. Receipt: `backend/test-output/release-gates/f5dac634bd24/receipt.json`.
- Das exakt geprüfte Image `sha256:3b3bd2dda47df891f06622fa1418ea4992ab1d33a13545d57c7692c120d7566b` wurde über `scripts/deploy-verified-release.py` auf `NetworkIS` bereitgestellt. Der produktive `/api/build-info`-Endpunkt meldet denselben Quell-Hash `1c848042b4bf8ee02b4695ce82bce18c814c2cf0db017ce9d7ce854271800127` wie das Receipt.
- Produktive Gegenprobe für das betroffene Projekt: I2C (15 offene Prüffelder), PWM (9), GPIO (3) und SPI (4) zeigen jeweils `hardware_review_proposal.status=REVIEW_REQUIRED` und `communication_schedule.status=UNVERIFIED`. Bei PWM/GPIO ist `capacity_applicable=false`. Die produktive Routing-Tabellenvalidierung umfasste 11 Routen und ergab 0 `CUSTOM_PROTOCOL`-Warnungen, 0 Fehler und 0 Warnungen.
- Die gespeicherte Topologie wurde unverändert über den Workflow-Endpunkt bestätigt (8 Knoten, 7 Kanten, 0 erzeugte oder veraltete Routen); damit sind Netzwerk-Editor `COMPLETE`, Routing `APPROVED` und Capacity `WARNING`. Die aktuelle Kapazitäts-Snapshot-ID ist `a51ebaad-d658-43ae-a892-2a29461c11ae`. Der danach ausgeführte Preflight steht auf `WARNING` mit den vier offenen lokalen Zeitnachweisen; `ready_for_simulation=false`. Simulation und Data Science bleiben deshalb `OUTDATED`. Es wurde keine Safety- oder Zeitfreigabe aus ungeprüften Profilkandidaten abgeleitet.

## Fachlich offene Projektdaten

Für dieses Raspberry-Pi-Projekt fehlen weiterhin bestätigte Master-/Gerätezuordnung, I2C-Adressen und Clock-Stretching-Grenzen, SPI-Chip-Select und Takt-/Transfergrenzen sowie PWM-Frequenz, Aktualisierungs-/Erfassungsgrenzen und GPIO-Abtast-/Entprell-/Flankengrenzen. NIS zeigt sie jetzt gerätebezogen als Prüfauftrag. Sie werden weder erfunden noch stillschweigend aus einem generischen TechnologyProfile übernommen. Die Zeitfreigabe bleibt deshalb für diese Netze offen. Auch nach Eingabe und Bestätigung der Werte ist für eine automatische Freigabe noch ein gerätespezifisches Scheduling-Modell erforderlich; der vorliegende Fix liefert keinen solchen Nachweis.

Der Bericht zur vorangegangenen S01–S20-A/B-Produktionsreparatur steht in `docs/NETWORK_SIMULATOR_PRODUCTION_S01_S20_REPAIR_REPORT_2026-09-24.md`. Diese gezielte Reparatur ist kein vollständiger erneuter Tool-Checker-Lauf und erklärt die Kampagne nicht zum PASS.
