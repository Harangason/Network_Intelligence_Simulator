# Vom Nutzer pausiert — 2026-10-11

FORTGESETZT: Der Nutzer hat anschließend „weiter“ beauftragt. Aktiver neuer Lauf:
backend/test-output/release-gates/delivery-aabc332ced9f/5a23ab7e250c/receipt.json.
Der historische Pausenstand unten bleibt als Unterbrechungsnachweis erhalten.

Nutzer: „mach mal pause ich will codex updaten und neustarten“.
Der laufende Release-Test wurde unterbrochen. Keine Produktivübernahme erfolgte.
EIP bleibt entsprechend ausdrücklicher Nutzerentscheidung ohne Deployment.

## Erledigter Stand

- Safety-/Normprofile, kanonische SafetyRequirements, konservative technische Prüfbelege und NIS-Quellenverzeichnis umgesetzt.
- EIP-Import im Quellcode umgesetzt und lokal geprüft; EIP NICHT produktiv übernehmen.
- Voller vorheriger Backend-Lauf: 21792 Tests und 56 Subtests bestanden, 2 übersprungen.
- Frontend: 605 Tests bestanden, TypeScript und Build bestanden.
- Vorheriger Browserlauf: 108/109 bestanden. Ein veralteter Quellenverzeichnis-Selektor erwartete „Name Bustyp“ statt der bewusst eingeführten Spalte „Technologie / Normbereich“.
- Dieser Selektor wurde ohne Abschwächung der Sortier-/Such-/Projekt-/Rechteprüfungen korrigiert. Alle vier Quellenverzeichnis-Fälle bestanden danach gegen das unveränderte Image (source-label-browser.log).
- Die diagnostische PREPARED-Instanz 83ce1adf2b22 wurde anschließend vollständig entfernt.

## Unterbrochener aktueller Lauf

Receipt: backend/test-output/release-gates/delivery-41d256f97324/446d5f064d03/receipt.json.
Speicher-, TypeScript- und 605 Frontend-Tests bestanden; Backend während Nutzerpause noch nicht abgeschlossen. Browser und HTTP wurden in diesem Lauf nicht erreicht.
Der Lauf ist kein PASS und berechtigt nicht zum Deployment.

## Fortsetzung ausschließlich nach Nutzerauftrag

1. Keine neue Build-/Image-Löschung erforderlich: wiederverwendbares Image
   `sha256:d41ebaf9cc8f94605d382946b49b01db0fddb4b3c536bc5e0859984f1caec83b`
   (`networkis:candidate-e7cc98f3e6fb`). Bestehender FAIL-Receipt für dessen Wiederverwendung:
   backend/test-output/release-gates/delivery-b37a5c6cc165/e7cc98f3e6fb/receipt.json.
2. Erwarteter Source-SHA: 578b113c9473eb7f8da425d31833d0de5486e39e1574907ac1697fecdbb48471;
   Git-Basis ef07cf7fc1def14234f8ea0ec1fcebfec23d391c. Nicht committen oder andere Änderungen überschreiben.
3. `backend/.venv/Scripts/python.exe scripts/release-and-deploy.py` erneut ausführen.
   Vollständiges Gate unverändert; genaue Image-Übernahme nur mit vollständigem PASS.
   Gesamte Browserlogs auf Fehler prüfen, nicht nur letzte erfolgreiche Zeilen.
4. Nach Deployment `verify_delivered.py --receipt <echter PASS>` aus diesem Workload-Verzeichnis ausführen.
   GET-only prüfen, keine Produktiv-Testdaten erstellen.
5. `finish_delivery_evidence.py --receipt <echter PASS> --delivery-log <neues erfolgreiches Log>`
   erst nach echter Übernahme und production-functional.json ausführen.
   Required Outcomes und Completion-Guard ehrlich aktualisieren; EIP-NEIN erhalten.
6. NIS-UI auf /studio/intelligence und /sources mit Projekt
   20261009072206008-4bb505f1 tatsächlich ansehen. Bei Chat-Links immer localhost UND
   http://192.168.178.10:13500 mit identischem Pfad/Projekt nennen.

Produktion bei Pause weiterhin altes Image:
sha256:ebba6b6c79f448b7ad6736b461098310da056b1f951cf873f306f131239e5ba1.
Kein Worker wurde für diesen Lauf pausiert. Die freigegebenen alten Fehlversuchs-Images
ba52fd62fb41 und 1d8155ff129c wurden bereits auditiert entfernt; Archive bleiben erhalten.
Weitere Images nicht aufgrund dieser bereits verbrauchten Freigaben entfernen.
