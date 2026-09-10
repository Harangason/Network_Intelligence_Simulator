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


def requests_model_change(prompt: str) -> bool:
    """Conservative intent boundary; model prose cannot grant itself a write."""
    # Explanations about editing are read requests, unlike "Kannst du ... anlegen?".
    if re.match(r'\s*(?:wie\b|warum\b|wann\b|weshalb\b|erkläre\b|erkl[aä]r\b|welche\b|zeige\b|liste\b|how\b|why\b|explain\b|show\b|list\b)', prompt, re.I) and not re.search(r'\b(?:und|and|then|anschließend)\s+(?:erstell|erzeug|änder|lösch|entfern|create|update|delete|remove)\w*', prompt, re.I):
        return False
    return bool(re.search(
        r'\b(?:erzeug\w*|erstell\w*|anleg\w*|anzulegen|lege\b.{0,180}\ban\b|'
        r'hinzufüg\w*|hinzufueg\w*|füg\w*|fueg\w*|änder\w*|aender\w*|'
        r'lösch\w*|loesch\w*|entfern\w*|ersetz\w*|benenn\w*|umbauen|'
        r'implementier\w*|reparier\w*|beheb\w*|generier\w*|modellier\w*|benötige|brauche|'
        r'create\w*|add|update\w*|delete\w*|remove\w*|replace\w*|rename\w*|fix|build|generate\w*)\b',
        prompt, re.I | re.S,
    ))


def unsupported_change_claim(text: str) -> bool:
    return bool(re.search(r'\b(?:angelegt|erstellt|erzeugt|geändert|gelöscht|entfernt|übernommen|'
                          r'created|updated|deleted|removed|applied)\b', text, re.I))


class EngineeringAgent:
    async def analyze_trace_root_cause(self, job_id: str, **options):
        return await self.client.call("analyze_trace_root_cause", {"job_id": job_id, **options})

    async def explain_simulation_failure(self, job_id: str, **options):
        return await self.client.call("explain_simulation_failure", {"job_id": job_id, **options})

    async def investigate_deadline_miss(self, job_id: str, **options):
        return await self.client.call("investigate_deadline_miss", {"job_id": job_id, **options})

    async def analyze_fault_effects(self, job_id: str, **options):
        return await self.client.call("analyze_fault_effects", {"job_id": job_id, **options})

    async def compare_simulation_runs(self, before_reasoning_id: str, after_reasoning_id: str):
        return await self.client.call("compare_simulation_runs", {"before_reasoning_id": before_reasoning_id, "after_reasoning_id": after_reasoning_id})

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

        # Explicit trace investigation bypasses generator and approval continuation.
        job_match = re.search(r"\b[a-f0-9]{32}\b", prompt, re.I)
        if job_match and re.search(r"ursach|reasoning|root.?cause|deadline|fault.*analys|fehler.*erkl", prompt, re.I):
            tool = "investigate_deadline_miss" if re.search(r"deadline", prompt, re.I) else "analyze_trace_root_cause"
            result = await call(tool, {"job_id": job_match.group(), "goal": prompt[:2000]})
            complete = result.success and result.data.get("completion_status") in {"COMPLETE", "NO_ANOMALY_IN_WINDOW"} and result.data.get("validation_status") == "CURRENT"
            text = result.data.get("conclusion", "Ursachenanalyse konnte nicht ausgeführt werden.") if result.success else "Ursachenanalyse konnte nicht ausgeführt werden."
            if result.success:
                event("FINDING", text=text, metadata={"reasoning_id": result.data["reasoning_id"],
                    "completion_status": result.data["completion_status"], "validation_status": result.data["validation_status"]})
            event("RESULT", status="ANSWERED" if complete else "INCOMPLETE", text=text)
            return {"run_id": run_id, "status": "ANSWERED" if complete else "INCOMPLETE", "text": text,
                    "events": events, "context": context.model_dump(), "trace": traces, "proposals": []}

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
        if (confirmed_wizard and target_index >= 0 and all(
                workflow_statuses.get(step) in {'COMPLETE', 'APPROVED', 'WARNING'}
                for step in workflow_order[:target_index + 1])):
            text = 'Alle beauftragten Workflow-Schritte sind bereits vollständig und aktuell. Es wurde kein zusätzlicher Lauf gestartet.'
            event('RESULT', status='COMPLETED', text=text)
            return {'run_id': run_id, 'status': 'COMPLETED', 'text': text, 'events': events,
                    'context': context.model_dump(), 'trace': traces, 'proposals': []}
        if confirmed_wizard and target_index >= workflow_order.index('routing') and not routing_complete:
            if project.data.get('wizard_communication', {}).get('complete') is False:
                result = await call('generate_wizard_communication_contract', {'prompt': prompt})
                if result.success and result.data.get('status') != 'UNCHANGED':
                    proposal = await validate_proposal(result.data)
                    valid = proposal.get('status') == 'VALIDATED'
                    text = 'Kommunikationsplan vor dem Routing prüfen und übernehmen.'
                    event('APPROVAL', proposal=proposal, text=text)
                    status = 'READY_FOR_REVIEW' if valid else 'INCOMPLETE'
                    event('RESULT', status=status, text=text)
                    return {'run_id': run_id, 'status': status, 'text': text, 'events': events,
                            'context': context.model_dump(), 'trace': traces, 'proposals': list(proposals.values())}
                if not result.success:
                    text = 'Kommunikationsplanung unvollständig: ' + '; '.join(str(f.get('message', '')) for f in result.findings)
                    event('RESULT', status='INCOMPLETE', text=text)
                    return {'run_id': run_id, 'status': 'INCOMPLETE', 'text': text, 'events': events,
                            'context': context.model_dump(), 'trace': traces, 'proposals': []}
            routing_check = project.data.get('artifact_checks', {}).get('routing', {})
            counts = routing_check.get('counts') or {}
            coverage = routing_check.get('coverage') or {}
            if (counts.get('total', 0) > 0 and counts.get('approved') == counts.get('total')
                    and counts.get('valid') == counts.get('total') and coverage.get('complete') is False
                    and not project.data.get('wizard_communication', {}).get('complete')):
                text = (f"Alle {counts['total']} vorhandenen Routen sind bereits valide und freigegeben. "
                        f"Im Simulationsumfang fehlen bestätigte Transporte für {len(coverage.get('missing_message_ids') or [])} Nachrichten "
                        f"und {len(coverage.get('missing_signal_ids') or [])} Signale. "
                        "Bitte die fehlenden Empfänger bzw. Transportanforderungen fachlich bestätigen oder "
                        "im Preflight einen begründeten kleineren Simulationsumfang speichern. "
                        "Bereits freigegebene Routen werden nicht erneut erzeugt.")
                event('FINDING', severity='ERROR', text=text, metadata={'coverage': coverage})
                event('RESULT', status='INCOMPLETE', text=text)
                return {'run_id': run_id, 'status': 'INCOMPLETE', 'text': text, 'events': events,
                        'context': context.model_dump(), 'trace': traces, 'proposals': []}
            event('PROGRESS', status='PLANNING', text='Routing aus dem bestätigten Systemcluster-Graph vorbereiten.')
            result = await call('generate_wizard_routing', {'prompt': prompt})
            if result.success and result.data.get('status') in {'APPLIED', 'UNCHANGED'}:
                routing_check = project.data.get('artifact_checks', {}).get('routing', {})
                coverage = routing_check.get('coverage') or {}
                missing_messages = len(coverage.get('missing_message_ids') or [])
                missing_signals = len(coverage.get('missing_signal_ids') or [])
                details = (f'{missing_messages} Nachrichten und {missing_signals} Signale ohne abgedeckten Transport '
                           'im gespeicherten Simulationsumfang.' if coverage and not coverage.get('complete') else
                           f"Noch offene Routing-Prüfungen: {routing_check.get('counts') or {}}.")
                text = ('Die Routen aus diesem bestätigten Auftrag wurden bereits übernommen. '
                        f'Die Routing-Prüfung ist weiterhin unvollständig: {details} '
                        'Bitte die fehlenden Empfänger bzw. Transportanforderungen fachlich bestätigen oder '
                        'im Preflight einen begründeten kleineren Simulationsumfang speichern. '
                        'Der bestehende Vorschlag wird nicht erneut zur Freigabe angeboten.')
                event('FINDING', severity='ERROR', text=text, metadata={'coverage': coverage})
                event('RESULT', status='INCOMPLETE', text=text)
                return {'run_id': run_id, 'status': 'INCOMPLETE', 'text': text, 'events': events,
                        'context': context.model_dump(), 'trace': traces, 'proposals': []}
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

        if (confirmed_wizard and target_index >= workflow_order.index('parameters')
                and topology_complete and not parameters_complete):
            event('PROGRESS', status='PLANNING', text='Technologieabhängige Parameter-Defaults aus der Registry übernehmen.')
            result = await call('generate_wizard_parameters', {'prompt': prompt})
            parameters_complete = bool(
                result.success and (result.data.get('artifact_check') or {}).get('complete')
            )
            if not parameters_complete:
                status = 'INCOMPLETE'
                text = 'Die technologieabhängigen Parameter konnten nicht vollständig gespeichert werden. ' + '; '.join(
                    str(f.get('message', '')) for f in result.findings)
                event('RESULT', status=status, text=text)
                return {'run_id': run_id, 'status': status, 'text': text, 'events': events,
                        'context': context.model_dump(), 'trace': traces, 'proposals': []}
            technology_count = len(result.data.get('technology_ids') or [])
            field_count = len(result.data.get('parameters') or {})
            event('PROGRESS', status='VALIDATING',
                  text=f'{field_count} Parameterfelder für {technology_count} Technologien gespeichert.',
                  workload={'completed': field_count, 'total': field_count})
            if target_index == workflow_order.index('parameters'):
                status = 'COMPLETED'
                text = 'Die technologieabhängigen Parameter-Defaults sind vollständig im kanonischen Projektstand gespeichert.'
                event('RESULT', status=status, text=text)
                return {'run_id': run_id, 'status': status, 'text': text, 'events': events,
                        'context': context.model_dump(), 'trace': traces, 'proposals': []}

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
                capacity_networks = (result.data.get('results') or {}).get('networks') or []
                physical_segment_ids = {
                    str(item.get('network_id') or '') for item in capacity_networks if isinstance(item, dict)
                }
                confirmed_gateway_segments = bool(re.search(
                    r'^- Netzarchitektur-ID:\s*gateway_ecu_segments\s*$', prompt, re.I | re.M
                ))
                segment_rule_missing = confirmed_gateway_segments and not any(
                    re.search(r'-S\d+$', network_id, re.I) for network_id in physical_segment_ids
                )
                local_io_rule_missing = confirmed_gateway_segments and not any(
                    '-IO-' in network_id.upper() for network_id in physical_segment_ids
                )
                if segment_rule_missing or local_io_rule_missing:
                    repair = await call('generate_wizard_network', {'prompt': prompt})
                    if repair.success and repair.data.get('status') not in {'APPLIED', 'UNCHANGED'}:
                        proposal = await validate_proposal(repair.data)
                        valid = proposal.get('status') == 'VALIDATED'
                        event('APPROVAL', proposal=proposal, text=proposal['rationale'])
                        status = 'READY_FOR_REVIEW' if valid else 'INCOMPLETE'
                        text = (
                            ('Die freigegebene Gateway-Segmentregel war in der physischen Topologie noch nicht '
                             'materialisiert. Die korrigierte Netzaufteilung mit den konfigurierten Teilnehmergrenzen je '
                             'Segment ist geprüft und wartet auf Übernahme.'
                             if segment_rule_missing else
                             'Sensor-/Aktor-I/O war noch dem gemeinsamen Controller-Backbone zugerechnet. '
                             'Die geprüfte Topologie trennt lokale I/O-Segmente vom freigegebenen Systembus '
                             'und wartet auf Übernahme.')
                            if valid else
                            'Die aus dem Capacity-Befund abgeleitete Topologie-Reparatur enthält noch '
                            'Validierungsfehler.'
                        )
                        event('RESULT', status=status, text=text)
                        return {'run_id': run_id, 'status': status, 'text': text, 'events': events,
                                'context': context.model_dump(), 'trace': traces,
                                'proposals': list(proposals.values())}
                remediation = await call('plan_capacity_remediation', {'prompt': prompt})
                if remediation.success:
                    branch_plans = remediation.data.get('networks') or []
                    split_plans = [
                        item for item in branch_plans
                        if item.get('decision') == 'SPLIT_CURRENT_TECHNOLOGY'
                    ]
                    migration_plans = [
                        item for item in branch_plans
                        if item.get('decision') == 'MIGRATE_TECHNOLOGY'
                    ]
                    if split_plans:
                        repair = await call('generate_capacity_network_repair', {'prompt': prompt})
                        if repair.success:
                            proposal = await validate_proposal(repair.data)
                            valid = proposal.get('status') == 'VALIDATED'
                            event('APPROVAL', proposal=proposal, text=proposal['rationale'])
                            status = 'READY_FOR_REVIEW' if valid else 'INCOMPLETE'
                            text = (
                                f'{len(split_plans)} überlastete physische Zweige wurden paketweise analysiert. '
                                'Das Tool hat Segmentanzahl und Ressourcenbedarf aus der Ziel-Buslast bestimmt; '
                                'Bestand und zusätzliche Planungsressourcen sind im Vorschlag ausgewiesen. '
                                'Die geprüfte Topologie wartet auf Übernahme, nicht auf eine manuell geschätzte Segmentanzahl.'
                                + (
                                    f' Zusätzlich benötigen {len(migration_plans)} Zweige einen separat '
                                    'freizugebenden Technologiewechsel einschließlich Teilnehmer- und '
                                    'Gateway-Interfaces.'
                                    if migration_plans else ''
                                )
                                if valid else
                                'Der paketweise Capacity-Reparaturvorschlag enthält noch Validierungsfehler.'
                            )
                            event('RESULT', status=status, text=text)
                            return {'run_id': run_id, 'status': status, 'text': text, 'events': events,
                                    'context': context.model_dump(), 'trace': traces,
                                    'proposals': list(proposals.values())}
                    if migration_plans:
                        details = '; '.join(
                            f"{item.get('network_id')}: {item.get('protocol')} → {item.get('selected_protocol')}"
                            for item in migration_plans
                        )
                        status = 'INCOMPLETE'
                        text = (
                            'Die Zweiganalyse hat einen geeigneten Technologiewechsel gefunden, aber keine '
                            f'zulässige automatische Interface-Migration: {details}. Teilnehmer- und '
                            'Gateway-Interfaces müssen vor der Topologieänderung bestätigt werden.'
                        )
                        event('RESULT', status=status, text=text)
                        return {'run_id': run_id, 'status': status, 'text': text, 'events': events,
                                'context': context.model_dump(), 'trace': traces, 'proposals': []}
                status = 'INCOMPLETE'
                unresolved = remediation.data.get('unresolved') if remediation.success else []
                detail = f" {'; '.join(str(item) for item in unresolved[:3])}" if unresolved else ''
                text = 'Capacity & Timing wurde berechnet, enthält aber technisch nicht auflösbare Kapazitätsbefunde.' + detail
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
            validation_complete = True
            if target_index == workflow_order.index('validation'):
                text = 'Der Workflow-Preflight ist abgeschlossen.'
                event('RESULT', status='COMPLETED', text=text)
                return {'run_id': run_id, 'status': 'COMPLETED', 'text': text, 'events': events,
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
            if status != 'READY_TO_CONTINUE':
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
            change_requested = requests_model_change(prompt)
            evidence_retries = 0
            status, text = "INCOMPLETE", "Bitte beschreibe das gewünschte Engineering-Ergebnis oder wähle ein Objekt aus."
            if self.reasoner:
                for step in range(self.max_steps):
                    decision = await self.reasoner.next(messages, context, allowed)
                    if not decision.get("calls"):
                        reviewed_changes = bool(proposals) and all(p.get('status') == 'VALIDATED' and p.get('changes') for p in proposals.values())
                        if change_requested and not proposals and evidence_retries < min(2, self.max_repairs) and step + 1 < self.max_steps:
                            evidence_retries += 1
                            messages.append(decision.get('assistant_message') or {'role': 'assistant', 'content': decision.get('text', '')})
                            messages.append({'role': 'system', 'content':
                                'Für den Änderungsauftrag fehlt ein durch Werkzeuge erzeugter und validierter Vorschlag. '
                                'Nutze discover_engineering_tools und einen passenden Generator oder stelle mit ask_engineering_question eine notwendige Fachfrage. '
                                'Behaupte keine Erstellung oder Übernahme anhand einer Textantwort.'})
                            continue
                        if confirmed_wizard_run and not proposals:
                            text = ("Der bestätigte Auftrag wurde analysiert, aber es wurde kein prüfbarer Änderungs- oder Workload-Aufruf erzeugt. "
                                    "Der kanonische Projektstand ist unverändert; die Massenanlage benötigt einen passenden serverseitigen Generator.")
                            status = "INCOMPLETE"
                        elif proposals:
                            status = 'READY_FOR_REVIEW' if reviewed_changes else 'INCOMPLETE'
                            text = ('Der Änderungsvorschlag wurde erzeugt und validiert. Die Änderungen warten auf deine Freigabe und Übernahme.'
                                    if reviewed_changes else 'Der Änderungsvorschlag ist noch nicht vollständig validiert. Bitte die konkreten Findings prüfen.')
                        elif change_requested or unsupported_change_claim(decision.get('text') or ''):
                            status = 'INCOMPLETE'
                            text = 'Für die gewünschte Änderung liegt noch kein validierter Vorschlag vor. Es wurde keine Modelländerung übernommen. Bitte die fehlenden Angaben oder verfügbaren Werkzeuge prüfen.'
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
                        messages.append({"role":"tool","tool_call_id":tool_call["id"],"tool_name":name,"content":result.model_dump_json()})
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
