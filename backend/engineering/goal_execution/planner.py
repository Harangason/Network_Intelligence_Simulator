"""Inspect first, plan the complete dependency delta, then request bounded authority."""
from uuid import uuid4
from .models import (DesiredEngineeringState, EngineeringExecutionPlan, EngineeringExecutionStep,
    EngineeringModelDelta, GoalType, COMPLETION_CONTRACTS)
from .ports import inspect_port_decision, finding
from .graph import digest
from ..physical_ports import technology_id
from ..routing.payload_scope import message_scope, scope_allows

STEP_DEFINITIONS = [
    ('revision', 'Modellrevision prüfen', 'inspect_model_situation'),
    ('capability', 'Technologie-Fähigkeit prüfen', 'inspect_communication_capability'),
    ('controller', 'Controller und Kanalgrenzen prüfen', 'inspect_controller_capacity'),
    ('interface', 'HardwareInterface wiederverwenden oder erstellen', 'create_hardware_interface'),
    ('port', 'Physischen Port wiederverwenden oder erstellen', 'create_physical_port'),
    ('port_binding', 'Controller, Interface und Port verbinden', 'bind_port_to_interface'),
    ('network', 'Port mit dem freigegebenen Netz verbinden', 'connect_port_to_network'),
    ('topology', 'Kanonische Topologie und Mitgliedschaft aktualisieren', 'update_network_membership'),
    ('functions', 'Aktuelle Funktionszuordnung prüfen', 'inspect_function_mapping'),
    ('functional_interfaces', 'Logische Schnittstellen auflösen', 'resolve_function_interfaces'),
    ('payload', 'Benötigte Daten und Empfänger prüfen', 'resolve_payload_elements'),
    ('transport', 'TransportUnits wiederverwenden oder erzeugen', 'bind_transport_unit'),
    ('packing', 'Technologiespezifische Nutzlast prüfen', 'pack_transport_unit'),
    ('identifier', 'Identifier kollisionsfrei auflösen', 'allocate_identifier'),
    ('routing', 'Betroffene Routing-Einträge aktualisieren', 'update_goal_routing'),
    ('supersede', 'Ersetzte Routen kontrolliert ablösen', 'supersede_goal_routes'),
    ('invalidate', 'Abhängige alte Ergebnisse als veraltet markieren', 'invalidate_goal_results'),
    ('capacity', 'Interface- und Netzlast berechnen', 'recalculate_network_load'),
    ('timing', 'Zeitverhalten und Fristen berechnen', 'recalculate_timing'),
    ('addresses', 'Logische Adressen prüfen', 'validate_logical_addresses'),
    ('validation', 'Modell, Port, Bindung, Transport und Routing validieren', 'validate_goal_model'),
    ('preflight', 'Communication Preflight ausführen', 'run_communication_preflight'),
    ('completion', 'Zielzustand unabhängig prüfen', 'evaluate_goal_completion'),
]


class EngineeringImpactResolver:
    def resolve(self, graph, delta):
        touched = {str(ref) for group in (delta.create, delta.update, delta.supersede)
                   for item in group for ref in item.get('target_refs', [])}
        related = set(touched)
        for ref in touched: related.update(graph.find_downstream_dependencies(ref))
        routes = [r for r in graph.model.get('routing', []) if str(r.get('source', {}).get('node_id')) in related
                  or any(str(d.get('node_id')) in related for d in r.get('destinations', []))]
        return {'affected_objects': sorted(related), 'affected_relations': [r for r in graph.relations
                    if str(r.get('source_id')) in related or str(r.get('target_id')) in related],
            'affected_routes': [r['id'] for r in routes], 'affected_transport_units': sorted(related & graph.messages.keys()),
            'affected_networks': sorted({str(i.get('network_ref')) for i in graph.hni.values() if str(i.get('hardware_node_id')) in related and i.get('network_ref')}),
            'affected_calculations': ['capacity_timing', 'preflight'],
            'affected_simulation_runs': graph.state.get('simulation_snapshots', []),
            'affected_trace_results': graph.state.get('trace_results', []),
            'required_revalidation': ['model', 'port', 'binding', 'transport', 'routing', 'capacity', 'timing', 'preflight']}


def connection_plan(graph, goal, source_ref, target_ref, message_ids=()):
    from .followups import requested_followups, simulation_configuration
    followups = requested_followups(goal)
    source, target = graph.find_object(source_ref), graph.find_object(target_ref)
    source_ref, target_ref = str(source['id']), str(target['id'])
    kind = GoalType.CONNECT_FUNCTIONS if source_ref in graph.functions and target_ref in graph.functions else GoalType.CONNECT_HARDWARE
    desired = DesiredEngineeringState(goal=goal, goal_type=kind, target_objects=[source_ref, target_ref],
        required_relationships=[{'source': source_ref, 'target': target_ref, 'type': 'COMMUNICATES_WITH'}],
        required_connectivity=[{'source': source_ref, 'target': target_ref}],
        required_validation=['model', 'port', 'binding', 'transport', 'routing', 'capacity', 'timing', 'preflight'],
        completion_criteria=COMPLETION_CONTRACTS[kind])
    workload = {'workload_id': f'goal-{uuid4()}', 'goal': goal, 'desired_state': desired.model_dump(mode='json'),
                'model_revision': graph.revision, 'status': 'PLANNING', 'authorization': None, 'journal': [],
                'strategies': [], 'pending_decision': None, 'validation_state': {}, 'attempts': 0,
                'source_ref': source_ref, 'target_ref': target_ref, 'message_ids': list(message_ids)}
    workload['followup_goals'] = followups
    try:
        followup_configuration = simulation_configuration(goal, graph.state) if followups else {}
    except ValueError as error:
        return {**workload, 'status': 'BLOCKED', 'findings': [finding('SIMULATION_SCOPE_REQUIRED', str(error))]}
    try:
        src, dst = graph.host(source_ref), graph.host(target_ref)
    except ValueError as error:
        return {**workload, 'status': 'BLOCKED', 'findings': [finding('FUNCTION_MAPPING_MISSING', str(error))]}
    src_id, dst_id = str(src['id']), str(dst['id'])
    workload['host_refs'] = [src_id, dst_id]
    if src_id == dst_id:
        return {**workload, 'status': 'BLOCKED', 'findings': [finding('LOCAL_TRANSPORT_REQUIRED', 'Beide Funktionen liegen auf derselben Hardware. Lokalen Datenaustausch ausdrücklich modellieren; keine künstliche Busroute anlegen.')]}
    destination_interfaces = graph.find_function_interfaces(target_ref) if target_ref in graph.functions else [i for i in graph.interfaces.values() if str(i.get('hardware_node_id')) == dst_id]
    source_interfaces = graph.find_function_interfaces(source_ref) if source_ref in graph.functions else [i for i in graph.interfaces.values() if str(i.get('hardware_node_id')) == src_id]
    source_interface_ids = {str(i['id']) for i in source_interfaces}
    allowed = []
    for message in graph.messages.values():
        if str(message.get('interface_id')) not in source_interface_ids or message.get('direction') == 'rx': continue
        scope = message_scope(message)
        if not any(scope_allows(scope, {'node_id': dst_id, 'interface_id': str(i['id'])}, graph.interfaces) for i in destination_interfaces):
            # A required receive interface may be created on the actual target function.
            # Explicit local recipient boundaries still apply before that creation.
            if scope['restricted'] and not {target_ref, dst_id}.intersection(scope['consumer_refs']): continue
        if scope['scope'] == 'LOCAL_IO' and target_ref in graph.functions and target_ref not in scope['consumer_refs']: continue
        if scope['consumer_refs'] and not {target_ref, dst_id, *[str(i['id']) for i in destination_interfaces]}.intersection(scope['consumer_refs']): continue
        if any(str(s.get('message_id')) == str(message['id']) for s in graph.signals.values()): allowed.append(message)
    selected = [m for m in allowed if str(m['id']) in set(message_ids)] if message_ids else allowed
    if message_ids and len(selected) != len(set(message_ids)):
        return {**workload, 'status': 'BLOCKED', 'findings': [finding('PAYLOAD_SCOPE_INVALID', 'Payload fehlt oder liegt außerhalb des freigegebenen Funktions-/Empfängerumfangs.') ]}
    if not source_interfaces or not selected:
        return {**workload, 'status': 'BLOCKED', 'findings': [finding('PAYLOAD_DATA_GAP', 'Logische Schnittstelle oder benötigte, explizit kodierte Funktionsausgänge fehlen. Datenbedarf konkret festlegen; keine Signalwerte erfinden.')],
                'data_gaps': [{'source': source_ref, 'target': target_ref, 'missing': 'functional_interface_or_payload'}]}
    if not message_ids and len(selected) > 1:
        workload.update(status='SUSPENDED_FOR_DECISION', pending_decision={'kind': 'PAYLOAD', 'decision_id': str(uuid4()),
            'question': f'Welche Daten von {source["name"]} benötigt {target["name"]}?',
            'options': [{'id': str(m['id']), 'label': m['name']} for m in selected], 'selection_mode': 'MULTI'})
        return workload
    workload['message_ids'] = [str(m['id']) for m in selected]
    desired.required_transport = [{'message_ref': str(m['id']), 'source': source_ref, 'target': target_ref} for m in selected]
    workload['desired_state'] = desired.model_dump(mode='json')
    existing = graph.find_routes_between(source_ref, target_ref)
    existing = [r for r in existing if set(r.get('payload', {}).get('message_ids', [])).intersection(workload['message_ids'])
                or r.get('payload', {}).get('message_id') in workload['message_ids']]
    decisions = []
    for interface in graph.find_hardware_interfaces(src_id):
        net = graph.networks.get(interface.get('network_ref'))
        if not net or not interface.get('physical_port_ref'): continue
        if technology_id(interface['technology']) != technology_id(net['technology']): continue
        decision = inspect_port_decision(graph, dst_id, interface['technology'], net['id']); decisions.append(decision)
        for option in decision['options']:
            strategy = {'id': f'direct:{interface["id"]}:{option["id"]}', 'label': f'Direkt über {net.get("name", net["id"])} · {interface["technology"]}',
                'source_port': str(interface['id']), 'target_port': decision.get('existing_interface_ref'), 'network_ref': net['id'],
                'technology': interface['technology'], 'port_decision': decision, 'option': option,
                'needs_decision': option['id'] != 'REUSE' or any(r.get('approval_state') == 'APPROVED' for r in existing)}
            workload['strategies'].append(strategy)
    for path in graph.find_gateways_between(source_ref, target_ref):
        if not path['ports']: continue
        if any(s['option']['id'] == 'REUSE' and s['source_port'] == path['ports'][0] and s['target_port'] == path['ports'][-1] for s in workload['strategies']): continue
        workload['strategies'].append({'id': 'path:' + digest(path)[:16], 'label': 'Bestehenden geprüften Hardwarepfad verwenden',
            'source_port': path['ports'][0], 'target_port': path['ports'][-1], 'path': path,
            'network_ref': graph.hni[path['ports'][0]]['network_ref'], 'technology': graph.hni[path['ports'][0]]['technology'],
            'option': {'id': 'REUSE'}, 'needs_decision': any(r.get('approval_state') == 'APPROVED' for r in existing)})
    workload['port_decisions'] = decisions
    workload['situation'] = graph.situation([source_ref, target_ref]).model_dump(mode='json')
    if not workload['strategies']:
        workload.update(status='BLOCKED', findings=[f for d in decisions for f in d['findings']] or [finding('NO_VALID_COMMUNICATION_PATH', 'Es gibt keinen belegten kompatiblen Anschluss oder Gateway-Pfad. Bestätigte Hardware-Daten ergänzen.')])
        return workload
    for strategy in workload['strategies']:
        delta = EngineeringModelDelta(
            create=([{'object_type': kind, 'target_refs': [dst_id], 'network_ref': strategy['network_ref']}
                    for kind in (['PhysicalPort', 'NetworkConnection'] if strategy['option'].get('hardware_interface_ref') else ['HardwareNetworkInterface', 'PhysicalPort', 'NetworkConnection'])]
                if strategy['option']['id'] == 'CREATE_AND_CONNECT_PORT' else [])
                + ([{'object_type': 'Interface', 'target_refs': [target_ref, dst_id], 'technology': strategy['technology']}]
                    if not any(i.get('interface_type') == strategy['technology'] for i in destination_interfaces) else [])
                + ([{'object_type': 'RoutingEntry', 'target_refs': [source_ref, target_ref], 'message_refs': workload['message_ids']}]
                    if not existing else []),
            update=[{'object_type': 'Message', 'target_refs': workload['message_ids'],
                'fields': ['physical_transmit_bindings', 'transport_unit', 'dlc_if_missing', 'message_id_hex_if_missing']},
                {'object_type': 'Topology', 'target_refs': [src_id, dst_id]},
                *([{'object_type': 'HardwareNetworkInterface', 'target_refs': [strategy['option']['hardware_interface_ref']]}] if strategy['option'].get('hardware_interface_ref') else []),
                *[{'object_type': 'RoutingEntry', 'target_refs': [str(r['id'])], 'expected_revision': r['revision']} for r in existing]],
            supersede=[{'object_type': 'RoutingEntry', 'target_refs': [str(r['id'])]} for r in existing if r.get('status') == 'OUTDATED'],
            invalidate=[{'target_refs': [src_id, dst_id], 'types': ['SimulationSnapshot', 'SimulationRun', 'TraceAnalysis', 'CapacityResult', 'TimingResult']}],
            recalculate=[{'network_ref': strategy['network_ref'], 'types': ['interface_load', 'network_load', 'timing']}],
            validate=[{'types': desired.required_validation}])
        steps = [EngineeringExecutionStep(step_id=key, action=label, tool=tool, target_refs=[source_ref, target_ref],
                    inputs={'source_ref': source_ref, 'target_ref': target_ref, 'source_hardware_interface': strategy['source_port'],
                        'target_hardware_interface': strategy.get('target_port'), 'network_ref': strategy['network_ref'],
                        'message_refs': workload['message_ids'], 'port_option': strategy['option']},
                    prerequisites=[STEP_DEFINITIONS[index-1][0]] if index else [], expected_result=label, validation=key)
                 for index, (key, label, tool) in enumerate(STEP_DEFINITIONS)]
        plan = EngineeringExecutionPlan(goal=goal, model_revision=graph.revision, strategy=strategy['id'], steps=steps,
            dependencies=[{'before': a.step_id, 'after': b.step_id} for a, b in zip(steps, steps[1:])],
            validation_steps=[s.step_id for s in steps if s.step_id in {'capacity','timing','addresses','validation','preflight','completion'}],
            completion_criteria=desired.completion_criteria, delta=delta, followup_goals=followups, followup_configuration=followup_configuration)
        strategy['plan'] = plan.model_dump(mode='json'); strategy['impact'] = EngineeringImpactResolver().resolve(graph, delta)
    workload.update(status='SUSPENDED_FOR_DECISION', pending_decision={'kind': 'STRATEGY', 'decision_id': str(uuid4()),
        'question': f'{source["name"]} läuft auf {src["name"]}; {target["name"]} auf {dst["name"]}. Welcher Kommunikationsweg soll umgesetzt werden?',
        'options': [{'id': s['id'], 'label': s['label'], 'description':
            'Neuer physischer Port erforderlich. Die Wahl umfasst Interface, Anschluss, Transport, Routing, Berechnung und Validierung.'
            if s['option']['id'] == 'CREATE_AND_CONNECT_PORT' else 'Vorhandene Anschlüsse verwenden; Transport, Routing und Prüfungen vollständig ausführen.'} for s in workload['strategies']],
        'selection_mode': 'SINGLE'})
    if followups:
        suffix = f' Anschließend den aktuellen Modellstand als Normalprüfung für {followup_configuration["duration_s"]:g} s simulieren (Seed {followup_configuration["seed"]}, höchstens 100000 Ereignisse)' + (' und den Trace analysieren.' if 'ANALYZE_TRACE' in followups else '.')
        workload['pending_decision']['question'] += suffix
        for option in workload['pending_decision']['options']: option['description'] += suffix
    return workload
