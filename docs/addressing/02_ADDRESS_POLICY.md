# Address Policy

Pro Projekt konfiguriert `engineering_address_policies` den Vergabebereich, reservierte Bereiche, Wiederverwendung, Klassen-Addressability und die Strategie `LOWEST_FREE`, `SEQUENTIAL`, `DOMAIN_RANGE`, `DEVICE_CLASS_RANGE` oder `MANUAL`. Bereichsstrategien verwenden `domain_ranges` beziehungsweise `device_class_ranges` und fallen ohne passenden Eintrag auf den globalen Bereich zurück.

`GET/PATCH /api/engineering/addressing/policy` liest oder ändert die Policy. `NEVER_REUSE`/`NO_REUSE` schließt historisch vergebene Werte anhand des Address-Audits aus.
