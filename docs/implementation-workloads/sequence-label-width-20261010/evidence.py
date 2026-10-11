"""Capture only source/change evidence; does not run application tests."""
import argparse
import difflib
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FILES = ['frontend/src/features/simulation/ui/e2e-sequence-diagram.tsx', 'frontend/src/app/globals.css']
parser = argparse.ArgumentParser()
parser.add_argument('phase', choices=['before', 'after'])
phase = parser.parse_args().phase
def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
if phase == 'before':
    assert not (HERE / 'workload.json').exists(), 'Preserve existing before evidence.'
    for relative in FILES:
        target = HERE / 'before' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    note = HERE / 'source-findings.md'
    note.write_text('''# Markierte Sequenzbeschriftung

Projekt: 20261009072206008-4bb505f1; Simulation SEQUENCE.
Nutzer: Die lange Beschriftung „Ultraschall…“ überlagert Pfeile und Balken.
Quelle: bereitgestelltes Browserbild; keine neue Laufzeitprüfung durchgeführt.

Gemeinsamer Renderer: frontend/src/features/simulation/ui/e2e-sequence-diagram.tsx.
SequenceDiagramModel.events liefert route, technology, status und technische Details.
Der Renderer zentriert die Beschriftung bisher über der ganzen Pfeillänge und
begrenzt sie nur auf 64 Zeichen, unabhängig vom 184px-Teilnehmerabstand.
Bei mehreren Hops liegt die Mitte auf einer Lebenslinie; der Text bei y-8
überschneidet zudem den Aktivierungsbereich y-9 bis y+9.

Soll: sichtbare Beschriftung und technische Unterzeile innerhalb eines einzelnen
Zwischenraums, mit Abstand zu Lebenslinien, Aktivierungen und Pfeilen. Lange Texte
mit nativer Ellipse; volle Beschriftung weiterhin per Tooltip und Auswahl abrufbar.
Selbstnachrichten behalten ihre Schleife; ihre Beschriftung liegt rechts davon.
Dies gilt im bestehenden gemeinsamen Renderer für SIMULATED und OBSERVED.

Bestehende Abdeckung: frontend/e2e/studio-export-controls.spec.ts umfasst Auswahl,
transparente Hervorhebung und Aktivierungen. Pixelabhängige Beschriftungsbreite und
mehrere Teilnehmer/Selbstnachrichten sind darin noch nicht geprüft. Keine zweite
Registry und keine neuen Testdateien angelegt. Tests ausdrücklich vom Nutzer pausiert.
Produktivlieferung bleibt vom vollständigen PASS und dem offenen Image-Budget abhängig.
''', encoding='utf-8')
    work = {'goal_id': 'sequence-label-width-20261010', 'kind': 'repair', 'repository': str(ROOT),
        'modify_code': True, 'allow_repair': True,
        'revision_before': {relative: ref(ROOT / relative)['sha256'] for relative in FILES},
        'files_changed': FILES, 'before': [ref(HERE / 'before' / relative) for relative in FILES],
        'unresolved_decisions': [],
        'repair': {'owner': 'PROJECT_PRODUCT', 'root_cause': 'Character-only label limit and whole-arrow centering ignore lifeline spacing; label baseline intersects activation band.',
            'first_failing_layer': 'Shared SVG sequence renderer', 'reproduction': 'User annotated screenshot of Ultraschallverarbeitung route; current source geometry corroborates cause.',
            'evidence': [ref(note)], 'affected_files': FILES,
            'acceptance_criteria': ['Labels fit one lifeline gap without covering arrows or activations.', 'Full labels remain accessible.', 'Shared simulation/trace semantics remain intact.'],
            'targeted_tests': ['Deferred at explicit user instruction; do not execute tests until user resumes.'],
            'weaken_assertions_to_pass': False},
        'required_outcomes': ['bounded_shared_labels', 'full_label_accessibility', 'production_delivery'],
        'outcomes': {}, 'validation_requirements': ['release_gate'], 'validations': {},
        'parameters': {'run_tests': False, 'run_lint': False, 'run_validation': False, 'run_preflight': False},
        'delivery': {'decision': 'YES', 'authorization': 'Standing AGENTS production authorization after complete PASS; latest user instruction pauses tests.', 'status': 'PENDING_REQUIRED_GATE', 'target': 'Canonical NetworkIS'},
        'completion_status': 'IMPLEMENTING'}
else:
    work = json.loads((HERE / 'workload.json').read_text(encoding='utf-8'))
    patch = []
    for relative in FILES:
        target = HERE / 'after' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
        patch.extend(difflib.unified_diff((HERE / 'before' / relative).read_text(encoding='utf-8').splitlines(True),
            target.read_text(encoding='utf-8').splitlines(True), fromfile='before/' + relative, tofile='after/' + relative))
    diff = HERE / 'changes.patch'
    diff.write_text(''.join(patch), encoding='utf-8')
    work.update(after=[ref(HERE / 'after' / relative) for relative in FILES], diff=[ref(diff)],
        completion_status='IMPLEMENTED_NOT_TESTED_NOT_DEPLOYED',
        tests={'status': 'NOT_RUN_USER_REQUEST', 'reason': 'User explicitly paused all test execution for subsequent tasks.'},
        validations={'release_gate': {'status': 'NOT_RUN_USER_REQUEST', 'evidence': []}},
        remaining_findings=['No tests executed at user request.', 'Required complete release PASS and canonical deployment remain pending; image retention budget is still blocked.'])
(HERE / 'workload.json').write_text(json.dumps(work, indent=2), encoding='utf-8')
print(json.dumps({'phase': phase, 'status': work['completion_status'], 'tests_run': False}))
