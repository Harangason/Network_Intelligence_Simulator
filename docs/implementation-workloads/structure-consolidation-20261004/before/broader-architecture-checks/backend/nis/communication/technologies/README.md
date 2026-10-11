# Kommunikationstechnologien

Alle 125 vorhandenen Identitäten haben genau einen Ordner mit `profile.json`,
`definition.py` und einer README zum tatsächlichen Unterstützungsumfang.
CAN CC, CAN FD, Ethernet, LIN, I2C und SPI besitzen ausführbare Timingmodelle;
deren Framing, Scheduling und gegebenenfalls Arbitrierung liegen beim Eigentümer.
Andere Profile behalten ihre vorhandenen Fähigkeitszustände.

Neue Technologie: eigenen Ordner und explizites Profil gemäß TechnologyProfile
anlegen, ID in der bestehenden Katalogreihenfolge ergänzen, erforderliche Adapter
registrieren und Fähigkeiten erst nach belastbaren Nachweisen freigeben.
Keine zweite Registry und keine branchenabhängige Kopie anlegen.
`scripts/build/project-vocabulary.py` projiziert die Daten für das Frontend;
`test_structure_completion.py` prüft die Übereinstimmung.

Einstiege: [CAN](can/README.md), [CAN FD](can_fd/README.md),
[Ethernet](ethernet/README.md), [LIN](lin/README.md), [FlexRay](flexray/README.md).
Bestehende Altimporte bleiben durch `backend/nis/compatibility.json` kompatibel.
Verbraucher, Eigentümer und Entfernungskriterien stehen pro Pfad in
`docs/migrations/structure_mapping.csv`. Ein leerer interner Verbraucherscan
beweist keine Abwesenheit externer oder persistierter Verbraucher.
