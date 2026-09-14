"""Canonical output projection. Retrying this module never replays model commands."""
from copy import deepcopy
from datetime import datetime, timezone
from backend.agent_core.api.input_output import AgentOutputEnvelope, VisualizationRequest
from .graph import ModelGraphService, digest
from .store import save_goal

VERSION = '1'


class OutputComposer:
    def compose(self, goal, graph):
        revision = goal.get('result_revision')
        if not revision or graph.revision != revision:
            raise ValueError('Ausgabestand gehört nicht zur aktuellen Modellrevision.')
        route_ids = set(goal.get('route_ids', []))
        routes = [r for r in graph.model.get('routing', []) if str(r['id']) in route_ids]
        if not route_ids or {str(r['id']) for r in routes} != route_ids:
            raise ValueError('Gespeicherte Routen fehlen im aktuellen Modell.')
        nodes, edges = {}, {}
        def node(ref):
            ref = str(ref)
            row = graph.objects.get(ref)
            if row is None:
                raise ValueError('Ein kanonisches Diagrammobjekt fehlt: ' + ref)
            from .typing import type_reference
            nodes[ref] = {'id': ref, 'label': str(row.get('name') or ref),
                          'object_type': type_reference(graph, ref).engineering_type or 'ModelObject'}
            return ref
        def edge(source, target, label, evidence):
            source, target = node(source), node(target)
            edges[(source, target, label)] = {'source': source, 'target': target, 'label': label, 'evidence_ref': evidence}
        for route in routes:
            rid = str(route['id'])
            for path in route.get('route', {}).get('physical_paths', []):
                ports = path.get('ports', [])
                for ref in ports:
                    port = graph.hni[str(ref)]
                    edge(port['hardware_node_id'], ref, 'Anschluss', rid)
                for left, right in zip(ports, ports[1:]):
                    a, b = graph.hni[str(left)], graph.hni[str(right)]
                    network = graph.networks.get(a.get('network_ref')) if a.get('network_ref') == b.get('network_ref') else None
                    if network:
                        edge(left, network['id'], 'sendet', rid)
                        edge(network['id'], right, 'empfängt', rid)
                    elif a['hardware_node_id'] == b['hardware_node_id']:
                        edge(left, right, 'Weiterleitung', rid)
                    else:
                        raise ValueError('Der physische Abschnitt hat keinen belegten Netzbezug.')
            if not route.get('route', {}).get('physical_paths'):
                raise ValueError('Der kanonische physische Pfad fehlt.')
        for ref in goal['desired_state']['target_objects']:
            if ref in graph.functions:
                edge(ref, graph.host(ref)['id'], 'läuft auf', ref)
        all_nodes = list(nodes.values())
        visible = all_nodes[:200]
        visible_ids = {item['id'] for item in visible}
        visible_edges = [item for item in edges.values() if item['source'] in visible_ids and item['target'] in visible_ids][:400]
        diagram = VisualizationRequest(visualization_type='NETWORK_DIAGRAM', purpose='Aktuelle Verbindung',
            source_revision=revision, nodes=visible, relationships=visible_edges, total_objects=len(all_nodes),
            truncated=len(all_nodes) > len(visible) or len(edges) > len(visible_edges))
        completion = goal.get('engineering_completion', goal.get('completion')) or {}
        evidence = {**(goal.get('connection_completion') or {}).get('evidence', {}), **completion.get('evidence', {})}
        rows = [[label, 'Nachgewiesen' if evidence.get(key) is True else 'Offen'] for key, label in [
            ('routing_valid', 'Routing'), ('capacity_valid', 'Kapazität'),
            ('timing_valid', 'Funktionales Timing'), ('preflight_valid', 'Preflight')]]
        for network in (goal.get('capacity') or {}).get('results', {}).get('networks', []):
            if str(network.get('network_id')) not in nodes:
                continue
            name = nodes[str(network['network_id'])]['label']
            load = network.get('average_load_percent', network.get('bus_load_percent'))
            rows.append([name + ' · Netzlast', f'{load:g} %' if isinstance(load, (float, int)) else 'Offen'])
            evaluation = network.get('evaluation') or {}
            schedule = evaluation.get('schedule') or {}
            status = schedule.get('status')
            rows.append([name + ' · Sendeplan', {'FEASIBLE_UNDER_ASSUMPTIONS': 'Unter Annahmen erfüllbar',
                'EMPTY': 'Kein Verkehr', 'NOT_APPLICABLE': 'Nicht anwendbar', 'FAIL': 'Nicht erfüllt',
                'UNVERIFIED': 'Nicht nachgewiesen'}.get(status, str(status or 'Offen'))])
        table = VisualizationRequest(visualization_type='TABLE', purpose='Getrennte Prüfnachweise',
            source_revision=revision, columns=['Prüfung', 'Ergebnis'], rows=rows[:200],
            total_objects=len(rows), truncated=len(rows) > 200)
        provenance = {'model_revision': revision, 'capability_version': VERSION,
            'created_at': datetime.now(timezone.utc).isoformat(), 'input_ref': goal.get('input_ref'),
            'validation_evidence': evidence, 'journal_ref': goal['workload_id']}
        result = []
        for kind, view in [('VISUALIZATION', diagram), ('VALIDATION', table)]:
            result.append(AgentOutputEnvelope(output_id=digest([goal['workload_id'], revision, kind, view.model_dump(), evidence]),
                output_type=kind, status='CURRENT', project_ref=graph.model['project_id'], run_ref=goal['workload_id'],
                content=view.purpose, affected_objects=sorted(nodes)[:500], evidence_refs=sorted(route_ids)[:500],
                visualization=view, validation={'status': completion.get('status', 'INCOMPLETE')},
                provenance=provenance).model_dump(mode='json', exclude_none=True))
        return result


def ensure_outputs(goal):
    """Run after canonical execution, outside its rollback block; safe on resume."""
    if not goal.get('result_revision') or not goal.get('route_ids'):
        return goal
    if goal['status'] not in {'COMPLETE', 'READY_FOR_REVIEW', 'INCOMPLETE', 'OUTPUT_PENDING', 'FOLLOWUP_PENDING', 'SIMULATION_RUNNING'}:
        return goal
    from .executor import journal
    try:
        graph = ModelGraphService.load()
        if graph.revision != goal['result_revision']:
            for output in goal.get('outputs', []):
                output['status'] = 'STALE'
            goal.update(status='PLAN_STALE', authorization=None, followup_authorization=None)
            journal(goal, 'OUTPUT_SOURCE_STALE', expected=goal['result_revision'], actual=graph.revision)
            return save_goal(goal)
        if goal['status'] == 'OUTPUT_PENDING':
            goal['status'] = goal.pop('engineering_status')
            goal['completion'] = goal.pop('engineering_completion')
        signature = digest([graph.revision, goal.get('completion'), VERSION])
        if goal.get('output_signature') == signature and goal.get('outputs'):
            return goal
        goal['outputs'] = OutputComposer().compose(goal, graph)
        required = goal.get('plan', {}).get('output_plan', ['VISUALIZATION', 'VALIDATION'])
        from .models import DesiredEngineeringState, GoalCompletionEvaluator
        checked = GoalCompletionEvaluator().evaluate(DesiredEngineeringState.model_validate(goal['desired_state']),
            (goal.get('completion') or {}).get('evidence', {}), required_outputs=required, outputs=goal['outputs'])
        if any(key.startswith('output:') for key in checked['missing_conditions']):
            raise ValueError('Ein beauftragter Output fehlt.')
        goal['output_signature'] = signature
        goal.pop('output_error', None)
        journal(goal, 'OUTPUTS_GENERATED', output_ids=[o['output_id'] for o in goal['outputs']], model_revision=graph.revision)
    except Exception:
        import logging
        logging.getLogger(__name__).exception('Engineering output composition failed for %s', goal['workload_id'])
        if goal['status'] != 'OUTPUT_PENDING':
            goal['engineering_status'] = goal['status']
            goal['engineering_completion'] = deepcopy(goal.get('completion') or {})
        goal['status'] = 'OUTPUT_PENDING'
        goal['completion'] = {**goal['engineering_completion'], 'status': 'INCOMPLETE',
            'missing_conditions': [*goal['engineering_completion'].get('missing_conditions', []), 'outputs_generated']}
        goal['output_error'] = 'Die Modellarbeit ist gespeichert. Die Ausgabe konnte noch nicht erzeugt werden. Auftrag fortsetzen.'
        journal(goal, 'OUTPUTS_PENDING')
    return save_goal(goal)
