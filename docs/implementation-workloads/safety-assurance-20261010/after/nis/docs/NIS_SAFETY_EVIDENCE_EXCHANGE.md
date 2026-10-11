# Sicherheitsanforderungen und NIS/EIP-Prüfbelege

Stand: 2026-10-10. Implementierungsvertrag für `nis.safety-evidence.v1`.

## Geltungsbereich

NIS prüft ausdrücklich konfigurierte technische Kommunikations- und
Reaktionskriterien. EIP verknüpft diese Prüfbelege mit kanonischen Core-Quellen und
einem unabhängigen Review. Beide behalten ihre eigene Projektdatenbank.
ISO 26262, UN R155 (Cybersecurity/CSMS) und UN R156 (Software-Updates/SUMS) sind
getrennte Norm-/Regelungsprofile; eine Transportprüfung beweist keine vollständige
Lebenszyklus-, Managementsystem- oder Typgenehmigungskonformität.

## Kanonische Anforderung

`SafetyRequirement` nutzt in NIS die vorhandenen Governance-Spalten,
Versionshistorie, Relationen, Projektgrenzen und CAS-Updates. Die Anforderung
gehört zu einer kanonischen Function; die zugeordneten Routen müssen einen
Endpunkt auf deren Hardware haben. Jede Änderung invalidiert nachgelagerte
Workflow-Belege. Die Anforderung wird im Simulationsmodell eingefroren.

Die Konfiguration enthält:

- `profile`: standard, edition, domain, applicability, reason sowie optionale
  clause_refs und work_product_refs. Ausgabe/Änderungsserie und Anwendbarkeit
  sind ausdrücklich fachlich festzulegen; es gibt keine automatische ASIL-Zuweisung.
- `hazard_ref`, `safety_goal_ref`, `route_ids` (kanonische UUIDs).
- `integrity` optional: model, level, decision_ref. Dies ist eine referenzierte
  fachliche Entscheidung, keine vom Simulator erzeugte Einstufung.
- `criteria`: deadline_ms, freshness_ms, required_protections und fault_cases.
- `eip` optional: project_id, requirement_ref, source_revisions. Für EIP-Import
  müssen originale Core-SafetyRequirement-Revisionen ausdrücklich zugeordnet sein.

Profile dürfen weitere Branchenstandards benennen. Automotive wird weder
automatisch gewählt noch auf Industrie-/Robotikprojekte übertragen.

## Technische Prüfung

E2E-Zeit und Datenalter kommen aus dem vorhandenen gemeinsamen
`build_e2e_transactions`-Kalkulator. Empfängerakzeptanz, vollständige
Transportsegmente und sämtliche Fanout-Ziele brauchen Belege. Ein explizit
verlangter Schutzmechanismus benötigt einen receiver-seitigen `protection_checks`
Eintrag (`PASS`/`FAIL`), etwa CRC, Sequence Counter oder Data ID.

Jeder konfigurierte Fehlerfall hat eine eindeutige Fall-ID, Fehlertyp, eine
Erkennungsfrist, FTTI, einen erwarteten physischen sicheren Zustand und die
kanonische Hardware-ID des erwarteten Reaktionsempfängers (`receiver_id`).
`SAFETY_FAULT`, `SAFETY_DETECTION`, `SAFETY_REACTION` brauchen:

- event_id, safety_requirement_id, fault_case_id, fault_occurrence_id, receiver_id;
- eine endliche nicht negative time_s und dieselbe time_basis;
- detection/reaction: caused_by_event_id auf das originale Fehlerereignis;
- reaction: physical_state_observed=true und observed_state.

Mehrdeutige, fehlende oder unkorrelierte Belege ergeben NOT_EVALUATED. Ein
allgemeines Signal-Label SAFE_STATE oder EMERGENCY_STOP wird nicht als physischer
Reaktionsbeweis verwendet. Fehlende Mess-/Reaktionsinstrumentierung bleibt offen;
der Adapter erzeugt solche Messdaten nicht künstlich. Ein PASS betrifft nur den
ausdrücklich definierten technischen Prüfumfang und die vorhandenen Stichproben.

Preflight prüft die strukturellen Referenzen, getrennt von Sicherheitsfreigaben.
Das Ergebnis weist `safety_release_approved=false` aus. Normative Vollständigkeit
bleibt NOT_EVALUATED, auch wenn einzelne technische Kriterien PASS erreichen.

## Übergabe und Review

In NIS unter Intelligence Anforderungen erfassen und nach einem neuen Lauf
„Belege für EIP exportieren“ verwenden. Der Server exportiert den eingefrorenen
Bericht mit NIS-Projekt, Snapshot/Job, Modell-/Anforderungsrevisionen,
Prüfregelversion und SHA-256 des kanonischen JSON-Payloads. Schlüssel werden
sortiert, UTF-8 verwendet und ganzzahlige Float-Werte vor dem Hash als Integer
normalisiert, damit Browser-JSON (z. B. 2.0 → 2) denselben Inhaltsnachweis behält.

Projektpakete sind Operator-Eingaben. Beim Import wird ein mitgelieferter
Sicherheitsbericht aus dem Snapshot entfernt und dieser als OUTDATED markiert;
andere historische Laufdaten bleiben erhalten. Sicherheitsbelege erfordern
einen neuen serverseitigen Lauf. Ein importiertes PASS wird nicht als neu
berechneter Nachweis weiterexportiert.

EIP Safety Center → NIS-EVIDENCE bzw. Security Center → NIS-SECURITY-EVIDENCE →
Analyse erstellen: originales NIS-Projekt,
Titel, Begründung und exportierten Bericht einfügen. Import prüft Inhaltshash,
Schema, vollständigen Lauf, Projektzuordnung, originale Core-Quellenrevisionen
und SafetyRequirement-/SecurityRequirement-Typ im jeweiligen Board. Der vorhandene AssuranceAnalysis-Draft speichert das
Originalpaket mit Audit, Idempotenz und CAS. Ein Hash beweist Integrität, keine
authentische Herkunft. Operator-Import und aktueller NIS-Modellstand bleiben
UNVERIFIED bis zur unabhängigen Prüfung. EIP-Quellenänderungen markieren den
Draft OUTDATED; NIS-Aktualität wird nicht aus einer alten Datei behauptet.

Die vorhandene unabhängige Review-Anforderung erteilt keine Releasefreigabe.
Normative Work Products, HARA/TARA-Entscheidungen, Test-/Evidence-Qualifikation
und regulatorische Nachweise müssen weiterhin fachlich geprüft werden.

## Quellenverzeichnis

Die bestehenden NIS-Quellen führen ISO 26262-1:2018, ISO 26262-5:2018 sowie die
offiziellen UN-R155-/R156-Referenzseiten als eigenen Normbereich. Transport-
TechnologyProfile und deren Lizenzgates bleiben eigenständig. Es werden nur
Bibliografie und Links veröffentlicht, keine Normtexte oder kopierten Tabellen.
Veröffentlichungsrechte bleiben UNRESOLVED, bis eine Rechtsprüfung vorliegt.
Die 2021-Regelungsreferenzen behaupten keine aktuelle anwendbare Änderungsserie.
