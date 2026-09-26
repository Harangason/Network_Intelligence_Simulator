"""Read existing directed functional routes, without creating a connection."""
from __future__ import annotations

from copy import deepcopy
from math import isfinite

from ..capacity.service import CapacityTimingService
from ..goal_execution.graph import ModelGraphService
from ..project_context import current_project_id


def inspect_communication_path(arguments: dict) -> dict:
    graph = ModelGraphService.load()
    base = {'model_revision': graph.revision, 'evidence_kind': 'CALCULATED_MODEL',
            'observed_trace_available': False,
            'sequence': {'status': 'NOT_OBSERVED', 'transactions': [], 'receiver_action': 'NOT_OBSERVED'}}
    try:
        source = graph.find_object(arguments['source_ref'])
        target = graph.find_object(arguments['target_ref'])
        source_id, target_id = str(source['id']), str(target['id'])
        if source_id not in graph.functions or target_id not in graph.functions:
            raise ValueError('Quelle und Empfänger müssen eindeutige vorhandene Funktionen sein.')
    except (ValueError, KeyError) as error:
        return {**base, 'status': 'ENDPOINT_NOT_RESOLVED', 'reason': str(error), 'routes': []}
    base.update(source={'id': source_id, 'name': source['name']}, target={'id': target_id, 'name': target['name']})
    routes = []
    for route in graph.find_routes_between(source_id, target_id):
        if route.get('approval_state') != 'APPROVED' or route.get('status') == 'OUTDATED':
            continue
        intent = route.get('route', {}).get('functional_intent') or {}
        # Sharing a controller is not proof that a route belongs to this function.
        src_interface = graph.interfaces.get(str(route.get('source', {}).get('interface_id')), {})
        src = (intent.get('source') or {}).get('function_id') or src_interface.get('function_id')
        destinations = intent.get('destinations') or [
            {'function_id': graph.interfaces.get(str(item.get('interface_id')), {}).get('function_id')}
            for item in route.get('destinations', [])]
        if str(src) == source_id and target_id in {str(item.get('function_id')) for item in destinations}:
            routes.append(route)
    if not routes:
        return {**base, 'status': 'NO_FUNCTIONAL_ROUTE', 'routes': [],
                'reason': 'Zwischen diesen Funktionen ist keine aktuelle freigegebene gerichtete Route nachgewiesen.'}
    calculation = CapacityTimingService(current_project_id()).calculate(persist=False)
    metrics = calculation.get('results', {}).get('routes', [])
    rows = []
    for route in routes:
        path = route.get('route') or {}
        hops = []
        for hop in path.get('hops', []):
            ref = str(hop.get('node_id'))
            node = graph.hardware.get(ref)
            if node:
                hops.append({'id': ref, 'name': node['name'], 'device_type': node.get('device_type')})
        physical_paths = []
        for physical in path.get('physical_paths', []):
            ports = [graph.hni.get(str(ref)) for ref in physical.get('ports', [])]
            physical_paths.append({'resolved': bool(ports) and all(port is not None for port in ports),
                'ports': [{'id': port['id'], 'name': port.get('name'), 'technology': port.get('technology'),
                           'hardware_node_id': port.get('hardware_node_id'), 'network_ref': port.get('network_ref')}
                          for port in ports if port is not None], 'edges': deepcopy(physical.get('edges', []))})
        timing = [{key: deepcopy(row.get(key)) for key in (
            'route_id', 'message_id', 'network_id', 'protocol', 'end_to_end_latency_ms',
            'latency_status', 'max_latency_ms', 'breakdown', 'bottleneck')}
            for row in metrics if str(row.get('route_id')) == str(route['id'])]
        rows.append({'id': str(route['id']), 'name': route.get('name') or str(route['id']),
                     'hops': hops, 'physical_paths': physical_paths,
                     'gateways': deepcopy(path.get('gateways', [])),
                     'transformations': deepcopy(path.get('transformations', [])),
                     'payload': deepcopy(route.get('payload', {})), 'timing': timing})
    if ModelGraphService.load().revision != graph.revision:
        return {**base, 'status': 'MODEL_CHANGED', 'routes': [],
                'reason': 'Der Modellstand änderte sich während der Analyse. Erneut lesen.'}
    from .communication_evidence import simulation_sequence
    sequence = simulation_sequence({row['id'] for row in rows})
    if ModelGraphService.load().revision != graph.revision or sequence.get('reason') == 'MODEL_CHANGED':
        return {**base, 'status': 'MODEL_CHANGED', 'routes': [],
                'reason': 'Der Modellstand änderte sich während der Analyse. Erneut lesen.'}
    base['sequence'] = sequence
    if sequence['status'] == 'SIMULATED':
        base['evidence_kind'] = 'CALCULATED_MODEL_AND_SIMULATION'
    resolved = all(row['hops'] and row['physical_paths'] and all(p['resolved'] for p in row['physical_paths']) for row in rows)
    timing_known = all(row['timing'] and all(
        isinstance(timing['end_to_end_latency_ms'], (int, float))
        and not isinstance(timing['end_to_end_latency_ms'], bool)
        and isfinite(timing['end_to_end_latency_ms']) and timing['end_to_end_latency_ms'] >= 0
        for timing in row['timing']) for row in rows)
    return {**base, 'status': 'PHYSICAL_PATH_UNVERIFIED' if not resolved else
            'MODEL_PATH_RESOLVED' if timing_known else 'TIMING_UNVERIFIED',
            'routes': rows, 'calculation_version': calculation.get('provenance', {}).get('calculation_version'),
            'reason': 'Der vollständige physische Pfad ist nicht nachgewiesen.' if not resolved else
            '' if timing_known else 'Die aktuelle Modellberechnung liefert keine vollständigen Laufzeitnachweise.'}
