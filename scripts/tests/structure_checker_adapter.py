"""Tool Checker adapter invoking existing NIS test entrypoints."""
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
