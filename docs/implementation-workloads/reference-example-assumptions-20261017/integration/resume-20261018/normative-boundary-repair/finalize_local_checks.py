"""Bind actual completed local checks; never claims native/release success."""
import hashlib
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[5]
BASE = OUT.parent
INTEGRATION = BASE.parent
at = datetime.now(timezone.utc).isoformat()

def ref(path):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'path': str(path.resolve()), 'sha256': digest}

cases = list(ET.parse(OUT / 'regressions.xml').getroot().iter('testcase'))
assert len(cases) == 318
assert all(case.find('failure') is None and case.find('error') is None and case.find('skipped') is None for case in cases)
log = (OUT / 'regressions.log').read_text(encoding='utf-8', errors='replace')
assert '318 passed, 1 warning' in log
owned = json.loads((OUT / 'final-joint-owned-manifest.json').read_text())
for relative, row in owned.items():
    assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == row['current'], ('Source changed', relative)
for filename in ['ollama-stdout.log', 'ollama-stderr.log']:
    shutil.copyfile(BASE / filename, OUT / ('actual-local-' + filename))
identity = json.loads((OUT / 'final-input-identity.json').read_text())
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text())['paths']['docker_cli']
production = subprocess.check_output([docker, 'inspect', 'NetworkIS', '--format', '{{.Image}}'], text=True).strip()
assert production == 'sha256:3792d2e086e43af616d9fb63fd371c352fe101db5136b84f381cd9999363785b'
health = {}
for name, endpoint in [('ready', '/api/ready'), ('build-info', '/api/build-info')]:
    with urlopen('http://127.0.0.1:13500' + endpoint, timeout=15) as response:
        raw = response.read()
    health[name] = json.loads(raw)
    (OUT / ('production-' + name + '.json')).write_bytes(raw)
assert health['ready']['status'] == 'ready'
assert health['build-info']['source_sha256'] != identity['source_sha256']
result = {'at_utc': at, 'status': 'LOCAL_REPAIR_VALIDATED_PENDING_SCOPED_CLEANUP_APPROVAL',
          'input_identity': identity, 'owned_files_verified': len(owned),
          'regressions': {'tests': 318, 'passed': 318, 'failed': 0, 'skipped': 0, 'warnings': 1,
                          'seconds': 855.30, 'exit_code': 0, 'sql_isolation': True,
                          'evidence': [ref(OUT / 'regressions.xml'), ref(OUT / 'regressions.log')]},
          'red': {'failed': 3, 'passed': 1, 'evidence': ref(OUT / 'red.xml')},
          'green': {'passed': 4, 'evidence': ref(OUT / 'green.xml')},
          'original_source_context_diagnosis': ref(OUT / 'original-source-grouping.json'),
          'production': {'image_id': production, 'ready': True, 'new_source_delivered': False},
          'actual_native_vehicle_result': 'All16 local Qwen sections completed; aggregate context validation failed before adoption/model creation.',
          'actual_native_robot_result': 'Full unchanged file uploaded; inference not started on superseded candidate.',
          'original_simulation_pass': False, 'full_release_pass': False, 'productive_delivery': False,
          'cleanup_decision': ref(OUT / 'cleanup-decision.json'),
          'archive_audit': ref(OUT / 'archive-review-d520e6b852e5/archive-audit.json'),
          'provider_logs': [ref(OUT / 'actual-local-ollama-stdout.log'), ref(OUT / 'actual-local-ollama-stderr.log')]}
(OUT / 'validation-summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
workload_path = OUT / 'workload.json'
workload = json.loads(workload_path.read_text(encoding='utf-8'))
workload.update(status='LOCAL_VALIDATED_DELIVERY_PENDING', validation_summary=ref(OUT / 'validation-summary.json'))
workload['delivery'] = {'decision': 'AUTHORIZED_PENDING_STORAGE_DECISION_AND_REQUIRED_CHECKS',
                        'complete_pass': False, 'production_changed': False}
workload_path.write_text(json.dumps(workload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
parent_path = INTEGRATION / 'workload.json'
parent = json.loads(parent_path.read_text(encoding='utf-8'))
parent['status'] = 'WAITING_FOR_USER'
parent['active_stage'] = {'stage': 'PENDING_EXACT_SECURED_TEST_RUNTIME_IMAGE_CLEANUP_APPROVAL', 'at_utc': at,
                          'tests_running': False, 'qwen_running': False, 'full_pass': False}
parent['current_validation'] = ref(OUT / 'validation-summary.json')
parent['joint_delivery']['current_source_sha256'] = identity['source_sha256']
parent['completion_status'] = 'General normative-context parser repair validated by318 isolated regressions including4 new cases. Both original native simulations and full productive release remain pending. Exact secured d520 test-runtime/image removal approval pending after auto-review rejected container removal; no container or image has been removed.'
parent_path.write_text(json.dumps(parent, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(OUT / 'TODO.md').write_text('''# Fortsetzen des gemeinsamen NIS-Auftrags

Der vollständige Auftrag ist weiterhin offen. Produktion enthält die neue Korrektur noch nicht.

- Ausstehende ausdrückliche Freigabe betrifft nur `nis-e2e-app-d520e6b852e5`, `nis-e2e-db-d520e6b852e5` und `networkis:candidate-d520e6b852e5`. Automatische Freigabeprüfung lehnte Containerentfernung wegen nicht ausdrücklich freigegebenem Testprojektverlust ab. Nicht umgehen. Die beiden Container und das Image sind unverändert vorhanden. Vollständige Sicherung: archive-review-d520e6b852e5/archive-audit.json; DB-Dump und beide Projekt-Exporte vorhanden, alle23 Imagebestandteile geprüft. Frühere43-Freigabe nicht übertragen.
- Nach der Antwort die exakte Freigabe sichern, alle unveränderlichen Image-/Archiv-/DB-Identitäten, sämtliche Receipt-/Containerreferenzen frisch prüfen. Nur genehmigte Testcontainer entfernen und danach genau das genehmigte Image mit `docker image rm --no-prune`. Kein Force, kein Prune; Produktion/Rückfall unverändert.
- Finaler Sourcefreeze `227a0c4214c90700d0a248869ad808f0b28b45dcdd9092e1c5cfb29479d8a41c`, HEAD `70f0c160bc4f08bd23437f6b3c175523d1e5859c`, Verification `de878f5954f4d31eb6131041bec9d85d643ca00529758bef9b33b83881aca409`. final-joint-owned-manifest.json sichert30 Dateien; nur2 wurden gegenübercf37 geändert. Alle318 Parser-/Referenztests bestanden isoliert, 4neue Fälle, 1bekanntePydantic-Warnung,855.30s,Exit0.
- Neuen Kandidaten über `backend/.venv/Scripts/python.exe scripts/run-release-gate.py --prepare --output backend/test-output/release-gates/joint-normative-originals-227a0c4214c9` normal bauen. Keinen Entwicklungsbasis-Shortcut. Tatsächlichen Tag/ImageID/BaseURL aus dem PREPARED-Beleg übernehmen. Noch kein FullPASS.
- Auf dem neuen finalen Kandidaten beide unveränderten Originaldateien in neuen echten Testprojekten über den normalen Browser-/Qwen-Weg prüfen. Alle neuen tatsächlichen IDs/Hashwerte sichern. Fahrzeug komplett.txt originalSHA86865975c689643d9b07ea73e21d68fa6f4a3a8770402ffb537dba2d7ecdf4d7 (19088 Zeichen); Robotdatei D_INDUSTRIAL_ROBOTICS_054_063.md originalSHA8fc201a55e8b0afeb7b708ac70abd0c72a7b25eb17d90fceca71d80a291f3cef (63705 Zeichen). Browser-Auftragswrapper und Originalhash separat prüfen. neu9.txt nur getrennteReferenz und bestätigteHumanergänzung separat. Keine manuellen Modelle/Verbindungen/Routen/Signale oder Quellenänderungen. Das Vorgängerbildd520 ist nach dem Normenkontextfehler superseded.
- Vollständige Dokumentbefunde, Originalzitate/Profilkontexte/REQs, NIS-Qwen-Referenzplan, normale validate/review/apply, Routing, Physik, Parameterherkunft, Capacity, Preflight und gespeicherte erfolgreiche Simulationen mit beobachteter Kommunikation beweisen. Fahrzeug: Kamera-Objektdaten zurFahrerassistenz und Entscheidungs-/Stellbefehlkette bisAktor. Robot: alle10Profile/110vollständigeREQ und Funktionen erhalten. Originalmodell nie manuell korrigieren. Hardware-/Zeitqualifikation nicht erfinden.
- Autorisierter Peer `Review selected comment items`01a139b0-6181-7642-9f5d-563105609790 hältSourcefreeze; Peer `Locate evaluation section limit`01a143e7-705b-74f0-b43c-f7b2a1f9c707 wartet actualACCEPTEDReferenceDesignRecord+kanonischenSavedModelExport+neueRobotID fürread-onlyVerifier. Keine parallelen Inferenz-/Gate-Läufe.
- Erst nach beiden echten Originalsimulationen vollständiges Gate mit exakt diesem Image `scripts/run-release-gate.py --image <actualImmutableImageID>` ausführen. Vollständigen PASS mit `scripts/release-and-deploy.py --receipt <actualPASSReceipt>` produktiv übernehmen. Laufende Imageidentität, Gesundheit und betroffene Funktion prüfen. Nachweise/Guards finalisieren, nur tatsächlichen Scope melden. Gegenwärtige Produktion3792d2e086e43af616d9fb63fd371c352fe101db5136b84f381cd9999363785b bleibt gesund und unverändert.
''', encoding='utf-8')
print(json.dumps({'status': result['status'], 'regressions_passed': 318, 'production_ready': True, 'production_delivered': False}), flush=True)
