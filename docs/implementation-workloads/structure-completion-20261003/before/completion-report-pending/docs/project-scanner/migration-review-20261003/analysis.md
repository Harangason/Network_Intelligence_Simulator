# Prüfung der NIS-Strukturmigration

Stand: 03.10.2026. Prüfauftrag: Umsetzung gegen
`H:/OneDrive/Download/NIS_PROJEKTSTRUKTUR_UND_MIGRATIONSPLAN.md` prüfen.
Die Arbeitsanweisungen im Dokument wurden als Sollkriterien ausgewertet;
dieser Auftrag umfasst keine funktionale Nachimplementierung.

## Ergebnis

**Wesentlich umgesetzt und ausgeliefert, aber fachlich nicht vollständig abgeschlossen.**
Die neue Paketstruktur enthält echte Implementierungen. Technologieprofile,
Frontend-Features, zentrale Datenpfade, Kompatibilität und Produktionslieferung
sind durch Code und Testbelege gestützt. Die pauschale Aussage `COMPLETED` mit
`remaining_findings: []` ist gegenüber dem vollständigen Migrationsplan zu weitgehend.
Insbesondere wurden nicht alle technologiespezifischen Regeln aus allgemeinen
Modulen extrahiert. Ein noch vorhandener Frontend-Fallback ist reproduzierbar.

Quellstand: Git `2aeeec8facc169aa5e9eb414364d1f3b6d890b46`, umfangreicher
uncommitteter Arbeitsbaum. Maßgebliche aktuelle Anwendungsidentität:
`f482a20810f7727651e26cc8d77aad1f7160a1c420ac00b1d2757abee28ab182`.
Berichtsänderungen verändern diese Anwendungsidentität nicht.

## Befunde nach Priorität

### R1 — P1: Frontend ersetzt andere und unbekannte Technologien durch CAN FD

**Soll:** Abschnitte 4.3, 7 und 12: Registryvertrag konsumieren;
fehlende Unterstützung ausdrücklich melden; kein stiller CAN-/Ethernet-Fallback.
Zusätzlich gilt der bestehende TechnologyProfile-Vertrag.

**Ist:** [bus-technology.ts](../../../frontend/src/features/communication/lib/bus-technology.ts#L4)
besitzt eine kleine handgepflegte Aliasliste und liefert in Zeile 14 grundsätzlich
`can_fd`, wenn keine der dort bekannten Zuordnungen passt. Ein explizites
`MODBUS_RTU`, `NMEA2000` oder `MATTER` ist in dieser Liste nicht enthalten.
Ein Netzwerkname kann dann sogar eine andere Zuordnung erzwingen.

**Reproduktion:** Node mit der unveränderten Funktion, Netzwerk `marine_bus_01`:

| Protokoll | Rückgabe |
| --- | --- |
| `MODBUS_RTU` | `can_fd` |
| `NMEA2000` | `can_fd` |
| `MATTER` | `can_fd` |
| `ZZ_UNKNOWN` | `can_fd` |
| `null` | `can_fd` |

Originalausgabe: [frontend-fallback-reproduction.jsonl](frontend-fallback-reproduction.jsonl).

**Verbraucher und Wirkung:**
[simulation-wizard.tsx:199](../../../frontend/src/features/simulation/ui/simulation-wizard.tsx#L199)
verwendet diese Rückgabe für die Busart eines Netzwerkvorschlags.
`mergeRoutingSuggestionsIntoTopology` übernimmt sie in Ports und Kanten
(Zeilen 486–500). `applyAllRoutingSuggestions` ruft damit
`persistNetworkRelationships` auf (Zeilen 951–962).
Damit reicht die falsche Ableitung bis in einen schreibenden UI-Ablauf.
Die Hilfsfunktion wurde direkt ausgeführt; ein falscher Vorschlag wurde im
Produktionsprojekt **nicht** gespeichert. Ob jede betroffene Technologie durch
alle UI-Vorbedingungen zu diesem Ablauf gelangt, wurde nicht im Browser nachgestellt.

**Restarbeit:** Explizite Registryidentität erhalten. Nicht darstellbare Busarten
müssen eine offene/gesperrte Zuordnung ergeben. Netzwerk-Namensheuristiken dürfen
eine ausdrücklich angegebene Technologie nicht ersetzen. Positivfälle,
registrierte weitere Technologien und unbekannte Eingaben gemeinsam prüfen.

### R2 — P1: Technologiepakete besitzen noch nicht sämtliche technische Regeln

**Soll:** Abschnitte 4.2, 5 sowie Phasen 1–3: CAN-Regeln und Adapter bei CAN;
Technologieformeln aus allgemeinen Kapazitätsmodulen extrahieren;
allgemeine Orchestrierung und Dispatching außerhalb der Technologie belassen.

**Ist, am Quelltext geprüft:**

- [calculators.py:136](../../../backend/nis/engineering/capacity/calculators.py#L136)
  enthält CAN-FD-DLC-/Wire-Length-Regeln.
- [calculators.py:181](../../../backend/nis/engineering/capacity/calculators.py#L181)
  enthält CAN-CC-Stuffing und ab Zeile 193 CAN-FD-Phasenberechnungen;
  ab Zeile 217 Ethernet-Framing und ab Zeile 241 LIN-Framing.
- [calculators.py:275](../../../backend/nis/engineering/capacity/calculators.py#L275)
  implementiert die CAN-Zeitobergrenze.
- [event_scheduler.py:18](../../../backend/nis/simulation/runtime/event_scheduler.py#L18)
  enthält `_CanBus` und die konkrete CAN-Arbitrierung nach CAN-ID
  (Zeilen 94–102), neben allgemeiner Ereignisverwaltung.
- [catalog.py:5](../../../backend/nis/communication/catalog.py#L5) definiert die
  CAN-FD-DLC-Tabelle. `DDS_POLICY_ENTITIES` und die 577 Zeilen umfassende
  `REVIEW_RATE_PROPOSALS`-Definition ab Zeile 105 enthalten weiteres
  technologisches Wissen direkt im allgemeinen Katalog.
- [components.py:745](../../../backend/nis/communication/core/components.py#L745)
  enthält CAN-FD-/LIN-Sonderbehandlung. Der Registry-Timingadapter ruft in
  Zeilen 829–830 weiterhin `engineering.capacity.calculators.estimate_frame` auf.

Die Definitionen und CAN-Formatadapter liegen bereits im richtigen Paket;
LIN besitzt außerdem ein echtes `timing.py`. CAN und CAN FD besitzen keine
entsprechenden Timing-/Simulationsmodule, obwohl konkrete Implementierung
außerhalb existiert. Das Problem ist deren Verantwortung und Abhängigkeit,
nicht allein das Fehlen bestimmter Dateinamen. Die CAN-Ownership-Metadaten
verweisen ausdrücklich auf die allgemeinen Module und bestätigen die Verteilung.

**Bewertung:** Eine gemeinsame Paketwurzel und ein Profilordner pro ID sind
erreicht. Die im Plan geforderte vollständige fachliche Technologieheimat ist
nicht erreicht. Dies belegt keine fehlerhafte numerische Berechnung;
die gezielten CAN-/LIN-Regressionen bestehen.

**Restarbeit:** Technische Konstanten, konkrete Berechnungen und Arbitrierung
zu den verantwortlichen Technologiepaketen verlagern. Allgemeine Adapter
konsumieren deren öffentliche Verträge. Vorher-/Nachher-Verhalten, Varianten,
Kapazitätsstatus und gespeicherte IDs unverändert nachweisen.

### R3 — P2: Übergangsnachweise sind pauschal, Zuordnungsliste hat Lücken

**Soll:** Phase 6 verlangt pro Wrapper Verbraucher, Verantwortlichen und
Entfernungskriterium; Abschnitt 12 verlangt jede betroffene Datei in der Liste.

**Ist:** [structure_mapping.csv](../../migrations/structure_mapping.csv) enthält
3.663 Zeilen, darunter 927 `move-with-forwarding-entry` mit
`COMPATIBILITY_RETAINED`. Für sämtliche 3.617 Nicht-Datenzeilen ist `consumers`
wortgleich: `Recorded import graph and migration plans; canonical owner consumers preserved`.
Der Verifikationstext ist ebenfalls durchgehend derselbe Releaseverweis.
Ein individuell auflösbarer Verbraucherbeleg steht damit nicht in diesen Zeilen.
[project-structure.md](../../architecture/project-structure.md) formuliert
allgemeine Entfernungskriterien; die Aliasdatei enthält Pfadpaare.
Die gelesenen Migrationspläne enthalten Umzüge und Dateiinhalte, aber keine
individuellen Wrapper-Ablösebedingungen.

Zusätzlich fehlen folgende aktuelle Quellen sowohl unter `source_path`
als auch unter `target_path`:

- `scripts/build/project-vocabulary.py`
- `scripts/tests/test_release_frontend_discovery.py`
- `frontend/src/app/api/simulations/[id]/artifacts/[format]/route.ts`

Der Vokabularprojektor ist in der Architekturdokumentation ausdrücklich als Teil
der neuen Struktur beschrieben. Für die beiden anderen Dateien ist ihre
Zuordnung im Abschlussinventar nachzutragen beziehungsweise ihr abweichender
Umfang konkret zu begründen.

**Bewertung:** Die Zahl verbleibender Wrapper ist kein eigenständiger Fehler.
Ihre Beibehaltung schützt veröffentlichte Imports und Einstiegspunkte.
Es fehlt der verlangte konkrete Übergangsnachweis; Wrapper nicht pauschal löschen.

**Restarbeit:** Pro Altpfad tatsächliche interne/externe Verbraucher oder
explizit ungeklärte Verbraucher, zuständigen Owner und überprüfbares
Entfernungskriterium dokumentieren. Listenabdeckung automatisiert vergleichen.

### R4 — P2: Architekturprüfungen schützen die offenen Abnahmekriterien nicht

**Soll:** Abschnitt 11 fordert Prüfungen gegen technische Regeln außerhalb
ihrer Quelle sowie Integration neuer Architekturprüfungen in CI und Tool Checker.

**Ist:** [test_structure_architecture.py](../../../backend/tests/test_structure_architecture.py)
prüft Profilowner/IDs, einige Aliasidentitäten, statische Altimporte,
Branchen-Projektionen und Vokabulargleichheit. Diese Tests bestehen trotz R2.
Der vorhandene Frontendtest prüft die bekannten sechs Busarten und einen
historischen LIN-Namen; er besteht trotz R1.

Die neuen Tests werden im vollständigen Backend-Releasegate ausgeführt.
Eine Registrierung ihrer zusätzlichen Architekturregeln in den gelesenen
Tool-Checker-Konfigurationen/-Quellen/-Testfällen wurde nicht gefunden.
`tool-checker/config`, `gates` und `src` enthalten keine Dateien;
der aktive Bestand liegt unter `.tool-checker/`. Dessen
`config/project-cli.json` referenziert eine ältere Masterkampagne.
Eine Namenssuche ist kein Beweis, dass alle indirekten Prüfaufrufe fehlen;
ein konkreter Registrierungsbeleg fehlt jedoch. Der ursprüngliche Abschlussbericht
weist ausdrücklich keinen Tool-Checker-Kampagnen-PASS aus.

**Restarbeit:** Ownershipgrenzen und unbekannte Technologiezuordnungen
ausführbar prüfen, Listen-/Wrapperabdeckung prüfen und die Prüfungen im
vorhandenen Checker registrieren. Bestehende Kampagnennachweise erhalten.

### R5 — P3: Modulbezogene Technologie-Dokumentation fehlt

**Soll:** Abschnitt 4.2 nennt eine CAN-`README.md` mit Verantwortungen,
öffentlichen Aufrufen, tatsächlichen Fähigkeiten und Tests.

**Ist:** Keine `README.md` in den geprüften Paketen CAN, CAN FD, Ethernet,
LIN oder FlexRay. Die allgemeine Architekturdokumentation ist vorhanden,
ersetzt aber den geforderten Einstieg in das CAN-Modul nicht.

**Restarbeit:** Tatsächliche öffentliche Schnittstellen, Profil-/Variantenbezug,
Formatfähigkeiten und Verifikation je Modul dokumentieren. Fehlende Fähigkeiten
weiter ausdrücklich ausweisen; keine leeren Implementierungsdateien anlegen.

## Abnahmeübersicht

| Kriterium aus Abschnitt 12 | Bewertung und Nachweis |
| --- | --- |
| Gemeinsame Technologiehierarchie | Erfüllt für 125 Runtimeprofile; Paketowner-Test erneut bestanden. |
| Eine verantwortliche technische Quelle, konsumiert von Berechnungen/UI/Agent | Teilweise; R1/R2, weitere Planungsdefaults in Frontend und Backend separat. |
| Branchen referenzieren Technologien | Geprüfte Branchen-Projektionsprüfung besteht; historische Exportpresets explizit getrennt. |
| Technologieabdeckung und Varianten erhalten | Vorhandener Gleichheitsbeleg für 125 Profile/Registry; aktuelle Registrytests bestehen. Keine neue vollständige Inhaltsgleichheitsprüfung aller Profile in diesem Audit. |
| Projekte/Traces/Lernzustände/Jobs erhalten | Vorhandene lokale und produktive Snapshot-/Vergleichsbelege. Migrationstests bestehen. Keine neue vollständige fachliche Wiederaufnahme sämtlicher Lernzustände/Jobs. |
| API/CLI/MCP kompatibel | Installiertes-Paket-Beleg: 238 Routen, 125 Profile, 54 Presets, Importidentität. Historische komplette Releaseprüfung. Nicht alle 238 Routen einzeln erneut ausgeführt. |
| Zentrale Datenpfade, unabhängig vom Startort | Pfad- und Speichermigrationstests erneut bestanden. Alte unklassifizierte Nachweise/Originale werden bewusst erhalten. Ihre Existenz allein ist kein Fehler. |
| Jede betroffene Datei und begründeter Altpfad | Teilweise; R3. |
| Relevante Prüfungen bestehen, Lücken ausgewiesen | 86 gezielte Backendtests und ein vorhandener Frontendtest bestanden; aktuelle vollständige PASS-Receipt vorhanden. Ownership-/Fallback-/Checkerlücken: R4. |
| Dokumentation zeigt tatsächliche Struktur und Technologieeinstieg | Zentrale Architektur vorhanden; R5 und zu weitreichender Abschlussstatus. |

Phasenstatus: Phase 0 weitgehend belegt, Phase 1/2 wegen R2 unvollständig,
Phase 3 weitgehend umgesetzt mit noch nicht extrahierten Mischmodulen,
Phase 4 wegen R1 unvollständig, Phase 5 weitgehend belegt mit Dokumentationslücken,
Phase 6 wegen R3 unvollständig dokumentiert.

## Tatsächlich ausgeführte Verifikation

- Acht Backend-Testdateien über `backend/.venv/Scripts/python.exe
  scripts/run-isolated-tests.py`: **86 passed**, eine bekannte Modellfeldwarnung.
  Datenbankcontainer ausschließlich temporär/isoliert.
  [JUnit](targeted-tests.xml) enthält die einzelnen ausgeführten Fälle.
- `node --experimental-strip-types --test` für den vorhandenen
  `bus-technology.test.mjs`: **1 passed**.
- Unabhängige direkte Reproduktion der Frontend-Zuordnung: R1.
- Aktuelle HTTP-GETs `/api/ready` und `/api/build-info`: **200**, bereit;
  aktueller Quellhash entspricht dem laufenden Build.
- Docker-Inspect von `NetworkIS`: laufendes Image
  `sha256:82aba31b746f261bba90acdf19007bd572a5a05bcdd83f54e7913e5a2c364fe5`.
  Die vorhandene [aktuelle PASS-Receipt](../../../backend/test-output/release-gates/delivery-03abc9b49c50/e3f92b376988/receipt.json)
  benennt genau dieses Image und den aktuellen Quellhash; alle sieben dort
  aufgeführten Prüfungen haben Exitcode 0.
  [Frische Live-Verifikation](live-verification.json).
- Ursprüngliche Migrationsauslieferung: gültige historische PASS-Receipt
  `delivery-bf7db4db22a9/b81ef9f92f9f`, Image `7127544b2f8a…`.
  Der [Abschlussbericht](../../implementation-workloads/project-structure-migration-20261003/completion-report.md)
  meldet 21.551 Backend-, 560 Frontend- und 85 Browsertests sowie kleine/große
  Neunstufen-HTTP-Abläufe. Diese Zahlen sind vorhandene historische Belege,
  keine in diesem Audit neu ausgeführten Gesamtläufe.
- Automatischer Scanner: [Audit](scanner/audit.md), [Inventar](scanner/scan.json).
  6.408 Dateien inventarisiert, 1.928 Python-Dateien per AST geprüft, keine
  Parser-/Lesefehler im erfassten Umfang. Semantik nur an den in diesem Bericht
  benannten Quellen geprüft. Ausschlüsse stehen im Inventar.
  PEP 8 mit Basiswert 79 zeigt Stilbefunde; diese überwiegend bestehenden
  Befunde sind kein Nachweis für eine Migrationsregression. DE/EN-Markerprüfung
  beweist keine Übersetzungsqualität und war kein Abnahmekriterium dieses Plans.

Der erste lokale Testversuch nutzte versehentlich den allgemeinen Anaconda-
Interpreter und brach mit drei Collectionfehlern wegen fehlendem `psycopg` ab.
Der oben dokumentierte vollständige Wiederholungslauf verwendete die vorhandene
Backend-Umgebung und bestand. Daraus wird kein Produktfehler abgeleitet.

## Nächste Arbeiten und Grenzen

1. R1 korrigieren und die übernommenen Netzwerkvorschläge gegen bestätigte
   Registryidentitäten prüfen.
2. Die in R2 konkret belegten technischen Regeln samt Verbrauchern extrahieren.
3. R3/R4 schließen: konkrete Wrappernachweise, vollständige Zuordnungsliste,
   passende Architekturprüfungen und Checkerregistrierung.
4. R5 und den Abschlussstatus an die tatsächlich erreichten Kriterien anpassen.
5. Nach funktionalen Korrekturen vollständiges Releasegate ausführen und das
   exakte PASS-Image nach der bestehenden Projektregel ausliefern.

Dieser Audit hat ausschließlich neue Berichte/Nachweise und einen Verweis im
Regelregister geschrieben. Keine Anwendungsimplementierung, Kampagnenzustände
oder Nutzerdaten geändert; kein Deployment ausgelöst. Die genannten Restfehler
sind daher weiterhin im geprüften Arbeits- und Produktionsstand vorhanden.
Keine prozentuale Vollständigkeit: Die Kriterien haben unterschiedliche
Gewichte, und nicht jeder Laufzeitpfad wurde erneut ausgeführt.
