from datetime import datetime, timezone
from pathlib import Path
import json

out = Path(__file__).parent
receipt = json.loads((out / 'release-pass-receipt.json').read_text(encoding='utf-8'))
production = json.loads((out / 'production-verification.json').read_text(encoding='utf-8'))
guard = json.loads((out / 'completion-guard.json').read_text(encoding='utf-8-sig'))
assert receipt['status'] == 'PASS' and production['status'] == 'PASSED' and guard['status'] == 'COMPLETED'
progress = json.loads((out / 'progress.json').read_text(encoding='utf-8'))
progress.update(at_utc=datetime.now(timezone.utc).isoformat(), status='SCOPED_CODE_DELIVERY_COMPLETE',
    passed_checks=receipt['checks'], current_check=None, current_production_contains_new_owner_fix=True,
    vehicle_model_and_simulation_completed=False, image_id=production['image_id'])
(out / 'progress.json').write_text(json.dumps(progress, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
paragraph = '''## Produktiver Abschluss dieses Teilauftrags – 17.10.2026

Der vollständige Release delivery-996d5008074f/952edd277e95 hat PASS. Storageprüfung,
Typecheck, 689 Frontendtests, 22.097 Backendtests (56 Subtests, 2 übersprungen),
Produktionsbuild, 119 Browserfälle sowie kleine und große HTTP-Gesamtprüfung
bestanden. Der große HTTP-Fall enthält einen tatsächlich abgeschlossenen
Simulationsjob im isolierten Release-Testprojekt; das ist keine Simulation der
Originaldatei „Fahrzeug komplett.txt“.

Image sha256:3792d2e086e43af616d9fb63fd371c352fe101db5136b84f381cd9999363785b
mit Quelle fd2d74b9c17b37aec51f92b377d037a54f9d9959808a06328097a9570fd3d7e9
wurde über release-and-deploy produktiv übernommen. Readiness, Imageidentität
und sämtliche 16 eingefrorenen Rohdateihashes sind geprüft. Gegen die laufenden
Produktmethoden bestätigt die unveränderte Fahrzeugquelle 23 belegte
Zuordnungen statt 22 und weiterhin 15 offene; beide Fahrdynamikbefunde bleiben
getrennte Quellenidentitäten mit demselben belegten CDC-Verantwortlichen.
Es wurden keine kanonischen Modelle oder Simulationen hierfür geschrieben.

production-verification.json, release-pass-receipt.json und completion-guard.json
belegen den Teilabschluss. Die erste Abschlussprüfung beanstandete falsch
verschachtelte delivery.checks; die unveränderten Nachweise wurden im korrekten
Schema eingetragen, die Wiederholungsprüfung bestand ohne Beanstandungen.

Die vollständigen Originaldatei-Läufe und die inzwischen ausdrücklich beauftragte
getrennte Referenzplanung für Beispielprojekte laufen unter
../reference-example-assumptions-20261017 weiter. Die HMI-Antwort und „neu 9.txt“
sind dafür gesicherte Nutzerergänzungen; fehlende Angaben sind jetzt als
prüfbare Referenzannahmen zu planen. Der nächste Schritt ist keine manuelle
Modellkorrektur. Dieser Teilabschluss stellt keinen Gesamt-PASS dar.

'''
report = out / 'REPORT.md'
report.write_text(paragraph + report.read_text(encoding='utf-8'), encoding='utf-8', newline='\n')
todo = out / 'TODO.md'
text = todo.read_text(encoding='utf-8').replace('- [ ] Vollarchiv', '- [x] Vollarchiv').replace('- [ ] Offiziellen vollständigen Release', '- [x] Offiziellen vollständigen Release')
todo.write_text(text, encoding='utf-8', newline='\n')
