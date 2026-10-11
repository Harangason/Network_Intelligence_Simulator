import hashlib, json, re, sys
from pathlib import Path

out = Path(__file__).parent
root = out.parents[2]
receipt_path = (root/sys.argv[1]).resolve()
receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
live_path = out/'live-after.json'
live = json.loads(live_path.read_text(encoding='utf-8'))
assert receipt['status'] == 'PASS'
assert all(check['exit_code'] == 0 for check in receipt['checks'])
assert live['build']['source_sha256'] == receipt['release']['source_sha256']
assert live['health']['status'] == 'ready'
assert live['proposal_status'] == 'VALIDATED'
assert live['canonical_count'] == 0
assert live['device_hint_severities'] == ['INFO']
backend_log = (receipt_path.parent/'backend-tests.log').read_text(encoding='utf-8')
frontend_log = (receipt_path.parent/'frontend-tests.log').read_text(encoding='utf-8')
browser = json.loads((receipt_path.parent/'browser.json').read_text(encoding='utf-8'))
assert browser['stats']['unexpected'] == 0 and not browser.get('errors')
performance_browser = json.loads((out/'performance-browser.json').read_text(encoding='utf-8'))
assert performance_browser['stats']['expected'] == 4
assert performance_browser['stats']['unexpected'] == 0 and not performance_browser.get('errors')
catalog_browser = json.loads((out/'catalog-browser.json').read_text(encoding='utf-8'))
assert catalog_browser['stats']['expected'] == 8
assert catalog_browser['stats']['unexpected'] == 0 and not catalog_browser.get('errors')
assert catalog_browser['_evidence']['source_sha256'] == receipt['release']['source_sha256']
assert catalog_browser['_evidence']['image_id'] == receipt['image_id']
assert Path(catalog_browser['_evidence']['receipt']['path']) == receipt_path
assert '# pass 18' in (out/'restore-catalog-targeted.log').read_text(encoding='utf-8')
assert '243 passed' in (out/'schema-role-targeted.log').read_text(encoding='utf-8')
assert (out/'schema-role-equivalence-current.log').read_text(encoding='utf-8').count('"identical_results": true') == 3
assert '299 passed' in (out/'full-request-targeted.log').read_text(encoding='utf-8')
assert (out/'full-request-review-equivalence.log').read_text(encoding='utf-8').count('"identical_results": true') == 3
assert '195 passed' in (out/'routing-return-targeted.log').read_text(encoding='utf-8')
assert '181 passed' in (out/'topology-native-targeted.log').read_text(encoding='utf-8')
topology_equivalence = (out/'topology-native-equivalence.log').read_text(encoding='utf-8')
assert topology_equivalence.count('"identical_results": true') == 3
assert '"native_lin_scenarios": 30, "identical_derivations": true' in topology_equivalence
assert '# pass 51' in (out/'review-suite-clock-targeted.log').read_text(encoding='utf-8')
assert '174 passed' in (out/'native-consistency-regression.log').read_text(encoding='utf-8')
assert '1 passed' in (out/'saved-current-graph-regression.log').read_text(encoding='utf-8')
assert '174 passed' in (out/'sizing-only-first-regression.log').read_text(encoding='utf-8')
qualification_targeted = (out/'qualification-stress-targeted.log').read_text(encoding='utf-8')
assert re.search(r'\d+ passed', qualification_targeted)
failure_count = r'\b[1-9]\d* (?:failed|errors?)\b'
assert not re.search(failure_count, '0 errors. 0 failed')
assert all(re.search(failure_count, text) for text in ('1 error', '13 errors', '100 failed'))
assert not re.search(failure_count, qualification_targeted)
assert '48 passed' in (out/'simulation-load-targeted.log').read_text(encoding='utf-8')
assert '# pass 12' in (out/'parent-review-transfer-targeted.log').read_text(encoding='utf-8')
assert not (out/'parent-review-transfer-typecheck.log').read_text(encoding='utf-8').strip()
assert '72 passed' in (out/'duration-intent-backend.log').read_text(encoding='utf-8')
assert '# pass 6' in (out/'duration-intent-frontend.log').read_text(encoding='utf-8')
assert not (out/'duration-intent-typecheck.log').read_text(encoding='utf-8').strip()
duration_browser = json.loads((out/'duration-intent-browser.json').read_text(encoding='utf-8'))
assert duration_browser['stats']['expected'] == 2
assert duration_browser['stats']['unexpected'] == 0 and not duration_browser.get('errors')
assert duration_browser['_evidence']['source_sha256'] == receipt['release']['source_sha256']
assert duration_browser['_evidence']['image_id'] == receipt['image_id']
assert Path(duration_browser['_evidence']['receipt']['path']) == receipt_path
polling_before = json.loads((out/'workflow-polling-before-result.json').read_text(encoding='utf-8'))
polling_after = json.loads((out/'workflow-polling-after-result.json').read_text(encoding='utf-8'))
assert polling_before['identical_results'] and polling_after['identical_results']
assert polling_before['state_sha256'] == polling_after['state_sha256']
assert (out/'workflow-polling-before-state.json').read_bytes() == (out/'workflow-polling-after-state.json').read_bytes()
assert '152 passed' in (out/'workflow-polling-regression.log').read_text(encoding='utf-8')
assert '1 passed' in (out/'workflow-polling-after.log').read_text(encoding='utf-8')
duration_replay = json.loads((out/'observation-frozen-replay.json').read_text(encoding='utf-8'))
assert duration_replay['statuses'] == {'PASS': 766, 'FAIL': 0, 'NOT_EVALUATED': 0}
assert duration_replay['communications_unchanged'] and duration_replay['max_events_unchanged']
assert duration_replay['coverage'] == 'DETACHED_FROZEN_TRANSPORT_REPLAY_NOT_COMPLETE_RELEASE'
native_diagnostic = json.loads((out/'native-preflight-diagnostic.json').read_text(encoding='utf-8'))
assert native_diagnostic[-1]['label'] == 'post_split_sized'
assert native_diagnostic[-1]['unresolved'] == [] and native_diagnostic[-1]['invalid_routes'] == []
assert '86 passed' in (out/'performance-targeted.log').read_text(encoding='utf-8')
assert '40 passed' in (out/'rate-cache-targeted.log').read_text(encoding='utf-8')
assert '42 passed' in (out/'startup-targeted.log').read_text(encoding='utf-8')
targeted = (out/'targeted.log').read_text(encoding='utf-8')
assert '155 passed' in targeted
def evidence(path):
    return {'path':str(path.resolve()), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
def passed(*paths):
    return {'status':'PASSED', 'evidence':[evidence(path) for path in paths]}
path = out/'workload.json'
work = json.loads(path.read_text(encoding='utf-8'))
for relative in work['files_changed']:
    assert (root/relative).read_bytes() == (out/'after'/relative).read_bytes(), relative
work['outcomes'] = {
    'wizard_continuity': passed(receipt_path, live_path),
    'saved_value_precedence': passed(out/'targeted.log', receipt_path, out/'live-before.json', live_path),
    'simulation_readiness_without_device_qualification': passed(out/'targeted.log', receipt_path, live_path),
    'production_delivery': passed(receipt_path, out/'delivery.log', live_path),
}
work['validations'] = {
    'targeted_regression': passed(out/'targeted.log',out/'frontend-targeted.log',out/'gate-repair-targeted.log',
        out/'performance-targeted.log',out/'rate-cache-targeted.log',out/'startup-targeted.log',out/'performance-browser.json',
        out/'restore-catalog-targeted.log',out/'schema-role-targeted.log',out/'schema-role-equivalence-current.log',
        out/'full-request-targeted.log',out/'full-request-review-equivalence.log',out/'routing-return-targeted.log',
        out/'topology-native-targeted.log',out/'topology-native-equivalence.log',out/'catalog-browser.json',
        out/'native-consistency-regression.log',out/'saved-current-graph-regression.log',out/'native-preflight-diagnostic.json',
        out/'sizing-only-first-regression.log',out/'qualification-stress-targeted.log',
        out/'simulation-load-targeted.log',out/'parent-review-transfer-targeted.log',out/'parent-review-transfer-typecheck.log',
        out/'duration-intent-backend.log',out/'duration-intent-frontend.log',out/'duration-intent-typecheck.log',
        out/'duration-intent-browser.json',out/'observation-frozen-replay.json',
        out/'workflow-polling-regression.log',out/'workflow-polling-after.log',
        out/'workflow-polling-before-result.json',out/'workflow-polling-after-result.json'),
    'full_release_gate': passed(receipt_path),
    'production_verification': passed(out/'delivery.log',live_path),
}
work['tests'] = {
    'targeted_backend':155,
    'gate_repair_backend':int(re.search(r'(\d+) passed',(out/'gate-repair-targeted.log').read_text(encoding='utf-8')).group(1)),
    'performance_targeted_backend':86,
    'rate_planning_backend':40,
    'server_startup_backend':42,
    'performance_browser':performance_browser['stats'],
    'restore_catalog_frontend':18,
    'schema_role_backend':243,
    'full_request_backend':299,
    'routing_return_backend':195,
    'topology_native_backend':181,
    'native_consistency_backend':174,
    'saved_current_graph_backend':1,
    'sizing_only_backend':174,
    'qualification_stress_backend':int(re.search(r'(\d+) passed',qualification_targeted).group(1)),
    'simulation_load_planning_backend':48,
    'parent_review_transfer_frontend':12,
    'duration_intent_backend':72,
    'duration_intent_frontend':6,
    'duration_intent_browser':duration_browser['stats'],
    'workflow_polling_backend':152,
    'workflow_polling_frozen_equivalence':polling_after['state_sha256'],
    'frozen_transport_replay':duration_replay['statuses'],
    'topology_native_equivalence':'120 groups, 640 findings, 120 rate plans and 30 LIN layouts identical',
    'catalog_browser':catalog_browser['stats'],
    'full_backend':int(re.search(r'(\d+) passed',backend_log).group(1)),
    'frontend':int(re.search(r'# tests (\d+)',frontend_log).group(1)),
    'browser':browser['stats'],
    'small_http':'PASSED', 'large_http':'PASSED',
}
work['delivery'].update(tested_version=receipt['image_id'],running_version=receipt['image_id'],checks={
    'release':passed(receipt_path), 'deployment':passed(out/'delivery.log'),
    'health':passed(live_path), 'functional':passed(live_path),
})
work['remaining_findings'] = []
work['repair']['status'] = 'VERIFIED'
work['completion_status'] = 'COMPLETED'
path.write_text(json.dumps(work,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'status':'COMPLETED', 'tests':work['tests'], 'image_id':receipt['image_id']},ensure_ascii=False))
