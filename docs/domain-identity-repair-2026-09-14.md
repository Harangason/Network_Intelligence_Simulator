# Branche und Anschlusstechnik bei der Generierung erhalten

Stand: Korrektur implementiert, geprüft und am 14.09.2026 installiert.
Gate `f001288a38bd`: PASS. Build `9b599fccf321`.

## Befund

Der betroffene Auftrag ist als `embedded_systems` gespeichert, mit einem Controller,
drei Sensoren, fünf Aktoren und keinem Gateway. Die Technologieauswahl enthält
ADC/DAC/GPIO/I2C. Die fachliche Branche war daher nicht Automotive.
Der Parser behandelte einige Embedded-Technologien unvollständig, fiel allgemein
auf CAN zurück und ergänzte die unbenannten Ventilaktoren über Branchenvorlagen.
Deren Owner wurden in der Vollständigkeits-Erweiterung zu zusätzlichen Controllern.
Der Backend-Generator ersetzte jede Technologie außerhalb seiner kleinen Zuordnung
pauschal durch `automotive_ethernet` – auch SPI, ADC oder unbekannte Anschlüsse.

## Korrektur

- Ein expliziter Branchenparameter gilt gleichermaßen für `domain` und `modelType`.
- Fehlende Protokollangaben in Nicht-Automotive-Projekten bleiben `Other`.
  Explizites CAN bleibt auch außerhalb Automotive zulässig; Technologie und
  fachliche Branche sind getrennte Eigenschaften.
- ADC/DAC/GPIO/PWM werden bei Protokoll-, Technologie- und Anzahlermittlung erkannt.
- Bei genannten Ventilen und bestätigter Aktoranzahl werden die entsprechenden
  Ventilidentitäten erzeugt, statt unpassende Stellglieder aus Vorlagen einzusetzen.
- Die Topologiezuordnung verwendet für weitere Technologien das zentrale Register.
  Unbekannte Anschlüsse erzeugen einen Fehler mit Aufforderung zur Klärung,
  niemals ein erfundenes Automotive-Ethernet-Netz.
- Generatorversion v18 verhindert die unveränderte Wiederverwendung alter
  Vorschläge bei erneuter Generierung. Bestehende bestätigte Aufträge/Objekte
  werden durch die Installation nicht stillschweigend umgeschrieben.

## Nachweise und Grenzen

14 isolierte Backendtests bestanden, darunter eine echte Vorschlagserzeugung mit
einem Pi, drei Temperatursensoren und fünf Ventilaktoren in Embedded Systems und
ADC-Anschlüssen. Frontendtests prüfen Geräteidentitäten, unbekannte Anschlüsse,
Branchentreue und Embedded-Techniken. Der Produktionskandidat basiert auf
PASS `15ad5944b936`, mit genau vier deklarierten Änderungen und 1501 unveränderten
Dateien. Andere Änderungen im gemeinsamen Arbeitsverzeichnis sind nicht enthalten.

Die ADC-Vorgabe in diesem Test prüft die Identität der Technologie, nicht die
elektrische Eignung eines konkreten Raspberry-Pi-Modells oder Ventils. Unbekannte
Ports, Treiber, Zuordnungen und Regelungsfristen bleiben fachlich zu klären.
Die vollständige Regression bis Stufe neun wird vom Release-Gate ausgeführt.

## Abgeschlossene Prüfung und Installation

Alle sieben Releaseprüfungen bestanden: TypeScript, 333 Frontendtests,
1566 Backendtests (2 übersprungen, eine bekannte Pydantic-Warnung),
Produktionsbuild, 7 Browser-E2E-Fälle sowie kleine und große HTTP-Abnahme.
Die vorhandenen vollständigen Neun-Stufen-Fixtures prüfen den bisherigen
Gesamtworkflow; der zusätzliche Embedded-Test prüft die reale Vorschlagserzeugung,
nicht einen elektrischen Nachweis oder eine vollständige Embedded-Simulation.

Installiert ist das exakt geprüfte Image
`sha256:81f1b85564b7dcda1528aff84cb868030e8fa072e1af5e0fead5f6852c5596d6`.
Vor Installation wurde ein konsistentes Datenbankbackup erstellt (254664474 Bytes).
Alle 18 Nachprüfungen bestanden: Image, Build und Bereitschaft, Projektbestand,
Workflowrevision, Jobs, Snapshots, Volumes, Datenbankimage und Laufzeiteinstellungen.
Das Nutzerprojekt hatte vor und nach Installation einen Vorschlag und noch keine
kanonischen Hardwareobjekte. Der alte fehlerhafte Vorschlag wurde nicht verändert
oder freigegeben; eine erneute Generierung benötigt die neue Generatorversion.

Nachweise: `backend/test-output/domain-identity-release-gates/f001288a38bd/receipt.json`,
`source-provenance.json`, `product-backup.json`, `product-deployment-verification.json`.
Die verbindliche Branchenregel ist zusätzlich in `docs/WIZARD_EXECUTION_CONTRACT.md`
festgehalten.
