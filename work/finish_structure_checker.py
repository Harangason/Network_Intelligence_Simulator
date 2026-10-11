from finish_structure_owners import *

adapter = '''"""Tool Checker adapter invoking existing NIS test entrypoints."""
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

def execute(request):
    root = Path(request['project'])
    output = Path(request['output_directory'])
    step = request['step']
    report, log = output / 'architecture.xml', output / 'architecture.log'
    command = [str(root / 'backend/.venv/Scripts/python.exe'), str(root / 'scripts/run-isolated-tests.py'), '--',
               *step['pytest_targets'], '-q', '--junitxml=' + str(report)]
    with log.open('w', encoding='utf-8') as stream:
        result = subprocess.run(command, cwd=root, stdout=stream, stderr=subprocess.STDOUT, timeout=180)
    if result.returncode: raise RuntimeError('Architecture regression failed; see architecture.log')
    tree = ET.parse(report)
    suites = list(tree.getroot().iter('testsuite'))
    if not suites or any(int(s.get(key, 0)) for s in suites for key in ['failures', 'errors', 'skipped']):
        raise RuntimeError('Missing, failed or skipped regression evidence')
    if step.get('frontend_test'):
        node_log = output / 'frontend.log'
        with node_log.open('w', encoding='utf-8') as stream:
            node = subprocess.run(['node', '--experimental-strip-types', '--test', step['frontend_test']],
                                  cwd=root, stdout=stream, stderr=subprocess.STDOUT, timeout=60)
        if node.returncode: raise RuntimeError('Frontend regression failed')
    evidence = [{'ref':'xml', 'path':str(report), 'kind':'validation'}, {'ref':'log', 'path':str(log), 'kind':'log'}]
    checks = [dict(category=c['category'], name=c['name'], status='PASSED', evidence=['xml','log'],
                   **({'observed':False} if c['category']=='failure_conditions' else {})) for c in step['checks']]
    return {'status':'PASSED','llm_calls':0,'evidence':evidence,'observations':{'checks':checks}}

if __name__ == '__main__':
    print(json.dumps(execute(json.load(sys.stdin))))
'''
write('scripts/tests/structure_checker_adapter.py', adapter)
case_specs = [
    ('STRUCTURE_01', 'Registry projection and explicit unresolved technologies', ['test_frontend_technology_data_is_exact_backend_projection'], 'frontend/src/features/communication/lib/bus-technology.test.mjs'),
    ('STRUCTURE_02', 'Technology rules and arbitration have canonical owners', ['test_timing_dispatch_has_no_concrete_protocol_rules', 'test_runtime_arbitration_and_phy_rules_have_technology_owners'], None),
    ('STRUCTURE_03', 'Complete mapping and justified transition retention', ['test_mapping_covers_current_application_and_every_transition'], None),
    ('STRUCTURE_04', 'Independent architecture and mutation guards', ['test_timing_dispatch_has_no_concrete_protocol_rules'], None),
    ('STRUCTURE_05', 'All technology modules document actual support', ['test_technology_entry_documents_match_actual_capabilities'], None),
]
cases = []
for key, title, selectors, frontend in case_specs:
    criterion = title + ': every selected assertion passes without skips'
    failure = 'A selected assertion fails, errors, skips, or lacks stored evidence'
    targets = ['backend/tests/test_structure_completion.py::' + selector for selector in selectors]
    if key == 'STRUCTURE_04': targets.append('backend/tests/test_structure_architecture.py')
    step = dict(step_id='verify_contract', step_label=title, phase='engineering_execution', kind='adapter',
                adapter='nis-structure-regressions', timeout=240, precondition='Canonical source and installed backend/frontend test runtimes available; isolated Docker database only',
                pytest_targets=targets, checks=[{'category':'completion_criteria','name':criterion}, {'category':'failure_conditions','name':failure}])
    if frontend: step['frontend_test'] = frontend
    cases.append(dict(test_id=key,title=title,input='Current canonical source tree and real regression test entrypoints',
                      source_lines=[1,1], preconditions=[step['precondition']],mutating=False,browser_required=False,
                      completion_criteria=[criterion],failure_conditions=[failure],execution_plan=[step],overall_timeout=300))
source = dict(title='NIS structure migration responsibility regression suite',domain='engineering',
              purpose='Protect closed review findings R1-R5 independently of the historical EA campaign',
              global_rules=['No product database tests', 'No production writes', 'No LLM calls'],
              rule_files=[str(ROOT / 'AGENTS.md')],test_cases=cases)
write('docs/migrations/structure-checks.json', json.dumps(source, indent=2) + '\n')
path = '.tool-checker/state/config.json'
config = json.loads(read(path))
config['adapters']['nis-structure-regressions'] = dict(argv=[str(ROOT / 'backend/.venv/Scripts/python.exe'),str(ROOT / 'scripts/tests/structure_checker_adapter.py')], uses_llm=False,mutating=False)
write(path,json.dumps(config,indent=2) + '\n')
apply('checker-integration')
