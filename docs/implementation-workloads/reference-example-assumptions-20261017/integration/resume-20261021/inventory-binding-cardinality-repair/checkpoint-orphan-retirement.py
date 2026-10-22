"""Preserve the pre-build rejection and the sole running archival operation."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


result = read(OUT / 'candidate-prepare-result.json')
assert result['exit_code'] == 1
assert 'Retained test resources exist without containers' in (OUT / 'candidate-prepare.log').read_text(encoding='utf-8')
for name in ('candidate-prepare-freeze.json', 'candidate-prepare-result.json', 'candidate-prepare.log'):
    assert (OUT / name).read_bytes() == (OUT / 'prepare-attempt-57322' / name).read_bytes()
inventory = read(OUT / 'retire-orphan-resources/inventory.json')
now = datetime.now(timezone.utc).isoformat()
record = {'at_utc': now, 'status': 'ORPHAN_RESOURCE_ARCHIVAL_ACTIVE', 'session': 60762,
          'operator': str(OUT / 'retire_orphan_resources.py'), 'driver_process_ids': [44364, 62812],
          'networks': len(inventory['resources']['network']), 'volumes': len(inventory['resources']['volume']),
          'inventory': ref(OUT / 'retire-orphan-resources/inventory.json'),
          'prepare_session': 57322, 'prepare_exit_code': 1, 'prepare_process_ended': True,
          'prepare_rejection': 'Retained test resources exist without containers; no new build or image.',
          'prepare_evidence': [ref(OUT / 'prepare-attempt-57322' / name) for name in ('candidate-prepare-freeze.json', 'candidate-prepare-result.json', 'candidate-prepare.log')],
          'scope': 'Archive all exact unused disposable runtime volumes and their member hashes before any single-resource removal; preserve every image, original receipt, production and unrelated resource.',
          'no_active_inference_or_tests': True,
          'terminal_evidence_required': 'retire-orphan-resources/retirement.json + normal tool exit0 and actual process end',
          'next': 'Pause monitor after60762 actually ends. Verify exact retirement/backup evidence and protected identities. Preserve57322 attempt. Remove only its archived stale result marker before one fresh normal prepare_candidate.py; never duplicate a process/build. Then normal source-only transfer, actual both original workflows/models/ALL simulations and full exact-image gate/deployment.'}
write(OUT / 'checkpoint-orphan-retirement.json', record)
for path in (OUT / 'checkpoint.json', OUT.parent / 'checkpoint.json'):
    cp = read(path)
    cp.update(at_utc=now, status=record['status'], active_test_session=None, active_native_session=None,
              preparation_session=None, preparation_exit_code=1, active_operator_session=60762,
              orphan_retirement=ref(OUT / 'checkpoint-orphan-retirement.json'),
              next=record['next'],
              continuation_watch={'id':'nis-nach-fahrzeugpr-fung-fortsetzen','status':'ACTIVE_ONLY_ORPHAN_ARCHIVAL_60762'})
    write(path, cp)
path = OUT / 'workload.json'
work = read(path)
work.update(status=record['status'], orphan_retirement=ref(OUT / 'checkpoint-orphan-retirement.json'))
write(path, work)
note = f'''## Aktueller Fortsetzungspunkt: Sicherung verwaister Testressourcen60762

103+155=258 verschiedene gezielte Fälle aus zwei Läufen bestanden; beide
vollständigen Originalabnahmen/Modelle/ALL-Simulationen und volle Lieferung offen.
Die Hostbereinigung und38 Hosttoolprüfungen sind abgeschlossen. Der eigene6d6-
Teststack ist vollständig gesichert und exakt stillgelegt, Image/Receipt erhalten.
Verification wurde ohne App-/Gitänderung nachvollziehbar auf6a937cf1717f gebunden.

Die anschließende normale Vorbereitung57322 endete mit Exit1 vor jedem Build:
Die neue Schutzprüfung erkannte weitere verwaiste Ressourcen ohne Container.
Alle drei Dateien der Vorbereitung sind unverändert in prepare-attempt-57322
gesichert. Keine neue61c-Kandidatenimageidentität und keinPREPARED/PASS behaupten.

Jetzt läuft ausschließlich Session60762, retire_orphan_resources.py:
{record['volumes']} exakt inventarisierte unbenutzte disposable-Testvolumes und
{record['networks']} leere Testnetzwerke. Alle Volumes werden erst vollständig
aufF archiviert und pro Datei gehasht; vor jeder Einzelentfernung erneut alle
laufenden/gestoppten Referenzen, Identität/Erstellzeit, Labels und Schutzobjekte
prüfen. Keine Images oder fremden Ressourcen werden entfernt. Der Operator
hält die kanonische Gatesperre; kein zweiter Archivierer/Test/Build/Originalrequest.
Fortschritt, geringeCPU oder fehlender Toolhandle beweisen kein Ende.

Zuerst kompakt tatsächlichen Prozess60762 und retire-orphan-resources/retirement.json
prüfen. Terminaler Beleg, tatsächliches Prozessende und normaler Exit müssen passen.
Bei normalem Ende Monitor vor Folgearbeit pausieren. Bei Fehler zuerst tatsächliche
Teiloperationen/Archive/Identitäten abgleichen, keinen unkontrollierten Neustart.
Details und Hashbelege: checkpoint-orphan-retirement.json.

Nach geprüftem Ende:57322-Versuch erhalten, nur dessen bereits archivierten
alten candidate-prepare-result.json-Marker entfernen und einmal die bestehende
prepare_candidate.py normal aufrufen, falls kein neuer Prozess/Output besteht.
Kein neuer Outputpfad, Developmentbase oder Umgehen der Schutzprüfung.
Danach der bekannte Source-only-API-Transfer auf das tatsächliche neue Receipt,
16Antwort-/2Importrequesthashes und tatsächliche36f-Intakeherkunft, frische EIP/
Provider-/Produktqueueprüfung und echte neue native Originaloperationen.
Alle15Outcomes/15Validations und beide vollständigen Originale bleiben Pflicht;
erst vollständige Modelle/ALL-Simulationen, vollständiges finales Releasegate
und exakt getestete produktive Übernahme, dann Abschluss und Automationen löschen.
Produktion3792 enthält die neuen Korrekturen weiterhin nicht.

'''
for path in (OUT / 'NEXT.md', OUT / 'REPORT.md', OUT.parents[2] / 'TODO.md'):
    path.write_text(note + path.read_text(encoding='utf-8'), encoding='utf-8')
print(json.dumps({'status':record['status'],'session':60762,'volumes':record['volumes'],'networks':record['networks']}))
