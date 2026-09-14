"""Goal lifecycle. Only conversation/API input may authorize a saved decision."""
from copy import deepcopy
from .graph import ModelGraphService, digest
from .planner import connection_plan
from .models import ExecutionAuthorization
from .store import get_goal, save_goal
from .executor import execute, journal
from ..db import get_connection, _request_unit


def prepare(goal, source_ref, target_ref, message_ids=()):
    graph = ModelGraphService.load()
    result = connection_plan(graph, goal, source_ref, target_ref, message_ids)
    journal(result, 'MODEL_INSPECTED', revision=graph.revision, hosts=result.get('host_refs'), requirement=goal)
    result = validate_options(result)
    if len(result['strategies']) == 1 and result['strategies'][0]['option']['id'] == 'REUSE' and not result['strategies'][0]['needs_decision']:
        from ..agent_tools import conversation
        from backend.agent_core.orchestration.capability_intent import connection_request
        requested = conversation.read().get('current_requirement', '')
        match = connection_request(requested)
        if requested == goal and match:
            refs = [graph.find_object(text)['id'] for text in match]
            if list(map(str, refs)) == [result['source_ref'], result['target_ref']]:
                authorize(result, result['strategies'][0], 'explicit-user-connection-request', 'conversation-user')
                return execute(result['workload_id'])
    return save_goal(result)


def validate_options(goal):
    """Evaluate complete candidate deltas in a rolled-back database savepoint.

    No simulation is dispatched and no canonical changes, routes or snapshots
    survive this check. The same validators are used after human approval.
    """
    if not goal.get('strategies'): return goal
    if _request_unit.get() is None:
        raise RuntimeError('Die technische Vorprüfung benötigt eine gesperrte Projekttransaktion.')
    if len(goal['strategies']) > 8:
        goal.update(status='BLOCKED', pending_decision=None, findings=[{'code': 'ARCHITECTURE_SCOPE_REQUIRED',
            'severity': 'OPEN', 'message': 'Mehr als acht technische Wege sind möglich. Zielnetz oder Controller gezielt eingrenzen.'}])
        return goal
    class PreviewRollback(Exception): pass
    valid, rejected = [], []
    unit = _request_unit.get()
    dirty = unit.model_changed if unit else False
    for strategy in goal['strategies']:
        trial = deepcopy(goal)
        try:
            with get_connection():
                authorize(trial, strategy, 'technical-preview', 'technical-preview')
                trial = execute(trial['workload_id'])
                raise PreviewRollback()
        except PreviewRollback:
            pass
        finally:
            if unit: unit.model_changed = dirty
        preview = {'persisted': False, 'status': trial['status'], 'findings': trial.get('findings', []),
            'completion': trial.get('completion'), 'capacity': (trial.get('capacity') or {}).get('results', {}).get('networks', [])}
        if trial['status'] in {'COMPLETE', 'READY_FOR_REVIEW'}:
            strategy['technical_preview'] = preview
            valid.append(strategy)
        else:
            rejected.append({'strategy_id': strategy['id'], **preview})
    goal['rejected_strategies'] = rejected
    goal['strategies'] = valid
    if valid:
        goal['pending_decision']['options'] = [o for o in goal['pending_decision']['options'] if o['id'] in {s['id'] for s in valid}]
    else:
        goal.update(status='BLOCKED', pending_decision=None, findings=[f for r in rejected for f in r['findings']])
    return goal


def authorize(goal, strategy, decision_id, actor):
    """Internal human-input boundary; deliberately not registered as an MCP tool."""
    scope = sorted({*goal['desired_state']['target_objects'], *goal.get('host_refs', []), *goal['message_ids'], strategy['network_ref']})
    goal['authorization'] = ExecutionAuthorization(decision_id=decision_id, approved_goal=goal['goal'],
        approved_strategy=strategy['id'], allowed_change_types=['HardwareNetworkInterface', 'PhysicalPort', 'NetworkConnection',
            'Interface', 'MessageBinding', 'TransportUnit', 'MissingTransportParameters', 'RoutingEntry', 'Relation', 'Topology', 'AnalysisSnapshot'], affected_scope=scope,
        forbidden_changes=['HardwareCapabilityExpansion', 'CommunicationControllerCreation', 'HardwareReplacement',
            'SignalEncodingChange', 'UnrelatedRouteChange', 'DeleteAllRoutes'], model_revision=goal['model_revision'],
        authorized_by=actor, plan_hash=digest(strategy['plan'])).model_dump(mode='json')
    goal['pending_decision'] = None
    port_decision = strategy.get('port_decision')
    if port_decision:
        port_decision['status'] = 'ANSWERED'
        for item in goal.get('port_decisions', []):
            if item['decision_id'] == port_decision['decision_id']: item['status'] = 'ANSWERED'
    goal['status'] = 'READY'
    journal(goal, 'DECISION_AUTHORIZED', authorization=goal['authorization'])
    return save_goal(goal)


def answer(workload_id, decision_id, selected, *, actor):
    goal = get_goal(workload_id)
    decision = goal.get('pending_decision') or {}
    if decision.get('decision_id') != decision_id or goal['status'] != 'SUSPENDED_FOR_DECISION':
        raise ValueError('Diese Ausführungsentscheidung ist nicht mehr offen.')
    if decision['kind'] == 'PAYLOAD' and selected == ['__NEXT__'] and len(decision['options']) > 7:
        from uuid import uuid4
        pages = (len(decision['options']) + 6) // 7
        decision['page'] = (decision.get('page', 0) + 1) % pages
        decision['decision_id'] = str(uuid4())
        return save_goal(goal)
    valid = {o['id'] for o in decision['options']}
    if selected == ['DEFER']:
        goal.update(status='PAUSED', pending_decision=None)
        journal(goal, 'USER_DEFERRED')
        return save_goal(goal)
    if not selected or len(selected) != len(set(selected)) or not set(selected) <= valid:
        raise ValueError('Ungültige Entscheidung.')
    if decision['kind'] == 'STRATEGY' and len(selected) != 1:
        raise ValueError('Genau eine Strategie auswählen.')
    graph = ModelGraphService.load()
    if decision['kind'] == 'PAYLOAD':
        replacement = validate_options(connection_plan(graph, goal['goal'], goal['source_ref'], goal['target_ref'], selected))
        replacement.update(workload_id=workload_id, journal=goal['journal'])
        journal(replacement, 'PAYLOAD_SELECTED', message_ids=selected)
        return save_goal(replacement)
    strategy = next(s for s in goal['strategies'] if s['id'] == selected[0])
    if graph.revision != goal['model_revision']:
        replacement = validate_options(connection_plan(graph, goal['goal'], goal['source_ref'], goal['target_ref'], goal['message_ids']))
        replacement.update(workload_id=workload_id, journal=goal['journal'])
        journal(replacement, 'MODEL_REINSPECTED_AFTER_DECISION', old_revision=goal['model_revision'], revision=graph.revision)
        # A concurrently added matching port narrows the accepted strategy; never duplicate it.
        compatible = [s for s in replacement['strategies'] if s['source_port'] == strategy['source_port']
            and s['network_ref'] == strategy['network_ref'] and s['option']['id'] == 'REUSE'
            and strategy['option']['id'] == 'CREATE_AND_CONNECT_PORT'
            and replacement.get('host_refs') == goal.get('host_refs')
            and decision_context(replacement) == decision_context(goal)]
        if len(compatible) == 1:
            return authorize(replacement, compatible[0], decision_id, actor)
        return save_goal(replacement)
    return authorize(goal, strategy, decision_id, actor)


def decision_context(goal):
    situation = goal.get('situation') or {}
    targets = set(goal['desired_state']['target_objects'])
    return digest({'functions': [f for f in situation.get('functions', []) if str(f['id']) in targets],
        'hardware': [h for h in situation.get('hardware_nodes', []) if str(h['id']) in goal.get('host_refs', [])],
        'messages': [m for m in situation.get('transport_units', []) if str(m['id']) in goal['message_ids']],
        'signals': [s for s in situation.get('payload_elements', []) if str(s.get('message_id')) in goal['message_ids']]})


def resume(workload_id):
    goal = get_goal(workload_id)
    if goal['status'] == 'BACKGROUND_PAUSED' and goal.get('followup_authorization'):
        goal.update(status='SIMULATION_RUNNING', background={})
        journal(goal, 'FOLLOWUP_RESUMED_BY_USER')
        return save_goal(goal)
    if goal['status'] in {'READY', 'FAILED', 'BLOCKED'} and goal.get('authorization'):
        return execute(workload_id)
    if goal['status'] in {'PLAN_STALE', 'READY_FOR_REVIEW', 'PAUSED'}:
        replacement = validate_options(connection_plan(ModelGraphService.load(), goal['goal'], goal['source_ref'], goal['target_ref'], goal['message_ids']))
        replacement.update(workload_id=workload_id, journal=goal['journal'])
        journal(replacement, 'RESUMED_AND_REPLANNED')
        return save_goal(replacement)
    return goal


def presentation(goal):
    """Compact UI contract; detailed model facts remain in the execution journal."""
    from backend.agent_core.api.agent_response import AgentResponse, InteractiveQuestion
    decision = goal.get('pending_decision')
    summary = {'workload_id': goal['workload_id'], 'status': goal['status'], 'goal': goal['goal'],
        'completed': sum(s['status'] == 'SUCCEEDED' for s in goal.get('plan', {}).get('steps', [])),
        'total': len(goal.get('plan', {}).get('steps', [])) or 23}
    if decision:
        options = [{k: v for k, v in option.items() if k in {'id', 'label', 'description'}} for option in decision['options']]
        if len(options) > 8 and decision['kind'] == 'PAYLOAD':
            start = decision.get('page', 0) * 7
            options = options[start:start + 7] + [{'id': '__NEXT__', 'label': 'Weitere Nachrichten',
                'description': 'Allein auswählen, um die nächste Seite zu öffnen. Der Auftrag bleibt erhalten.'}]
        if len(options) == 1:
            options.append({'id': 'DEFER', 'label': 'Offen lassen', 'description': 'Keine Änderung ausführen.'})
        question = InteractiveQuestion(id=decision['decision_id'], question=decision['question'],
            description='Die gewählte Strategie umfasst alle beschriebenen Folgearbeiten. Neue Architekturentscheidungen werden erneut gefragt.',
            selection_mode=decision['selection_mode'], options=options, required=True, engineering_impact='REQUIRED')
        return AgentResponse(type='QUESTION', text=decision['question'], question=question, workload=summary,
            metadata={'decision_key': f'goal:{goal["workload_id"]}:{decision["decision_id"]}'}).model_dump(mode='json', exclude_none=True)
    conditions = (goal.get('completion') or {}).get('missing_conditions', [])
    detail = '\n'.join(f.get('message', '') for f in goal.get('findings', []))
    texts = {'COMPLETE': 'Die gewählte Kommunikation wurde umgesetzt und alle Zielbedingungen sind nachgewiesen.',
        'FOLLOWUP_PENDING': 'Die Kommunikation ist umgesetzt. Die beauftragte Simulation folgt auf dem geprüften Modellstand.',
        'SIMULATION_RUNNING': 'Die beauftragte Simulation läuft. Der Gesamtauftrag bleibt bis zum Nachweis der Kommunikation offen.',
        'INCOMPLETE': 'Der Gesamtauftrag ist noch offen: ' + ', '.join({'communication_observed': 'Kommunikation wurde im Trace nicht für alle beauftragten Routen nachgewiesen',
            'analysis_complete': 'Trace-Analyse fehlt', 'simulation_complete': 'Simulation ist nicht abgeschlossen'}.get(c, c) for c in conditions),
        'READY_FOR_REVIEW': 'Der neue Kommunikationsweg ist umgesetzt. Offen: ' + ', '.join({'timing_valid': 'bestätigter Nachweis der Funktionsfrist',
            'preflight_valid': 'Preflight-Befunde des Projekts'}.get(c, c) for c in conditions),
        'PLAN_STALE': 'Das Modell wurde geändert. Der Auftrag bleibt erhalten und muss neu geprüft werden.',
        'PAUSED': 'Auftrag offen gelassen.', 'READY': 'Strategie freigegeben. Die Folgearbeiten werden ausgeführt.'}
    text = texts.get(goal['status'], detail or 'Der Auftrag ist noch nicht vollständig umgesetzt.')
    if goal['status'] == 'COMPLETE' and goal.get('followup'):
        text += ' Die beauftragte Simulation ist beendet; die Kommunikation ist im Trace nachgewiesen.'
        if 'ANALYZE_TRACE' in goal.get('followup_goals', []): text += ' Die Trace-Analyse ist gespeichert.'
    if goal['status'] in {'COMPLETE', 'READY_FOR_REVIEW', 'FOLLOWUP_PENDING', 'SIMULATION_RUNNING'}:
        selected = next((s for s in goal['strategies'] if s['id'] == goal.get('plan', {}).get('strategy')), {})
        if selected: text += '\nWeg: ' + selected['label']
        networks = (goal.get('capacity') or {}).get('results', {}).get('networks', [])
        for network in networks:
            if network['network_id'] == selected.get('network_ref'):
                load = network.get('average_load_percent', network.get('bus_load_percent'))
                if isinstance(load, (float, int)): text += f'\nNetzlast {network.get("network_name", network["network_id"])}: {load:.2f} %.'
        text += f'\n{len(goal.get("route_ids", []))} Routing-Einträge geprüft. Frühere abhängige Auswertungen wurden als veraltet markiert.'
    return AgentResponse(type='RESULT', status=goal['status'], text=text,
        workload=summary, metadata={'hardware_facts_required': goal['status'] == 'BLOCKED' and any(
            f.get('code') in {'COMMUNICATION_CAPABILITY_MISSING', 'COMMUNICATION_CONTROLLER_MISSING', 'NO_VALID_COMMUNICATION_PATH'} for f in goal.get('findings', [])),
            'details': {'completion': goal.get('completion'), 'route_ids': goal.get('route_ids'),
            'findings': goal.get('findings'), 'journal': goal.get('journal'), 'followup': goal.get('followup')}}).model_dump(mode='json', exclude_none=True)
