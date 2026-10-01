# Herkunft und Anwendbarkeit jedes Felds

Diese Regeln sind ein Prüfplan. Sie erklären noch keinen Bustyp für vollständig
verifiziert. Jede Einzelakte muss die Anwendbarkeit und Quellen separat bestätigen.

## Bus- und Protokollparameter

Rate, Phasen, Mode, Framing, Adressierung, PHY, Arbitration und protokollspezifische
QoS gehören dem ausgewählten TechnologyProfile bzw. dessen explizitem Stack.
Ein Literaturwert braucht Quelle, Ausgabe, Abschnitt, Einheit und Bedingungen.
Ein maximaler Modustakt ist keine minimale Betriebsfrequenz. Ein obligatorischer
Basismodus hat Vorrang vor dem kleinsten Zahlenwert eines optionalen Modus.
Ein Profil mit mehreren möglichen Transporten verlangt eine ausdrückliche Auswahl.

## Tatsächliche Geräteeigenschaften

Teilnehmeridentität, Geräteadresse, Leitungslänge, Transceiver, Abtast-/Wandlungszeit,
Stretching, Setup-/Hold-Zeit, Queuegrenzen und Durchsatz sind keine universellen
Busdefaults. Quellen sind das ausgewählte Datenblatt, die Verdrahtung oder ein
bestätigter Transaktions-/Schedule-Nachweis. Busweite Angaben gehören zum Netz;
zielgerätespezifische Angaben zum Zielgerät; Transferumfang und Richtung zur
Transaktion. Eine Controller-Schnittstelle erhält nicht automatisch eine Slaveadresse.

## Anforderungen aus dem Projekt

Payload, Periode, Deadline, Timeout, zulässige Latenz/Jitter, Datenalter und geforderte
Zuverlässigkeit müssen zum tatsächlichen Auftrag passen. Ein Protokollgrenzwert
beweist diese Anforderungen nicht. Literaturdefault nur bei ausdrücklicher Definition
des betreffenden Protokollparameters, niemals durch bloße Namensähnlichkeit.

## NIS-Analyse und Simulationsszenario

Zielauslastung, Warnschwellen, Peak-/Burstfaktoren, Simulationsdauer, Seed, Eventlimit
und eingespritzte Fehler sind NIS-Konfiguration. Bestehende Szenariovorschläge dürfen
als solche angeboten werden; sie werden nicht als Busstandard oder Gerätebeweis
ausgegeben. Keine automatische Bestätigung durch bloßes Laden eines Formulars.

## Optionale Funktionen

Queue-, Prioritäts-, Sync- und Gatewayangaben gelten nur bei einer tatsächlichen
betreffenden Ressource/Funktion. Für CAN-Identifier, Ethernet-PCP, DDS-QoS,
I2C-Arbitration und Funk-Scheduling gelten unterschiedliche Semantik und Grenzen.
Ein universelles Prioritätsfeld 0–7 oder NTP/PTP für jeden Bus ist nicht zulässig.
Vorhandene bestätigte Projektwerte bleiben gespeichert, werden aber bei anderem
Profil nicht als dessen Parameter übernommen.

## Abschluss einer Einzelakte

Alle ursprünglichen und zusätzlich erforderlichen NIS-Felder sind einzeln erfasst:
Bedeutung, Einheit, Gültigkeit, Default/Herkunft, Grenzen/Abhängigkeiten und Quelle.
Unbelegte Standardbehauptungen sind entfernt. Unbekannte konkrete Hardwaredaten
bleiben offene Eingaben. Zusätzlich müssen Implementierung, Negativtests,
Persistenz und betroffene Berechnungspfade verifiziert sein. Eine fehlende
Berechnungsengine bleibt MODEL_MISSING; sie darf keinen Kapazitäts-PASS liefern.
