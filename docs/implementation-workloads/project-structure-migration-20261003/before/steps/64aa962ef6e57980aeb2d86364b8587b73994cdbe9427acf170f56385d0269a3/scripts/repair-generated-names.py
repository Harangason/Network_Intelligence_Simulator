"""Preview or atomically rename generated labels; preserve all technical IDs."""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.engineering.db import RequestUnit, close_pool, flush_model_changes
from backend.engineering.project_context import activate_project, reset_project
from backend.engineering.repository import list_objects, update_object
from backend.engineering.naming import concise_name, concise_bus_names
from backend.engineering.workflow.service import WorkflowStatusService


def all_rows(kind):
    rows, offset = [], 0
    while True:
        batch = list_objects(kind, limit=250, offset=offset)
        rows.extend(batch)
        if len(batch) < 250:
            return rows
        offset += len(batch)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    token = activate_project(args.project)
    unit = RequestUnit(args.project)
    try:
        workflow = WorkflowStatusService(args.project)
        state = workflow.get()
        parameters, topology = deepcopy(state['parameters']), deepcopy(state['topology'])
        networks = parameters.get('networks') or []
        names = concise_bus_names(networks)
        network_changes = [{'id': n['id'], 'before': n.get('name'), 'after': names[n['id']]} for n in networks if n.get('name') != names[n['id']]]
        changes = []
        for kind in ('Function', 'Interface', 'Message', 'HardwareNetworkInterface'):
            rows = all_rows(kind)
            for row in rows:
                name = row['name']
                if kind == 'HardwareNetworkInterface':
                    name = names.get(row.get('network_ref'), name)
                elif str(row.get('source') or '').lower() == 'ai_generated':
                    name = concise_name(kind, name)
                if name != row['name']:
                    changes.append({'object_type': kind, 'id': str(row['id']), 'before': row['name'], 'after': name, 'version': row['version']})
        for network in networks:
            network['name'] = names[network['id']]
        for node in topology.get('nodes') or []:
            for port in node.get('ports') or []:
                if port.get('physicalNetworkId') in names:
                    port['physicalNetworkName'] = names[port['physicalNetworkId']]
                    port['name'] = names[port['physicalNetworkId']]
        for edge in topology.get('edges') or []:
            if edge.get('physicalNetworkId') in names:
                edge['physicalNetworkName'] = names[edge['physicalNetworkId']]
        if args.apply and (changes or network_changes):
            for change in changes:
                update_object(change['object_type'], change['id'], {'name': change['after'], 'expected_version': change['version'],
                    'actor': 'name-correction', 'change_summary': 'Generierten Namen gemäß Nutzerwunsch vereinfachen'})
            flush_model_changes(actor='name-correction', reason='Generierte Namen vereinfacht')
            if network_changes:
                workflow.save_parameters(parameters, actor='name-correction')
            if topology != state['topology']:
                workflow.save_topology(topology, actor='name-correction')
            unit.finish(True)
        report = {'project_id': args.project, 'applied': args.apply, 'counts': dict(Counter(x['object_type'] for x in changes)),
                  'changes': changes, 'network_changes': network_changes}
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'project': args.project, 'applied': args.apply, 'counts': report['counts'], 'network_names': len(network_changes)}))
    finally:
        unit.close()
        reset_project(token)
        close_pool()


if __name__ == '__main__':
    main()
