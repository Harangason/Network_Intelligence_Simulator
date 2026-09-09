"""Explicit project-scoped port repair; --apply is only for an authorized project."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.agent_core.api.tool_contract import Permission
from backend.engineering.agent_tools import model, proposal_service
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.engineering.physical_ports import create_physical_port_repair_proposal, materialize_physical_ports, topology_port_findings
from backend.engineering.db import close_pool

parser = argparse.ArgumentParser()
parser.add_argument('--project', required=True)
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()
authority = ToolAuthority(args.project, 'audit-port-migration')


def scoped(operation):
    result = execute(authority, 'physical_port_migration', Permission.READ_MODEL, {}, lambda _: operation())
    if not result.success:
        raise RuntimeError(result.model_dump_json())
    return result.data


try:
    def preview():
        snapshot = model.model()
        before = topology_port_findings(snapshot['topology'], snapshot['hardware'], snapshot['hardware-interfaces'])
        topology, changes = materialize_physical_ports(snapshot['topology'], snapshot['hardware'], snapshot['hardware-interfaces'], model.networks(),
            routes=snapshot['routing'], messages=snapshot['messages'])
        return {'project_id': args.project, 'before_findings': dict(Counter(row['code'] for row in before)),
                'routing_count': len(snapshot['routing']), 'valid_routing_count': sum(bool((row.get('validation') or {}).get('valid')) for row in snapshot['routing']),
                'changes': dict(Counter(row.get('action', 'CREATE') + ' ' + row['object_type'] for row in changes)),
                'node_count': len(topology['nodes']), 'port_count': sum(len(node['ports']) for node in topology['nodes']),
                'edge_count': len(topology['edges']), 'physical_networks': len({edge['physicalNetworkId'] for edge in topology['edges']})}
    print(json.dumps(scoped(preview), ensure_ascii=False))
    if args.apply:
        proposal = scoped(create_physical_port_repair_proposal)
        print(json.dumps({key: proposal.get(key) for key in ('proposal_id', 'status', 'validation_result')}, ensure_ascii=False))
        if proposal['status'] != 'UNCHANGED':
            assert proposal['status'] == 'VALIDATED', proposal['validation_result']
            scoped(lambda: proposal_service.review(proposal['proposal_id'], revision=proposal['revision'], decision='approve', actor=authority.actor, trace_id=uuid4().hex))
            applied = scoped(lambda: proposal_service.apply(proposal['proposal_id'], actor=authority.actor, trace_id=uuid4().hex))
            assert applied['status'] == 'APPLIED', applied
            print(json.dumps({'status': applied['status'], 'canonical_count': len(applied['canonical_ids'])}))
            print(json.dumps(scoped(preview), ensure_ascii=False))
            print(json.dumps(scoped(create_physical_port_repair_proposal), ensure_ascii=False))
finally:
    close_pool()
