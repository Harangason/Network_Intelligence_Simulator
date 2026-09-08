"""Positive real HTTP repair/review/apply/resimulation, QA projects only."""
import argparse
from copy import deepcopy
from http.cookiejar import CookieJar
import json
from pathlib import Path
import time
from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.error import HTTPError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--wizard-report', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--base-url', default='http://127.0.0.1:13500')
    args = parser.parse_args()
    project = json.loads(args.wizard_report.read_text(encoding='utf-8'))['project']
    assert project.startswith('astra-e2e-'), 'Never modify the user project'
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    evidence = []
    def request(path, payload=None, method=None, headers=None, expected=200):
        started = time.monotonic()
        req = Request(args.base_url + path, method=method or ('POST' if payload is not None else 'GET'),
            headers={'X-Project-ID': project, 'Content-Type': 'application/json', **(headers or {})},
            data=None if payload is None else json.dumps(payload).encode())
        try:
            response = opener.open(req, timeout=55)
        except HTTPError as error:
            response = error
        with response:
            result = json.load(response)
            evidence.append({'path': path, 'method': req.method, 'status': response.status, 'seconds': round(time.monotonic()-started, 3)})
            assert response.status == expected, (path, response.status, result)
        return result
    state = request('/api/engineering/workflow')
    parameters = deepcopy(state['parameters'])
    # Controlled QA bottleneck, set BEFORE both runs; same hardware speed,
    # payloads, cycle times, deadline, scenario and seed in the comparison.
    capacity = request('/api/engineering/capacity')
    assert len(capacity['results']['networks']) == 1 and len(capacity['results']['routes']) >= 2
    current = capacity['results']['networks'][0]['burst_load_percent']
    factor = 73.5 / current
    for container in [parameters, *(parameters.get('technology_defaults') or {}).values()]:
        for key in ('bitrate', 'arbitration_bitrate', 'data_bitrate'):
            if key in container:
                container[key] = max(1000, round(container[key] / factor))
        container.update(target_bus_load_percent=60, warning_threshold=20)
    request('/api/engineering/workflow/parameters', {'parameters': parameters}, method='PATCH')
    capacity = request('/api/engineering/capacity/calculate', {})
    print(json.dumps({'phase': 'bottleneck', 'networks': capacity['results']['networks']}), flush=True)
    config = {'duration_s': .12, 'seed': 42, 'deadline_ms': 5, 'warning_threshold': 20,
        'formats': ['universal-jsonl', 'universal-csv'], 'scenario': {'mode': 'NORMAL', 'faults': []}}
    def simulate():
        preflight = request('/api/engineering/preflight', {})
        assert preflight['status'] in {'COMPLETE', 'WARNING', 'APPROVED'}, preflight
        snapshot = request('/api/engineering/workflow/simulation-snapshots', {'configuration': config}, expected=201)
        job = request('/api/simulations', {'workflow_snapshot_id': snapshot['id'], 'workflow_managed': True, 'project_id': project}, expected=202)
        job_id = job['id']
        for _ in range(50):
            job = request('/api/simulations/' + job_id)
            if job['status'] in {'completed', 'failed', 'canceled'}:
                break
            time.sleep(.5)
        assert job['status'] == 'completed', job.get('error')
        result = request('/api/engineering/reasoning', {'job_id': job_id}, expected=201)
        return snapshot, job_id, result
    before_snapshot, before_job, before = simulate()
    assert any(a['id'] == 'capacity-repair' for a in before['recommended_actions']), before
    print(json.dumps({'phase': 'before', 'job': before_job, 'completion': before['completion_status'], 'gaps': before['data_gaps']}), flush=True)
    original_topology = request('/api/engineering/workflow')['topology']
    proposal = request('/api/engineering/reasoning/' + before['reasoning_id'] + '/proposal', {'action_id': 'capacity-repair'}, expected=201)
    proposal = proposal.get('data', proposal)
    assert proposal['status'] == 'VALIDATED', proposal
    assert request('/api/engineering/workflow')['topology'] == original_topology, 'Proposal must not apply itself'
    csrf = request('/api/engineering/agent/review-session')['csrf_token']
    intent = {'X-Review-CSRF': csrf, 'X-Human-Review': 'confirmed'}
    path = '/api/engineering/agent/proposals/' + proposal['proposal_id']
    request(path + '/apply?view=status', {'revision': proposal['revision']}, expected=403)
    approved = request(path + '/review', {'decision': 'approve', 'revision': proposal['revision']}, headers=intent)
    assert approved['data']['status'] == 'APPROVED'
    applied = request(path + '/apply?view=status', {'revision': approved['data']['revision']}, headers=intent)
    assert applied['success'] and applied['data']['status'] == 'APPLIED', applied
    after_topology = request('/api/engineering/workflow')['topology']
    assert after_topology != original_topology
    request('/api/engineering/capacity/calculate', {})
    after_snapshot, after_job, after = simulate()
    comparison = request('/api/engineering/reasoning/compare', {'before_reasoning_id': before['reasoning_id'], 'after_reasoning_id': after['reasoning_id']})
    assert comparison['status'] == 'IMPROVEMENT_VERIFIED_IN_WINDOW', comparison
    for key in ('seed', 'duration_s', 'scenario', 'deadline_ms'):
        assert before_snapshot['configuration'][key] == after_snapshot['configuration'][key]
    report = {'project': project, 'before_job': before_job, 'after_job': after_job, 'proposal': proposal['proposal_id'],
        'before_snapshot': before_snapshot['id'], 'after_snapshot': after_snapshot['id'],
        'proposal_did_not_mutate_model': True, 'unauthorized_apply_rejected': True, 'approved_apply': True,
        'topology_changed': True, 'same_experiment': True, 'comparison': comparison, 'http': evidence,
        'browser_url': args.base_url + f'/trace-analysis?project={project}&job={after_job}&view=root-cause'}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
