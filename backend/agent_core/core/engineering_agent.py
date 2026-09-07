"""Engineering orchestration. No SQL, repositories or simulator domain imports."""
from __future__ import annotations

import asyncio
import re
from typing import Callable
from uuid import uuid4
from ..api.mcp_client import EngineeringMCPClient
from ..api.tool_contract import ToolResult
from ..context.agent_context import AgentContext
from ..api.agent_response import AgentResponse, InteractiveQuestion, validate_response


def reasoning_workload_progress(step: int, max_steps: int) -> dict[str, int]:
    """Expose bounded reasoning iterations as structured progress telemetry."""
    total = max(1, min(int(max_steps), 24))
    return {"completed": min(max(0, int(step)) + 1, total), "total": total}


class EngineeringAgent:
    def __init__(self, client: EngineeringMCPClient, *, reasoner=None, max_steps: int = 12, max_repairs: int = 3):
        self.client = client
        self.reasoner = reasoner
        self.max_steps = min(max_steps, 24)
        self.max_repairs = min(max_repairs, 5)

    async def run(self, prompt: str, context: AgentContext, *, emit: Callable[[dict], None] | None = None, history: list[dict] | None = None) -> dict:
        events, proposals, traces = [], {}, []
        run_id = str(uuid4())
        def event(kind, **data):
            metadata = {'run_id': run_id, **data.pop('metadata', {})}
            if 'data' in data:
                metadata['details'] = data.pop('data')
            if kind in {'QUESTION', 'SINGLE_SELECT', 'MULTI_SELECT'} and not data.get('question'):
                options = [{**{k:v for k,v in option.items() if k != 'value'}, 'id': option.get('id') or option.get('value')}
                    for option in data.pop('options', [])]
                metadata['decision_key'] = data.pop('question_id', str(uuid4()))
                data['question'] = {'id': str(uuid4()), 'question': data.get('text', ''),
                    'selection_mode': 'MULTI' if kind == 'MULTI_SELECT' else 'SINGLE', 'options': options}
            if not data.get('context_refs'):
                data['context_refs'] = context.selected_object_refs
            if data.get('question') and not data['question'].get('context_refs'):
                data['question']['context_refs'] = context.selected_object_refs
            if kind == 'PROGRESS' and 'progress' not in data:
                stages = ['Anforderung verstehen', 'Modell prüfen', 'Vorschlag vorbereiten', 'Validieren']
                index = {'RECEIVED':0, 'PLANNING':1, 'IN_PROGRESS':2, 'VALIDATING':3, 'READY_FOR_REVIEW':4}.get(data.get('status'), 2)
                data['progress'] = [{'label':label, 'status':'done' if i < index else 'active' if i == index else 'pending'} for i, label in enumerate(stages)]
            item = validate_response({"type": kind, 'metadata': metadata, **data})
            events.append(item)
            if emit:
                emit(item)
        async def call(name, arguments=None):
            result = await self.client.call(name, arguments)
            traces.append({"tool": name, "trace_id": result.trace_id, "status": result.status.value})
            if not result.success:
                for finding in result.findings:
                    event("FINDING", severity=finding.get("severity", "ERROR"), text=finding.get("message", str(finding)))
            return result
        async def validate_proposal(proposal):
            result = await call("validate_proposal", {"proposal_id": proposal["proposal_id"]})
            if result.success:
                proposals[result.data["proposal_id"]] = result.data
                return result.data
            return proposal
        answer = bool(context.answered_questions)
        if not answer:
            context = context.model_copy(update={"current_requirement": prompt})
        if context.current_workload and not re.search(r"weiter|fort|status|prüf|pruef|continue|resume",prompt,re.I):
            context.current_workload = None
        event("PROGRESS", status="RECEIVED", text="Auftrag aufgenommen.")
        project = await call("inspect_project")
        if not project.success:
            return {"status":"BLOCKED","events":events,"context":context.model_dump(),"trace":traces}
        stored_context = project.data.get("context") or {}
        context.active_workflow = project.data.get("active_step",context.active_workflow)
        selected = stored_context.get("selected_object")
        if isinstance(selected,dict) and selected.get("id") and not context.selected_object_refs:
            context.selected_object_refs = [{"id":str(selected["id"]),"object_type":str(selected.get("object_type") or selected.get("type") or "")}]
        event("PROGRESS", status="PLANNING", text="Projektstand und benötigte Arbeitsschritte prüfen.")

        if context.active_proposal and not context.current_workload:
            restored = await call('inspect_proposal', {'proposal_id':context.active_proposal})
            if restored.success and restored.data['status'] in {'VALIDATED', 'READY_FOR_REVIEW', 'APPROVED'}:
                event('APPROVAL', proposal=restored.data, text=restored.data['rationale'])
                event('RESULT', status=restored.data['status'], text='Der gespeicherte Vorschlag ist wiederhergestellt. Bitte seinen aktuellen Prüfstatus beachten.')
                return {'run_id':run_id, 'status':restored.data['status'], 'events':events, 'context':context.model_dump(), 'trace':traces, 'proposals':[restored.data]}
            context.active_proposal = None

        # Confirmed wizard creation precedes free-text heuristics: words such as
        # "welche" in an attached specification must not turn it into a query.
        confirmed_wizard = ('Strukturierte Vorgaben fuer den Engineering-Agenten:' in prompt
                and 'per Wizard-Uebernehmen bestaetigt' in prompt
                and re.search(r'^- Hardware-Sollwerte:\s*\{', prompt, re.M))
        if confirmed_wizard and not project.data.get('artifact_checks', {}).get('engineering_model', {}).get('complete'):
            event('PROGRESS', status='PLANNING', text='Engineering-Modell aus den bestätigten Wizard-Vorgaben vorbereiten.')
            result = await call('generate_wizard_model', {'prompt': prompt})
            if result.success:
                proposal = await validate_proposal(result.data)
                valid = proposal.get('status') == 'VALIDATED'
                event('PROGRESS', status='VALIDATING', text=f"{len(proposal['changes'])} Modelländerungen geprüft.",
                      workload={'completed': len(proposal['changes']) if valid else 0, 'total': len(proposal['changes'])})
                event('APPROVAL', proposal=proposal, text=proposal['rationale'])
                status = 'READY_FOR_REVIEW' if valid else 'INCOMPLETE'
                text = ('Das Engineering-Modell ist als geprüfter Vorschlag vorbereitet. Bitte die Modelländerungen freigeben; die weiteren Workflow-Schritte sind noch offen.'
                        if valid else 'Der Modellvorschlag benötigt Korrekturen. Die Validierung zeigt die konkreten Findings.')
            else:
                status = 'INCOMPLETE'
                text = 'Der Wizard-Generator konnte den Modellvorschlag nicht vorbereiten. ' + '; '.join(str(f.get('message', '')) for f in result.findings)
            event('RESULT', status=status, text=text)
            return {'run_id': run_id, 'status': status, 'text': text, 'events': events,
                    'context': context.model_dump(), 'trace': traces, 'proposals': list(proposals.values())}

        # A confirmed continuation has a deterministic server-side generator.
        # Do not ask the reasoner to infer hundreds of calls from the mass model.
        wizard_target = re.search(r'Fortsetzung des bestätigten Wizard-Auftrags:.*?Ziel:\s*([a-z_]+)', prompt, re.I | re.S)
        workflow_order = ['engineering_model', 'routing', 'network_editor', 'parameters', 'capacity_timing',
                          'validation', 'simulation', 'results_analysis', 'data_science_intelligence']
        target = wizard_target.group(1).casefold() if wizard_target else None
        target_index = workflow_order.index(target) if target in workflow_order else -1
        routing_complete = project.data.get('artifact_checks', {}).get('routing', {}).get('complete', False)
        topology_complete = project.data.get('artifact_checks', {}).get('network_editor', {}).get('complete', False)
        parameters_complete = project.data.get('artifact_checks', {}).get('parameters', {}).get('complete', False)
        workflow_statuses = project.data.get('statuses', {})
        capacity_complete = workflow_statuses.get('capacity_timing') in {'COMPLETE', 'APPROVED', 'WARNING'}
        validation_complete = workflow_statuses.get('validation') in {'COMPLETE', 'APPROVED', 'WARNING'}
        simulation_complete = workflow_statuses.get('simulation') in {'COMPLETE', 'APPROVED', 'WARNING'}
        results_complete = workflow_statuses.get('results_analysis') in {'COMPLETE', 'APPROVED', 'WARNING'}
        intelligence_complete = workflow_statuses.get('data_science_intelligence') in {'COMPLETE', 'APPROVED', 'WARNING'}
        if confirmed_wizard and target_index >= workflow_order.index('routing') and not routing_complete:
            event('PROGRESS', status='PLANNING', text='Routing aus dem bestätigten Systemcluster-Graph vorbereiten.')
            result = await call('generate_wizard_routing', {'prompt': prompt})
            if result.success:
                proposal = await validate_proposal(result.data)
                valid = proposal.get('status') == 'VALIDATED'
                event('PROGRESS', status='VALIDATING', text=f"{len(proposal['changes'])} Routen geprüft.",
                      workload={'completed': len(proposal['changes']) if valid else 0, 'total': len(proposal['changes'])})
                event('APPROVAL', proposal=proposal, text=proposal['rationale'])
                status = 'READY_FOR_REVIEW' if valid else 'INCOMPLETE'
                text = ('Der Routing-Vorschlag ist vollständig erzeugt und wartet auf die fachliche Freigabe.' if valid
                        else 'Der Routing-Vorschlag wurde erzeugt, enthält aber noch konkrete Validierungsfehler.')
            else:
                status = 'INCOMPLETE'
                text = 'Der serverseitige Routing-Generator konnte den bestätigten Auftrag nicht umsetzen. ' + '; '.join(str(f.get('message', '')) for f in result.findings)
            event('RESULT', status=status, text=text)
            return {'run_id': run_id, 'status': status, 'text': text, 'events': events,
                    'context': context.model_dump(), 'trace': traces, 'proposals': list(proposals.values())}

        if confirmed_wizard and target_index >= workflow_order.index('network_editor') and routing_complete and not topology_complete:
            event('PROGRESS', status='PLANNING', text='Physische Netzwerktopologie aus den freigegebenen Routen vorbereiten.')
            result = await call('generate_wizard_network', {'prompt': prompt})
            if result.success:
                proposal = await validate_proposal(result.data)
                valid = proposal.get('status') == 'VALIDATED'
                topology_change = next((change for change in proposal.get('changes', [])
                                        if change.get('object_type') == 'NetworkTopology'), {})
                topology = (topology_change.get('data') or {}).get('topology') or {}
                nodes = len(topology.get('nodes') or [])
                edges = len(topology.get('edges') or [])
                event('PROGRESS', status='VALIDATING', text=f'{nodes} Geräte und {edges} Netzsegmente geprüft.',
                      workload={'completed': nodes + edges if valid else 0, 'total': nodes + edges})
                event('APPROVAL', proposal=proposal, text=proposal['rationale'])
                status = 'READY_FOR_REVIEW' if valid else 'INCOMPLETE'
                text = ('Die physische Netzwerktopologie ist vollständig erzeugt und wartet auf die fachliche Freigabe.' if valid
                        else 'Die Netzwerktopologie wurde erzeugt, enthält aber noch konkrete Validierungsfehler.')
            else:
                status = 'INCOMPLETE'
                text = 'Der serverseitige Netzwerk-Generator konnte den bestätigten Auftrag nicht umsetzen. ' + '; '.join(str(f.get('message', '')) for f in result.findings)
            event('RESULT', status=status, text=text)
            return {'run_id': run_id, 'status': status, 'text': text, 'events': events,
                    'context': context.model_dump(), 'trace': traces, 'proposals': list(proposals.values())}

        # Capacity and preflight are deterministic analyses over canonical,
        # already reviewed artifacts. They do not need an LLM tool choice or a
        # second proposal store, and may run consecutively until a real finding
        # or the next human review gate is reached.
        if (confirmed_wizard and target_index >= workflow_order.index('capacity_timing')
                and topology_complete and parameters_complete and not capacity_complete):
            event('PROGRESS', status='PLANNING', text='Capacity & Timing aus Routing, Topologie und Parametern berechnen.')
            result = await call('calculate_capacity', {})
            if not result.success:
                status = 'INCOMPLETE'
                text = 'Capacity & Timing konnte nicht berechnet werden. ' + '; '.join(
                    str(f.get('message', '')) for f in result.findings)
                event('RESULT', status=status, text=text)
                return {'run_id': run_id, 'status': status, 'text': text, 'events': events,
                        'context': context.model_dump(), 'trace': traces, 'proposals': []}
            overview = (result.data.get('results') or {}).get('overview') or {}
            route_count = int(overview.get('route_count') or 0)
            message_count = len((result.data.get('results') or {}).get('messages') or [])
            network_count = int(overview.get('network_count') or 0)
            total = route_count + message_count + network_count
            capacity_complete = str(result.data.get('status') or '').upper() in {'COMPLETE', 'APPROVED', 'WARNING'}
            event('PROGRESS', status='VALIDATING',
                  text=f'{network_count} Netze, {route_count} Routen und {message_count} Nachrichten berechnet.',
                  workload={'completed': total if capacity_complete else 0, 'total': total})
            if not capacity_complete:
                status = 'INCOMPLETE'
                text = 'Capacity & Timing wurde berechnet, enthält aber blockierende Befunde.'
                event('RESULT', status=status, text=text)
                return {'run_id': run_id, 'status': status, 'text': text, 'events': events,
                        'context': context.model_dump(), 'trace': traces, 'proposals': []}
            if target_index == workflow_order.index('capacity_timing'):
                status = 'COMPLETED'
                text = 'Capacity & Timing ist vollständig aus dem aktuellen kanonischen Projektstand berechnet.'
                event('RESULT', status=status, text=text)
                return {'run_id': run_id, 'status': status, 'text': text, 'events': events,
                        'context': context.model_dump(), 'trace': traces, 'proposals': []}

        if (confirmed_wizard and target_index >= workflow_order.index('validation')
                and topology_complete and parameters_complete and capacity_complete and not validation_complete):
            event('PROGRESS', status='PLANNING', text='Verbindlichen Workflow-Preflight ausführen.')
            result = await call('validate_simulation_preflight', {})
            if not result.success:
                finding_codes = {str(item.get('code') or '') for item in result.findings}
                if finding_codes and finding_codes <= {'NETWORK_NODE_DISCONNECTED'}:
                    repair = await call('generate_wizard_network', {'prompt': prompt})
                    if repair.success:
                        proposal = await validate_proposal(repair.data)
                        valid = proposal.get('status') == 'VALIDATED'
                        event('APPROVAL', proposal=proposal, text=proposal['rationale'])
                        status = 'READY_FOR_REVIEW' if valid else 'INCOMPLETE'
                        text = ('Capacity & Timing ist vollständig. Für die im Preflight erkannten unverbundenen '
                                'Teilnehmer wurde eine physisch vollständige Topologie zur Freigabe vorbereitet.'
                                if valid else 'Die Topologie-Reparatur enthält noch konkrete Validierungsfehler.')
                        event('RESULT', status=status, text=text)
                        return {'run_id': run_id, 'status': status, 'text': text, 'events': events,
                                'context': context.model_dump(), 'trace': traces,
                                'proposals': list(proposals.values())}
                status = 'INCOMPLETE'
                text = ('Capacity & Timing ist berechnet. Der anschließende Preflight hat konkrete '
                        'blockierende Befunde gefunden; diese müssen vor der Simulation behoben werden.')
                event('RESULT', status=status, text=text)
                return {'run_id': run_id, 'status': status, 'text': text, 'events': events,
                        'context': context.model_dump(), 'trace': traces, 'proposals': []}
            checked = len(result.data.get('checked_steps') or [])
            warnings = int(result.data.get('warning_count') or 0)
            event('PROGRESS', status='VALIDATING',
                  text=f'Preflight über {checked} Workflow-Bereiche abgeschlossen; {warnings} Warnungen.',
                  workload={'completed': checked, 'total': checked})
            status = 'COMPLETED' if target_index == workflow_order.index('validation') else 'READY_TO_CONTINUE'
            text = ('Der Workflow-Preflight ist abgeschlossen.' if status == 'COMPLETED'
                    else 'Capacity & Timing und Workflow-Preflight sind abgeschlossen. Als Nächstes wird der unveränderliche Simulationssnapshot ausgeführt.')
            event('RESULT', status=status, text=text)
            return {'run_id': run_id, 'status': status, 'text': text, 'events': events,
                    'context': context.model_dump(), 'trace': traces, 'proposals': []}

        # A confirmed wizard run owns a bounded, reproducible normal simulation.
        # Reuse an already prepared/running snapshot so an explicit retry never
        # creates a second job for the same canonical project state.
        if (confirmed_wizard and target_index >= workflow_order.index('simulation')
                and validation_complete and not simulation_complete):
            event('PROGRESS', status='PLANNING', text='Aktuellen Preflight-Stand als SimulationSnapshot vorbereiten.')
            snapshots = project.data.get('simulation_snapshots') or []
            current_snapshot = next((item for item in snapshots
                                     if not item.get('is_outdated') and str(item.get('status') or '').upper()
                                     in {'READY', 'RUNNING'}), None)
            if current_snapshot is None:
                snapshot_result = await call('create_simulation_snapshot', {'configuration': {
                    'duration_s': 1.0,
                    'seed': 42,
                    'max_events': 100_000,
                    'formats': ['universal-jsonl', 'universal-csv'],
                    'scenario': {'mode': 'NORMAL', 'faults': []},
                }})
                if not snapshot_result.success:
                    status = 'INCOMPLETE'
                    text = 'Der validierte Simulationssnapshot konnte nicht angelegt werden. ' + '; '.join(
                        str(f.get('message', '')) for f in snapshot_result.findings)
                    event('RESULT', status=status, text=text)
                    return {'run_id': run_id, 'status': status, 'text': text, 'events': events,
                            'context': context.model_dump(), 'trace': traces, 'proposals': []}
                current_snapshot = snapshot_result.data

            snapshot_id = str(current_snapshot.get('id') or '')
            job_id = str(current_snapshot.get('job_id') or '')
            snapshot_status = str(current_snapshot.get('status') or '').upper()
            if not job_id and snapshot_status == 'READY':
                start_result = await call('start_simulation', {'snapshot_id': snapshot_id})
                if not start_result.success:
                    status = 'INCOMPLETE'
                    text = 'Der SimulationSnapshot wurde erstellt, konnte aber nicht gestartet werden. ' + '; '.join(
                        str(f.get('message', '')) for f in start_result.findings)
                    event('RESULT', status=status, text=text)
                    return {'run_id': run_id, 'status': status, 'text': text, 'events': events,
                            'context': context.model_dump(), 'trace': traces, 'proposals': []}
                job_id = str(start_result.data.get('id') or '')
            if not job_id:
                status = 'INCOMPLETE'
                text = 'Der SimulationSnapshot besitzt keine ausführbare Job-ID.'
                event('RESULT', status=status, text=text)
                return {'run_id': run_id, 'status': status, 'text': text, 'events': events,
                        'context': context.model_dump(), 'trace': traces, 'proposals': []}

            job = None
            for attempt in range(240):
                status_result = await call('get_simulation_status', {'job_id': job_id})
                if not status_result.success:
                    status = 'INCOMPLETE'
                    text = 'Der gestartete Simulationslauf konnte nicht mehr gelesen werden. ' + '; '.join(
                        str(f.get('message', '')) for f in status_result.findings)
                    event('RESULT', status=status, text=text)
                    return {'run_id': run_id, 'status': status, 'text': text, 'events': events,
                            'context': context.model_dump(), 'trace': traces, 'proposals': []}
                job = status_result.data
                job_status = str(job.get('status') or '').lower()
                if job_status in {'completed', 'failed', 'canceled'}:
                    break
                if attempt % 20 == 0:
                    event('PROGRESS', status='IN_PROGRESS', text='Simulation läuft auf dem unveränderlichen Projektstand.',
                          workload={'completed': attempt, 'total': 240})
                await asyncio.sleep(0.25)
            job_status = str((job or {}).get('status') or '').lower()
            if job_status != 'completed':
                status = 'INCOMPLETE'
                detail = str((job or {}).get('error') or ('Zeitfenster überschritten' if job_status not in {'failed', 'canceled'} else job_status))
                text = f'Der Simulationslauf wurde nicht erfolgreich abgeschlossen: {detail}.'
                event('RESULT', status=status, text=text)
                return {'run_id': run_id, 'status': status, 'text': text, 'events': events,
                        'context': context.model_dump(), 'trace': traces, 'proposals': []}

            refreshed = await call('inspect_project')
            refreshed_statuses = refreshed.data.get('statuses', {}) if refreshed.success else {}
            simulation_complete = refreshed_statuses.get('simulation') in {'COMPLETE', 'APPROVED', 'WARNING'}
            results_complete = refreshed_statuses.get('results_analysis') in {'COMPLETE', 'APPROVED', 'WARNING'}
            if not simulation_complete or not results_complete:
                status = 'INCOMPLETE'
                text = 'Die Simulation ist beendet, aber der kanonische Results-/Analysis-Nachweis ist unvollständig.'
            else:
                status = 'COMPLETED' if target_index <= workflow_order.index('results_analysis') else 'READY_TO_CONTINUE'
                text = ('Simulation und Results / Analysis sind vollständig abgeschlossen.' if status == 'COMPLETED'
                        else 'Simulation und Results / Analysis sind vollständig abgeschlossen. Als Nächstes folgt Data Science & Intelligence.')
            event('PROGRESS', status='VALIDATING', text='Simulationslauf und Ergebnisartefakte kanonisch geprüft.',
                  workload={'completed': 1 if simulation_complete and results_complete else 0, 'total': 1})
            event('RESULT', status=status, text=text)
            return {'run_id': run_id, 'status': status, 'text': text, 'events': events,
                    'context': context.model_dump(), 'trace': traces, 'proposals': []}

        if (confirmed_wizard and target_index >= workflow_order.index('data_science_intelligence')
                and simulation_complete and results_complete and not intelligence_complete):
            event('PROGRESS', status='PLANNING', text='Data Science & Intelligence aus den verifizierten Simulationsergebnissen bewerten.')
            result = await call('assess_intelligence', {})
            if not result.success:
                status = 'INCOMPLETE'
                text = 'Data Science & Intelligence konnte nicht erzeugt werden. ' + '; '.join(
                    str(f.get('message', '')) for f in result.findings)
            else:
                intelligence_status = str(result.data.get('status') or '').upper()
                intelligence_complete = intelligence_status in {'COMPLETE', 'APPROVED', 'WARNING'}
                findings = result.data.get('findings') or []
                status = 'COMPLETED' if intelligence_complete else 'INCOMPLETE'
                text = (f'Data Science & Intelligence ist mit {len(findings)} nachvollziehbaren Befunden abgeschlossen.'
                        if intelligence_complete else 'Die Systembewertung enthält blockierende Befunde und ist noch nicht abgeschlossen.')
                event('PROGRESS', status='VALIDATING', text=f'{len(findings)} Intelligence-Befunde bewertet.',
                      workload={'completed': len(findings) if intelligence_complete else 0,
                                'total': len(findings)})
            event('RESULT', status=status, text=text)
            return {'run_id': run_id, 'status': status, 'text': text, 'events': events,
                    'context': context.model_dump(), 'trace': traces, 'proposals': []}

        # Explicit structured decisions precede the existing proposal pipeline.
        if re.search(r'kamera|camera', prompt, re.I) and re.search(r'umfeld|umgebung|überwach|ueberwach|erkenn|vision|360', prompt, re.I) and not re.search(r'^\s*(zeige|liste|welche|inspect)|\d+\s+(?:Funktion(?:en)?|functions?|Signal(?:e)?|signals?)\b', prompt, re.I):
            from ..orchestration.camera_dialog import next_camera_decision
            decision = next_camera_decision(context.answered_questions)
            if decision:
                event(decision.pop('type'), **decision)
                return {'run_id':run_id, 'status':'BLOCKED', 'events':events, 'context':context.model_dump(), 'trace':traces}
            choices = {key: value['selected_options'] for key, value in context.answered_questions.items()}
            result = await call('generate_camera_architecture', {'coverage':choices['camera_coverage'][0],
                'outputs':choices['camera_outputs'], 'profile':choices['camera_profile'][0], 'prompt':prompt})
            if result.success:
                proposal = await validate_proposal(result.data)
                event('RECOMMENDATION', title='Kameraarchitektur', text='Die ausgewählte Sensoranordnung mit Vision Controller und Ethernet-Schnittstellen ist als prüfbarer Strukturvorschlag vorbereitet.',
                    recommendation={'Änderungen':len(proposal['changes']), 'Sensorprofil':choices['camera_profile'][0], 'Ausgaben':len(choices['camera_outputs'])},
                    actions=[{'type':'DETAILS','label':'Details anzeigen'}])
                event('FINDING', title='Kommunikation noch zu dimensionieren', severity='WARNING',
                    text='Der Strukturvorschlag legt noch keine belastbare Bandbreite oder Ende-zu-Ende-Latenz fest. Auflösung, Bildrate, Kodierung und Netzwerktopologie müssen vor Routing und Simulation geprüft werden.',
                    actions=[{'type':'NAVIGATE','object_type':'Capacity','label':'Kapazität und Timing öffnen'}])
                event('APPROVAL', proposal=proposal, text=proposal['rationale'])
            status = 'READY_FOR_REVIEW' if proposals and all(p['status']=='VALIDATED' for p in proposals.values()) else 'INCOMPLETE'
            event('RESULT', status=status, text='Der Architekturvorschlag ist erstellt. Den aktuellen Prüf- und Übernahmestand zeigt die Vorschlagskarte.' if status == 'READY_FOR_REVIEW' else 'Die Architektur benötigt weitere Korrekturen; die Findings zeigen die Ursache.')
            return {'run_id':run_id, 'status':status, 'events':events, 'context':context.model_dump(), 'trace':traces, 'proposals':list(proposals.values())}

        # Signal counts are interpreted and checked by the existing Python
        # workload planner behind MCP, not by the language model.
        signal_request = bool(re.search(r"\d+.*signal|signal.*\d+", prompt, re.I)) and not re.search(r"\b(welche|zeige|liste|list|inspect)\b", prompt, re.I)
        if context.current_workload or (signal_request and not confirmed_wizard):
            workload_id = context.current_workload
            if not workload_id:
                result = await call("create_workload", {"request":{"prompt":prompt,"workload_type":"SIGNAL_GENERATION",
                    "constraints":context.user_constraints,"max_generation_attempts":self.max_repairs}})
                if not result.success:
                    return {"status":"INCOMPLETE","events":events,"context":context.model_dump(),"trace":traces}
                workload_id = str(result.data["workload_id"])
                context.current_workload = workload_id
                await call("start_workload", {"workload_id":workload_id})
            for attempt in range(self.max_repairs+1):
                result = await call("validate_workload", {"workload_id":workload_id})
                progress = await call("get_workload_progress", {"workload_id":workload_id})
                if not result.success or not progress.success:
                    break
                data = progress.data
                event("PROGRESS", status=data["status"], text=f"{data['valid']} von {data['requested']} gültig.", workload=data)
                if data["status"] in {"READY_FOR_REVIEW", "COMPLETED", "BLOCKED", "FAILED", "CANCELED"}:
                    break
                if attempt == self.max_repairs:
                    break
                event("PROGRESS", status="REPAIRING", text="Fehlende oder ungültige Ergebnisse gezielt nacharbeiten.")
                await call("repair_workload" if data["invalid"] else "generate_missing", {"workload_id":workload_id})
            progress = await call("get_workload_progress", {"workload_id":workload_id})
            status = progress.data.get("status", "INCOMPLETE") if progress.success else "BLOCKED"
            if status == "READY_FOR_REVIEW":
                review = await call("prepare_workload_review", {"workload_id":workload_id})
                if review.success:
                    proposals.update({p["proposal_id"]:p for p in review.data["proposals"]})
                    if not proposals or not all(p["status"] == "VALIDATED" for p in proposals.values()):
                        status = "INCOMPLETE"
                else:
                    status = "INCOMPLETE"
            text = ("Alle Zielzahlen und Prüfkriterien sind erfüllt. Die Vorschläge warten auf deine Freigabe."
                    if status == "READY_FOR_REVIEW" else "Der Auftrag ist vollständig übernommen."
                    if status == "COMPLETED" else "Der Auftrag ist noch offen. Die Findings zeigen die fehlenden Voraussetzungen.")
        elif not answer and re.search(r"erzeug|erstell|benötig|benoetig|entwerf|modelli|generate|create", prompt, re.I) and re.search(r"funktion|function", prompt, re.I) and not re.search(r"vollständig|komplett|gesamte|complete|full", prompt, re.I):
            selected = next((ref for ref in context.selected_object_refs if ref.get("object_type")=="HardwareNode"), {})
            result = await call("generate_functions", {"prompt":prompt,"domain":context.project_domain,"hardware_id":selected.get("id")})
            if result.success:
                await validate_proposal(result.data)
            status = "READY_FOR_REVIEW" if proposals and all(p["status"]=="VALIDATED" for p in proposals.values()) else "INCOMPLETE"
            text = "Der Funktionsvorschlag ist zur Prüfung bereit." if status=="READY_FOR_REVIEW" else "Der Vorschlag benötigt weitere Angaben oder Korrekturen."
        else:
            messages = [*(history or [])[-12:], {"role":"user","content":prompt}]
            tools = await self.client.tools()
            from ..orchestration.tool_selection import select_tools
            allowed = select_tools(prompt,tools)
            confirmed_wizard_run = "Strukturierte Vorgaben fuer den Engineering-Agenten:" in prompt and "per Wizard-Uebernehmen bestaetigt" in prompt
            status, text = "INCOMPLETE", "Bitte beschreibe das gewünschte Engineering-Ergebnis oder wähle ein Objekt aus."
            if self.reasoner:
                for step in range(self.max_steps):
                    decision = await self.reasoner.next(messages, context, allowed)
                    if not decision.get("calls"):
                        if confirmed_wizard_run and not proposals:
                            text = ("Der bestätigte Auftrag wurde analysiert, aber es wurde kein prüfbarer Änderungs- oder Workload-Aufruf erzeugt. "
                                    "Der kanonische Projektstand ist unverändert; die Massenanlage benötigt einen passenden serverseitigen Generator.")
                            status = "INCOMPLETE"
                        else:
                            text = decision.get("text") or text
                            # A language-model sentence cannot mark the workload complete.
                            status = "READY_FOR_REVIEW" if proposals and all(p["status"]=="VALIDATED" for p in proposals.values()) else "ANSWERED" if not proposals and traces and all(t["status"] == "SUCCESS" for t in traces) else "INCOMPLETE"
                        break
                    messages.append(decision["assistant_message"])
                    for tool_call in decision["calls"]:
                        name, arguments = tool_call["name"], tool_call["arguments"]
                        if name not in {tool["name"] for tool in allowed}:
                            result = ToolResult(success=False,status="PERMISSION_DENIED",findings=[{"message":"Werkzeug nicht verfügbar."}])
                        else:
                            result = await call(name, arguments.get("request", arguments))
                        messages.append({"role":"tool","tool_call_id":tool_call["id"],"content":result.model_dump_json()})
                        if result.success and isinstance(result.data,dict):
                            if name == "discover_engineering_tools":
                                discovered = {item["name"] for item in result.data.get("tools",[])}
                                current = {item["name"] for item in allowed}
                                allowed.extend(tool for tool in tools if tool["name"] in discovered-current and tool["name"]!="apply_approved_proposal")
                            if result.data.get("proposal_id"):
                                checked = await validate_proposal(result.data)
                                messages[-1]["content"] = result.model_copy(update={"data":checked}).model_dump_json()
                            if result.data.get("agent_response"):
                                response = result.data["agent_response"]
                                event(response["type"],**{k:v for k,v in response.items() if k!="type"})
                                return {"run_id":run_id,"status":"BLOCKED","events":events,"context":context.model_dump(),"trace":traces}
                    event(
                        "PROGRESS",
                        status="IN_PROGRESS",
                        text=f"Arbeitsschritt {step+1} geprüft.",
                        workload=reasoning_workload_progress(step, self.max_steps),
                    )
            else:
                result = await call("inspect_findings")
                event("RESULT", text="Projektprüfung", data=result.data)
                text = "Die Projektprüfung ist ausgeführt. Für freie Fragen wird der konfigurierte lokale Sprachmodelldienst benötigt."
        for proposal in proposals.values():
            event("APPROVAL", proposal=proposal, text=proposal["rationale"])
        event("RESULT", status=status, text=text)
        return {"run_id":run_id,"status":status,"text":text,"events":events,"proposals":list(proposals.values()),
                "context":context.model_dump(),"trace":traces}
