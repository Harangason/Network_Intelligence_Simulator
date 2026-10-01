# Technologieparameter – ausgeliefert, 2026-10-01

## Produktiver Stand

Build `0931ed1fbae6`, getestetes und laufendes Image `sha256:2715d9c009d614c90db5dbb543da2d10bd45c6ebfebf855055988c353feeaf3c`.
Vollständiger Release-Gate PASS; Lieferung durch `scripts/release-and-deploy.py`. Datenbank, Speicher und Anwendung betriebsbereit. Ein Kandidatenimage wurde nach Korrektur des Browsertests wiederverwendet. Historische Images wurden nicht gelöscht.

## Änderung und geprüfter Umfang

- TechnologyProfile/Registry liefert Vorschläge an Wizard, Parameterformular und Geräteeditor. Bestätigte Werte bleiben erhalten.
- 125 registrierte Profile und alle deklarierten Parameter auf Vorschlag, Datentyp, Auswahl und Grenzen geprüft. 13.392 verschiedene Technologiepaare auf fremde bestätigte Transportparameter geprüft.
- I²C: Standardmodus 100.000 bit/s; NMEA 2000: eigene feste CAN-Rate 250.000 bit/s; SPI: kein universeller Gerätetakt. Minimale/grenzwertige Raten werden anhand des tatsächlichen Profils validiert. CAN-FD-Altwerte bleiben kompatibel.
- Geräteeditor zeigt die Felder des ausgewählten Profils und bestätigt Vorschläge nicht automatisch. I²C-/SPI-Befunde nennen konkrete fehlende Transaktionsdaten und führen zu Geräteanschlüssen.
- 72 historische Katalograten bleiben als prüfpflichtige Katalogkandidaten gekennzeichnet. Sie sind kein unabhängig nachgewiesener Standardwert. Analyse-/Timingvorschläge sind keine garantierten Geräteanforderungen. Nicht ausführbare Kapazitätsmodelle werden ausdrücklich ausgewiesen.

## Verifikation

- Backend: 3.051 bestanden, 2 übersprungen, 56 Unterprüfungen bestanden.
- Frontend: 540 bestanden; Typprüfung bestanden.
- Browser: 79 bestanden, einschließlich aller 125 Busauswahlen und Geräteeditor.
- Echte HTTP-Abnahme klein: 18/18 Signale, keine ausgeschlossenen Signale, keine fehlenden Beobachtungen oder fehlgeschlagenen Routen.
- Echte HTTP-Abnahme groß: 1.169/1.404 Signale beobachtet, 235 ausdrücklich ausgewiesene Transportausschlüsse; keine fehlenden erforderlichen Beobachtungen oder fehlgeschlagenen Routen. Bewertungsstatus COMPLETE, Konformität PASS. Dies behauptet keine vollständige Transportabdeckung aller 1.404 Signale.
- Unabhängige Tool-Checker-Kampagne bleibt unverändert REPAIR_1_ACTIVE. Der Release-Gate-PASS ist kein Kampagnen-PASS.

## Aktuelles Projekt

Projekt `20261001051525213-c260002f`: sämtliche gespeicherten Parameter unverändert; I²C 100.000 bit/s weiterhin USER_CONFIRMED. Die 26 vorgeschlagenen Modelländerungen sind unverändert und nicht übernommen. Aktor, Sensor und ECU bleiben erkannt.
Der bestehende Vorschlag wurde erneut validiert. Vier offene I²C-Befunde nennen jetzt Master, Adresse/Adressbreite, Modus, Transferrichtung/-umfang, Start/Stop-, Clock-Stretch- und gegebenenfalls Arbitrationsgrenzen sowie Quelle/Bestätigung. Diese Daten benötigen Geräteunterlagen. Ein Standardtakt allein beweist keine Kapazität.

## Nachweise

Release: `backend/test-output/release-gates/delivery-7ae3589dab31/9c51183bc4d0/receipt.json`.
Katalog: `catalog-audit.md` und `catalog-audit.json` in diesem Ordner.
Produktivprüfung: `work/technology-defaults-live-verification-20261001.json`.
Vorschlagsprüfung: `work/technology-defaults-live-proposal-check-20261001.json`.
Screenshot: `work/technology-defaults-live-wizard-20261001.jpg`.
