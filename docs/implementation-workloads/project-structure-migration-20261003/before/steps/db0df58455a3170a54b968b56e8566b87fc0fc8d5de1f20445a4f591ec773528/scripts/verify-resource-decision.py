"""Read-only assessment of the live tool's sizing decision; never applies it."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:13500')
    parser.add_argument('--project', required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    headers = {'X-Project-ID': args.project, 'Content-Type': 'application/json'}
    def request(path, payload=None):
        req = Request(args.base_url + path, headers=headers,
                      data=None if payload is None else json.dumps(payload).encode())
        with urlopen(req, timeout=60) as response:
            return json.load(response)
    def fingerprint(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
    before = request('/api/engineering/workflow')
    capacity_before = request('/api/engineering/capacity')
    decision = request('/api/engineering/capacity/optimize', {})
    after = request('/api/engineering/workflow')
    capacity_after = request('/api/engineering/capacity')
    assert decision['applied'] is False
    assert decision['resource_policy']['mode'] == 'AUTO_SIZE', decision
    assert fingerprint(before['topology']) == fingerprint(after['topology']), 'Tool assessment changed topology.'
    assert before['statuses'] == after['statuses'], 'Tool assessment changed workflow statuses.'
    assert capacity_before['id'] == capacity_after['id'], 'Tool assessment replaced the capacity snapshot.'
    branches = [item['branch_analysis'] for item in decision['proposals'] if item.get('branch_analysis')]
    split = [item for item in branches if item['decision'] == 'SPLIT_CURRENT_TECHNOLOGY']
    report = {'project': args.project, 'applied': False, 'topology_unchanged': True, 'workflow_unchanged': True,
              'capacity_snapshot_unchanged': True, 'resource_policy': decision['resource_policy'],
              'resource_allocation': decision['resource_allocation'], 'decision_rationale': decision['decision_rationale'],
              'plan_status': decision['plan_status'], 'analyzed_branches': len(branches),
              'same_technology_splits': len(split), 'new_segments_for_load': sum(item['additional_segments'] for item in split),
              'max_projected_split_load_percent': max((item['projected_max_load_percent'] for item in split), default=None),
              'unresolved_branches': [item['network_id'] for item in branches if item['decision'] == 'UNRESOLVED_CAPACITY_CONSTRAINT']}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
