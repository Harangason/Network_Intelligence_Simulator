# Lasso und verbindliche Systemzuordnung

Stand: 10.09.2026. Ausgelieferter Build: `46cb7bf5a661`.

## Bedienung

Im Netzwerk-Editor **Lasso · Zuordnen** einschalten, mit gedrückter linker
Maustaste ein Rechteck um Geräte oder Systemrahmen ziehen. Die Richtung des
Rechtecks und der Zoom sind frei. Ein markiertes Steuergerät nimmt seine
untergeordneten Geräte mit. Alternativ kann ein einzelnes ausgewähltes Gerät
über **Gerät zuordnen** bearbeitet werden.

Der Dialog zeigt die bisherige Zugehörigkeit und die geplante Änderung.
Cluster und Systemrahmen sind alphabetisch sortiert. Erst **Zuordnung und
Verbindungen übernehmen** speichert die Auswahl. Abbrechen schreibt nichts;
Escape beendet das Markieren beziehungsweise schließt den Dialog.

## Durchgängige Änderung

- Kanonische Geräteidentität: Cluster und Systembesitzer, einschließlich expliziter
  Aufhebung einer vorherigen Besitzerzuordnung.
- Physische Anschlüsse und Bussegmente: passende vorhandene Busse nutzen,
  bei Bedarf weitere Segmente und Anschlüsse anlegen. Die konfigurierten
  Teilnehmergrenzen werden berücksichtigt. Interne Busse eines vollständig
  verschobenen Systems bleiben erhalten.
- Routen: physische Pfade, Ports, Netze und gegebenenfalls Gateway-Hops neu
  bestimmen. Auch von umverdrahteten Verbindungen betroffene Durchgangsrouten
  werden berücksichtigt.
- Bei einem Besitzerwechsel Rückmeldungen zum neuen Besitzer führen und
  Befehle dort bereitstellen. Gemeinsam benutzte Befehle bleiben für die übrigen
  Geräte erhalten; Multicast-Routen werden bei einer Teilauswahl aufgeteilt.
- Nachrichten, Signale und Transportverträge: Produzenten, Empfänger,
  Signalquellen, Nachrichtenbindungen und gegebenenfalls kollidierende
  Nachrichtenkennungen abgleichen. Bitlayout, Skalierung und Einheit bleiben
  bei übernommenen Befehlen erhalten. Auch Signalrouten ohne explizite
  Nachrichtenreferenz werden unterstützt.
- Bestätigter Wizard-Systemgraph und Rückmeldungen für den Agenten werden
  aktualisiert. Explizite Zuordnungen haben Vorrang vor älteren Ableitungen.
- Die neue Szene wird serverseitig erzeugt und in SQL gespeichert. Unberührte
  manuelle Positionen bleiben erhalten. Simulation und Berechnung werden
  entsprechend als veraltet gekennzeichnet.

Vorschau und Übernahme verwenden einen Fingerabdruck und eine Versionsprüfung.
Zwischenzeitliche Änderungen verhindern die Übernahme einer veralteten Vorschau.
Alle Schreibvorgänge gehören zu einer Datenbanktransaktion. Eine ungültige Route
oder ein Fehler während des Schreibens rollt die gesamte Änderung zurück.
Geänderte Routen verlieren die alte Freigabe und stehen nach erfolgreicher
Validierung erneut zur Freigabe bereit.

Beim Browser-Abnahmetest wurde außerdem ein doppelter Synchronisierungslauf
gefunden und entfernt: Nach einer bestätigten Zuordnung werden nur die
Lesemodelle aktualisiert. Ein ausdrücklich angeforderter Modellabgleich lädt
anschließend die vollständige gespeicherte Szene und die aktuellen Versionen.

## Nachweise

Tests wurden auf den Kopien `lasso-assignment-acceptance-20260910` und
`lasso-assignment-multicast-20260910` durchgeführt. Das Originalprojekt
`network-project-20260910042736034-d11591d0` wurde nicht umgruppiert.
Seine Topologie und Parameter wurden abschließend mit dem Zustand vor Beginn
der Arbeiten verglichen: unverändert, 261 Geräte.

| Prüfung | Ergebnis |
| --- | --- |
| Backend: Zuordnung, Szenen, physische Anschlüsse, Modellbesitzer | 45 bestanden; 4 bestehende DB-abhängige Tests lokal übersprungen |
| Frontend einschließlich Lasso-Geometrie und alphabetischer Sortierung | 225 bestanden |
| Produktionsbuild einschließlich TypeScript-Prüfung | bestanden |
| Zwei komplette Rahmen in anderes Cluster, anschließend einzelner Aktor in anderes System | gespeichert, konsistent; 10 betroffene Routen erneut freigegeben |
| Teilauswahl einer Multicast-Befehlsroute | übriger Empfänger unverändert versorgt; 3 Routen erneut freigegeben |
| Browser: einzelner Aktor mit Lasso, Vorschau und Bestätigung | kanonischer Besitzer geändert; Befehl und Rückmeldung gültig |
| Browser: kompletter Rahmen bei 80 % Zoom, Rechteck von rechts unten nach links oben | zwei Geräte korrekt erfasst; Clusterwechsel gespeichert; 6 Routen erneut freigegeben |
| Veraltete Vorschau | HTTP 409, keine Schreibänderungen |
| Absichtlich ausgelöster Fehler nach dem ersten Route-Schreibvorgang | vollständiger Rollback einschließlich Kontext, Parametern und Relationen |
| Absichtlich ungültiger Kommunikationspfad nach Modelländerung | HTTP 400, vollständiger Rollback |
| Ansicht nach Speichern und erneutem Laden | Szene bleibt verfügbar |

Maschinenlesbare Ergebnisse stehen in `network-assignment-acceptance.json`,
`network-assignment-multicast-acceptance.json` und
`network-assignment-ui-acceptance.json`. Die HTTP- und Rollback-Skripte liegen
unter `scripts/verify-assignment-*.py` sowie `scripts/verify-network-assignment.py`.
Die Testskripte verwenden festgelegte Testprojekt-IDs und sollten auf frischen
Testkopien ausgeführt werden; sie verändern die genannten Testdaten bewusst.
