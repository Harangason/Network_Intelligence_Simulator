"""Record targeted results and the safely blocked host-tool transition."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent
PARENT = OUT.parent
WORK = OUT.parents[2]


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


spec = importlib.util.spec_from_file_location('nis_transition_identity', ROOT / 'scripts/release/release-and-deploy.py')
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
actual = owner.current_identity()
expected = read(OUT / 'current-input-identity.json')
assert actual[:2] == (expected['source_sha256'], expected['commit_id'])
results = [read(OUT / (name + '-result.json')) for name in ('reasoner-regressions', 'remaining-reference-regressions')]
assert [r['cases'] for r in results] == [103, 155]
assert all(r['exit_code'] == 0 for r in results)
now = datetime.now(timezone.utc).isoformat()
record = {
    'at_utc': now,
    'status': 'PREPARATION_STOPPED_BEFORE_BUILD_HOST_VERIFICATION_CHANGED',
    'session': 90140, 'exit_code': 1, 'process_ended': True,
    'observed_assertion_tuple': ['61c7649a933dc0fae72c85586bb07db43a4875ec3ed0fc09a97cca52050b89fc',
                                 '70f0c160bc4f08bd23437f6b3c175523d1e5859c',
                                 '6a937cf1717fd5e739801dcda34dea04f079221d1282c31cb3f1a8c1722f97ba'],
    'original_frozen_identity': expected,
    'fresh_identity': dict(zip(('source_sha256', 'commit_id', 'verification_sha256'), actual)),
    'application_and_commit_unchanged': True,
    'new_build_started': False,
    'targeted_cases': 258, 'targeted_runs': 2,
    'results': [ref(OUT / (name + '-result.json')) for name in ('reasoner-regressions', 'remaining-reference-regressions')],
    'aggregate': ref(OUT / 'targeted-reference-aggregate.json'),
    'concurrent_host_workload': str(ROOT / 'docs/implementation-workloads/test-stack-retention-20261021/workload.json'),
    'next': 'Wait for the existing host cleanup/tooling operation to complete. Verify its final evidence, frozen files and process end without duplicating cleanup/tests. Preserve old verification identity, reconcile new host-tool verification and archive/retire the exact obsolete 6d6 stack before one normal preparation. Never bypass the new gate lock or retained-stack bound.',
    'original_models_all_simulations_full_gate_delivery': 'PENDING',
}
write(OUT / 'candidate-prepare-identity-stop.json', record)
for path in (OUT / 'checkpoint.json', PARENT / 'checkpoint.json'):
    cp = read(path)
    cp.update(at_utc=now, status='TARGETED_258_PASS_WAITING_EXISTING_HOST_TRANSITION',
              active_test_session=None, active_native_session=None,
              preparation_session=None, preparation_exit_code=1,
              new_candidate_built=False, current_application_source_sha256=actual[0],
              current_verification_sha256=actual[2],
              host_transition=ref(OUT / 'candidate-prepare-identity-stop.json'),
              next=record['next'])
    cp['continuation_watch'] = {'id': 'nis-nach-fahrzeugpr-fung-fortsetzen',
                                'status': 'PAUSED_DURING_FOLLOWUP'}
    write(path, cp)
work = read(OUT / 'workload.json')
work.update(status='TARGETED_PASS_WAITING_EXISTING_HOST_TRANSITION', host_transition=ref(OUT / 'candidate-prepare-identity-stop.json'))
write(OUT / 'workload.json', work)
note = '''## Aktueller Stand nach den gezielten Regressionen

103 Reasonerfälle (Session63080) und155 angrenzende Referenzfälle
(Session64221) bestanden jeweils mit Exit0 und finalem XML;258 verschiedene
Fälle in zwei getrennten Läufen. Beide Originalabnahmen, gespeicherte Modelle,
ALL-Simulationen und vollständiges Releasegate sind weiter offen.

Die normale Vorbereitung90140 endete mit Exit1 vor jedem Build: Die
Anwendungsquelle61c7649a933d und HEAD70f sind unverändert, die parallel
überarbeiteten Host-Releasewerkzeuge änderten jedoch die Verification-Identität.
Der strikte Freeze hat das korrekt erkannt. Der ursprüngliche Freeze bleibt
erhalten. Keine neue Kandidatenvorbereitung, doppelte Bereinigung oder Umgehung
der neuen Stack-/Sperrregeln. Zuerst die laufende, getrennt belegte Bereinigung
test-stack-retention-20261021 abschließen lassen und deren Ergebnis prüfen;
danach den überholten6d6-Teststack vollständig sichern und exakt stilllegen,
die Host-Verification nachvollziehbar neu einfrieren und einmal normal vorbereiten.

Die konkrete75ccb-Entfernung ist bereits vollständig belegt und abgeschlossen;
sie ist keine ausstehende Nutzerentscheidung. Produktion3792 enthält die neue
Korrektur weiterhin nicht. Details: candidate-prepare-identity-stop.json.

'''
for path in (OUT / 'REPORT.md', OUT / 'NEXT.md'):
    previous = path.read_text(encoding='utf-8')
    path.write_text(note + previous, encoding='utf-8')
todo = WORK / 'TODO.md'
todo.write_text(note + todo.read_text(encoding='utf-8'), encoding='utf-8')
print(json.dumps({'status': record['status'], 'identity': actual, 'targeted_cases_in_two_runs': 258}))
