"""Bounded deterministic execution paths over registered engineering tools.

The general agent remains available for goals without a deterministic adapter.
Handlers return None only when their narrow input contract does not apply.
"""
from __future__ import annotations

from typing import Any

from ..api.agent_response import AgentResponse
from .goal_resolver import EngineeringGoal, GoalType


class EngineeringExecutor:
    def __init__(self, client):
        self.client = client
        self.handlers = {GoalType.CREATE_PROJECT: self._simple_project,
                         GoalType.PERIODIC_ACQUISITION: self._periodic_acquisition,
                         GoalType.CHANGE_CONFIGURATION: self._network_configuration,
                         GoalType.EXTEND_HARDWARE: self._hardware_channel,
                         GoalType.RUN_SIMULATION: self._gateway_outage,
                         GoalType.REPAIR: self._recipient_repair,
                         GoalType.DIAGNOSE: self._message_timing_diagnosis}

    async def execute(self, goal: EngineeringGoal, context: Any, resolved_context: dict,
                      *, emit, available_tools: set[str]) -> dict | None:
        if resolved_context.get('wizard_request'):
            return None
        handler = self.handlers.get(goal.goal_type)
        if handler is None:
            return None
        return await handler(goal, context, emit=emit, available_tools=available_tools)

    async def _recipient_repair(self, goal, context, *, emit, available_tools):
        from .goal_resolver import recipient_repair_intent
        if not recipient_repair_intent(goal.original_request):
            return None
        required = {'inspect_signal_recipients', 'prepare_signal_recipient_repair', 'validate_proposal'}
        events, trace, proposals = [], [], []
        details = {'workload_id': goal.goal_id, 'completion': {'complete': False}}
        run_id = getattr(getattr(context, 'input_envelope', None), 'run_ref', '')

        def finish(status, text, proposal=None):
            if proposal:
                names = [item['signal_name'] for item in details.get('findings') or [] if item.get('review_required')]
                visible = text + (' Offene Empfänger: ' + ', '.join(names[:20]) + '.' if names else '')
                if len(names) > 20:
                    visible += ' Weitere offene Signale stehen in den gespeicherten Prüfergebnissen.'
                summary = AgentResponse(type='RESULT', status='READY_FOR_REVIEW', text=visible,
                    findings=details.get('findings') or [], metadata={
                        'run_id': run_id, 'input_ref': getattr(getattr(context, 'input_envelope', None), 'input_id', ''),
                        'details': dict(details), 'tool_trace_id': trace[-1]['trace_id'] if trace else None,
                    }).model_dump(mode='json', exclude_none=True)
                events.append(summary); emit(summary)
            event = AgentResponse(type='APPROVAL' if proposal else 'RESULT', status=status,
                text=text, proposal=proposal, findings=details.get('findings') or [], metadata={
                    'run_id': run_id, 'input_ref': getattr(getattr(context, 'input_envelope', None), 'input_id', ''),
                    'details': details, 'tool_trace_id': trace[-1]['trace_id'] if trace else None,
                }).model_dump(mode='json', exclude_none=True)
            events.append(event); emit(event)
            return {'run_id': run_id, 'status': status, 'events': events, 'trace': trace,
                    'context': context.model_dump(mode='json'), 'proposals': proposals}

        async def call(name, arguments):
            response = await self.client.call(name, arguments)
            trace.append({'tool': name, 'trace_id': response.trace_id, 'status': response.status.value})
            return response

        if not required <= available_tools:
            details['missing_tools'] = sorted(required - available_tools)
            return finish('NOT_SUPPORTED_WITH_CAPABILITY_GAP', 'Die vollständige Empfängerprüfung ist nicht verfügbar.')
        inspected = await call('inspect_signal_recipients', {'workload_id': goal.goal_id})
        if not inspected.success:
            details['findings'] = inspected.findings
            return finish('BLOCKED', 'Der Signalbestand konnte nicht vollständig im aktuellen Projekt geprüft werden.')
        details.update(inspected.data)
        prepared = await call('prepare_signal_recipient_repair', {'workload_id': goal.goal_id,
            'expected_model_revision': inspected.data['model_revision']})
        if not prepared.success:
            return finish('BLOCKED', 'Der geprüfte Empfängerstand ist nicht mehr aktuell oder die Reparatur konnte nicht vorbereitet werden.')
        details.update(prepared.data)
        proposal = details.pop('proposal', None)
        count = len(details['scanned_signal_ids'])
        pending = len(details['review_required_signal_ids'])
        if not proposal:
            details['completion'] = {'complete': True}
            return finish('COMPLETED', f'{count} Signale geprüft. Keine eindeutige fehlende Route zur Übernahme. '
                f'{pending} Signal(e) bleiben zur Empfängerklärung offen. Es wurden keine Empfänger erfunden.')
        checked = await call('validate_proposal', {'proposal_id': proposal['proposal_id']})
        proposal = checked.data or proposal
        if not checked.success or proposal.get('status') != 'VALIDATED':
            return finish('BLOCKED', 'Die eindeutigen Empfängerrouten konnten nicht als gültiger Vorschlag bestätigt werden.')
        proposals.append(proposal)
        details['proposal_id'] = proposal['proposal_id']
        return finish('READY_FOR_REVIEW', f'{count} Signale geprüft. Für '
            f"{len(details['repairable_signal_ids'])} Signal(e) sind Empfänger ausdrücklich gespeichert und die fehlenden Routen eindeutig. "
            f'Diese Routen sind zur Übernahme vorbereitet. {pending} Signal(e) bleiben zur Empfängerklärung offen.', proposal)

    async def _gateway_outage(self, goal, context, *, emit, available_tools):
        import asyncio
        from time import monotonic
        from .gateway_intent import gateway_outage_intent
        if not gateway_outage_intent(goal.original_request):
            return None
        required = {'inspect_gateway_outage_request', 'calculate_capacity', 'validate_simulation_preflight',
                    'prepare_gateway_outage', 'start_simulation', 'get_simulation_status',
                    'analyze_fault_effects', 'assess_gateway_outage'}
        events, trace = [], []
        details = {'workload_id': goal.goal_id, 'completion': {'complete': False}}
        run_id = getattr(getattr(context, 'input_envelope', None), 'run_ref', '')

        def event(kind, text, status):
            item = AgentResponse(type=kind, status=status, text=text, metadata={
                'run_id': run_id, 'input_ref': getattr(getattr(context, 'input_envelope', None), 'input_id', ''),
                'details': dict(details), 'tool_trace_id': trace[-1]['trace_id'] if trace else None
            }).model_dump(mode='json', exclude_none=True)
            events.append(item)
            emit(item)

        def finish(status, text):
            event('RESULT', text, status)
            return {'run_id': run_id, 'status': status, 'events': events, 'trace': trace,
                    'context': context.model_dump(mode='json'), 'proposals': []}

        async def call(name, arguments):
            response = await self.client.call(name, arguments)
            trace.append({'tool': name, 'trace_id': response.trace_id, 'status': response.status.value})
            if not response.success:
                details['failed_tool'] = name
                details['findings'] = response.findings
            return response

        if not required <= available_tools:
            details['missing_tools'] = sorted(required - available_tools)
            return finish('NOT_SUPPORTED_WITH_CAPABILITY_GAP', 'Für die Gateway-Ausfallsimulation fehlt eine erforderliche Fachfähigkeit.')
        inspected = await call('inspect_gateway_outage_request', {'workload_id': goal.goal_id})
        if not inspected.success:
            reason = '; '.join(str(f.get('message', '')) for f in inspected.findings)
            return finish('BLOCKED', 'Der Gateway-Ausfall kann nicht eindeutig vorbereitet werden. ' + reason)
        details.update(inspected.data)
        event('PROGRESS', 'Ausgewähltes Gateway und vorhandene Kommunikationswege sind aufgelöst. Kapazität und Preflight werden geprüft.', 'VALIDATING')
        capacity = await call('calculate_capacity', {})
        preflight = await call('validate_simulation_preflight', {})
        if not capacity.success or not preflight.success or (preflight.data or {}).get('ready_for_simulation') is not True:
            details['preflight'] = preflight.data
            return finish('BLOCKED', 'Der aktuelle Preflight erlaubt noch keine Gateway-Ausfallsimulation.')
        prepared = await call('prepare_gateway_outage', {'workload_id': goal.goal_id,
                              'expected_model_revision': inspected.data['model_revision']})
        if not prepared.success:
            return finish('BLOCKED', 'Der Gateway-Simulationsstand konnte nicht aktuell und eindeutig gespeichert werden.')
        details.update(prepared.data)
        job_id = prepared.data.get('job_id')
        if not job_id:
            if prepared.data.get('snapshot_status') != 'READY':
                return finish('INCOMPLETE', 'Der gespeicherte Lauf wurde bereits angefordert; seine Job-Identität ist noch nicht nachgewiesen.')
            started = await call('start_simulation', {'snapshot_id': prepared.data['snapshot_id']})
            if not started.success or not (started.data or {}).get('id'):
                return finish('INCOMPLETE', 'Der gespeicherte Gateway-Lauf konnte noch nicht als gestarteter Simulationsjob bestätigt werden.')
            job_id = started.data['id']
        details['job_id'] = job_id
        event('PROGRESS', 'Das angeforderte Ausfallszenario ist gespeichert. Der zugehörige Simulationslauf wird geprüft.', 'RUNNING')
        deadline = monotonic() + 150
        for _ in range(76):
            polled = await call('get_simulation_status', {'job_id': job_id})
            if not polled.success:
                return finish('INCOMPLETE', 'Der gespeicherte Simulationslauf ist momentan nicht abrufbar.')
            status = (polled.data or {}).get('status')
            if status == 'completed':
                break
            if status not in {'pending', 'queued', 'running'}:
                details['job_status'] = status
                return finish('BLOCKED', 'Der Gateway-Simulationslauf wurde nicht erfolgreich abgeschlossen.')
            if monotonic() >= deadline:
                return finish('INCOMPLETE', 'Der Gateway-Lauf ist noch aktiv. Szenario und Job bleiben für die Fortsetzung gespeichert.')
            await asyncio.sleep(2)
        else:
            return finish('INCOMPLETE', 'Der Gateway-Lauf ist noch nicht abgeschlossen; seine gespeicherte Identität bleibt erhalten.')
        analyzed = await call('analyze_fault_effects', {'job_id': job_id, 'goal': goal.original_request})
        if not analyzed.success or not (analyzed.data or {}).get('reasoning_id'):
            return finish('INCOMPLETE', 'Der Lauf ist beendet, seine Auswirkungen sind noch nicht durch gespeicherte Trace-Befunde belegt.')
        assessed = await call('assess_gateway_outage', {'workload_id': goal.goal_id, 'reasoning_id': analyzed.data['reasoning_id']})
        if not assessed.success:
            return finish('INCOMPLETE', 'Szenario, Lauf und Trace-Befunde konnten nicht gemeinsam als aktuell bestätigt werden.')
        details.update(assessed.data)
        if details.get('completion', {}).get('complete') is not True:
            return finish('INCOMPLETE', 'Für den Gateway-Ausfall fehlen noch vollständige, korrelierte Nachweise. Die offenen Zielbedingungen sind gespeichert.')
        names = ', '.join(item['name'] for item in details['affected_communications'][:20])
        if len(details['affected_communications']) > 20:
            names += '; weitere Kommunikationswege stehen in den Ergebnisdetails'
        return finish('COMPLETED', f"Der Ausfall von {details['gateway_name']} wurde simuliert. "
            f"{len(details['affected_route_ids'])} Kommunikationsroute(n) sind durch {details['dropped_frame_count']} "
            f'ausgefallene Übertragungen im Trace betroffen: {names}. Die Ursachenbefunde sind gespeichert. '
            'Dies belegt die simulierten Ausfallfolgen. Eine funktionale Timing-Freigabe erfordert gesonderte Nachweise.')

    async def _hardware_channel(self, goal, context, *, emit, available_tools):
        required = {'inspect_hardware_channel_request', 'inspect_communication_capability',
                    'inspect_controller_capacity', 'find_free_channel', 'prepare_hardware_channel', 'validate_proposal'}
        if not required <= available_tools:
            return None
        inspected = await self.client.call('inspect_hardware_channel_request', {'request': goal.original_request})
        data = inspected.data or {}
        if not inspected.success or not data.get('supported'):
            return None
        trace = [{'tool': 'inspect_hardware_channel_request', 'trace_id': inspected.trace_id, 'status': inspected.status.value}]
        events = []
        run_id = getattr(getattr(context, 'input_envelope', None), 'run_ref', '')

        async def call(name, arguments):
            response = await self.client.call(name, arguments)
            trace.append({'tool': name, 'trace_id': response.trace_id, 'status': response.status.value})
            return response

        def event(kind, **fields):
            item = AgentResponse(type=kind, metadata={'run_id': run_id,
                'input_ref': getattr(getattr(context, 'input_envelope', None), 'input_id', ''),
                'tool_trace_id': trace[-1]['trace_id'], 'details': data}, **fields).model_dump(mode='json', exclude_none=True)
            events.append(item)
            emit(item)

        if data.get('hardware_id') and data.get('controller_id'):
            capability = await call('inspect_communication_capability', {'hardware_ref': data['hardware_id']})
            capacity = await call('inspect_controller_capacity', {'controller_ref': data['controller_id']})
            free = await call('find_free_channel', {'controller_ref': data['controller_id']})
            if not all(item.success for item in (capability, capacity, free)):
                data = {**data, 'status': 'BLOCKED', 'reason': 'Die aktuelle Hardwarekapazität konnte nicht vollständig geprüft werden.'}
            else:
                data = {**data, 'capability_inspection': capability.data, 'controller_capacity': capacity.data,
                        'free_channel_inspection': free.data}
        proposal = None
        if data.get('status') == 'READY':
            prepared = await call('prepare_hardware_channel', {'request': goal.original_request,
                'workload_id': goal.goal_id, 'expected_model_revision': data['model_revision']})
            proposal = (prepared.data or {}).get('proposal') if prepared.success else None
            if proposal and proposal.get('proposal_id'):
                checked = await call('validate_proposal', {'proposal_id': proposal['proposal_id']})
                proposal = checked.data or proposal
                if checked.success and proposal.get('status') == 'VALIDATED':
                    data['proposal_id'] = proposal['proposal_id']
                    event('APPROVAL', proposal=proposal, text='Der angeforderte Hardwarekanal ist anhand der bestätigten Controllergrenzen geprüft und zur Freigabe vorbereitet. Netzbindung, Bitrate und Kommunikation werden dadurch nicht festgelegt.')
                    status = 'READY_FOR_REVIEW'
                else:
                    event('RESULT', status='BLOCKED', text='Der Kanalvorschlag konnte nicht validiert werden.',
                          findings=(proposal.get('validation_result') or {}).get('findings') or checked.findings)
                    status = 'BLOCKED'
            else:
                reason = (prepared.data or {}).get('reason') or 'Der Hardwarekanal konnte nicht als geprüfter Vorschlag vorbereitet werden.'
                event('RESULT', status='BLOCKED', text=reason, findings=prepared.findings)
                status = 'BLOCKED'
        elif data.get('status') == 'ALREADY_PRESENT':
            # Presence alone cannot claim that dependent assessments were checked.
            event('RESULT', status='INCOMPLETE', text='Der angeforderte Kanal ist bereits im Modell vorhanden. Es wurde kein weiterer Anschluss angelegt; abhängige Prüfergebnisse sind noch nicht vollständig nachgewiesen.')
            status = 'INCOMPLETE'
        else:
            event('RESULT', status='BLOCKED', text=data.get('reason') or 'Die bestätigte Hardwarekapazität reicht für diesen Kanal nicht aus.', findings=data.get('findings') or [])
            status = 'BLOCKED'
        return {'run_id': run_id, 'status': status, 'events': events, 'trace': trace,
                'context': context.model_dump(mode='json'), 'proposals': [proposal] if proposal else []}

    async def _simple_project(self, goal: EngineeringGoal, context: Any, *, emit,
                              available_tools: set[str]) -> dict | None:
        if 'plan_simple_project' not in available_tools:
            return None
        response = await self.client.call('plan_simple_project', {
            'requirement': goal.original_request, 'workload_id': goal.goal_id})
        if not response.success:
            return None  # The general agent handles inputs outside this narrow parser.
        data = response.data or {}
        if not data.get('supported'):
            return None
        run_id = getattr(getattr(context, 'input_envelope', None), 'run_ref', '')
        events = []

        def event(kind: str, **fields):
            item = AgentResponse(type=kind, metadata={
                'run_id': run_id, 'input_ref': getattr(getattr(context, 'input_envelope', None), 'input_id', ''),
                'tool_trace_id': response.trace_id, **fields.pop('metadata', {})},
                **fields).model_dump(mode='json', exclude_none=True)
            events.append(item)
            emit(item)

        proposal = data.get('proposal')
        if proposal and proposal.get('status') == 'VALIDATED':
            event('APPROVAL', proposal=proposal,
                  text='Die angeforderte Projektstruktur ist geprüft. Nach deiner Freigabe werden die Modellobjekte im geöffneten Projekt angelegt.',
                  metadata={'open_decisions': data.get('open_decisions', []),
                            'model_revision_before': data.get('model_revision_before')})
            status = 'READY_FOR_REVIEW'
        elif data.get('status') == 'ALREADY_PRESENT':
            event('RESULT', status='COMPLETED', text='Die angeforderte Struktur ist im aktuellen Modell bereits vorhanden.',
                  metadata={'details': {'completion': {'complete': True},
                                        'canonical_ids': data.get('canonical_ids', []),
                                        'model_revision': data.get('model_revision')}})
            status = 'COMPLETED'
        else:
            message = str(data.get('reason') or 'Der Strukturvorschlag konnte nicht validiert werden.')
            findings = (proposal or {}).get('validation_result', {}).get('findings') or []
            event('RESULT', status='BLOCKED', text=message, findings=findings,
                  metadata={'details': data})
            status = 'BLOCKED'
        return {'run_id': run_id, 'status': status, 'events': events,
                'context': context.model_dump(mode='json'), 'trace': [{
                    'tool': 'plan_simple_project', 'trace_id': response.trace_id,
                    'status': response.status.value}], 'proposals': [proposal] if proposal else []}

    async def _periodic_acquisition(self, goal: EngineeringGoal, context: Any, *, emit,
                                    available_tools: set[str]) -> dict | None:
        """Expose the existing reviewed ECU generator without claiming E2E completion.

        Only its confirmed 30 s position-poll pattern is implemented. Other
        intervals still use the general agent until a transport-independent
        acquisition planner exists.
        """
        if not {'generate_functions', 'validate_proposal'} <= available_tools:
            return None
        periods = [item.get('seconds') for item in goal.timing_constraints if item.get('kind') == 'PERIOD']
        if periods != [30.0] or not any(word in goal.original_request.casefold()
                                        for word in ('stellgliedposition', 'aktorposition')):
            return None
        generated = await self.client.call('generate_functions', {'prompt': goal.original_request})
        run_id = getattr(getattr(context, 'input_envelope', None), 'run_ref', '')
        input_ref = getattr(getattr(context, 'input_envelope', None), 'input_id', '')
        events = []
        trace = [{'tool': 'generate_functions', 'trace_id': generated.trace_id,
                  'status': generated.status.value}]

        def event(kind: str, **fields):
            item = AgentResponse(type=kind, metadata={'run_id': run_id, 'input_ref': input_ref,
                'tool_trace_id': generated.trace_id, **fields.pop('metadata', {})},
                **fields).model_dump(mode='json', exclude_none=True)
            events.append(item)
            emit(item)

        if not generated.success:
            findings = generated.findings or []
            detail = next((str(item.get('message')) for item in findings if item.get('message')), '')
            event('RESULT', status='BLOCKED', findings=findings,
                  text='Die 30-Sekunden-Abfrage ist erkannt. Für einen geprüften ECU-Vorschlag fehlen '
                       'bestätigte Anschlusstechnologie oder Statuszyklus im aktuellen Modell. '
                       + detail,
                  metadata={'failure_code': 'PERIODIC_ACQUISITION_INPUT_GAP',
                            'missing_outcomes': goal.required_outcomes})
            return {'run_id': run_id, 'status': 'BLOCKED', 'events': events,
                    'context': context.model_dump(mode='json'), 'trace': trace, 'proposals': []}
        proposal = generated.data or {}
        if not proposal.get('proposal_id'):
            event('RESULT', status='BLOCKED', text='Der ECU-Generator hat keinen prüfbaren Vorschlag geliefert.',
                  metadata={'failure_code': 'PERIODIC_ACQUISITION_PROPOSAL_MISSING'})
            return {'run_id': run_id, 'status': 'BLOCKED', 'events': events,
                    'context': context.model_dump(mode='json'), 'trace': trace, 'proposals': []}
        validated = await self.client.call('validate_proposal', {'proposal_id': proposal['proposal_id']})
        trace.append({'tool': 'validate_proposal', 'trace_id': validated.trace_id,
                      'status': validated.status.value})
        proposal = validated.data or proposal
        if not validated.success or proposal.get('status') != 'VALIDATED':
            event('RESULT', status='BLOCKED', text='Der ECU-Entwurf konnte nicht validiert werden.',
                  findings=(proposal.get('validation_result') or {}).get('findings') or validated.findings,
                  metadata={'failure_code': 'PERIODIC_ACQUISITION_VALIDATION_FAILED'})
            return {'run_id': run_id, 'status': 'BLOCKED', 'events': events,
                    'context': context.model_dump(mode='json'), 'trace': trace, 'proposals': [proposal]}
        missing = ['Positionsdaten und Kodierung je Stellglied bestätigen',
                   'Anfrage/Antwort und Route im kanonischen Modell anlegen',
                   'Kapazität, E2E-Frist und Preflight nach der Modelländerung prüfen']
        event('APPROVAL', proposal=proposal,
              text='Die ECU mit einer Funktion für die Abfrage alle 30 Sekunden ist geprüft und kann '
                   'übernommen werden. Die Kommunikation ist damit noch nicht ausführbar; '
                   'Positionsdaten, Route und Timing bleiben offen.',
              metadata={'missing_engineering_steps': missing,
                        'completion_status': 'INCOMPLETE', 'period_ms': 30000})
        return {'run_id': run_id, 'status': 'READY_FOR_REVIEW', 'events': events,
                'context': context.model_dump(mode='json'), 'trace': trace, 'proposals': [proposal]}

    async def _network_configuration(self, goal: EngineeringGoal, context: Any, *, emit,
                                     available_tools: set[str]) -> dict | None:
        if 'plan_lin_bitrate' not in available_tools:
            return None
        planned = await self.client.call('plan_lin_bitrate', {
            'requirement': goal.original_request, 'workload_id': goal.goal_id})
        if not planned.success or not (planned.data or {}).get('supported'):
            return None
        data = planned.data
        run_id = getattr(getattr(context, 'input_envelope', None), 'run_ref', '')
        events = []
        trace = [{'tool': 'plan_lin_bitrate', 'trace_id': planned.trace_id,
                  'status': planned.status.value}]

        def event(kind: str, **fields):
            item = AgentResponse(type=kind, metadata={
                'run_id': run_id, 'input_ref': getattr(getattr(context, 'input_envelope', None), 'input_id', ''),
                'tool_trace_id': planned.trace_id, **fields.pop('metadata', {})},
                **fields).model_dump(mode='json', exclude_none=True)
            events.append(item)
            emit(item)

        proposal = data.get('proposal')
        if proposal and proposal.get('status') == 'VALIDATED':
            event('APPROVAL', proposal=proposal,
                  text=f"Das LIN-Netz {data['network_id']} wird auf {data['bitrate_bps']} bit/s gesetzt. "
                       'Nach der Freigabe werden Kapazität, Timing und Preflight neu berechnet.',
                  metadata={'model_revision_before': goal.project_context.get('model_revision'),
                            'network_id': data['network_id'], 'bitrate_bps': data['bitrate_bps']})
            status = 'READY_FOR_REVIEW'
        elif data.get('status') == 'ALREADY_CONFIGURED':
            if {'calculate_capacity', 'validate_simulation_preflight'} <= available_tools:
                capacity = await self.client.call('calculate_capacity', {})
                preflight = await self.client.call('validate_simulation_preflight', {})
                trace.extend([{'tool': 'calculate_capacity', 'trace_id': capacity.trace_id,
                               'status': capacity.status.value},
                              {'tool': 'validate_simulation_preflight', 'trace_id': preflight.trace_id,
                               'status': preflight.status.value}])
                capacity_data, preflight_data = capacity.data or {}, preflight.data or {}
                if (capacity_data.get('snapshot_id') and preflight_data.get('snapshot_id')):
                    evidence_refs = [data['network_id'], capacity_data['snapshot_id'], preflight_data['snapshot_id']]
                    event('RESULT', status='COMPLETED',
                          text=f"Das LIN-Netz {data['network_id']} hat bereits {data['bitrate_bps']} bit/s. "
                               f"Kapazität und Timing wurden neu berechnet; Preflight: {preflight_data.get('preflight_status') or preflight_data.get('status')}.",
                          metadata={'details': {'completion': {'complete': True},
                                                'capacity_status': capacity_data.get('status'),
                                                'preflight_status': preflight_data.get('preflight_status'),
                                                'evidence_refs': evidence_refs}})
                    status = 'COMPLETED'
                else:
                    event('RESULT', status='BLOCKED', text='Die LIN-Bitrate ist bereits gesetzt, aber die Neuberechnung konnte nicht vollständig nachgewiesen werden.',
                          findings=[*capacity.findings, *preflight.findings])
                    status = 'BLOCKED'
            else:
                event('RESULT', status='BLOCKED', text='Für die angeforderte Neuberechnung fehlen Kapazitäts- oder Preflight-Werkzeuge.')
                status = 'BLOCKED'
        else:
            event('RESULT', status='BLOCKED', text=str(data.get('reason') or 'LIN-Netz konnte nicht bestimmt werden.'),
                  findings=data.get('findings') or [], metadata={'candidates': data.get('candidates') or [],
                          'failure_code': 'NETWORK_CONFIGURATION_DECISION_REQUIRED'})
            status = 'BLOCKED'
        return {'run_id': run_id, 'status': status, 'events': events,
                'context': context.model_dump(mode='json'), 'trace': trace,
                'proposals': [proposal] if proposal else []}

    async def _message_timing_diagnosis(self, goal: EngineeringGoal, context: Any, *, emit,
                                        available_tools: set[str]) -> dict | None:
        request = goal.original_request.casefold()
        if 'inspect_message_timing' not in available_tools or not any(
                word in request for word in ('zu spät', 'zu spaet', 'latenz', 'deadline', 'laufzeit')):
            return None
        inspected = await self.client.call('inspect_message_timing', {'request': goal.original_request})
        if not inspected.success:
            return None
        data = inspected.data or {}
        run_id = getattr(getattr(context, 'input_envelope', None), 'run_ref', '')
        status = data.get('status')
        message = data.get('message') or {}
        routes = data.get('routes') or []
        trace = [{'tool': 'inspect_message_timing', 'trace_id': inspected.trace_id,
                  'status': inspected.status.value}]
        sequence = data.get('sequence') or {}
        trace_analysis = None
        if (sequence.get('status') == 'SIMULATED' and sequence.get('job_id') and message.get('id')
                and 'inspect_message_trace_timing' in available_tools):
            traced = await self.client.call('inspect_message_trace_timing', {
                'job_id': sequence['job_id'], 'message_id': str(message['id']), 'request': goal.original_request[:2000]})
            trace.append({'tool': 'inspect_message_trace_timing', 'trace_id': traced.trace_id,
                          'status': traced.status.value})
            candidate = traced.data if isinstance(traced.data, dict) else {}
            lineage = candidate.get('lineage') or {}
            versions = lineage.get('source_versions') or {}
            if (traced.success and candidate.get('project_id') == context.active_project_id
                    and candidate.get('simulation_run_id') == sequence['job_id']
                    and lineage.get('message_id') == str(message['id']) and versions
                    and all(value == (sequence.get('source_versions') or {}).get(key) for key, value in versions.items())
                    and candidate.get('validation_status') == 'CURRENT'):
                trace_analysis = candidate
                data = {**data, 'trace_analysis': trace_analysis}
        if status == 'MODEL_DEADLINE_FAIL':
            late = [item for item in routes if item.get('latency_status') == 'FAIL']
            worst = max(late, key=lambda item: float(item.get('end_to_end_latency_ms') or 0))
            bottleneck = worst.get('bottleneck') or {}
            text = (f"Für {message.get('name')} berechnet das aktuelle Modell auf Route {worst['route_id']} "
                    f"{worst['end_to_end_latency_ms']} ms E2E-Latenz bei {worst['max_latency_ms']} ms Frist. "
                    f"Der größte berechnete Anteil ist {bottleneck.get('component') or 'unbekannt'} "
                    f"mit {bottleneck.get('delay_ms') or 0} ms. "
                    'Das ist eine Modellrechnung; eine tatsächlich verspätete Zustellung benötigt '
                    'einen zugeordneten Simulation- oder Import-Trace als Nachweis.')
            result_status = 'INCOMPLETE'
        elif status == 'MODEL_DEADLINE_PASS':
            worst = max(routes, key=lambda item: float(item.get('end_to_end_latency_ms') or 0))
            text = (f"Das aktuelle Modell berechnet für {message.get('name')} höchstens "
                    f"{worst['end_to_end_latency_ms']} ms auf Route {worst['route_id']} "
                    f"bei {worst['max_latency_ms']} ms Frist; eine Überschreitung ist hier nicht berechnet. "
                    'Für einen beobachteten verspäteten Empfang wird ein zugeordneter Trace benötigt.')
            result_status = 'INCOMPLETE'
        else:
            text = str(data.get('reason') or 'Die Latenz dieser Nachricht ist mit den aktuellen Modelldaten nicht belegbar.')
            result_status = 'BLOCKED'
        if sequence.get('status') == 'SIMULATED':
            import math
            latencies = [item['transport_latency_ms'] for item in sequence.get('transactions') or []
                         if type(item.get('transport_latency_ms')) in (int, float)
                         and math.isfinite(item['transport_latency_ms']) and item['transport_latency_ms'] >= 0]
            confirmed = set((trace_analysis or {}).get('confirmed_causes') or [])
            timing_faults = {'MESSAGE_DELAY', 'GATEWAY_DELAY', 'MESSAGE_JITTER', 'MESSAGE_WRONG_CYCLE',
                             'NETWORK_OVERLOAD', 'CONGESTION', 'QUEUE_OVERFLOW', 'BURST_TRAFFIC'}
            hypotheses = [item for item in (trace_analysis or {}).get('hypotheses') or []
                          if item.get('id') in confirmed and item.get('status') == 'SUPPORTED'
                          and (str(item.get('id')).startswith('queue:')
                               or str(item.get('id')).startswith('fault:') and str(item['id']).rsplit(':', 1)[-1] in timing_faults)]
            late = any(item.get('deadline_status') == 'FAIL' for item in sequence.get('transactions') or [])
            timing_effect = any(item.get('type') == 'DEADLINE_MISS' for item in (trace_analysis or {}).get('observations') or [])
            if latencies and late and timing_effect and hypotheses and trace_analysis.get('completion_status') == 'COMPLETE':
                maximum = max(latencies)
                model_times = [item['end_to_end_latency_ms'] for item in routes
                               if type(item.get('end_to_end_latency_ms')) in (int, float)
                               and math.isfinite(item['end_to_end_latency_ms'])]
                text = (f"Der zugeordnete Simulations-Trace zeigt für {message.get('name')} "
                        f"bis zu {maximum:g} ms Transportlaufzeit. ")
                if model_times:
                    text += f"Die statische Modellrechnung beträgt höchstens {max(model_times):g} ms. "
                text += ' '.join(str(item['description']) for item in hypotheses[:3])
                raw = [item.get('details') or {} for item in trace_analysis.get('evidence_refs') or []
                       if item.get('source_type') == 'TraceEvent']
                parts = []
                for field, label in [('configured_latency_ms', 'zusätzliche Verzögerung'),
                                     ('transmission_latency_ms', 'Übertragung'), ('queue_delay_ms', 'Warteschlange')]:
                    values = [row[field] for row in raw if type(row.get(field)) in (int, float)
                              and math.isfinite(row[field]) and row[field] >= 0]
                    if values:
                        parts.append(f'{label} bis {max(values):g} ms')
                if parts:
                    text += ' Trace-Anteile: ' + ', '.join(parts) + '.'
                text += ' Dies ist ein Simulationsnachweis; eine reale Zustellung oder funktionale Empfängerannahme ist damit nicht bestätigt.'
                result_status = 'ANSWERED'
            else:
                text = (f"Für {message.get('name')} liegt ein zugeordneter Simulations-Trace vor. "
                        'Die nachrichtenbezogene Ursachenanalyse ist noch nicht vollständig bestätigt; '
                        'die Modellrechnung und die verfügbaren Trace-Nachweise stehen in der Auswertung. '
                        'Eine funktionale Empfängerannahme wird daraus nicht abgeleitet.')
                result_status = 'INCOMPLETE'
        event = AgentResponse(type='RESULT', status=result_status, text=text,
            metadata={'run_id': run_id, 'input_ref': getattr(getattr(context, 'input_envelope', None), 'input_id', ''),
                      'tool_trace_id': inspected.trace_id, 'details': data,
                      'failure_code': status if result_status == 'BLOCKED' else None,
                      'evidence_kind': 'CALCULATED_MODEL_AND_SIMULATION' if trace_analysis else 'CALCULATED_MODEL'}).model_dump(mode='json', exclude_none=True)
        emit(event)
        return {'run_id': run_id, 'status': result_status, 'events': [event],
                'context': context.model_dump(mode='json'),
                'trace': trace, 'proposals': []}
