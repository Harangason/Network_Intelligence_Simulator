"""Read-only product evidence; no tests or SQL against the product database."""
import json
from pathlib import Path
from urllib.request import Request, urlopen
from hashlib import sha256

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).parent
PROJECT = '20261006112021387-b7939de0'
PROPOSAL = '4dfcaab5-6f2f-409a-ae3e-f8b82b617b03'
for name, path in {
    'parameters-before': '/workflow/parameters',
    'proposal-before': f'/agent/proposals/{PROPOSAL}',
    'workflow-before': '/workflow?view=summary',
    'conversation-before': '/agent/conversation',
}.items():
    try:
        with urlopen(Request('http://localhost:13500/api/engineering' + path,
                             headers={'X-Project-ID': PROJECT}), timeout=60) as response:
            value = json.load(response)
        (OUT / (name + '.json')).write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
        if name == 'proposal-before':
            p = value['data']
            print(name, p['status'], p['revision'], len(p['changes']), 'findings', len(p['validation_result']['findings']))
        elif name == 'parameters-before':
            print(name, value['project_id'], value['versions'])
        elif name == 'workflow-before':
            print(name, json.dumps(value.get('context', {}).get('agent_execution', {}), ensure_ascii=False)[:1800])
        else:
            print(name, list(value))
    except Exception as error:
        print(name, type(error).__name__, str(error))

workload_path = OUT / 'workload.json'
if not workload_path.exists():
    workload = {
        'goal_id': OUT.name, 'goal_type': 'PARAMETER_USABILITY_AND_PROPOSAL_RELEASE',
        'repository': str(ROOT), 'project_scope': PROJECT + ' / ' + PROPOSAL + '; all technology parameter forms',
        'requested_change': 'Meaningful simulation inputs, common parameters first with editable collapsed details; reliable save/reload and reviewed model apply.',
        'kind': 'repair', 'modify_code': True, 'allow_repair': True,
        'required_outcomes': ['meaningful_parameter_values', 'prioritized_parameter_ui', 'save_and_review_apply', 'production_delivery'],
        'constraints': ['TechnologyProfile SSOT', 'Project-only user values', 'Keep evidence gates and revision authority'],
        'forbidden_changes': ['Product database tests', 'Invented device/source identifiers', 'Assert success without durable apply', 'Weaken physical evidence gates'],
        'validation_requirements': ['targeted_regression', 'full_release_gate', 'production_verification'],
        'unresolved_decisions': [], 'files_changed': [], 'files_inspected': [],
        'revision_before': {}, 'completion_status': 'ANALYZING',
        'repair': {'owner': 'PROJECT_PRODUCT', 'first_failing_layer': 'Under diagnosis',
                   'root_cause': '', 'reproduction': 'User project: empty canonical model, VALIDATED 2114-change proposal and parameter saves at version 4; synthetic source identifiers in LIN form.',
                   'evidence': [], 'weaken_assertions_to_pass': False},
        'context': {'campaign_id': 'nis-ea-independent-20260924-run1', 'campaign_state': 'REPAIR_1_ACTIVE',
                    'independent_campaign_unchanged': True},
    }
    workload_path.write_text(json.dumps(workload, indent=2), encoding='utf-8')
